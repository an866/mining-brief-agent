"""Resolve a PDF from an http(s) URL, a file:// URI, or a local path.

Remote PDFs are cached under ``data/cache/pdf-cache/`` keyed by a hash of the
URL, so repeated extraction during a demo run never re-downloads. Cached files
are re-validated against the ``%PDF`` magic header — a truncated cache entry or
an HTML error page must never be handed to the parser.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from mining_brief_core.errors import FetchError
from mining_brief_core.http import PDF_MAX_BYTES, fetch_bytes
from mining_brief_core.paths import cache_dir, project_root

_PDF_MAGIC = b"%PDF"
CACHE_SUBDIR = "pdf-cache"
REFRESH_ENV_VAR = "MINING_BRIEF_REFRESH"


def _cache_path_for(url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    directory = cache_dir() / CACHE_SUBDIR
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{digest}.pdf"


def _validate_pdf_bytes(payload: bytes, origin: str) -> None:
    if not payload.startswith(_PDF_MAGIC):
        raise FetchError(
            f"{origin} did not return a PDF (missing %PDF header — got {payload[:16]!r}...)"
        )


def resolve_pdf_source(uri: str) -> tuple[Path, bool]:
    """Return ``(local_path, downloaded)`` for the given URI.

    Raises :class:`FetchError` if the resource cannot be fetched or is not a PDF.
    """
    parsed = urlparse(uri)

    if parsed.scheme in ("http", "https"):
        cache_path = _cache_path_for(uri)
        refresh = os.environ.get(REFRESH_ENV_VAR) == "1"
        if cache_path.is_file() and not refresh:
            cached = cache_path.read_bytes()
            try:
                _validate_pdf_bytes(cached, uri)
                return cache_path, False
            except FetchError:
                cache_path.unlink(missing_ok=True)  # corrupt cache entry; re-download
        payload = fetch_bytes(uri, timeout=30.0, max_bytes=PDF_MAX_BYTES)
        _validate_pdf_bytes(payload, uri)
        cache_path.write_bytes(payload)
        return cache_path, True

    if parsed.scheme == "file":
        path = (
            Path(unquote(parsed.path.lstrip("/")))
            if os.name == "nt"
            else Path(unquote(parsed.path))
        )
        return _validate_local(path, uri)

    if parsed.scheme and len(parsed.scheme) > 1:
        raise FetchError(
            f"unsupported URI scheme {parsed.scheme!r} (use http(s), file://, or a path)"
        )

    # Bare path: absolute, or relative to the project root (so data/samples/... works
    # regardless of the process working directory).
    candidate = Path(uri)
    if not candidate.is_absolute():
        candidate = project_root() / candidate
    return _validate_local(candidate, uri)


def _validate_local(path: Path, origin: str) -> tuple[Path, bool]:
    if not path.is_file():
        raise FetchError(f"local PDF not found: {path} (from {origin!r})")
    with path.open("rb") as handle:
        header = handle.read(8)
    _validate_pdf_bytes(header, str(path))
    return path, False
