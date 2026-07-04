---
title: "Designing for Change: Boundaries, Contracts, and Dependency Inversion in Python"
date: 2026-07-03
description: "Isolating what varies with Protocols and constructor injection, structuring a ports-and-adapters core, and using frozen dataclasses to make invalid states unrepresentable in Python — with no framework required."
tags:
  - Python
  - Architecture
  - Software Design
  - SOLID
  - Software Engineering
categories:
  - Python
draft: false
---

## Introduction

Python's flexibility makes it easy to wire everything together directly — call the `requests` library from inside your business logic, import the ORM model straight into your pricing rules, instantiate a third-party SDK client wherever it's needed. It works, right up until the payment provider changes, or you want a fast unit test that doesn't need a live database.

Designing for change means drawing boundaries around the parts of the system likely to move — third-party services, storage, transport — so that a swap or a test double touches one small adapter instead of rippling through the codebase.

This post covers the practical mechanics in Python: `Protocol` and `ABC` for dependency inversion, a ports-and-adapters shape for a small service, and frozen dataclasses that make invalid states impossible to construct. Python needs no framework for any of it.

---

## Coupling, Cohesion, and the Cost of Guessing Wrong

**Coupling** is how much one module knows about another's internals; **cohesion** is how tightly a module's own responsibilities hang together. The classic mistake is coupling business logic directly to something volatile because it's the fastest way to get a feature working:

```python
# Tightly coupled: checkout() cannot run, or be tested, without a live Stripe account
import stripe

stripe.api_key = os.environ["STRIPE_KEY"]

def checkout(order: Order) -> None:
    stripe.Charge.create(amount=order.total_cents, currency="usd")
    # ...
```

This ships fast — but adding a second payment provider, unit-testing `checkout` without the network, or absorbing a breaking SDK change all become edits to `checkout` itself, not an isolated adapter swap.

The fix isn't "wrap everything in an abstraction." It's abstracting specifically at the seams likely to vary — I/O, third-party services, storage — and leaving pure computation (a discount calculation, a tax rule) as plain functions with no interface at all, because there's no second implementation and nothing to swap.

---

## Dependency Inversion Without a Framework: `Protocol` and `ABC`

Python offers two idiomatic ways to define a contract the core code depends on, instead of a concrete implementation.

**`typing.Protocol`** gives you *structural* typing — anything with the right method shape satisfies the contract, with no inheritance required:

```python
from typing import Protocol

class PaymentGateway(Protocol):
    def charge(self, amount: "Money", customer_reference: str) -> "PaymentResult": ...
```

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Money:
    amount_minor_units: int
    currency_code: str

    def __post_init__(self) -> None:
        if self.amount_minor_units < 0:
            raise ValueError(f"amount cannot be negative: {self.amount_minor_units}")
        if len(self.currency_code) != 3:
            raise ValueError(f"currency_code must be a 3-letter ISO code: {self.currency_code!r}")

@dataclass(frozen=True)
class PaymentResult:
    approved: bool
    provider_reference: str
```

A concrete adapter — the only place that imports the third-party SDK — satisfies the `Protocol` just by having a matching `charge` method, with no explicit `implements`:

```python
class StripePaymentGateway:
    def __init__(self, client: "stripe.Client") -> None:
        self._client = client

    def charge(self, amount: Money, customer_reference: str) -> PaymentResult:
        result = self._client.charges.create(
            amount=amount.amount_minor_units, currency=amount.currency_code
        )
        return PaymentResult(approved=result.is_successful, provider_reference=result.id)
```

The core depends only on the `Protocol`, injected through the constructor:

```python
class OrderService:
    def __init__(self, payment_gateway: PaymentGateway) -> None:
        self._payment_gateway = payment_gateway

    def checkout(self, order: "Order") -> PaymentResult:
        amount = Money(order.total_minor_units, order.currency_code)
        return self._payment_gateway.charge(amount, order.customer_id)
```

`OrderService` never imports `stripe`. A test can pass any object with a matching `charge` method — a plain function, a lambda-like callable, or a hand-written fake — with zero mocking framework and zero inheritance:

```python
class FakeGateway:
    def charge(self, amount: Money, customer_reference: str) -> PaymentResult:
        return PaymentResult(approved=True, provider_reference="fake-1")

def test_checkout_returns_approved_result() -> None:
    service = OrderService(payment_gateway=FakeGateway())
    order = Order(order_id="ord-1", customer_id="cust-1", total_minor_units=1999, currency_code="USD")

    result = service.checkout(order)

    assert result.approved is True
```

If you'd rather force implementers to explicitly opt in (nominal typing, useful when the contract carries real behavioral guarantees beyond method shape), `abc.ABC` is the alternative:

```python
from abc import ABC, abstractmethod

class PaymentGatewayABC(ABC):
    @abstractmethod
    def charge(self, amount: Money, customer_reference: str) -> PaymentResult: ...
```

Either way, no framework is involved — this is constructor injection with plain Python objects. A framework like FastAPI's `Depends` or a DI container can automate the *wiring*, but the design decision (`OrderService` depends on an abstraction, not a concrete SDK) holds with or without one.

---

## Ports and Adapters: The Domain Core Stays Framework-Free

The same idea structures a whole service: a domain core that defines *ports* (Protocols) for what it needs, and *adapters* at the edges that implement those ports against real infrastructure.

```python
from typing import Protocol, Optional

class OrderRepository(Protocol):
    def find_by_id(self, order_id: str) -> Optional["Order"]: ...
    def save(self, order: "Order") -> None: ...
```

```python
# Domain core: depends only on the ports, knows nothing about SQL or the ORM
class OrderProcessor:
    def __init__(self, repository: OrderRepository, payment_gateway: PaymentGateway) -> None:
        self._repository = repository
        self._payment_gateway = payment_gateway

    def process_payment(self, order_id: str) -> PaymentResult:
        order = self._repository.find_by_id(order_id)
        if order is None:
            raise LookupError(f"no order with id {order_id}")

        result = self._payment_gateway.charge(
            Money(order.total_minor_units, order.currency_code), order.customer_id
        )
        if result.approved:
            self._repository.save(order.mark_paid())
        return result
```

An in-memory adapter makes the core trivially testable — no database, no fixtures, no test containers:

```python
class InMemoryOrderRepository:
    def __init__(self) -> None:
        self._store: dict[str, Order] = {}

    def find_by_id(self, order_id: str) -> Optional[Order]:
        return self._store.get(order_id)

    def save(self, order: Order) -> None:
        self._store[order.order_id] = order
```

```python
def test_process_payment_marks_order_paid_when_charge_approved() -> None:
    repository = InMemoryOrderRepository()
    repository.save(Order("ord-1", "cust-1", 1999, "USD", paid=False))
    processor = OrderProcessor(repository=repository, payment_gateway=FakeGateway())

    result = processor.process_payment("ord-1")

    assert result.approved is True
    assert repository.find_by_id("ord-1").paid is True
```

A production adapter — `SqlAlchemyOrderRepository`, backed by a real session — implements the same `OrderRepository` shape and is wired in only at the application's composition root (where the app starts up), never imported by name inside `OrderProcessor`:

```
        ┌─────────────────────────────┐
        │        Domain Core          │
        │  OrderProcessor, Order,     │
        │  Money  (no I/O imports)    │
        └───────────┬─────────────────┘
                     │ depends on (ports/Protocols)
        ┌────────────┴─────────────┐
        │ OrderRepository           │  PaymentGateway
        └───┬───────────────┬──────┘
            │               │
   InMemoryOrderRepository  StripePaymentGateway   (adapters, at the edges)
   SqlAlchemyOrderRepository
```

---

## Make Invalid States Unrepresentable

`Money` above already does this: `frozen=True` makes it immutable after construction, and `__post_init__` runs its validation on the *only* path an instance can come into existence — there's no setter later that could skip the check.

Extend that to state transitions with an `Enum` instead of a loose `status: str` or a `paid: bool` flag that fails to capture "cancelled" at all:

```python
from dataclasses import dataclass, replace
from enum import Enum, auto

class OrderStatus(Enum):
    PENDING = auto()
    PAID = auto()
    CANCELLED = auto()

@dataclass(frozen=True)
class Order:
    order_id: str
    customer_id: str
    total_minor_units: int
    currency_code: str
    status: OrderStatus = OrderStatus.PENDING

    def mark_paid(self) -> "Order":
        if self.status is not OrderStatus.PENDING:
            raise ValueError(f"cannot mark paid from status {self.status.name}")
        return replace(self, status=OrderStatus.PAID)
```

`mark_paid` returns a *new* `Order` rather than mutating in place — combined with `frozen=True`, an `Order` object can never silently drift into an inconsistent state from some far-away code path holding a reference to it. The guard clause makes the illegal transition (paying an already-cancelled order) raise immediately rather than corrupt state quietly.

For a stricter, type-checker-enforced version of the same idea, a small tagged union of dataclasses (mirroring the sealed-type pattern) works too — but for most services, a validated `Enum` plus a guarded transition method is the pragmatic default; reach for the union when different statuses genuinely carry different data (e.g., only a `Cancelled` variant has a `reason` field).

---

## When Not to Do This

Every `Protocol`, every extra layer of indirection, has a cost: more files to open when tracing a call, and the real risk of **premature abstraction** — building a seam for a second implementation that never shows up.

Don't add a `Protocol` for:
- A small, stable, in-house helper with no plausible second implementation and no test-isolation pressure.
- Pure functions (formatting, arithmetic, validation rules) with no I/O — there's nothing to swap.
- A prototype or one-off script where the entire point is learning fast, not building for reuse.

The signal a seam is worth it: you already have, or clearly will have, a second implementation — or the boundary is genuinely volatile I/O (a paid API, a datastore, a queue). Absent either, an interface is speculative generality: extra indirection for a change that may never come, making the one real implementation harder to read for no offsetting benefit.

---

## Practical Takeaways

| Practice | Why it matters |
|----------|-----------------|
| Depend on `Protocol`/`ABC` at I/O boundaries, not concrete SDKs | Swapping a provider touches one adapter, not the core |
| Inject dependencies through `__init__`, no framework required | Dependencies are explicit and easy to fake in tests |
| Keep the domain core free of SDK/ORM imports | The core stays portable and fast to test |
| Give every port an in-memory adapter for tests | Unit tests run with no network, no database |
| Validate in `__post_init__` on frozen dataclasses | Invalid objects simply cannot exist |
| Model state with `Enum` + guarded transitions (or tagged unions) | Illegal transitions raise instead of corrupting state |
| Don't add a `Protocol` with no second implementation | Premature abstraction costs more than it saves |

Designing for change is a bet on *where* things will vary, not a guarantee against all future work. Spend the abstraction budget at the boundaries most likely to move — third-party services, storage, transport — and leave the stable, purely internal logic simple, direct, and framework-free.
