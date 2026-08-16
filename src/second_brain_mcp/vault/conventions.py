"""Pure string conventions — no I/O, no os, no pathlib.

Slug from text, timestamped filename, frontmatter rendering. Not wired to
any tool in this increment; it exists and is unit-tested now so
vault-semantic-tools (increment 4) registers over proven code.
"""

import re
import unicodedata


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


def render_frontmatter(fields: dict[str, str]) -> str:
    """Render YAML frontmatter block.

    >>> render_frontmatter({"source": "voice", "created": "2026-08-16"})
    '---\\nsource: voice\\ncreated: 2026-08-16\\n---'
    """
    lines = ["---"]
    for key, value in fields.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)
