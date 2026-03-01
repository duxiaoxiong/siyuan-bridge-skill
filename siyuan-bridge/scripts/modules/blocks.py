"""Block operations."""

from typing import Dict, List, Optional

from ..core.client import SiyuanClient
from ..core.errors import ValidationError
from ..core.id_utils import escape_sql_value
from ..formats.markdown_utils import (
    append_markdown_table_row,
    build_callout_markdown,
    extract_reference_tokens,
    inject_safe_embed_scope,
    mark_first_unchecked_task,
    normalize_embed_sql,
)


class BlockModule:
    def __init__(self, client: SiyuanClient):
        self.client = client

    def get_block_content(self, block_id: str, fmt: str = "markdown") -> Dict[str, object]:
        block = self.client.get_block(block_id)
        if not block:
            raise ValidationError(f"找不到块: {block_id}")

        doc_id = self.client.resolve_root_doc_id(block_id)
        self.client._mark_read(doc_id, source=f"block-get:{fmt}")

        mode = str(fmt or "markdown").strip().lower()
        if mode == "meta":
            keys = (
                "id",
                "type",
                "subtype",
                "root_id",
                "parent_id",
                "box",
                "hpath",
                "content",
                "name",
                "created",
                "updated",
                "sort",
            )
            data = {k: block.get(k, "") for k in keys}
            return {"code": 0, "msg": "", "data": data}

        if mode == "kramdown":
            res = self.client.get_block_kramdown(block_id)
            if res.get("code") != 0:
                return res
            return {"code": 0, "msg": "", "data": {"format": "kramdown", "content": res.get("data", {}).get("kramdown", "")}}

        if mode == "dom":
            res = self.client.get_block_dom(block_id)
            if res.get("code") != 0:
                return res
            return {"code": 0, "msg": "", "data": {"format": "dom", "content": res.get("data", {}).get("dom", "")}}

        content = block.get("markdown") or block.get("content", "")
        return {"code": 0, "msg": "", "data": {"format": "markdown", "content": content}}

    def _collect_markdown_for_target(self, block_id_or_doc_id: str) -> Dict[str, str]:
        block = self.client.get_block(block_id_or_doc_id)
        if not block:
            raise ValidationError(f"找不到块: {block_id_or_doc_id}")

        if block.get("type") == "d":
            safe_id = escape_sql_value(block_id_or_doc_id)
            sql = (
                "SELECT markdown FROM blocks "
                f"WHERE root_id='{safe_id}' AND id!='{safe_id}' ORDER BY sort ASC"
            )
            res = self.client.sql_query(sql)
            if res.get("code") != 0:
                raise ValidationError(f"读取文档内容失败: {res.get('msg')}")
            rows = res.get("data", []) or []
            text = "\n\n".join((r.get("markdown", "") or "") for r in rows)
            self.client._mark_read(block_id_or_doc_id, source="refs-extract:doc")
            return {"doc_id": block_id_or_doc_id, "text": text}

        doc_id = self.client.resolve_root_doc_id(block_id_or_doc_id)
        self.client._mark_read(doc_id, source="refs-extract:block")
        return {"doc_id": doc_id, "text": block.get("markdown", "") or block.get("content", "")}

    def extract_refs(self, block_id_or_doc_id: str) -> Dict[str, object]:
        payload = self._collect_markdown_for_target(block_id_or_doc_id)
        refs = extract_reference_tokens(payload["text"])
        return {
            "code": 0,
            "msg": "",
            "data": {
                "target_id": block_id_or_doc_id,
                "doc_id": payload["doc_id"],
                **refs,
            },
        }

    def create_callout(self, parent_id: str, callout_type: str, text: str) -> Dict[str, object]:
        markdown = build_callout_markdown(callout_type, text)
        return self.client.append_block(parent_id, markdown)

    def update_callout(self, block_id: str, callout_type: str, text: str) -> Dict[str, object]:
        markdown = build_callout_markdown(callout_type, text)
        return self.client.update_block(block_id, markdown, data_type="markdown")

    def create_safe_embed(
        self,
        parent_id: str,
        raw_sql: str,
        scope: str = "box",
        limit: int = 64,
    ) -> Dict[str, object]:
        doc_id = self.client.resolve_root_doc_id(parent_id)
        doc_meta = self.client.get_doc_meta(doc_id)
        scope_mode = str(scope or "box").strip().lower()

        scope_sql: Optional[str] = None
        if scope_mode == "box":
            box = escape_sql_value(doc_meta.get("box", ""))
            if box:
                scope_sql = f"box = '{box}'"
        elif scope_mode == "root":
            scope_sql = f"root_id = '{escape_sql_value(doc_id)}'"
        elif scope_mode == "none":
            scope_sql = None
        else:
            raise ValidationError(f"未知 scope: {scope_mode}，可选 box/root/none")

        try:
            merged_sql = inject_safe_embed_scope(
                raw_sql,
                scope_sql=scope_sql,
                default_limit=max(1, int(limit)),
            )
        except ValueError as e:
            raise ValidationError(str(e))

        markdown = "{{" + merged_sql + "}}"
        res = self.client.append_block(parent_id, markdown)
        if res.get("code") != 0:
            return res
        return {
            "code": 0,
            "msg": "",
            "data": {
                "scope": scope_mode,
                "doc_id": doc_id,
                "sql": normalize_embed_sql(merged_sql),
                "block_result": res.get("data"),
            },
        }

    def create_super_scaffold(
        self,
        parent_id: str,
        layout: str = "col",
        count: int = 2,
    ) -> Dict[str, object]:
        top = str(layout or "col").strip().lower()
        if top not in ("col", "row"):
            raise ValidationError("super scaffold 布局仅支持 col 或 row")
        total = max(1, int(count))
        child = "row" if top == "col" else "col"

        lines = [f"{{{{{{{top}"]
        for idx in range(total):
            lines.append(f"{{{{{{{child}")
            lines.append(f"Section {idx + 1}")
            lines.append("}}}")
            lines.append("")
        if lines[-1] == "":
            lines.pop()
        lines.append("}}}")
        markdown = "\n".join(lines)
        return self.client.append_block(parent_id, markdown)

    def append_table_row(self, block_id: str, cells: Optional[List[str]] = None) -> Dict[str, object]:
        block = self.client.get_block(block_id)
        if not block:
            raise ValidationError(f"找不到表格块: {block_id}")
        if block.get("type") != "t":
            raise ValidationError(f"目标块不是表格 type=t: {block_id}")

        markdown = block.get("markdown", "") or ""
        if not markdown:
            raise ValidationError("表格块 markdown 为空")
        try:
            updated = append_markdown_table_row(markdown, cells=cells)
        except ValueError as e:
            raise ValidationError(str(e))
        return self.client.update_block(block_id, updated, data_type="markdown")

    def check_task(self, block_id: str):
        doc_id = self.client.resolve_root_doc_id(block_id)
        self.client._guard_doc_write(doc_id, "check-task")

        kramdown_res = self.client.get_block_kramdown(block_id)
        if kramdown_res.get("code") != 0:
            return kramdown_res

        original = kramdown_res.get("data", {}).get("kramdown", "")
        updated = mark_first_unchecked_task(original)
        if updated == original:
            return {"code": 0, "msg": "未发现可勾选任务", "data": {"updated": False}}

        res = self.client.update_block(block_id, updated, data_type="kramdown")
        if res.get("code") == 0:
            return {"code": 0, "msg": "", "data": {"updated": True}}
        return res
