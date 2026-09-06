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


def build_linkedin_share(
    post: Post, author_urn: str, commentary: str, visibility: str = "PUBLIC"
) -> dict:
    """Return the `ugcPosts` ARTICLE-share payload dict for a LinkedIn create call.

    `commentary` is the already-resolved human text (see
    `generate.resolve_linkedin_commentary`) — it must NOT already contain the
    canonical link. This function always appends `post.canonical_url` to the
    commentary and sets the ARTICLE preview card, so the caller never has to
    think about the link or the card.
    """
    text = f"{commentary.rstrip()}\n\n{post.canonical_url}"
    return {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "ARTICLE",
                "media": [
                    {
                        "status": "READY",
                        "originalUrl": post.canonical_url,
                        "title": {"text": post.title},
                        "description": {"text": post.description},
                    }
                ],
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": visibility},
    }
