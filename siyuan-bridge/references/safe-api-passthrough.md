# Safe API Passthrough

Use this reference when a needed SiYuan API endpoint is not yet wrapped by the bridge.

## Command

The bridge exposes a generic API passthrough similar to Copilot's `siyuan_fetch_sync_post`, but safer for an external agent.

```bash
python3 scripts/siyuan.py api post /api/system/version '{}'
python3 scripts/siyuan.py api post /api/attr/getBlockAttrs '{"id":"..."}'
python3 scripts/siyuan.py api post /api/block/updateBlock '{"id":"...","dataType":"markdown","data":"..."}' --allow-write
```

Behavior:

- Default allowlist for read-only endpoints.
- Write endpoints require an explicit `--allow-write` flag.
- Write endpoints must integrate with read-before-write guard when they target a document/block/AttributeView.
- Every write logs action and payload shape.
- Dangerous notebook/file removal endpoints require explicit confirmation text or stay omitted.

## Candidate Read-Only Endpoints

- `/api/system/version`
- `/api/notebook/lsNotebooks`
- `/api/query/sql`
- `/api/block/getBlockKramdown`
- `/api/block/getBlockDOM`
- `/api/block/getChildBlocks`
- `/api/attr/getBlockAttrs`
- `/api/filetree/listDocsByPath`
- `/api/filetree/getHPathByID`
- `/api/filetree/getIDsByHPath`
- `/api/av/renderAttributeView`
- `/api/av/getAttributeView`
- `/api/av/getAttributeViewKeysByAvID`
- `/api/av/searchAttributeView`

## Endpoints To Treat As Writes

- `/api/block/insertBlock`
- `/api/block/updateBlock`
- `/api/block/deleteBlock`
- `/api/block/moveBlock`
- `/api/attr/setBlockAttrs`
- `/api/filetree/createDocWithMd`
- `/api/filetree/renameDocByID`
- `/api/filetree/moveDocsByID`
- `/api/av/addAttributeViewBlocks`
- `/api/av/addAttributeViewKey`
- `/api/av/removeAttributeViewBlocks`
- `/api/av/removeAttributeViewKey`
- `/api/av/setAttributeViewBlockAttr`
- `/api/av/batchSetAttributeViewBlockAttrs`
