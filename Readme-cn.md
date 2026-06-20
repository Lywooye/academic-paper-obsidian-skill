# Academic Paper to Obsidian Skill

中文说明文件。英文版见 `README.md`。

这是一个轻量级、OpenClaw 优先的 skill，用于把 DOI/PDF 交接流程变成基于 Zotero 和 Obsidian 的学术阅读工作流。它让 agent 可以清楚地完成文献信息核对、Zotero 条目创建、总结保存、细读/归档/已读列表维护，并可选地把 PDF 转换成能在 Obsidian 中直接链接的 Markdown 笔记。

核心能力：

- 根据 DOI/PDF 交接信息核准文献元数据，并创建 Zotero 条目
- 将本地 PDF 附加到匹配的 Zotero 条目
- 由 summary agent 生成并保存文献总结 Markdown 笔记
- 维护 Obsidian 中的 close-reading、archive 和 read 列表
- 可选使用 MinerU 将 PDF 转换为 Markdown，方便在 Obsidian 内阅读原文并做笔记
- 将 close-reading 列表条目直接链接到生成的 Markdown 文件
- 校验阅读列表条目和转换后 Markdown 中的图片链接

本仓库刻意不包含个人路径、API key、飞书 ID、私有 agent 名称和私有日志。所有本地配置都应通过 `config.json` 和环境变量完成。

## OpenClaw 优先，但不只支持 OpenClaw

本项目为 OpenClaw 风格的 agent 工作流设计：它包含 `SKILL.md`、三个通用 agent 角色，以及 reference、summary、coordinator agent 之间的交接规则。

底层 Python 脚本都是普通命令行工具。其他 agent 系统只要能按文档参数调用 shell 命令，也可以使用同一套流程；这些脚本也可以手动运行。

## 工作流程

1. 将 DOI 或 PDF 发给你的 coordinator agent。
2. reference agent 核准 Zotero 信息，并添加 Zotero 条目。
3. summary agent 撰写文献总结，并由 coordinator agent 发送给你。
4. 你回复处理决定，例如 `close-reading` 或 `archive`。
5. coordinator agent 将文献信息写入对应的 Obsidian close-reading 或 archive 列表，并校验条目存在。
6. 如果你选择 `close-reading`，coordinator agent 可以可选地用 MinerU 将 PDF 转换为 Markdown。生成的 Markdown 会保存到你配置的 Obsidian 目录中，close-reading 列表里的文献标题会直接链接到这个 Markdown 笔记。表格和图片也会随正文一起转换，方便在 Obsidian 内阅读原文并做笔记。
7. 读完后，告诉 coordinator agent 这篇文献为 `read`；coordinator agent 会自动把文献信息移入 Obsidian read 列表并校验。

## 适合谁

如果你使用以下工具，这个项目会比较有用：

- Zotero 作为文献元数据的可信来源
- Obsidian 作为长期阅读列表和笔记库
- OpenClaw 等 agent 系统来协调文献检索、总结和文件操作
- 可选使用 MinerU 做 PDF 到 Markdown 的转换

它可能不适合一般读者，但如果你已经在同时使用 Zotero 和 Obsidian，并希望减少 PDF、列表和笔记交接中的断点，它会比较有用。

## 快速开始

```bash
git clone https://github.com/Lywooye/academic-paper-obsidian-skill.git
cd academic-paper-obsidian-skill
cp config.example.json config.json
cp .env.example .env
```

编辑 `config.json`：

```json
{
  "vaultRoot": "/absolute/path/to/your/obsidian-vault"
}
```

导出 Zotero 凭证：

```bash
export ZOTERO_API_KEY="..."
export ZOTERO_USER_ID="..."
```

运行测试：

```bash
python3 -m unittest discover -s tests
```

## 常用命令

将文献加入 close-reading 列表：

```bash
python3 scripts/reading_list.py \
  --config config.json \
  --action add \
  --status todo \
  --id "ABCDEFGH" \
  --title "Paper Title" \
  --file "Paper Title-2026-06-20-ABCDEFGH.md" \
  --journal "Medical Image Analysis" \
  --if "N/A" \
  --date "2026-06-20" \
  --doi "10.xxxx/example" \
  --summary "A concise reason to read this paper."
```

将本地 PDF 附加到已有 Zotero 条目：

```bash
python3 scripts/attach_pdf_by_doi.py "/path/to/paper.pdf" --doi "10.xxxx/example" --config config.json
```

保存 summary agent 的总结笔记：

```bash
python3 scripts/write_summary_note.py \
  --config config.json \
  --id "ABCDEFGH" \
  --title "Paper Title" \
  --cn-title "论文中文标题" \
  --journal "Medical Image Analysis" \
  --date "2026-06-20" \
  --doi "10.xxxx/example" \
  --summary-file examples/sample_summary.md
```

手动或通过持久化任务运行器用 MinerU 将 PDF 转换为 Markdown：

```bash
python3 scripts/convert_and_notify.py "/path/to/paper.pdf" --config config.json --zotero-id "ABCDEFGH"
```

在 OpenClaw 中排队一个面向用户的 MinerU 转换任务：

```bash
python3 scripts/queue_convert_and_notify.py \
  "/path/to/paper.pdf" \
  --config config.json \
  --zotero-id "ABCDEFGH"
```

对于 OpenClaw，这是推荐的用户可见路径。queue 脚本会创建一个 `openclaw cron add --command-argv ... --announce` command job；该 job 会在 `convert_and_notify.py` 校验 Markdown 文件和图片链接后，自动发送最终成功/失败结果。立即返回的 queue 响应只代表“已排队”，不要再单独创建 PID 轮询 cron。

MinerU 是可选的。在本地 MinerU 安装可用之前，保持 `mineru.enabled=false` 即可。

## 配置

### 前置条件

你需要：

- Python 3.10+
- 一个 Obsidian vault
- Zotero API key
- 可选安装 MinerU，仅在需要 PDF 到 Markdown 转换时使用

### 配置 Obsidian

复制示例配置：

```bash
cp config.example.json config.json
```

将 `vaultRoot` 设置为你的 Obsidian vault：

```json
{
  "vaultRoot": "/absolute/path/to/your/obsidian-vault"
}
```

如果你的 vault 使用不同文件夹结构，可以继续调整 vault 相对路径：

```json
{
  "paths": {
    "readingDir": "01_Maps/03_Reading",
    "academicTodoList": "Academic Papers - To Read.md",
    "academicArchiveList": "Academic Papers - Archive.md",
    "academicNotesDir": "00_Inbox/PDFs",
    "summaryNotesDir": "11_Academic/Summaries",
    "attachmentsDir": "99_Resources/Attachments"
  }
}
```

列表文件名可以本地化。例如：

```json
{
  "academicTodoList": "Papers - Close Reading.md",
  "academicArchiveList": "Papers - Archive.md"
}
```

### 配置 Zotero

在 Zotero 设置页创建 API key，并导出为环境变量：

```bash
export ZOTERO_API_KEY="your-zotero-api-key"
export ZOTERO_USER_ID="your-zotero-user-id"
```

如果使用 Zotero group library，则导出 `ZOTERO_GROUP_ID`，而不是 `ZOTERO_USER_ID`：

```bash
export ZOTERO_GROUP_ID="your-zotero-group-id"
```

你也可以复制 `.env.example` 到 `.env` 作为本地参考，但脚本会从环境变量读取凭证。

### 配置 Agent 名称

公开工作流使用三个通用角色名称：

- `reference agent`：解析 DOI/Zotero 元数据、PDF 附件和来源信息
- `summary agent`：基于可信元数据和可用正文生成文献总结
- `coordinator agent`：调用脚本、写入文件并校验输出

你可以保留默认名称，也可以在 `config.json` 中个性化：

```json
{
  "agents": {
    "referenceAgentName": "reference agent",
    "summaryAgentName": "summary agent",
    "coordinatorAgentName": "coordinator agent"
  }
}
```

这些名称只会作为来源信息写入总结笔记。脚本本身不依赖特定 agent 平台。

### 可选 MinerU 配置

MinerU 默认关闭。如果你只需要 Zotero 附件和 Obsidian 阅读列表管理，可以保持关闭：

```json
{
  "mineru": {
    "enabled": false
  }
}
```

如果要启用 PDF 到 Markdown 转换，需要单独安装 MinerU，并将 `mineru.bin` 指向本地可执行文件：

```json
{
  "mineru": {
    "enabled": true,
    "bin": "/absolute/path/to/mineru",
    "deviceMode": "mps",
    "timeoutSec": 3600,
    "taskResultDownloadTimeoutSec": 600,
    "pdfRenderTimeoutSec": 600
  }
}
```

Apple Silicon 可优先使用 `mps`，支持 NVIDIA 的环境可用 `cuda`，也可以使用较慢的 `cpu` 作为兜底。

### 可选 OpenClaw Queue 配置

本项目是 OpenClaw 优先的。在 OpenClaw 中，用户可见的长时间 PDF 转换应作为 command job 排队，而不是直接在对话 agent turn 中运行：

```json
{
  "openclaw": {
    "cli": "openclaw",
    "commandCwd": "",
    "channel": "",
    "notifyToEnv": "OPENCLAW_MINERU_NOTIFY_TO",
    "outputMaxBytes": 12000,
    "timeoutGraceSec": 300
  }
}
```

只有当你的 OpenClaw 部署需要显式投递目标时，才设置 `OPENCLAW_MINERU_NOTIFY_TO`。实际平台用户或频道 ID 应保存在本地环境变量中，不要写入 `config.json`：

```bash
export OPENCLAW_MINERU_NOTIFY_TO="your-openclaw-delivery-target"
```

先用 `--dry-run` 确认 OpenClaw 将创建的 command job：

```bash
python3 scripts/queue_convert_and_notify.py \
  "/path/to/paper.pdf" \
  --config config.json \
  --zotero-id "ABCDEFGH" \
  --dry-run
```

不要把私有用户 ID 写进公开配置或文档。其他 agent 系统可以跳过 `queue_convert_and_notify.py`，直接从自己的持久化任务运行器调用 `convert_and_notify.py`；但应保留相同的完成标准：只有在 Markdown 产物和图片链接都校验通过后，才报告成功。

### 冒烟测试

运行单元测试：

```bash
python3 -m unittest discover -s tests
```

然后针对配置好的 vault 测试阅读列表写入：

```bash
python3 scripts/reading_list.py \
  --config config.json \
  --action add \
  --status todo \
  --id "ABCDEFGH" \
  --title "Paper Title" \
  --file "Paper Title-2026-06-20-ABCDEFGH.md" \
  --journal "Example Journal" \
  --if "N/A" \
  --date "2026-06-20" \
  --doi "10.xxxx/example" \
  --summary "A concise reason to read this paper."
```

再测试总结笔记写入：

```bash
python3 scripts/write_summary_note.py \
  --config config.json \
  --id "ABCDEFGH" \
  --title "Paper Title" \
  --journal "Example Journal" \
  --date "2026-06-20" \
  --doi "10.xxxx/example" \
  --summary "This is a short test summary."
```

`config.example.json` 包含所有支持的配置项。最重要的字段包括：

- `vaultRoot`：Obsidian vault 的绝对路径
- `paths.academicNotesDir`：转换后的文献 Markdown 文件目录
- `paths.summaryNotesDir`：summary agent 笔记保存目录
- `paths.attachmentsDir`：提取图片保存目录
- `paths.academicTodoList`：close-reading 列表文件名
- `paths.academicArchiveList`：archive 列表文件名
- `agents.referenceAgentName`：负责解析 reference 和 Zotero 元数据的 agent 显示名称
- `agents.summaryAgentName`：负责写总结的 agent 显示名称
- `agents.coordinatorAgentName`：负责确定性写入的 agent 显示名称
- `zotero.*Env`：保存 Zotero 凭证的环境变量名
- `mineru.*`：可选本地 PDF 转换后端
- `openclaw.*`：OpenClaw 部署可选的 command-job queue 设置

不要提交 `config.json` 或 `.env`。

## 安全模型

本工作流将模型工作和确定性状态变更分开：

- reference agent 解析元数据、DOI、Zotero item key 和 PDF 附件
- summary agent 负责总结和分类
- coordinator agent 只在校验完成后执行确定性写入并报告结果
- 总结笔记通过 `scripts/write_summary_note.py` 保存
- Zotero 元数据来自 Zotero 或其他可信学术来源
- 阅读列表只通过 `scripts/reading_list.py` 写入
- PDF 附件只通过 `scripts/attach_pdf_by_doi.py` 处理
- 在 OpenClaw 中，用户可见的 MinerU 工作应通过 `scripts/queue_convert_and_notify.py` 排队
- MinerU 转换只有在 Markdown、Zotero ID 和图片链接都校验通过后才算完成

这样可以避免常见失败：agent 说已经写入或转换完成，但实际没有可用的 Obsidian 产物。

## 发布检查清单

公开发布前：

- 本地扫描真实路径、API token、平台标识符、用户 ID 和私有 agent 名称
- 保持 `config.json` 和 `.env` 不被 git 跟踪
- 运行 `python3 -m unittest discover -s tests`
- 在临时 vault 中测试，再到真实 vault 测试
- 只有在不包含私有论文笔记或用户 ID 时，才添加截图或示例输出

## License

MIT.
