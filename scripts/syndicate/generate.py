"""Generate the Medium import checklist and per-post social teasers.

Pure functions: given `Post` objects, return Markdown strings. No network,
no filesystem writes — the CLI owns writing to `syndication/`.
"""

from __future__ import annotations

import re

from syndicate.posts import Post

MEDIUM_IMPORT_URL = "https://medium.com/p/import"

# Category -> subreddit. Every post also gets r/programming (§4 of the plan);
# AI/LLM/Agentic-tagged posts also get r/MachineLearning.
_CATEGORY_SUBREDDITS: dict[str, str] = {
    "Java": "r/java",
    "Python": "r/Python",
}
_AI_TAGS = {"AI", "LLM", "Agentic"}

_HASHTAG_STRIP_RE = re.compile(r"[^A-Za-z0-9]")
_MAX_HASHTAGS = 5


def medium_import_list(posts: list[Post]) -> str:
    """Markdown for `syndication/medium-import-list.md`: explains why Medium
    import is manual (no write API), that importing via Medium's tool sets
    the canonical back to the original (what we want for SEO), the
    step-by-step process, and a table of every post's canonical URL.
    """
    lines = [
        "# Medium Import List",
        "",
        "Medium has no write API — its publishing integration tokens were deprecated, so "
        "there is nothing to script here. Each post is imported manually via Medium's own "
        "**Import** tool instead. This is actually what we want for SEO: Medium's importer "
        "automatically sets the story's canonical URL back to the original post on "
        "`pg-blogs.netlify.app`, so the Medium copy never competes with the original in "
        "search results.",
        "",
        "## Steps (repeat for each post below)",
        "",
        f"1. Go to [{MEDIUM_IMPORT_URL}]({MEDIUM_IMPORT_URL}).",
        "2. Paste the post's canonical URL from the table below into the importer.",
        "3. Click **Import**.",
        "4. Review the imported draft — check headings, code blocks, and images render "
        "correctly.",
        "5. Click **Publish**.",
        "",
        "## Posts",
        "",
        "| # | Title | Canonical URL |",
        "| --- | --- | --- |",
    ]
    for index, post in enumerate(posts, start=1):
        lines.append(f"| {index} | {post.title} | [{post.canonical_url}]({post.canonical_url}) |")
    lines.append("")
    return "\n".join(lines)


def _hashtags(tags: list[str], limit: int = _MAX_HASHTAGS) -> list[str]:
    """Turn front-matter tags into hashtags: strip non-alphanumerics
    (`"Software Engineering"` -> `SoftwareEngineering`), dedupe (first
    occurrence wins), cap at `limit`.
    """
    result: list[str] = []
    for tag in tags:
        cleaned = _HASHTAG_STRIP_RE.sub("", tag)
        if not cleaned or cleaned in result:
            continue
        result.append(cleaned)
        if len(result) == limit:
            break
    return result


def _subreddits(post: Post) -> list[str]:
    """Map the post's category/tags to suggested subreddits: the
    category-specific subreddit(s), always `r/programming`, and
    `r/MachineLearning` when the tags suggest AI/LLM/agentic content.
    """
    result: list[str] = []
    for category in post.categories:
        mapped = _CATEGORY_SUBREDDITS.get(category)
        if mapped and mapped not in result:
            result.append(mapped)
    if "r/programming" not in result:
        result.append("r/programming")
    if any(tag in _AI_TAGS for tag in post.tags) and "r/MachineLearning" not in result:
        result.append("r/MachineLearning")
    return result


def _linkedin_hook(post: Post) -> str:
    """A 2-3 sentence professional hook derived from the post's description."""
    description = post.description.strip()
    if description and not description.endswith((".", "!", "?")):
        description += "."
    return (
        f"{description} I wrote up the patterns, trade-offs, and practices that hold up "
        f"once this hits production — including the mistakes that are easy to make and "
        f"expensive to unwind."
    )


def teaser(post: Post) -> str:
    """Markdown for `syndication/teasers/<slug>.md`: title, then a LinkedIn
    hook + hashtags, a Reddit suggestion + subreddits, and a Hacker News
    suggestion — each section carries the canonical URL.
    """
    hashtag_line = " ".join(f"#{tag}" for tag in _hashtags(post.tags))
    subreddit_line = ", ".join(_subreddits(post))

    lines = [
        f"# {post.title}",
        "",
        "## LinkedIn",
        "",
        f"{_linkedin_hook(post)} Full post: {post.canonical_url}",
        "",
        hashtag_line,
        "",
        "## Reddit",
        "",
        f"**Suggested title:** {post.title}",
        "",
        f"**Subreddits:** {subreddit_line}",
        "",
        "Reddit etiquette: post the link together with a genuine comment or summary of "
        "what's in it — don't just drop the link with no context. Low-effort "
        "self-promotion gets removed (and gets you banned from the subreddit).",
        "",
        f"Link: {post.canonical_url}",
        "",
        "## Hacker News",
        "",
        f"**Suggested title:** {post.title}",
        "",
        'Submit as a link submission (not a text post) — reserve the "Show HN" prefix for '
        "projects you've built yourself, not articles.",
        "",
        f"Link: {post.canonical_url}",
        "",
    ]
    return "\n".join(lines)
