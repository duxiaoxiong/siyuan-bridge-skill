# Siyuan Bridge Skill

Siyuan Bridge is a practical skill for operating SiYuan notes through a stable CLI.  
It is designed for real editing tasks: read documents, update blocks, manage AttributeView databases, and apply safe patch workflows.

## Repository Layout

- Human docs are in repo root: `README.md`, `README.zh-CN.md`.
- Actual skill package is in `skill/`.
- The file used by agents is `skill/SKILL.md`.

## What It Can Do

- Read documents in readable/typed/patchable views.
- Import full content from URL, Markdown, or chat text into a document.
- Write full documents (`replace` or `append`) and perform block-level edits.
- Operate AttributeView databases:
  - create database docs
  - create inline databases in existing pages
  - add/remove columns
  - add rows and set cells by column name
  - validate schema, strict writes, and date encoding
- Enforce read-before-write guard by default to reduce accidental conflicts.

## How It Is Implemented (Short Version)

- `skill/scripts/core/`
  - `config.py`: config loading and priority handling
  - `client.py`: unified SiYuan API client and write guard integration
  - `logging_utils.py`: UTF-8 safe write logs
- `skill/scripts/modules/`
  - `documents.py`: document read/write/import
  - `blocks.py`: block-level operations
  - `attributeview.py`: database operations and type conversion
  - `search.py`: query helpers
- `skill/scripts/guards/`
  - `read_guard.py`: read-first policy and conflict checks
- `skill/scripts/formats/`
  - `pmf.py`: PMF parse/render and safe patch subset
- `skill/scripts/cli/siyuan_cli.py`
  - user-facing command routing and compatibility behavior

## API Token Storage

Token is not hardcoded in repository files.

Configuration priority:
1. Environment variables
2. `skill/scripts/config.local.json`
3. `skill/scripts/config.json`

Token sources:
- `SIYUAN_TOKEN` (highest priority)
- `token_file` path (default: `~/.config/siyuan/api_token`)

Recommended setup:

```bash
mkdir -p ~/.config/siyuan
echo "your_siyuan_api_token" > ~/.config/siyuan/api_token
chmod 600 ~/.config/siyuan/api_token
cp skill/scripts/config.example.json skill/scripts/config.local.json
```

## Safety Defaults

- Read-before-write guard is enabled by default.
- Unsafe bypass is explicit only: `SIYUAN_ALLOW_UNSAFE_WRITE=true`.
- AV date values are written as Unix epoch milliseconds.
- CLI rejects literal `\n` by default for write args; use stdin/heredoc or `--decode-escapes`.
