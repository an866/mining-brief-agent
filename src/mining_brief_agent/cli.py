"""Command-line interface for the mining brief agent."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from mining_brief_core.errors import MiningBriefError

from . import __version__
from .agent import run_brief

DEFAULT_QUERY = "给我生成一份关于 Pilbara 锂矿的今日简报"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mining-brief",
        description=(
            "生成矿权日报（Markdown）：通过 MCP stdio 调用 mining-news-mcp / "
            "mineral-pdf-mcp / lme-price-mcp 三个数据源，输出带引用源的简报。"
        ),
    )
    parser.add_argument(
        "query", nargs="?", default=DEFAULT_QUERY, help=f"自然语言查询（默认：{DEFAULT_QUERY}）"
    )
    parser.add_argument("--days", type=int, default=7, help="新闻检索窗口（天，默认 7）")
    parser.add_argument("--top-news", type=int, default=5, help="简报展示的新闻条数（默认 5）")
    parser.add_argument("--fetch-top", type=int, default=2, help="抓取全文的新闻条数（默认 2）")
    parser.add_argument(
        "--narrator",
        choices=("auto", "template", "anthropic"),
        default="auto",
        help="摘要叙述器：auto=有 Claude 凭据时用 Claude，否则模板（默认 auto）",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="离线模式：数据通道强制用仓库内置快照（演示数据）",
    )
    parser.add_argument("--output", type=Path, help="把 Markdown 报告写入指定文件")
    parser.add_argument(
        "--json", type=Path, dest="json_path", help="把取证证据包（JSON）写入指定文件"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Windows consoles often default to GBK; never crash on CJK output.
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

    try:
        result = asyncio.run(
            run_brief(
                args.query,
                days=args.days,
                top_news=args.top_news,
                fetch_top=args.fetch_top,
                narrator=args.narrator,
                offline=args.offline,
            )
        )
    except MiningBriefError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("已取消。", file=sys.stderr)
        return 130

    print(result.markdown)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(result.markdown + "\n")
        print(f"\n[Markdown 已写入 {args.output}]", file=sys.stderr)

    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        with args.json_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                json.loads(result.evidence.model_dump_json()),
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write("\n")
        print(f"[证据包已写入 {args.json_path}]", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
