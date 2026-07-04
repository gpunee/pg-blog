"""Build the Dev.to article payload from a `Post` (pure, no network).

Draft is the default: callers must pass `publish=True` explicitly to set
`published: true`. See §3a of the plan — publishing is outward-facing.
"""

from __future__ import annotations

from syndicate.posts import Post
from syndicate.tags import devto_tags
from syndicate.transform import to_portable_markdown


def build_devto_article(post: Post, publish: bool) -> dict:
    """Return the `article` payload dict for a Dev.to create/update call.

    `publish` controls `published` directly — there is no implicit default
    inside this function; callers (the CLI) are responsible for defaulting
    to `False` unless `--publish` was passed.
    """
    body_markdown, _warnings = to_portable_markdown(post.body_markdown)
    return {
        "title": post.title,
        "body_markdown": body_markdown,
        "published": publish,
        "canonical_url": post.canonical_url,
        "description": post.description,
        "tags": devto_tags(post.tags),
    }
