from __future__ import annotations

import json
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen


class FetchError(RuntimeError):
    pass


def fetch_json(url: str, timeout: int = 20, headers: dict[str, str] | None = None) -> object:
    try:
        return json.loads(fetch_text(url, timeout, headers))
    except json.JSONDecodeError as exc:
        raise FetchError(f"Could not parse JSON from {url}: {exc}") from exc


def fetch_text(url: str, timeout: int = 20, headers: dict[str, str] | None = None) -> str:
    return fetch_text_with_opener(url, timeout, headers)


def fetch_text_with_cookies(
    url: str,
    timeout: int = 20,
    headers: dict[str, str] | None = None,
) -> str:
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    return fetch_text_with_opener(url, timeout, headers, opener.open)


def fetch_text_with_opener(
    url: str,
    timeout: int = 20,
    headers: dict[str, str] | None = None,
    open_url=urlopen,
) -> str:
    request_headers = {
        "Accept": "application/json",
        "User-Agent": "agentic-job-search/0.1 (+https://github.com/andalenavals/agentic-job-search)",
    }
    if headers:
        request_headers.update(headers)
    request = Request(
        url,
        headers=request_headers,
    )
    try:
        with open_url(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise FetchError(f"Could not fetch {url}: {exc}") from exc
