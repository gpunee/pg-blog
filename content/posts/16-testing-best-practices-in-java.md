---
title: "Testing Best Practices in Java"
date: 2026-07-03
description: "Testing at the right level with JUnit 5 and Mockito, covering the unhappy path with parameterized tests, avoiding over-mocking, and treating coverage as a signal instead of a target."
tags:
  - Java
  - Testing
  - JUnit
  - Software Engineering
categories:
  - Java
draft: false
---

## Introduction

Most Java codebases have plenty of tests and still get burned by production bugs. The problem is rarely *quantity* — it's that the tests exercise the wrong things: they assert internal wiring instead of behavior, they mock away every collaborator until nothing real is left, or they cover the happy path ten times and the failure path zero times.

Good tests are fast, deterministic, and tell you something true about behavior. This post covers the practices that make JUnit 5 and Mockito tests actually earn their keep.

---

## Test at the Right Level: the Pyramid

Not every test should be the same shape. The test pyramid is a rough guide to where effort should go:

- **Unit tests** — the bulk of your suite. Pure logic, no I/O, no framework startup. Milliseconds each.
- **Integration tests** — fewer of these. Verify the *seams*: does your repository actually talk to the real database dialect, does your HTTP client actually parse the real response shape.
- **End-to-end tests** — a handful. Cover the critical user flows through the whole stack, accepting that they're slow and more brittle.

```java
// Unit — pure logic, no Spring context, no database
class DiscountCalculatorTest {

    private final DiscountCalculator calculator = new DiscountCalculator();

    @Test
    void appliesTenPercentForOrdersOverHundred() {
        var total = calculator.apply(new Order(150.0));

        assertEquals(135.0, total, 0.001);
    }
}
```

```java
// Integration — the seam that matters: our SQL against a real database dialect
@SpringBootTest
@Testcontainers
class OrderRepositoryIntegrationTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

    @Autowired
    private OrderRepository repository;

    @Test
    void findsOrdersPlacedInTheLastWeek() {
        repository.save(new Order("ord-1", Instant.now()));

        var recent = repository.findRecentOrders(Duration.ofDays(7));

        assertThat(recent).hasSize(1);
    }
}
```

A unit test suite of a thousand tests that never touches a database runs in seconds and catches most logic bugs. A handful of integration tests catch the ones that only show up at the boundary — the dialect quirk, the serialization mismatch.

---

## Test Behavior, Not Implementation

A test that asserts *how* a method works, rather than *what* it produces, breaks the moment you refactor — even when the behavior is unchanged. That's a test actively working against you.

```java
// DON'T: coupled to implementation details
@Test
void usesArrayListInternally() {
    var service = new OrderService();
    service.addItem("sku-1");

    verify(service.getInternalList()).add("sku-1"); // brittle, meaningless to callers
}

// DO: coupled to the observable contract
@Test
void addingAnItemIncludesItInTheOrderTotal() {
    var service = new OrderService();
    service.addItem("sku-1", 25.0);

    assertEquals(25.0, service.total());
}
```

If you rewrite `OrderService` to use an array, a map, or a different sort order internally, the second test still passes as long as the public contract holds. That's the point: tests should protect behavior, not architecture.

---

## Cover the Unhappy Path with Parameterized Tests

A single happy-path test tells you the code works for one input. Real bugs live at the boundaries — empty input, negative numbers, nulls, malformed strings. `@ParameterizedTest` lets you assert the same behavior across a whole matrix of inputs without duplicating the test body.

```java
class PortParserTest {

    @ParameterizedTest
    @ValueSource(strings = {"80", "443", "8080", "65535"})
    void parsesValidPorts(String raw) {
        assertDoesNotThrow(() -> PortParser.parse(raw));
    }

    @ParameterizedTest
    @ValueSource(strings = {"-1", "0", "65536", "not-a-number", ""})
    void rejectsInvalidPorts(String raw) {
        assertThrows(IllegalArgumentException.class, () -> PortParser.parse(raw));
    }

    @ParameterizedTest
    @CsvSource({
        "100, 10, 90",
        "0, 5, -5",
        "-20, -20, 0"
    })
    void subtractsCorrectly(int a, int b, int expected) {
        assertEquals(expected, a - b);
    }
}
```

`assertThrows` is the tool for asserting a failure mode is a *contract*, not an accident — the test fails loudly if a future change silently stops rejecting invalid input.

---

## Arrange–Act–Assert, One Assertion per Test

Structure every test in three clear sections, and give it a name that states the behavior, not the method under test:

```java
@Test
void withdrawingMoreThanBalanceThrowsInsufficientFundsException() {
    // Arrange
    var account = new Account(BigDecimal.valueOf(50));

    // Act + Assert
    assertThrows(InsufficientFundsException.class,
        () -> account.withdraw(BigDecimal.valueOf(100)));
}
```

Prefer one logical assertion (or one tightly related group) per test. `shouldDoX_whenY` style names read like a spec: when this test fails, its name tells you what broke without opening the body.

---

## Test Doubles: Mock, Stub, Fake — and When Not To

Mockito makes it easy to replace a collaborator, but "easy" is not the same as "correct."

```java
class OrderServiceTest {

    private final PaymentGateway gateway = mock(PaymentGateway.class);
    private final OrderService service = new OrderService(gateway);

    @BeforeEach
    void setUp() {
        // fresh mocks per test — no shared state leaking between tests
    }

    @Test
    void placingAnOrderChargesTheGateway() {
        when(gateway.charge(any(), eq(BigDecimal.valueOf(49.99))))
            .thenReturn(ChargeResult.success("txn-1"));

        var result = service.placeOrder(new Order("cust-1", BigDecimal.valueOf(49.99)));

        assertTrue(result.isSuccessful());
        verify(gateway).charge(eq("cust-1"), eq(BigDecimal.valueOf(49.99)));
    }

    @Test
    void gatewayDeclineSurfacesAsOrderFailure() {
        when(gateway.charge(any(), any())).thenReturn(ChargeResult.declined("insufficient funds"));

        var result = service.placeOrder(new Order("cust-1", BigDecimal.valueOf(49.99)));

        assertFalse(result.isSuccessful());
    }
}
```

- **Mock** what you *own* the interface of — `PaymentGateway` is our own abstraction over a third party, so mocking it is fine.
- **Don't mock what you don't own.** Mocking a third-party library's internal classes couples your tests to that library's implementation details, and the mock can silently drift from what the real library actually does. Wrap the dependency behind your own interface, then mock *that*.
- **Prefer a fake for your own seams** when the real behavior is cheap to reproduce — an in-memory `Map`-backed repository is more honest than a mock that returns canned values, because it actually exercises lookup/insert logic.
- **Over-mocking is the real anti-pattern.** A test that mocks five collaborators and verifies ten interactions is asserting the *implementation graph*, not the behavior. It breaks on every refactor and tells you nothing about correctness. If a test needs that much setup, the class under test probably has too many responsibilities.

---

## Determinism: No Real Clock, Network, or Randomness

A unit test that depends on the wall clock, the network, or `Math.random()` is not really a unit test — it's a test that fails on Tuesdays, or in CI, or 1% of the time for no visible reason. Inject anything non-deterministic so it can be controlled in the test.

```java
public class InvoiceService {
    private final Clock clock;

    public InvoiceService(Clock clock) {
        this.clock = clock;
    }

    public Invoice generate(Order order) {
        return new Invoice(order, LocalDate.now(clock));
    }
}
```

```java
@Test
void invoiceDateMatchesTheFixedClock() {
    var fixedClock = Clock.fixed(Instant.parse("2026-07-03T00:00:00Z"), ZoneOffset.UTC);
    var service = new InvoiceService(fixedClock);

    var invoice = service.generate(new Order("ord-1"));

    assertEquals(LocalDate.of(2026, 7, 3), invoice.date());
}
```

The same applies to network calls (fake or mock the client) and randomness (inject a seeded `Random` or a supplier you control). A test suite that is fast, isolated, and repeatable is one you can trust to fail *only* when something is actually broken.

---

## Coverage Is a Signal, Not a Target

A number on a coverage report tells you which lines *ran* during the suite — it says nothing about whether the right assertions were made. It is entirely possible to hit 95% line coverage while asserting almost nothing meaningful:

```java
// 100% line coverage, zero value: no assertion on the actual result
@Test
void callsCalculate() {
    var calculator = new DiscountCalculator();
    calculator.apply(new Order(150.0)); // executed, but never checked
}
```

Chasing a coverage percentage as the goal incentivizes exactly this: tests written to *touch* code rather than to *verify* it. Use coverage the way you'd use a linter warning — as a prompt to look at what's untested, not as a pass/fail gate on its own. A getter with 100% coverage and no branches is worth less than a 60%-covered parser with real edge-case assertions.

---

## Practical Checklist

| Practice | Why it matters |
|----------|----------------|
| Match test type to what you're verifying (pyramid) | Fast unit tests catch most bugs; fewer, slower tests catch the rest |
| Assert behavior, not internals | Tests survive refactors instead of breaking on them |
| Parameterize input matrices, cover failure modes | Edge cases get exercised, not just the one happy path |
| Arrange–Act–Assert, one assertion per test | Failures point directly at what broke |
| Mock what you own, prefer fakes for your own seams | Avoids drift and over-coupling to third-party internals |
| Inject the clock, network, and randomness | Tests stay fast, isolated, and repeatable |
| Treat coverage as a signal, not a target | High coverage of trivial code isn't a good test suite |

---

## Final Thoughts

A test suite earns trust the same way production code does: by being deliberate about what it verifies. Pick the right level for each test, assert the contract instead of the wiring, push failure modes through parameterized cases, keep collaborators honest with mocks and fakes used appropriately, and eliminate non-determinism at the source.

Do that, and a green build actually means something — instead of just meaning the tests ran.
