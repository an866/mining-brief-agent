# 数据来源与诚实性声明（Data Sources）

本文件逐项声明每个数据通道的真实性，供评审交叉核对。原则：**任何合成数据都显式标注，
报告页脚与证据包都记录本次运行实际使用的通道**，不存在"看不出来是假数据"的路径。

## 1. 新闻（mining-news-mcp）

| 通道 | 内容 | 真实性 |
| --- | --- | --- |
| `live` | mining.com RSS (`https://www.mining.com/feed/`) + Google News RSS（按查询词） | **实时真实数据**，正文经 readability-lite 抽取 |
| `snapshot` | `data/snapshots/news.json`（22 条演示语料） | **合成演示数据**：标题均属虚构，不得归属任何真实媒体或公司；每条注明 `published_days_ago`，加载时折算为"今天 - N 天" |

- `auto`（默认）：先试 live；失败/空结果回落 snapshot，并在结果 `notes` 与报告页脚声明。
- 快照中 3 条带全文（`body`），用于离线演示 `fetch_article`；其余返回明确的"无全文"错误提示。

## 2. 价格（lme-price-mcp）

| 通道 | 内容 | 真实性 |
| --- | --- | --- |
| `live` | 新浪财经 `hq.sinajs.cn` 实时行情：LME 铜/锌/镍（`hf_CAD/hf_ZSD/hf_NID`，USD/t）、碳酸锂主力（`nf_LC0`）、铁矿石主力（`nf_I0`，CNY/t） | **实时真实数据（尽力而为）**：仅提供最新价；符号格式非新浪正式文档，解析器有录制样例测试，格式漂移会报错并回落快照 |
| `snapshot` | `data/snapshots/prices/*.json`（90 天、5 品种） | **合成演示数据**：固定种子随机游走（种子与基准价见 `scripts/build_price_snapshots.py` 的 `PARAMS`），量级参考 2025 年前后的公开水平，但不是任何真实行情 |

- 题目原始来源（LME 官方、SHFE、上海钢联）都有登录墙/授权要求，不适合放在演示仓库；
  `live` 通道的 provider 结构就是接入它们的位置（实现 `PriceProvider` 协议即可）。
- 走势（`get_trend`）的历史序列来自快照；`auto` 会把 live 的**最新价**合并到快照序列末点，
  合并行为在 `notes` 与报告页脚标注为 `snapshot+live`。

## 3. NI 43-101 资源量（mineral-pdf-mcp）

| 文档 | 真实性 |
| --- | --- |
| `data/samples/pilbara_li2o_ni43101_sample.pdf` | **合成演示文档**：由 `scripts/make_sample_pdf.py` 生成（reportlab，字节可复现），每页页脚标注 "synthetic sample, not a real NI 43-101 report" |
| `data/samples/andes_cu_au_ni43101_sample.pdf` | 同上（铜金双商品表格） |
| `data/samples/prose_resources_note_sample.pdf` | 同上（正文语句型资源量，用于测试 text 模式抽取） |

- 任意 http(s) PDF URL、file:// URI 或仓库内路径都可以作为 `pdf_url` 传入；
  非法内容（非 `%PDF` 开头）会被拒绝。远程下载缓存于 `data/cache/pdf-cache/`（已 gitignore）。

## 4. 时间与格式约定

- 线上交换的时间均为 **timezone-aware UTC**，JSON 序列化为 ISO-8601（如 `2026-10-08T12:00:00Z`）。
- 快照中的相对天数（`days_ago` / `published_days_ago`）在**加载时**折算为绝对日期，
  保证任何时候运行演示，"近 7 天"窗口都有内容。
- 报告展示层使用北京时间（UTC+8）。

## 5. 报告中的通道标注

每次生成的报告头部会写"数据通道：新闻=… ｜ 储量=… ｜ 价格=…"，取值即本次实际结果：

- `实时抓取` = live 成功；`离线快照（演示数据）` = 回落；`快照历史 + 实时最新价` = 合并；
- 任何回落都会在"运行提示与降级记录"中给出具体原因（上游 HTTP 状态、反爬等）。
