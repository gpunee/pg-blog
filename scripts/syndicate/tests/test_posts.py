from pathlib import Path

from syndicate.posts import load_posts


def _write(path: Path, *, title, description, tags, categories, draft, body):
    tags_yaml = "\n".join(f"  - {t}" for t in tags)
    categories_yaml = "\n".join(f"  - {c}" for c in categories)
    path.write_text(
        f"""---
title: "{title}"
description: "{description}"
tags:
{tags_yaml}
categories:
{categories_yaml}
draft: {"true" if draft else "false"}
---

{body}
"""
    )


def test_load_posts_parses_front_matter_and_computes_canonical_url(tmp_path):
    posts_dir = tmp_path / "posts"
    posts_dir.mkdir()
    _write(
        posts_dir / "12-designing-for-change-in-java.md",
        title="Designing for Change",
        description="A post about boundaries.",
        tags=["Java", "Architecture"],
        categories=["Java"],
        draft=False,
        body="Some body text.",
    )

    posts = load_posts(content_dir=str(posts_dir))

    assert len(posts) == 1
    post = posts[0]
    assert post.slug == "12-designing-for-change-in-java"
    assert post.title == "Designing for Change"
    assert post.description == "A post about boundaries."
    assert post.tags == ["Java", "Architecture"]
    assert post.categories == ["Java"]
    assert post.canonical_url == (
        "https://pg-blogs.netlify.app/posts/12-designing-for-change-in-java/"
    )
    assert "Some body text." in post.body_markdown


def test_load_posts_sorts_by_numeric_prefix_not_lexicographically(tmp_path):
    posts_dir = tmp_path / "posts"
    posts_dir.mkdir()
    for n, name in [(2, "2-second.md"), (10, "10-tenth.md"), (1, "1-first.md")]:
        _write(
            posts_dir / name,
            title=f"Post {n}",
            description="d",
            tags=["Java"],
            categories=["Java"],
            draft=False,
            body="body",
        )

    posts = load_posts(content_dir=str(posts_dir))

    assert [p.slug for p in posts] == ["1-first", "2-second", "10-tenth"]


def test_load_posts_skips_search_md_and_draft_true(tmp_path):
    posts_dir = tmp_path / "posts"
    posts_dir.mkdir()
    (posts_dir / "search.md").write_text("Search index page, no front matter needed.")
    _write(
        posts_dir / "1-draft-post.md",
        title="Draft",
        description="d",
        tags=["Java"],
        categories=["Java"],
        draft=True,
        body="body",
    )
    _write(
        posts_dir / "2-published-post.md",
        title="Published",
        description="d",
        tags=["Java"],
        categories=["Java"],
        draft=False,
        body="body",
    )

    posts = load_posts(content_dir=str(posts_dir))

    assert [p.slug for p in posts] == ["2-published-post"]
