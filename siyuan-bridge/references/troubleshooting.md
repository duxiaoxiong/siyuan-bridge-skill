# Troubleshooting

Use this reference when connectivity, authentication, or write safety fails.

## Health Check

```bash
python3 scripts/siyuan.py doctor --json
```

Read the `checks` array:

- `api-url`: configuration loaded.
- `token`: token loaded from env/config/token file.
- `api-version`: endpoint reachable.
- `api-notebooks`: authenticated notebook access works.
- `unsafe-write`: whether unsafe write bypass is enabled.

## Common Failures

Connection refused:

- Wrong endpoint.
- SiYuan container is stopped.
- Port is not exposed.
- Using localhost from the wrong machine.

Version passes but notebooks fail:

- Endpoint is reachable, but token is wrong or missing.
- Rewrite `~/.config/siyuan/api_token` and retry.

FRP works slowly:

- Prefer LAN endpoint when local.
- Use `SIYUAN_API_URL='https://<your-siyuan-domain>'` only when remote access is needed.

Write rejected by read guard:

- Read the containing document first:
  ```bash
  python3 scripts/siyuan.py open-doc <doc_id> typed --semantic --json
  ```
- For single writes, reading first is fine.
- For **bulk operations** (moving/rewriting 10+ docs), the read guard is impractical. Options:
  1. Bypass with env var: `SIYUAN_ALLOW_UNSAFE_WRITE=true python3 scripts/siyuan.py ...`
  2. Call the SiYuan HTTP API directly (see `references/api-quick-reference.md`).
- Do not bypass unless explicitly requested by the user.

SQL returns fewer rows than expected:

- SiYuan SQL API has a default limit of ~64 rows for SELECT queries.
- Always add `LIMIT 500` (or higher) to your SQL: `SELECT ... FROM blocks WHERE ... LIMIT 500`
- `SELECT COUNT(*)` works without limit.
- This does NOT affect `doc tree` or other non-SQL APIs.

`doc tree` fails with "no such file or directory" after batch moves:

- SiYuan's filesystem index may lag behind the database after bulk operations.
- Use SQL queries to verify structure instead:
  ```sql
  SELECT id, content, path FROM blocks WHERE root_id = id AND path LIKE '%<section>%' LIMIT 500
  ```
- The index typically refreshes within seconds. If it persists, restart SiYuan.

Literal `\n` rejected:

- Use stdin/heredoc for multiline content, or pass `--decode-escapes` only when intentional.

New AttributeView write fails:

- Run `av render <id>` and retry after initialization.
- Prefer `av validate <id>` after setup.
