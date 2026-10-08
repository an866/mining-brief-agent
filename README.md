# mining-brief-agent · 矿权日报 Agent（MCP 架构）

基于 [MCP (Model Context Protocol)](https://modelcontextprotocol.io) 的「矿权日报」智能体：**3 个 MCP server + 1 个 Agent 编排客户端**，输入一句自然语言（如 *"给我生成一份关于 Pilbara 锂矿的今日简报"*），输出一份 Markdown 简报：新闻摘要 + NI 43-101 储量数据 + 价格走势 + 风险提示，且每个结论都带引用源链接。

```text
┌────────────────────────────────── mining-brief-agent ──────────────────────────────────┐
│                                                                                        │
│   用户输入: "给我生成一份关于 Pilbara 锂矿的今日简报"                                    │
│                    │                                                                   │
│                    ▼                                                                   │
│   ┌────────────────────────────┐      MCP / stdio（也可 streamable-http）              │
│   │  mining-brief (Agent CLI)  │◄──────────────────────────────┐                       │
│   │  规划 → 并行取证 → 风险规则 │                               │                       │
│   │  → 叙述(模板/Claude) → 组稿 │                               │                       │
│   └────────────┬───────────────┘                               │                       │
│                │ MCP client (stdio)                             │                       │
│      ┌─────────┼──────────────────────┬───────────────────────┐│                       │
│      ▼         ▼                      ▼                       ▼│                       │
│ ┌─────────┐ ┌──────────────────┐ ┌───────────────┐            ││                       │
│ │ mining- │ │  mineral-pdf-mcp │ │ lme-price-mcp │            ││                       │
│ │ news-mcp│ │                  │ │               │            ││                       │
│ │ search  │ │ extract_resources│ │ get_price     │            ││                       │
│ │ fetch_  │ │  (NI 43-101      │ │ get_trend     │            ││                       │
│ │ article │ │   储量表格解析)   │ │               │            ││                       │
│ └────┬────┘ └────────┬─────────┘ └──────┬────────┘            ││                       │
│      │               │                  │                     ││                       │
│  实时RSS/网页     pdfplumber 解析     实时行情/离线快照         ││                       │
│  或离线快照        + URL 缓存          双通道降级               ││                       │
└──────┼───────────────┼──────────────────┼─────────────────────┘│                       │
       ▼               ▼                  ▼                      │                       │
   mining.com /    ASX/公司公告      新浪财经 hf_/nf_             │                       │
   Google News     (NI 43-101 PDF)   行情接口                     │                       │
                                                                  │                       │
   Claude Desktop ──────────── mcp-config.json（直接挂载 3 个 server）┘                   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

> 本项目为面试题目「题 #2 — 用 MCP 协议搭一个矿权日报 Agent」的实现。需求原文：3 个 MCP server（news / NI 43-101 PDF / price）+ 1 个 client 端 Agent 编排，输出 Markdown 简报（新闻摘要 + 储量数据 + 价格走势 + 风险提示）+ 引用源链接，`mcp-config.json` 可直接接入 Claude Desktop / Cursor，`RUN.md` 5 分钟可跑。

## 快速开始（5 分钟）

### 方式一：Docker（推荐，一条命令）

```bash
docker compose run --rm agent
```

默认执行题目要求的示例查询并打印 Markdown 简报。自定义查询：

```bash
docker compose run --rm agent "给我生成一份关于 安第斯铜金矿 的今日简报"
```

### 方式二：本地 Python（3.11+）

```bash
pip install -e ".[llm]" && mining-brief "给我生成一份关于 Pilbara 锂矿的今日简报"
```

### 方式三：接入 Claude Desktop / Cursor（MCP 原生验证）

把仓库根目录的 [`mcp-config.json`](mcp-config.json) 中的 `mcpServers` 段合并进你的客户端配置（Claude Desktop: `%APPDATA%\Claude\claude_desktop_config.json`），重启客户端后即可在会话中直接调用 `search` / `fetch_article` / `extract_resources` / `get_price` / `get_trend` 五个工具。也可以用脚本自动写入（自动定位解释器、备份原配置）：

```bash
python scripts/register_mcp.py --write
```

详细步骤与离线/在线模式说明见 [RUN.md](RUN.md)。

## MCP 工具清单

| Server | 工具 | 签名 | 说明 |
| --- | --- | --- | --- |
| `mining-news-mcp` | `search` | `search(query, days=7, limit=10)` | 近 N 天矿业新闻检索（实时 RSS 或离线快照） |
| `mining-news-mcp` | `fetch_article` | `fetch_article(url)` | 抓取全文并抽取正文（readability-lite） |
| `mineral-pdf-mcp` | `extract_resources` | `extract_resources(pdf_url)` | 从 NI 43-101 PDF 抽取 Indicated/Inferred 等类别储量表（矿石量 Mt / 品位 / 金属量），附页码与证据句 |
| `lme-price-mcp` | `get_price` | `get_price(commodity, date=None)` | 指定日期价格（LME 铜/锌/镍、碳酸锂、铁矿石） |
| `lme-price-mcp` | `get_trend` | `get_trend(commodity, days=30)` | 价格走势序列 + 涨跌幅 + 方向 |

## 设计要点

- **双通道数据源，自动降级**：每个 server 支持 `live`（实时抓取）/ `snapshot`（随仓库携带的离线快照）/ `auto`（先实时、失败自动回落快照并在报告中标注）。评审环境即使无外网、或被反爬（LME 登录墙、mining.com 的 Cloudflare），`docker compose run` 也能完整跑通演示。
- **数据诚实性**：快照价格序列为*演示用合成数据*（在 `docs/data-sources.md` 中逐项声明来源与合成方式）；新闻快照为演示语料，不冒充任何真实媒体内容；实时模式抓取的才是真实数据，且报告页脚会标注本次用了哪条通道。
- **可引用的储量抽取**：`extract_resources` 的每条结果都带 PDF 页码与原文证据句（`evidence`），供报告生成 `[n]` 引用与人工复核。
- **LLM 可插拔、非必需**：默认模板叙述器（`--narrator template`）零依赖确定性生成摘要与风险提示；设置 `ANTHROPIC_API_KEY` 后可用 `--narrator anthropic` 让 Claude 撰写叙述段落（严格基于取证结果，失败自动回落模板）。
- **stdio 协议卫生**：所有 server 日志强制走 stderr，stdout 只输出 MCP 协议帧。
- **工程化**：`pyproject.toml` 统一管理（ruff / mypy strict / pytest + 覆盖率），GitHub Actions CI 在 Ubuntu + Windows 双平台跑 lint、类型检查、全量测试（含真实 stdio 子进程的端到端用例）。

## 项目结构

```text
mining-brief-agent/
├── mcp-config.json          # Claude Desktop / Cursor 直连配置
├── docker-compose.yml       # 一条命令跑通
├── src/
│   ├── mining_news_mcp/     # MCP server 1：新闻（RSS 实时 + 快照降级）
│   ├── mineral_pdf_mcp/     # MCP server 2：NI 43-101 储量抽取
│   ├── lme_price_mcp/       # MCP server 3：价格与走势
│   ├── mining_brief_agent/  # Agent 客户端（自写 ReAct 式编排 + 组稿）
│   └── mining_brief_core/   # 共享：路径 / 日志 / HTTP / 错误
├── data/
│   ├── snapshots/           # 离线快照（新闻 / 价格）
│   ├── samples/             # 演示用 NI 43-101 样例 PDF（合成）
│   └── projects.json        # 项目档案（别名 → 商品 / 新闻检索式 / 报告）
├── tests/                   # 单元 + 端到端（真实 MCP stdio 子进程）
└── docs/                    # 架构决策记录 / 数据来源声明
```

## 开发

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check .
mypy src
pytest -m "not e2e"        # 单元
pytest -m e2e              # 端到端（会拉起真实 MCP server 子进程）
```

## English Summary

`mining-brief-agent` is an MCP-based agent that generates a daily Markdown brief for a mining project: it orchestrates **three MCP servers** (mining news search/全文抓取; NI 43-101 mineral-resource PDF extraction; LME/SHFE commodity prices & trends) from a **self-written ReAct-style client** (plan → parallel evidence gathering → rule-based risk scan → narration → markdown composition). Each data server offers a live path plus a bundled offline snapshot with automatic graceful degradation, so the demo runs fully offline in 5 minutes (`docker compose run --rm agent`). All findings in the brief carry numbered source citations. Engineering: typed Python (mypy strict), ruff, pytest incl. a real-stdio end-to-end test, GitHub Actions CI on Ubuntu + Windows, Dockerized, and `mcp-config.json` ready for Claude Desktop / Cursor.

## License

MIT — see [LICENSE](LICENSE).
