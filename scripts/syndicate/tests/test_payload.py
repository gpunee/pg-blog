from syndicate.payload import build_devto_article
from syndicate.posts import Post


def _post(**overrides) -> Post:
    defaults = dict(
        slug="12-designing-for-change-in-java",
        title="Designing for Change",
        description="A post about boundaries.",
        tags=["Java", "Architecture", "SOLID", "Software Engineering", "Testing"],
        categories=["Java"],
        canonical_url="https://pg-blogs.netlify.app/posts/12-designing-for-change-in-java/",
        body_markdown='See [post]({{< ref "3-java-and-the-jvm-ecosystem.md" >}}) for context.',
    )
    defaults.update(overrides)
    return Post(**defaults)


# --- paired ON/OFF (required) -------------------------------------------------


def test_build_devto_article_published_false_when_publish_false():
    article = build_devto_article(_post(), publish=False)
    assert article["published"] is False


def test_build_devto_article_published_true_when_publish_true():
    article = build_devto_article(_post(), publish=True)
    assert article["published"] is True


# --- shape / content -----------------------------------------------------------


def test_build_devto_article_includes_canonical_url():
    article = build_devto_article(_post(), publish=False)
    assert article["canonical_url"] == "https://pg-blogs.netlify.app/posts/12-designing-for-change-in-java/"


def test_build_devto_article_tags_capped_at_four():
    article = build_devto_article(_post(), publish=False)
    assert len(article["tags"]) <= 4
    assert article["tags"] == ["java", "architecture", "softwareengineering", "testing"]


def test_build_devto_article_body_has_no_hugo_shortcodes():
    article = build_devto_article(_post(), publish=False)
    assert "{{<" not in article["body_markdown"]
    assert "{{%" not in article["body_markdown"]
    assert "https://pg-blogs.netlify.app/posts/3-java-and-the-jvm-ecosystem/" in article["body_markdown"]


def test_build_devto_article_carries_title_and_description():
    article = build_devto_article(_post(), publish=False)
    assert article["title"] == "Designing for Change"
    assert article["description"] == "A post about boundaries."
