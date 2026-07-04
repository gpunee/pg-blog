---
title: "Testing Best Practices in Python"
date: 2026-07-03
description: "Testing at the right level with pytest, covering the unhappy path with parametrize and fixtures, avoiding over-mocking with monkeypatch, and treating coverage as a signal instead of a target."
tags:
  - Python
  - Testing
  - pytest
  - Software Engineering
categories:
  - Python
draft: false
---

## Introduction

Python's testing tools are lightweight enough that it's easy to write a lot of tests without writing *good* ones. A suite that mocks every collaborator, duplicates the same assertion ten times with different inputs pasted in by hand, or chases a coverage number will pass in CI and still miss real bugs.

pytest gives you fixtures, `parametrize`, and `monkeypatch` — the tools that make it just as easy to write the *right* tests as the wrong ones. This post covers how to use them well.

---

## Test at the Right Level: the Pyramid

Not every test should look the same. The test pyramid is a rough guide to where your effort should go:

- **Unit tests** — the bulk of the suite. Pure functions and classes, no I/O, no real database. Milliseconds each.
- **Integration tests** — fewer of these. Verify the *seams*: does your ORM query actually produce correct SQL against a real database, does your HTTP client actually parse a real response.
- **End-to-end tests** — a handful. Cover the critical flows through the whole stack, accepting they're slower and more brittle.

```python
# Unit — pure logic, no database, no framework
def test_applies_ten_percent_discount_for_orders_over_100():
    calculator = DiscountCalculator()

    total = calculator.apply(order_total=150.0)

    assert total == pytest.approx(135.0)
```

```python
# Integration — the seam that matters: our query against a real database
import pytest

@pytest.fixture
def db_session(postgres_container):
    # real Postgres in a test container, not mocked
    with postgres_container.session() as session:
        yield session

def test_finds_orders_placed_in_the_last_week(db_session):
    db_session.add(Order(id="ord-1", placed_at=datetime.now(UTC)))
    db_session.commit()

    recent = order_repository.find_recent(db_session, within=timedelta(days=7))

    assert len(recent) == 1
```

A unit suite that never touches a database runs in seconds and catches most logic bugs. A handful of integration tests catch what only shows up at the boundary — the query that's syntactically fine but semantically wrong, the serialization mismatch.

---

## Test Behavior, Not Implementation

A test that asserts *how* a function works internally breaks the moment you refactor, even when the observable behavior hasn't changed. That kind of test actively works against you.

```python
# DON'T: coupled to implementation details
def test_uses_a_list_internally(mocker):
    service = OrderService()
    spy = mocker.spy(service, "_items")  # asserting internal storage

    service.add_item("sku-1")

    assert spy.append.called  # breaks if _items becomes a dict

# DO: coupled to the observable contract
def test_adding_an_item_includes_it_in_the_order_total():
    service = OrderService()
    service.add_item("sku-1", price=25.0)

    assert service.total() == 25.0
```

If `OrderService` is rewritten to store items in a `dict` or a different order internally, the second test still passes as long as `total()` behaves correctly. That's the point — tests should protect behavior, not internal structure.

---

## Cover the Unhappy Path with `parametrize`

One happy-path test tells you a function works for one input. Real bugs live at the boundaries — empty strings, negative numbers, `None`, malformed data. `@pytest.mark.parametrize` runs the same assertion across a matrix of inputs without copy-pasting the test body.

```python
import pytest


@pytest.mark.parametrize("raw", ["80", "443", "8080", "65535"])
def test_parses_valid_ports(raw):
    assert parse_port(raw) == int(raw)


@pytest.mark.parametrize("raw", ["-1", "0", "65536", "not-a-number", ""])
def test_rejects_invalid_ports(raw):
    with pytest.raises(ValueError):
        parse_port(raw)


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (100, 10, 90),
        (0, 5, -5),
        (-20, -20, 0),
    ],
)
def test_subtracts_correctly(a, b, expected):
    assert a - b == expected
```

`pytest.raises` asserts a failure mode is a *contract*, not an accident — the test fails loudly if a future change silently stops rejecting invalid input.

---

## Arrange–Act–Assert, One Assertion per Test

Structure every test in three clear sections and name it after the behavior, not the function under test:

```python
def test_withdrawing_more_than_balance_raises_insufficient_funds():
    # Arrange
    account = Account(balance=50)

    # Act + Assert
    with pytest.raises(InsufficientFundsError):
        account.withdraw(100)
```

Prefer one logical assertion (or a tightly related group) per test. A name like `test_withdrawing_more_than_balance_raises_insufficient_funds` reads like a spec — when it fails, you know what broke without opening the test body.

---

## Fixtures for Setup, Test Doubles for Collaborators

pytest fixtures replace repetitive setup and teardown; `monkeypatch` (or `unittest.mock`) replaces collaborators.

```python
import pytest


@pytest.fixture
def gateway(mocker):
    return mocker.Mock(spec=PaymentGateway)


@pytest.fixture
def service(gateway):
    return OrderService(gateway=gateway)


def test_placing_an_order_charges_the_gateway(service, gateway):
    gateway.charge.return_value = ChargeResult(success=True, transaction_id="txn-1")

    result = service.place_order(Order(customer_id="cust-1", amount=49.99))

    assert result.is_successful
    gateway.charge.assert_called_once_with("cust-1", 49.99)


def test_gateway_decline_surfaces_as_order_failure(service, gateway):
    gateway.charge.return_value = ChargeResult(success=False, reason="insufficient funds")

    result = service.place_order(Order(customer_id="cust-1", amount=49.99))

    assert not result.is_successful
```

- **Mock what you own the interface of** — `PaymentGateway` is our own abstraction over a third-party API, so mocking it (with `spec=` to keep the mock honest about the real interface) is appropriate.
- **Don't mock what you don't own.** Patching internals of a third-party library (`monkeypatch.setattr("requests.Session.send", ...)`) couples your tests to that library's implementation and can silently drift from what it actually does. Wrap the dependency behind your own thin interface, then mock that.
- **Prefer a fake for your own seams** when the real behavior is cheap to reproduce — an in-memory dict-backed repository exercises real lookup/insert logic instead of just returning canned values.
- **Over-mocking is the real anti-pattern.** A test that patches five collaborators and asserts every call it made is testing the implementation graph, not the behavior. It breaks on every refactor and proves nothing about correctness. If a test needs that much patching, the function under test is probably doing too much.

---

## Determinism: No Real Clock, Network, or Randomness

A unit test that depends on `datetime.now()`, a live network call, or `random.random()` isn't really a unit test — it's a test that fails on Tuesdays, in CI, or 1% of the time for no visible reason. Inject anything non-deterministic, or patch it explicitly at the boundary, so the test controls it.

```python
from datetime import date


class InvoiceService:
    def __init__(self, clock):
        self._clock = clock  # a callable returning "today"

    def generate(self, order):
        return Invoice(order=order, issued_on=self._clock())


def test_invoice_date_matches_the_fixed_clock():
    fixed_clock = lambda: date(2026, 7, 3)
    service = InvoiceService(clock=fixed_clock)

    invoice = service.generate(Order(id="ord-1"))

    assert invoice.issued_on == date(2026, 7, 3)
```

```python
def test_retry_uses_patched_sleep(monkeypatch):
    sleep_calls = []
    monkeypatch.setattr("time.sleep", lambda seconds: sleep_calls.append(seconds))

    call_with_retry(flaky_operation, max_attempts=3)

    assert len(sleep_calls) == 2  # slept between retries, but the test ran instantly
```

The same applies to network calls (fake or mock the client) and randomness (inject a seeded `random.Random` instance). A suite that is fast, isolated, and repeatable is one you can trust to fail *only* when something is actually broken.

---

## Coverage Is a Signal, Not a Target

A coverage percentage tells you which lines *ran* during the suite — it says nothing about whether the assertions made were meaningful. It's entirely possible to hit 95% line coverage while asserting almost nothing:

```python
# 100% line coverage, zero value: no assertion on the actual result
def test_calls_calculate():
    calculator = DiscountCalculator()
    calculator.apply(order_total=150.0)  # executed, but the return value is never checked
```

Chasing a coverage number as the goal rewards exactly this — tests written to *touch* code rather than to *verify* it. Use `pytest --cov` the way you'd use a linter warning: a prompt to look at what's untested, not a pass/fail gate by itself. A `__repr__` method at 100% coverage is worth less than a 60%-covered parser with real edge-case assertions.

---

## Practical Checklist

| Practice | Why it matters |
|----------|----------------|
| Match test type to what you're verifying (pyramid) | Fast unit tests catch most bugs; fewer, slower tests catch the rest |
| Assert behavior, not internals | Tests survive refactors instead of breaking on them |
| Parametrize input matrices, cover failure modes | Edge cases get exercised, not just the one happy path |
| Arrange–Act–Assert, one assertion per test | Failures point directly at what broke |
| Mock what you own, prefer fakes for your own seams | Avoids drift and over-coupling to third-party internals |
| Inject or patch the clock, network, and randomness | Tests stay fast, isolated, and repeatable |
| Treat coverage as a signal, not a target | High coverage of trivial code isn't a good test suite |

---

## Final Thoughts

A pytest suite earns trust the same way production code does: by being deliberate about what it verifies. Pick the right level for each test, assert the contract instead of the wiring, push failure modes through `parametrize`, keep collaborators honest with fixtures and `monkeypatch` used appropriately, and eliminate non-determinism at the source.

Do that, and a green `pytest` run actually means something — instead of just meaning the tests executed.
