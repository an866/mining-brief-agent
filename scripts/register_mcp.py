"""Register the three MCP servers with Claude Desktop (or Cursor).

Why a script: ``mcp-config.json`` uses bare console-script names, which only
resolve when the interpreter's Scripts/bin directory is on the client app's
PATH. This script writes entries that use **this** interpreter
(``sys.executable -m <module>``), so the config works regardless of PATH
scoping — and it merges instead of overwriting, with a timestamped backup.

Usage::

    python scripts/register_mcp.py            # dry run: show what would change
    python scripts/register_mcp.py --write    # back up + merge into the config
    python scripts/register_mcp.py --config path/to/mcp.json --write
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

SERVER_MODULES = {
    "mining-news": ("mining_news_mcp", {"MINING_NEWS_SOURCE": "auto"}),
    "mineral-pdf": ("mineral_pdf_mcp", {}),
    "lme-price": ("lme_price_mcp", {"MINING_PRICE_SOURCE": "auto"}),
}


def default_config_path() -> Path | None:
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    return None


def build_entries(python: str) -> dict[str, dict]:
    entries: dict[str, dict] = {}
    for name, (module, env) in SERVER_MODULES.items():
        entry: dict = {"command": python, "args": ["-m", module]}
        if env:
            entry["env"] = dict(env)
        entries[name] = entry
    return entries


def merge_config(existing: dict, entries: dict[str, dict]) -> dict:
    merged = dict(existing)
    servers = dict(merged.get("mcpServers") or {})
    servers.update(entries)
    merged["mcpServers"] = servers
    return merged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, help="target client config (default: Claude Desktop)")
    parser.add_argument("--write", action="store_true", help="actually write (default: dry run)")
    args = parser.parse_args(argv)

    config_path = args.config or default_config_path()
    if config_path is None:
        print(
            "无法自动定位 Claude Desktop 配置（此平台未知），请用 --config 指定路径。",
            file=sys.stderr,
        )
        return 2

    entries = build_entries(sys.executable)
    existing: dict = {}
    if config_path.is_file():
        try:
            existing = json.loads(config_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            print(f"配置文件不是合法 JSON，拒绝改动：{config_path}（{exc}）", file=sys.stderr)
            return 1
    merged = merge_config(existing, entries)

    print(f"目标配置：{config_path}")
    print(json.dumps({"mcpServers": entries}, ensure_ascii=False, indent=2))

    if not args.write:
        print("（dry-run；加 --write 执行写入）")
        return 0

    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.is_file():
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup = config_path.with_suffix(config_path.suffix + f".bak-{stamp}")
        shutil.copy2(config_path, backup)
        print(f"已备份原配置：{backup}")
    config_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("已写入。重启 Claude Desktop / Cursor 后生效。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
