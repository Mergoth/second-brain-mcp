"""Tests for vault.conventions — pure string functions, no I/O."""

from second_brain_mcp.vault.conventions import render_frontmatter, slugify, timestamped_filename


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

    def test_empty(self) -> None:
        assert render_frontmatter({}) == "---\n---"
