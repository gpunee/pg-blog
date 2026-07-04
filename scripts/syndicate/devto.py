"""Thin Dev.to API client.

Base `https://dev.to/api`, header `api-key: $DEVTO_API_KEY`. All HTTP goes
through `self._session` (injectable for tests) and `_request`, the single
choke point that adds the auth header and retries on 429/5xx.

The API key is a secret: read only from the `DEVTO_API_KEY` env var, never
logged, and never included in any exception message.
"""

from __future__ import annotations

import os
import time

import requests

# Module-level indirection so tests can monkeypatch retries to no-op.
SLEEP = time.sleep

MAX_RETRIES = 3
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class DevToError(Exception):
    """Raised for a non-2xx Dev.to API response. Carries status + body, but
    never the API key.
    """

    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Dev.to API error {status_code}: {body}")


class DevToClient:
    def __init__(
        self,
        api_key: str | None = None,
        session: requests.Session | None = None,
        base_url: str = "https://dev.to/api",
    ):
        # Falls back to the env var lazily read here (once, at construction) —
        # not re-read per call — so an explicit api_key still wins.
        self._api_key = api_key if api_key is not None else os.environ.get("DEVTO_API_KEY")
        self._session = session if session is not None else requests.Session()
        self._base_url = base_url.rstrip("/")

    @property
    def has_key(self) -> bool:
        """Whether an API key is configured — never exposes the key itself."""
        return bool(self._api_key)

    def _require_key(self) -> str:
        if not self._api_key:
            raise RuntimeError("DEVTO_API_KEY not set")
        return self._api_key

    def _request(self, method: str, path: str, json: dict | None = None) -> dict:
        api_key = self._require_key()
        url = f"{self._base_url}{path}"
        headers = {"api-key": api_key}

        attempt = 0
        while True:
            attempt += 1
            response = self._session.request(method, url, json=json, headers=headers)
            status = response.status_code

            if 200 <= status < 300:
                return response.json()

            if status in RETRYABLE_STATUSES and attempt < MAX_RETRIES:
                SLEEP(2 ** (attempt - 1))
                continue

            # Non-2xx, non-retryable (or retries exhausted): surface status +
            # body, never the key.
            raise DevToError(status, response.text)

    def list_my_articles(self) -> list[dict]:
        """GET /articles/me/all — the account's own articles (all statuses).
        Single page is sufficient at this scale (per_page=1000 covers it).
        """
        return self._request("GET", "/articles/me/all?per_page=1000")

    def create_article(self, article: dict) -> dict:
        """POST /articles — body `{"article": article}`."""
        return self._request("POST", "/articles", json={"article": article})

    def update_article(self, article_id: int, article: dict) -> dict:
        """PUT /articles/{id} — body `{"article": article}`."""
        return self._request("PUT", f"/articles/{article_id}", json={"article": article})
