# Evidence — Syndication Increment 02: Dev.to publisher (CLI, idempotent, gated)

- **Date:** 2026-07-04 · **Plan:** `docs/plans/syndication.md` §3.1/3.2/3a/4.1 (APPROVED) · **Base:** `bfab221` (uncommitted)
- **Implementer:** Sonnet subagent; **orchestrator independently re-ran suite + real dry-run + key checks.**

## Created (`scripts/syndicate/`)
- `devto.py` (`DevToClient`: key from `DEVTO_API_KEY` env only, `_request` choke point w/ 429/5xx retry, `DevToError` carrying status+body but **never the key**), `state.py` (atomic slug→id map), `payload.py` (pure `build_devto_article`), `cli.py` (`devto` subcommand), `__main__.py`, `state.json` (`{}`), `requests` added to requirements.
- Tests: `test_payload.py`, `test_devto.py`, `test_cli.py` — all HTTP mocked, no live calls.

## Acceptance (orchestrator's own run)
- `./venv/bin/pytest -q` → **47 passed** (incl. inc-01).
- **Dry-run, no key, all 19:** prints every intended payload, **"0 network calls made"**, no crash on empty key; 19 post lines; **0 shortcode leaks** in payloads.
- **Paired ON/OFF (feature gate):** dry-run without `--publish` → `published=False`; with `--publish` → `published=True`.
- **Idempotency** (mocked): state-id → `update`; canonical-match fallback → `update` with matched id; neither → `create` + id saved after 2xx.
- **Secret handling:** key never interpolated into output (source grep clean); `DevToError` excludes the key (explicit test); missing key → `RuntimeError` naming the var, no value.

## Deviations (reviewed & accepted)
- `python -m syndicate` must run with cwd = `scripts/` (parent of the package) — matches pytest's package anchor; no source change needed. **Follow-up:** add a repo-root convenience wrapper in inc 03.
- `state.json` created empty (committable; populated on first live run).
- Added `DevToClient.has_key` for fail-fast UX (doesn't change the secret contract).
- No lint/type tooling (not installed); pytest + smoke are the gate.

Gate status: PASS. Syndication increment 03 may start.
