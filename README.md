# Siyuan Bridge Skill

Siyuan Bridge 是一个面向 SiYuan 的技能包，通过稳定的 CLI 提供可落地的笔记操作能力。
核心目标是三点：写入可靠、数据库操作稳定、安全边界清晰。

English version: [README.en.md](./README.en.md)

## 仓库结构

- 根目录放人类文档：`README.md`（中文主文档）、`README.en.md`（英文辅助文档）。
- 实际 skill 包放在 `siyuan-bridge/` 目录。
- Agent 入口文件是 `siyuan-bridge/SKILL.md`。

## 主要功能

### 文档能力

- 支持 `readable`、`typed`、`patchable` 三种文档读取视图。
- 支持从 URL、Markdown、对话文本整文导入。
- 支持整文写入（`replace`/`append`）。
- 支持 PMF 补丁流程，便于受控修改。

### 块级能力

- 支持 update/append/prepend/insert-after/delete 等基础写操作。
- 提供 `check`、callout、表格追加行等实用命令。

### AttributeView（数据库）能力

- 支持新建独立数据库文档与页面内内嵌数据库。
- 支持 schema 读取、按列名写入、增删列、增删行。
- 支持 JSON 批量 seed 与数据库自检。
- 覆盖常用字段类型：text/number/date/select/mSelect/checkbox/url/email/phone/relation/mAsset。

## 数据库能力为什么稳定

数据库路径做了明确的“防错机制 + 固定流程”：

- AV ID 统一解析：
  可传 AV block ID 或真实 AV ID，内部自动归一。
- 异步就绪处理：
  新建库后会等待/重试，直到 AV view 可写。
- 主键列稳定：
  默认在主键 `block` 列后插入业务列，避免主键被挤乱。
- 严格写入模式：
  `--strict` 会拒绝未知列名，不做静默吞错。
- 行 ID 可靠回收：
  加行后会重新渲染并获取真实 row_id。
- 选项列可控：
  `add-col --options` 支持显式颜色并落盘到 schema。
- 日期编码正确：
  date 统一按 Unix 毫秒写入，避免年份显示异常。
- 内嵌建库目标明确：
  同时支持 `doc_id` 与普通 `block_id` 作为父目标。

## 安全与数据一致性

- 默认启用读后写保护。
- 冲突检测结合读标记、文档更新时间和 TTL。
- 仅显式开关可绕过：`SIYUAN_ALLOW_UNSAFE_WRITE=true`。
- PMF `apply-patch` 当前版本采用安全子集策略。
- 写入参数中若出现字面量 `\n`，CLI 默认拒绝，并提示使用 stdin/heredoc 或 `--decode-escapes`。

## 实现方式（简述）

- `siyuan-bridge/scripts/core/`：配置、API 客户端、日志基础设施。
- `siyuan-bridge/scripts/modules/`：文档、块、检索、数据库业务模块。
- `siyuan-bridge/scripts/guards/`：读后写围栏与冲突检测。
- `siyuan-bridge/scripts/formats/`：PMF 与 markdown 辅助。
- `siyuan-bridge/scripts/cli/siyuan_cli.py`：对外命令路由与兼容入口。

## API Token 存储方式

仓库中不硬编码 token。

配置优先级：
1. 环境变量
2. `siyuan-bridge/scripts/config.local.json`
3. `siyuan-bridge/scripts/config.json`

Token 来源：
- `SIYUAN_TOKEN`（最高优先级）
- `token_file`（默认：`~/.config/siyuan/api_token`）

推荐配置：

```bash
mkdir -p ~/.config/siyuan
echo "your_siyuan_api_token" > ~/.config/siyuan/api_token
chmod 600 ~/.config/siyuan/api_token
cp siyuan-bridge/scripts/config.example.json siyuan-bridge/scripts/config.local.json
```
