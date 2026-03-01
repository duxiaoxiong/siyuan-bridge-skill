import unittest

from scripts.modules.documents import DocumentModule


class FakeClient:
    class Settings:
        open_doc_char_limit = 10000

    def __init__(self):
        self.settings = self.Settings()
        self.deleted = []
        self.appended = []

    def get_doc_meta(self, doc_id):
        return {"id": doc_id, "content": "Doc", "updated": "20260101010101", "hpath": "/Doc"}

    def sql_query(self, _stmt):
        return {
            "code": 0,
            "msg": "",
            "data": [
                {"id": "doc-1", "markdown": "", "type": "d", "subtype": "", "parent_id": "", "sort": "0"},
                {"id": "b1", "markdown": "Para", "type": "p", "subtype": "", "parent_id": "doc-1", "sort": "1"},
                {"id": "b2", "markdown": "- [ ] TODO", "type": "i", "subtype": "t", "parent_id": "doc-1", "sort": "2"},
                {"id": "b3", "markdown": "> [!TIP]\n> demo", "type": "callout", "subtype": "TIP", "parent_id": "doc-1", "sort": "3"},
            ],
        }

    def _mark_read(self, *_args, **_kwargs):
        return None

    def _guard_doc_write(self, *_args, **_kwargs):
        return None

    def update_block(self, *_args, **_kwargs):
        return {"code": 0, "msg": "", "data": {}}

    def get_block(self, block_id):
        if block_id == "doc-1":
            return {"id": "doc-1", "type": "d"}
        return {}

    def delete_block(self, block_id):
        self.deleted.append(block_id)
        return {"code": 0, "msg": "", "data": {}}

    def append_block(self, parent_id, markdown):
        self.appended.append((parent_id, markdown))
        return {"code": 0, "msg": "", "data": {}}

    def create_doc(self, notebook_id, path, markdown):
        return {"code": 0, "msg": "", "data": "doc-created-1"}


class DocumentModuleTests(unittest.TestCase):
    def test_open_doc_typed(self):
        docs = DocumentModule(FakeClient())
        out = docs.open_doc("doc-1", view="typed")
        content = out["content"]
        self.assertIn("## Type Counts", content)
        self.assertIn("- p: 1", content)
        self.assertIn("- callout: 1", content)

    def test_write_full_replace_existing_doc(self):
        client = FakeClient()
        docs = DocumentModule(client)
        out = docs.write_full("doc-1", "new content", mode="replace")
        self.assertEqual(out["code"], 0)
        self.assertEqual(out["data"]["mode"], "replace")
        self.assertEqual(len(client.deleted), 3)
        self.assertEqual(client.appended[0][0], "doc-1")

    def test_write_full_create_new_doc(self):
        client = FakeClient()
        client.settings.main_notebook_id = "nb-1"
        docs = DocumentModule(client)
        out = docs.write_full("/demo/new-doc", "hello", mode="replace")
        self.assertEqual(out["code"], 0)
        self.assertEqual(out["data"]["mode"], "create")

    def test_import_content_md(self):
        docs = DocumentModule(FakeClient())
        out = docs.import_content("hello markdown", "md", "nb-1", "/demo/import")
        self.assertEqual(out["code"], 0)
        self.assertEqual(out["data"]["source_type"], "md")

    def test_open_doc_typed_semantic(self):
        class SemanticClient(FakeClient):
            def sql_query(self, _stmt):
                return {
                    "code": 0,
                    "msg": "",
                    "data": [
                        {"id": "doc-1", "markdown": "", "type": "d", "subtype": "", "parent_id": "", "sort": "0"},
                        {"id": "h1", "markdown": "# Title", "type": "h", "subtype": "h1", "parent_id": "doc-1", "sort": "1"},
                        {"id": "l1", "markdown": "- item 1", "type": "l", "subtype": "u", "parent_id": "doc-1", "sort": "2"},
                        {"id": "i1", "markdown": "- item 1", "type": "i", "subtype": "u", "parent_id": "l1", "sort": "3"},
                        {"id": "p1", "markdown": "item 1", "type": "p", "subtype": "", "parent_id": "i1", "sort": "4"},
                        {"id": "p2", "markdown": "", "type": "p", "subtype": "", "parent_id": "doc-1", "sort": "5"},
                        {"id": "p3", "markdown": "normal paragraph", "type": "p", "subtype": "", "parent_id": "doc-1", "sort": "6"},
                    ],
                }

        docs = DocumentModule(SemanticClient())
        out = docs.open_doc("doc-1", view="typed", semantic=True)
        self.assertTrue(out["semantic"])
        self.assertEqual(out["typed"]["semantic"], True)
        self.assertNotIn("l", out["typed"]["type_counts"])
        self.assertEqual(out["typed"]["type_counts"].get("p"), 1)
        self.assertIn("semantic: true", out["content"])


if __name__ == "__main__":
    unittest.main()
