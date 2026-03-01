"""Document read/edit workflows including PMF support."""

from collections import defaultdict
import html
import os
import re
from html.parser import HTMLParser
from typing import Dict, List, Optional
import urllib.request

from ..core.client import SiyuanClient
from ..core.errors import ValidationError
from ..core.id_utils import escape_sql_value
from ..formats.pmf import PMFFormat


class _HTMLTextExtractor(HTMLParser):
    """Small HTML to text extractor for import (stdlib only)."""

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self._in_title = False
        self.title = ""
        self.parts: List[str] = []

    def handle_starttag(self, tag: str, attrs):
        t = (tag or "").lower()
        if t in ("script", "style"):
            self._skip_depth += 1
            return
        if t == "title":
            self._in_title = True
        if t in ("p", "div", "section", "article", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str):
        t = (tag or "").lower()
        if t in ("script", "style") and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if t == "title":
            self._in_title = False
        if t in ("p", "div", "section", "article", "li", "tr"):
            self.parts.append("\n")

    def handle_data(self, data: str):
        if self._skip_depth > 0:
            return
        text = " ".join((data or "").split())
        if not text:
            return
        if self._in_title and not self.title:
            self.title = text
        self.parts.append(text)

    def to_text(self) -> str:
        text = "".join(self.parts)
        text = html.unescape(text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


class DocumentModule:
    def __init__(self, client: SiyuanClient):
        self.client = client
        self.pmf = PMFFormat()

    def _should_skip_semantic_block(self, block: Dict[str, str], type_by_id: Dict[str, str]) -> bool:
        btype = (block.get("type", "") or "").strip()
        markdown = (block.get("markdown", "") or "").strip()
        parent_type = type_by_id.get(block.get("parent_id", ""), "")

        # List container block is structural noise for semantic summaries.
        if btype == "l":
            return True
        # Empty paragraphs are mostly formatting artifacts.
        if btype == "p" and not markdown:
            return True
        # Paragraphs under list items often duplicate item text.
        if btype == "p" and parent_type in ("i", "l"):
            return True
        return False

    def _build_typed_analysis(self, blocks: List[Dict[str, str]], semantic: bool = False) -> Dict[str, object]:
        by_type = defaultdict(int)
        by_subtype = defaultdict(int)
        samples = defaultdict(list)
        type_by_id = {b.get("id", ""): b.get("type", "") for b in blocks}
        counted = 0

        for block in blocks:
            if semantic and self._should_skip_semantic_block(block, type_by_id):
                continue
            btype = block.get("type", "") or "unknown"
            subtype = block.get("subtype", "") or "-"
            key = f"{btype}/{subtype}"
            by_type[btype] += 1
            by_subtype[key] += 1
            counted += 1
            if len(samples[btype]) < 3:
                snippet = " ".join((block.get("markdown", "") or "").split())
                samples[btype].append(
                    {
                        "id": block.get("id", ""),
                        "subtype": subtype,
                        "snippet": snippet[:120],
                    }
                )

        return {
            "semantic": bool(semantic),
            "counted_blocks": counted,
            "type_counts": {k: by_type[k] for k in sorted(by_type.keys())},
            "subtype_counts": {k: by_subtype[k] for k in sorted(by_subtype.keys())},
            "samples": {k: samples[k] for k in sorted(samples.keys())},
        }

    def _get_doc_blocks(self, doc_id: str) -> List[Dict[str, str]]:
        safe_id = escape_sql_value(doc_id)
        sql = (
            "SELECT id, markdown, type, subtype, parent_id, sort FROM blocks "
            f"WHERE root_id='{safe_id}' ORDER BY sort ASC"
        )
        res = self.client.sql_query(sql)
        if res.get("code") != 0:
            raise ValidationError(f"读取文档块失败: {res.get('msg')}")

        rows = res.get("data", []) or []
        blocks: List[Dict[str, str]] = []
        for row in rows:
            block_id = row.get("id", "")
            if block_id == doc_id:
                continue
            blocks.append(
                {
                    "id": block_id,
                    "markdown": row.get("markdown", "") or row.get("content", ""),
                    "type": row.get("type", ""),
                    "subtype": row.get("subtype", ""),
                    "parent_id": row.get("parent_id", ""),
                }
            )
        return blocks

    def open_doc(
        self,
        doc_id: str,
        view: str = "readable",
        full: bool = False,
        cursor: Optional[str] = None,
        limit_chars: Optional[int] = None,
        limit_blocks: Optional[int] = None,
        semantic: bool = False,
    ) -> Dict[str, object]:
        meta = self.client.get_doc_meta(doc_id)
        if not meta:
            raise ValidationError(f"文档不存在: {doc_id}")

        blocks = self._get_doc_blocks(doc_id)
        start_index = 0
        if cursor:
            for i, block in enumerate(blocks):
                if block["id"] == cursor:
                    start_index = i + 1
                    break

        char_limit = limit_chars if limit_chars is not None else self.client.settings.open_doc_char_limit
        block_limit = limit_blocks if limit_blocks is not None else len(blocks)

        selected: List[Dict[str, str]] = []
        current_chars = 0
        next_cursor: Optional[str] = None

        for block in blocks[start_index:]:
            block_text = block.get("markdown", "")
            projected = current_chars + len(block_text)
            if not full and (projected > char_limit or len(selected) >= block_limit):
                next_cursor = selected[-1]["id"] if selected else block["id"]
                break
            selected.append(block)
            current_chars = projected

        partial = next_cursor is not None
        self.client._mark_read(doc_id, source=f"open-doc:{view}")

        typed_data: Optional[Dict[str, object]] = None
        if view == "patchable":
            content = self.pmf.to_pmf(
                blocks=selected,
                doc_id=doc_id,
                partial=partial,
                cursor=next_cursor,
                updated=meta.get("updated", ""),
            )
        elif view == "typed":
            typed_data = self._build_typed_analysis(selected, semantic=semantic)

            lines = [
                f"# {meta.get('content', '')}",
                f"doc_id: {doc_id}",
                f"updated: {meta.get('updated', '')}",
                f"hpath: {meta.get('hpath', '')}",
                f"block_count: {len(selected)}",
                f"counted_blocks: {typed_data.get('counted_blocks', len(selected))}",
                f"semantic: {str(bool(semantic)).lower()}",
                "",
                "## Type Counts",
            ]
            for btype, count in typed_data.get("type_counts", {}).items():
                lines.append(f"- {btype}: {count}")
            lines.append("")
            lines.append("## Subtype Counts")
            for key, count in typed_data.get("subtype_counts", {}).items():
                lines.append(f"- {key}: {count}")
            lines.append("")
            lines.append("## Samples")
            for btype in sorted(typed_data.get("samples", {}).keys()):
                lines.append(f"### {btype}")
                for item in typed_data.get("samples", {}).get(btype, []):
                    lines.append(f"- {item['id']} [{item['subtype']}] {item['snippet']}")
                lines.append("")
            if partial and next_cursor:
                lines.append(
                    f"[partial] 文档过长，继续读取: open-doc {doc_id} {view} --cursor {next_cursor}"
                )
            content = "\n".join(lines).rstrip() + "\n"
        else:
            lines = [
                f"# {meta.get('content', '')}",
                f"doc_id: {doc_id}",
                f"updated: {meta.get('updated', '')}",
                f"hpath: {meta.get('hpath', '')}",
                "",
            ]
            for block in selected:
                text = block.get("markdown", "").strip()
                lines.append(text)
                lines.append("")
            if partial and next_cursor:
                lines.append(
                    f"[partial] 文档过长，继续读取: open-doc {doc_id} {view} --cursor {next_cursor}"
                )
            content = "\n".join(lines).rstrip() + "\n"

        return {
            "doc_id": doc_id,
            "partial": partial,
            "next_cursor": next_cursor,
            "block_count": len(selected),
            "view": view,
            "semantic": bool(semantic) if view == "typed" else False,
            "typed": typed_data,
            "content": content,
        }

    def apply_patch(self, doc_id: str, pmf_content: str) -> Dict[str, object]:
        parsed = self.pmf.from_pmf(pmf_content)
        if parsed["partial"]:
            raise ValidationError("apply-patch 拒绝 partial=true 的 PMF")

        if parsed["doc_id"] != doc_id:
            raise ValidationError(
                f"PMF 文档 ID 不匹配: pmf={parsed['doc_id']} target={doc_id}"
            )

        existing = self._get_doc_blocks(doc_id)
        existing_map = {b["id"]: b for b in existing}
        incoming_blocks = parsed["blocks"]
        incoming_ids = {b["id"] for b in incoming_blocks}
        existing_ids = set(existing_map.keys())

        if incoming_ids != existing_ids:
            raise ValidationError(
                "apply-patch 首版仅支持 update 安全子集，PMF 必须包含文档全部现有块且不新增/不删减。"
            )

        self.client._guard_doc_write(doc_id, "apply-patch")

        updated = 0
        for block in incoming_blocks:
            block_id = block["id"]
            new_markdown = block.get("markdown", "")
            old_markdown = existing_map[block_id].get("markdown", "")
            if new_markdown == old_markdown:
                continue
            res = self.client.update_block(block_id, new_markdown, data_type="markdown")
            if res.get("code") != 0:
                raise ValidationError(f"块更新失败 {block_id}: {res.get('msg')}")
            updated += 1

        return {
            "code": 0,
            "msg": "",
            "data": {
                "doc_id": doc_id,
                "updated_blocks": updated,
                "mode": "update-only",
            },
        }

    def write_full(
        self,
        target: str,
        markdown: str,
        mode: str = "replace",
        notebook_id: str = "",
    ) -> Dict[str, object]:
        target_text = str(target or "").strip()
        if not target_text:
            raise ValidationError("缺少目标 doc_id 或路径")

        normalized_mode = str(mode or "replace").strip().lower()
        if normalized_mode not in ("replace", "append"):
            raise ValidationError("write-full 模式仅支持 replace|append")

        block = self.client.get_block(target_text)
        if block and block.get("type") == "d":
            doc_id = target_text
            self.client._mark_read(doc_id, source=f"doc-write-full:{normalized_mode}")
            if normalized_mode == "append":
                res = self.client.append_block(doc_id, markdown)
                if res.get("code") != 0:
                    raise ValidationError(f"追加文档失败: {res.get('msg')}")
                return {
                    "code": 0,
                    "msg": "",
                    "data": {
                        "doc_id": doc_id,
                        "mode": "append",
                        "appended_chars": len(markdown),
                    },
                }

            blocks = self._get_doc_blocks(doc_id)
            deleted = 0
            for item in reversed(blocks):
                block_id = item.get("id", "")
                if not block_id:
                    continue
                res = self.client.delete_block(block_id)
                if res.get("code") != 0:
                    raise ValidationError(f"删除旧块失败 {block_id}: {res.get('msg')}")
                deleted += 1

            if markdown.strip():
                res = self.client.append_block(doc_id, markdown)
                if res.get("code") != 0:
                    raise ValidationError(f"写入新内容失败: {res.get('msg')}")

            return {
                "code": 0,
                "msg": "",
                "data": {
                    "doc_id": doc_id,
                    "mode": "replace",
                    "deleted_blocks": deleted,
                    "written_chars": len(markdown),
                },
            }

        if not target_text.startswith("/") and "/" not in target_text:
            raise ValidationError(f"目标既不是文档 ID，也不是路径: {target_text}")

        nb_id = str(notebook_id or self.client.settings.main_notebook_id or "").strip()
        if not nb_id:
            raise ValidationError("写入新文档时缺少 notebook_id（可通过 --notebook 或 main_notebook_id 配置）")
        created = self.client.create_doc(nb_id, target_text, markdown)
        if created.get("code") != 0:
            raise ValidationError(f"创建文档失败: {created.get('msg')}")
        return {
            "code": 0,
            "msg": "",
            "data": {
                "doc_id": str(created.get("data", "")),
                "mode": "create",
                "path": target_text,
                "written_chars": len(markdown),
            },
        }

    def _chat_to_markdown(self, text: str) -> str:
        out = ["# Imported Chat", ""]
        for raw in (text or "").splitlines():
            line = raw.strip()
            if not line:
                continue
            if ":" in line:
                role, content = line.split(":", 1)
                role_norm = role.strip().lower()
                if role_norm in ("user", "assistant", "system"):
                    out.append(f"## {role_norm.title()}")
                    out.append(content.strip())
                    out.append("")
                    continue
            out.append(f"- {line}")
        return "\n".join(out).rstrip() + "\n"

    def _fetch_url_to_markdown(self, url: str) -> str:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "siyuan-bridge/1.0",
                "Accept": "text/html,text/plain,text/markdown,*/*",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as res:
                raw = res.read()
                content_type = str(res.headers.get("Content-Type", "")).lower()
                charset = res.headers.get_content_charset() or "utf-8"
        except Exception as e:
            raise ValidationError(f"抓取 URL 失败: {e}")

        text = raw.decode(charset, errors="replace")
        if "text/markdown" in content_type or "text/plain" in content_type:
            return f"# Imported From URL\n\nSource: {url}\n\n{text.strip()}\n"

        parser = _HTMLTextExtractor()
        parser.feed(text)
        body = parser.to_text()
        title = parser.title or "Imported Page"
        return f"# {title}\n\nSource: {url}\n\n{body}\n"

    def import_content(
        self,
        source: str,
        source_type: str,
        notebook_id: str,
        path: str,
        raw_content: str = "",
    ) -> Dict[str, object]:
        stype = str(source_type or "").strip().lower()
        if stype not in ("url", "md", "chat"):
            raise ValidationError("import 类型仅支持 url|md|chat")

        src = str(source or "").strip()
        if not src and not raw_content:
            raise ValidationError("缺少导入 source")
        if not notebook_id.strip():
            raise ValidationError("缺少 notebook_id")
        if not path.strip():
            raise ValidationError("缺少目标 path")

        if stype == "url":
            markdown = self._fetch_url_to_markdown(src)
        else:
            if raw_content:
                text = raw_content
            elif os.path.isfile(src):
                with open(src, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            else:
                text = src
            markdown = text if stype == "md" else self._chat_to_markdown(text)

        created = self.client.create_doc(notebook_id, path, markdown)
        if created.get("code") != 0:
            raise ValidationError(f"导入创建文档失败: {created.get('msg')}")
        return {
            "code": 0,
            "msg": "",
            "data": {
                "doc_id": str(created.get("data", "")),
                "source_type": stype,
                "source": src if src else "<stdin>",
                "path": path,
                "chars": len(markdown),
            },
        }
