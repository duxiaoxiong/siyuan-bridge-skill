"""Patchable Markdown Format (PMF) helpers."""

import time
from typing import Dict, List, Optional

from ..core.errors import ValidationError


class PMFFormat:
    def to_pmf(
        self,
        blocks: List[Dict[str, str]],
        doc_id: str,
        partial: bool = False,
        cursor: Optional[str] = None,
        updated: str = "",
    ) -> str:
        header = [
            "---",
            f"doc_id: {doc_id}",
            f"partial: {'true' if partial else 'false'}",
            f"cursor: {cursor if cursor else 'null'}",
            f"timestamp: {int(time.time())}",
            f"updated: {updated if updated else ''}",
            "---",
            "",
        ]
        body: List[str] = []
        for block in blocks:
            body.append((block.get("markdown") or "").rstrip())
            body.append(f'{{: id="{block.get("id", "")}"}}')
            body.append("")
        return "\n".join(header + body).rstrip() + "\n"

    def from_pmf(self, pmf_content: str) -> Dict[str, object]:
        text = (pmf_content or "").replace("\r\n", "\n").replace("\r", "\n")
        if not text.startswith("---\n"):
            raise ValidationError("无效 PMF: 缺少头部")

        parts = text.split("\n---\n", 1)
        if len(parts) != 2:
            raise ValidationError("无效 PMF: 头部结束标记缺失")

        header_text = parts[0][4:]
        body_text = parts[1]

        header: Dict[str, str] = {}
        for line in header_text.split("\n"):
            if not line.strip() or ":" not in line:
                continue
            key, value = line.split(":", 1)
            header[key.strip()] = value.strip()

        doc_id = header.get("doc_id", "")
        if not doc_id:
            raise ValidationError("无效 PMF: 缺少 doc_id")

        partial = header.get("partial", "false").lower() == "true"
        cursor = header.get("cursor")
        if cursor == "null":
            cursor = None

        blocks: List[Dict[str, str]] = []
        buf: List[str] = []
        block_id: Optional[str] = None

        for raw_line in body_text.split("\n"):
            line = raw_line.strip()
            if line.startswith("{: id=\"") and line.endswith("\"}"):
                block_id = line[len("{: id=\"") : -2]
                markdown = "\n".join(buf).strip("\n")
                blocks.append({"id": block_id, "markdown": markdown})
                buf = []
                block_id = None
            else:
                buf.append(raw_line)

        return {
            "doc_id": doc_id,
            "partial": partial,
            "cursor": cursor,
            "timestamp": header.get("timestamp"),
            "updated": header.get("updated", ""),
            "blocks": blocks,
        }
