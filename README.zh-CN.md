# Siyuan Bridge Skill

Siyuan Bridge 是一个面向 SiYuan 的实用技能，提供稳定的 CLI 来完成真实的笔记读写任务。  
重点能力是：文档读取、块编辑、AttributeView 数据库操作，以及安全补丁流程。

## 能力范围

- 以 readable/typed/patchable 视图读取文档。
- 将 URL、Markdown、对话文本整文导入到 SiYuan。
- 执行整文写入（`replace`/`append`）和块级写操作。
- 操作 AttributeView 数据库：
  - 创建数据库文档
  - 在现有页面内创建内嵌数据库
  - 增删列
  - 增加行并按列名写单元格
  - 校验 schema、严格写入、日期编码
- 默认启用读后写保护，降低误写和并发冲突风险。

## 实现方式（简述）

- `scripts/core/`
  - `config.py`：配置加载与优先级处理
  - `client.py`：统一 SiYuan API 客户端与写入保护集成
  - `logging_utils.py`：UTF-8 安全日志写入
- `scripts/modules/`
  - `documents.py`：文档读取/写入/导入
  - `blocks.py`：块级操作
  - `attributeview.py`：数据库能力与类型转换
  - `search.py`：查询能力
- `scripts/guards/`
  - `read_guard.py`：读后写围栏与冲突检测
- `scripts/formats/`
  - `pmf.py`：PMF 解析/渲染与安全子集补丁
- `scripts/cli/siyuan_cli.py`
  - 对外命令路由与兼容入口

## API Token 存储方式

仓库中不硬编码 token。

配置优先级：
1. 环境变量
2. `scripts/config.local.json`
3. `scripts/config.json`

Token 来源：
- `SIYUAN_TOKEN`（最高优先级）
- `token_file` 路径（默认：`~/.config/siyuan/api_token`）

推荐配置：

```bash
mkdir -p ~/.config/siyuan
echo "your_siyuan_api_token" > ~/.config/siyuan/api_token
chmod 600 ~/.config/siyuan/api_token
cp scripts/config.example.json scripts/config.local.json
```

## 安全默认值

- 默认开启读后写保护。
- 仅显式开关可绕过：`SIYUAN_ALLOW_UNSAFE_WRITE=true`。
- AV 日期按 Unix 毫秒时间戳写入。
- 写入参数中如果包含字面量 `\n`，CLI 默认拒绝；请改用 stdin/heredoc 或 `--decode-escapes`。
