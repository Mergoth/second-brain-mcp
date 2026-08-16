"""Semantic MCP tool adapters — encode vault filing conventions in code.

Composes vault.store and vault.conventions (and vault.tasks), never each other,
and never imports primitives.py (ADR-0004 territory).
Every path passes through vault.paths.resolve() (ADR-0002).
"""

import datetime
from typing import Any

from second_brain_mcp.vault import conventions, paths, store, tasks


def capture_thought(text: str, source: str, domain: str | None = None) -> str:
    """Capture a raw thought note to raw/thoughts/YYYY-MM-DD-HHMM-<slug>.md.

    Enforces closed domain list and writes YAML frontmatter with created timestamp.
    """
    if domain is not None:
        conventions.validate_domain(domain)

    now = datetime.datetime.now(datetime.UTC).astimezone()
    timestamp_filename = now.strftime("%Y-%m-%d-%H%M")
    timestamp_created = now.strftime("%Y-%m-%dT%H:%M")

    filename = conventions.build_thought_filename(text, timestamp_filename)
    rel_path = f"raw/thoughts/{filename}"
    resolved = paths.resolve(rel_path)

    content = conventions.format_thought_note(
        text=text,
        source=source,
        created=timestamp_created,
        domain=domain,
    )

    store.write_note(resolved, content, mode="create")
    return rel_path


def list_task_sections() -> list[str]:
    """Read Tasks.md live and return all '## ' section headers."""
    resolved = paths.resolve("Tasks.md")
    content = store.read_note(resolved)
    return tasks.parse_sections(content)


def add_task(
    text: str,
    section: str,
    priority: str | None = None,
    due: str | None = None,
    link: str | None = None,
) -> str:
    """Add a task under an existing section in Tasks.md.

    Never invents date or priority. Reports added markers in the returned result.
    Raises TaskSectionNotFoundError listing available sections if section is not found.
    """
    resolved = paths.resolve("Tasks.md")
    content = store.read_note(resolved)

    task_line = tasks.format_task(text=text, priority=priority, due=due, link=link)
    matched_section, updated_content = tasks.insert_task_into_section(
        content=content,
        section=section,
        task_line=task_line,
    )

    store.write_note(resolved, updated_content, mode="overwrite")
    return f"Added task to '{matched_section}': {task_line}"


def get_tasks(filter: str | None = None) -> list[dict[str, Any]]:
    """Parse Tasks.md into structured tasks, flagging overdue items proactively.

    Optional filter: 'pending', 'completed', 'overdue', 'all', or section name.
    """
    resolved = paths.resolve("Tasks.md")
    content = store.read_note(resolved)
    all_tasks = tasks.parse_tasks(content)
    return tasks.filter_tasks(all_tasks, filter_by=filter)


def append_log(line: str) -> str:
    """Append an entry to meta/log.md. Enforces append-only write mode."""
    resolved = paths.resolve("meta/log.md")
    entry = line if line.endswith("\n") else f"{line}\n"

    store.write_note(resolved, entry, mode="append")
    return f"Appended to meta/log.md: {entry.strip()}"
