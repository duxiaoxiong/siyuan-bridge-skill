import unittest

from scripts.formats.markdown_utils import (
    append_markdown_table_row,
    build_callout_markdown,
    extract_reference_tokens,
    inject_safe_embed_scope,
)


class MarkdownUtilsTests(unittest.TestCase):
    def test_extract_reference_tokens(self):
        text = (
            'See ((20240101120000-abcdefg "Demo")) and [[WikiLink]] #tag/demo# '
            "{{ SELECT * FROM blocks LIMIT 3 }}"
        )
        refs = extract_reference_tokens(text)
        self.assertEqual(refs["counts"]["block_refs"], 1)
        self.assertEqual(refs["block_refs"][0]["id"], "20240101120000-abcdefg")
        self.assertEqual(refs["wiki_links"][0], "WikiLink")
        self.assertEqual(refs["tags"][0], "tag/demo")
        self.assertIn("SELECT * FROM blocks LIMIT 3", refs["query_embeds"][0])

    def test_build_callout_markdown(self):
        md = build_callout_markdown("tip", "hello\nworld")
        self.assertTrue(md.startswith("> [!TIP]"))
        self.assertIn("> hello", md)
        self.assertIn("> world", md)

    def test_inject_safe_embed_scope_and_limit(self):
        sql = inject_safe_embed_scope(
            "SELECT id FROM blocks",
            scope_sql="box = 'main'",
            default_limit=20,
        )
        self.assertIn("WHERE box = 'main'", sql)
        self.assertIn("LIMIT 20", sql)

    def test_append_markdown_table_row(self):
        table = "| A | B |\n| --- | --- |\n| 1 | 2 |"
        updated = append_markdown_table_row(table, ["x", "y"])
        self.assertIn("| x | y |", updated)
        self.assertEqual(len(updated.splitlines()), 4)


if __name__ == "__main__":
    unittest.main()
