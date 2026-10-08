# RUN — 5 分钟跑起来

三种方式任选。**方式一与方式二不需要任何 API Key**：默认的模板叙述器是确定性的，
`ANTHROPIC_API_KEY` 只影响摘要由谁撰写（Claude 或模板），不影响管线是否可跑。

---

## 方式一：Docker（推荐，一条命令）

前置：已安装并启动 Docker Desktop。

```bash
docker compose run --rm agent
```

默认执行题目要求的示例查询 *"给我生成一份关于 Pilbara 锂矿的今日简报"*，并在终端打印 Markdown 简报。

自定义查询：

```bash
docker compose run --rm agent "给我生成一份关于 安第斯铜金矿 的今日简报"
```

说明：

- 数据通道默认为 `auto`：有外网时抓实时数据；被反爬/无外网时自动回落仓库内置快照，
  并在报告页脚标注本次实际通道。想强制离线/在线：`MINING_NEWS_SOURCE=snapshot docker compose run --rm agent`。
- 首次构建会拉取 `python:3.12-slim` 并安装依赖；网络受限时可为 Docker 配置镜像加速。

## 方式二：本地 Python（≥ 3.11）

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e ".[llm]"

mining-brief --offline                    # 纯离线演示（快照数据，秒级出报告）
mining-brief "皮尔巴拉最近有什么新闻"      # 自定义查询
```

想让 Claude 撰写摘要与风险观察（可选）：

```bash
# Windows (cmd)
set ANTHROPIC_API_KEY=sk-ant-...
# macOS/Linux
export ANTHROPIC_API_KEY=sk-ant-...
mining-brief --narrator anthropic
```

未设置 Key 或调用失败时会自动回落到模板叙述器，并在报告末尾标注原因。

## 方式三：接入 Claude Desktop / Cursor（MCP 原生验证）

**自动（推荐）**：脚本会定位客户端配置、备份后合并，并写入**绝对解释器路径**
（避免客户端 PATH 找不到命令的问题）：

```bash
python scripts/register_mcp.py --write     # 加 --config 可指定 Cursor 等其他客户端配置
```

**手动**：把仓库根目录 [`mcp-config.json`](mcp-config.json) 的 `mcpServers` 段合并进：

- Claude Desktop：`%APPDATA%\Claude\claude_desktop_config.json`（Windows）/
  `~/Library/Application Support/Claude/claude_desktop_config.json`（macOS）
- Cursor：`.cursor/mcp.json`

若客户端提示找不到命令，把 `command` 换成本机 Python 的绝对路径并加 `"args": ["-m", "mining_news_mcp"]`（其余两个 server 同理）。

**验证**：重启客户端，新建会话后直接对话，例如：

> 用 search 搜一下 "Pilbara lithium" 最近 7 天的新闻，然后对第一条调用 fetch_article

三个 server 提供的工具：

| Server | 工具 |
| --- | --- |
| `mining-news` | `search(query, days=7, limit=10)`、`fetch_article(url)` |
| `mineral-pdf` | `extract_resources(pdf_url)` |
| `lme-price` | `get_price(commodity, date=None)`、`get_trend(commodity, days=30)` |

## 常用参数

| 参数 | 说明 |
| --- | --- |
| `--days N` | 新闻窗口（默认 7） |
| `--offline` | 强制快照通道（演示数据） |
| `--narrator auto\|template\|anthropic` | 摘要叙述器（默认 auto） |
| `--top-news N` / `--fetch-top N` | 简报新闻条数 / 抓取全文条数 |
| `--output report.md` | 写出 Markdown |
| `--json evidence.json` | 写出取证证据包（含每行储量证据句） |

## 环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `MINING_NEWS_SOURCE` | `auto` | `auto` / `live` / `snapshot` |
| `MINING_PRICE_SOURCE` | `auto` | 同上（走势历史始终来自快照通道） |
| `MINING_BRIEF_HOME` | 仓库根 | 数据目录定位（Docker 中为 `/app`） |
| `MINING_BRIEF_REFRESH` | — | 设为 `1` 忽略 PDF 缓存重新下载 |
| `MINING_BRIEF_LOG_LEVEL` | `INFO` | server 日志级别（stderr） |
| `MINING_BRIEF_LLM_MODEL` | `claude-opus-5` | Claude 叙述器所用模型 |
| `ANTHROPIC_API_KEY` | — | 可选；设置后 `--narrator auto` 自动用 Claude |

## 故障排查

| 症状 | 处理 |
| --- | --- |
| 报告标注"离线快照" | 属预期降级（无外网 / 上游反爬）。设 `MINING_NEWS_SOURCE=live` 可看到具体失败原因 |
| Windows 终端中文显示乱码 | 报告本身是 UTF-8；用 Windows Terminal 或 `chcp 65001`，或 `--output` 写文件查看 |
| `docker compose` 拉镜像慢 | 为 Docker Desktop 配置国内 registry mirror |
| Claude Desktop 工具列表为空 | 用 `register_mcp.py --write`（绝对路径版配置）并重启客户端 |
| 想换/新增商品或项目 | `src/lme_price_mcp/commodities.py` 的注册表、`data/projects.json` 的档案，各加一条即可 |
