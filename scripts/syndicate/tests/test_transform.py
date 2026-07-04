from syndicate.transform import (
    extract_table_sections,
    rewrite_cross_links,
    strip_shortcodes,
    table_to_bullets,
    to_portable_markdown,
)


# --- rewrite_cross_links -----------------------------------------------------


def test_rewrite_cross_links_happy_path():
    md = (
        'This post builds on '
        '[Building Reliable LLM Applications in Java]'
        '({{< ref "11-building-reliable-llm-apps-in-java.md" >}}): read that first.'
    )
    result = rewrite_cross_links(md)
    assert (
        "[Building Reliable LLM Applications in Java]"
        "(https://pg-blogs.netlify.app/posts/11-building-reliable-llm-apps-in-java/)"
        in result
    )
    assert "{{<" not in result


def test_rewrite_cross_links_no_shortcodes_unchanged():
    md = "Just a plain paragraph with a [regular link](https://example.com) in it."
    assert rewrite_cross_links(md) == md


def test_rewrite_cross_links_two_links_both_rewrite():
    md = (
        "See [post A]({{< ref \"3-java-and-the-jvm-ecosystem.md\" >}}) "
        "and also [post B]({{< ref \"4-error-handling-best-practices-in-java.md\" >}})."
    )
    result = rewrite_cross_links(md)
    assert "https://pg-blogs.netlify.app/posts/3-java-and-the-jvm-ecosystem/" in result
    assert (
        "https://pg-blogs.netlify.app/posts/4-error-handling-best-practices-in-java/"
        in result
    )
    assert "{{<" not in result


def test_rewrite_cross_links_percent_form():
    md = 'See [post]({{% ref "9-avoiding-orm-traps-and-n-plus-1-in-python.md" %}}).'
    result = rewrite_cross_links(md)
    assert (
        "https://pg-blogs.netlify.app/posts/9-avoiding-orm-traps-and-n-plus-1-in-python/"
        in result
    )
    assert "{{%" not in result


# --- strip_shortcodes ---------------------------------------------------------


def test_strip_shortcodes_removes_stray_shortcode_and_reports_it():
    md = "Some text before {{< figure src=\"x.png\" >}} and after."
    cleaned, warnings = strip_shortcodes(md)
    assert "{{<" not in cleaned
    assert "Some text before" in cleaned
    assert "and after." in cleaned
    assert len(warnings) == 1
    assert "figure" in warnings[0]


def test_strip_shortcodes_preserves_fenced_code_block():
    md = (
        "Before the block.\n\n"
        "```java\n"
        'String s = "{{< not a real shortcode >}}";\n'
        "```\n\n"
        "After the block."
    )
    cleaned, warnings = strip_shortcodes(md)
    # The fenced block must survive byte-for-byte.
    assert '"{{< not a real shortcode >}}"' in cleaned
    assert warnings == []


def test_strip_shortcodes_no_shortcodes_no_warnings():
    md = "Nothing special here, just prose."
    cleaned, warnings = strip_shortcodes(md)
    assert cleaned == md
    assert warnings == []


def test_strip_shortcodes_strips_outside_but_preserves_inside_same_doc():
    md = (
        "A stray {{< foo >}} shortcode outside.\n\n"
        "```\n"
        "keep {{< this >}} untouched\n"
        "```\n"
    )
    cleaned, warnings = strip_shortcodes(md)
    assert "keep {{< this >}} untouched" in cleaned
    assert "{{< foo >}}" not in cleaned
    assert warnings == ["{{< foo >}}"]


# --- to_portable_markdown ------------------------------------------------------


def test_to_portable_markdown_end_to_end():
    md = (
        "See [Building Reliable LLM Apps]"
        '({{< ref "10-building-reliable-llm-apps-in-python.md" >}}) for context.\n\n'
        "```python\n"
        'x = "{{< leave me alone >}}"\n'
        "```\n\n"
        "Also a stray {{< note >}} shortcode.\n"
    )
    cleaned, warnings = to_portable_markdown(md)

    assert (
        "https://pg-blogs.netlify.app/posts/10-building-reliable-llm-apps-in-python/"
        in cleaned
    )
    assert '"{{< leave me alone >}}"' in cleaned  # code block untouched
    assert "{{< note >}}" not in cleaned  # stray shortcode stripped
    assert warnings == ["{{< note >}}"]


# --- table_to_bullets ----------------------------------------------------------


def test_table_to_bullets_one_column():
    table = "| Practice |\n|----------|\n| Match model tier |\n| Cache large prefixes |"
    result = table_to_bullets(table)
    assert result == "- Match model tier\n- Cache large prefixes"
    assert "|" not in result


def test_table_to_bullets_two_columns():
    table = (
        "| Practice | Why it matters |\n"
        "|----------|----------------|\n"
        "| Match model tier to task difficulty | Don't overpay or under-provision |\n"
        "| Cache large shared prefixes | Lower cost and latency |"
    )
    result = table_to_bullets(table)
    assert result == (
        "- **Match model tier to task difficulty** — Don't overpay or under-provision\n"
        "- **Cache large shared prefixes** — Lower cost and latency"
    )
    assert "|" not in result


def test_table_to_bullets_three_columns():
    table = (
        "| Approach | Pros | Cons |\n"
        "|----------|------|------|\n"
        "| Retry | Simple | Can amplify load |"
    )
    result = table_to_bullets(table)
    assert result == "- **Retry** — Pros: Simple; Cons: Can amplify load"
    assert "|" not in result


def test_table_to_bullets_preserves_inline_formatting():
    table = (
        "| Practice | Why it matters |\n"
        "|----------|----------------|\n"
        "| Use `structured outputs` | See [docs](https://example.com) for **details** |"
    )
    result = table_to_bullets(table)
    assert "`structured outputs`" in result
    assert "[docs](https://example.com)" in result
    assert "**details**" in result
    assert result.startswith("- **Use `structured outputs`** — ")


# --- extract_table_sections -----------------------------------------------------


def test_extract_table_sections_pairs_nearest_preceding_heading():
    md = (
        "Some intro text.\n\n"
        "## Practical Checklist\n\n"
        "| Practice | Why it matters |\n"
        "|----------|----------------|\n"
        "| Match model tier | Don't overpay |\n\n"
        "Some more prose.\n"
    )
    sections = extract_table_sections(md)
    assert len(sections) == 1
    heading, table = sections[0]
    assert heading == "Practical Checklist"
    assert "Match model tier" in table


def test_extract_table_sections_returns_tables_in_document_order():
    md = (
        "## First\n\n"
        "| a |\n|---|\n| 1 |\n\n"
        "### Second\n\n"
        "| b |\n|---|\n| 2 |\n"
    )
    sections = extract_table_sections(md)
    assert [heading for heading, _ in sections] == ["First", "Second"]
    assert "| 1 |" in sections[0][1]
    assert "| 2 |" in sections[1][1]


def test_extract_table_sections_no_heading_yields_none():
    md = "| a |\n|---|\n| 1 |\n"
    sections = extract_table_sections(md)
    assert len(sections) == 1
    assert sections[0][0] is None


def test_extract_table_sections_ignores_table_inside_fenced_code_block():
    md = (
        "## Real Table\n\n"
        "| a |\n|---|\n| 1 |\n\n"
        "```\n"
        "| fake | table |\n"
        "|------|-------|\n"
        "| in a | fence |\n"
        "```\n"
    )
    sections = extract_table_sections(md)
    assert len(sections) == 1
    assert sections[0][0] == "Real Table"
    assert "1" in sections[0][1]
    assert "fake" not in sections[0][1]
