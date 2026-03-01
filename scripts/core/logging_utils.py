"""Logging helpers with UTF-8 safe writes."""

import json
import os
from datetime import datetime
from typing import Any


def resolve_path(base_dir: str, raw_path: str) -> str:
    path = raw_path or ".siyuan-writes.log"
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(base_dir, path))


def append_write_log(log_path: str, action: str, payload: Any) -> None:
    directory = os.path.dirname(log_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body = json.dumps(payload, ensure_ascii=False)
    line = f"[{timestamp}] {action}: {body}\n"
    with open(log_path, "a", encoding="utf-8", errors="replace") as f:
        f.write(line)
