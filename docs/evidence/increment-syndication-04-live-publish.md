# Evidence — Syndication Phase 5: live Dev.to publish (owner-executed, orchestrator-reconciled)

- **Date:** 2026-07-04 · **Plan:** `docs/plans/syndication.md` §5, §3a · **Base:** `bfab221` (uncommitted at time of run)
- **Executed by:** the **owner**, at runtime, with their own `DEVTO_API_KEY` exported in their shell.
  The orchestrator did **not** run the live publish — inlining the key was (correctly) blocked by the
  credential-leakage classifier, so the live step was handed off. This file records what the
  orchestrator can **independently observe** after the fact; it is a reconciliation record, not a
  captured gate transcript.

## What is independently verifiable (no key required)
- `scripts/syndicate/state.json` now maps **all 19 slugs → Dev.to article IDs** (`4067810`–`4067830`),
  where it was `{}` at the inc-02 gate. The tool writes state **only after a confirmed 2xx** on
  create (`state.py`, verified inc-02), so this is direct evidence that **19 articles were created
  successfully** on the owner's Dev.to account.
- **Token hygiene:** `grep -rn "6nN9eELX"` across all `*.py/*.md/*.json/*.sh` → **clean**; the key is
  present in no file. `.gitignore` covers `venv/` + `.env`.
- **Idempotency going forward:** because state.json is populated and about to be committed, re-runs
  will `update` these 19 articles rather than duplicate them (design §3.2).

## What is NOT independently verified here (limitation, stated plainly)
- **Draft vs. published status of each article** cannot be confirmed by the orchestrator without the
  API key (which it must not hold). Determining whether the run created drafts (`--all`, the safe
  default) or went live (`--publish`) requires either the owner's console or an authenticated
  `list_my_articles()` call the owner runs. **Owner: confirm status on https://dev.to/dashboard.**
- No live HTTP transcript was captured (the run happened outside this session).

## Follow-ups for the owner
1. **Rotate the exposed token** `6nN9eELX…` (it is in this session's plaintext chat history).
2. Confirm on the Dev.to dashboard whether the 19 are drafts or live; publish/adjust as desired.

Gate status: PASS (reconciliation — 19 successful creates evidenced via state.json; publish-status
verification delegated to the owner as noted).
