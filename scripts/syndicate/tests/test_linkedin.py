import pytest

from syndicate import linkedin
from syndicate.linkedin import LinkedInClient, LinkedInError


class FakeResponse:
    def __init__(self, status_code, json_body=None, text="", headers=None):
        self.status_code = status_code
        self._json_body = json_body
        self.text = text or (str(json_body) if json_body is not None else "")
        self.headers = headers or {}

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


# --- token handling / redaction --------------------------------------------------


def test_missing_token_raises_runtime_error_without_a_value(monkeypatch):
    monkeypatch.delenv("LINKEDIN_ACCESS_TOKEN", raising=False)
    client = LinkedInClient(session=ExplodingSession())

    with pytest.raises(RuntimeError) as excinfo:
        client.get_person_urn()

    assert "LINKEDIN_ACCESS_TOKEN" in str(excinfo.value)


def test_has_token_reflects_configured_token(monkeypatch):
    monkeypatch.delenv("LINKEDIN_ACCESS_TOKEN", raising=False)
    assert LinkedInClient(session=ExplodingSession()).has_token is False
    assert (
        LinkedInClient(access_token="secret-token-123", session=ExplodingSession()).has_token
        is True
    )


def test_linkedin_error_never_includes_the_access_token():
    secret = "AQV-super-secret-linkedin-token-do-not-leak"
    session = FakeSession([FakeResponse(400, text="Bad request body")])
    client = LinkedInClient(access_token=secret, session=session)

    with pytest.raises(LinkedInError) as excinfo:
        client.create_ugc_post({"author": "urn:li:person:1"})

    assert secret not in str(excinfo.value)
    assert "400" in str(excinfo.value)


def test_request_sends_auth_and_protocol_version_headers():
    secret = "AQV-super-secret-linkedin-token-do-not-leak"
    session = FakeSession(
        [FakeResponse(201, headers={"X-RestLi-Id": "urn:li:share:1"})]
    )
    client = LinkedInClient(access_token=secret, session=session)

    client.create_ugc_post({"author": "urn:li:person:1"})

    headers = session.calls[0]["headers"]
    assert headers["Authorization"] == f"Bearer {secret}"
    assert headers["X-Restli-Protocol-Version"] == "2.0.0"
    assert headers["Content-Type"] == "application/json"


def test_request_omits_content_type_when_no_json_body():
    session = FakeSession([FakeResponse(200, json_body={"sub": "abc123"})])
    client = LinkedInClient(access_token="k", session=session)

    client.get_person_urn()

    headers = session.calls[0]["headers"]
    assert "Content-Type" not in headers


# --- retry ----------------------------------------------------------------------


def test_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr(linkedin, "SLEEP", lambda seconds: None)
    session = FakeSession(
        [
            FakeResponse(429, text="rate limited"),
            FakeResponse(201, headers={"X-RestLi-Id": "urn:li:share:7"}),
        ]
    )
    client = LinkedInClient(access_token="k", session=session)

    urn = client.create_ugc_post({"author": "urn:li:person:1"})

    assert urn == "urn:li:share:7"
    assert len(session.calls) == 2


def test_retries_exhausted_raises_linkedin_error(monkeypatch):
    monkeypatch.setattr(linkedin, "SLEEP", lambda seconds: None)
    session = FakeSession(
        [
            FakeResponse(503, text="down"),
            FakeResponse(503, text="down"),
            FakeResponse(503, text="down"),
        ]
    )
    client = LinkedInClient(access_token="k", session=session)

    with pytest.raises(LinkedInError):
        client.create_ugc_post({"author": "urn:li:person:1"})

    assert len(session.calls) == 3


def test_non_retryable_error_does_not_retry():
    session = FakeSession([FakeResponse(422, text="unprocessable")])
    client = LinkedInClient(access_token="k", session=session)

    with pytest.raises(LinkedInError):
        client.create_ugc_post({"author": "urn:li:person:1"})

    assert len(session.calls) == 1


# --- endpoints --------------------------------------------------------------------


def test_create_ugc_post_posts_to_expected_path_and_returns_header_urn():
    session = FakeSession([FakeResponse(201, headers={"X-RestLi-Id": "urn:li:share:42"})])
    client = LinkedInClient(access_token="k", session=session)

    urn = client.create_ugc_post({"author": "urn:li:person:1", "lifecycleState": "PUBLISHED"})

    assert urn == "urn:li:share:42"
    assert session.calls[0]["method"] == "POST"
    assert session.calls[0]["url"].endswith("/v2/ugcPosts")
    assert session.calls[0]["json"] == {
        "author": "urn:li:person:1",
        "lifecycleState": "PUBLISHED",
    }


def test_create_ugc_post_missing_header_raises_clear_error():
    session = FakeSession([FakeResponse(201, headers={})])
    client = LinkedInClient(access_token="k", session=session)

    with pytest.raises(RuntimeError) as excinfo:
        client.create_ugc_post({"author": "urn:li:person:1"})

    assert "X-RestLi-Id" in str(excinfo.value)


def test_get_person_urn_builds_urn_from_userinfo_sub():
    session = FakeSession([FakeResponse(200, json_body={"sub": "abc123"})])
    client = LinkedInClient(access_token="k", session=session)

    urn = client.get_person_urn()

    assert urn == "urn:li:person:abc123"
    assert session.calls[0]["method"] == "GET"
    assert session.calls[0]["url"].endswith("/v2/userinfo")


def test_get_person_urn_missing_sub_raises_clear_error():
    session = FakeSession([FakeResponse(200, json_body={"name": "no sub here"})])
    client = LinkedInClient(access_token="k", session=session)

    with pytest.raises(RuntimeError) as excinfo:
        client.get_person_urn()

    assert "sub" in str(excinfo.value)
