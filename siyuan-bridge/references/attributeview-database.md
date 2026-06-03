# AttributeView Database

Use this reference for SiYuan AttributeView database discovery, schema inspection, row/column writes, templates, and validation.

For deeper payload/type details, also read `references/attributeview-api.md`.

## Safe Protocol

Always prefer this sequence:

1. Inspect schema:
   ```bash
   python3 scripts/siyuan.py av schema <av_id_or_av_block_id>
   ```
2. Add rows with named fields:
   ```bash
   python3 scripts/siyuan.py av add-row-with-data <av_id_or_av_block_id> --strict '{"__title":"Demo","Status":"Todo"}'
   ```
3. Update cells by column name:
   ```bash
   python3 scripts/siyuan.py av set-cell-by-name <av_id_or_av_block_id> <row_id> <column_name> <value>
   ```
4. Validate when behavior is uncertain:
   ```bash
   python3 scripts/siyuan.py av validate <av_id_or_av_block_id>
   ```

## Existing Commands

```bash
python3 scripts/siyuan.py av types
python3 scripts/siyuan.py av render <av_id_or_av_block_id>
python3 scripts/siyuan.py av schema <av_id_or_av_block_id>
python3 scripts/siyuan.py av search <keyword> [--av <av_id>]
python3 scripts/siyuan.py av columns <av_id>
python3 scripts/siyuan.py av block-to-item <av_id> <block_ids_csv>
python3 scripts/siyuan.py av item-to-block <av_id> <item_ids_csv>
python3 scripts/siyuan.py av block-databases <block_id>
python3 scripts/siyuan.py av add-col <av_id_or_av_block_id> <name> <type>
python3 scripts/siyuan.py av add-row <av_id_or_av_block_id>
python3 scripts/siyuan.py av add-row-from-block <av_id_or_av_block_id> <block_id>
python3 scripts/siyuan.py av set-cell <av_id_or_av_block_id> <key_id> <row_id> <type> <value>
python3 scripts/siyuan.py av remove-rows <av_id_or_av_block_id> <row1,row2>
python3 scripts/siyuan.py av duplicate <av_id_or_av_block_id>
```

Templates and seed rows:

```bash
python3 scripts/siyuan.py av create-template <notebook_id> <path> '[{"name":"Status","type":"select"}]'
python3 scripts/siyuan.py av create-inline-template <parent_id_or_doc_id> '[{"name":"Status","type":"select"}]' --rows '[{"__title":"Task A","Status":"Todo"}]' --strict
python3 scripts/siyuan.py av seed <av_id_or_av_block_id> --rows '[{"__title":"Task B","Status":"Doing"}]' --strict
```

## Safety Details

- AV IDs are normalized from AV block IDs when possible.
- New databases may initialize asynchronously; render and retry when needed.
- Business columns are inserted after the primary `block` column by default.
- `--strict` rejects unknown column names.
- Date writes use Unix epoch milliseconds.
- Select and mSelect options can use explicit colors.

## Discovery Helpers

Use `av search` to locate databases by keyword, `av columns` to inspect key IDs, and the item/block conversion commands when updating bound rows.
