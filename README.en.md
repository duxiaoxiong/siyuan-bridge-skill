# Siyuan Bridge Skill

This is a Codex/agent skill for connecting to SiYuan through the SiYuan HTTP API. It provides a Python CLI for searching notes, reading documents, editing content, and working with AttributeView databases.

Primary Chinese document: [README.md](./README.md)

## Location

The actual skill package is:

```text
siyuan-bridge/
```

Main entry points:

```text
siyuan-bridge/SKILL.md
siyuan-bridge/scripts/siyuan.py
```

## Install For Local Codex

Copy the skill folder into Codex skills:

```bash
mkdir -p ~/.codex/skills
cp -R siyuan-bridge ~/.codex/skills/siyuan-bridge
```

For updates, use `rsync` without overwriting local config:

```bash
rsync -a --delete \
  --exclude 'scripts/config.local.json' \
  --exclude 'scripts/.siyuan-read-guard-cache.json' \
  --exclude 'scripts/.siyuan-writes.log' \
  siyuan-bridge/ ~/.codex/skills/siyuan-bridge/
```

## Configuration

Config priority:

1. Environment variables
2. `siyuan-bridge/scripts/config.local.json`
3. `siyuan-bridge/scripts/config.json`

Store the API token outside the repo:

```bash
mkdir -p ~/.config/siyuan
echo "your_siyuan_api_token" > ~/.config/siyuan/api_token
chmod 600 ~/.config/siyuan/api_token
```

Create local config:

```bash
cd siyuan-bridge
cp scripts/config.example.json scripts/config.local.json
```

Example `scripts/config.local.json`:

```json
{
  "api_url": "http://127.0.0.1:6806",
  "token_file": "~/.config/siyuan/api_token",
  "forbidden_notebooks": [],
  "main_notebook_id": "",
  "read_guard_ttl_seconds": 3600,
  "open_doc_char_limit": 15000,
  "write_log_path": ".siyuan-writes.log",
  "read_guard_cache_path": ".siyuan-read-guard-cache.json"
}
```

Temporary endpoint override:

```bash
SIYUAN_API_URL="https://<your-siyuan-domain>" python3 scripts/siyuan.py doctor --json
```

## Check Connection

```bash
cd siyuan-bridge
python3 scripts/siyuan.py doctor --json
python3 scripts/siyuan.py capabilities --json
```

## Common Commands

```bash
python3 scripts/siyuan.py notebooks --json
python3 scripts/siyuan.py docs recent --limit 10 --json
python3 scripts/siyuan.py open-doc <doc_id> typed --semantic --json
python3 scripts/siyuan.py doc tree <notebook_id> / --depth 2 --limit 200 --json
python3 scripts/siyuan.py search <keyword>
python3 scripts/siyuan.py search-type d --limit 10
python3 scripts/siyuan.py block get <block_id> --format markdown
python3 scripts/siyuan.py block attrs <block_id>
python3 scripts/siyuan.py api post /api/system/version '{}'
```

## Writes

Read the target document before editing it:

```bash
python3 scripts/siyuan.py open-doc <doc_id> typed --semantic --json
```

Basic writes:

```bash
python3 scripts/siyuan.py append <parent_id> "new content"
python3 scripts/siyuan.py update <block_id> "new content"
python3 scripts/siyuan.py prepend <parent_id> "new content"
python3 scripts/siyuan.py insert-after <block_id> "new content"
python3 scripts/siyuan.py delete <block_id>
```

Document operations:

```bash
python3 scripts/siyuan.py doc create-child <parent_doc_id> <title> "content"
python3 scripts/siyuan.py doc rename <doc_id> <new_title>
python3 scripts/siyuan.py doc move <from_doc_ids_csv> <to_doc_id>
python3 scripts/siyuan.py doc write-full <doc_id_or_path> --mode replace < markdown.md
```

## AttributeView

```bash
python3 scripts/siyuan.py av schema <av_id_or_av_block_id>
python3 scripts/siyuan.py av add-row-with-data <av_id_or_av_block_id> --strict '{"__title":"Task B","Status":"Todo"}'
python3 scripts/siyuan.py av seed <av_id_or_av_block_id> --rows '[{"__title":"Task C"}]' --strict
python3 scripts/siyuan.py av validate <av_id_or_av_block_id>
```

## Write Guard

The CLI has a read-before-write guard. If an edit is rejected, read the target document first.

Emergency bypass:

```bash
SIYUAN_ALLOW_UNSAFE_WRITE=true python3 scripts/siyuan.py ...
```

Do not leave this enabled by default.

## Local Files

Do not commit these:

```text
siyuan-bridge/scripts/config.local.json
siyuan-bridge/scripts/.siyuan-read-guard-cache.json
siyuan-bridge/scripts/.siyuan-writes.log
```

## Tests

```bash
cd siyuan-bridge
python3 -m unittest discover -s scripts/tests
python3 scripts/siyuan.py doctor --json
```
