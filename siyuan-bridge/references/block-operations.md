# Block Operations

Use this reference for block reads/writes, callouts, tables, embeds, and block attributes.

## Reads And Attributes

Read content:

```bash
python3 scripts/siyuan.py block get <block_id> --format markdown
python3 scripts/siyuan.py block get <block_id> --format kramdown
python3 scripts/siyuan.py block get <block_id> --format dom
python3 scripts/siyuan.py block get <block_id> --format meta
```

Low-token read filters:

```bash
python3 scripts/siyuan.py block get <block_id> --format markdown --command "length"
python3 scripts/siyuan.py block get <block_id> --format markdown --command "grep keyword"
python3 scripts/siyuan.py block get <block_id> --format markdown --command "head 20"
python3 scripts/siyuan.py block get <block_id> --format markdown --command "grep keyword | head 10"
```

Block attributes:

```bash
python3 scripts/siyuan.py block attrs <block_id>
python3 scripts/siyuan.py block set-attrs <block_id> '{"custom-status":"done"}'
```

## Existing Writes

Append as last child:

```bash
python3 scripts/siyuan.py append <parent_id> <markdown>
```

Prepend as first child:

```bash
python3 scripts/siyuan.py prepend <parent_id> <markdown>
```

Insert after a block:

```bash
python3 scripts/siyuan.py insert-after <block_id> <markdown>
```

Update a block:

```bash
python3 scripts/siyuan.py update <block_id> <markdown>
```

Delete a block:

```bash
python3 scripts/siyuan.py delete <block_id>
```

Read-before-write guard is enabled by default. Read the containing document before writing.

## Structured Helpers

Callouts:

```bash
python3 scripts/siyuan.py callout create <parent_id> NOTE "Text"
python3 scripts/siyuan.py callout update <block_id> WARNING "Text"
```

Safe query embeds:

```bash
python3 scripts/siyuan.py embed create-safe <parent_id> "SELECT * FROM blocks LIMIT 20" --scope box
```

Super block scaffold:

```bash
python3 scripts/siyuan.py super scaffold <parent_id> --layout col --count 2
```

Table row append:

```bash
python3 scripts/siyuan.py table append-row <table_block_id> '["A","B","C"]'
```

Reference extraction:

```bash
python3 scripts/siyuan.py refs extract <block_id_or_doc_id>
```

Attribute writes are guarded like other block writes; read the containing document first when setting attrs.
