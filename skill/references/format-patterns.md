# SiYuan Format Patterns (Practical)

Collected from official guide notebook (`思源笔记用户指南`) and SQL sampling.

## High-value patterns

### Block reference
```md
((20201224120447-veyqmvr "alias"))
```

### Tag
```md
#内容块/类型#
```

### Wiki link
```md
[[文档标题]]
```

### Query embed
```md
{{SELECT * FROM blocks WHERE content LIKE '%foo%' LIMIT 20}}
```

### Callout
```md
> [!TIP]
> text
```

### Super block
```md
{{{col
{{{row
content
}}}
}}}
```

### AttributeView
```html
<div data-type="NodeAttributeView" data-av-id="20240208155918-uylgwbj" data-av-type="table"></div>
```

## SQL notes for agent use
- Prefer `type/subtype` filters for targeted reads.
- For embed SQL, always add scope (`box` or `root_id`) and `LIMIT`.
- For large docs, start with `open-doc <doc_id> typed` before patch workflows.
