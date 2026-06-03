# Document Operations

Use this reference for whole-document import, creation, replacement, and future file-tree operations.

## Existing Commands

Recursive document tree:

```bash
python3 scripts/siyuan.py doc tree <notebook_id> [path] [--sort n] [--depth n] [--limit n] [--json]
```

Defaults are agent-friendly: `--depth 3 --limit 200`. Use `--depth 0 --limit 0` only when a full recursive tree is truly needed.

Create a child document:

```bash
python3 scripts/siyuan.py doc create-child <parent_doc_id> <title> [content|stdin]
```

Rename or move documents by ID:

```bash
python3 scripts/siyuan.py doc rename <doc_id> <title>
python3 scripts/siyuan.py doc move <from_doc_ids_csv> <to_id>
```

Import content from URL, Markdown, or chat text:

```bash
python3 scripts/siyuan.py doc import <source> --type url|md|chat --to <notebook_id> <path>
```

Write or append a full document:

```bash
python3 scripts/siyuan.py doc write-full <doc_id_or_path> --mode replace
python3 scripts/siyuan.py doc write-full <doc_id_or_path> --mode append
```

Create a document with Markdown:

```bash
python3 scripts/siyuan.py create <notebook_id> <path>
```

Use stdin or heredoc for multiline content. The CLI rejects literal `\n` in command arguments by default.

## Safe Edit Flow

1. Read the document:
   ```bash
   python3 scripts/siyuan.py open-doc <doc_id> typed --semantic --json
   ```
2. Choose the smallest safe write operation.
3. For whole-document edits, prefer PMF when feasible:
   ```bash
   python3 scripts/siyuan.py open-doc <doc_id> patchable
   python3 scripts/siyuan.py apply-patch <doc_id> < patch.pmf
   ```
4. Re-read or validate the result.

## Still Intentionally Omitted

Document removal is not exposed as a first-class command yet. Add it only with explicit confirmation semantics.
