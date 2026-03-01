# Siyuan Bridge Skill

Siyuan Bridge is a SiYuan-oriented skill package for practical note operations through a stable CLI.
It focuses on three things: reliable editing, database operations (AttributeView), and safe write behavior.

Primary Chinese document: [README.md](./README.md)

## Repository Layout

- Human-facing docs are in repo root: `README.md` (primary Chinese), `README.en.md` (supporting English).
- The actual skill package is in `siyuan-bridge/`.
- Agent entry file is `siyuan-bridge/SKILL.md`.

## Main Capabilities

### Document workflows

- Read documents in `readable`, `typed`, and `patchable` views.
- Import full content from URL, Markdown, or chat text.
- Write full documents with `replace`/`append`.
- Support PMF-based patch flow for controlled edits.

### Block workflows

- Update, append, prepend, insert-after, and delete blocks.
- Provide utility block operations such as `check`, callout helpers, and table row append.

### AttributeView (Database) workflows

- Create standalone database docs and inline databases in existing pages.
- Inspect schema and write by column name.
- Add/remove columns and rows.
- Seed rows from JSON and validate database behavior.
- Support common value types: text, number, date, select/mSelect, checkbox, url, email, phone, relation, mAsset.

## Why Database Operations Are Stable

The database part is designed with explicit safeguards and deterministic steps:

- AV ID normalization:
  accept both AV block ID and real AV ID, then normalize internally.
- Async readiness handling:
  wait/retry until AV view is ready before first write.
- Primary column consistency:
  business columns are inserted after primary `block` column by default.
- Strict mapping mode:
  `--strict` rejects unknown column names instead of silently ignoring.
- Real row ID resolution:
  after row insertion, re-render and detect the actual persisted row ID.
- Select option persistence:
  `add-col --options` supports explicit colors and persists options to schema.
- Correct date encoding:
  date values are written as Unix epoch milliseconds to avoid wrong-year rendering.
- Inline target flexibility:
  inline template creation supports both `doc_id` and normal `block_id`.

## Safety and Data Integrity

- Read-before-write guard is enabled by default.
- Conflict checks use read marker + document update state + TTL.
- Unsafe bypass is explicit only: `SIYUAN_ALLOW_UNSAFE_WRITE=true`.
- PMF apply-patch uses a safe subset in current version.
- Write commands reject literal `\n` arguments by default and suggest stdin/heredoc or `--decode-escapes`.

## Implementation Overview

- `siyuan-bridge/scripts/core/`: config loading, API client, logging utilities.
- `siyuan-bridge/scripts/modules/`: domain logic for documents, blocks, search, and AttributeView.
- `siyuan-bridge/scripts/guards/`: read guard and conflict detection.
- `siyuan-bridge/scripts/formats/`: PMF and markdown helpers.
- `siyuan-bridge/scripts/cli/siyuan_cli.py`: user-facing command router and compatibility entry behavior.

## API Token Storage

Token is not hardcoded in repository files.

Configuration priority:
1. Environment variables
2. `siyuan-bridge/scripts/config.local.json`
3. `siyuan-bridge/scripts/config.json`

Token sources:
- `SIYUAN_TOKEN` (highest priority)
- `token_file` (default: `~/.config/siyuan/api_token`)

Recommended setup:

```bash
mkdir -p ~/.config/siyuan
echo "your_siyuan_api_token" > ~/.config/siyuan/api_token
chmod 600 ~/.config/siyuan/api_token
cp siyuan-bridge/scripts/config.example.json siyuan-bridge/scripts/config.local.json
```
