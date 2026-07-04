import pytest

from syndicate import devto
from syndicate.devto import DevToClient, DevToError


class FakeResponse:
    def __init__(self, status_code, json_body=None, text=""):
        self.status_code = status_code
        self._json_body = json_body
        self.text = text or (str(json_body) if json_body is not None else "")

    def json(self):
        return self._json_body


class FakeSession:
    """Records calls and returns responses from a pre-programmed queue (per
    call, or a single fixed response if `responses` is not a list of one per
    call).
    """

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, json=None, headers=None):
        self.calls.append(
            {"method": method, "url": url, "json": json, "headers": headers}
        )
        if len(self.responses) > 1:
            return self.responses.pop(0)
        return self.responses[0]


class ExplodingSession:
    """A session that fails the test if it is ever called — used to prove a
    code path makes zero network calls.
    """

    def request(self, *args, **kwargs):
        raise AssertionError("network call made when none was expected")


# --- key handling / redaction --------------------------------------------------


def test_missing_key_raises_runtime_error_without_a_value(monkeypatch):
    monkeypatch.delenv("DEVTO_API_KEY", raising=False)
    client = DevToClient(session=ExplodingSession())

    with pytest.raises(RuntimeError) as excinfo:
        client.list_my_articles()

    assert "DEVTO_API_KEY" in str(excinfo.value)


def test_has_key_reflects_configured_key(monkeypatch):
    monkeypatch.delenv("DEVTO_API_KEY", raising=False)
    assert DevToClient(session=ExplodingSession()).has_key is False
    assert DevToClient(api_key="secret-123", session=ExplodingSession()).has_key is True


def test_devto_error_never_includes_the_api_key():
    secret = "sk-super-secret-key-do-not-leak"
    session = FakeSession([FakeResponse(400, text="Bad request body")])
    client = DevToClient(api_key=secret, session=session)

    with pytest.raises(DevToError) as excinfo:
        client.create_article({"title": "x"})

    assert secret not in str(excinfo.value)
    assert "400" in str(excinfo.value)


def test_request_sends_api_key_header_not_in_body():
    secret = "sk-super-secret-key-do-not-leak"
    session = FakeSession([FakeResponse(200, json_body={"id": 1})])
    client = DevToClient(api_key=secret, session=session)

    client.create_article({"title": "x"})

    assert session.calls[0]["headers"]["api-key"] == secret


# --- retry ----------------------------------------------------------------------


def test_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr(devto, "SLEEP", lambda seconds: None)
    session = FakeSession([FakeResponse(429, text="rate limited"), FakeResponse(200, json_body={"id": 7})])
    client = DevToClient(api_key="k", session=session)

    result = client.create_article({"title": "x"})

    assert result == {"id": 7}
    assert len(session.calls) == 2


def test_retries_exhausted_raises_devto_error(monkeypatch):
    monkeypatch.setattr(devto, "SLEEP", lambda seconds: None)
    session = FakeSession(
        [FakeResponse(503, text="down"), FakeResponse(503, text="down"), FakeResponse(503, text="down")]
    )
    client = DevToClient(api_key="k", session=session)

    with pytest.raises(DevToError):
        client.create_article({"title": "x"})

    assert len(session.calls) == 3


def test_non_retryable_error_does_not_retry():
    session = FakeSession([FakeResponse(422, text="unprocessable")])
    client = DevToClient(api_key="k", session=session)

    with pytest.raises(DevToError):
        client.create_article({"title": "x"})

    assert len(session.calls) == 1


# --- endpoints --------------------------------------------------------------------


def test_list_my_articles_hits_expected_path():
    session = FakeSession([FakeResponse(200, json_body=[{"id": 1, "canonical_url": "x"}])])
    client = DevToClient(api_key="k", session=session)

    result = client.list_my_articles()

    assert result == [{"id": 1, "canonical_url": "x"}]
    assert session.calls[0]["method"] == "GET"
    assert session.calls[0]["url"].endswith("/articles/me/all?per_page=1000")


def test_create_article_posts_wrapped_body():
    session = FakeSession([FakeResponse(200, json_body={"id": 42})])
    client = DevToClient(api_key="k", session=session)

    result = client.create_article({"title": "Hello"})

    assert result == {"id": 42}
    assert session.calls[0]["method"] == "POST"
    assert session.calls[0]["url"].endswith("/articles")
    assert session.calls[0]["json"] == {"article": {"title": "Hello"}}


def test_update_article_puts_wrapped_body_to_id_path():
    session = FakeSession([FakeResponse(200, json_body={"id": 42})])
    client = DevToClient(api_key="k", session=session)

    result = client.update_article(42, {"title": "Hello 2"})

    assert result == {"id": 42}
    assert session.calls[0]["method"] == "PUT"
    assert session.calls[0]["url"].endswith("/articles/42")
    assert session.calls[0]["json"] == {"article": {"title": "Hello 2"}}
