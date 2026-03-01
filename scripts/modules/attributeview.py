"""AttributeView (database) module."""

import datetime as dt
import json
import os
import random
import re
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..core.client import SiyuanClient
from ..core.errors import ValidationError
from ..core.id_utils import extract_av_id_from_kramdown, make_siyuan_like_id


class AttributeViewClient:
    SELECT_COLOR_POOL = tuple(str(i) for i in range(1, 14))

    def __init__(self, client: SiyuanClient):
        self.client = client

    # Common key types exposed by Siyuan AV.
    SUPPORTED_KEY_TYPES = (
        "text",
        "number",
        "date",
        "select",
        "mSelect",
        "checkbox",
        "url",
        "email",
        "phone",
        "relation",
        "mAsset",
        "rollup",
        "template",
        "created",
        "updated",
        "block",
    )

    READ_ONLY_VALUE_TYPES = ("created", "updated", "rollup")
    KEY_TYPE_ALIASES = {
        "mselect": "mSelect",
        "multi-select": "mSelect",
        "multi_select": "mSelect",
        "multiselect": "mSelect",
        "select": "select",
        "text": "text",
        "number": "number",
        "date": "date",
        "checkbox": "checkbox",
        "url": "url",
        "email": "email",
        "phone": "phone",
        "relation": "relation",
        "masset": "mAsset",
        "asset": "mAsset",
        "template": "template",
        "created": "created",
        "updated": "updated",
        "rollup": "rollup",
        "block": "block",
    }

    def _normalize_av_id(self, raw_id: str) -> str:
        candidate = str(raw_id or "").strip()
        if not candidate:
            raise ValidationError("缺少 av_id 或 av block_id")

        # If an AV block id is passed by mistake, convert it to real av_id.
        block = self.client.get_block(candidate)
        if block and block.get("type") == "av":
            return self.get_av_id_from_block(candidate)
        return candidate

    def _normalize_key_type(self, key_type: str) -> str:
        raw = str(key_type or "").strip()
        if not raw:
            return "text"
        lowered = raw.lower()
        if lowered in self.KEY_TYPE_ALIASES:
            return self.KEY_TYPE_ALIASES[lowered]
        return raw

    def get_schema(self, av_id: str) -> Dict[str, Any]:
        normalized = self._normalize_av_id(av_id)
        render = self.render(normalized, wait_ready=True)
        if render.get("code") != 0:
            raise ValidationError(f"渲染数据库失败: {render.get('msg')}")
        view = render.get("data", {}).get("view", {})
        columns = view.get("columns", []) or []
        rows = view.get("rows", []) or []
        result_columns = []
        by_id: Dict[str, Dict[str, Any]] = {}
        by_name: Dict[str, Dict[str, Any]] = {}
        for col in columns:
            ctype = self._normalize_key_type(col.get("type", "text"))
            item = {
                "id": col.get("id", ""),
                "name": col.get("name", ""),
                "type": ctype,
                "writable": ctype not in self.READ_ONLY_VALUE_TYPES,
                "options": col.get("options", []) or [],
            }
            result_columns.append(item)
            if item["id"]:
                by_id[item["id"]] = item
            if item["name"]:
                by_name[item["name"]] = item
        return {
            "av_id": normalized,
            "view_id": view.get("id", ""),
            "row_ids": [r.get("id", "") for r in rows if r.get("id")],
            "columns": result_columns,
            "by_id": by_id,
            "by_name": by_name,
        }

    def _resolve_column(self, av_id: str, key_ref: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ref = str(key_ref or "").strip()
        if not ref:
            raise ValidationError("缺少列引用（key_id 或列名）")
        s = schema or self.get_schema(av_id)
        if ref in s["by_id"]:
            return s["by_id"][ref]
        if ref in s["by_name"]:
            return s["by_name"][ref]
        raise ValidationError(f"找不到列: {ref}")

    def _doc_id_for_av_or_raise(self, av_id: str) -> Tuple[str, str]:
        normalized = self._normalize_av_id(av_id)
        doc_id = self.client.resolve_doc_id_from_av_id(normalized)
        if not doc_id:
            if self.client.allow_unsafe_write:
                return normalized, ""
            raise ValidationError(f"无法解析 av_id 所属文档: {normalized}")
        return normalized, doc_id

    def _av_write(self, path: str, payload: Dict[str, Any], operation: str, av_id: str):
        normalized, doc_id = self._doc_id_for_av_or_raise(av_id)
        payload = dict(payload)
        if payload.get("avID"):
            payload["avID"] = normalized
        return self.client.post_with_guard(
            path=path,
            payload=payload,
            operation=operation,
            doc_id=doc_id,
            log_action=operation,
        )

    def get_av_id_from_block(self, block_id: str) -> str:
        res = self.client.get_block_kramdown(block_id)
        if res.get("code") != 0:
            raise ValidationError(f"读取块 kramdown 失败: {res.get('msg')}")
        kramdown = res.get("data", {}).get("kramdown", "")
        return extract_av_id_from_kramdown(kramdown)

    def _render_once(self, av_id: str, view_id: str = "", page: int = 1, page_size: int = -1):
        payload: Dict[str, Any] = {"id": av_id, "page": page, "pageSize": page_size}
        if view_id:
            payload["viewID"] = view_id
        return self.client._post("/api/av/renderAttributeView", payload)

    def wait_until_ready(
        self,
        av_id: str,
        max_attempts: int = 12,
        sleep_seconds: float = 0.2,
    ) -> Dict[str, Any]:
        normalized = self._normalize_av_id(av_id)
        last_msg = ""
        for _ in range(max_attempts):
            res = self._render_once(normalized)
            if res.get("code") == 0:
                view = res.get("data", {}).get("view", {})
                if view and view.get("id"):
                    doc_id = self.client.resolve_doc_id_from_av_id(normalized)
                    if doc_id:
                        self.client._mark_read(doc_id, source="av-render")
                    return res
            last_msg = str(res.get("msg", "")).strip()
            time.sleep(sleep_seconds)
        raise ValidationError(
            f"AttributeView 尚未就绪: {normalized}. "
            f"最后错误: {last_msg or 'unknown'}"
        )

    def render(
        self,
        av_id: str,
        view_id: str = "",
        page: int = 1,
        page_size: int = -1,
        wait_ready: bool = False,
    ):
        normalized = self._normalize_av_id(av_id)
        if wait_ready:
            res = self.wait_until_ready(normalized)
        else:
            res = self._render_once(normalized, view_id=view_id, page=page, page_size=page_size)
        if res.get("code") == 0:
            doc_id = self.client.resolve_doc_id_from_av_id(normalized)
            if doc_id:
                self.client._mark_read(doc_id, source="av-render")
        return res

    def get_info(self, av_id: str):
        normalized = self._normalize_av_id(av_id)
        return self.client._post("/api/av/getAttributeView", {"id": normalized})

    def get_columns(self, av_id: str) -> List[Dict[str, Any]]:
        render = self.render(av_id, wait_ready=True)
        if render.get("code") != 0:
            raise ValidationError(f"渲染数据库失败: {render.get('msg')}")
        columns = render.get("data", {}).get("view", {}).get("columns", [])
        return columns

    def add_column(
        self,
        av_id: str,
        key_name: str,
        key_type: str,
        key_icon: str = "",
        previous_key_id: str = "",
        key_id: str = "",
        options: Optional[List[Dict[str, str]]] = None,
        prime_options: bool = False,
    ):
        normalized = self._normalize_av_id(av_id)
        normalized_key_type = self._normalize_key_type(key_type)
        if normalized_key_type not in self.SUPPORTED_KEY_TYPES:
            raise ValidationError(
                f"不支持的列类型: {key_type}. 可选: {', '.join(self.SUPPORTED_KEY_TYPES)}"
            )
        self.wait_until_ready(normalized)
        resolved_previous = str(previous_key_id or "").strip()
        if not resolved_previous:
            schema = self.get_schema(normalized)
            primary_col = next((c for c in schema.get("columns", []) if c.get("type") == "block"), None)
            if primary_col and primary_col.get("id"):
                resolved_previous = str(primary_col.get("id", ""))

        payload = {
            "avID": normalized,
            "keyID": key_id or f"{normalized}-{make_siyuan_like_id('col')}",
            "keyName": key_name,
            "keyType": normalized_key_type,
            "keyIcon": key_icon,
            "previousKeyID": resolved_previous,
        }
        if options and normalized_key_type in ("select", "mSelect"):
            payload["options"] = [
                {
                    "name": str(item.get("name", "")).strip(),
                    "color": str(item.get("color", "")).strip() or random.choice(self.SELECT_COLOR_POOL),
                    "desc": str(item.get("desc", "")).strip(),
                }
                for item in options
                if str(item.get("name", "")).strip()
            ]
        res = self._av_write("/api/av/addAttributeViewKey", payload, "av-add-column", normalized)
        if res.get("code") != 0 and "view not found" in str(res.get("msg", "")).lower():
            # New database can be created before view is ready; wait then retry once.
            self.wait_until_ready(normalized)
            res = self._av_write("/api/av/addAttributeViewKey", payload, "av-add-column", normalized)

        if (
            res.get("code") == 0
            and prime_options
            and payload.get("options")
            and normalized_key_type in ("select", "mSelect")
        ):
            self._prime_select_options(
                normalized,
                [
                    {
                        "key_id": payload.get("keyID", ""),
                        "type": normalized_key_type,
                        "options": payload.get("options", []),
                    }
                ],
            )
        return res

    def remove_column(self, av_id: str, key_id: str, remove_relation_dest: bool = False):
        normalized = self._normalize_av_id(av_id)
        payload = {
            "avID": normalized,
            "keyID": key_id,
            "removeRelationDest": bool(remove_relation_dest),
        }
        return self._av_write("/api/av/removeAttributeViewKey", payload, "av-remove-column", normalized)

    def _row_ids(self, av_id: str) -> List[str]:
        render = self.render(av_id, wait_ready=True)
        if render.get("code") != 0:
            raise ValidationError(f"渲染数据库失败: {render.get('msg')}")
        rows = render.get("data", {}).get("view", {}).get("rows", [])
        return [r.get("id", "") for r in rows if r.get("id")]

    def add_row(self, av_id: str, detached: bool = True, source_block_id: str = "") -> str:
        normalized = self._normalize_av_id(av_id)
        before = set(self._row_ids(av_id))
        src_id = str(source_block_id or "").strip() or make_siyuan_like_id("row")
        is_detached = bool(detached) if not source_block_id else False
        payload = {"avID": normalized, "srcs": [{"id": src_id, "isDetached": is_detached}]}
        res = self._av_write("/api/av/addAttributeViewBlocks", payload, "av-add-row", normalized)
        if res.get("code") != 0:
            raise ValidationError(f"添加行失败: {res.get('msg')}")

        time.sleep(0.2)
        after = self._row_ids(av_id)
        new_ids = [row_id for row_id in after if row_id not in before]
        if new_ids:
            return new_ids[-1]
        if source_block_id and source_block_id in after:
            return source_block_id
        if after:
            return after[-1]
        raise ValidationError("添加行后未找到实际 row_id")

    def remove_rows(self, av_id: str, row_ids: Iterable[str]):
        normalized = self._normalize_av_id(av_id)
        payload = {"avID": normalized, "srcIDs": list(row_ids)}
        return self._av_write("/api/av/removeAttributeViewBlocks", payload, "av-remove-rows", normalized)

    def _to_epoch_ms(self, when: dt.datetime) -> int:
        if when.tzinfo is None:
            when = when.replace(tzinfo=dt.timezone.utc)
        return int(when.timestamp() * 1000)

    def _parse_date_value(self, value: Any) -> Tuple[int, bool]:
        if isinstance(value, dt.datetime):
            return self._to_epoch_ms(value), False
        if isinstance(value, dt.date):
            return self._to_epoch_ms(dt.datetime.combine(value, dt.time.min, tzinfo=dt.timezone.utc)), True

        if isinstance(value, (int, float)):
            iv = int(value)
            digits = len(str(abs(iv)))
            if digits == 8:
                try:
                    parsed = dt.datetime.strptime(str(iv), "%Y%m%d")
                    return self._to_epoch_ms(parsed.replace(tzinfo=dt.timezone.utc)), True
                except ValueError:
                    pass
            if digits == 14:
                try:
                    parsed = dt.datetime.strptime(str(iv), "%Y%m%d%H%M%S")
                    return self._to_epoch_ms(parsed.replace(tzinfo=dt.timezone.utc)), False
                except ValueError:
                    pass
            if digits >= 12:
                return iv, False
            return iv * 1000, False

        text = str(value).strip()
        for fmt, is_date_only in (
            ("%Y-%m-%d", True),
            ("%Y%m%d", True),
            ("%Y/%m/%d", True),
            ("%Y-%m-%d %H:%M:%S", False),
            ("%Y%m%d%H%M%S", False),
            ("%Y-%m-%dT%H:%M:%S", False),
        ):
            try:
                parsed = dt.datetime.strptime(text, fmt)
                if is_date_only:
                    parsed = parsed.replace(hour=0, minute=0, second=0, tzinfo=dt.timezone.utc)
                else:
                    parsed = parsed.replace(tzinfo=dt.timezone.utc)
                return self._to_epoch_ms(parsed), is_date_only
            except ValueError:
                continue
        raise ValidationError(f"无法解析日期值: {value}")

    def _as_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        text = str(value).strip().lower()
        return text in ("1", "true", "yes", "y", "on")

    def _parse_select_options(
        self,
        value: Any,
        option_color_map: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, str]]:
        color_map = option_color_map or {}

        def _parse_item(item: Any) -> Optional[Dict[str, str]]:
            if isinstance(item, dict):
                content = str(item.get("content", item.get("name", ""))).strip()
                if not content:
                    return None
                color = str(item.get("color", "")).strip() or color_map.get(content) or random.choice(self.SELECT_COLOR_POOL)
                return {"content": content, "color": color}

            text = str(item).strip()
            if not text:
                return None

            # Allow inline color syntax: "Todo|3"
            if "|" in text:
                head, tail = text.rsplit("|", 1)
                head = head.strip()
                tail = tail.strip()
                if head and tail:
                    return {"content": head, "color": tail}

            return {
                "content": text,
                "color": color_map.get(text) or random.choice(self.SELECT_COLOR_POOL),
            }

        if isinstance(value, list):
            items = value
        elif isinstance(value, str) and "," in value:
            items = [x.strip() for x in value.split(",") if x.strip()]
        else:
            items = [value]
        parsed = [_parse_item(v) for v in items]
        return [item for item in parsed if item]

    def _option_color_map(self, column_meta: Optional[Dict[str, Any]]) -> Dict[str, str]:
        if not column_meta:
            return {}
        options = column_meta.get("options", []) or []
        out: Dict[str, str] = {}
        for option in options:
            name = str(option.get("name", "")).strip()
            color = str(option.get("color", "")).strip()
            if name and color:
                out[name] = color
        return out

    def _parse_relation(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            ids = value.get("ids")
            if isinstance(ids, list):
                return {"type": "relation", "relation": {"blockIDs": [str(x) for x in ids]}}
        if isinstance(value, (list, tuple, set)):
            return {"type": "relation", "relation": {"blockIDs": [str(x) for x in value]}}
        text = str(value).strip()
        if not text:
            return {"type": "relation", "relation": {"blockIDs": []}}
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return {"type": "relation", "relation": {"blockIDs": [str(x) for x in parsed]}}
            except Exception:
                pass
        if re.search(r"[,\s]+", text):
            ids = [x for x in re.split(r"[,\s]+", text) if x]
            return {"type": "relation", "relation": {"blockIDs": ids}}
        return {"type": "relation", "relation": {"blockIDs": [text]}}

    def _parse_masset(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("[") and text.endswith("]"):
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, list):
                        value = parsed
                except Exception:
                    pass
        raw_items = value if isinstance(value, list) else [value]
        assets: List[Dict[str, str]] = []
        for item in raw_items:
            if isinstance(item, dict):
                content = str(item.get("content", "")).strip()
                if not content:
                    continue
                assets.append(
                    {
                        "type": str(item.get("type", "file")).strip() or "file",
                        "name": str(item.get("name", os.path.basename(content))).strip() or os.path.basename(content),
                        "content": content,
                    }
                )
                continue
            content = str(item).strip()
            if not content:
                continue
            assets.append(
                {
                    "type": "file",
                    "name": os.path.basename(content) or content,
                    "content": content,
                }
            )
        return {"type": "mAsset", "mAsset": assets}

    def _build_value(self, col_type: str, value: Any, column_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        t = self._normalize_key_type(col_type or "text")
        if t in self.READ_ONLY_VALUE_TYPES:
            raise ValidationError(f"{t} 列为系统计算列，不支持直接写入")
        if t == "text":
            return {"type": "text", "text": {"content": str(value)}}
        if t == "number":
            return {
                "type": "number",
                "number": {"content": float(value), "isNotEmpty": True},
            }
        if t == "date":
            content, is_date_only = self._parse_date_value(value)
            return {
                "type": "date",
                "date": {
                    "content": content,
                    "isNotEmpty": True,
                    "hasEndDate": False,
                    "isNotTime": is_date_only,
                },
            }
        if t == "select":
            return {
                "type": "select",
                "mSelect": self._parse_select_options(value, option_color_map=self._option_color_map(column_meta))[:1],
            }
        if t == "mSelect":
            return {
                "type": "mSelect",
                "mSelect": self._parse_select_options(value, option_color_map=self._option_color_map(column_meta)),
            }
        if t == "checkbox":
            return {
                "type": "checkbox",
                "checkbox": {"checked": self._as_bool(value)},
            }
        if t == "url":
            return {"type": "url", "url": {"content": str(value)}}
        if t == "email":
            return {"type": "email", "email": {"content": str(value)}}
        if t == "phone":
            return {"type": "phone", "phone": {"content": str(value)}}
        if t == "relation":
            return self._parse_relation(value)
        if t == "mAsset":
            return self._parse_masset(value)
        if t == "block":
            return {"type": "block", "block": {"content": str(value)}}
        if t == "template":
            return {"type": "template", "template": {"content": str(value)}}
        return {"type": "text", "text": {"content": str(value)}}

    def set_cell(
        self,
        av_id: str,
        key_id: str,
        item_id: str,
        value: Any,
        col_type: str = "text",
        column_meta: Optional[Dict[str, Any]] = None,
    ):
        normalized = self._normalize_av_id(av_id)
        payload = {
            "avID": normalized,
            "keyID": key_id,
            "itemID": item_id,
            "value": self._build_value(col_type, value, column_meta=column_meta)
            if not (isinstance(value, dict) and "type" in value)
            else value,
        }
        return self._av_write("/api/av/setAttributeViewBlockAttr", payload, "av-set-cell", normalized)

    def set_cell_by_name(self, av_id: str, row_id: str, key_ref: str, value: Any):
        normalized = self._normalize_av_id(av_id)
        schema = self.get_schema(normalized)
        if row_id not in schema["row_ids"]:
            raise ValidationError(f"找不到行: {row_id}")
        col = self._resolve_column(normalized, key_ref, schema=schema)
        return self.set_cell(
            av_id=normalized,
            key_id=col["id"],
            item_id=row_id,
            value=value,
            col_type=col["type"],
            column_meta=col,
        )

    def batch_set_cells(self, av_id: str, values: List[Dict[str, Any]]):
        normalized = self._normalize_av_id(av_id)
        payload = {"avID": normalized, "values": values}
        return self._av_write(
            "/api/av/batchSetAttributeViewBlockAttrs",
            payload,
            "av-batch-set-cells",
            normalized,
        )

    def duplicate(self, av_id: str):
        normalized = self._normalize_av_id(av_id)
        payload = {"avID": normalized}
        return self._av_write("/api/av/duplicateAttributeViewBlock", payload, "av-duplicate", normalized)

    def add_row_with_data(self, av_id: str, data: Dict[str, Any], strict: bool = False) -> str:
        normalized = self._normalize_av_id(av_id)
        schema = self.get_schema(normalized)
        col_map = schema["by_name"]
        primary_col = next((c for c in schema.get("columns", []) if c.get("type") == "block"), None)
        payload = dict(data or {})
        primary_block_id = str(payload.pop("__primary_block_id", "")).strip()
        title_value = payload.pop("__title", None)
        unknown_cols: List[str] = []
        prepared: List[Dict[str, Any]] = []
        for name, raw_value in payload.items():
            col = col_map.get(name)
            if not col:
                unknown_cols.append(name)
                continue
            prepared.append(
                {
                    "keyID": col.get("id", "") or col.get("id"),
                    "value": self._build_value(col.get("type", "text"), raw_value, column_meta=col),
                }
            )
        if strict and unknown_cols:
            raise ValidationError(f"未找到列: {', '.join(unknown_cols)}")

        row_id = self.add_row(
            normalized,
            detached=not bool(primary_block_id),
            source_block_id=primary_block_id,
        )

        if title_value is not None and primary_col and not primary_block_id:
            prepared.append(
                {
                    "keyID": primary_col.get("id", ""),
                    "value": self._build_value("block", title_value, column_meta=primary_col),
                }
            )

        values: List[Dict[str, Any]] = []
        for item in prepared:
            item_with_row = dict(item)
            item_with_row["itemID"] = row_id
            values.append(item_with_row)
        if values:
            res = self.batch_set_cells(normalized, values)
            if res.get("code") != 0:
                raise ValidationError(f"批量设置单元格失败: {res.get('msg')}")
        return row_id

    def validate_database(self, av_id: str, cleanup: bool = True) -> Dict[str, Any]:
        normalized = self._normalize_av_id(av_id)
        checks: List[Dict[str, Any]] = []
        ok = True

        def _add_check(name: str, status: str, detail: str, data: Optional[Dict[str, Any]] = None) -> None:
            nonlocal ok
            item: Dict[str, Any] = {"name": name, "status": status, "detail": detail}
            if data:
                item["data"] = data
            checks.append(item)
            if status == "failed":
                ok = False

        schema = self.get_schema(normalized)
        columns = schema.get("columns", [])
        primary_col = next((c for c in columns if c.get("type") == "block"), None)
        if not primary_col:
            _add_check("primary-column", "failed", "Schema has no block primary column")
        else:
            is_first = bool(columns) and columns[0].get("id") == primary_col.get("id")
            status = "passed" if is_first else "warning"
            _add_check(
                "primary-column",
                status,
                "Primary block column detected",
                {"column": primary_col.get("name", ""), "is_first": is_first},
            )

        try:
            self.add_row_with_data(
                normalized,
                {"__title": "[validate] strict-check", "__unknown_validate_col__": "x"},
                strict=True,
            )
            _add_check("strict-column-mapping", "failed", "Unknown column unexpectedly accepted with strict mode")
        except ValidationError:
            _add_check("strict-column-mapping", "passed", "Unknown column is rejected in strict mode")
        except Exception as exc:
            _add_check("strict-column-mapping", "failed", f"Strict mode check failed unexpectedly: {exc}")

        date_col = next(
            (c for c in columns if c.get("type") == "date" and c.get("writable")),
            None,
        )
        if not date_col:
            _add_check("date-epoch-ms", "skipped", "No writable date column in schema")
        else:
            expected_ms = int(dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
            validate_row_id = ""
            try:
                validate_row_id = self.add_row_with_data(
                    normalized,
                    {"__title": "[validate] date-check", str(date_col.get("name", "")): "2026-03-01"},
                    strict=True,
                )
                rendered = self.render(normalized, wait_ready=True)
                rows = rendered.get("data", {}).get("view", {}).get("rows", []) or []
                target_row = next((r for r in rows if r.get("id") == validate_row_id), None)
                if not target_row:
                    _add_check("date-epoch-ms", "failed", "Validation row not found after write")
                else:
                    target_cell = None
                    for cell in target_row.get("cells", []) or []:
                        value = cell.get("value", {}) or {}
                        if value.get("keyID") == date_col.get("id"):
                            target_cell = value
                            break
                    if not target_cell:
                        _add_check("date-epoch-ms", "failed", "Date cell missing in validation row")
                    else:
                        date_data = target_cell.get("date", {}) or {}
                        content = date_data.get("content")
                        try:
                            content_int = int(content)
                        except (TypeError, ValueError):
                            content_int = -1
                        is_epoch_ms = content_int >= 10**12
                        exact_match = content_int == expected_ms
                        if is_epoch_ms and exact_match:
                            _add_check(
                                "date-epoch-ms",
                                "passed",
                                "Date is persisted as epoch milliseconds",
                                {"content": content_int, "expected": expected_ms, "isNotTime": date_data.get("isNotTime")},
                            )
                        else:
                            _add_check(
                                "date-epoch-ms",
                                "failed",
                                "Date content is not expected epoch milliseconds",
                                {"content": content, "expected": expected_ms, "isNotTime": date_data.get("isNotTime")},
                            )
            except Exception as exc:
                _add_check("date-epoch-ms", "failed", f"Date validation failed: {exc}")
            finally:
                if cleanup and validate_row_id:
                    try:
                        self.remove_rows(normalized, [validate_row_id])
                    except Exception:
                        _add_check("cleanup", "warning", f"Failed to remove validation row: {validate_row_id}")

        return {
            "code": 0 if ok else 1,
            "msg": "" if ok else "validation failed",
            "data": {
                "av_id": normalized,
                "ok": ok,
                "cleanup": bool(cleanup),
                "checks": checks,
            },
        }

    def seed_rows(self, av_id: str, rows: List[Dict[str, Any]], strict: bool = True) -> Dict[str, Any]:
        normalized = self._normalize_av_id(av_id)
        row_ids: List[str] = []
        errors: List[Dict[str, Any]] = []
        for idx, row in enumerate(rows):
            try:
                row_id = self.add_row_with_data(normalized, row, strict=strict)
                row_ids.append(row_id)
            except Exception as exc:
                errors.append({"index": idx, "error": str(exc)})
        ok = not errors
        return {
            "code": 0 if ok else 1,
            "msg": "" if ok else "seed failed",
            "data": {
                "av_id": normalized,
                "strict": bool(strict),
                "requested": len(rows),
                "inserted": len(row_ids),
                "row_ids": row_ids,
                "errors": errors,
            },
        }

    def _normalize_columns(self, columns: Optional[List[Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for item in columns or []:
            col_name = ""
            col_type = "text"
            col_options: List[Dict[str, str]] = []

            if isinstance(item, str) and ":" in item:
                col_name, col_type = item.split(":", 1)
            elif isinstance(item, dict):
                col_name = str(item.get("name", "")).strip()
                col_type = str(item.get("type", "text")).strip()
                raw_options = item.get("options", [])
                if isinstance(raw_options, list):
                    for opt in raw_options:
                        if isinstance(opt, dict):
                            name = str(opt.get("name", "")).strip()
                            color = str(opt.get("color", "")).strip()
                            if name:
                                col_options.append(
                                    {
                                        "name": name,
                                        "color": color or random.choice(self.SELECT_COLOR_POOL),
                                        "desc": str(opt.get("desc", "")).strip(),
                                    }
                                )
                        else:
                            text = str(opt).strip()
                            if text:
                                col_options.append(
                                    {
                                        "name": text,
                                        "color": random.choice(self.SELECT_COLOR_POOL),
                                        "desc": "",
                                    }
                                )
            else:
                continue

            if not str(col_name).strip():
                continue
            normalized.append(
                {
                    "name": str(col_name).strip(),
                    "type": self._normalize_key_type(col_type or "text"),
                    "options": col_options,
                }
            )
        return normalized

    def _prime_select_options(self, av_id: str, select_col_options: List[Dict[str, Any]]) -> None:
        if not select_col_options:
            return
        temp_row_id = self.add_row(av_id)
        try:
            for col in select_col_options:
                key_id = col["key_id"]
                options = col["options"]
                if col["type"] == "select":
                    for opt in options:
                        value = {
                            "type": "select",
                            "mSelect": [
                                {
                                    "content": opt["name"],
                                    "color": opt["color"],
                                }
                            ],
                        }
                        res = self.set_cell(av_id, key_id, temp_row_id, value, col_type="select")
                        if res.get("code") != 0:
                            raise ValidationError(f"初始化 select 选项失败 {opt['name']}: {res.get('msg')}")
                else:
                    value = {
                        "type": "mSelect",
                        "mSelect": [
                            {
                                "content": opt["name"],
                                "color": opt["color"],
                            }
                            for opt in options
                        ],
                    }
                    res = self.set_cell(av_id, key_id, temp_row_id, value, col_type="mSelect")
                    if res.get("code") != 0:
                        raise ValidationError(f"初始化 mSelect 选项失败: {res.get('msg')}")
        finally:
            self.remove_rows(av_id, [temp_row_id])

    def _configure_av_columns(
        self,
        av_id: str,
        columns: Optional[List[Any]] = None,
        *,
        remove_default_single_select: bool = False,
    ) -> None:
        normalized_cols = self._normalize_columns(columns)
        schema = self.get_schema(av_id)

        if remove_default_single_select:
            default_single = next(
                (
                    c
                    for c in schema.get("columns", [])
                    if c.get("type") == "select" and c.get("name") in ("单选", "Select")
                ),
                None,
            )
            if default_single and default_single.get("id"):
                self.remove_column(av_id, default_single.get("id", ""))
                schema = self.get_schema(av_id)

        primary_col = next((c for c in schema.get("columns", []) if c.get("type") == "block"), None)
        previous = primary_col.get("id", "") if primary_col else ""
        select_col_options: List[Dict[str, Any]] = []

        for col in normalized_cols:
            col_name = col["name"]
            col_type = col["type"]
            col_options = col.get("options", [])
            key_id = f"{av_id}-{make_siyuan_like_id('col')}"
            result = self.add_column(
                av_id=av_id,
                key_name=col_name,
                key_type=col_type,
                previous_key_id=previous,
                key_id=key_id,
                options=col_options,
            )
            if result.get("code") != 0:
                raise ValidationError(f"添加列失败 {col_name}: {result.get('msg')}")
            previous = key_id
            if col_options and col_type in ("select", "mSelect"):
                select_col_options.append(
                    {
                        "key_id": key_id,
                        "type": col_type,
                        "options": col_options,
                    }
                )

        self._prime_select_options(av_id, select_col_options)

    def _list_av_blocks(self, doc_id: str) -> List[Dict[str, Any]]:
        safe_doc = str(doc_id).replace("'", "''")
        sql = (
            "SELECT id, parent_id, sort FROM blocks "
            f"WHERE root_id='{safe_doc}' AND type='av' ORDER BY sort DESC"
        )
        res = self.client.sql_query(sql)
        if res.get("code") != 0:
            raise ValidationError(f"查询文档 AV 块失败: {res.get('msg')}")
        return res.get("data", []) or []

    def _last_top_level_block_id(self, doc_id: str) -> str:
        safe_doc = str(doc_id).replace("'", "''")
        sql = (
            "SELECT id FROM blocks "
            f"WHERE root_id='{safe_doc}' AND parent_id='{safe_doc}' AND id!='{safe_doc}' "
            "ORDER BY sort DESC LIMIT 1"
        )
        res = self.client.sql_query(sql)
        if res.get("code") != 0:
            raise ValidationError(f"查询文档顶层块失败: {res.get('msg')}")
        rows = res.get("data", []) or []
        if rows:
            return rows[0].get("id", "")
        return ""

    def create_database(self, notebook_id: str, path: str, columns: Optional[List[Any]] = None):
        markdown = '<div data-type="NodeAttributeView" data-av-type="table"></div>'
        create_res = self.client.create_doc(notebook_id, path, markdown)
        if create_res.get("code") != 0:
            raise ValidationError(f"创建数据库文档失败: {create_res.get('msg')}")

        doc_id = str(create_res.get("data", ""))
        if not doc_id:
            raise ValidationError("创建数据库文档成功但未返回 doc_id")

        block_id = ""
        for _ in range(6):
            sql = (
                "SELECT id FROM blocks "
                f"WHERE root_id='{doc_id}' AND type='av' LIMIT 1"
            )
            res = self.client.sql_query(sql)
            if res.get("code") == 0 and res.get("data"):
                block_id = res["data"][0].get("id", "")
                if block_id:
                    break
            time.sleep(0.2)

        if not block_id:
            raise ValidationError("创建数据库后无法定位 av block")

        av_id = self.get_av_id_from_block(block_id)
        self.wait_until_ready(av_id)
        self._configure_av_columns(av_id, columns=columns, remove_default_single_select=False)

        return {"doc_id": doc_id, "block_id": block_id, "av_id": av_id}

    def create_inline_template(
        self,
        parent_id: str,
        columns: Optional[List[Any]] = None,
        rows: Optional[List[Dict[str, Any]]] = None,
        strict: bool = True,
        remove_default_single_select: bool = True,
    ) -> Dict[str, Any]:
        parent = str(parent_id or "").strip()
        if not parent:
            raise ValidationError("缺少 parent_id")

        parent_block = self.client.get_block(parent)
        if not parent_block:
            raise ValidationError(f"找不到块: {parent}")

        parent_type = str(parent_block.get("type", "")).strip()
        if parent_type == "d":
            doc_id = str(parent_block.get("id", "")).strip()
            if not doc_id:
                raise ValidationError(f"无法解析文档 ID: {parent}")
            top_level_anchor = self._last_top_level_block_id(doc_id)
            insert_mode = "insert-after" if top_level_anchor else "insert-root"
            insert_target = top_level_anchor or doc_id
        else:
            doc_id = self.client.resolve_root_doc_id(parent)
            insert_mode = "append-child"
            insert_target = parent

        before = {row.get("id", "") for row in self._list_av_blocks(doc_id) if row.get("id")}

        markdown = '<div data-type="NodeAttributeView" data-av-type="table"></div>'
        if insert_mode == "insert-after":
            append_res = self.client.insert_block_after(insert_target, markdown)
        elif insert_mode == "insert-root":
            append_res = self.client.insert_block(insert_target, "markdown", markdown)
        else:
            append_res = self.client.append_block(insert_target, markdown)
        if append_res.get("code") != 0:
            raise ValidationError(f"页面内插入数据库失败: {append_res.get('msg')}")

        block_id = ""
        for _ in range(10):
            rows_now = self._list_av_blocks(doc_id)
            new_rows = [r for r in rows_now if r.get("id", "") and r.get("id", "") not in before]
            if new_rows:
                preferred_parent = parent if parent_type != "d" else doc_id
                preferred = next((r for r in new_rows if r.get("parent_id", "") == preferred_parent), None)
                block_id = (preferred or new_rows[0]).get("id", "")
                if block_id:
                    break
            time.sleep(0.2)

        if not block_id:
            raise ValidationError("页面内建库后无法定位新的 av block")

        av_id = self.get_av_id_from_block(block_id)
        self.wait_until_ready(av_id)
        self._configure_av_columns(
            av_id,
            columns=columns,
            remove_default_single_select=remove_default_single_select,
        )

        seed_info = None
        if rows:
            seed_result = self.seed_rows(av_id, rows, strict=strict)
            seed_info = seed_result.get("data", {})

        return {
            "doc_id": doc_id,
            "parent_id": parent,
            "block_id": block_id,
            "av_id": av_id,
            "inline": True,
            "seed": seed_info,
        }
