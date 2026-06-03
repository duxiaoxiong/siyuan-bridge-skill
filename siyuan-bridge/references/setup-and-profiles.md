# Setup And Profiles

Use this reference when configuring or switching SiYuan endpoints.

## Config Priority

The CLI loads configuration in this order:

1. Environment variables
2. `scripts/config.local.json`
3. `scripts/config.json`

Use `config.local.json` for the default endpoint and keep tokens outside the repo.

## Local Default

For a local/private setup, keep the default endpoint in `config.local.json`:

```json
{
  "api_url": "http://<lan-host>:6806",
  "token_file": "~/.config/siyuan/api_token"
}
```

The token should be stored at:

```bash
~/.config/siyuan/api_token
```

Permissions:

```bash
chmod 700 ~/.config/siyuan
chmod 600 ~/.config/siyuan/api_token
```

## LAN vs FRP

Prefer LAN for normal work:

```bash
python3 scripts/siyuan.py doctor --json
python3 scripts/siyuan.py docs recent --limit 10 --json
```

Use the FRP domain only when outside the LAN or when explicitly testing public access:

```bash
SIYUAN_API_URL='https://<your-siyuan-domain>' python3 scripts/siyuan.py doctor --json
SIYUAN_API_URL='https://<your-siyuan-domain>' python3 scripts/siyuan.py docs recent --limit 10 --json
```

## Safety Notes

- Do not commit tokens.
- Prefer HTTPS for public access.
- Treat the FRP endpoint as exposed internet surface even when token-protected.
- If both endpoints work, choose LAN unless the user asks for remote/public verification.
