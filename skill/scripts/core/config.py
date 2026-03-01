"""Configuration loader.

Priority: env > config.local.json > config.json
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from .errors import ConfigurationError


@dataclass
class Settings:
    api_url: str
    token: str
    token_file: str
    forbidden_notebooks: List[str]
    main_notebook_id: str
    read_guard_ttl_seconds: int
    open_doc_char_limit: int
    write_log_path: str
    read_guard_cache_path: str


SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
LOCAL_CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.local.json")


def _read_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _env_list(value: str) -> List[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def _to_int(raw: Any, default: int) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _read_secret_file(path: str) -> str:
    try:
        resolved = Path(path).expanduser()
        if not resolved.exists():
            return ""
        return resolved.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def load_settings() -> Settings:
    base = _read_json(CONFIG_PATH)
    local = _read_json(LOCAL_CONFIG_PATH)
    data: Dict[str, Any] = {**base, **local}

    env_api_url = os.environ.get("SIYUAN_API_URL")
    env_token = os.environ.get("SIYUAN_TOKEN")
    env_token_file = os.environ.get("SIYUAN_TOKEN_FILE")
    env_forbidden = os.environ.get("SIYUAN_FORBIDDEN_NOTEBOOKS")
    env_main_notebook_id = os.environ.get("SIYUAN_MAIN_NOTEBOOK_ID")
    env_guard_ttl = os.environ.get("SIYUAN_READ_GUARD_TTL_SECONDS")
    env_open_doc_limit = os.environ.get("SIYUAN_OPEN_DOC_CHAR_LIMIT")
    env_log_path = os.environ.get("SIYUAN_WRITE_LOG_PATH")
    env_cache_path = os.environ.get("SIYUAN_READ_GUARD_CACHE_PATH")

    if env_api_url:
        data["api_url"] = env_api_url
    if env_token is not None:
        data["token"] = env_token
    if env_token_file is not None:
        data["token_file"] = env_token_file
    if env_forbidden:
        data["forbidden_notebooks"] = _env_list(env_forbidden)
    if env_main_notebook_id is not None:
        data["main_notebook_id"] = env_main_notebook_id
    if env_guard_ttl is not None:
        data["read_guard_ttl_seconds"] = _to_int(env_guard_ttl, 3600)
    if env_open_doc_limit is not None:
        data["open_doc_char_limit"] = _to_int(env_open_doc_limit, 15000)
    if env_log_path is not None:
        data["write_log_path"] = env_log_path
    if env_cache_path is not None:
        data["read_guard_cache_path"] = env_cache_path

    api_url = str(data.get("api_url", "")).strip().rstrip("/")
    if not api_url:
        raise ConfigurationError("缺少配置: api_url")

    token_file = str(data.get("token_file", "~/.config/siyuan/api_token")).strip()
    token = str(data.get("token", "")).strip()
    if not token and token_file:
        token = _read_secret_file(token_file)

    settings = Settings(
        api_url=api_url,
        token=token,
        token_file=token_file,
        forbidden_notebooks=list(data.get("forbidden_notebooks", []) or []),
        main_notebook_id=str(data.get("main_notebook_id", "")).strip(),
        read_guard_ttl_seconds=_to_int(data.get("read_guard_ttl_seconds"), 3600),
        open_doc_char_limit=_to_int(data.get("open_doc_char_limit"), 15000),
        write_log_path=str(data.get("write_log_path", ".siyuan-writes.log")),
        read_guard_cache_path=str(data.get("read_guard_cache_path", ".siyuan-read-guard-cache.json")),
    )
    return settings


SETTINGS = load_settings()
