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
- Do not bypass unless explicitly requested by the user:
  ```bash
  SIYUAN_ALLOW_UNSAFE_WRITE=true python3 scripts/siyuan.py ...
  ```

Literal `\n` rejected:

- Use stdin/heredoc for multiline content, or pass `--decode-escapes` only when intentional.

New AttributeView write fails:

- Run `av render <id>` and retry after initialization.
- Prefer `av validate <id>` after setup.
