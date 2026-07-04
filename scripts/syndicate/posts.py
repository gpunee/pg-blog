"""Load Hugo blog posts and expose them as plain-data `Post` objects.

Pure/local-filesystem only: no network, no writes to `content/`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import frontmatter

CANONICAL_BASE = "https://pg-blogs.netlify.app/posts"

_LEADING_NUMBER_RE = re.compile(r"^(\d+)-")


@dataclass
class Post:
    slug: str
    title: str
    description: str
    tags: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    canonical_url: str = ""
    body_markdown: str = ""


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from `start` (default: this file's directory) until a directory
    containing `hugo.toml` is found. Raises FileNotFoundError if none is found.
    """
    current = (start or Path(__file__).parent).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "hugo.toml").is_file():
            return candidate
    raise FileNotFoundError(
        f"Could not find repo root (no hugo.toml found walking up from {current})"
    )


def _sort_key(path: Path) -> tuple[int, str]:
    match = _LEADING_NUMBER_RE.match(path.stem)
    if match:
        return (int(match.group(1)), path.stem)
    # Files without a numeric prefix sort after numbered ones, alphabetically.
    return (float("inf"), path.stem)


def load_posts(content_dir: str = "content/posts") -> list[Post]:
    """Load all published posts from `content_dir` (resolved relative to the
    repo root), sorted by the numeric filename prefix.

    Skips `search.md` and any post with `draft: true` in its front matter.
    """
    repo_root = find_repo_root()
    posts_dir = repo_root / content_dir

    md_paths = sorted(posts_dir.glob("*.md"), key=_sort_key)

    posts: list[Post] = []
    for path in md_paths:
        if path.name == "search.md":
            continue

        parsed = frontmatter.load(path)
        if parsed.metadata.get("draft") is True:
            continue

        slug = path.stem
        title = parsed.metadata.get("title", "")
        description = parsed.metadata.get("description", "")
        tags = list(parsed.metadata.get("tags", []) or [])
        categories = list(parsed.metadata.get("categories", []) or [])
        canonical_url = f"{CANONICAL_BASE}/{slug}/"

        posts.append(
            Post(
                slug=slug,
                title=title,
                description=description,
                tags=tags,
                categories=categories,
                canonical_url=canonical_url,
                body_markdown=parsed.content,
            )
        )

    return posts
