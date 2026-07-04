---
title: "Production-Grade Docker Images for Python"
date: 2026-07-03
description: "Slim base images, multi-stage builds with virtual environments, layer-cached dependency installs, running as non-root, and correct signal handling for small, secure Python containers."
tags:
  - Python
  - Docker
  - DevOps
  - Containers
categories:
  - Python
draft: false
---

## Introduction

The typical first-draft Python `Dockerfile` — `FROM python`, `COPY . .`, `pip install -r requirements.txt` — produces an image that is close to a gigabyte, reinstalls every dependency whenever a single source file changes, and runs as root with a Python process that ignores `SIGTERM`.

This post covers how to fix all of that: **small images, cached dependency installs, a non-root runtime, and clean shutdowns.**

---

## Pick the Right Base Image

`python:3.12-slim` is the pragmatic default: a Debian-based image with Python but without the large build toolchain. Avoid the full `python:3.12` (hundreds of MB of tools you don't run) and be cautious with `alpine` — its `musl` libc frequently breaks or slows down packages with C extensions (NumPy, pandas, database drivers), forcing slow source builds.

```dockerfile
FROM python:3.12-slim
```

Pin the version. `latest` is not a reproducible build.

---

## Order Layers So Dependencies Cache

Docker caches each layer and invalidates everything after the first change. If you `COPY . .` before installing dependencies, every code edit busts the dependency layer and reinstalls everything. Copy the requirements first:

```dockerfile
WORKDIR /app

# Copy ONLY the dependency manifest first — this layer caches until deps change
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy source — code changes only invalidate from here down
COPY . .
```

`--no-cache-dir` stops `pip` from keeping its download cache inside the image, shaving off tens of megabytes.

---

## Use Multi-Stage Builds for a Clean Runtime

Packages with C extensions need compilers (`gcc`, headers) to *build* but not to *run*. A multi-stage build compiles wheels in a fat builder stage, then copies only the installed environment into a slim runtime:

```dockerfile
# ---- Build stage ----
FROM python:3.12-slim AS build
WORKDIR /app
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"
RUN apt-get update && apt-get install -y --no-install-recommends gcc
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Runtime stage ----
FROM python:3.12-slim
COPY --from=build /venv /venv
ENV PATH="/venv/bin:$PATH"
WORKDIR /app
COPY . .
CMD ["python", "-m", "myapp"]
```

The runtime image gets the ready-made virtual environment but never the compilers — smaller and with a narrower attack surface.

---

## Set Python's Container Environment Variables

Two settings matter in every Python container:

```dockerfile
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
```

- `PYTHONUNBUFFERED=1` — flush stdout/stderr immediately so your logs actually appear in `docker logs` and your log aggregator in real time, instead of being buffered until the process exits.
- `PYTHONDONTWRITEBYTECODE=1` — skip writing `.pyc` files you'll never reuse in an immutable container.

---

## Never Run as Root

As with any container, drop to an unprivileged user so a breakout doesn't hand over host root:

```dockerfile
RUN useradd --create-home --system appuser
USER appuser
```

Place this after installing dependencies (which may need root) but before the `CMD`.

---

## Handle Signals: Don't Let PID 1 Ignore SIGTERM

When an orchestrator stops a container it sends `SIGTERM`, waits, then `SIGKILL`s. A Python process running as PID 1 does not get the default signal handlers, so a naive setup ignores `SIGTERM` and every shutdown takes the full grace period before a hard kill — dropping in-flight requests.

For web apps, run a proper server (Gunicorn/Uvicorn) that manages workers and forwards signals. For a bare script, add a lightweight init like `tini`:

```dockerfile
# tini becomes PID 1 and forwards signals to your process
ENTRYPOINT ["tini", "--"]
CMD ["python", "-m", "myapp"]
```

This gives you fast, graceful shutdowns instead of a 30-second stall on every deploy.

---

## Add a Health Check

Expose and probe a real readiness signal so the orchestrator routes traffic only when the app can serve:

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
```

In Kubernetes, prefer native liveness/readiness probes — same idea, better integration.

---

## Practical Checklist

| Practice | Payoff |
|----------|--------|
| `python:3.12-slim`, pinned | Small, reproducible, C-ext friendly |
| Copy `requirements.txt` first | Dependency layer caches |
| `pip install --no-cache-dir` | Smaller image |
| Multi-stage with a venv | No compilers in runtime |
| `PYTHONUNBUFFERED=1` | Logs appear in real time |
| Non-root `USER` | Contains a breakout |
| `tini` / real server as PID 1 | Graceful `SIGTERM` shutdown |
| Health check / probes | Traffic only when ready |

---

## Final Thoughts

A good Python image is mostly about ordering and restraint: install dependencies before copying code so caching works, keep build tools out of the runtime, unbuffer your logs, run as a non-root user, and make sure PID 1 actually handles signals. Each is a few lines — together they turn a slow, bloated, root-running container into one you can deploy dozens of times a day without thinking about it.
