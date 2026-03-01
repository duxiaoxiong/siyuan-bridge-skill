"""Read-before-write guard with optimistic version checks."""

import json
import os
import time
from typing import Any, Dict

from ..core.errors import ConflictError, GuardError


class ReadGuard:
    def __init__(self, cache_file: str, ttl_seconds: int = 3600):
        self.cache_file = cache_file
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Dict[str, Any]] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        if not os.path.exists(self.cache_file):
            self.cache = {}
            return
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self.cache = payload.get("docs", {}) if isinstance(payload, dict) else {}
        except Exception:
            self.cache = {}

    def _save_cache(self) -> None:
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        payload = {"version": 1, "docs": self.cache}
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def prune(self) -> None:
        now = time.time()
        expired = []
        for doc_id, meta in self.cache.items():
            if now - float(meta.get("ts", 0)) > self.ttl_seconds:
                expired.append(doc_id)
        for doc_id in expired:
            self.cache.pop(doc_id, None)
        if expired:
            self._save_cache()

    def register_read(self, doc_id: str, updated_at: str, source: str = "unknown") -> None:
        self.prune()
        self.cache[doc_id] = {
            "doc_id": doc_id,
            "ts": time.time(),
            "updated_at": updated_at or "",
            "source": source,
            "last_write_at": 0,
        }
        self._save_cache()

    def ensure_write_allowed(
        self,
        doc_id: str,
        current_updated_at: str,
        operation: str,
        allow_unsafe: bool = False,
    ) -> None:
        if allow_unsafe:
            return

        self.prune()
        meta = self.cache.get(doc_id)
        if not meta:
            raise GuardError(
                f"读后写围栏: 执行 {operation} 前必须先读取文档 {doc_id}。"
                f"请先运行 open-doc {doc_id} readable|patchable"
            )

        if time.time() - float(meta.get("ts", 0)) > self.ttl_seconds:
            raise GuardError(
                f"读后写围栏: 文档 {doc_id} 的读取已过期（TTL={self.ttl_seconds}s），请重新读取。"
            )

        cached_updated_at = str(meta.get("updated_at", ""))
        if cached_updated_at and current_updated_at and cached_updated_at != current_updated_at:
            raise ConflictError(
                f"读后写围栏: 文档 {doc_id} 自读取后被修改。"
                f"读取版本={cached_updated_at}, 当前版本={current_updated_at}"
            )

    def mark_write(self, doc_id: str, new_updated_at: str) -> None:
        meta = self.cache.get(doc_id)
        if not meta:
            return
        meta["last_write_at"] = time.time()
        meta["updated_at"] = str(new_updated_at or "")
        meta["ts"] = time.time()
        self._save_cache()
