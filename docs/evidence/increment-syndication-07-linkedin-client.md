# Evidence — increment-syndication-07 · LinkedIn L2 (`LinkedInClient`)

> Plan `docs/plans/linkedin-syndication.md` §4.1: **07 = L2**. Continues the `increment-syndication-*` series.

- **Date:** 2026-07-26
- **Plan:** `docs/plans/linkedin-syndication.md` (Status: APPROVED) — Increment L2
- **Base commit:** `4c429ee` (working tree; L1+L2 changes uncommitted — deploy/commit is a separate owner-authorized step)
- **Model:** implementer = Sonnet; orchestrator re-ran the gate and read both files independently.

## Delivered
- `scripts/syndicate/linkedin.py` (new) — `LinkedInError(status_code, body)` (message = status+body, **never** the token) and `LinkedInClient`, modeled on `DevToClient`:
  - env-only token (`LINKEDIN_ACCESS_TOKEN`, read once at construction; explicit arg wins); `has_token` property; `_require_token()` (message carries no token value).
  - `_request(method, path, json=None) -> requests.Response` — single choke point; headers `Authorization: Bearer …`, `X-Restli-Protocol-Version: 2.0.0`, `Content-Type: application/json` only when a JSON body is sent; devto's exact retry loop (`SLEEP`, `MAX_RETRIES=3`, `RETRYABLE_STATUSES={429,500,502,503,504}`). **Returns the raw `Response`** on 2xx (the plan's key divergence — the create path needs a response *header*).
  - `get_person_urn() -> str` — `GET /v2/userinfo` → `urn:li:person:{sub}`; clear error if `sub` absent.
  - `create_ugc_post(payload) -> str` — `POST /v2/ugcPosts`; returns the URN from the **`X-RestLi-Id` response header**; clear error if that header is absent.
- `scripts/syndicate/tests/test_linkedin.py` (new) — 12 mock-network tests; `FakeResponse` carries a `headers` dict.

## Gate (orchestrator's own run — independent of the subagent report)
1. **Full suite:** `cd scripts/syndicate && ./venv/bin/pytest -q` → **`94 passed in 0.45s`** (82 pre-existing incl. L1 + 12 new). New file alone: `pytest -q tests/test_linkedin.py` → `12 passed`.
2. **Acceptance (plan §4 L2 / §3.2), verified by reading code + tests:**
   - token-not-set → `RuntimeError` naming `LINKEDIN_ACCESS_TOKEN`, no token value; `has_token` True/False by config.
   - **token redaction genuinely asserted** — `test_linkedin_error_never_includes_the_access_token` seeds a known secret, forces a 400, asserts `secret not in str(err)` and `"400" in str(err)`.
   - `_request` sends `Authorization: Bearer <token>` + `X-Restli-Protocol-Version: 2.0.0`; `Content-Type` present on POST, **omitted on GET** (paired tests).
   - retry: 429→201 succeeds (2 calls); 503×3 exhausted → `LinkedInError` (3 calls); 422 → `LinkedInError`, **no** retry (1 call). `SLEEP` monkeypatched to no-op.
   - `create_ugc_post` POSTs to `/v2/ugcPosts`, returns URN from `X-RestLi-Id` header; missing header → clear `RuntimeError` naming the header.
   - `get_person_urn` builds `urn:li:person:{sub}` from mocked userinfo (`GET /v2/userinfo`); missing `sub` → clear `RuntimeError`.
   - **Zero live network** — every test uses `FakeSession`/`ExplodingSession`; `ExplodingSession.request` fails the test if ever called.
3. **Additive-only proof (repo root, correct pathspec):** `git status --porcelain` shows only `M generate.py` / `M payload.py` (L1, +63/-0) as tracked changes; `linkedin.py`, `test_linkedin.py`, `test_linkedin_payload.py` are `??` untracked-new; `git check-ignore` confirms `linkedin.py`/`test_linkedin.py` are **not** gitignored. No existing tracked file beyond L1's two was modified → `devto`/`medium`/`teasers` provably untouched; their tests stay green in the 94.
4. **Static checks:** no ruff/black/mypy/CI configured for this subproject (re-confirmed) — pytest is the whole gate, consistent with prior `syndicate` increments; both files parse and match neighbor line-length conventions.

## Grounding
- Endpoint, `X-Restli-Protocol-Version: 2.0.0`, `X-RestLi-Id`-header result, and `/v2/userinfo`→`sub` are the plan §3.4 rows the planner verified against Microsoft Learn "Share on LinkedIn" (2026-07-26). No API shape from memory.

## Deviations / judgment calls
1. **Error type for malformed-success cases:** missing `sub` (userinfo) and missing `X-RestLi-Id` (create) raise **`RuntimeError`**, not `LinkedInError`. Plan §3.2 allowed "`LinkedInError`/clear error"; `RuntimeError` is semantically apt — these are local-data/parse failures on an otherwise-2xx response, so `LinkedInError`'s `(status, body)` shape doesn't fit. **Recorded as an as-built note in the plan (§3.2 + §3.5) via plan-sync**, because it has a downstream L3 consequence: the per-post live loop must treat **both** `LinkedInError` (non-2xx) **and** this `RuntimeError` (malformed 201) as a failed post so a single bad response can't abort the batch.
2. Two tests beyond the enumerated minimum (`Content-Type` omitted on GET; headers captured on the create path) — both verify already-specified §3.2 behavior; not scope creep.

## Gate status: PASS
Next: Increment L3 (`increment-syndication-08`) — `linkedin` CLI subcommand, idempotency state, sidecar wiring, README.
