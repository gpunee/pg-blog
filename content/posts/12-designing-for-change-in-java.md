---
title: "Designing for Change: Boundaries, Contracts, and Dependency Inversion in Java"
date: 2026-07-03
description: "Isolating what varies with interfaces and constructor injection, structuring a ports-and-adapters core, and using records to make invalid states unrepresentable in Java — without over-abstracting."
tags:
  - Java
  - Architecture
  - Software Design
  - SOLID
  - Software Engineering
categories:
  - Java
draft: false
---

## Introduction

Most Java systems don't fail because a single class was written badly. They fail because the *boundaries* between classes were drawn in the wrong place — a database library leaks into business logic, a payment provider's SDK shows up in twelve unrelated files, and changing one third-party dependency means touching half the codebase.

Designing for change is not about predicting the future correctly. It's about **isolating what varies** so that when it inevitably does vary — a new payment provider, a swapped database, a different message broker — the blast radius is one adapter, not the whole system.

This post covers the practical mechanics: dependency inversion, ports-and-adapters, and making illegal states impossible to construct — plus where to stop.

---

## Coupling, Cohesion, and the Cost of Guessing Wrong

Two forces pull against each other in every design:

- **Coupling** — how much one module knows about another's internals. Low coupling means you can change a module without rippling changes elsewhere.
- **Cohesion** — how tightly a module's responsibilities belong together. High cohesion means a class has one clear reason to change.

The classic mistake is coupling business logic directly to volatile, external things — HTTP clients, ORMs, cloud SDKs — because that's the fastest way to get something working:

```java
// Tightly coupled: OrderService cannot exist without Stripe's SDK
public class OrderService {
    private final StripeClient stripeClient = new StripeClient(System.getenv("STRIPE_KEY"));

    public void checkout(Order order) {
        stripeClient.charges().create(order.totalCents(), "usd");
        // ...
    }
}
```

This compiles, ships, and works — until you need to add a second payment provider, or write a test without hitting the network, or the SDK does a breaking major-version bump. Every one of those becomes a rewrite of `OrderService` itself, not an isolated change.

The fix is not "add an abstraction for everything." It's to abstract specifically at the seams that are *likely to vary*: I/O, third-party services, storage. A pure computation with no external dependency (tax calculation, discount rules) usually doesn't need an interface at all — that would be an abstraction with no second implementation and no real caller-side benefit, just extra indirection to read through.

---

## Dependency Inversion: Program to an Interface

The Dependency Inversion Principle says high-level policy (the order workflow) should not depend on low-level detail (a specific payment SDK). Both should depend on an abstraction owned by the high-level side:

```java
// The core defines the contract it needs — no import of any SDK
public interface PaymentGateway {
    PaymentResult charge(Money amount, String customerReference);
}
```

```java
public record Money(long amountMinorUnits, String currencyCode) {
    public Money {
        if (amountMinorUnits < 0) {
            throw new IllegalArgumentException("amount cannot be negative: " + amountMinorUnits);
        }
        if (currencyCode == null || currencyCode.length() != 3) {
            throw new IllegalArgumentException("currencyCode must be a 3-letter ISO code: " + currencyCode);
        }
    }
}

public record PaymentResult(boolean approved, String providerReference) {}
```

A concrete adapter implements the interface and is the *only* place that imports the third-party SDK:

```java
public final class StripePaymentGateway implements PaymentGateway {
    private final StripeClient client;

    public StripePaymentGateway(StripeClient client) {
        this.client = client;
    }

    @Override
    public PaymentResult charge(Money amount, String customerReference) {
        var charge = client.charges().create(amount.amountMinorUnits(), amount.currencyCode());
        return new PaymentResult(charge.isSuccessful(), charge.id());
    }
}
```

The order workflow now depends only on the interface, injected through its constructor:

```java
public final class OrderService {
    private final PaymentGateway paymentGateway;

    // Constructor injection: the dependency is explicit, required, and immutable
    public OrderService(PaymentGateway paymentGateway) {
        this.paymentGateway = paymentGateway;
    }

    public PaymentResult checkout(Order order) {
        var amount = new Money(order.totalMinorUnits(), order.currencyCode());
        return paymentGateway.charge(amount, order.customerId());
    }
}
```

`OrderService` compiles and runs with zero knowledge of Stripe, a competitor's SDK, or a fake used in tests. Swapping providers means writing one new adapter class — `OrderService` never changes.

A framework like Spring can wire `new StripePaymentGateway(...)` into `OrderService`'s constructor automatically via `@Bean`/`@Autowired`, but nothing above requires it — this is plain constructor injection, and you could wire it by hand in a `main` method just as validly. The design decision (depend on the interface) is independent of whether a DI container does the wiring.

---

## Ports and Adapters: The Domain Core Stays Framework-Free

Zoom out from a single dependency and the same idea structures the whole application: a **domain core** in the center that defines *ports* (interfaces) for everything it needs from the outside world, and *adapters* at the edges that implement those ports against real infrastructure.

```java
// Port — owned by the domain, expresses what the domain needs, not how storage works
public interface OrderRepository {
    Optional<Order> findById(String orderId);
    void save(Order order);
}
```

```java
// Domain core: depends only on the port, knows nothing about SQL or JDBC
public final class OrderProcessor {
    private final OrderRepository repository;
    private final PaymentGateway paymentGateway;

    public OrderProcessor(OrderRepository repository, PaymentGateway paymentGateway) {
        this.repository = repository;
        this.paymentGateway = paymentGateway;
    }

    public PaymentResult processPayment(String orderId) {
        var order = repository.findById(orderId)
            .orElseThrow(() -> new NoSuchElementException("no order with id " + orderId));
        var result = paymentGateway.charge(
            new Money(order.totalMinorUnits(), order.currencyCode()), order.customerId());
        if (result.approved()) {
            repository.save(order.markPaid());
        }
        return result;
    }
}
```

An in-memory adapter makes the core trivially testable, with no database and no test containers:

```java
public final class InMemoryOrderRepository implements OrderRepository {
    private final Map<String, Order> store = new HashMap<>();

    @Override
    public Optional<Order> findById(String orderId) {
        return Optional.ofNullable(store.get(orderId));
    }

    @Override
    public void save(Order order) {
        store.put(order.orderId(), order);
    }
}
```

```java
@Test
void processPayment_marksOrderPaid_whenChargeApproved() {
    var repository = new InMemoryOrderRepository();
    repository.save(new Order("ord-1", "cust-1", 1999, "USD", false));
    var processor = new OrderProcessor(repository, (amount, ref) -> new PaymentResult(true, "px_1"));

    var result = processor.processPayment("ord-1");

    assertTrue(result.approved());
    assertTrue(repository.findById("ord-1").orElseThrow().paid());
}
```

Notice the test passes a **lambda** as the `PaymentGateway` — since it's a single-method interface, no mocking framework is required for this seam. A production adapter (`JdbcOrderRepository`, backed by a real `DataSource`) implements the same `OrderRepository` port and is wired in only at the application's composition root (`main`, or a Spring `@Configuration` class) — never referenced by name inside `OrderProcessor`.

```
        ┌─────────────────────────────┐
        │        Domain Core          │
        │   OrderProcessor, Order,    │
        │   Money  (no I/O imports)   │
        └───────────┬─────────────────┘
                     │ depends on (ports)
        ┌────────────┴─────────────┐
        │ OrderRepository           │  PaymentGateway
        └───┬───────────────┬──────┘
            │               │
   InMemoryOrderRepository  StripePaymentGateway   (adapters, at the edges)
   JdbcOrderRepository
```

---

## Make Invalid States Unrepresentable

The `Money` record above already does this: it is impossible to construct a `Money` with a negative amount or a malformed currency code, because the compact constructor validates on every construction path — there is no way to get an instance into an invalid state later. Compare that to a class with a public setter for `amount` that some far-away code path forgets to validate.

Sealed hierarchies extend the same idea to *state transitions*. An order shouldn't be payable twice, and a cancelled order shouldn't be payable at all — encode that in the type instead of a boolean flag and scattered `if` checks:

```java
public sealed interface OrderStatus permits Pending, Paid, Cancelled {}
public record Pending() implements OrderStatus {}
public record Paid(String providerReference) implements OrderStatus {}
public record Cancelled(String reason) implements OrderStatus {}

public PaymentResult processPayment(Order order, PaymentGateway gateway) {
    return switch (order.status()) {
        case Paid p -> throw new IllegalStateException("order already paid: " + p.providerReference());
        case Cancelled c -> throw new IllegalStateException("order cancelled: " + c.reason());
        case Pending p -> gateway.charge(order.amount(), order.customerId());
    };
}
```

The `switch` over a sealed interface is exhaustive — the compiler rejects the code if a fourth `OrderStatus` variant is ever added and this method isn't updated. A `boolean isPaid` field offers no such guarantee; it's easy to leave a call site unhandled.

---

## When Not to Do This

Every interface, every port, every extra layer has a cost: more files to navigate, more indirection to trace through when reading the code, and a real risk of **premature abstraction** — building a seam for a second implementation that never arrives.

Don't introduce a `PaymentGateway`-style interface for:
- A single, stable, in-house utility with no plausible second implementation and no test-isolation need.
- Pure logic (tax rules, string formatting) that has no I/O and nothing to swap.
- A prototype or spike where the entire point is to learn something before committing to a design.

The signal that a seam is *earning its keep* is concrete: you have (or clearly will have) a second implementation, or the boundary is exactly the kind of volatile I/O this post is about (a paid third-party service, a datastore, a queue). Abstracting "in case we need it later" without either of those is speculative generality — it adds a layer of indirection for a change that may never come, and makes the one implementation you do have harder to read for no offsetting benefit.

---

## Practical Takeaways

| Practice | Why it matters |
|----------|-----------------|
| Depend on interfaces at I/O boundaries, not concrete SDKs | Swapping a provider touches one adapter, not the core |
| Inject dependencies through the constructor | Dependencies are explicit, required, and easy to fake in tests |
| Keep the domain core free of framework/SDK imports | The core stays portable and fast to test |
| Give every port an in-memory adapter for tests | Unit tests run with no network, no database |
| Validate in constructors (records, compact constructors) | Invalid objects simply cannot exist |
| Model state transitions with sealed types, not booleans | The compiler enforces exhaustive handling |
| Don't abstract a seam with no second implementation | Premature abstraction costs more than it saves |

Designing for change is a bet on *where* things will vary, not a guarantee against all future work. Spend the abstraction budget at the boundaries most likely to move — third-party services, storage, transport — and leave the stable, purely internal logic simple and direct.
