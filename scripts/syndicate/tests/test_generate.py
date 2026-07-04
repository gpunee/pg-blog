from syndicate.generate import medium_checklist_snippets, medium_import_list, teaser
from syndicate.posts import Post


def _java_post(**overrides) -> Post:
    defaults = dict(
        slug="16-testing-best-practices-in-java",
        title="Testing Best Practices in Java",
        description="Testing at the right level with JUnit 5 and Mockito.",
        tags=["Java", "Testing", "JUnit", "Software Engineering"],
        categories=["Java"],
        canonical_url="https://pg-blogs.netlify.app/posts/16-testing-best-practices-in-java/",
        body_markdown="Body.",
    )
    defaults.update(overrides)
    return Post(**defaults)


def _python_post(**overrides) -> Post:
    defaults = dict(
        slug="17-testing-best-practices-in-python",
        title="Testing Best Practices in Python",
        description="Testing at the right level with pytest.",
        tags=["Python", "Testing", "pytest", "Software Engineering"],
        categories=["Python"],
        canonical_url="https://pg-blogs.netlify.app/posts/17-testing-best-practices-in-python/",
        body_markdown="Body.",
    )
    defaults.update(overrides)
    return Post(**defaults)


# --- medium_import_list -------------------------------------------------------


def test_medium_import_list_contains_all_canonical_urls():
    posts = [_java_post(), _python_post()]
    result = medium_import_list(posts)

    assert _java_post().canonical_url in result
    assert _python_post().canonical_url in result


def test_medium_import_list_contains_import_step():
    result = medium_import_list([_java_post()])

    assert "medium.com/p/import" in result
    assert "Import" in result
    assert "Publish" in result


def test_medium_import_list_explains_manual_canonical_behavior():
    result = medium_import_list([_java_post()])

    assert "no write API" in result or "write API" in result
    assert "canonical" in result.lower()


def test_medium_import_list_mentions_table_checklists():
    result = medium_import_list([_java_post()])

    assert "table" in result.lower()
    assert "medium-checklists" in result


# --- medium_checklist_snippets ---------------------------------------------------


def test_medium_checklist_snippets_empty_for_table_less_post():
    post = _java_post(body_markdown="Just prose, no tables here.")
    assert medium_checklist_snippets(post) == ""


def test_medium_checklist_snippets_includes_heading_and_bullets():
    post = _java_post(
        body_markdown=(
            "## Practical Checklist\n\n"
            "| Practice | Why it matters |\n"
            "|----------|----------------|\n"
            "| Match model tier | Don't overpay |\n"
            "| Cache prefixes | Lower cost |\n"
        )
    )
    result = medium_checklist_snippets(post)

    assert post.title in result
    assert f"Canonical: {post.canonical_url}" in result
    assert "**Practical Checklist**" in result
    assert "- **Match model tier** — Don't overpay" in result
    assert "- **Cache prefixes** — Lower cost" in result
    assert "|" not in result


# --- teaser --------------------------------------------------------------------


def test_teaser_contains_title_and_canonical_link():
    post = _java_post()
    result = teaser(post)

    assert post.title in result
    assert result.count(post.canonical_url) >= 3  # LinkedIn, Reddit, HN sections


def test_teaser_contains_linkedin_hashtag_derived_from_tag():
    result = teaser(_java_post())

    assert "#Java" in result
    assert "#Testing" in result


def test_teaser_java_post_suggests_r_java():
    result = teaser(_java_post())

    assert "r/java" in result
    assert "r/programming" in result


def test_teaser_python_post_suggests_r_python_not_r_java():
    result = teaser(_python_post())

    assert "r/Python" in result
    assert "r/java" not in result


def test_teaser_ai_tagged_post_suggests_machine_learning_subreddit():
    post = _java_post(tags=["Java", "AI", "LLM", "Anthropic"])
    result = teaser(post)

    assert "r/MachineLearning" in result


def test_teaser_non_ai_post_does_not_suggest_machine_learning_subreddit():
    result = teaser(_java_post())

    assert "r/MachineLearning" not in result


def test_teaser_hacker_news_notes_no_show_hn_for_articles():
    result = teaser(_java_post())

    assert "Show HN" in result
    assert "Hacker News" in result
