"""Pure string conventions — no I/O, no os, no pathlib.

Slug from text, timestamped filename, frontmatter rendering, thought note formatting,
and domain validation against the closed domain list.
"""

import re
import unicodedata
from typing import Any

from second_brain_mcp.errors import InvalidDomainError

CLOSED_DOMAINS: frozenset[str] = frozenset({
    "work",
    "finance",
    "legal",
    "health",
    "trips",
    "home",
    "plants",
    "smart-home",
    "projects",
    "learning",
})


def validate_domain(domain: str | None) -> None:
    """Assert that a domain belongs to the closed list.

    Raises InvalidDomainError if domain is not recognized.
    """
    if domain is not None and domain not in CLOSED_DOMAINS:
        raise InvalidDomainError(
            f"domain {domain!r} is not in closed domain list: {sorted(CLOSED_DOMAINS)}"
        )


def slugify(text: str, max_length: int = 60) -> str:
    """Turn arbitrary text into a URL/filename-safe slug.

    >>> slugify("Hello, World! It's a test")
    'hello-world-it-s-a-test'
    """
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    if len(text) > max_length:
        text = text[:max_length].rstrip("-")
    return text


def timestamped_filename(slug: str, timestamp: str, extension: str = ".md") -> str:
    """Build a timestamped filename for raw/thoughts.

    >>> timestamped_filename("my-idea", "2026-08-16-1430")
    '2026-08-16-1430-my-idea.md'
    """
    return f"{timestamp}-{slug}{extension}"


def build_thought_filename(text: str, timestamp: str) -> str:
    """Build a timestamped thought filename from text and timestamp."""
    slug = slugify(text)
    if not slug:
        slug = "thought"
    return timestamped_filename(slug, timestamp)


def render_frontmatter(fields: dict[str, Any]) -> str:
    """Render YAML frontmatter block.

    >>> render_frontmatter({"source": "voice", "created": "2026-08-16"})
    '---\\nsource: voice\\ncreated: 2026-08-16\\n---'
    """
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, (list, tuple)):
            lines.append(f"{key}: [{', '.join(str(v) for v in value)}]")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def format_thought_note(
    text: str, source: str, created: str, domain: str | None = None
) -> str:
    """Render full thought note content with frontmatter and body."""
    tags = ["type/note"]
    if domain is not None:
        validate_domain(domain)
        tags.append(f"domain/{domain}")

    frontmatter = render_frontmatter({
        "created": created,
        "source": source,
        "status": "raw",
        "tags": tags,
    })
    return f"{frontmatter}\n\n{text}\n"

