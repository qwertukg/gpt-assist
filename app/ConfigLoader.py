import os
import json
from typing import Dict

# ------------------------- Константы путей -------------------------
CONFIG_PATH = "config.json"      # роли и их промпты
STATE_PATH = "roles_state.json"  # сохранённые ID ассистентов / стора

# ------------------------- ConfigLoader ----------------------------
class ConfigLoader:
    """Читает обязательный `config.json`.

    Формат:
    {
      "roles": {
        "AppSec": "prompt...",
        "TechLead": "prompt..."
      },
      "openai_api_key": "sk-...",          # либо переменная окружения
      "vector_store_name": "diff-store"     # опционально
    }
    """

    def __init__(self, path: str = CONFIG_PATH):
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Конфиг '{path}' не найден. Создайте файл согласно документации."
            )
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        if not data.get("roles"):
            raise ValueError("В config.json отсутствует ключ 'roles' или он пуст.")
        self.role_prompts: Dict[str, str] = data["roles"]
        self.api_key: str = data.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("API‑ключ не найден ни в config.json, ни в переменной окружения OPENAI_API_KEY.")
        self.vector_store_name: str = data.get("vector_store_name", "diff-store")

# ------------------------- RoleStateManager ------------------------
class RoleStateManager:
    """Сохраняет / загружает ID стора и ассистентов."""

    def __init__(self, path: str = STATE_PATH):
        self.path = path
        self.vector_store_id: str | None = None
        self.roles: Dict[str, str] = {}
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            self.vector_store_id = data.get("vector_store_id")
            self.roles = data.get("roles", {})

    def save(self):
        with open(self.path, "w", encoding="utf-8") as fp:
            json.dump({
                "vector_store_id": self.vector_store_id,
                "roles": self.roles,
            }, fp, ensure_ascii=False, indent=2)