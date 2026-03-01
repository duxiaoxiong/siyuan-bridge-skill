# AttributeView API

## Data model and persistence
1. A document keeps an AV block (`type='av'`) in `blocks`.
2. The AV block markdown stores the real database id:
`<div data-type="NodeAttributeView" data-av-id="...">`.
3. Real AV data is persisted in:
`data/storage/av/<av_id>.json`.
4. Row block ids for detached rows may not appear in `blocks` table.

## ID rules
- `av_block_id` is not `av_id`.
- Always resolve `av_id` from AV block kramdown.
- Commands in this skill now accept both:
  - real `av_id`
  - AV block id (auto-converted internally)
- Agent-safe commands:
  - `av schema` to resolve columns and writable flags
  - `av set-cell-by-name` to avoid manual `key_id` lookup
  - `av add-row-with-data --strict` to fail fast on unknown columns
  - `av help <subcommand>` (or `av <subcommand> --help`) for exact parameter forms

## Create database flow
1. Create a doc with:
`<div data-type="NodeAttributeView" data-av-type="table"></div>`.
2. Query AV block in the new doc (`type='av'`).
3. Resolve `av_id` from kramdown (`data-av-id`).
4. Wait until AV view is ready (`renderAttributeView` succeeds with `view.id`).
5. Detect primary `block` column and add business columns after it.
6. Add rows and set cells.

Inline template flow (`create-inline-template`):
1. Accept `parent_id_or_doc_id`.
2. Insert AV block into existing page (for `doc_id`, insert after last top-level block).
3. Resolve new AV block by before/after diff in the same doc.
4. Configure columns, optionally remove default single-select column.
5. Optionally seed rows in strict mode.

## Important race condition
- Symptom: `addAttributeViewKey` returns `view not found`.
- Cause: AV view init is async; `storage/av/<av_id>.json` may not exist yet.
- Fix: retry render until ready before first write.

## Core APIs and payloads

### Render
`POST /api/av/renderAttributeView`
```json
{"id":"<av_id>","page":1,"pageSize":-1}
```

### Add column
`POST /api/av/addAttributeViewKey`
```json
{
  "avID":"<av_id>",
  "keyID":"<custom-col-id>",
  "keyName":"Task",
  "keyType":"text",
  "keyIcon":"",
  "previousKeyID":""
}
```

Behavior in this skill:
- If `previousKeyID` is omitted, default to the primary `block` column id (keeps primary first).
- For `select/mSelect`, `add-col --options` triggers an option-prime write so option names/colors persist in schema.

`select/mSelect` columns can include preset options:
```json
{
  "options":[{"name":"Todo","color":"2","desc":""},{"name":"Doing","color":"7","desc":""}]
}
```

### Add row
`POST /api/av/addAttributeViewBlocks`
```json
{
  "avID":"<av_id>",
  "srcs":[{"id":"<temp-row-id>","isDetached":true}]
}
```

Linked primary row (first column clickable to an existing block/page):
```json
{
  "avID":"<av_id>",
  "srcs":[{"id":"<existing-block-id>","isDetached":false}]
}
```

### Set cell
`POST /api/av/setAttributeViewBlockAttr`
```json
{
  "avID":"<av_id>",
  "keyID":"<col-id>",
  "itemID":"<real-row-id>",
  "value":{"type":"text","text":{"content":"hello"}}
}
```

### Batch set
`POST /api/av/batchSetAttributeViewBlockAttrs`
```json
{
  "avID":"<av_id>",
  "values":[{"keyID":"<col-id>","itemID":"<row-id>","value":{...}}]
}
```

## Supported key types
- Editable/common: `text`, `number`, `date`, `select`, `mSelect`, `checkbox`, `url`, `email`, `phone`, `relation`, `mAsset`, `template`, `block`
- System/read-only in value writes: `created`, `updated`, `rollup`

## Value payload examples

### text
```json
{"type":"text","text":{"content":"hello"}}
```

### number
```json
{"type":"number","number":{"content":12.5,"isNotEmpty":true}}
```

### date
```json
{"type":"date","date":{"content":1772150400000,"isNotEmpty":true,"hasEndDate":false,"isNotTime":true}}
```

Date encoding in this skill:
- Write `date.content` as Unix epoch milliseconds.
- Date-only inputs (`YYYY-MM-DD`, `YYYYMMDD`, `date`) set `isNotTime=true`.
- Date-time inputs (`YYYY-MM-DD HH:MM:SS`, ISO datetime, `datetime`) set `isNotTime=false`.

### select / mSelect
```json
{"type":"select","mSelect":[{"content":"In Progress","color":"1"}]}
```
```json
{"type":"mSelect","mSelect":[{"content":"A","color":"1"},{"content":"B","color":"1"}]}
```

Color policy in this skill:
- keep existing color when option already exists in schema
- support explicit color syntax in write value: `"Todo|3"`
- otherwise assign a random color from built-in pool

### checkbox
```json
{"type":"checkbox","checkbox":{"checked":true}}
```

### relation
```json
{"type":"relation","relation":{"blockIDs":["20260227-aaa","20260227-bbb"]}}
```

### mAsset
```json
{
  "type":"mAsset",
  "mAsset":[{"type":"file","name":"demo.png","content":"assets/demo.png"}]
}
```

## CLI examples
- `python3 scripts/siyuan.py av types`
- `python3 scripts/siyuan.py av help create-db`
- `python3 scripts/siyuan.py av schema <av_id_or_av_block_id>`
- `python3 scripts/siyuan.py av resolve-id <av_block_id>`
- `python3 scripts/siyuan.py av create-db <notebook_id> <path> "Task:text,Due:date"`
- `python3 scripts/siyuan.py av create-template <notebook_id> <path>`
- `python3 scripts/siyuan.py av create-inline-template <parent_id_or_doc_id> '[{"name":"Status","type":"select","options":[{"name":"Todo","color":"2"}]}]' --rows '[{"__title":"Task A","Status":"Todo"}]' --strict`
- `python3 scripts/siyuan.py av create-db <notebook_id> <path> '[{"name":"Status","type":"select","options":[{"name":"Todo","color":"2"}]}]'`
- `python3 scripts/siyuan.py av add-col <av_id_or_av_block_id> Priority select --options '[{"name":"P0","color":"1"},{"name":"P1","color":"3"}]'`
- `python3 scripts/siyuan.py av add-col <av_id_or_av_block_id> Priority select --after <previous_key_id>`
- `python3 scripts/siyuan.py av add-row-with-data <av_id_or_av_block_id> '{"Task":"Demo"}'`
- `python3 scripts/siyuan.py av add-row-with-data <av_id_or_av_block_id> --strict '{"Task":"Demo"}'`
- `python3 scripts/siyuan.py av add-row-with-data <av_id_or_av_block_id> --strict '{"__title":"Task A","Status":"Todo"}'`
- `python3 scripts/siyuan.py av add-row-with-data <av_id_or_av_block_id> --strict --primary-block <block_id> '{"Status":"Doing"}'`
- `python3 scripts/siyuan.py av add-row-from-block <av_id_or_av_block_id> <block_id>`
- `python3 scripts/siyuan.py av seed <av_id_or_av_block_id> --rows '[{"__title":"Task A","Status":"Todo"},{"__title":"Task B","Status":"Doing"}]'`
- `python3 scripts/siyuan.py av validate <av_id_or_av_block_id>`
- `python3 scripts/siyuan.py av validate <av_id_or_av_block_id> --no-cleanup`
- `python3 scripts/siyuan.py av set-cell-by-name <av_id_or_av_block_id> <row_id> Task "Demo"`

## Reserved payload keys for `add-row-with-data`
- `__title`: write primary `block` column text for detached rows.
- `__primary_block_id`: link row primary to existing block/page (`isDetached=false`).
- CLI equivalent: `--primary-block <block_id>` injects `__primary_block_id`.
