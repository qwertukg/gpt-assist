import copy
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
                self.state: Dict[str, Any] = json.load(f)
        else:
            self.state = {}

        self.client = OpenAI(api_key=self.config.api_key)

        # Vector Store: берём из state или создаём
        self.vector_store_id = (
            self.state.get("vector_store_id")
            or self._ensure_vector_store(self.config.vector_store_name)
        )
        self.state["vector_store_id"] = self.vector_store_id

        # Роли -> prompt
        self.roles: Dict[str, str] = self.config.role_prompts

        # Контекст тредов: thread_id -> {"prev": str, "meta": dict}
        # при отсутствии — пустой словарь
        self.threads: Dict[str, Dict[str, Any]] = copy.deepcopy(self.state.get("threads", {}))

        # сохраняем всё, чтобы сразу был актуальный state.json
        self._dump_state()

    # ------------------------- helper: persist ---------------------------
    def _dump_state(self):
        """Пишет self._state на диск."""
        self.state["threads"] = copy.deepcopy(self.threads)
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

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


    # 2) create_thread — один thread на одну feature;
    #    если feature отсутствует или пустой → всегда новый thread.
    def create_thread(self, role: str, feature: str, version: str) -> str:
        """
        • Возвращаем существующий thread, когда feature совпадает.
        • При новом/пустом feature всегда создаётся новый thread.
        """

        # --- уже есть тред для этой фичи ---
        existing_feature_id = self.get_thread_id_by_feature(role, feature)

        if existing_feature_id:
            versions = self.threads[existing_feature_id]["meta"]["versions"]
            if version not in versions:
                versions.append(version)
            return existing_feature_id

        # --- новый тред ---
        tid = f"thr_{int(time.time() * 1000)}"
        self.threads[tid] = {
            "prev": "",
            "resp_id": "",
            "meta": {
                "role": role,
                "feature": feature,
                "versions": [version],
            },
        }
        return tid

    def get_thread_id_by_feature(self, role: str, feature: str) -> Optional[str]:
        for thread_id, thread_data in self.state.get("threads", {}).items():
            if thread_data.get("meta", {}).get("role") == role and thread_data["meta"]["feature"] == feature:
                return thread_id
        return None


    # ------------------------- chat -------------------------------------
    def send_message(self, role: str, thread_id: str, content: str) -> str:
        if role not in self.roles:
            raise ValueError(f"Unknown role: {role}")
        if thread_id not in self.threads:
            raise ValueError(f"Unknown thread_id {thread_id}")

        thread = self.threads[thread_id]
        meta = thread["meta"]
        role = meta["role"]
        feature = meta["feature"]
        versions = meta["versions"]
        last_response_id = self.threads[thread_id]["resp_id"] or None

        response = self.client.responses.create(
            model="gpt-4o-mini",
            instructions=f"""{self.roles[role]}
            
            Контекст: перед тобой изменения по фиче {feature}, с версиями {versions}.
            Это история последовательных изменений. Используй её, чтобы учитывать развитие кода и понимать текущую стадию.
            """,
            input=content,
            previous_response_id=last_response_id,
            tools=[{
                "type": "file_search",
                "vector_store_ids": [self.vector_store_id],
            }],
        )

        # print(f"resp_id: {last_response_id}")
        # print(f"response.id: {response.id}")
        # print(f"content: {content}")

        self.threads[thread_id]["resp_id"] = response.id
        self._dump_state()

        return response.output_text


    def clear_file_storage(self):
        files = self.client.files.list().data
        for f in files:
            print(f"Удаляю файл {f.id} ({f.filename})")
            self.client.files.delete(file_id=f.id)