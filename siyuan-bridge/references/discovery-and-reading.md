# Discovery And Reading

Use this reference when an agent needs to find notes, inspect content, or minimize context use before writing.

## First Commands

```bash
python3 scripts/siyuan.py doctor --json
python3 scripts/siyuan.py capabilities --json
python3 scripts/siyuan.py docs recent --limit 10 --json
```

Follow `data.next_actions` from JSON responses.

## Search

General content search:

```bash
python3 scripts/siyuan.py search "keyword" --limit 20
```

Type-targeted discovery:

```bash
python3 scripts/siyuan.py search-type av --limit 20
python3 scripts/siyuan.py search-type query_embed --limit 20
python3 scripts/siyuan.py search-type table --limit 20
```

Recent documents:

```bash
python3 scripts/siyuan.py docs recent --limit 10 --json
```

## Reading Views

Use semantic typed JSON first when planning edits:

```bash
python3 scripts/siyuan.py open-doc <doc_id> typed --semantic --json
```

Use readable Markdown when summarizing:

```bash
python3 scripts/siyuan.py open-doc <doc_id> readable
```

Use patchable PMF before controlled modifications:

```bash
python3 scripts/siyuan.py open-doc <doc_id> patchable
```

Get exact block content:

```bash
python3 scripts/siyuan.py block get <block_id> --format markdown
python3 scripts/siyuan.py block get <block_id> --format kramdown
python3 scripts/siyuan.py block get <block_id> --format dom
python3 scripts/siyuan.py block get <block_id> --format meta
```

## Low-Token Reading Pattern

1. `docs recent --json` or `search`.
2. `open-doc typed --semantic --json` for structure.
3. `block get` only for exact target blocks.
4. Avoid full readable exports unless the task needs prose context.
