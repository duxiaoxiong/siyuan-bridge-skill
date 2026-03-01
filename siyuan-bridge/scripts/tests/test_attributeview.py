import unittest
from unittest.mock import patch

from scripts.modules.attributeview import AttributeViewClient
from scripts.core.errors import ValidationError


class DummyClient:
    allow_unsafe_write = True

    def __init__(self):
        self._render_calls = 0
        self._reads = []

    def get_block(self, raw_id):
        if raw_id == "20260227-avblock":
            return {"id": raw_id, "type": "av"}
        return {}

    def resolve_doc_id_from_av_id(self, av_id):
        if av_id == "20260227-realav":
            return "20260227-doc"
        return ""

    def get_block_kramdown(self, block_id):
        return {
            "code": 0,
            "msg": "",
            "data": {
                "kramdown": '<div data-type="NodeAttributeView" data-av-id="20260227-realav" data-av-type="table"></div>'
            },
        }

    def _post(self, path, payload):
        if path != "/api/av/renderAttributeView":
            return {"code": 0, "msg": "", "data": {}}
        self._render_calls += 1
        if self._render_calls < 3:
            return {"code": -1, "msg": "view not found", "data": None}
        return {
            "code": 0,
            "msg": "",
            "data": {"id": payload.get("id"), "view": {"id": "view-1", "columns": [], "rows": []}},
        }

    def _mark_read(self, doc_id, source="unknown"):
        self._reads.append((doc_id, source))


class SchemaClient:
    allow_unsafe_write = True

    def __init__(self):
        self.last_guard_payload = None
        self.rows = ["row-1"]

    def get_block(self, _):
        return {}

    def resolve_doc_id_from_av_id(self, _):
        return "doc-1"

    def _mark_read(self, *_args, **_kwargs):
        return None

    def _post(self, path, payload):
        if path == "/api/av/renderAttributeView":
            return {
                "code": 0,
                "msg": "",
                "data": {
                    "id": payload.get("id"),
                    "view": {
                        "id": "view-1",
                        "columns": [
                            {"id": "col-primary", "name": "主键", "type": "block"},
                            {"id": "col-task", "name": "Task", "type": "text"},
                            {"id": "col-due", "name": "Due", "type": "date"},
                            {
                                "id": "col-status",
                                "name": "Status",
                                "type": "select",
                                "options": [{"name": "Todo", "color": "6"}],
                            },
                            {"id": "col-roll", "name": "Roll", "type": "rollup"},
                        ],
                        "rows": [{"id": rid} for rid in self.rows],
                    },
                },
            }
        return {"code": 0, "msg": "", "data": {}}

    def post_with_guard(self, path, payload, operation, doc_id, log_action):
        self.last_guard_payload = {
            "path": path,
            "payload": payload,
            "operation": operation,
            "doc_id": doc_id,
            "log_action": log_action,
        }
        if path == "/api/av/addAttributeViewBlocks":
            srcs = payload.get("srcs", [])
            for src in srcs:
                self.rows.append(src.get("id", "row-2"))
        return {"code": 0, "msg": "", "data": {"value": payload.get("value")}}


class CreateDbClient:
    allow_unsafe_write = True

    def __init__(self):
        self.add_key_payloads = []
        self.rows = []
        self.last_set_payload = None

    def get_block(self, _):
        return {}

    def resolve_doc_id_from_av_id(self, _):
        return "doc-1"

    def create_doc(self, _notebook_id, _path, _markdown):
        return {"code": 0, "msg": "", "data": "doc-1"}

    def sql_query(self, _sql):
        return {"code": 0, "msg": "", "data": [{"id": "av-block-1"}]}

    def get_block_kramdown(self, _block_id):
        return {
            "code": 0,
            "msg": "",
            "data": {
                "kramdown": '<div data-type="NodeAttributeView" data-av-id="real-av-1" data-av-type="table"></div>'
            },
        }

    def _post(self, path, payload):
        if path == "/api/av/renderAttributeView":
            return {
                "code": 0,
                "msg": "",
                "data": {
                    "id": payload.get("id"),
                    "view": {
                        "id": "view-1",
                        "columns": [
                            {"id": "col-primary", "name": "主键", "type": "block"},
                            {"id": "col-default", "name": "单选", "type": "select"},
                        ],
                        "rows": [{"id": rid} for rid in self.rows],
                    },
                },
            }
        return {"code": 0, "msg": "", "data": {}}

    def post_with_guard(self, path, payload, operation, doc_id, log_action):
        if path == "/api/av/addAttributeViewKey":
            self.add_key_payloads.append(payload)
        if path == "/api/av/addAttributeViewBlocks":
            srcs = payload.get("srcs", [])
            for src in srcs:
                self.rows.append(src.get("id"))
        if path == "/api/av/setAttributeViewBlockAttr":
            self.last_set_payload = payload
        if path == "/api/av/removeAttributeViewBlocks":
            to_remove = set(payload.get("srcIDs", []))
            self.rows = [x for x in self.rows if x not in to_remove]
        return {"code": 0, "msg": "", "data": {}}

    def _mark_read(self, *_args, **_kwargs):
        return None


class ValidateClient:
    allow_unsafe_write = True

    def __init__(self, include_primary: bool = True):
        self.include_primary = include_primary
        self.rows = {}

    def get_block(self, _):
        return {}

    def resolve_doc_id_from_av_id(self, _):
        return "doc-1"

    def _mark_read(self, *_args, **_kwargs):
        return None

    def _columns(self):
        columns = [
            {"id": "col-primary", "name": "主键", "type": "block"},
            {"id": "col-due", "name": "Due", "type": "date"},
            {"id": "col-task", "name": "Task", "type": "text"},
        ]
        if not self.include_primary:
            return [c for c in columns if c["type"] != "block"]
        return columns

    def _render_rows(self):
        rendered = []
        for row_id, row in self.rows.items():
            cells = []
            for key_id, value in row.get("values", {}).items():
                payload = dict(value)
                payload["keyID"] = key_id
                cells.append({"value": payload, "valueType": value.get("type", "")})
            rendered.append({"id": row_id, "cells": cells})
        return rendered

    def _post(self, path, payload):
        if path == "/api/av/renderAttributeView":
            return {
                "code": 0,
                "msg": "",
                "data": {
                    "id": payload.get("id"),
                    "view": {
                        "id": "view-1",
                        "columns": self._columns(),
                        "rows": self._render_rows(),
                    },
                },
            }
        return {"code": 0, "msg": "", "data": {}}

    def post_with_guard(self, path, payload, operation, doc_id, log_action):
        if path == "/api/av/addAttributeViewBlocks":
            for src in payload.get("srcs", []):
                row_id = src.get("id")
                if row_id:
                    self.rows[row_id] = {"values": {}}
            return {"code": 0, "msg": "", "data": {}}

        if path == "/api/av/batchSetAttributeViewBlockAttrs":
            for item in payload.get("values", []):
                row = self.rows.setdefault(item.get("itemID", ""), {"values": {}})
                row["values"][item.get("keyID", "")] = item.get("value", {})
            return {"code": 0, "msg": "", "data": {}}

        if path == "/api/av/removeAttributeViewBlocks":
            for rid in payload.get("srcIDs", []):
                self.rows.pop(rid, None)
            return {"code": 0, "msg": "", "data": {}}

        return {"code": 0, "msg": "", "data": {}}


class InlineTemplateClient:
    allow_unsafe_write = True

    def __init__(self, has_top_level: bool = True):
        self.has_top_level = has_top_level
        self.rows = []
        self.av_blocks = []
        self.columns = [
            {"id": "col-primary", "name": "主键", "type": "block"},
            {"id": "col-default", "name": "单选", "type": "select"},
        ]
        self.insert_mode = ""
        self.insert_target = ""

    def get_block(self, block_id):
        if block_id == "doc-1":
            return {"id": "doc-1", "type": "d"}
        if block_id == "blk-parent":
            return {"id": "blk-parent", "type": "p", "root_id": "doc-1"}
        return {}

    def resolve_root_doc_id(self, block_id):
        if block_id == "blk-parent":
            return "doc-1"
        return ""

    def resolve_doc_id_from_av_id(self, _av_id):
        return "doc-1"

    def sql_query(self, sql):
        if "AND type='av'" in sql:
            return {"code": 0, "msg": "", "data": list(self.av_blocks)}
        if "parent_id='doc-1'" in sql and "LIMIT 1" in sql:
            return {"code": 0, "msg": "", "data": [{"id": "blk-last"}] if self.has_top_level else []}
        return {"code": 0, "msg": "", "data": []}

    def append_block(self, parent_id, _markdown):
        self.insert_mode = "append-child"
        self.insert_target = parent_id
        self.av_blocks = [{"id": "av-block-new", "parent_id": parent_id, "sort": "999"}]
        return {"code": 0, "msg": "", "data": {}}

    def insert_block_after(self, previous_id, _markdown):
        self.insert_mode = "insert-after"
        self.insert_target = previous_id
        self.av_blocks = [{"id": "av-block-new", "parent_id": "doc-1", "sort": "999"}]
        return {"code": 0, "msg": "", "data": {}}

    def insert_block(self, parent_id, _data_type, _data, previous_id=""):
        self.insert_mode = "insert-root"
        self.insert_target = parent_id
        self.av_blocks = [{"id": "av-block-new", "parent_id": "doc-1", "sort": "999"}]
        return {"code": 0, "msg": "", "data": {"previous_id": previous_id}}

    def get_block_kramdown(self, _block_id):
        return {
            "code": 0,
            "msg": "",
            "data": {
                "kramdown": '<div data-type="NodeAttributeView" data-av-id="real-av-1" data-av-type="table"></div>'
            },
        }

    def _mark_read(self, *_args, **_kwargs):
        return None

    def _post(self, path, payload):
        if path == "/api/av/renderAttributeView":
            return {
                "code": 0,
                "msg": "",
                "data": {
                    "id": payload.get("id"),
                    "view": {
                        "id": "view-1",
                        "columns": list(self.columns),
                        "rows": [{"id": rid} for rid in self.rows],
                    },
                },
            }
        return {"code": 0, "msg": "", "data": {}}

    def post_with_guard(self, path, payload, operation, doc_id, log_action):
        if path == "/api/av/addAttributeViewKey":
            self.columns.append(
                {
                    "id": payload.get("keyID", ""),
                    "name": payload.get("keyName", ""),
                    "type": payload.get("keyType", "text"),
                    "options": payload.get("options", []),
                }
            )
        if path == "/api/av/removeAttributeViewKey":
            key_id = payload.get("keyID", "")
            self.columns = [col for col in self.columns if col.get("id") != key_id]
        if path == "/api/av/addAttributeViewBlocks":
            for src in payload.get("srcs", []):
                rid = src.get("id")
                if rid:
                    self.rows.append(rid)
        if path == "/api/av/removeAttributeViewBlocks":
            to_remove = set(payload.get("srcIDs", []))
            self.rows = [rid for rid in self.rows if rid not in to_remove]
        return {"code": 0, "msg": "", "data": {"doc_id": doc_id, "op": operation, "log": log_action}}


class AttributeViewTests(unittest.TestCase):
    def setUp(self):
        self.av = AttributeViewClient(DummyClient())

    def test_build_text_value(self):
        value = self.av._build_value("text", "hello")
        self.assertEqual(value["type"], "text")
        self.assertEqual(value["text"]["content"], "hello")

    def test_build_number_value(self):
        value = self.av._build_value("number", "12")
        self.assertEqual(value["type"], "number")
        self.assertEqual(value["number"]["content"], 12.0)

    def test_build_date_value(self):
        value = self.av._build_value("date", "2026-02-27")
        self.assertEqual(value["type"], "date")
        self.assertEqual(value["date"]["content"], 1772150400000)

    def test_build_checkbox_value(self):
        value = self.av._build_value("checkbox", 1)
        self.assertTrue(value["checkbox"]["checked"])

    def test_build_checkbox_value_from_string(self):
        value = self.av._build_value("checkbox", "true")
        self.assertTrue(value["checkbox"]["checked"])

    def test_build_relation_value(self):
        value = self.av._build_value("relation", "20260227-aaa,20260227-bbb")
        self.assertEqual(value["type"], "relation")
        self.assertEqual(value["relation"]["blockIDs"], ["20260227-aaa", "20260227-bbb"])

    def test_build_masset_value(self):
        value = self.av._build_value("mAsset", "assets/demo.png")
        self.assertEqual(value["type"], "mAsset")
        self.assertEqual(value["mAsset"][0]["content"], "assets/demo.png")

    def test_reject_read_only_value_type(self):
        with self.assertRaises(ValidationError):
            self.av._build_value("rollup", "x")

    def test_normalize_av_id_from_av_block_id(self):
        normalized = self.av._normalize_av_id("20260227-avblock")
        self.assertEqual(normalized, "20260227-realav")

    def test_wait_until_ready(self):
        res = self.av.wait_until_ready("20260227-avblock", max_attempts=5, sleep_seconds=0)
        self.assertEqual(res.get("code"), 0)
        self.assertEqual(self.av.client._render_calls, 3)
        self.assertEqual(self.av.client._reads[-1][0], "20260227-doc")

    def test_schema_has_writable_flag(self):
        av = AttributeViewClient(SchemaClient())
        schema = av.get_schema("20260227-realav")
        writable = {c["name"]: c["writable"] for c in schema["columns"]}
        self.assertTrue(writable["Task"])
        self.assertFalse(writable["Roll"])

    def test_set_cell_by_name_infers_type(self):
        client = SchemaClient()
        av = AttributeViewClient(client)
        av.set_cell_by_name("20260227-realav", "row-1", "Due", "2026-02-27")
        self.assertEqual(client.last_guard_payload["payload"]["keyID"], "col-due")
        self.assertEqual(client.last_guard_payload["payload"]["value"]["type"], "date")

    def test_set_cell_by_name_uses_existing_select_option_color(self):
        client = SchemaClient()
        av = AttributeViewClient(client)
        av.set_cell_by_name("20260227-realav", "row-1", "Status", "Todo")
        value = client.last_guard_payload["payload"]["value"]
        self.assertEqual(value["type"], "select")
        self.assertEqual(value["mSelect"][0]["color"], "6")

    def test_add_column_defaults_after_primary(self):
        client = SchemaClient()
        av = AttributeViewClient(client)
        av.add_column("20260227-realav", "Priority", "select")
        payload = client.last_guard_payload["payload"]
        self.assertEqual(client.last_guard_payload["path"], "/api/av/addAttributeViewKey")
        self.assertEqual(payload["previousKeyID"], "col-primary")

    def test_add_column_prime_select_options(self):
        client = CreateDbClient()
        av = AttributeViewClient(client)
        av.add_column(
            "real-av-1",
            "Status",
            "select",
            options=[{"name": "Todo", "color": "2"}],
            prime_options=True,
        )
        self.assertEqual(client.add_key_payloads[0]["previousKeyID"], "col-primary")
        self.assertIsNotNone(client.last_set_payload)

    def test_select_option_random_color_default(self):
        with patch("scripts.modules.attributeview.random.choice", return_value="9"):
            value = self.av._build_value("select", "NewStatus")
        self.assertEqual(value["type"], "select")
        self.assertEqual(value["mSelect"][0]["color"], "9")

    def test_select_option_explicit_color(self):
        value = self.av._build_value("select", "Doing|3")
        self.assertEqual(value["type"], "select")
        self.assertEqual(value["mSelect"][0]["content"], "Doing")
        self.assertEqual(value["mSelect"][0]["color"], "3")

    def test_add_row_with_data_strict_rejects_unknown(self):
        av = AttributeViewClient(SchemaClient())
        with self.assertRaises(ValidationError):
            av.add_row_with_data("20260227-realav", {"UnknownCol": "x"}, strict=True)

    def test_add_row_with_data_title_maps_to_primary(self):
        client = SchemaClient()
        av = AttributeViewClient(client)
        av.add_row_with_data("20260227-realav", {"Task": "A", "__title": "Row Title"}, strict=True)
        self.assertEqual(client.last_guard_payload["path"], "/api/av/batchSetAttributeViewBlockAttrs")
        values = client.last_guard_payload["payload"]["values"]
        key_ids = [v["keyID"] for v in values]
        self.assertIn("col-primary", key_ids)

    def test_add_row_with_data_primary_block_id(self):
        client = SchemaClient()
        av = AttributeViewClient(client)
        row_id = av.add_row_with_data(
            "20260227-realav",
            {"Task": "From linked block", "__primary_block_id": "20260227-linked"},
            strict=True,
        )
        self.assertEqual(row_id, "20260227-linked")

    def test_create_database_inserts_columns_after_primary(self):
        client = CreateDbClient()
        av = AttributeViewClient(client)
        av.create_database(
            "nb-1",
            "/test/path",
            columns=[
                {"name": "Task", "type": "text"},
                {"name": "Status", "type": "select", "options": ["Todo", {"name": "Doing", "color": "4"}]},
            ],
        )
        self.assertGreaterEqual(len(client.add_key_payloads), 2)
        first = client.add_key_payloads[0]
        second = client.add_key_payloads[1]
        self.assertEqual(first["previousKeyID"], "col-primary")
        self.assertEqual(second["previousKeyID"], first["keyID"])
        self.assertEqual(second["keyType"], "select")
        self.assertEqual(second["options"][1]["name"], "Doing")
        self.assertEqual(second["options"][1]["color"], "4")
        self.assertIsNotNone(client.last_set_payload)

    def test_validate_database_success(self):
        client = ValidateClient(include_primary=True)
        av = AttributeViewClient(client)
        result = av.validate_database("20260227-realav", cleanup=True)
        self.assertEqual(result["code"], 0)
        self.assertTrue(result["data"]["ok"])
        self.assertFalse(client.rows)
        checks = {item["name"]: item["status"] for item in result["data"]["checks"]}
        self.assertEqual(checks["primary-column"], "passed")
        self.assertEqual(checks["strict-column-mapping"], "passed")
        self.assertEqual(checks["date-epoch-ms"], "passed")

    def test_validate_database_missing_primary(self):
        client = ValidateClient(include_primary=False)
        av = AttributeViewClient(client)
        result = av.validate_database("20260227-realav", cleanup=True)
        self.assertEqual(result["code"], 1)
        self.assertFalse(result["data"]["ok"])
        checks = {item["name"]: item["status"] for item in result["data"]["checks"]}
        self.assertEqual(checks["primary-column"], "failed")

    def test_seed_rows_success(self):
        av = AttributeViewClient(SchemaClient())
        result = av.seed_rows("20260227-realav", [{"Task": "A"}, {"Task": "B"}], strict=True)
        self.assertEqual(result["code"], 0)
        self.assertEqual(result["data"]["inserted"], 2)

    def test_seed_rows_with_error(self):
        av = AttributeViewClient(SchemaClient())
        result = av.seed_rows("20260227-realav", [{"UnknownCol": "x"}], strict=True)
        self.assertEqual(result["code"], 1)
        self.assertEqual(result["data"]["inserted"], 0)
        self.assertEqual(len(result["data"]["errors"]), 1)

    def test_create_inline_template_with_doc_id_uses_insert_after(self):
        client = InlineTemplateClient(has_top_level=True)
        av = AttributeViewClient(client)
        result = av.create_inline_template(
            "doc-1",
            columns=[{"name": "Task", "type": "text"}],
            rows=[{"Task": "A"}],
            strict=True,
        )
        self.assertEqual(client.insert_mode, "insert-after")
        self.assertEqual(client.insert_target, "blk-last")
        self.assertEqual(result["doc_id"], "doc-1")
        self.assertEqual(result["seed"]["inserted"], 1)

    def test_create_inline_template_with_empty_doc_uses_insert_root(self):
        client = InlineTemplateClient(has_top_level=False)
        av = AttributeViewClient(client)
        result = av.create_inline_template(
            "doc-1",
            columns=[{"name": "Task", "type": "text"}],
            rows=[],
            strict=True,
        )
        self.assertEqual(client.insert_mode, "insert-root")
        self.assertEqual(client.insert_target, "doc-1")
        self.assertEqual(result["doc_id"], "doc-1")

    def test_create_inline_template_with_block_parent_uses_append_child(self):
        client = InlineTemplateClient(has_top_level=True)
        av = AttributeViewClient(client)
        result = av.create_inline_template(
            "blk-parent",
            columns=[{"name": "Task", "type": "text"}],
            rows=[],
            strict=True,
        )
        self.assertEqual(client.insert_mode, "append-child")
        self.assertEqual(client.insert_target, "blk-parent")
        self.assertEqual(result["doc_id"], "doc-1")


if __name__ == "__main__":
    unittest.main()
