"""Main Siyuan CLI entrypoint."""

import json
import os
import sys
from typing import Any, Dict, List, Optional

from ..core.client import DEFAULT_CLIENT
from ..core.errors import SiyuanBridgeError, ValidationError
from ..modules.attributeview import AttributeViewClient
from ..modules.blocks import BlockModule
from ..modules.documents import DocumentModule
from ..modules.search import SearchModule


def _print_json(data: Dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _with_next_actions(payload: Dict[str, Any], next_actions: List[str]) -> Dict[str, Any]:
    out = dict(payload or {})
    data = out.get("data")
    if isinstance(data, dict):
        new_data = dict(data)
    else:
        new_data = {"value": data}
    new_data["next_actions"] = list(next_actions or [])
    out["data"] = new_data
    return out


def _print_usage() -> None:
    print("用法: siyuan.py <命令> [参数...]")
    print(
        "命令: doctor, capabilities, version, notebooks, docs, doc, search, search-type, sql, export, create, "
        "update, append, prepend, insert-after, delete, check, block, refs, callout, embed, super, table, "
        "open-doc, apply-patch, av"
    )


def _collect_content_with_source(args: List[str], start_idx: int) -> Dict[str, Any]:
    if len(args) > start_idx:
        return {"content": " ".join(args[start_idx:]), "from_stdin": False}
    if not sys.stdin.isatty():
        return {"content": sys.stdin.read(), "from_stdin": True}
    raise ValidationError("缺少内容参数，可通过参数或 stdin 提供")


def _decode_escaped_text(text: str) -> str:
    out: List[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt == "n":
                out.append("\n")
                i += 2
                continue
            if nxt == "t":
                out.append("\t")
                i += 2
                continue
            if nxt == "r":
                out.append("\r")
                i += 2
                continue
            if nxt == "\\":
                out.append("\\")
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def _normalize_multiline_content(
    text: str,
    *,
    from_stdin: bool,
    decode_escapes: bool,
    command_name: str,
) -> str:
    if decode_escapes:
        return _decode_escaped_text(text)
    if (not from_stdin) and "\\n" in text and "\n" not in text:
        raise ValidationError(
            f"{command_name} 检测到字面量 \\\\n。请使用 heredoc/stdin 传多行内容，或添加 --decode-escapes。"
        )
    return text


def _parse_write_content(args: List[str], start_idx: int, command_name: str) -> str:
    decode_escapes = False
    idx = start_idx
    if len(args) > idx and args[idx] == "--decode-escapes":
        decode_escapes = True
        idx += 1
    payload = _collect_content_with_source(args, idx)
    return _normalize_multiline_content(
        str(payload.get("content", "")),
        from_stdin=bool(payload.get("from_stdin", False)),
        decode_escapes=decode_escapes,
        command_name=command_name,
    )


def _parse_open_doc_flags(args: List[str]) -> Dict[str, Any]:
    flags: Dict[str, Any] = {
        "full": False,
        "cursor": None,
        "limit_chars": None,
        "limit_blocks": None,
        "json": False,
        "semantic": False,
    }
    i = 0
    while i < len(args):
        item = args[i]
        if item == "--full":
            flags["full"] = True
            i += 1
        elif item == "--json":
            flags["json"] = True
            i += 1
        elif item == "--semantic":
            flags["semantic"] = True
            i += 1
        elif item == "--cursor" and i + 1 < len(args):
            flags["cursor"] = args[i + 1]
            i += 2
        elif item == "--limit-chars" and i + 1 < len(args):
            flags["limit_chars"] = int(args[i + 1])
            i += 2
        elif item == "--limit-blocks" and i + 1 < len(args):
            flags["limit_blocks"] = int(args[i + 1])
            i += 2
        else:
            raise ValidationError(f"未知参数: {item}")
    return flags


def _print_av_help(topic: str = "") -> None:
    t = str(topic or "").strip()
    if not t:
        print("用法: siyuan.py av <subcommand> [参数...]")
        print("子命令:")
        print("  resolve-id <av_block_id>")
        print("  render <av_id_or_av_block_id>")
        print("  schema <av_id_or_av_block_id>")
        print("  types")
        print("  add-col <av_id_or_av_block_id> <name> <type> [--after <previous_key_id>] [--options <json_array>]")
        print("  add-row <av_id_or_av_block_id>")
        print("  add-row-from-block <av_id_or_av_block_id> <block_id>")
        print("  set-cell <av_id_or_av_block_id> <key_id> <row_id> <type> <value>")
        print("  set-cell-by-name <av_id_or_av_block_id> <row_id> <column_name> <value>")
        print("  add-row-with-data <av_id_or_av_block_id> [--strict] [--primary-block <block_id>] <json>")
        print("  validate <av_id_or_av_block_id> [--no-cleanup]")
        print("  remove-rows <av_id_or_av_block_id> <row1,row2>")
        print("  duplicate <av_id_or_av_block_id>")
        print("  create-db <notebook_id> <path> <columns_text_or_json>")
        print("  create-template <notebook_id> <path> [columns_text_or_json]")
        print("  create-inline-template <parent_id_or_doc_id> [columns_text_or_json] [--rows <json|@file|->] [--strict|--no-strict] [--keep-default-select]")
        print("  seed <av_id_or_av_block_id> --rows <json|@file|-> [--strict|--no-strict]")
        print("  seed-test-db <notebook_id> <path>")
        print("")
        print("示例:")
        print("  siyuan.py av help create-db")
        print("  siyuan.py av create-db nb '/demo/db' 'Task:text,Due:date'")
        print("  siyuan.py av create-db nb '/demo/db' '[{\"name\":\"Status\",\"type\":\"select\",\"options\":[{\"name\":\"Todo\",\"color\":\"2\"}]}]'")
        print("  siyuan.py av add-row-with-data <av> --strict '{\"Task\":\"Demo\",\"__title\":\"Title\"}'")
        print("  siyuan.py av add-row-with-data <av> --primary-block 20260227-abcdefg '{\"Status\":\"Doing\"}'")
        print("  siyuan.py av create-inline-template <parent_id> '[{\"name\":\"Status\",\"type\":\"select\",\"options\":[{\"name\":\"Todo\",\"color\":\"2\"}]}]'")
        print("  siyuan.py av validate <av>")
        print("  siyuan.py av seed <av> --rows @seed_rows.json")
        return

    usage_map = {
        "resolve-id": "用法: siyuan.py av resolve-id <av_block_id>",
        "render": "用法: siyuan.py av render <av_id_or_av_block_id>",
        "schema": "用法: siyuan.py av schema <av_id_or_av_block_id>",
        "types": "用法: siyuan.py av types",
        "add-col": "用法: siyuan.py av add-col <av_id_or_av_block_id> <name> <type> [--after <previous_key_id>] [--options <json_array>]",
        "add-row": "用法: siyuan.py av add-row <av_id_or_av_block_id>",
        "add-row-from-block": "用法: siyuan.py av add-row-from-block <av_id_or_av_block_id> <block_id>",
        "set-cell": "用法: siyuan.py av set-cell <av_id_or_av_block_id> <key_id> <row_id> <type> <value>",
        "set-cell-by-name": "用法: siyuan.py av set-cell-by-name <av_id_or_av_block_id> <row_id> <column_name> <value>",
        "add-row-with-data": "用法: siyuan.py av add-row-with-data <av_id_or_av_block_id> [--strict] [--primary-block <block_id>] <json>",
        "validate": "用法: siyuan.py av validate <av_id_or_av_block_id> [--no-cleanup]",
        "remove-rows": "用法: siyuan.py av remove-rows <av_id_or_av_block_id> <row1,row2>",
        "duplicate": "用法: siyuan.py av duplicate <av_id_or_av_block_id>",
        "create-db": "用法: siyuan.py av create-db <notebook_id> <path> <columns_text_or_json>",
        "create-template": "用法: siyuan.py av create-template <notebook_id> <path> [columns_text_or_json]",
        "create-inline-template": "用法: siyuan.py av create-inline-template <parent_id_or_doc_id> [columns_text_or_json] [--rows <json|@file|->] [--strict|--no-strict] [--keep-default-select]",
        "seed": "用法: siyuan.py av seed <av_id_or_av_block_id> --rows <json|@file|-> [--strict|--no-strict]",
        "seed-test-db": "用法: siyuan.py av seed-test-db <notebook_id> <path>",
    }
    if t in usage_map:
        print(usage_map[t])
        return
    print(f"未知 av 子命令: {t}")
    _print_av_help("")


def _parse_search_type_flags(args: List[str]) -> Dict[str, Any]:
    if not args:
        raise ValidationError("用法: search-type <type> [--subtype x] [--box box_id] [--limit n]")
    flags: Dict[str, Any] = {"type": args[0], "subtype": "", "box": "", "limit": 20}
    i = 1
    while i < len(args):
        item = args[i]
        if item == "--subtype" and i + 1 < len(args):
            flags["subtype"] = args[i + 1]
            i += 2
        elif item == "--box" and i + 1 < len(args):
            flags["box"] = args[i + 1]
            i += 2
        elif item == "--limit" and i + 1 < len(args):
            flags["limit"] = int(args[i + 1])
            i += 2
        else:
            raise ValidationError(f"search-type 未知参数: {item}")
    return flags


def _parse_embed_flags(args: List[str]) -> Dict[str, Any]:
    if len(args) < 2:
        raise ValidationError("用法: embed create-safe <parent_id> <sql> [--scope box|root|none] [--limit n]")
    flags: Dict[str, Any] = {"parent_id": args[0], "scope": "box", "limit": 64}
    sql_parts: List[str] = []
    i = 1
    while i < len(args):
        item = args[i]
        if item == "--scope" and i + 1 < len(args):
            flags["scope"] = args[i + 1]
            i += 2
            continue
        if item == "--limit" and i + 1 < len(args):
            flags["limit"] = int(args[i + 1])
            i += 2
            continue
        sql_parts.append(item)
        i += 1
    if not sql_parts:
        raise ValidationError("缺少 SQL 内容")
    flags["sql"] = " ".join(sql_parts)
    return flags


def _parse_super_flags(args: List[str]) -> Dict[str, Any]:
    if not args:
        raise ValidationError("用法: super scaffold <parent_id> [--layout col|row] [--count n]")
    flags: Dict[str, Any] = {"parent_id": args[0], "layout": "col", "count": 2}
    i = 1
    while i < len(args):
        item = args[i]
        if item == "--layout" and i + 1 < len(args):
            flags["layout"] = args[i + 1]
            i += 2
        elif item == "--count" and i + 1 < len(args):
            flags["count"] = int(args[i + 1])
            i += 2
        else:
            raise ValidationError(f"super scaffold 未知参数: {item}")
    return flags


def _cmd_block(blocks: BlockModule, args: List[str]) -> int:
    if len(args) < 2:
        print("用法: siyuan.py block get <block_id> [--format markdown|kramdown|dom|meta]")
        return 1
    sub = args[0]
    if sub != "get":
        print(f"未知 block 子命令: {sub}")
        return 1
    block_id = args[1]
    fmt = "markdown"
    if len(args) >= 4 and args[2] == "--format":
        fmt = args[3]
    elif len(args) == 3 and args[2].startswith("--format="):
        fmt = args[2].split("=", 1)[1]
    elif len(args) > 2:
        raise ValidationError("block get 参数错误")

    res = blocks.get_block_content(block_id, fmt=fmt)
    if res.get("code") != 0:
        _print_json(res)
        return 1
    payload = res.get("data", {})
    if fmt in ("markdown", "kramdown", "dom"):
        print(payload.get("content", ""))
    else:
        _print_json(res)
    return 0


def _cmd_refs(blocks: BlockModule, args: List[str]) -> int:
    if len(args) >= 2 and args[0] == "extract":
        _print_json(blocks.extract_refs(args[1]))
        return 0
    print("用法: siyuan.py refs extract <block_id_or_doc_id>")
    return 1


def _cmd_callout(blocks: BlockModule, args: List[str]) -> int:
    if len(args) < 4:
        print("用法: siyuan.py callout create <parent_id> <TYPE> <text...>")
        print("      siyuan.py callout update <block_id> <TYPE> <text...>")
        return 1
    sub = args[0]
    target = args[1]
    ctype = args[2]
    text = " ".join(args[3:])
    if sub == "create":
        _print_json(blocks.create_callout(target, ctype, text))
        return 0
    if sub == "update":
        _print_json(blocks.update_callout(target, ctype, text))
        return 0
    print(f"未知 callout 子命令: {sub}")
    return 1


def _cmd_embed(blocks: BlockModule, args: List[str]) -> int:
    if not args or args[0] not in ("create-safe",):
        print("用法: siyuan.py embed create-safe <parent_id> <sql> [--scope box|root|none] [--limit n]")
        return 1
    flags = _parse_embed_flags(args[1:])
    _print_json(
        blocks.create_safe_embed(
            parent_id=flags["parent_id"],
            raw_sql=flags["sql"],
            scope=flags["scope"],
            limit=flags["limit"],
        )
    )
    return 0


def _cmd_super(blocks: BlockModule, args: List[str]) -> int:
    if not args or args[0] != "scaffold":
        print("用法: siyuan.py super scaffold <parent_id> [--layout col|row] [--count n]")
        return 1
    flags = _parse_super_flags(args[1:])
    _print_json(
        blocks.create_super_scaffold(
            parent_id=flags["parent_id"],
            layout=flags["layout"],
            count=flags["count"],
        )
    )
    return 0


def _cmd_table(blocks: BlockModule, args: List[str]) -> int:
    if len(args) < 2 or args[0] != "append-row":
        print("用法: siyuan.py table append-row <table_block_id> [json_cells|a,b,c]")
        return 1
    block_id = args[1]
    cells: Optional[List[str]] = None
    if len(args) >= 3:
        raw = " ".join(args[2:]).strip()
        if raw.startswith("["):
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise ValidationError("table append-row JSON 必须是数组")
            cells = [str(x) for x in parsed]
        else:
            cells = [x.strip() for x in raw.split(",")]
    _print_json(blocks.append_table_row(block_id, cells=cells))
    return 0


def _cmd_doctor(client, args: List[str]) -> int:
    json_mode = "--json" in args or not args
    checks: List[Dict[str, Any]] = []

    def _add(name: str, status: str, detail: str, data: Optional[Dict[str, Any]] = None) -> None:
        item: Dict[str, Any] = {"name": name, "status": status, "detail": detail}
        if data:
            item["data"] = data
        checks.append(item)

    settings = client.settings
    token_file = os.path.expanduser(str(settings.token_file or ""))
    _add("api-url", "passed" if bool(settings.api_url) else "failed", "api_url configured")
    _add("token", "passed" if bool(settings.token) else "warning", "token loaded")
    _add(
        "token-file",
        "passed" if (token_file and os.path.exists(token_file)) else "warning",
        "token file path checked",
        {"path": token_file},
    )

    version = client.get_version()
    _add(
        "api-version",
        "passed" if version.get("code") == 0 else "failed",
        "version API check",
        {"response": version},
    )
    notebooks = client.ls_notebooks()
    _add(
        "api-notebooks",
        "passed" if notebooks.get("code") == 0 else "failed",
        "notebooks API check",
        {"count": len(notebooks.get("data", {}).get("notebooks", []) if notebooks.get("code") == 0 else [])},
    )
    _add(
        "unsafe-write",
        "warning" if bool(client.allow_unsafe_write) else "passed",
        "SIYUAN_ALLOW_UNSAFE_WRITE switch",
        {"enabled": bool(client.allow_unsafe_write)},
    )

    ok = all(c["status"] != "failed" for c in checks)
    payload = {"code": 0 if ok else 1, "msg": "" if ok else "doctor checks failed", "data": {"ok": ok, "checks": checks}}
    if ok:
        payload = _with_next_actions(payload, ["python3 scripts/siyuan.py docs recent --limit 10 --json"])
    else:
        payload = _with_next_actions(payload, ["python3 scripts/siyuan.py doctor --json"])
    if json_mode:
        _print_json(payload)
    else:
        for item in checks:
            print(f"[{item['status']}] {item['name']}: {item['detail']}")
    return 0 if ok else 1


def _cmd_capabilities(client, args: List[str]) -> int:
    json_mode = "--json" in args or not args
    payload = {
        "code": 0,
        "msg": "",
        "data": {
            "entrypoint": "python3 scripts/siyuan.py",
            "l1_commands": [
                "doctor",
                "capabilities --json",
                "docs recent --limit 10 --json",
                "open-doc <doc_id> typed --semantic --json",
                "doc import <source> --type url|md|chat --to <notebook_id> <path>",
                "doc write-full <doc_id_or_path> [--mode replace|append] [--notebook <id>]",
                "av create-inline-template <parent_id_or_doc_id> [columns_json] [--rows <json|@file|->]",
                "av create-template <notebook_id> <path> [columns]",
                "av add-row-with-data <av_id_or_av_block_id> --strict <json>",
                "av seed <av_id_or_av_block_id> --rows <json|@file|->",
                "av validate <av_id_or_av_block_id>",
            ],
            "features": {
                "read_guard_default_on": True,
                "unsafe_write_enabled": bool(client.allow_unsafe_write),
                "pmf_apply_patch": True,
                "doc_import_url": True,
                "doc_write_full": True,
                "av_inline_template_create": True,
                "av_template_create": True,
                "av_seed_rows": True,
            },
        },
    }
    payload = _with_next_actions(
        payload,
        [
            "python3 scripts/siyuan.py doctor --json",
            "python3 scripts/siyuan.py docs recent --limit 10 --json",
        ],
    )
    if json_mode:
        _print_json(payload)
        return 0
    for cmd in payload["data"]["l1_commands"]:
        print(cmd)
    return 0


def _cmd_docs(search: SearchModule, args: List[str]) -> int:
    if not args or args[0] != "recent":
        print("用法: siyuan.py docs recent [--limit N] [--box notebook_id] [--json]")
        return 1
    limit = 10
    box = ""
    json_mode = False
    i = 1
    while i < len(args):
        token = args[i]
        if token == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
            continue
        if token == "--box" and i + 1 < len(args):
            box = args[i + 1]
            i += 2
            continue
        if token == "--json":
            json_mode = True
            i += 1
            continue
        raise ValidationError(f"docs recent 未知参数: {token}")
    res = search.search_recent_docs(limit=limit, box=box)
    if res.get("code") != 0:
        _print_json(res)
        return 1
    items = res.get("data", []) or []
    if json_mode:
        next_actions: List[str] = []
        if items:
            first_id = items[0].get("id", "")
            if first_id:
                next_actions.append(f"python3 scripts/siyuan.py open-doc {first_id} typed")
        next_actions.append("python3 scripts/siyuan.py capabilities --json")
        _print_json(_with_next_actions({"code": 0, "msg": "", "data": {"count": len(items), "items": items}}, next_actions))
        return 0
    for row in items:
        print(f"{row.get('updated', '')} | {row.get('content', '')} | {row.get('id', '')} | {row.get('hpath', '')}")
    return 0


def _cmd_doc(documents: DocumentModule, args: List[str]) -> int:
    if not args:
        print("用法: siyuan.py doc import <source> --type url|md|chat --to <notebook_id> <path>")
        print("      siyuan.py doc write-full <doc_id_or_path> [--mode replace|append] [--notebook id] [--decode-escapes] [content|stdin]")
        return 1
    sub = args[0]
    if sub == "import" and len(args) >= 2:
        source = args[1]
        stype = "md"
        notebook_id = ""
        path = ""
        i = 2
        while i < len(args):
            token = args[i]
            if token == "--type" and i + 1 < len(args):
                stype = args[i + 1]
                i += 2
                continue
            if token == "--to" and i + 2 < len(args):
                notebook_id = args[i + 1]
                path = args[i + 2]
                i += 3
                continue
            raise ValidationError(f"doc import 未知参数: {token}")
        if not notebook_id or not path:
            raise ValidationError("doc import 缺少 --to <notebook_id> <path>")
        raw_content = ""
        if source == "-":
            if sys.stdin.isatty():
                raise ValidationError("source 为 '-' 时需要通过 stdin 提供内容")
            raw_content = sys.stdin.read()
        _print_json(
            _with_next_actions(
                documents.import_content(
                    source=source,
                    source_type=stype,
                    notebook_id=notebook_id,
                    path=path,
                    raw_content=raw_content,
                ),
                [
                    "python3 scripts/siyuan.py docs recent --limit 5 --json",
                    "python3 scripts/siyuan.py open-doc <doc_id> typed",
                ],
            )
        )
        return 0
    if sub == "import":
        print("参数不足: doc import")
        print("用法: siyuan.py doc import <source> --type url|md|chat --to <notebook_id> <path>")
        return 1

    if sub == "write-full" and len(args) >= 2:
        target = args[1]
        mode = "replace"
        notebook_id = ""
        decode_escapes = False
        payload_parts: List[str] = []
        i = 2
        while i < len(args):
            token = args[i]
            if token == "--mode" and i + 1 < len(args):
                mode = args[i + 1]
                i += 2
                continue
            if token == "--notebook" and i + 1 < len(args):
                notebook_id = args[i + 1]
                i += 2
                continue
            if token == "--decode-escapes":
                decode_escapes = True
                i += 1
                continue
            payload_parts.append(token)
            i += 1
        if payload_parts:
            raw_markdown = " ".join(payload_parts)
            markdown = _normalize_multiline_content(
                raw_markdown,
                from_stdin=False,
                decode_escapes=decode_escapes,
                command_name="doc write-full",
            )
        elif not sys.stdin.isatty():
            markdown = _normalize_multiline_content(
                sys.stdin.read(),
                from_stdin=True,
                decode_escapes=decode_escapes,
                command_name="doc write-full",
            )
        else:
            raise ValidationError("doc write-full 缺少内容（参数或 stdin）")
        _print_json(
            _with_next_actions(
                documents.write_full(target, markdown, mode=mode, notebook_id=notebook_id),
                [
                    "python3 scripts/siyuan.py docs recent --limit 5 --json",
                    "python3 scripts/siyuan.py open-doc <doc_id> typed",
                ],
            )
        )
        return 0
    if sub == "write-full":
        print("参数不足: doc write-full")
        print("用法: siyuan.py doc write-full <doc_id_or_path> [--mode replace|append] [--notebook id] [--decode-escapes] [content|stdin]")
        return 1

    print(f"未知 doc 子命令: {sub}")
    return 1


def _default_template_columns() -> List[Any]:
    return [
        {"name": "Task", "type": "text"},
        {
            "name": "Status",
            "type": "select",
            "options": [
                {"name": "Todo", "color": "2"},
                {"name": "Doing", "color": "7"},
                {"name": "Done", "color": "4"},
            ],
        },
        {"name": "Tags", "type": "mSelect"},
        {"name": "Due", "type": "date"},
    ]


def _parse_columns_arg(raw: str) -> List[Any]:
    text = str(raw or "").strip()
    if not text:
        return []
    if text.startswith("["):
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            raise ValidationError("列定义 JSON 必须是数组")
        return parsed
    return [x.strip() for x in text.split(",") if x.strip()]


def _load_rows_spec(rows_spec: str) -> List[Dict[str, Any]]:
    if rows_spec == "-":
        if sys.stdin.isatty():
            raise ValidationError("rows 为 '-' 需要 stdin")
        raw_rows = sys.stdin.read()
    elif rows_spec.startswith("@"):
        with open(rows_spec[1:], "r", encoding="utf-8", errors="replace") as f:
            raw_rows = f.read()
    else:
        raw_rows = rows_spec
    rows = json.loads(raw_rows)
    if not isinstance(rows, list):
        raise ValidationError("rows 必须是 JSON 数组")
    for idx, item in enumerate(rows):
        if not isinstance(item, dict):
            raise ValidationError(f"rows[{idx}] 必须是对象")
    return rows


def _cmd_av(av: AttributeViewClient, args: List[str]) -> int:
    if not args:
        _print_av_help("")
        return 1
    if args[0] in ("--help", "-h", "help"):
        _print_av_help(args[1] if len(args) >= 2 else "")
        return 0

    sub = args[0]
    if "--help" in args[1:] or "-h" in args[1:]:
        _print_av_help(sub)
        return 0

    if sub == "resolve-id" and len(args) >= 2:
        print(av.get_av_id_from_block(args[1]))
        return 0
    if sub == "resolve-id":
        print("参数不足: resolve-id")
        _print_av_help("resolve-id")
        return 1

    if sub == "render" and len(args) >= 2:
        _print_json(av.render(args[1]))
        return 0
    if sub == "render":
        print("参数不足: render")
        _print_av_help("render")
        return 1

    if sub == "types":
        _print_json(
            {
                "code": 0,
                "msg": "",
                "data": {
                    "supported_key_types": list(av.SUPPORTED_KEY_TYPES),
                    "read_only_value_types": list(av.READ_ONLY_VALUE_TYPES),
                },
            }
        )
        return 0

    if sub == "schema" and len(args) >= 2:
        schema = av.get_schema(args[1])
        _print_json(
            {
                "code": 0,
                "msg": "",
                "data": {
                    "av_id": schema["av_id"],
                    "view_id": schema["view_id"],
                    "row_count": len(schema["row_ids"]),
                    "columns": schema["columns"],
                },
            }
        )
        return 0
    if sub == "schema":
        print("参数不足: schema")
        _print_av_help("schema")
        return 1

    if sub == "add-col" and len(args) >= 4:
        av_id, key_name, key_type = args[1], args[2], args[3]
        previous = ""
        options = None
        i = 4
        while i < len(args):
            token = args[i]
            if token == "--after" and i + 1 < len(args):
                previous = args[i + 1]
                i += 2
                continue
            if token == "--options" and i + 1 < len(args):
                parsed = json.loads(args[i + 1])
                if not isinstance(parsed, list):
                    raise ValidationError("add-col --options 需要 JSON 数组")
                options = parsed
                i += 2
                continue
            if not previous and not token.startswith("--"):
                previous = token
                i += 1
                continue
            raise ValidationError(f"add-col 未知参数: {token}")
        _print_json(
            av.add_column(
                av_id,
                key_name,
                key_type,
                previous_key_id=previous,
                options=options,
                prime_options=bool(options),
            )
        )
        return 0
    if sub == "add-col":
        print("参数不足: add-col")
        _print_av_help("add-col")
        return 1

    if sub == "add-row" and len(args) >= 2:
        row_id = av.add_row(args[1])
        _print_json({"code": 0, "msg": "", "data": {"row_id": row_id}})
        return 0
    if sub == "add-row":
        print("参数不足: add-row")
        _print_av_help("add-row")
        return 1

    if sub == "add-row-from-block" and len(args) >= 3:
        row_id = av.add_row(args[1], detached=False, source_block_id=args[2])
        _print_json({"code": 0, "msg": "", "data": {"row_id": row_id}})
        return 0
    if sub == "add-row-from-block":
        print("参数不足: add-row-from-block")
        _print_av_help("add-row-from-block")
        return 1

    if sub == "set-cell" and len(args) >= 6:
        av_id, key_id, item_id, col_type = args[1], args[2], args[3], args[4]
        value = " ".join(args[5:])
        _print_json(av.set_cell(av_id, key_id, item_id, value, col_type=col_type))
        return 0
    if sub == "set-cell":
        print("参数不足: set-cell")
        _print_av_help("set-cell")
        return 1

    if sub == "set-cell-by-name" and len(args) >= 5:
        av_id, row_id, key_ref = args[1], args[2], args[3]
        value = " ".join(args[4:])
        _print_json(av.set_cell_by_name(av_id, row_id, key_ref, value))
        return 0
    if sub == "set-cell-by-name":
        print("参数不足: set-cell-by-name")
        _print_av_help("set-cell-by-name")
        return 1

    if sub == "add-row-with-data" and len(args) >= 3:
        av_id = args[1]
        strict = False
        primary_block = ""
        payload_parts: List[str] = []
        i = 2
        while i < len(args):
            token = args[i]
            if token == "--strict":
                strict = True
                i += 1
                continue
            if token == "--primary-block" and i + 1 < len(args):
                primary_block = args[i + 1]
                i += 2
                continue
            payload_parts = args[i:]
            break
        if not payload_parts:
            print("参数不足: add-row-with-data")
            _print_av_help("add-row-with-data")
            return 1
        payload = json.loads(" ".join(payload_parts))
        if primary_block:
            payload["__primary_block_id"] = primary_block
        row_id = av.add_row_with_data(av_id, payload, strict=strict)
        _print_json({"code": 0, "msg": "", "data": {"row_id": row_id}})
        return 0
    if sub == "add-row-with-data":
        print("参数不足: add-row-with-data")
        _print_av_help("add-row-with-data")
        return 1

    if sub == "validate" and len(args) >= 2:
        av_id = args[1]
        cleanup = True
        for token in args[2:]:
            if token == "--no-cleanup":
                cleanup = False
                continue
            raise ValidationError(f"validate 未知参数: {token}")
        result = av.validate_database(av_id, cleanup=cleanup)
        next_actions = ["python3 scripts/siyuan.py av render <av_id_or_av_block_id>"]
        if result.get("code") != 0:
            next_actions.insert(0, "python3 scripts/siyuan.py av schema <av_id_or_av_block_id>")
        _print_json(_with_next_actions(result, next_actions))
        return 0 if result.get("code") == 0 else 1
    if sub == "validate":
        print("参数不足: validate")
        _print_av_help("validate")
        return 1

    if sub == "remove-rows" and len(args) >= 3:
        av_id = args[1]
        row_ids = [x.strip() for x in " ".join(args[2:]).split(",") if x.strip()]
        _print_json(av.remove_rows(av_id, row_ids))
        return 0
    if sub == "remove-rows":
        print("参数不足: remove-rows")
        _print_av_help("remove-rows")
        return 1

    if sub == "duplicate" and len(args) >= 2:
        _print_json(av.duplicate(args[1]))
        return 0
    if sub == "duplicate":
        print("参数不足: duplicate")
        _print_av_help("duplicate")
        return 1

    if sub == "create-db" and len(args) >= 3:
        notebook_id, path = args[1], args[2]
        columns = []
        if len(args) >= 4:
            raw = " ".join(args[3:])
            if raw.strip().startswith("["):
                parsed = json.loads(raw)
                if not isinstance(parsed, list):
                    raise ValidationError("create-db 的 JSON 列定义必须是数组")
                columns = parsed
            else:
                columns = [x.strip() for x in raw.split(",") if x.strip()]
        result = av.create_database(notebook_id, path, columns=columns)
        _print_json(
            _with_next_actions(
                {"code": 0, "msg": "", "data": result},
                [
                    "python3 scripts/siyuan.py av schema <av_id_or_av_block_id>",
                    "python3 scripts/siyuan.py av validate <av_id_or_av_block_id>",
                ],
            )
        )
        return 0
    if sub == "create-db":
        print("参数不足: create-db")
        _print_av_help("create-db")
        return 1

    if sub == "create-template" and len(args) >= 3:
        notebook_id, path = args[1], args[2]
        columns: List[Any] = _default_template_columns()
        if len(args) >= 4:
            columns = _parse_columns_arg(" ".join(args[3:]))
        result = av.create_database(notebook_id, path, columns=columns)
        _print_json(
            _with_next_actions(
                {"code": 0, "msg": "", "data": {**result, "template": True}},
                [
                    "python3 scripts/siyuan.py av seed <av_id_or_av_block_id> --rows '[{\"__title\":\"Task A\"}]'",
                    "python3 scripts/siyuan.py av validate <av_id_or_av_block_id>",
                ],
            )
        )
        return 0
    if sub == "create-template":
        print("参数不足: create-template")
        _print_av_help("create-template")
        return 1

    if sub == "create-inline-template" and len(args) >= 2:
        parent_id = args[1]
        columns: List[Any] = _default_template_columns()
        rows: List[Dict[str, Any]] = []
        strict = True
        remove_default_single_select = True

        i = 2
        if i < len(args) and not args[i].startswith("--"):
            columns = _parse_columns_arg(args[i])
            i += 1

        while i < len(args):
            token = args[i]
            if token == "--rows" and i + 1 < len(args):
                rows = _load_rows_spec(args[i + 1])
                i += 2
                continue
            if token == "--strict":
                strict = True
                i += 1
                continue
            if token == "--no-strict":
                strict = False
                i += 1
                continue
            if token == "--keep-default-select":
                remove_default_single_select = False
                i += 1
                continue
            raise ValidationError(f"create-inline-template 未知参数: {token}")

        result = av.create_inline_template(
            parent_id=parent_id,
            columns=columns,
            rows=rows,
            strict=strict,
            remove_default_single_select=remove_default_single_select,
        )
        _print_json(
            _with_next_actions(
                {"code": 0, "msg": "", "data": result},
                [
                    "python3 scripts/siyuan.py av render <av_id_or_av_block_id>",
                    "python3 scripts/siyuan.py av validate <av_id_or_av_block_id>",
                ],
            )
        )
        return 0
    if sub == "create-inline-template":
        print("参数不足: create-inline-template")
        _print_av_help("create-inline-template")
        return 1

    if sub == "seed" and len(args) >= 2:
        av_id = args[1]
        strict = True
        rows_spec = ""
        i = 2
        while i < len(args):
            token = args[i]
            if token == "--rows" and i + 1 < len(args):
                rows_spec = args[i + 1]
                i += 2
                continue
            if token == "--strict":
                strict = True
                i += 1
                continue
            if token == "--no-strict":
                strict = False
                i += 1
                continue
            raise ValidationError(f"seed 未知参数: {token}")
        if not rows_spec:
            print("参数不足: seed")
            _print_av_help("seed")
            return 1
        rows = _load_rows_spec(rows_spec)
        result = av.seed_rows(av_id, rows, strict=strict)
        _print_json(
            _with_next_actions(
                result,
                [
                    "python3 scripts/siyuan.py av validate <av_id_or_av_block_id>",
                    "python3 scripts/siyuan.py av render <av_id_or_av_block_id>",
                ],
            )
        )
        return 0 if result.get("code") == 0 else 1
    if sub == "seed":
        print("参数不足: seed")
        _print_av_help("seed")
        return 1

    if sub == "seed-test-db" and len(args) >= 3:
        notebook_id, path = args[1], args[2]
        columns = [
            "Task:text",
            "Amount:number",
            "Due:date",
            "Status:select",
            "Tags:mSelect",
            "Done:checkbox",
            "Link:url",
            "Email:email",
            "Phone:phone",
            "Related:relation",
            "Asset:mAsset",
        ]
        created = av.create_database(notebook_id, path, columns=columns)
        av_id = created["av_id"]

        seed_rows = [
            {
                "Task": "Seed row 1",
                "Amount": 10,
                "Due": "2026-03-01",
                "Status": "Todo",
                "Tags": ["demo", "seed"],
                "Done": False,
                "Link": "https://example.com/1",
                "Email": "row1@example.com",
                "Phone": "10001",
                "Related": [],
                "Asset": "assets/demo-1.png",
            },
            {
                "Task": "Seed row 2",
                "Amount": 20.5,
                "Due": "2026-03-02",
                "Status": "Doing",
                "Tags": ["demo", "doing"],
                "Done": True,
                "Link": "https://example.com/2",
                "Email": "row2@example.com",
                "Phone": "10002",
                "Related": [],
                "Asset": "assets/demo-2.png",
            },
            {
                "Task": "Seed row 3",
                "Amount": 30,
                "Due": "2026-03-03",
                "Status": "Done",
                "Tags": ["demo", "done"],
                "Done": True,
                "Link": "https://example.com/3",
                "Email": "row3@example.com",
                "Phone": "10003",
                "Related": [],
                "Asset": "assets/demo-3.png",
            },
            {
                "Task": "Seed row 4",
                "Amount": 40,
                "Due": "2026-03-04",
                "Status": "Todo",
                "Tags": ["demo", "todo"],
                "Done": False,
                "Link": "https://example.com/4",
                "Email": "row4@example.com",
                "Phone": "10004",
                "Related": [],
                "Asset": "assets/demo-4.png",
            },
            {
                "Task": "Seed row 5",
                "Amount": 50,
                "Due": "2026-03-05",
                "Status": "Doing",
                "Tags": ["demo", "urgent"],
                "Done": False,
                "Link": "https://example.com/5",
                "Email": "row5@example.com",
                "Phone": "10005",
                "Related": [],
                "Asset": "assets/demo-5.png",
            },
        ]

        row_ids: List[str] = []
        for row in seed_rows:
            row_ids.append(av.add_row_with_data(av_id, row, strict=True))

        _print_json(
            {
                "code": 0,
                "msg": "",
                "data": {
                    **created,
                    "seed_rows": len(seed_rows),
                    "row_ids": row_ids,
                },
            }
        )
        return 0
    if sub == "seed-test-db":
        print("参数不足: seed-test-db")
        _print_av_help("seed-test-db")
        return 1

    print(f"未知 av 子命令: {sub}")
    _print_av_help("")
    return 1


def main(argv: Optional[List[str]] = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])

    client = DEFAULT_CLIENT
    search = SearchModule(client)
    av = AttributeViewClient(client)
    blocks = BlockModule(client)
    documents = DocumentModule(client)

    if not args:
        _print_usage()
        return 1

    cmd = args[0]
    if cmd in ("help", "--help", "-h"):
        _print_usage()
        return 0

    alias_map = {
        "edit": "update",
        "insert": "append",
    }
    cmd = alias_map.get(cmd, cmd)

    try:
        if cmd == "version":
            _print_json(client.get_version())
            return 0

        if cmd == "doctor":
            return _cmd_doctor(client, args[1:])

        if cmd == "capabilities":
            return _cmd_capabilities(client, args[1:])

        if cmd == "notebooks":
            json_mode = "--json" in args[1:]
            res = client.ls_notebooks()
            if res.get("code") == 0:
                if json_mode:
                    _print_json(
                        _with_next_actions(
                            res,
                            [
                                "python3 scripts/siyuan.py docs recent --limit 10 --json",
                            ],
                        )
                    )
                    return 0
                for nb in res.get("data", {}).get("notebooks", []):
                    icon = nb.get("icon")
                    icon_char = chr(int(icon, 16)) if icon else "📓"
                    print(f"{icon_char} {nb.get('name', '')} (ID: {nb.get('id', '')})")
                return 0
            _print_json(res)
            return 1

        if cmd == "docs":
            return _cmd_docs(search, args[1:])

        if cmd == "doc":
            return _cmd_doc(documents, args[1:])

        if cmd == "search" and len(args) >= 2:
            keyword = " ".join(args[1:])
            res = search.smart_search(keyword, limit=20)
            if res.get("code") == 0:
                for block in res.get("data", []):
                    print(f"📄 {block.get('hpath', 'N/A')}")
                    print(f"   ID: {block.get('id', '')}")
                    print(f"   内容: {str(block.get('content', ''))[:80]}...")
                    print()
                return 0
            _print_json(res)
            return 1

        if cmd == "search-type" and len(args) >= 2:
            flags = _parse_search_type_flags(args[1:])
            res = search.search_by_type(
                flags["type"],
                subtype=flags["subtype"],
                box=flags["box"],
                limit=flags["limit"],
            )
            if res.get("code") == 0:
                for block in res.get("data", []):
                    print(f"📄 {block.get('hpath', 'N/A')}")
                    print(f"   ID: {block.get('id', '')}")
                    print(f"   类型: {block.get('type', '')}/{block.get('subtype', '')}")
                    print(f"   内容: {str(block.get('content', ''))[:80]}...")
                    print()
                return 0
            _print_json(res)
            return 1

        if cmd == "sql" and len(args) >= 2:
            _print_json(client.sql_query(" ".join(args[1:])))
            return 0

        if cmd == "export" and len(args) >= 2:
            res = client.export_md(args[1])
            if res.get("code") == 0:
                print(res.get("data", {}).get("content", ""))
                return 0
            _print_json(res)
            return 1

        if cmd == "create" and len(args) >= 3:
            notebook_id, path = args[1], args[2]
            markdown = ""
            if len(args) >= 4 or not sys.stdin.isatty():
                markdown = _parse_write_content(args, 3, "create")
            _print_json(client.create_doc(notebook_id, path, markdown))
            return 0

        if cmd == "update" and len(args) >= 3:
            block_id = args[1]
            markdown = _parse_write_content(args, 2, "update")
            _print_json(client.update_block(block_id, markdown))
            return 0

        if cmd == "append" and len(args) >= 3:
            parent_id = args[1]
            markdown = _parse_write_content(args, 2, "append")
            _print_json(client.append_block(parent_id, markdown))
            return 0

        if cmd == "prepend" and len(args) >= 3:
            parent_id = args[1]
            markdown = _parse_write_content(args, 2, "prepend")
            _print_json(client.prepend_block(parent_id, markdown))
            return 0

        if cmd == "insert-after" and len(args) >= 3:
            previous_id = args[1]
            markdown = _parse_write_content(args, 2, "insert-after")
            _print_json(client.insert_block_after(previous_id, markdown))
            return 0

        if cmd == "delete" and len(args) >= 2:
            _print_json(client.delete_block(args[1]))
            return 0

        if cmd == "check" and len(args) >= 2:
            _print_json(blocks.check_task(args[1]))
            return 0

        if cmd == "block":
            return _cmd_block(blocks, args[1:])

        if cmd == "refs":
            return _cmd_refs(blocks, args[1:])

        if cmd == "callout":
            return _cmd_callout(blocks, args[1:])

        if cmd == "embed":
            return _cmd_embed(blocks, args[1:])

        if cmd == "super":
            return _cmd_super(blocks, args[1:])

        if cmd == "table":
            return _cmd_table(blocks, args[1:])

        if cmd == "open-doc" and len(args) >= 2:
            doc_id = args[1]
            view = "readable"
            rest = args[2:]
            if rest and rest[0] in ("readable", "patchable", "typed"):
                view = rest[0]
                rest = rest[1:]
            flags = _parse_open_doc_flags(rest)
            json_mode = bool(flags.pop("json", False))
            result = documents.open_doc(doc_id, view=view, **flags)
            if json_mode:
                _print_json({"code": 0, "msg": "", "data": result})
            else:
                print(result["content"])
            return 0

        if cmd == "apply-patch" and len(args) >= 2:
            doc_id = args[1]
            if sys.stdin.isatty():
                raise ValidationError("apply-patch 需要通过 stdin 传入 PMF 内容")
            pmf_content = sys.stdin.read()
            _print_json(documents.apply_patch(doc_id, pmf_content))
            return 0

        if cmd == "av":
            return _cmd_av(av, args[1:])

        print(f"未知命令或参数不足: {cmd}")
        return 1

    except (SiyuanBridgeError, json.JSONDecodeError, ValueError) as e:
        print(f"错误: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
