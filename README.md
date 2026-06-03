# Siyuan Bridge Skill

这是一个给 Codex/agent 使用的 SiYuan 连接 skill。它通过一个 Python CLI 调用 SiYuan HTTP API，用来搜索、读取、修改文档和操作 AttributeView 数据库。

English version: [README.en.md](./README.en.md)

## 目录

实际 skill 在：

```text
siyuan-bridge/
```

主要入口：

```text
siyuan-bridge/SKILL.md
siyuan-bridge/scripts/siyuan.py
```

## 安装到本机 Codex

把 `siyuan-bridge/` 复制到 Codex 的 skills 目录：

```bash
mkdir -p ~/.codex/skills
cp -R siyuan-bridge ~/.codex/skills/siyuan-bridge
```

如果本机已经装过，可以用 `rsync` 覆盖，但不要覆盖本地配置：

```bash
rsync -a --delete \
  --exclude 'scripts/config.local.json' \
  --exclude 'scripts/.siyuan-read-guard-cache.json' \
  --exclude 'scripts/.siyuan-writes.log' \
  siyuan-bridge/ ~/.codex/skills/siyuan-bridge/
```

## 配置连接

配置优先级：

1. 环境变量
2. `siyuan-bridge/scripts/config.local.json`
3. `siyuan-bridge/scripts/config.json`

推荐把 token 放在单独文件里，不写进仓库：

```bash
mkdir -p ~/.config/siyuan
echo "your_siyuan_api_token" > ~/.config/siyuan/api_token
chmod 600 ~/.config/siyuan/api_token
```

复制本地配置文件：

```bash
cd siyuan-bridge
cp scripts/config.example.json scripts/config.local.json
```

编辑 `scripts/config.local.json`：

```json
{
  "api_url": "http://127.0.0.1:6806",
  "token_file": "~/.config/siyuan/api_token",
  "forbidden_notebooks": [],
  "main_notebook_id": "",
  "read_guard_ttl_seconds": 3600,
  "open_doc_char_limit": 15000,
  "write_log_path": ".siyuan-writes.log",
  "read_guard_cache_path": ".siyuan-read-guard-cache.json"
}
```

如果 SiYuan 在 NAS、Docker 或远程机器上，把 `api_url` 改成对应地址。临时切换地址可以用环境变量：

```bash
SIYUAN_API_URL="https://<your-siyuan-domain>" python3 scripts/siyuan.py doctor --json
```

## 检查连接

在 skill 目录运行：

```bash
cd siyuan-bridge
python3 scripts/siyuan.py doctor --json
```

如果正常，会看到：

```json
{
  "ok": true
}
```

也可以列出功能：

```bash
python3 scripts/siyuan.py capabilities --json
```

## 常用命令

查看笔记本：

```bash
python3 scripts/siyuan.py notebooks --json
```

查看最近文档：

```bash
python3 scripts/siyuan.py docs recent --limit 10 --json
```

读取文档结构：

```bash
python3 scripts/siyuan.py open-doc <doc_id> typed --semantic --json
```

读取有限文档树：

```bash
python3 scripts/siyuan.py doc tree <notebook_id> / --depth 2 --limit 200 --json
```

搜索：

```bash
python3 scripts/siyuan.py search <keyword>
python3 scripts/siyuan.py search-type d --limit 10
```

读取块：

```bash
python3 scripts/siyuan.py block get <block_id> --format markdown
python3 scripts/siyuan.py block get <block_id> --format kramdown --command "head 20"
python3 scripts/siyuan.py block attrs <block_id>
```

调用只读 API：

```bash
python3 scripts/siyuan.py api post /api/system/version '{}'
```

## 写入命令

写入前建议先读目标文档：

```bash
python3 scripts/siyuan.py open-doc <doc_id> typed --semantic --json
```

常见写入：

```bash
python3 scripts/siyuan.py append <parent_id> "new content"
python3 scripts/siyuan.py update <block_id> "new content"
python3 scripts/siyuan.py prepend <parent_id> "new content"
python3 scripts/siyuan.py insert-after <block_id> "new content"
python3 scripts/siyuan.py delete <block_id>
```

文档操作：

```bash
python3 scripts/siyuan.py doc create-child <parent_doc_id> <title> "content"
python3 scripts/siyuan.py doc rename <doc_id> <new_title>
python3 scripts/siyuan.py doc move <from_doc_ids_csv> <to_doc_id>
python3 scripts/siyuan.py doc write-full <doc_id_or_path> --mode replace < markdown.md
```

## AttributeView 数据库

查看 schema：

```bash
python3 scripts/siyuan.py av schema <av_id_or_av_block_id>
```

创建页面内数据库：

```bash
python3 scripts/siyuan.py av create-inline-template <parent_doc_id> \
  '[{"name":"Status","type":"select","options":[{"name":"Todo","color":"2"}]}]' \
  --rows '[{"__title":"Task A","Status":"Todo"}]' \
  --strict
```

加一行：

```bash
python3 scripts/siyuan.py av add-row-with-data <av_id_or_av_block_id> --strict \
  '{"__title":"Task B","Status":"Todo"}'
```

批量 seed：

```bash
python3 scripts/siyuan.py av seed <av_id_or_av_block_id> --rows '[{"__title":"Task C"}]' --strict
```

检查数据库：

```bash
python3 scripts/siyuan.py av validate <av_id_or_av_block_id>
```

## 写入保护

默认有读后写保护。简单说：修改已有内容前，先读目标文档；否则某些写入会被拒绝。

如果确实要绕过：

```bash
SIYUAN_ALLOW_UNSAFE_WRITE=true python3 scripts/siyuan.py ...
```

不建议长期打开这个开关。

## 本地文件

这些文件是本地状态，不应该提交：

```text
siyuan-bridge/scripts/config.local.json
siyuan-bridge/scripts/.siyuan-read-guard-cache.json
siyuan-bridge/scripts/.siyuan-writes.log
```

## 测试

运行单元测试：

```bash
cd siyuan-bridge
python3 -m unittest discover -s scripts/tests
```

运行连接测试：

```bash
python3 scripts/siyuan.py doctor --json
```
