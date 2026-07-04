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

# A `##`/`###` heading line (not `####` or deeper) — group 2 is the heading text.
_HEADING_RE = re.compile(r"^(#{2,3})(?!#)\s+(.*\S)\s*$")

# A cell that is only dashes (with optional leading/trailing `:` for GFM
# alignment markers) — used to recognize a table's separator row.
_SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")


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


def _split_table_row(line: str) -> list[str]:
    """Strip the leading/trailing `|` (if present) and whitespace, then split
    on `|` into cell strings. Inline Markdown inside a cell is left verbatim.
    """
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return len(stripped) >= 2 and stripped.startswith("|") and stripped.endswith("|")


def _is_separator_row(line: str) -> bool:
    if not _is_table_row(line):
        return False
    cells = _split_table_row(line)
    return bool(cells) and all(_SEPARATOR_CELL_RE.match(cell) for cell in cells)


def table_to_bullets(table_md: str) -> str:
    """Convert one GFM table (header row + `|---|` separator row + data rows)
    into a Medium-friendly bullet list, one bullet per data row:

    - 1 column: `- c1`
    - 2 columns: `- **c1** — c2`
    - N>2 columns: `- **c1** — <header2>: c2; <header3>: c3; ...` — using the
      header row's labels for columns 2..N.

    The separator row is ignored. Cell whitespace and the leading/trailing
    `|` are stripped; inline Markdown inside cells (bold, code, links) is
    preserved verbatim.
    """
    lines = [line for line in table_md.strip("\n").split("\n") if line.strip()]
    if len(lines) < 2:
        return ""

    header_cells = _split_table_row(lines[0])
    data_rows = [_split_table_row(line) for line in lines[2:]]
    ncols = len(header_cells)

    bullets: list[str] = []
    for row in data_rows:
        if ncols <= 1:
            bullets.append(f"- {row[0] if row else ''}")
        elif ncols == 2:
            second = row[1] if len(row) > 1 else ""
            bullets.append(f"- **{row[0]}** — {second}")
        else:
            parts = []
            for col_index in range(1, ncols):
                header_label = header_cells[col_index] if col_index < len(header_cells) else ""
                cell = row[col_index] if col_index < len(row) else ""
                parts.append(f"{header_label}: {cell}")
            bullets.append(f"- **{row[0]}** — " + "; ".join(parts))

    return "\n".join(bullets)


def extract_table_sections(body_md: str) -> list[tuple[str | None, str]]:
    """Return every Markdown table in `body_md`, in document order, paired
    with the text of its nearest preceding `##`/`###` heading (`None` if
    there is none yet). Tables inside fenced code blocks are ignored (reuses
    the `_FENCED_CODE_RE` fence-splitting approach used in `strip_shortcodes`).
    """
    sections: list[tuple[str | None, str]] = []
    current_heading: str | None = None

    parts = _FENCED_CODE_RE.split(body_md)
    for index, part in enumerate(parts):
        if index % 2 == 1:
            # Fenced code block — never scanned for headings or tables.
            continue

        lines = part.split("\n")
        i = 0
        while i < len(lines):
            heading_match = _HEADING_RE.match(lines[i])
            if heading_match:
                current_heading = heading_match.group(2).strip()
                i += 1
                continue

            if (
                _is_table_row(lines[i])
                and i + 1 < len(lines)
                and _is_separator_row(lines[i + 1])
            ):
                table_lines = [lines[i], lines[i + 1]]
                j = i + 2
                while j < len(lines) and _is_table_row(lines[j]):
                    table_lines.append(lines[j])
                    j += 1
                sections.append((current_heading, "\n".join(table_lines)))
                i = j
                continue

            i += 1

    return sections
