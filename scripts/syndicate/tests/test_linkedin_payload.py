from pathlib import Path

from syndicate.generate import linkedin_commentary, resolve_linkedin_commentary
from syndicate.payload import build_linkedin_share
from syndicate.posts import Post, load_posts

AUTHOR_URN = "urn:li:person:abc123"


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


# --- (1) exact ARTICLE dict shape ---------------------------------------------


def test_build_linkedin_share_exact_shape():
    post = _post()
    commentary = "A hand-written hook about designing for change."
    share = build_linkedin_share(post, AUTHOR_URN, commentary)

    assert share == {
        "author": AUTHOR_URN,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": f"{commentary}\n\n{post.canonical_url}"
                },
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
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }


def test_build_linkedin_share_default_visibility_is_public():
    post = _post()
    share = build_linkedin_share(post, AUTHOR_URN, "hook text")
    assert share["visibility"]["com.linkedin.ugc.MemberNetworkVisibility"] == "PUBLIC"


def test_build_linkedin_share_visibility_override():
    post = _post()
    share = build_linkedin_share(post, AUTHOR_URN, "hook text", visibility="CONNECTIONS")
    assert share["visibility"]["com.linkedin.ugc.MemberNetworkVisibility"] == "CONNECTIONS"


def test_build_linkedin_share_commentary_text_ends_with_canonical_url():
    post = _post()
    for commentary in ["Short hook.", "A longer, multi-sentence hook with punctuation!  "]:
        share = build_linkedin_share(post, AUTHOR_URN, commentary)
        text = share["specificContent"]["com.linkedin.ugc.ShareContent"]["shareCommentary"]["text"]
        assert text.endswith(post.canonical_url)


def test_build_linkedin_share_media_carries_title_and_description():
    post = _post()
    share = build_linkedin_share(post, AUTHOR_URN, "hook text")
    media = share["specificContent"]["com.linkedin.ugc.ShareContent"]["media"][0]
    assert media["title"]["text"] == post.title
    assert media["description"]["text"] == post.description
    assert media["originalUrl"] == post.canonical_url
    assert media["status"] == "READY"


# --- (2) override present ------------------------------------------------------


def test_resolve_linkedin_commentary_uses_sidecar_when_present(tmp_path: Path):
    post = _post()
    (tmp_path / f"{post.slug}.md").write_text("Owner-authored take on this post.\n")

    result = resolve_linkedin_commentary(post, tmp_path)

    assert result == "Owner-authored take on this post."
    assert result != linkedin_commentary(post)


# --- (3) override absent / empty / whitespace-only ------------------------------


def test_resolve_linkedin_commentary_falls_back_when_sidecar_absent(tmp_path: Path):
    post = _post()

    result = resolve_linkedin_commentary(post, tmp_path)

    assert result == linkedin_commentary(post)


def test_resolve_linkedin_commentary_falls_back_when_sidecar_empty(tmp_path: Path):
    post = _post()
    (tmp_path / f"{post.slug}.md").write_text("")

    result = resolve_linkedin_commentary(post, tmp_path)

    assert result == linkedin_commentary(post)


def test_resolve_linkedin_commentary_falls_back_when_sidecar_whitespace_only(tmp_path: Path):
    post = _post()
    (tmp_path / f"{post.slug}.md").write_text("   \n\n\t \n")

    result = resolve_linkedin_commentary(post, tmp_path)

    assert result == linkedin_commentary(post)


def test_linkedin_commentary_does_not_contain_canonical_url():
    post = _post()
    assert post.canonical_url not in linkedin_commentary(post)


# --- (4) all 35 real posts -------------------------------------------------------


def test_build_linkedin_share_over_all_real_posts_yields_article_shares():
    posts = load_posts()
    assert len(posts) == 35

    for post in posts:
        commentary = linkedin_commentary(post)
        share = build_linkedin_share(post, AUTHOR_URN, commentary)
        assert share["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] == "ARTICLE"
