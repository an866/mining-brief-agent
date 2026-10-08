"""MCP client hub: spawn the three servers over stdio and call their tools.

The agent is a *client*: it never imports the server packages' logic, it
speaks MCP. Servers are launched as subprocesses (``python -m <module>``)
using the same interpreter that runs the agent, with per-run environment
overrides (this is how ``--offline`` pins the data channels to snapshots).
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

from mining_brief_core.errors import MiningBriefError

NEWS_SERVER = "mining-news"
PDF_SERVER = "mineral-pdf"
PRICE_SERVER = "lme-price"


class AgentToolError(MiningBriefError):
    """An MCP tool call failed (transport error or tool-reported error)."""


@dataclass(frozen=True)
class ServerSpec:
    name: str
    module: str


SERVERS: tuple[ServerSpec, ...] = (
    ServerSpec(NEWS_SERVER, "mining_news_mcp"),
    ServerSpec(PDF_SERVER, "mineral_pdf_mcp"),
    ServerSpec(PRICE_SERVER, "lme_price_mcp"),
)


def _result_text(result: Any) -> str:
    for block in getattr(result, "content", None) or []:
        if isinstance(block, TextContent):
            return block.text
    return ""


class ServerHub:
    """Owns one MCP session per server for the duration of a brief run."""

    def __init__(
        self,
        *,
        env_overrides: dict[str, str] | None = None,
        python_executable: str | None = None,
    ) -> None:
        self._env_overrides = dict(env_overrides or {})
        self._python = python_executable or sys.executable
        self._stack: AsyncExitStack | None = None
        self._sessions: dict[str, ClientSession] = {}

    async def __aenter__(self) -> ServerHub:
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        env = {**os.environ, **self._env_overrides}
        try:
            for spec in SERVERS:
                params = StdioServerParameters(
                    command=self._python,
                    args=["-m", spec.module],
                    env=env,
                )
                read_stream, write_stream = await self._stack.enter_async_context(
                    stdio_client(params)
                )
                session = await self._stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
                await session.initialize()
                self._sessions[spec.name] = session
        except BaseException:
            await self._stack.aclose()
            self._stack = None
            raise
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None

    async def call_tool(self, server: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call ``tool`` on ``server`` and return its structured result as a dict."""
        session = self._sessions.get(server)
        if session is None:
            raise AgentToolError(f"MCP server {server!r} is not connected")
        try:
            result = await session.call_tool(tool, arguments)
        except Exception as exc:
            raise AgentToolError(f"{server}.{tool} transport error: {exc}") from exc

        if getattr(result, "is_error", False):
            raise AgentToolError(f"{server}.{tool} failed: {_result_text(result)}")

        structured = getattr(result, "structured_content", None)
        if isinstance(structured, dict) and structured:
            return structured

        text = _result_text(result)
        try:
            parsed = json.loads(text)
        except ValueError as exc:
            raise AgentToolError(f"{server}.{tool} returned a non-JSON payload") from exc
        if not isinstance(parsed, dict):
            raise AgentToolError(f"{server}.{tool} returned a non-object payload")
        return parsed
