import pytest

from syndicate import cli
from syndicate.posts import Post
from syndicate.state import load_state


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


class ExplodingDevToClient:
    """Instantiating (or calling) this raises — proves a code path never
    touches the network layer at all.
    """

    def __init__(self, *args, **kwargs):
        raise AssertionError("DevToClient constructed when no network call was expected")


class FakeDevToClient:
    """Records calls; no real HTTP. `has_key` and the return values of each
    method are configurable per test.
    """

    def __init__(self, has_key=True, list_result=None, create_id=999):
        self.has_key = has_key
        self._list_result = list_result if list_result is not None else []
        self._create_id = create_id
        self.list_calls = 0
        self.create_calls = []
        self.update_calls = []

    def list_my_articles(self):
        self.list_calls += 1
        return self._list_result

    def create_article(self, article):
        self.create_calls.append(article)
        return {"id": self._create_id}

    def update_article(self, article_id, article):
        self.update_calls.append((article_id, article))
        return {"id": article_id}


@pytest.fixture
def state_path(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    monkeypatch.setattr(cli, "_state_path", lambda: path)
    return path


# --- dry-run makes zero network calls -------------------------------------------


def test_dry_run_makes_zero_network_calls(monkeypatch, capsys, state_path):
    monkeypatch.setattr(cli, "load_posts", lambda: [_post()])
    monkeypatch.setattr(cli, "DevToClient", ExplodingDevToClient)

    exit_code = cli.main(["devto", "--all", "--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "1-foo" in captured.out
    assert "Dry run" in captured.out


def test_dry_run_reports_draft_by_default(monkeypatch, capsys, state_path):
    monkeypatch.setattr(cli, "load_posts", lambda: [_post()])
    monkeypatch.setattr(cli, "DevToClient", ExplodingDevToClient)

    cli.main(["devto", "--all", "--dry-run"])

    out = capsys.readouterr().out
    assert "published=False" in out


def test_dry_run_reports_published_true_with_publish_flag(monkeypatch, capsys, state_path):
    monkeypatch.setattr(cli, "load_posts", lambda: [_post()])
    monkeypatch.setattr(cli, "DevToClient", ExplodingDevToClient)

    cli.main(["devto", "--all", "--dry-run", "--publish"])

    out = capsys.readouterr().out
    assert "published=True" in out


# --- idempotency -----------------------------------------------------------------


def test_known_state_id_triggers_update_not_create(monkeypatch, state_path):
    monkeypatch.setattr(cli, "load_posts", lambda: [_post()])
    fake_client = FakeDevToClient()
    monkeypatch.setattr(cli, "DevToClient", lambda: fake_client)

    from syndicate.state import save_state

    save_state(state_path, {"1-foo": 123})

    exit_code = cli.main(["devto", "--all"])

    assert exit_code == 0
    assert fake_client.update_calls == [(123, fake_client.update_calls[0][1])]
    assert fake_client.create_calls == []
    assert fake_client.list_calls == 0  # known id — no need to reconcile
    assert load_state(state_path) == {"1-foo": 123}


def test_canonical_match_fallback_triggers_update(monkeypatch, state_path):
    post = _post()
    monkeypatch.setattr(cli, "load_posts", lambda: [post])
    fake_client = FakeDevToClient(
        list_result=[{"id": 555, "canonical_url": post.canonical_url}]
    )
    monkeypatch.setattr(cli, "DevToClient", lambda: fake_client)

    exit_code = cli.main(["devto", "--all"])

    assert exit_code == 0
    assert len(fake_client.update_calls) == 1
    assert fake_client.update_calls[0][0] == 555
    assert fake_client.create_calls == []
    assert load_state(state_path) == {"1-foo": 555}


def test_no_match_triggers_create_and_saves_returned_id(monkeypatch, state_path):
    post = _post()
    monkeypatch.setattr(cli, "load_posts", lambda: [post])
    fake_client = FakeDevToClient(list_result=[], create_id=777)
    monkeypatch.setattr(cli, "DevToClient", lambda: fake_client)

    exit_code = cli.main(["devto", "--all"])

    assert exit_code == 0
    assert len(fake_client.create_calls) == 1
    assert fake_client.update_calls == []
    assert load_state(state_path) == {"1-foo": 777}


def test_missing_key_refuses_live_run_without_network_calls(monkeypatch, capsys, state_path):
    monkeypatch.setattr(cli, "load_posts", lambda: [_post()])
    fake_client = FakeDevToClient(has_key=False)
    monkeypatch.setattr(cli, "DevToClient", lambda: fake_client)

    exit_code = cli.main(["devto", "--all"])

    assert exit_code == 1
    assert "DEVTO_API_KEY" in capsys.readouterr().out
    assert fake_client.create_calls == []
    assert fake_client.update_calls == []


# --- --publish guard --------------------------------------------------------------


def test_publish_without_yes_on_non_tty_refuses(monkeypatch, capsys, state_path):
    monkeypatch.setattr(cli, "load_posts", lambda: [_post()])
    fake_client = FakeDevToClient(list_result=[], create_id=1)
    monkeypatch.setattr(cli, "DevToClient", lambda: fake_client)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)

    exit_code = cli.main(["devto", "--all", "--publish"])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "--yes" in out
    assert fake_client.create_calls == []
    assert fake_client.update_calls == []


def test_publish_with_yes_skips_prompt_and_publishes(monkeypatch, state_path):
    post = _post()
    monkeypatch.setattr(cli, "load_posts", lambda: [post])
    fake_client = FakeDevToClient(list_result=[], create_id=1)
    monkeypatch.setattr(cli, "DevToClient", lambda: fake_client)

    exit_code = cli.main(["devto", "--all", "--publish", "--yes"])

    assert exit_code == 0
    assert fake_client.create_calls[0]["published"] is True


def test_publish_without_yes_on_tty_aborts_on_non_y_answer(monkeypatch, capsys, state_path):
    monkeypatch.setattr(cli, "load_posts", lambda: [_post()])
    fake_client = FakeDevToClient(list_result=[], create_id=1)
    monkeypatch.setattr(cli, "DevToClient", lambda: fake_client)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")

    exit_code = cli.main(["devto", "--all", "--publish"])

    assert exit_code == 1
    assert "Aborted" in capsys.readouterr().out
    assert fake_client.create_calls == []


def test_publish_without_yes_on_tty_proceeds_on_y_answer(monkeypatch, state_path):
    monkeypatch.setattr(cli, "load_posts", lambda: [_post()])
    fake_client = FakeDevToClient(list_result=[], create_id=1)
    monkeypatch.setattr(cli, "DevToClient", lambda: fake_client)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")

    exit_code = cli.main(["devto", "--all", "--publish"])

    assert exit_code == 0
    assert fake_client.create_calls[0]["published"] is True


# --- --only selection --------------------------------------------------------------


def test_only_filters_by_numeric_prefix(monkeypatch, capsys, state_path):
    monkeypatch.setattr(
        cli, "load_posts", lambda: [_post(slug="1-foo"), _post(slug="2-bar", canonical="https://pg-blogs.netlify.app/posts/2-bar/")]
    )
    monkeypatch.setattr(cli, "DevToClient", ExplodingDevToClient)

    cli.main(["devto", "--only", "2", "--dry-run"])

    out = capsys.readouterr().out
    assert "2-bar" in out
    assert "1-foo" not in out


# --- medium / teasers (pure generation, no network) -------------------------------


@pytest.fixture
def syndication_dir(tmp_path, monkeypatch):
    path = tmp_path / "syndication"
    monkeypatch.setattr(cli, "_syndication_dir", lambda: path)
    return path


def test_medium_writes_import_list_with_all_posts(monkeypatch, capsys, syndication_dir):
    posts = [_post(slug="1-foo"), _post(slug="2-bar", canonical="https://pg-blogs.netlify.app/posts/2-bar/")]
    monkeypatch.setattr(cli, "load_posts", lambda: posts)

    exit_code = cli.main(["medium"])

    output_path = syndication_dir / "medium-import-list.md"
    assert exit_code == 0
    assert output_path.is_file()
    content = output_path.read_text()
    assert "https://pg-blogs.netlify.app/posts/1-foo/" in content
    assert "https://pg-blogs.netlify.app/posts/2-bar/" in content
    assert "2" in capsys.readouterr().out


def test_teasers_writes_one_file_per_post(monkeypatch, capsys, syndication_dir):
    posts = [_post(slug="1-foo"), _post(slug="2-bar", canonical="https://pg-blogs.netlify.app/posts/2-bar/")]
    monkeypatch.setattr(cli, "load_posts", lambda: posts)

    exit_code = cli.main(["teasers"])

    teasers_dir = syndication_dir / "teasers"
    assert exit_code == 0
    assert (teasers_dir / "1-foo.md").is_file()
    assert (teasers_dir / "2-bar.md").is_file()
    assert "2 teaser file" in capsys.readouterr().out
