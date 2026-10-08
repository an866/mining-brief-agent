"""Shared exception hierarchy.

All errors raised by the packages derive from :class:`MiningBriefError` so
callers can catch one type for the whole family. MCP server tools never let
these propagate as tracebacks: they translate them into structured error
payloads (see each server's ``server.py``).
"""

from __future__ import annotations


class MiningBriefError(Exception):
    """Base class for all application errors."""


class FetchError(MiningBriefError):
    """A remote resource (page, feed, PDF) could not be fetched."""


class ProviderError(MiningBriefError):
    """A data provider failed, is misconfigured, or returned unusable data."""


class DataNotFoundError(MiningBriefError):
    """A requested commodity, project, or dataset does not exist."""
