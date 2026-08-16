"""Tests for vault.conventions — pure string functions, no I/O."""

import pytest

from second_brain_mcp.errors import InvalidDomainError
from second_brain_mcp.vault.conventions import (
    CLOSED_DOMAINS,
    format_thought_note,
    render_frontmatter,
    slugify,
    timestamped_filename,
    validate_domain,
)


class TestSlugify:
    def test_simple(self) -> None:
        assert slugify("Hello World") == "hello-world"

    def test_special_chars(self) -> None:
        assert slugify("Hello, World! It's a test") == "hello-world-it-s-a-test"

    def test_unicode(self) -> None:
        assert slugify("Über cool") == "uber-cool"

    def test_max_length(self) -> None:
        result = slugify("a" * 100)
        assert len(result) <= 60

    def test_empty(self) -> None:
        assert slugify("!!!") == ""

    def test_leading_trailing_special(self) -> None:
        assert slugify("---hello---") == "hello"


class TestTimestampedFilename:
    def test_default(self) -> None:
        assert timestamped_filename("my-idea", "2026-08-16-1430") == "2026-08-16-1430-my-idea.md"

    def test_custom_extension(self) -> None:
        result = timestamped_filename("data", "2026-01-01-0000", ".txt")
        assert result == "2026-01-01-0000-data.txt"


class TestRenderFrontmatter:
    def test_basic(self) -> None:
        result = render_frontmatter({"source": "voice", "created": "2026-08-16"})
        assert result == "---\nsource: voice\ncreated: 2026-08-16\n---"

    def test_with_list(self) -> None:
        result = render_frontmatter({"tags": ["type/note", "domain/work"]})
        assert result == "---\ntags: [type/note, domain/work]\n---"


class TestDomainValidation:
    def test_valid_domains(self) -> None:
        for domain in CLOSED_DOMAINS:
            validate_domain(domain)
        validate_domain(None)

    def test_invalid_domain_raises(self) -> None:
        with pytest.raises(InvalidDomainError):
            validate_domain("arbitrary-domain")


class TestFormatThoughtNote:
    def test_format_without_domain(self) -> None:
        content = format_thought_note(
            text="Thinking about modular architecture",
            source="voice",
            created="2026-08-16T14:30",
        )
        assert "created: 2026-08-16T14:30" in content
        assert "source: voice" in content
        assert "status: raw" in content
        assert "tags: [type/note]" in content
        assert content.endswith("\n\nThinking about modular architecture\n")

    def test_format_with_domain(self) -> None:
        content = format_thought_note(
            text="Buying groceries",
            source="text",
            created="2026-08-16T14:30",
            domain="home",
        )
        assert "tags: [type/note, domain/home]" in content

