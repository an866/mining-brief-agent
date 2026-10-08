"""Logging setup for MCP servers and the agent.

MCP stdio transport owns stdout: the *only* thing a stdio server may write to
stdout is protocol frames. Every log record therefore goes to **stderr**, and
:func:`configure_logging` is idempotent so repeated calls from server startup
do not stack handlers.
"""

from __future__ import annotations

import logging
import os
import sys

DEFAULT_LOGGER_NAME = "mining_brief"
LOG_LEVEL_ENV_VAR = "MINING_BRIEF_LOG_LEVEL"


def configure_logging(name: str = DEFAULT_LOGGER_NAME) -> logging.Logger:
    """Return a logger writing to stderr at ``MINING_BRIEF_LOG_LEVEL`` (INFO default)."""
    level_name = os.environ.get(LOG_LEVEL_ENV_VAR, "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s [%(name)s] %(message)s"))
        logger.addHandler(handler)
    logger.propagate = False
    return logger
