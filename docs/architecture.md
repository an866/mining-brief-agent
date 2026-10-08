# 架构说明与决策记录（Architecture）

## 命题与目标

面试题 #2 要求：3 个 MCP server（news / NI 43-101 PDF / price）+ 1 个 Agent 客户端，
输入自然语言生成 Markdown 矿权日报（新闻摘要 + 储量数据 + 价格走势 + 风险提示）+ 引用源链接；
`mcp-config.json` 可直接接入 Claude Desktop / Cursor；5 分钟内可跑（含一条 docker-compose）。

## 运行序列（run_brief）

```text
用户查询 "给我生成一份关于 Pilbara 锂矿的今日简报"
    │
    ▼  planning.resolve_query —— 别名匹配（data/projects.json）→ 项目 + 商品 + 新闻检索式
    │
    ▼  ServerHub（stdio，三个子进程）        ┌─ mining-news:  search ──► 快照/实时
    │   ── 并行 gather ──                    ├─ mineral-pdf: extract_resources（缓存+%PDF 校验）
    │                                        └─ lme-price:   get_trend × N 商品
    │        （单项失败 → 标记 error 通道 + warnings，不阻断）
    │
    ▼  fetch_article（top-k 全文，失败仅记 warning）
    │
    ▼  composer.build_citations —— 全部来源分配稳定 [n] 编号（先于叙述）
    ▼  agent._derive_risks —— 规则扫描（价格阈值 / Inferred 占比 / 关键词 / 通道披露）
    ▼  narrate —— TemplateNarrator（默认）或 AnthropicNarrator（claude-opus-5，
    │             严格引用约束；任何失败回落模板并把原因写进 mode）
    ▼  composer.compose —— 分节 Markdown + 引用清单 + 页脚通道说明 + 免责声明
```

## 关键决策

1. **Python + MCP SDK 2.x（`mcp.server.mcpserver.MCPServer`）**。选 Python 因为
   pdfplumber 的表格抽取远强于 JS 生态；选当前 2.x SDK 顺带验证了同步工具函数会被
   SDK 自动放线程池执行（`anyio.to_thread.run_sync`），stdio 事件循环保持可并发。
2. **工具错误映射为 `ToolError`**：SDK 会把未识别异常脱敏（"nothing from an
   unexpected exception reaches the client"），所以每个工具显式捕获领域异常并转成
   `ToolError`，客户端能看到可行动的错误文本。
3. **双通道数据源 + 显式降级**（`auto|live|snapshot`）：演示/评审环境不可控
   （反爬、登录墙、无外网），因此每个 server 内置仓库快照作为可达性下限；所有降级
   都记录在结果 `notes` → 证据包 → 报告页脚。**不存在静默假数据**（见 data-sources.md）。
4. **引用先行**：`build_citations` 在叙述之前分配 `[n]`，叙述器（模板或 Claude）与
   组稿器共享同一编号空间；Claude 提示词被严格约束"只能使用提供的证据并标注编号"，
   模板叙述器本身就是从证据推导的确定性函数。
5. **LLM 可插拔、非必需**：模板叙述器保证零依赖可跑；`AnthropicNarrator` 是增强项，
   带服务端 refusal fallback（`server-side-fallback-2026-07-01`），并在任何异常
   （无 SDK、无凭据、API 错误、输出不合格式）时回落到模板且注明原因。
6. **单项失败不拖垮全局**：`asyncio.gather(return_exceptions=True)` + per-source
   error 通道；新闻挂了仍有价格与储量章节，反之亦然。
7. **数据模型单一事实源**：server 的 pydantic 模型直接作为 wire schema；agent 反序列化
   时复用同一模型类（`SearchResult.model_validate(...)`），schema 只有一处定义。
8. **stdio 协议卫生**：全部日志强制 stderr（stdout 只允许协议帧）；这是 stdio MCP
   server 最容易踩的坑，shared `logging_setup` 统一处理。
9. **可复现演示数据**：价格快照（固定种子）与样例 PDF（reportlab `invariant=1`，
   LF 换行）字节可复现；快照用相对天数存储、加载时折算，任何日期运行演示窗口都成立。

## 目录职责

| 路径 | 职责 |
| --- | --- |
| `src/mining_brief_core` | 跨包共享：路径解析 / stderr 日志 / 礼貌 HTTP（UA+超时+字节上限）/ 异常层级 |
| `src/mining_news_mcp` | 新闻 server：RSS 实时 + 快照；readability-lite 抽取 |
| `src/mineral_pdf_mcp` | PDF server：表格/正文双策略抽取 NI 43-101 资源量；URL 缓存与校验 |
| `src/lme_price_mcp` | 价格 server：商品注册表（中英别名）、新浪行情、走势分析、unicode 迷你图 |
| `src/mining_brief_agent` | Agent：规划 / MCP 客户端枢纽 / 风险规则 / 叙述 / 组稿 / CLI |
| `data/` | 演示快照、样例 PDF、项目档案（见 data-sources.md） |
| `scripts/` | 样例 PDF 生成、价格快照生成、客户端配置注册（均幂等） |
| `tests/` | 单元 + 真实 stdio 端到端（离线确定性） |

## 已知边界

- 新浪行情仅提供最新价，走势历史来自快照；接入付费源（LME/钢联）需实现
  `PriceProvider` 协议的 `get_series`。
- 储量抽取覆盖常见 NI 43-101 表格形态与正文语句；跨页表头、合并单元格等复杂版式
  会降级为警告（不猜测）。
- 新闻检索依赖上游 RSS 可用性；Google News 在部分网络环境不可达（自动降级已覆盖）。
