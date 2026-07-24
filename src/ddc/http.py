"""Minimal HTTP client on top of urllib — no third-party dependencies.

Every collector goes through :func:`get_json` / :func:`get_text`, which add a
polite User-Agent, timeouts, and retry with exponential backoff.  Failures are
raised as :class:`FetchError` so callers can log and continue with other
sources.
"""

from __future__ import annotations

import gzip
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

USER_AGENT = (
    "DataDrivenChemistryPapers/1.0 "
    "(https://github.com/; open scholarly metadata indexer)"
)

DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3


class FetchError(Exception):
    """Raised when a URL could not be fetched after all retries."""


def build_url(base: str, params: Optional[Dict[str, Any]] = None) -> str:
    if not params:
        return base
    query = urllib.parse.urlencode(
        {k: v for k, v in params.items() if v is not None}, doseq=True
    )
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}{query}"


def get_bytes(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> bytes:
    """GET a URL and return the response body, retrying on transient errors."""
    full_url = build_url(url, params)
    req_headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
    if headers:
        req_headers.update(headers)

    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(full_url, headers=req_headers)
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                body = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return body
        except urllib.error.HTTPError as exc:
            last_error = exc
            # 429/5xx are worth retrying; 4xx (other than 429) are not.
            if exc.code != 429 and exc.code < 500:
                raise FetchError(f"HTTP {exc.code} for {full_url}") from exc
            wait = 2.0 ** attempt
            if exc.code == 429:
                # Honor the server's Retry-After if present (capped at 2 min).
                retry_after = exc.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    wait = min(float(retry_after), 120.0)
            log.warning("HTTP %s from %s; retry %d/%d in %.0fs",
                        exc.code, full_url, attempt, retries, wait)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            wait = 2.0 ** attempt
            log.warning("Network error for %s (%s); retry %d/%d in %.0fs",
                        full_url, exc, attempt, retries, wait)
        if attempt < retries:
            time.sleep(wait)
    raise FetchError(f"Failed to fetch {full_url}: {last_error}") from last_error


def get_text(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    return get_bytes(url, params, headers, timeout).decode("utf-8", "replace")


def get_json(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Any:
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    body = get_bytes(url, params, req_headers, timeout)
    try:
        return json.loads(body)
    except ValueError as exc:
        raise FetchError(f"Invalid JSON from {url}: {exc}") from exc
