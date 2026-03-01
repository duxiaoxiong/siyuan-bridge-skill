"""Core Siyuan API client with safety guard integration."""

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from .config import SETTINGS, Settings, load_settings
from .errors import ApiError, ValidationError
from .id_utils import escape_sql_value
from .logging_utils import append_write_log, resolve_path
from ..guards.read_guard import ReadGuard


class SiyuanClient:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or load_settings()
        self.api_url = self.settings.api_url.rstrip("/")
        self.headers = {
            "Content-Type": "application/json",
        }
        if self.settings.token:
            self.headers["Authorization"] = f"Token {self.settings.token}"

        self.scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.write_log_path = resolve_path(self.scripts_dir, self.settings.write_log_path)
        cache_path = resolve_path(self.scripts_dir, self.settings.read_guard_cache_path)
        self.read_guard = ReadGuard(cache_path, self.settings.read_guard_ttl_seconds)
        self.allow_unsafe_write = os.environ.get("SIYUAN_ALLOW_UNSAFE_WRITE", "").lower() == "true"

    def _post(self, path: str, data: Optional[Dict[str, Any]] = None, timeout: int = 30) -> Dict[str, Any]:
        url = f"{self.api_url}{path}"
        req = urllib.request.Request(
            url,
            data=json.dumps(data or {}).encode("utf-8"),
            headers=self.headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as res:
                payload = json.loads(res.read().decode("utf-8", errors="replace"))
        except urllib.error.URLError as e:
            return {"code": -1, "msg": str(e), "data": None}
        except Exception as e:
            return {"code": -1, "msg": f"响应解析失败: {e}", "data": None}

        if not isinstance(payload, dict):
            return {"code": -1, "msg": "响应不是 JSON object", "data": payload}
        payload.setdefault("code", -1)
        payload.setdefault("msg", "")
        return payload

    def _require_success(self, res: Dict[str, Any], action: str) -> Dict[str, Any]:
        if res.get("code") != 0:
            raise ApiError(f"{action} 失败: {res.get('msg')}")
        return res

    def _is_forbidden(self, value: str) -> bool:
        text = str(value or "").lower()
        for forbidden in self.settings.forbidden_notebooks:
            if forbidden.lower() in text:
                return True
        return False

    def _guard_doc_write(self, doc_id: str, operation: str) -> None:
        meta = self.get_doc_meta(doc_id)
        current_updated = meta.get("updated", "") if meta else ""
        self.read_guard.ensure_write_allowed(
            doc_id=doc_id,
            current_updated_at=current_updated,
            operation=operation,
            allow_unsafe=self.allow_unsafe_write,
        )

    def _mark_read(self, doc_id: str, source: str = "unknown") -> None:
        meta = self.get_doc_meta(doc_id)
        self.read_guard.register_read(doc_id, meta.get("updated", "") if meta else "", source=source)

    def _mark_write(self, doc_id: str) -> None:
        # Doc updated timestamp can lag briefly after write. Retry a few times to
        # reduce false conflict detection on consecutive writes.
        cached = self.read_guard.cache.get(doc_id, {}) if isinstance(self.read_guard.cache, dict) else {}
        prev_updated = str(cached.get("updated_at", ""))
        latest_updated = ""
        for _ in range(6):
            meta = self.get_doc_meta(doc_id)
            latest_updated = meta.get("updated", "") if meta else ""
            if latest_updated and latest_updated != prev_updated:
                break
            time.sleep(0.05)

        if not latest_updated or latest_updated == prev_updated:
            latest_updated = ""
        self.read_guard.mark_write(doc_id, latest_updated)

    def _log_write(self, action: str, payload: Dict[str, Any]) -> None:
        append_write_log(self.write_log_path, action, payload)

    def get_version(self) -> Dict[str, Any]:
        return self._post("/api/system/version")

    def ls_notebooks(self) -> Dict[str, Any]:
        res = self._post("/api/notebook/lsNotebooks")
        if res.get("code") == 0:
            notebooks = res.get("data", {}).get("notebooks", [])
            filtered = [nb for nb in notebooks if not self._is_forbidden(nb.get("name", ""))]
            res["data"]["notebooks"] = filtered
        return res

    def sql_query(self, stmt: str) -> Dict[str, Any]:
        return self._post("/api/query/sql", {"stmt": stmt})

    def search(self, keyword: str, limit: int = 20) -> Dict[str, Any]:
        safe_kw = escape_sql_value(keyword)
        sql = (
            "SELECT id, content, hpath, type, root_id FROM blocks "
            f"WHERE content LIKE '%{safe_kw}%' LIMIT {int(limit)}"
        )
        res = self.sql_query(sql)
        if res.get("code") == 0:
            res["data"] = [b for b in res.get("data", []) if not self._is_forbidden(b.get("hpath", ""))]
        return res

    def search_docs(self, keyword: str, limit: int = 10) -> Dict[str, Any]:
        safe_kw = escape_sql_value(keyword)
        sql = (
            "SELECT id, content, hpath, created, updated FROM blocks "
            f"WHERE content LIKE '%{safe_kw}%' AND type='d' LIMIT {int(limit)}"
        )
        return self.sql_query(sql)

    def get_doc_meta(self, doc_id: str) -> Dict[str, Any]:
        safe_id = escape_sql_value(doc_id)
        sql = (
            "SELECT id, content, hpath, updated, box, type FROM blocks "
            f"WHERE id='{safe_id}' LIMIT 1"
        )
        res = self.sql_query(sql)
        if res.get("code") == 0 and res.get("data"):
            return res["data"][0]
        return {}

    def get_block(self, block_id: str) -> Dict[str, Any]:
        safe_id = escape_sql_value(block_id)
        sql = f"SELECT * FROM blocks WHERE id='{safe_id}' LIMIT 1"
        res = self.sql_query(sql)
        if res.get("code") == 0 and res.get("data"):
            return res["data"][0]
        return {}

    def resolve_root_doc_id(self, block_id: str) -> str:
        block = self.get_block(block_id)
        if not block:
            raise ValidationError(f"找不到块: {block_id}")
        if block.get("type") == "d":
            return block.get("id", "")
        root_id = block.get("root_id", "")
        if not root_id:
            raise ValidationError(f"无法解析根文档 ID: {block_id}")
        return root_id

    def resolve_doc_id_from_av_id(self, av_id: str) -> str:
        safe_av_id = escape_sql_value(av_id)
        sql = (
            "SELECT root_id FROM blocks "
            "WHERE type='av' "
            f"AND markdown LIKE '%data-av-id=\"{safe_av_id}\"%' LIMIT 1"
        )
        res = self.sql_query(sql)
        if res.get("code") == 0 and res.get("data"):
            return res["data"][0].get("root_id", "")
        return ""

    def export_md(self, doc_id: str) -> Dict[str, Any]:
        res = self._post("/api/export/exportMdContent", {"id": doc_id})
        if res.get("code") == 0:
            self._mark_read(doc_id, source="export-md")
        return res

    def create_doc(self, notebook_id: str, path: str, markdown: str = "") -> Dict[str, Any]:
        if self._is_forbidden(notebook_id) or self._is_forbidden(path):
            raise ValidationError(f"禁止访问笔记本或路径: {notebook_id} {path}")
        payload = {"notebook": notebook_id, "path": path, "markdown": markdown}
        self._log_write("create_doc", payload)
        res = self._post("/api/filetree/createDocWithMd", payload)
        if res.get("code") == 0 and res.get("data"):
            self._mark_read(str(res["data"]), source="create-doc")
        return res

    def _guard_by_parent(self, parent_id: str, operation: str) -> str:
        doc_id = self.resolve_root_doc_id(parent_id)
        self._guard_doc_write(doc_id, operation)
        return doc_id

    def _guard_by_block(self, block_id: str, operation: str) -> str:
        doc_id = self.resolve_root_doc_id(block_id)
        self._guard_doc_write(doc_id, operation)
        return doc_id

    def insert_block(self, parent_id: str, data_type: str, data: str, previous_id: str = "") -> Dict[str, Any]:
        doc_id = self._guard_by_parent(parent_id, "insert-block")
        payload = {
            "dataType": data_type,
            "data": data,
            "parentID": parent_id,
            "previousID": previous_id,
        }
        self._log_write("insert_block", payload)
        res = self._post("/api/block/insertBlock", payload)
        if res.get("code") == 0:
            self._mark_write(doc_id)
        return res

    def append_block(self, parent_id: str, markdown: str) -> Dict[str, Any]:
        doc_id = self._guard_by_parent(parent_id, "append-block")
        payload = {"dataType": "markdown", "data": markdown, "parentID": parent_id}
        self._log_write("append_block", payload)
        res = self._post("/api/block/appendBlock", payload)
        if res.get("code") == 0:
            self._mark_write(doc_id)
        return res

    def prepend_block(self, parent_id: str, markdown: str) -> Dict[str, Any]:
        doc_id = self._guard_by_parent(parent_id, "prepend-block")
        payload = {"dataType": "markdown", "data": markdown, "parentID": parent_id}
        self._log_write("prepend_block", payload)
        res = self._post("/api/block/prependBlock", payload)
        if res.get("code") == 0:
            self._mark_write(doc_id)
        return res

    def insert_block_after(self, previous_id: str, markdown: str) -> Dict[str, Any]:
        doc_id = self._guard_by_block(previous_id, "insert-after")
        payload = {"dataType": "markdown", "data": markdown, "previousID": previous_id}
        self._log_write("insert_block_after", payload)
        res = self._post("/api/block/insertBlock", payload)
        if res.get("code") == 0:
            self._mark_write(doc_id)
        return res

    def update_block(self, block_id: str, content: str, data_type: str = "markdown") -> Dict[str, Any]:
        doc_id = self._guard_by_block(block_id, "update-block")
        payload = {"dataType": data_type, "data": content, "id": block_id}
        self._log_write("update_block", payload)
        res = self._post("/api/block/updateBlock", payload)
        if res.get("code") == 0:
            self._mark_write(doc_id)
        return res

    def delete_block(self, block_id: str) -> Dict[str, Any]:
        doc_id = self._guard_by_block(block_id, "delete-block")
        payload = {"id": block_id}
        self._log_write("delete_block", payload)
        res = self._post("/api/block/deleteBlock", payload)
        if res.get("code") == 0:
            self._mark_write(doc_id)
        return res

    def set_block_attrs(self, block_id: str, attrs: Dict[str, Any]) -> Dict[str, Any]:
        doc_id = self._guard_by_block(block_id, "set-block-attrs")
        payload = {"id": block_id, "attrs": attrs}
        self._log_write("set_block_attrs", payload)
        res = self._post("/api/attr/setBlockAttrs", payload)
        if res.get("code") == 0:
            self._mark_write(doc_id)
        return res

    def get_child_blocks(self, parent_id: str) -> Dict[str, Any]:
        return self._post("/api/block/getChildBlocks", {"id": parent_id})

    def move_block(self, block_id: str, parent_id: Optional[str] = None, previous_id: Optional[str] = None) -> Dict[str, Any]:
        doc_id = self._guard_by_block(block_id, "move-block")
        payload: Dict[str, Any] = {"id": block_id}
        if parent_id:
            payload["parentID"] = parent_id
        if previous_id:
            payload["previousID"] = previous_id
        self._log_write("move_block", payload)
        res = self._post("/api/block/moveBlock", payload)
        if res.get("code") == 0:
            self._mark_write(doc_id)
        return res

    def get_block_dom(self, block_id: str) -> Dict[str, Any]:
        return self._post("/api/block/getBlockDOM", {"id": block_id})

    def get_block_kramdown(self, block_id: str) -> Dict[str, Any]:
        return self._post("/api/block/getBlockKramdown", {"id": block_id})

    def post_with_guard(
        self,
        path: str,
        payload: Dict[str, Any],
        operation: str,
        doc_id: Optional[str] = None,
        log_action: Optional[str] = None,
    ) -> Dict[str, Any]:
        effective_doc_id = doc_id or ""
        if effective_doc_id:
            self._guard_doc_write(effective_doc_id, operation)
        if log_action:
            self._log_write(log_action, payload)
        res = self._post(path, payload)
        if res.get("code") == 0 and effective_doc_id:
            self._mark_write(effective_doc_id)
        return res


DEFAULT_CLIENT = SiyuanClient(SETTINGS)
