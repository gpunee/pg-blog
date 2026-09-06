import pytest

from syndicate import cli
from syndicate.generate import linkedin_commentary
from syndicate.linkedin import LinkedInError
from syndicate.posts import Post
from syndicate.state import load_state, save_state


def _post(slug="1-foo", canonical="https://pg-blogs.netlify.app/posts/1-foo/") -> Post:
    return Post(
        slug=slug,
        title="Foo",
        description="A post about foo.",
        tags=["Java"],
        categories=["Java"],
        canonical_url=canonical,
        body_markdown="Body text.",
    )


class ExplodingLinkedInClient:
    """Instantiating (or calling) this raises — proves a code path never
    touches the network layer at all.
    """

    def __init__(self, *args, **kwargs):
        raise AssertionError("LinkedInClient constructed when no network call was expected")


class FakeLinkedInClient:
    """Records calls; no real HTTP. `has_token` and the per-call results of
    `get_person_urn`/`create_ugc_post` are configurable per test — a
    configured result may be an Exception instance, which is raised instead
    of returned (used to simulate a `LinkedInError`/`RuntimeError` mid-batch).
    """

    def __init__(self, has_token=True, create_results=None, person_urn="urn:li:person:fake123"):
        self.has_token = has_token
        self._create_results = list(create_results) if create_results is not None else []
        self._person_urn = person_urn
        self.create_calls: list[dict] = []
        self.get_person_urn_calls = 0

    def get_person_urn(self):
        self.get_person_urn_calls += 1
        if isinstance(self._person_urn, Exception):
            raise self._person_urn
        return self._person_urn

    def create_ugc_post(self, payload):
        self.create_calls.append(payload)
        result = self._create_results.pop(0) if self._create_results else "urn:li:share:default"
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture
def linkedin_state_path(tmp_path, monkeypatch):
    path = tmp_path / "linkedin_state.json"
    monkeypatch.setattr(cli, "_linkedin_state_path", lambda: path)
    return path


@pytest.fixture
def linkedin_sidecar_dir(tmp_path, monkeypatch):
    path = tmp_path / "linkedin"
    path.mkdir()
    monkeypatch.setattr(cli, "_linkedin_sidecar_dir", lambda: path)
    return path


@pytest.fixture(autouse=True)
def _clean_author_urn_env(monkeypatch):
    # Baseline: no ambient LINKEDIN_AUTHOR_URN leaking in from the real shell.
    # Tests that need it set call monkeypatch.setenv(...) themselves.
    monkeypatch.delenv("LINKEDIN_AUTHOR_URN", raising=False)


# --- default / --dry-run: zero network calls, full preview, footer ---------------


def test_default_makes_zero_network_calls_and_prints_footer(
    monkeypatch, capsys, linkedin_state_path, linkedin_sidecar_dir
):
    monkeypatch.setattr(cli, "load_posts", lambda: [_post()])
    monkeypatch.setattr(cli, "LinkedInClient", ExplodingLinkedInClient)

    exit_code = cli.main(["linkedin", "--all"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "1-foo" in out
    assert "LinkedIn has no draft state; nothing was posted." in out
    assert "Re-run with --publish to post live." in out


def test_dry_run_makes_zero_network_calls_and_prints_footer(
    monkeypatch, capsys, linkedin_state_path, linkedin_sidecar_dir
):
    monkeypatch.setattr(cli, "load_posts", lambda: [_post()])
    monkeypatch.setattr(cli, "LinkedInClient", ExplodingLinkedInClient)

    exit_code = cli.main(["linkedin", "--all", "--dry-run"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "LinkedIn has no draft state; nothing was posted." in out


def test_dry_run_with_publish_flag_still_previews_zero_network(
    monkeypatch, capsys, linkedin_state_path, linkedin_sidecar_dir
):
    # --dry-run always wins, even paired with --publish (mirrors devto).
    monkeypatch.setattr(cli, "load_posts", lambda: [_post()])
    monkeypatch.setattr(cli, "LinkedInClient", ExplodingLinkedInClient)

    exit_code = cli.main(["linkedin", "--all", "--dry-run", "--publish"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "LinkedIn has no draft state; nothing was posted." in out


def test_preview_prints_full_resolved_commentary_and_canonical(
    monkeypatch, capsys, linkedin_state_path, linkedin_sidecar_dir
):
    post = _post()
    monkeypatch.setattr(cli, "load_posts", lambda: [post])
    monkeypatch.setattr(cli, "LinkedInClient", ExplodingLinkedInClient)

    cli.main(["linkedin", "--all", "--dry-run"])

    out = capsys.readouterr().out
    assert linkedin_commentary(post) in out
    assert post.canonical_url in out
    assert "source=generated" in out


def test_preview_shows_placeholder_author_urn_when_env_unset(
    monkeypatch, capsys, linkedin_state_path, linkedin_sidecar_dir
):
    monkeypatch.setattr(cli, "load_posts", lambda: [_post()])
    monkeypatch.setattr(cli, "LinkedInClient", ExplodingLinkedInClient)

    cli.main(["linkedin", "--all", "--dry-run"])

    out = capsys.readouterr().out
    assert "urn:li:person:<resolved-at-publish-time>" in out


def test_preview_shows_env_author_urn_when_set(
    monkeypatch, capsys, linkedin_state_path, linkedin_sidecar_dir
):
    monkeypatch.setenv("LINKEDIN_AUTHOR_URN", "urn:li:person:owner1")
    monkeypatch.setattr(cli, "load_posts", lambda: [_post()])
    monkeypatch.setattr(cli, "LinkedInClient", ExplodingLinkedInClient)

    cli.main(["linkedin", "--all", "--dry-run"])

    out = capsys.readouterr().out
    assert "urn:li:person:owner1" in out
    assert "urn:li:person:<resolved-at-publish-time>" not in out


# --- sidecar override vs generated fallback (labelled) ----------------------------


def test_sidecar_override_used_and_labelled_sidecar(
    monkeypatch, capsys, linkedin_state_path, linkedin_sidecar_dir
):
    post = _post(slug="1-foo")
    monkeypatch.setattr(cli, "load_posts", lambda: [post])
    monkeypatch.setattr(cli, "LinkedInClient", ExplodingLinkedInClient)
    (linkedin_sidecar_dir / "1-foo.md").write_text("Owner-authored take on this post.\n")

    cli.main(["linkedin", "--all", "--dry-run"])

    out = capsys.readouterr().out
    assert "source=sidecar" in out
    assert "Owner-authored take on this post." in out
    assert linkedin_commentary(post) not in out


def test_no_sidecar_uses_generated_and_labelled_generated(
    monkeypatch, capsys, linkedin_state_path, linkedin_sidecar_dir
):
    post = _post(slug="2-bar", canonical="https://pg-blogs.netlify.app/posts/2-bar/")
    monkeypatch.setattr(cli, "load_posts", lambda: [post])
    monkeypatch.setattr(cli, "LinkedInClient", ExplodingLinkedInClient)

    cli.main(["linkedin", "--all", "--dry-run"])

    out = capsys.readouterr().out
    assert "source=generated" in out
    assert linkedin_commentary(post) in out


# --- --only selection --------------------------------------------------------------


def test_only_filters_by_numeric_prefix(
    monkeypatch, capsys, linkedin_state_path, linkedin_sidecar_dir
):
    monkeypatch.setattr(
        cli,
        "load_posts",
        lambda: [
            _post(slug="1-foo"),
            _post(slug="2-bar", canonical="https://pg-blogs.netlify.app/posts/2-bar/"),
        ],
    )
    monkeypatch.setattr(cli, "LinkedInClient", ExplodingLinkedInClient)

    cli.main(["linkedin", "--only", "2", "--dry-run"])

    out = capsys.readouterr().out
    assert "2-bar" in out
    assert "1-foo" not in out


def test_only_unknown_prefix_selects_nothing(
    monkeypatch, capsys, linkedin_state_path, linkedin_sidecar_dir
):
    monkeypatch.setattr(cli, "load_posts", lambda: [_post()])
    monkeypatch.setattr(cli, "LinkedInClient", ExplodingLinkedInClient)

    exit_code = cli.main(["linkedin", "--only", "99", "--dry-run"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "No posts selected." in out


# --- idempotency: already-shared slug is skipped ----------------------------------


def test_publish_skips_already_shared_slug_without_create_call(
    monkeypatch, capsys, linkedin_state_path, linkedin_sidecar_dir
):
    monkeypatch.setenv("LINKEDIN_AUTHOR_URN", "urn:li:person:owner1")
    post = _post()
    monkeypatch.setattr(cli, "load_posts", lambda: [post])
    fake_client = FakeLinkedInClient()
    monkeypatch.setattr(cli, "LinkedInClient", lambda: fake_client)
    save_state(linkedin_state_path, {"1-foo": "urn:li:share:existing"})

    exit_code = cli.main(["linkedin", "--all", "--publish", "--yes"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert fake_client.create_calls == []
    assert "already shared (urn=urn:li:share:existing)" in out
    assert load_state(linkedin_state_path) == {"1-foo": "urn:li:share:existing"}
    assert "skipped(already): 1" in out


# --- --publish guards --------------------------------------------------------------


def test_publish_without_token_exits_1_with_zero_network(
    monkeypatch, capsys, linkedin_state_path, linkedin_sidecar_dir
):
    monkeypatch.setattr(cli, "load_posts", lambda: [_post()])
    fake_client = FakeLinkedInClient(has_token=False)
    monkeypatch.setattr(cli, "LinkedInClient", lambda: fake_client)

    exit_code = cli.main(["linkedin", "--all", "--publish"])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "LINKEDIN_ACCESS_TOKEN" in out
    assert fake_client.create_calls == []
    assert fake_client.get_person_urn_calls == 0


def test_publish_without_yes_on_non_tty_refuses(
    monkeypatch, capsys, linkedin_state_path, linkedin_sidecar_dir
):
    monkeypatch.setenv("LINKEDIN_AUTHOR_URN", "urn:li:person:owner1")
    monkeypatch.setattr(cli, "load_posts", lambda: [_post()])
    fake_client = FakeLinkedInClient()
    monkeypatch.setattr(cli, "LinkedInClient", lambda: fake_client)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)

    exit_code = cli.main(["linkedin", "--all", "--publish"])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "--yes" in out
    assert fake_client.create_calls == []


def test_publish_with_yes_creates_exactly_once_and_records_state(
    monkeypatch, linkedin_state_path, linkedin_sidecar_dir
):
    monkeypatch.setenv("LINKEDIN_AUTHOR_URN", "urn:li:person:owner1")
    post = _post()
    monkeypatch.setattr(cli, "load_posts", lambda: [post])
    fake_client = FakeLinkedInClient(create_results=["urn:li:share:999"])
    monkeypatch.setattr(cli, "LinkedInClient", lambda: fake_client)

    exit_code = cli.main(["linkedin", "--all", "--publish", "--yes"])

    assert exit_code == 0
    assert len(fake_client.create_calls) == 1
    assert load_state(linkedin_state_path) == {"1-foo": "urn:li:share:999"}


# --- error handling: LinkedInError + malformed-success RuntimeError ---------------


def test_mixed_errors_both_counted_failed_state_has_only_successes(
    monkeypatch, capsys, linkedin_state_path, linkedin_sidecar_dir
):
    monkeypatch.setenv("LINKEDIN_AUTHOR_URN", "urn:li:person:owner1")
    posts = [
        _post(slug="1-foo"),
        _post(slug="2-bar", canonical="https://pg-blogs.netlify.app/posts/2-bar/"),
        _post(slug="3-baz", canonical="https://pg-blogs.netlify.app/posts/3-baz/"),
    ]
    monkeypatch.setattr(cli, "load_posts", lambda: posts)
    fake_client = FakeLinkedInClient(
        create_results=[
            LinkedInError(400, "bad request body"),
            RuntimeError(
                "LinkedIn ugcPosts response missing the 'X-RestLi-Id' header"
            ),
            "urn:li:share:333",
        ]
    )
    monkeypatch.setattr(cli, "LinkedInClient", lambda: fake_client)

    exit_code = cli.main(["linkedin", "--all", "--publish", "--yes"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert len(fake_client.create_calls) == 3
    assert "[1-foo] FAILED" in out
    assert "[2-bar] FAILED" in out
    assert "[3-baz] shared" in out
    assert load_state(linkedin_state_path) == {"3-baz": "urn:li:share:333"}
    assert "Shared: 1, skipped(already): 0, failed: 2." in out


# --- author URN resolution: env-set skips userinfo; unset resolves once ----------


def test_publish_with_env_author_urn_skips_userinfo_call(
    monkeypatch, linkedin_state_path, linkedin_sidecar_dir
):
    monkeypatch.setenv("LINKEDIN_AUTHOR_URN", "urn:li:person:owner1")
    posts = [
        _post(slug="1-foo"),
        _post(slug="2-bar", canonical="https://pg-blogs.netlify.app/posts/2-bar/"),
    ]
    monkeypatch.setattr(cli, "load_posts", lambda: posts)
    fake_client = FakeLinkedInClient(create_results=["urn:li:share:1", "urn:li:share:2"])
    monkeypatch.setattr(cli, "LinkedInClient", lambda: fake_client)

    cli.main(["linkedin", "--all", "--publish", "--yes"])

    assert fake_client.get_person_urn_calls == 0
    assert fake_client.create_calls[0]["author"] == "urn:li:person:owner1"
    assert fake_client.create_calls[1]["author"] == "urn:li:person:owner1"


def test_publish_without_env_author_urn_resolves_once_for_the_batch(
    monkeypatch, linkedin_state_path, linkedin_sidecar_dir
):
    posts = [
        _post(slug="1-foo"),
        _post(slug="2-bar", canonical="https://pg-blogs.netlify.app/posts/2-bar/"),
    ]
    monkeypatch.setattr(cli, "load_posts", lambda: posts)
    fake_client = FakeLinkedInClient(
        person_urn="urn:li:person:resolved1",
        create_results=["urn:li:share:1", "urn:li:share:2"],
    )
    monkeypatch.setattr(cli, "LinkedInClient", lambda: fake_client)

    cli.main(["linkedin", "--all", "--publish", "--yes"])

    assert fake_client.get_person_urn_calls == 1
    assert fake_client.create_calls[0]["author"] == "urn:li:person:resolved1"
    assert fake_client.create_calls[1]["author"] == "urn:li:person:resolved1"
