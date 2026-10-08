"""Polite shared HTTP client.

Every outbound request carries an identifiable ``User-Agent`` (so operators of
the upstream sites can find us) and hard timeouts (so one slow source never
stalls a brief). Response bodies are capped in size to bound memory use when
streaming a hostile or accidentally huge resource.
"""

from __future__ import annotations

import httpx

from .errors import FetchError

USER_AGENT = "mining-brief-agent/0.1 (+https://github.com/mining-brief-agent/mining-brief-agent)"
DEFAULT_TIMEOUT_S = 15.0
DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5 MiB
PDF_MAX_BYTES = 64 * 1024 * 1024  # 64 MiB


def build_client(
    *,
    timeout: float = DEFAULT_TIMEOUT_S,
    headers: dict[str, str] | None = None,
) -> httpx.Client:
    """Build an ``httpx.Client`` with the shared defaults applied."""
    merged = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "en,zh-CN;q=0.8",
    }
    if headers:
        merged.update(headers)
    return httpx.Client(timeout=timeout, headers=merged, follow_redirects=True)


def fetch_bytes(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_S,
    max_bytes: int = DEFAULT_MAX_BYTES,
    headers: dict[str, str] | None = None,
) -> bytes:
    """GET ``url`` and return the body, capped at ``max_bytes``."""
    try:
        with (
            build_client(timeout=timeout, headers=headers) as client,
            client.stream("GET", url) as response,
        ):
            response.raise_for_status()
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise FetchError(
                        f"GET {url} exceeded the {max_bytes} byte cap; refusing to buffer further"
                    )
                chunks.append(chunk)
            return b"".join(chunks)
    except httpx.HTTPStatusError as exc:
        raise FetchError(f"GET {url} returned HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise FetchError(f"GET {url} failed: {exc}") from exc


def fetch_text(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_S,
    max_bytes: int = DEFAULT_MAX_BYTES,
    headers: dict[str, str] | None = None,
) -> str:
    """GET ``url`` and decode the body as text (httpx charset detection)."""
    body = fetch_bytes(url, timeout=timeout, max_bytes=max_bytes, headers=headers)
    return body.decode("utf-8", errors="replace")
