"""Map the blog's front-matter tags to Dev.to-valid tags.

Dev.to tags must be lowercase, alphanumeric-only, and a post may carry at
most 4. Pure function, no network.
"""

from __future__ import annotations

import re

MAX_TAGS = 4

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]")

# Exact alias map: our tag (as written in front matter) -> Dev.to tag.
_ALIASES: dict[str, str] = {
    "Java": "java",
    "Python": "python",
    "JVM": "java",
    "Kotlin": "kotlin",
    "Scala": "scala",
    "Software Engineering": "softwareengineering",
    "Programming Languages": "programming",
    "Backend": "backend",
    "Architecture": "architecture",
    "Software Design": "architecture",
    "SOLID": "architecture",
    "Error Handling": "errorhandling",
    "Exceptions": "errorhandling",
    "Testing": "testing",
    "JUnit": "testing",
    "pytest": "testing",
    "Databases": "database",
    "Indexing": "database",
    "ORM": "database",
    "JPA": "database",
    "Hibernate": "database",
    "SQLAlchemy": "database",
    "SQL": "sql",
    "Django": "django",
    "Docker": "docker",
    "Containers": "docker",
    "DevOps": "devops",
    "Kubernetes": "kubernetes",
    "Cloud": "cloud",
    "Microservices": "microservices",
    "AI": "ai",
    "Agentic": "ai",
    "Anthropic": "ai",
    "LLM": "llm",
    "Performance": "performance",
}


def _slugify(tag: str) -> str:
    """Fallback slugification for any tag not in the alias map: lowercase,
    strip anything that isn't a-z/0-9.
    """
    return _NON_ALNUM_RE.sub("", tag.lower())


def devto_tags(tags: list[str]) -> list[str]:
    """Map our ordered tags (language -> discipline -> specific) to Dev.to
    tags: alias-mapped or slugified, deduped (first occurrence wins, input
    order preserved), empty results dropped, then truncated to the first
    `MAX_TAGS`.
    """
    result: list[str] = []
    for tag in tags:
        mapped = _ALIASES.get(tag, _slugify(tag))
        if not mapped:
            continue
        if mapped in result:
            continue
        result.append(mapped)

    return result[:MAX_TAGS]
