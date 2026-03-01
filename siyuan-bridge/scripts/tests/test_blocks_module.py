import unittest

from scripts.modules.blocks import BlockModule


class FakeClient:
    def __init__(self):
        self.updated = None
        self.appended = None
        self.read_mark = None

    def get_block(self, block_id):
        if block_id == "doc-1":
            return {"id": "doc-1", "type": "d", "box": "main", "markdown": ""}
        if block_id == "table-1":
            return {
                "id": "table-1",
                "type": "t",
                "root_id": "doc-1",
                "markdown": "| A | B |\n| --- | --- |\n| 1 | 2 |",
            }
        if block_id == "blk-1":
            return {
                "id": "blk-1",
                "type": "p",
                "root_id": "doc-1",
                "markdown": "Ref ((20240101120000-abcdefg)) #tag#",
            }
        return {}

    def resolve_root_doc_id(self, _):
        return "doc-1"

    def get_doc_meta(self, _):
        return {"id": "doc-1", "box": "main"}

    def append_block(self, parent_id, markdown):
        self.appended = {"parent_id": parent_id, "markdown": markdown}
        return {"code": 0, "msg": "", "data": {"id": "new-block"}}

    def update_block(self, block_id, content, data_type="markdown"):
        self.updated = {"block_id": block_id, "content": content, "data_type": data_type}
        return {"code": 0, "msg": "", "data": {"id": block_id}}

    def sql_query(self, _sql):
        return {"code": 0, "msg": "", "data": [{"markdown": "((20240101120000-abcdefg))"}]}

    def _mark_read(self, doc_id, source="unknown"):
        self.read_mark = {"doc_id": doc_id, "source": source}

    def get_block_kramdown(self, _):
        return {"code": 0, "msg": "", "data": {"kramdown": "demo"}}

    def get_block_dom(self, _):
        return {"code": 0, "msg": "", "data": {"dom": "<p>demo</p>"}}


class BlockModuleTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.blocks = BlockModule(self.client)

    def test_create_safe_embed(self):
        res = self.blocks.create_safe_embed("blk-1", "SELECT id FROM blocks", scope="box", limit=10)
        self.assertEqual(res["code"], 0)
        self.assertIn("box = 'main'", res["data"]["sql"])
        self.assertIn("LIMIT 10", res["data"]["sql"])

    def test_append_table_row(self):
        res = self.blocks.append_table_row("table-1", cells=["x", "y"])
        self.assertEqual(res["code"], 0)
        self.assertIn("| x | y |", self.client.updated["content"])

    def test_extract_refs(self):
        res = self.blocks.extract_refs("blk-1")
        self.assertEqual(res["code"], 0)
        self.assertEqual(res["data"]["counts"]["block_refs"], 1)


if __name__ == "__main__":
    unittest.main()
