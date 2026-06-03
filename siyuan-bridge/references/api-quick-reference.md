# SiYuan API Quick Reference

## Authentication

All requests require the `Authorization` header with **`Token ` prefix**:

```
Authorization: Token <your_api_token>
Content-Type: application/json
```

Config: `scripts/config.local.json` -> `token_file` (default `~/.config/siyuan/api_token`).

## Core Endpoints

### System
- `POST /api/system/version` `{}` -- Returns version string
- `POST /api/notebook/lsNotebooks` `{}` -- List all notebooks

### File Tree / Documents
- `POST /api/filetree/listDocsByPath` `{"notebook":"<nb>","path":"/<path>"}` -- List docs in directory
- `POST /api/filetree/getIDsByHPath` `{"notebook":"<nb>","hPath":"/<hpath>"}` -- Get doc IDs by human path
- `POST /api/filetree/moveDocsByID` `{"fromIDs":["<id1>",...],"toID":"<parent_id>"}` -- Move docs under parent. Batch-safe.
- `POST /api/filetree/renameDoc` `{"notebook":"<nb>","path":"/<path>","title":"<new>"}` -- Rename doc
- `POST /api/filetree/createDocWithMd` `{"notebook":"<nb>","path":"/<path>","markdown":"..."}` -- Create from markdown

### Block Operations
- `POST /api/block/getBlockByID` `{"id":"<block_id>"}` -- Get single block
- `POST /api/block/getBlockKramdown` `{"id":"<block_id>"}` -- Get block with kramdown
- `POST /api/block/insertBlock` `{"dataType":"markdown","data":"...","nextID":"","parentID":"<parent>"}` -- Insert block
- `POST /api/block/updateBlock` `{"id":"<block_id>","dataType":"markdown","data":"..."}` -- Update block
- `POST /api/block/deleteBlock` `{"id":"<block_id>"}` -- Delete block
- `POST /api/block/moveBlock` `{"id":"<block_id>","parentID":"<parent>","previousID":"<prev>"}` -- Move block position
- `POST /api/block/getBlockBreadcrumb` `{"id":"<block_id>"}` -- Get ancestry path

### Search and Query
- `POST /api/search/fullTextSearchBlock` `{"query":"<keyword>","page":1}` -- Full-text search
- `POST /api/query/sql` `{"stmt":"SELECT ... LIMIT 500"}` -- SQL query. Default limit ~64 rows; always add LIMIT.

### Document Content
- `POST /api/block/getDoc` `{"id":"<doc_id>","size":102400}` -- Get full doc (kramdown)
- `POST /api/export/exportMdContent` `{"id":"<doc_id>"}` -- Export as markdown

## Python Usage Pattern

```python
import requests

API_URL = "http://<host>:<port>"
TOKEN = open(token_file).read().strip()

def api(endpoint, data):
    r = requests.post(
        f"{API_URL}{endpoint}", json=data,
        headers={"Authorization": f"Token {TOKEN}", "Content-Type": "application/json"},
        timeout=15
    )
    return r.json()

# Batch move docs
result = api("/api/filetree/moveDocsByID", {
    "fromIDs": ["doc_id_1", "doc_id_2"],
    "toID": "parent_doc_id"
})
```

## Pitfalls

- **Auth format**: Must be `Token <token>`, not bare `<token>`.
- **SQL limit**: Default returns ~64 rows. Always add `LIMIT 500` (or higher) for SELECT.
- **Empty response**: Some endpoints return HTTP 200 with empty body on success. Check status code.
- **moveDocsByID vs moveDoc**: Use `moveDocsByID` (plural). Singular `moveDoc` has different path-based params.
