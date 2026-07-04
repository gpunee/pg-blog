"""Load/save the syndication state map (`slug -> devto_article_id`).

Contains only public Dev.to article IDs, no secrets. Committed so idempotency
survives across machines (§3.2 of the plan).
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def load_state(path: str | Path) -> dict:
    """Return the slug -> devto_article_id map, or `{}` if the file is
    missing or unreadable.
    """
    path = Path(path)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(path: str | Path, state: dict) -> None:
    """Write `state` to `path` atomically (temp file + rename) so a crash
    mid-write never corrupts the committed state file.
    """
    path = Path(path)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    os.replace(tmp_path, path)
