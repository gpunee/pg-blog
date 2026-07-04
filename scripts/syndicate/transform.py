"""Pure functions that turn Hugo Markdown into platform-portable Markdown.

No network, no filesystem access — pure string transforms.
"""

from __future__ import annotations

import re

CANONICAL_BASE = "https://pg-blogs.netlify.app/posts"

# {{< ref "NN-name.md" >}}  or  {{% ref "NN-name.md" %}}  (optional whitespace
# inside the {{ }} delimiters, around `ref`, and around the quoted filename).
_CROSS_LINK_RE = re.compile(
    r'\{\{<\s*ref\s+"([^"]+?)\.md"\s*>\}\}'
    r'|'
    r'\{\{%\s*ref\s+"([^"]+?)\.md"\s*%\}\}'
)

# Any remaining {{< ... >}} or {{% ... %}} shortcode, non-greedy so adjacent
# shortcodes on the same line don't get merged into one match.
_SHORTCODE_RE = re.compile(r"\{\{<.*?>\}\}|\{\{%.*?%\}\}", re.DOTALL)

# Fenced code blocks (```...``` including an optional language tag), so we can
# leave them byte-for-byte untouched when stripping shortcodes. Capturing
# group so re.split() keeps the matched fences in the result.
_FENCED_CODE_RE = re.compile(r"(```.*?```)", re.DOTALL)


def rewrite_cross_links(md: str) -> str:
    """Replace `{{< ref "NN-name.md" >}}` / `{{% ref "NN-name.md" %}}` shortcodes
    (as used inside Markdown links) with the absolute canonical URL of the
    referenced post.
    """

    def _replace(match: re.Match[str]) -> str:
        filename = match.group(1) or match.group(2)
        return f"{CANONICAL_BASE}/{filename}/"

    return _CROSS_LINK_RE.sub(_replace, md)


def strip_shortcodes(md: str) -> tuple[str, list[str]]:
    """Remove any remaining `{{< ... >}}` / `{{% ... %}}` shortcodes, leaving
    fenced code blocks completely untouched.

    Returns `(cleaned_markdown, warnings)` where `warnings` is the list of
    shortcode strings that were stripped (empty if none were found).
    """
    warnings: list[str] = []

    def _clean_segment(segment: str) -> str:
        def _collect(match: re.Match[str]) -> str:
            warnings.append(match.group(0))
            return ""

        return _SHORTCODE_RE.sub(_collect, segment)

    # Split the text so fenced code blocks are preserved verbatim: every other
    # element of the split (odd indices) is a fenced block, matching the
    # capturing group order of re.split.
    parts = _FENCED_CODE_RE.split(md)

    cleaned_parts = []
    for index, part in enumerate(parts):
        if index % 2 == 1:
            # Fenced code block — pass through byte-for-byte.
            cleaned_parts.append(part)
        else:
            cleaned_parts.append(_clean_segment(part))

    return "".join(cleaned_parts), warnings


def to_portable_markdown(md: str) -> tuple[str, list[str]]:
    """Run `rewrite_cross_links` then `strip_shortcodes`, returning the
    cleaned Markdown and any warnings about shortcodes that had to be
    forcibly stripped.
    """
    rewritten = rewrite_cross_links(md)
    return strip_shortcodes(rewritten)
