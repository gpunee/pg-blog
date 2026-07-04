---
title: "Production-Grade Docker Images for Java"
date: 2026-07-03
description: "Multi-stage builds, layered JARs, slim JRE base images, running as non-root, JVM container-awareness, and health checks — how to ship small, secure, fast-starting Java containers."
tags:
  - Java
  - Docker
  - DevOps
  - Containers
categories:
  - Java
draft: false
---

## Introduction

A Java `Dockerfile` can be three lines and technically work — or it can be a 700 MB image that runs as root, rebuilds from scratch on every code change, and gets OOM-killed under load. The difference is a handful of well-understood practices.

This post walks through building Java images that are **small, secure, cache-friendly, and container-aware**.

---

## Start From a Slim, Current JRE — Not a JDK

You need a JDK to *build*, but only a JRE to *run*. Shipping a full JDK bloats the image and widens the attack surface.

```dockerfile
# Runtime base: JRE only, on a slim distro
FROM eclipse-temurin:21-jre-jammy
```

Pin the major version (`21`) and prefer official, maintained images (Eclipse Temurin). Avoid `latest` — reproducible builds require a fixed base.

---

## Use Multi-Stage Builds

A multi-stage build compiles with the full toolchain, then copies only the finished artifact into a clean runtime image. The build tools never ship to production:

```dockerfile
# ---- Build stage ----
FROM eclipse-temurin:21-jdk-jammy AS build
WORKDIR /app
COPY . .
RUN ./mvnw -q -DskipTests package

# ---- Runtime stage ----
FROM eclipse-temurin:21-jre-jammy
WORKDIR /app
COPY --from=build /app/target/app.jar app.jar
ENTRYPOINT ["java", "-jar", "/app.jar"]
```

The final image contains a JRE and one JAR — nothing else.

---

## Layer the JAR for Fast Rebuilds

A fat JAR copied as one file means *any* code change invalidates the whole layer, forcing Docker to re-pull dependencies on every build. Spring Boot's **layered JARs** split dependencies (which rarely change) from your application classes (which change constantly):

```dockerfile
FROM eclipse-temurin:21-jdk-jammy AS build
WORKDIR /app
COPY . .
RUN ./mvnw -q -DskipTests package \
 && java -Djarmode=layertools -jar target/app.jar extract --destination extracted

FROM eclipse-temurin:21-jre-jammy
WORKDIR /app
# Ordered least- to most-frequently changed → maximal cache reuse
COPY --from=build /app/extracted/dependencies/ ./
COPY --from=build /app/extracted/spring-boot-loader/ ./
COPY --from=build /app/extracted/snapshot-dependencies/ ./
COPY --from=build /app/extracted/application/ ./
ENTRYPOINT ["java", "org.springframework.boot.loader.launch.JarLauncher"]
```

Now a code-only change rebuilds a few kilobytes of application layer instead of re-copying hundreds of megabytes of dependencies.

---

## Never Run as Root

By default a container runs as root, so a container escape becomes host root. Create an unprivileged user and drop to it:

```dockerfile
RUN groupadd --system app && useradd --system --gid app app
USER app
```

This is the single highest-value security line in most Java `Dockerfile`s.

---

## Make the JVM Container-Aware

Older JVMs read the *host's* total memory and ignored cgroup limits — then got OOM-killed when they grew past the container's quota. Modern JDKs (11+) respect cgroup limits, but you should still size the heap explicitly relative to the container:

```dockerfile
# Use up to 75% of the container's memory limit for the heap
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75.0", "-jar", "/app.jar"]
```

`-XX:MaxRAMPercentage` scales with whatever memory limit the orchestrator assigns — far safer than a hard-coded `-Xmx` that's wrong the moment the limit changes.

---

## Add a Health Check

Give the orchestrator a way to know the app is actually serving, not just that the process is up. With Spring Boot Actuator:

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD wget -qO- http://localhost:8080/actuator/health | grep -q UP || exit 1
```

In Kubernetes you would use liveness/readiness probes instead, but the principle is identical: expose a real health signal.

---

## Consider GraalVM Native Images for Fast Startup

If cold-start latency or memory footprint is critical (serverless, aggressive autoscaling), a **GraalVM native image** compiles the app ahead of time. It starts in milliseconds and uses a fraction of the memory — at the cost of longer builds and some reflection configuration. Frameworks like Quarkus and Spring Boot 3 support it directly. Reach for it when startup is a real constraint, not by default.

---

## Practical Checklist

| Practice | Payoff |
|----------|--------|
| JRE (not JDK) runtime base | Smaller image, less attack surface |
| Multi-stage build | Build tools never ship |
| Layered JAR | Fast, cache-friendly rebuilds |
| Non-root `USER` | Contains a breakout |
| `-XX:MaxRAMPercentage` | No surprise OOM-kills |
| Health check / probes | Orchestrator knows real state |
| Pinned base image tag | Reproducible builds |

---

## Final Thoughts

A production Java image is a security and operations artifact, not just a way to run a JAR. Ship a slim JRE, build in stages, layer for caching, run as a non-root user, and let the JVM see its real memory limit. None of it is exotic — it is just the difference between an image you can trust in production and one that surprises you at the worst possible time.
