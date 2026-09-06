"""Thin LinkedIn API client ("Share on LinkedIn" — personal-profile shares).

Base `https://api.linkedin.com`, header `Authorization: Bearer $LINKEDIN_ACCESS_TOKEN`
plus `X-Restli-Protocol-Version: 2.0.0`. All HTTP goes through `self._session`
(injectable for tests) and `_request`, the single choke point that adds the
auth headers and retries on 429/5xx.

The access token is a secret: read only from the `LINKEDIN_ACCESS_TOKEN` env
var, never logged, and never included in any exception message.
"""

from __future__ import annotations

import os
import time

import requests

# Module-level indirection so tests can monkeypatch retries to no-op.
SLEEP = time.sleep

MAX_RETRIES = 3
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class LinkedInError(Exception):
    """Raised for a non-2xx LinkedIn API response. Carries status + body, but
    never the access token.
    """

    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"LinkedIn API error {status_code}: {body}")


class LinkedInClient:
    def __init__(
        self,
        access_token: str | None = None,
        session: requests.Session | None = None,
        base_url: str = "https://api.linkedin.com",
    ):
        # Falls back to the env var lazily read here (once, at construction) —
        # not re-read per call — so an explicit access_token still wins.
        self._access_token = (
            access_token if access_token is not None else os.environ.get("LINKEDIN_ACCESS_TOKEN")
        )
        self._session = session if session is not None else requests.Session()
        self._base_url = base_url.rstrip("/")

    @property
    def has_token(self) -> bool:
        """Whether an access token is configured — never exposes the token itself."""
        return bool(self._access_token)

    def _require_token(self) -> str:
        if not self._access_token:
            raise RuntimeError("LINKEDIN_ACCESS_TOKEN not set")
        return self._access_token

    def _request(self, method: str, path: str, json: dict | None = None) -> requests.Response:
        token = self._require_token()
        url = f"{self._base_url}{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Restli-Protocol-Version": "2.0.0",
        }
        if json is not None:
            headers["Content-Type"] = "application/json"

        attempt = 0
        while True:
            attempt += 1
            response = self._session.request(method, url, json=json, headers=headers)
            status = response.status_code

            if 200 <= status < 300:
                # Unlike devto, the caller needs the Response object itself —
                # ugcPosts create returns the new URN in a response *header*,
                # not the (often empty) JSON body.
                return response

            if status in RETRYABLE_STATUSES and attempt < MAX_RETRIES:
                SLEEP(2 ** (attempt - 1))
                continue

            # Non-2xx, non-retryable (or retries exhausted): surface status +
            # body, never the token.
            raise LinkedInError(status, response.text)

    def get_person_urn(self) -> str:
        """GET /v2/userinfo — parse `sub` from the OpenID Connect claims and
        return `urn:li:person:{sub}`. Requires the token to carry
        `openid profile`.
        """
        response = self._request("GET", "/v2/userinfo")
        sub = response.json().get("sub")
        if not sub:
            raise RuntimeError(
                "LinkedIn userinfo response missing 'sub' — the token likely "
                "lacks the 'openid profile' scope"
            )
        return f"urn:li:person:{sub}"

    def create_ugc_post(self, payload: dict) -> str:
        """POST /v2/ugcPosts — on success, return the share URN from the
        `X-RestLi-Id` response header (LinkedIn does not return it in the
        body).
        """
        response = self._request("POST", "/v2/ugcPosts", json=payload)
        urn = response.headers.get("X-RestLi-Id")
        if not urn:
            raise RuntimeError(
                "LinkedIn ugcPosts response missing the 'X-RestLi-Id' header "
                "— cannot determine the created share URN"
            )
        return urn
