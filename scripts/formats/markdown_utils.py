"""Markdown related helpers."""

import re
from typing import Any, Dict, List, Optional


_BLOCK_ID_LINE_RE = re.compile(r'^\{:\s*id="([^"]+)"[^}]*\}\s*$')
_BLOCK_REF_RE = re.compile(
    r"\(\((?P<id>\d{14}-[a-z0-9]{7})(?:\s+(?:\"(?P<alias_d>[^\"]*)\"|'(?P<alias_s>[^']*)'))?\)\)",
    re.IGNORECASE,
)
_WIKI_LINK_RE = re.compile(r"\[\[([^\]\n]+)\]\]")
_TAG_RE = re.compile(r"(?<!\w)#([^#\s][^#\n]*?)#")
_QUERY_EMBED_RE = re.compile(r"(?<!\{)\{\{(?!\{)([\s\S]*?)(?<!\})\}\}(?!\})")


def _dedupe_keep_order(items: List[Any]) -> List[Any]:
    seen = set()
    out: List[Any] = []
    for item in items:
        marker = repr(item)
        if marker in seen:
            continue
        seen.add(marker)
        out.append(item)
    return out


def strip_html_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "")


def mark_first_unchecked_task(markdown: str) -> str:
    for pattern in (r"-\s*\[\s\]", r"-\s*\[ \]", r"\[ \]"):
        updated, count = re.subn(pattern, "- [x]", markdown, count=1)
        if count > 0:
            return updated
    return markdown


def split_kramdown_blocks(kramdown: str) -> List[Dict[str, str]]:
    lines = (kramdown or "").split("\n")
    blocks: List[Dict[str, str]] = []
    buf: List[str] = []

    for line in lines:
        match = _BLOCK_ID_LINE_RE.match(line.strip())
        if not match:
            buf.append(line)
            continue

        block_id = match.group(1)
        markdown = "\n".join(buf).strip("\n")
        blocks.append({"id": block_id, "markdown": markdown})
        buf = []

    return [b for b in blocks if b["markdown"].strip()]


def extract_reference_tokens(markdown: str) -> Dict[str, Any]:
    text = markdown or ""
    block_refs = []
    for m in _BLOCK_REF_RE.finditer(text):
        alias = (m.group("alias_d") or m.group("alias_s") or "").strip()
        block_refs.append(
            {
                "id": m.group("id"),
                "alias": alias,
            }
        )

    wiki_links = [m.group(1).strip() for m in _WIKI_LINK_RE.finditer(text) if m.group(1).strip()]
    tags = [m.group(1).strip() for m in _TAG_RE.finditer(text) if m.group(1).strip()]
    query_embeds = [m.group(1).strip() for m in _QUERY_EMBED_RE.finditer(text) if m.group(1).strip()]

    block_refs = _dedupe_keep_order(block_refs)
    wiki_links = _dedupe_keep_order(wiki_links)
    tags = _dedupe_keep_order(tags)
    query_embeds = _dedupe_keep_order(query_embeds)

    return {
        "block_refs": block_refs,
        "wiki_links": wiki_links,
        "tags": tags,
        "query_embeds": query_embeds,
        "counts": {
            "block_refs": len(block_refs),
            "wiki_links": len(wiki_links),
            "tags": len(tags),
            "query_embeds": len(query_embeds),
        },
    }


def build_callout_markdown(callout_type: str, text: str) -> str:
    ctype = str(callout_type or "").strip().upper()
    if not ctype:
        ctype = "NOTE"
    lines = [f"> [!{ctype}]"]
    body = (text or "").splitlines() or [""]
    for line in body:
        if line.strip():
            lines.append(f"> {line.strip()}")
        else:
            lines.append(">")
    return "\n".join(lines)


def normalize_embed_sql(raw_sql: str) -> str:
    text = str(raw_sql or "").strip()
    if text.startswith("{{") and text.endswith("}}"):
        text = text[2:-2].strip()
    text = text.rstrip(";").strip()
    return text


def inject_safe_embed_scope(
    sql: str,
    *,
    scope_sql: Optional[str],
    default_limit: int,
) -> str:
    stmt = normalize_embed_sql(sql)
    if not stmt:
        raise ValueError("嵌入 SQL 不能为空")
    if not re.match(r"^\s*select\b", stmt, re.IGNORECASE):
        raise ValueError("嵌入 SQL 仅允许 SELECT")

    clause_match = re.search(r"\b(order\s+by|group\s+by|limit|offset)\b", stmt, re.IGNORECASE)
    if clause_match:
        base = stmt[: clause_match.start()].rstrip()
        tail = stmt[clause_match.start() :].lstrip()
    else:
        base = stmt
        tail = ""

    has_scope = re.search(r"\b(root_id|box|hpath)\b", base, re.IGNORECASE) is not None
    if scope_sql and not has_scope:
        if re.search(r"\bwhere\b", base, re.IGNORECASE):
            base = f"{base} AND {scope_sql}"
        else:
            base = f"{base} WHERE {scope_sql}"

    has_limit = re.search(r"\blimit\s+\d+\b", stmt, re.IGNORECASE) is not None
    merged = f"{base} {tail}".strip()
    if not has_limit:
        merged = f"{merged} LIMIT {int(default_limit)}".strip()
    return merged


def append_markdown_table_row(table_markdown: str, cells: Optional[List[str]] = None) -> str:
    lines = (table_markdown or "").splitlines()
    if len(lines) < 2:
        raise ValueError("不是有效表格块，至少需要表头和分隔行")

    header = lines[0].strip()
    separator = lines[1].strip()
    if "|" not in header or "|" not in separator:
        raise ValueError("不是有效 Markdown 表格格式")

    def _split_row(row: str) -> List[str]:
        raw = row.strip()
        if raw.startswith("|"):
            raw = raw[1:]
        if raw.endswith("|"):
            raw = raw[:-1]
        return [part.strip() for part in raw.split("|")]

    header_cells = _split_row(header)
    col_count = len(header_cells)
    if col_count == 0:
        raise ValueError("表格列数为 0")

    incoming = [str(c) for c in (cells or [])]
    if len(incoming) < col_count:
        incoming.extend([""] * (col_count - len(incoming)))
    if len(incoming) > col_count:
        incoming = incoming[:col_count]

    normalized = [c.replace("|", r"\|").replace("\n", " ").strip() for c in incoming]
    new_row = "| " + " | ".join(normalized) + " |"
    lines.append(new_row)
    return "\n".join(lines)
