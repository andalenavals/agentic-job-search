from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class FetchError(RuntimeError):
    pass


def fetch_json(url: str, timeout: int = 20, headers: dict[str, str] | None = None) -> object:
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
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise FetchError(f"Could not fetch {url}: {exc}") from exc
