from syndicate.tags import devto_tags


def test_devto_tags_dedupes_aliases_that_collapse_to_the_same_tag():
    tags = ["Java", "Architecture", "Software Design", "SOLID", "Software Engineering"]
    assert devto_tags(tags) == ["java", "architecture", "softwareengineering"]


def test_devto_tags_truncates_to_four_when_five_distinct():
    tags = ["Java", "Docker", "Kubernetes", "Cloud", "Microservices"]
    result = devto_tags(tags)
    assert result == ["java", "docker", "kubernetes", "cloud"]
    assert len(result) == 4


def test_devto_tags_slugifies_unknown_tags_with_spaces_and_special_chars():
    tags = ["Rust!", "Go Lang", "C++"]
    assert devto_tags(tags) == ["rust", "golang", "c"]


def test_devto_tags_ai_family_dedupes_to_two_llm_tags():
    tags = ["Java", "AI", "Agentic", "LLM", "Anthropic"]
    assert devto_tags(tags) == ["java", "ai", "llm"]


def test_devto_tags_empty_input_returns_empty_list():
    assert devto_tags([]) == []


def test_devto_tags_drops_empty_slugified_result():
    # A tag that is entirely non-alphanumeric slugifies to "" and is dropped.
    tags = ["Java", "***", "Testing"]
    assert devto_tags(tags) == ["java", "testing"]


def test_devto_tags_preserves_input_order_language_discipline_specific():
    tags = ["Python", "Testing", "pytest"]
    # pytest -> testing, a dup of Testing -> testing; dedup keeps first.
    assert devto_tags(tags) == ["python", "testing"]
