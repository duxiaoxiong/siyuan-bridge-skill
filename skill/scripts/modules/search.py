"""Search module with templates and smart routing."""

import re
from typing import Dict

from ..core.client import SiyuanClient
from ..core.id_utils import escape_sql_value


QUERY_TEMPLATES = {
    "recent_docs": "SELECT id, content, hpath, updated FROM blocks WHERE type='d' ORDER BY updated DESC LIMIT {limit}",
    "tagged_blocks": "SELECT id, content, hpath, type FROM blocks WHERE content LIKE '%#{tag}%' LIMIT {limit}",
}


class SearchModule:
    def __init__(self, client: SiyuanClient):
        self.client = client

    def search_recent_docs(self, limit: int = 20, box: str = "") -> Dict[str, object]:
        sql = QUERY_TEMPLATES["recent_docs"].format(limit=int(limit))
        if box.strip():
            sql = (
                "SELECT id, content, hpath, updated, box FROM blocks "
                f"WHERE type='d' AND box='{escape_sql_value(box.strip())}' "
                f"ORDER BY updated DESC LIMIT {int(limit)}"
            )
        return self.client.sql_query(sql)

    def search_by_tag(self, tag: str, limit: int = 50) -> Dict[str, object]:
        safe_tag = escape_sql_value(tag.lstrip("#"))
        sql = QUERY_TEMPLATES["tagged_blocks"].format(tag=safe_tag, limit=int(limit))
        return self.client.sql_query(sql)

    def search_by_date_keyword(self, keyword: str, limit: int = 50) -> Dict[str, object]:
        clean = keyword.strip().replace(".", "-")
        if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", clean):
            date_key = clean.replace("-", "")[:8]
            sql = (
                "SELECT id, content, hpath, updated FROM blocks "
                f"WHERE updated LIKE '{escape_sql_value(date_key)}%' LIMIT {int(limit)}"
            )
            return self.client.sql_query(sql)
        return self.client.search(keyword, limit=limit)

    def smart_search(self, keyword: str, limit: int = 20) -> Dict[str, object]:
        kw = keyword.strip()
        if kw.startswith("#"):
            return self.search_by_tag(kw, limit=limit)
        if re.match(r"^(\d{4}[.-]\d{1,2}[.-]\d{1,2}|\d{1,2}[.-]\d{1,2})$", kw):
            return self.search_by_date_keyword(kw, limit=limit)
        return self.client.search(kw, limit=limit)

    def search_by_type(
        self,
        block_type: str,
        *,
        subtype: str = "",
        box: str = "",
        limit: int = 20,
    ) -> Dict[str, object]:
        btype = str(block_type or "").strip()
        if not btype:
            return {"code": -1, "msg": "缺少块类型 type", "data": None}
        if not re.match(r"^[a-zA-Z0-9_]+$", btype):
            return {"code": -1, "msg": f"非法类型: {btype}", "data": None}

        clauses = [f"type='{escape_sql_value(btype)}'"]
        if subtype.strip():
            clauses.append(f"subtype='{escape_sql_value(subtype.strip())}'")
        if box.strip():
            clauses.append(f"box='{escape_sql_value(box.strip())}'")

        where = " AND ".join(clauses)
        sql = (
            "SELECT id, content, hpath, type, subtype, updated, box FROM blocks "
            f"WHERE {where} ORDER BY updated DESC LIMIT {int(limit)}"
        )
        return self.client.sql_query(sql)
