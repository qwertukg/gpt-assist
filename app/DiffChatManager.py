import json
import os
import time
from pathlib import Path
from typing import Dict, Optional, Any

from openai import OpenAI

CONFIG_PATH = "config.json"
STATE_PATH = "state.json"


class ConfigLoader:
    """Читает заранее подготовленный config.json."""

    def __init__(self, path: str = CONFIG_PATH):
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        self.api_key: str = raw["OPENAI_API_KEY"]
        self.vector_store_name: str = raw.get("vector_store_name", "diff-store")
        self.role_prompts: Dict[str, str] = raw["roles"]  # {"TechLead": "...", ...}


class DiffChatManager:
    """
    Обёртка над Responses API + File Search с дисковой персистенцией.
    • сохраняет vector_store_id и состояние тредов в state.json
    """

    # ------------------------- init / bootstrap -------------------------
    def __init__(self,
                 *,
                 config_path: str = CONFIG_PATH,
                 state_path: str = STATE_PATH):
        self.config = ConfigLoader(config_path)
        self.state_path = Path(state_path)

        # загрузка state.json (если есть)
        if self.state_path.exists():
            with open(self.state_path, encoding="utf-8") as f:
                self._state: Dict[str, Any] = json.load(f)
        else:
            self._state = {}

        self.client = OpenAI(api_key=self.config.api_key)

        # Vector Store: берём из state или создаём
        self.vector_store_id = (
            self._state.get("vector_store_id")
            or self._ensure_vector_store(self.config.vector_store_name)
        )
        self._state["vector_store_id"] = self.vector_store_id

        # Роли -> prompt
        self.roles: Dict[str, str] = self.config.role_prompts

        # Контекст тредов: thread_id -> {"prev": str, "meta": dict}
        # при отсутствии — пустой словарь
        self._threads: Dict[str, Dict[str, Any]] = self._state.get("threads", {})

        # построим индекс feature → thread_id
        self._rebuild_index()

        # сохраняем всё, чтобы сразу был актуальный state.json
        self._dump_state()

    # ------------------------- helper: persist ---------------------------
    def _dump_state(self):
        """Пишет self._state на диск."""
        self._state["threads"] = self._threads
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)

    # ------------------------- vector store ------------------------------
    def _ensure_vector_store(self, name: str) -> str:
        for vs in self.client.vector_stores.list(limit=100).data:
            if vs.name == name:
                return vs.id
        return self.client.vector_stores.create(name=name).id

    def upload_diff_version(self, diff_path: str) -> str:
        """Загружает diff-файл и индексирует его в Vector Store."""
        with open(diff_path, "rb") as f:
            file_obj = self.client.files.create(file=f, purpose="assistants")
        self.client.vector_stores.file_batches.create_and_poll(
            self.vector_store_id,
            file_ids=[file_obj.id],
        )
        return file_obj.id

    # ------------------------ threads ------------------------
    def _rebuild_index(self) -> None:
        """map feature → thread_id, только для EXISTING тредов"""
        self._index = {
            data["meta"].get("feature"): tid
            for tid, data in self._threads.items()
            if data["meta"].get("feature")  # не пустой feature
        }

    # 2) create_thread — один thread на одну feature;
    #    если feature отсутствует или пустой → всегда новый thread.
    def create_thread(self, meta: Optional[Dict[str, str]] = None) -> str:
        """
        • Возвращаем существующий thread, когда feature совпадает.
        • При новом/пустом feature всегда создаётся новый thread.
        """
        meta = meta or {}
        feat: str = meta.get("feature") or ""  # '' если нет ключа
        commit = meta.get("commit")

        # --- уже есть тред для этой фичи ---
        if feat and feat in self._index:
            tid = self._index[feat]
            if commit:
                self._threads[tid]["meta"].setdefault("commits", []).append(commit)
                self._dump_state()
            return tid

        # --- новый тред ---
        tid = f"thr_{int(time.time() * 1000)}"
        self._threads[tid] = {
            "prev": "",
            "meta": {
                "feature": feat,  # может быть ''
                "commits": [commit] if commit else []
            },
        }
        self._rebuild_index()
        self._dump_state()
        return tid

    # ------------------------- chat -------------------------------------
    def send_message(self, role: str, thread_id: str, content: str) -> str:
        if role not in self.roles:
            raise ValueError(f"Unknown role: {role}")
        if thread_id not in self._threads:
            raise ValueError(f"Unknown thread_id {thread_id}")

        thread = self._threads[thread_id]
        prev_id = thread["prev"] or None  # '' → None
        meta_txt = ", ".join(
            f"{k}={v}" for k, v in thread["meta"].items()
        )

        response = self.client.responses.create(
            model="gpt-4o-mini",
            instructions=f"{self.roles[role]}\n\n[meta] {meta_txt}",
            input=content,
            previous_response_id=prev_id,
            tools=[{
                "type": "file_search",
                "vector_store_ids": [self.vector_store_id],
            }],
        )

        # --- сохраняем prev, ТОЛЬКО если фича уже была (len(commits) > 1)
        #     ИЛИ prev уже заполнен (это >2-й, >3-й … вызов) ---
        commits = thread["meta"].get("commits", [])
        if thread["meta"].get("feature") and (thread["prev"] or len(commits) > 1):
            thread["prev"] = response.id
            self._dump_state()

        return response.output_text
