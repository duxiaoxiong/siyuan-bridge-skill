import unittest

from scripts.formats.pmf import PMFFormat


class PMFTests(unittest.TestCase):
    def test_render_and_parse(self):
        pmf = PMFFormat()
        content = pmf.to_pmf(
            blocks=[
                {"id": "20260227-aaa", "markdown": "# 标题"},
                {"id": "20260227-bbb", "markdown": "段落"},
            ],
            doc_id="20260227-doc",
            partial=False,
            cursor=None,
            updated="20260227120000",
        )
        parsed = pmf.from_pmf(content)
        self.assertEqual(parsed["doc_id"], "20260227-doc")
        self.assertFalse(parsed["partial"])
        self.assertEqual(len(parsed["blocks"]), 2)


if __name__ == "__main__":
    unittest.main()
