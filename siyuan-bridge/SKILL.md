---
name: siyuan-bridge
description: SiYuan Note bridge for search, read/write, block operations, AttributeView database CRUD, and safe PMF patch editing with read-before-write guard. Use when requests involve SiYuan API access, `!siyuan` style commands, note retrieval, content updates, or database row/column changes.
---

# Siyuan Bridge

Use this skill for SiYuan API operations through:
- direct skill entry:
`python3 scripts/siyuan.py ...`
- safe document edits (read-first, patchable PMF)
- AttributeView database CRUD
- NAS-hosted SiYuan connections through LAN or environment override

## Setup (Required)
Config priority:
`environment variables > scripts/config.local.json > scripts/config.json`

```bash
cp scripts/config.example.json scripts/config.local.json
mkdir -p ~/.config/siyuan
echo "your_siyuan_api_token" > ~/.config/siyuan/api_token
chmod 600 ~/.config/siyuan/api_token
```

Minimum required config keys:
- `api_url`
- `token_file` (default `~/.config/siyuan/api_token`)

For LAN/FRP profile guidance, read `references/setup-and-profiles.md`.

## Default Agent Workflow
1. Health check:
`python3 scripts/siyuan.py doctor --json`
2. Discover targets with low context cost:
`python3 scripts/siyuan.py docs recent --limit 10 --json`
3. Read before writing:
`python3 scripts/siyuan.py open-doc <doc_id> typed --semantic --json`
4. Write using L1 commands first (`doc import`, `doc write-full`, `av create-template`, `av seed`).
5. Validate writes (`av validate`) and retry only if needed.
6. Follow `data.next_actions` from JSON output instead of probing random commands.

## Task Router (Start Here)
- Need quick structure understanding: `open-doc <doc_id> typed`
- Need low-noise structure summary: `open-doc <doc_id> typed --semantic`
- Need machine-readable doc structure: `open-doc <doc_id> typed --json`
- Need full readable content: `open-doc <doc_id> readable`
- Need capability discovery for no-context agents: `capabilities --json`
- Need guided next step after each L1 call: use returned `data.next_actions`
- Need latest docs quickly: `docs recent --limit 10 --json`
- Need recursive document tree: `doc tree <notebook_id> / --depth 2 --limit 200 --json`
- Need create child document: `doc create-child <parent_doc_id> <title>`
- Need rename/move docs: `doc rename <doc_id> <title>`, `doc move <from_doc_ids_csv> <to_id>`
- Need full-document import (url/md/chat): `doc import <source> --type url|md|chat --to <notebook_id> <path>`
- Need full-document write/replace: `doc write-full <doc_id_or_path> [--mode replace|append]`
- Need patch workflow: `open-doc <doc_id> patchable` then `apply-patch`
- Need exact block format/details: `block get <block_id> --format meta|kramdown|dom`
- Need low-token block filtering: `block get <block_id> --format markdown --command 'grep keyword|head 20|length'`
- Need block attributes: `block attrs <block_id>`, `block set-attrs <block_id> <json_attrs>`
- Need type-targeted discovery (callout/table/av/query_embed): `search-type <type> [--subtype ...] [--box ...]`
- Need normal content write: `update|append|prepend|insert-after|delete`
- Need callout write: `callout create|update`
- Need safe query-embed write: `embed create-safe <parent_id> <sql> --scope root|box`
- Need super block scaffold: `super scaffold <parent_id> --layout col|row --count n`
- Need append markdown table row: `table append-row <table_block_id> [json_cells|a,b,c]`
- Need database template and seed: `av create-template`, `av seed`, then `av validate`
- Need inline database in an existing page/doc: `av create-inline-template <parent_id_or_doc_id> [columns_json] [--rows ...]`
- Need database discovery helpers: `av search`, `av columns`, `av block-to-item`, `av item-to-block`, `av block-databases`
- Need database row/column write: `av schema`, then `av add-row-with-data --strict`, then `av set-cell-by-name`
- Need a missing read-only API: `api post /api/... <json>`; write APIs require `--allow-write`
- Need extract links/references/tags/embed SQL from text: `refs extract <block_id_or_doc_id>`
- Need command details beyond this router: load the relevant reference below, not every reference.

## Core Commands
General:
- `doctor`, `capabilities --json`, `version`, `notebooks`, `docs recent`, `search`, `search-type`, `sql`, `export`
- `doc tree <notebook_id> [path] [--sort n] [--depth n] [--limit n] [--json]`
- `doc create-child <parent_doc_id> <title> [--decode-escapes] [content|stdin]`
- `doc rename <doc_id> <title>`
- `doc move <from_doc_ids_csv> <to_id>`
- `doc import <source> --type url|md|chat --to <notebook_id> <path>`
- `doc write-full <doc_id_or_path> [--mode replace|append] [--notebook <id>] [--decode-escapes]`
- `block get <block_id> [--format markdown|kramdown|dom|meta] [--command 'grep x|head n|length']`
- `block attrs <block_id>`
- `block set-attrs <block_id> <json_attrs>`
- `api post /api/path <json_payload> [--allow-write]`
- `refs extract <block_id_or_doc_id>`

Block writes:
- `create <notebook_id> <path> [--decode-escapes] [content]`
- `update <block_id> [--decode-escapes] <content>` (`edit` alias)
- `append <parent_id> [--decode-escapes] <content>` (`insert` alias)
- `prepend <parent_id> [--decode-escapes] <content>`
- `insert-after <block_id> [--decode-escapes] <content>`
- `delete <block_id>`
- `check <block_id>`
- `callout create <parent_id> <TYPE> <text...>`
- `callout update <block_id> <TYPE> <text...>`
- `embed create-safe <parent_id> <sql> [--scope box|root|none] [--limit n]`
- `super scaffold <parent_id> [--layout col|row] [--count n]`
- `table append-row <table_block_id> [json_cells|a,b,c]`

PMF safe editing:
- `open-doc <doc_id> readable|typed|patchable [--full|--cursor ...] [--json] [--semantic]`
- `apply-patch <doc_id> < patch.pmf`

## AttributeView Protocol (Agent-Safe)
Always prefer this sequence:
1. Inspect schema:
`python3 scripts/siyuan.py av schema <av_id_or_av_block_id>`
2. Add row and set values strictly:
`python3 scripts/siyuan.py av add-row-with-data <av_id_or_av_block_id> --strict '{"__title":"Demo","Status":"Todo"}'`
3. Update specific cell by name:
`python3 scripts/siyuan.py av set-cell-by-name <av_id_or_av_block_id> <row_id> <column_name> <value>`
4. For linked primary rows (clickable page/block link), bind an existing block:
`python3 scripts/siyuan.py av add-row-with-data <av_id_or_av_block_id> --strict --primary-block <block_id> '{"Status":"Doing"}'`
5. Run built-in checks when AV behavior is uncertain:
`python3 scripts/siyuan.py av validate <av_id_or_av_block_id>`
6. For page-embedded DB creation in one command (recommended for templates):
`python3 scripts/siyuan.py av create-inline-template <parent_id_or_doc_id> '[{"name":"Status","type":"select","options":[{"name":"Todo","color":"2"}]}]' --rows '[{"__title":"Task A","Status":"Todo"}]' --strict`

Other AV commands:
- `av help [subcommand]`
- `av types`
- `av render <av_id_or_av_block_id>`
- `av search <keyword> [--av <av_id>]`
- `av columns <av_id>`
- `av block-to-item <av_id> <block_ids_csv>`
- `av item-to-block <av_id> <item_ids_csv>`
- `av block-databases <block_id>`
- `av add-col <av_id_or_av_block_id> <name> <type> [--after <previous_key_id>] [--options <json_array>]`
- `av add-row <av_id_or_av_block_id>`
- `av add-row-from-block <av_id_or_av_block_id> <block_id>`
- `av set-cell <av_id_or_av_block_id> <key_id> <row_id> <type> <value>`
- `av validate <av_id_or_av_block_id> [--no-cleanup]`
- `av remove-rows <av_id_or_av_block_id> <row1,row2>`
- `av duplicate <av_id_or_av_block_id>`
- `av create-db <notebook_id> <path> "Task:text,Due:date"`
- `av create-template <notebook_id> <path> [columns_text_or_json]`
- `av create-inline-template <parent_id_or_doc_id> [columns_text_or_json] [--rows <json|@file|->] [--strict|--no-strict] [--keep-default-select]`
- `av seed <av_id_or_av_block_id> --rows <json|@file|-> [--strict|--no-strict]`
- `av create-db <notebook_id> <path> '[{"name":"Status","type":"select","options":[{"name":"Todo","color":"2"},{"name":"Doing","color":"7"}]}]'`
- `av seed-test-db <notebook_id> <path>` (create DB + 5 seed rows across common types)

## Safety and Error Handling
- Read-before-write guard is on by default. It applies to **all write operations**: `update`, `append`, `prepend`, `insert-after`, `delete`, `create`, `doc move`, `doc write-full`, `callout create/update`, `embed create-safe`, `super scaffold`, `table append-row`, and all `av` write commands.
- The guard requires you to `open-doc` the target document **before** any write. For bulk operations this is impractical.
- **Bulk operation workarounds** (in order of preference):
  1. Set `SIYUAN_ALLOW_UNSAFE_WRITE=true` environment variable to disable the guard entirely.
  2. Call the SiYuan HTTP API directly (bypasses the CLI guard). See `references/api-quick-reference.md`.
  3. Pre-read each doc via `open-doc <id> typed` before issuing writes (slow, not recommended for 10+ docs).
- AV date writes use Unix epoch milliseconds (not `YYYYMMDDHHMMSS`) to avoid wrong-year rendering.
- AV initialization is async. If DB is newly created and write fails, run:
`av render <id>` then retry.
- For newly created DBs, business columns are inserted after the primary `block` column so the first column stays clickable.
- `av add-col` now defaults to inserting after the primary `block` column when `--after` is omitted.
- `av create-inline-template` accepts both `doc_id` and normal `block_id` as parent target.
- For `select/mSelect`, option color can be explicit (`"Todo|3"` or JSON `{"name":"Todo","color":"3"}`); if missing, color is random.
- If command-arg content contains literal `\n`, CLI now rejects by default and asks to use heredoc/stdin or `--decode-escapes`.

## References (Load On Demand)
- Connection setup, LAN default, FRP override, token storage:
`references/setup-and-profiles.md`
- Discovery, search, reading views, low-token reading:
`references/discovery-and-reading.md`
- Document import/write workflow and planned doc-tree operations:
`references/document-operations.md`
- Block, callout, table, embed, attributes:
`references/block-operations.md`
- AttributeView workflow, payload formats, type details:
`references/attributeview-database.md`
- Safe generic API passthrough design and current guardrails:
`references/safe-api-passthrough.md`
- Format patterns from official guide:
`references/format-patterns.md`
- Read guard and PMF behavior:
`references/read-guard-pmf.md`
- API endpoints, auth format, payloads, Python patterns:
`references/api-quick-reference.md`
- Troubleshooting connection/write failures:
`references/troubleshooting.md`
- Reconstructing doc hierarchy from block refs (Notion import cleanup):
`references/doc-hierarchy-reconstruction.md`

## Pitfalls (Learned the Hard Way)
- **SQL API row limit**: SiYuan SQL API returns ~64 rows by default. Always add `LIMIT 500`+ for large result sets. COUNT(*) works without limit but SELECT returns truncated.
- **Auth header format**: Must be `Authorization: Token <token>` (with "Token " prefix), not bare token.
- **Doc move via CLI triggers read guard**: `doc move` CLI command requires reading the doc first. Use direct API `/api/filetree/moveDocsByID` with `{"fromIDs": [...], "toID": "..."}` to bypass.
- **`doc tree` after moves**: May fail with "no such file or directory" until SiYuan refreshes its index. Use SQL queries to verify structure instead.
- **`parent_id` field empty for imports**: Document hierarchy is determined by filesystem path, not the `parent_id` column in blocks table.
