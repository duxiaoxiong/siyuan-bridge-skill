# Doc Hierarchy Reconstruction from Block References

Use this when Notion or other imports flatten a hierarchical document structure into a flat list.

## Problem

Notion exports preserve `((block_id 'text'))` block references between pages, but the imported documents are placed flat under a single parent. The original page nesting is lost.

## Approach

### 1. Find parent-child relationships from refs table

```sql
SELECT 
  parent_doc.id as parent_id,
  child_doc.id as child_id,
  COUNT(*) as ref_count
FROM refs r
JOIN blocks src ON r.block_id = src.id
JOIN blocks parent_doc ON src.root_id = parent_doc.id
JOIN blocks tgt ON r.def_block_id = tgt.id
JOIN blocks child_doc ON tgt.root_id = child_doc.id
WHERE parent_doc.path LIKE '%<SECTION_ID>%'
  AND child_doc.path LIKE '%<SECTION_ID>%'
  AND parent_doc.root_id = parent_doc.id
  AND child_doc.root_id = child_doc.id
  AND parent_doc.id != child_doc.id
GROUP BY parent_doc.id, child_doc.id
```

**Important**: Match by `root_id` (document level), not by `def_block_id` directly. References point to specific blocks within documents, not to document root blocks.

### 2. Pick best parent for each child

When a child is referenced by multiple parents, choose the parent with the most references to that child, or the parent with the most total children.

### 3. Detect and handle cycles

```python
def has_cycle(mapping):
    visited, rec_stack = set(), set()
    def dfs(node):
        visited.add(node)
        rec_stack.add(node)
        parent = mapping.get(node)
        if parent:
            if parent not in visited:
                if dfs(parent): return True
            elif parent in rec_stack:
                return True
        rec_stack.discard(node)
        return False
    return any(dfs(n) for n in mapping if n not in visited)
```

### 4. Build topological execution order

Move deepest-level children first so intermediate parents remain at root level when their children are moved.

```python
def get_level(doc_id, mapping, cache={}):
    if doc_id in cache: return cache[doc_id]
    if doc_id not in mapping: cache[doc_id] = 0; return 0
    cache[doc_id] = 1 + get_level(mapping[doc_id], mapping, cache)
    return cache[doc_id]

moves = sorted(levels.items(), key=lambda x: -x[1])
```

### 5. Execute moves via API

Use `/api/filetree/moveDocsByID` directly (bypasses read guard):

```python
result = api("/api/filetree/moveDocsByID", {
    "fromIDs": child_id_list,
    "toID": parent_id
})
```

### 6. Verify

After moves, use SQL to verify (not `doc tree`, which may need index refresh):

```sql
SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN path LIKE '%SECTION_ID/%/%' THEN 1 ELSE 0 END) as nested,
  SUM(CASE WHEN path NOT LIKE '%SECTION_ID/%/%' THEN 1 ELSE 0 END) as flat
FROM blocks 
WHERE root_id = id AND path LIKE '%SECTION_ID%' AND id != 'SECTION_ID'
```

## Notes

- The `parent_id` column in blocks table is empty for imported docs. Hierarchy is by filesystem path.
- `doc tree` may fail with "no such file or directory" after batch moves until SiYuan refreshes its index.
- Block references survive doc moves -- `((block_id 'text'))` links remain valid regardless of location.
