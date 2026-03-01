import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from scripts.cli import siyuan_cli


class FakeClient:
    class _Settings:
        api_url = "http://127.0.0.1:6806"
        token = "test-token"
        token_file = "~/.config/siyuan/api_token"

    def __init__(self):
        self.settings = self._Settings()
        self.allow_unsafe_write = False

    def update_block(self, block_id, content):
        return {"code": 0, "data": {"id": block_id, "content": content}}

    def create_doc(self, notebook_id, path, markdown=""):
        return {"code": 0, "msg": "", "data": "doc-created-1", "payload": {"notebook_id": notebook_id, "path": path, "markdown": markdown}}

    def append_block(self, parent_id, markdown):
        return {"code": 0, "msg": "", "data": {"parent_id": parent_id, "markdown": markdown}}

    def prepend_block(self, parent_id, markdown):
        return {"code": 0, "msg": "", "data": {"parent_id": parent_id, "markdown": markdown}}

    def insert_block_after(self, previous_id, markdown):
        return {"code": 0, "msg": "", "data": {"previous_id": previous_id, "markdown": markdown}}

    def get_version(self):
        return {"code": 0, "msg": "", "data": "3.5.7"}

    def ls_notebooks(self):
        return {"code": 0, "msg": "", "data": {"notebooks": [{"id": "nb-1", "name": "main", "icon": "1F4D3"}]}}


class FakeSearch:
    def __init__(self, _):
        pass

    def search_by_type(self, block_type, subtype="", box="", limit=20):
        return {
            "code": 0,
            "msg": "",
            "data": [
                {
                    "id": "blk-1",
                    "hpath": "/Demo",
                    "type": block_type,
                    "subtype": subtype,
                    "content": f"box={box} limit={limit}",
                }
            ],
        }

    def search_recent_docs(self, limit=20, box=""):
        return {
            "code": 0,
            "msg": "",
            "data": [
                {
                    "id": "doc-1",
                    "content": "Recent Doc",
                    "hpath": "/Recent/Doc",
                    "updated": "20260227150000",
                    "box": box or "nb-1",
                    "limit": limit,
                }
            ],
        }


class FakeAV:
    SUPPORTED_KEY_TYPES = ("text", "number")
    READ_ONLY_VALUE_TYPES = ("rollup",)

    def __init__(self, _):
        self.rows = []
        self.last_add_col = {}
        self.inline_calls = []

    def get_schema(self, _):
        return {"av_id": "av-1", "view_id": "view-1", "row_ids": [], "columns": []}

    def set_cell_by_name(self, av_id, row_id, key_ref, value):
        return {
            "code": 0,
            "msg": "",
            "data": {"av_id": av_id, "row_id": row_id, "key_ref": key_ref, "value": value},
        }

    def create_database(self, notebook_id, path, columns=None):
        return {
            "doc_id": "doc-1",
            "block_id": "blk-av-1",
            "av_id": "av-1",
            "notebook_id": notebook_id,
            "path": path,
            "columns": columns or [],
        }

    def create_inline_template(
        self,
        parent_id,
        columns=None,
        rows=None,
        strict=True,
        remove_default_single_select=True,
    ):
        payload = {
            "doc_id": "doc-1",
            "parent_id": parent_id,
            "block_id": "blk-inline-1",
            "av_id": "av-inline-1",
            "inline": True,
            "columns": columns or [],
            "rows": rows or [],
            "strict": strict,
            "remove_default_single_select": remove_default_single_select,
        }
        self.inline_calls.append(payload)
        return payload

    def add_column(
        self,
        av_id,
        key_name,
        key_type,
        key_icon="",
        previous_key_id="",
        key_id="",
        options=None,
        prime_options=False,
    ):
        self.last_add_col = {
            "av_id": av_id,
            "key_name": key_name,
            "key_type": key_type,
            "key_icon": key_icon,
            "previous_key_id": previous_key_id,
            "key_id": key_id,
            "options": options or [],
            "prime_options": bool(prime_options),
        }
        return {"code": 0, "msg": "", "data": self.last_add_col}

    def add_row_with_data(self, av_id, payload, strict=False):
        self.rows.append((av_id, payload, strict))
        return f"row-{len(self.rows)}"

    def add_row(self, av_id, detached=True, source_block_id=""):
        self.rows.append((av_id, {"source_block_id": source_block_id, "detached": detached}, False))
        return source_block_id or f"row-{len(self.rows)}"

    def validate_database(self, av_id, cleanup=True):
        return {
            "code": 0,
            "msg": "",
            "data": {
                "av_id": av_id,
                "ok": True,
                "cleanup": cleanup,
                "checks": [
                    {"name": "primary-column", "status": "passed", "detail": "ok"},
                    {"name": "strict-column-mapping", "status": "passed", "detail": "ok"},
                    {"name": "date-epoch-ms", "status": "passed", "detail": "ok"},
                ],
            },
        }

    def seed_rows(self, av_id, rows, strict=True):
        return {
            "code": 0,
            "msg": "",
            "data": {
                "av_id": av_id,
                "requested": len(rows),
                "inserted": len(rows),
                "strict": strict,
                "errors": [],
            },
        }


class FakeBlocks:
    def __init__(self, _):
        pass

    def get_block_content(self, block_id, fmt="markdown"):
        if fmt == "meta":
            return {"code": 0, "msg": "", "data": {"id": block_id, "type": "p"}}
        return {"code": 0, "msg": "", "data": {"format": fmt, "content": f"{fmt}:{block_id}"}}

    def extract_refs(self, target):
        return {"code": 0, "msg": "", "data": {"target_id": target, "counts": {"block_refs": 1}}}

    def create_callout(self, parent_id, callout_type, text):
        return {"code": 0, "msg": "", "data": {"parent_id": parent_id, "type": callout_type, "text": text}}

    def update_callout(self, block_id, callout_type, text):
        return {"code": 0, "msg": "", "data": {"block_id": block_id, "type": callout_type, "text": text}}

    def create_safe_embed(self, parent_id, raw_sql, scope="box", limit=64):
        return {"code": 0, "msg": "", "data": {"parent_id": parent_id, "sql": raw_sql, "scope": scope, "limit": limit}}

    def create_super_scaffold(self, parent_id, layout="col", count=2):
        return {"code": 0, "msg": "", "data": {"parent_id": parent_id, "layout": layout, "count": count}}

    def append_table_row(self, block_id, cells=None):
        return {"code": 0, "msg": "", "data": {"block_id": block_id, "cells": cells or []}}


class FakeDocs:
    def __init__(self, _):
        pass

    def open_doc(self, doc_id, view="readable", **kwargs):
        return {"content": f"doc={doc_id} view={view} flags={kwargs}"}

    def import_content(self, source, source_type, notebook_id, path, raw_content=""):
        return {
            "code": 0,
            "msg": "",
            "data": {
                "doc_id": "doc-imported-1",
                "source": source,
                "source_type": source_type,
                "notebook_id": notebook_id,
                "path": path,
                "chars": len(raw_content or source),
            },
        }

    def write_full(self, target, markdown, mode="replace", notebook_id=""):
        return {
            "code": 0,
            "msg": "",
            "data": {
                "doc_id": target,
                "mode": mode,
                "notebook_id": notebook_id,
                "chars": len(markdown),
            },
        }


class CliCommandTests(unittest.TestCase):
    def test_decode_escaped_text_preserves_unicode(self):
        raw = "# 标题\\n\\n段落A\\n- [ ] 任务1"
        decoded = siyuan_cli._decode_escaped_text(raw)
        self.assertIn("# 标题", decoded)
        self.assertIn("段落A", decoded)
        self.assertIn("- [ ] 任务1", decoded)
        self.assertIn("\n\n", decoded)

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_unknown_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["unknown-cmd"])
        self.assertEqual(code, 1)
        self.assertIn("未知命令", buf.getvalue())

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_av_types_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["av", "types"])
        self.assertEqual(code, 0)
        self.assertIn("supported_key_types", buf.getvalue())

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_av_schema_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["av", "schema", "av-1"])
        self.assertEqual(code, 0)
        self.assertIn("\"view_id\": \"view-1\"", buf.getvalue())

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_av_set_cell_by_name_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["av", "set-cell-by-name", "av-1", "row-1", "Task", "hello"])
        self.assertEqual(code, 0)
        self.assertIn("\"key_ref\": \"Task\"", buf.getvalue())

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_help_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("命令: doctor", buf.getvalue())

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_doctor_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["doctor"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("\"ok\": true", out)
        self.assertIn("\"next_actions\"", out)

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_capabilities_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["capabilities", "--json"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("\"l1_commands\"", out)
        self.assertIn("\"next_actions\"", out)

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_av_help_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["av", "--help"])
        self.assertEqual(code, 0)
        self.assertIn("seed-test-db", buf.getvalue())

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_av_help_create_db_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["av", "help", "create-db"])
        self.assertEqual(code, 0)
        self.assertIn("用法: siyuan.py av create-db", buf.getvalue())

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_av_seed_test_db_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["av", "seed-test-db", "nb-1", "/test/path"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("\"seed_rows\": 5", out)
        self.assertIn("\"av_id\": \"av-1\"", out)

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_av_create_db_with_json_columns(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(
                [
                    "av",
                    "create-db",
                    "nb-1",
                    "/test/path",
                    '[{"name":"Status","type":"select","options":[{"name":"Todo","color":"2"}]}]',
                ]
            )
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("\"columns\": [", out)
        self.assertIn("\"name\": \"Status\"", out)

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_av_create_template_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["av", "create-template", "nb-1", "/template/db"])
        self.assertEqual(code, 0)
        self.assertIn("\"template\": true", buf.getvalue())

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_av_create_inline_template_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(
                [
                    "av",
                    "create-inline-template",
                    "doc-1",
                    '[{"name":"Status","type":"select","options":[{"name":"Todo","color":"2"}]}]',
                    "--rows",
                    '[{"__title":"Task A","Status":"Todo"}]',
                    "--no-strict",
                ]
            )
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("\"inline\": true", out)
        self.assertIn("\"remove_default_single_select\": true", out)
        self.assertIn("\"strict\": false", out)

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_av_add_col_with_options_and_after(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(
                [
                    "av",
                    "add-col",
                    "av-1",
                    "Status",
                    "select",
                    "--after",
                    "col-primary",
                    "--options",
                    '[{"name":"Todo","color":"2"}]',
                ]
            )
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("\"previous_key_id\": \"col-primary\"", out)
        self.assertIn("\"name\": \"Todo\"", out)
        self.assertIn("\"prime_options\": true", out)

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_av_seed_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["av", "seed", "av-1", "--rows", '[{"Task":"A"},{"Task":"B"}]'])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("\"inserted\": 2", out)
        self.assertIn("\"next_actions\"", out)

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_av_add_row_with_data_primary_block_flag(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(
                [
                    "av",
                    "add-row-with-data",
                    "av-1",
                    "--primary-block",
                    "20260227-linked",
                    '{"Task":"Demo"}',
                ]
            )
        self.assertEqual(code, 0)
        self.assertIn("\"row_id\": \"row-1\"", buf.getvalue())

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_av_validate_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["av", "validate", "av-1"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("\"ok\": true", out)
        self.assertIn("\"cleanup\": true", out)
        self.assertIn("\"next_actions\"", out)

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_av_validate_no_cleanup_flag(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["av", "validate", "av-1", "--no-cleanup"])
        self.assertEqual(code, 0)
        self.assertIn("\"cleanup\": false", buf.getvalue())

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_search_type_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["search-type", "callout", "--subtype", "TIP", "--limit", "5"])
        self.assertEqual(code, 0)
        self.assertIn("类型: callout/TIP", buf.getvalue())

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_docs_recent_json(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["docs", "recent", "--limit", "3", "--json"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("\"count\": 1", out)
        self.assertIn("\"next_actions\"", out)

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_doc_import_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["doc", "import", "hello", "--type", "md", "--to", "nb-1", "/demo/import"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("\"doc_id\": \"doc-imported-1\"", out)
        self.assertIn("\"next_actions\"", out)

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_doc_write_full_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["doc", "write-full", "doc-1", "--mode", "append", "demo content"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("\"mode\": \"append\"", out)
        self.assertIn("\"next_actions\"", out)

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_doc_write_full_rejects_literal_escaped_newline(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["doc", "write-full", "doc-1", "line1\\nline2"])
        self.assertEqual(code, 1)
        self.assertIn("检测到字面量 \\\\n", buf.getvalue())

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_doc_write_full_decode_escapes(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["doc", "write-full", "doc-1", "--decode-escapes", "line1\\nline2"])
        self.assertEqual(code, 0)
        self.assertIn("\"mode\": \"replace\"", buf.getvalue())

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_create_rejects_literal_escaped_newline(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["create", "nb-1", "/demo/path", "# Title\\n\\nBody"])
        self.assertEqual(code, 1)
        self.assertIn("检测到字面量 \\\\n", buf.getvalue())

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_create_decode_escapes(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["create", "nb-1", "/demo/path", "--decode-escapes", "# Title\\n\\nBody"])
        self.assertEqual(code, 0)
        self.assertIn("\"doc-created-1\"", buf.getvalue())

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_block_get_meta_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["block", "get", "blk-1", "--format", "meta"])
        self.assertEqual(code, 0)
        self.assertIn("\"type\": \"p\"", buf.getvalue())

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_refs_extract_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["refs", "extract", "blk-1"])
        self.assertEqual(code, 0)
        self.assertIn("\"target_id\": \"blk-1\"", buf.getvalue())

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_embed_create_safe_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(
                ["embed", "create-safe", "parent-1", "SELECT * FROM blocks", "--scope", "root", "--limit", "30"]
            )
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("\"scope\": \"root\"", out)
        self.assertIn("\"limit\": 30", out)

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_super_scaffold_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["super", "scaffold", "parent-1", "--layout", "row", "--count", "3"])
        self.assertEqual(code, 0)
        self.assertIn("\"layout\": \"row\"", buf.getvalue())

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_table_append_row_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["table", "append-row", "table-1", "[\"A\",\"B\"]"])
        self.assertEqual(code, 0)
        self.assertIn("\"cells\": [", buf.getvalue())

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_open_doc_typed_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["open-doc", "doc-1", "typed"])
        self.assertEqual(code, 0)
        self.assertIn("view=typed", buf.getvalue())

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_open_doc_typed_json_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["open-doc", "doc-1", "typed", "--json", "--semantic"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("\"code\": 0", out)
        self.assertIn("view=typed", out)

    @patch("scripts.cli.siyuan_cli.DEFAULT_CLIENT", new=FakeClient())
    @patch("scripts.cli.siyuan_cli.SearchModule", new=FakeSearch)
    @patch("scripts.cli.siyuan_cli.AttributeViewClient", new=FakeAV)
    @patch("scripts.cli.siyuan_cli.BlockModule", new=FakeBlocks)
    @patch("scripts.cli.siyuan_cli.DocumentModule", new=FakeDocs)
    def test_notebooks_json_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = siyuan_cli.main(["notebooks", "--json"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("\"notebooks\": [", out)
        self.assertIn("\"next_actions\"", out)


if __name__ == "__main__":
    unittest.main()
