"""Task parsing, formatting, and section manipulation for Tasks.md.

Obsidian-tasks syntax:
- Checkbox: - [ ] (pending) or - [x] / - [X] (completed)
- Priority: ⏫ (urgent), 🔼 (high), ⏬ (low), 🔽 (lowest)
- Due date: 📅 YYYY-MM-DD
- Done date: ✅ YYYY-MM-DD
- Note link: [[Note]]

Sections are live ## headers in Tasks.md. They are never hardcoded.
"""

import datetime
import re
from typing import Any

from second_brain_mcp.errors import TaskSectionNotFoundError, TaskValidationError

PRIORITY_TO_EMOJI: dict[str, str] = {
    "urgent": "⏫",
    "high": "🔼",
    "low": "⏬",
    "lowest": "🔽",
    "⏫": "⏫",
    "🔼": "🔼",
    "⏬": "⏬",
    "🔽": "🔽",
}

EMOJI_TO_PRIORITY: dict[str, str] = {
    "⏫": "urgent",
    "🔼": "high",
    "⏬": "low",
    "🔽": "lowest",
}


def parse_sections(content: str) -> list[str]:
    """Extract section names from markdown '## ' headers in content."""
    sections: list[str] = []
    for line in content.splitlines():
        if line.startswith("## "):
            header = line[3:].strip()
            if header:
                sections.append(header)
    return sections


def find_matching_section(section: str, available_sections: list[str]) -> str | None:
    """Find a section from available_sections matching the requested section case-insensitively."""
    target = section.strip().lower()
    if not target:
        return None

    # 1. Exact case-insensitive match
    for s in available_sections:
        if s.strip().lower() == target:
            return s

    # 2. Match with leading emoji/symbols stripped
    for s in available_sections:
        clean_s = re.sub(r"^[^\w\s]+", "", s).strip().lower()
        if clean_s == target:
            return s

    # 3. Substring match (if unique)
    matches = [
        s
        for s in available_sections
        if target in s.lower()
        or target in re.sub(r"^[^\w\s]+", "", s).strip().lower()
    ]
    if len(matches) == 1:
        return matches[0]

    return None


def format_task(
    text: str,
    priority: str | None = None,
    due: str | None = None,
    link: str | None = None,
) -> str:
    """Format a task line according to obsidian-tasks syntax.

    Never invents date or priority.
    """
    clean_text = text.strip()
    if not clean_text:
        raise TaskValidationError("Task text cannot be empty.")

    parts = [f"- [ ] {clean_text}"]

    if priority is not None:
        p_key = priority.strip().lower()
        if p_key in PRIORITY_TO_EMOJI:
            parts.append(PRIORITY_TO_EMOJI[p_key])
        elif priority in PRIORITY_TO_EMOJI:
            parts.append(PRIORITY_TO_EMOJI[priority])
        else:
            raise TaskValidationError(
                f"Invalid priority {priority!r}. Allowed: urgent, high, low (or ⏫, 🔼, ⏬)"
            )

    if due is not None:
        due_str = due.strip()
        if due_str.startswith("📅"):
            due_str = due_str.lstrip("📅").strip()
        try:
            datetime.date.fromisoformat(due_str)
        except ValueError:
            raise TaskValidationError(
                f"Invalid due date {due!r}. Expected YYYY-MM-DD format."
            )
        parts.append(f"📅 {due_str}")

    if link is not None:
        link_str = link.strip()
        if link_str.startswith("[[") and link_str.endswith("]]"):
            parts.append(link_str)
        else:
            parts.append(f"[[{link_str}]]")

    return " ".join(parts)


def insert_task_into_section(
    content: str,
    section: str,
    task_line: str,
) -> tuple[str, str]:
    """Insert a task line under the matched section in Tasks.md content.

    Returns (matched_section_name, updated_content).
    Raises TaskSectionNotFoundError listing available sections if not found.
    """
    available_sections = parse_sections(content)
    matched = find_matching_section(section, available_sections)
    if matched is None:
        raise TaskSectionNotFoundError(
            f"Section {section!r} not found in Tasks.md. Available sections: {available_sections}"
        )

    lines = content.splitlines()
    header_idx = -1
    for i, line in enumerate(lines):
        if line.startswith("## ") and line[3:].strip() == matched:
            header_idx = i
            break

    if header_idx == -1:
        raise TaskSectionNotFoundError(
            f"Section {section!r} header not found in Tasks.md lines."
        )

    # Find the next header (## or #) or end of file
    next_header_idx = len(lines)
    for i in range(header_idx + 1, len(lines)):
        if lines[i].startswith("## ") or lines[i].startswith("# "):
            next_header_idx = i
            break

    # Find the insertion point: after the last non-blank content in this section
    insert_idx = None
    for k in range(next_header_idx - 1, header_idx, -1):
        if lines[k].strip():
            insert_idx = k + 1
            break

    if insert_idx is None:
        # Section had no non-blank lines
        insert_idx = header_idx + 1

    new_lines = lines[:insert_idx] + [task_line] + lines[insert_idx:]
    result = "\n".join(new_lines)
    if content.endswith("\n"):
        result += "\n"

    return matched, result


def parse_tasks(
    content: str, today: datetime.date | None = None
) -> list[dict[str, Any]]:
    """Parse Tasks.md content into structured task dictionaries, flagging overdue."""
    if today is None:
        today = datetime.datetime.now(datetime.UTC).astimezone().date()

    tasks: list[dict[str, Any]] = []
    current_section: str | None = None

    for line in content.splitlines():
        if line.startswith("## "):
            current_section = line[3:].strip()
            continue

        match = re.match(r"^\s*-\s*\[([ xX])\]\s*(.*)$", line)
        if not match:
            continue

        status_char = match.group(1)
        completed = status_char in ("x", "X")
        item_text = match.group(2).strip()

        # Extract priority
        priority: str | None = None
        for emoji, name in EMOJI_TO_PRIORITY.items():
            if emoji in item_text:
                priority = name
                item_text = item_text.replace(emoji, "").strip()
                break

        # Extract due date: 📅 YYYY-MM-DD
        due: str | None = None
        due_match = re.search(r"📅\s*(\d{4}-\d{2}-\d{2})", item_text)
        if due_match:
            due = due_match.group(1)
            item_text = (
                item_text[: due_match.start()] + item_text[due_match.end() :]
            ).strip()

        # Extract completion date: ✅ YYYY-MM-DD
        completed_date: str | None = None
        comp_match = re.search(r"✅\s*(\d{4}-\d{2}-\d{2})", item_text)
        if comp_match:
            completed_date = comp_match.group(1)
            item_text = (
                item_text[: comp_match.start()] + item_text[comp_match.end() :]
            ).strip()

        # Extract link: [[...]]
        link: str | None = None
        link_match = re.search(r"\[\[(.*?)\]\]", item_text)
        if link_match:
            link = link_match.group(1)
            item_text = (
                item_text[: link_match.start()] + item_text[link_match.end() :]
            ).strip()

        clean_text = re.sub(r"\s+", " ", item_text).strip()

        overdue = False
        if not completed and due is not None:
            try:
                due_d = datetime.date.fromisoformat(due)
                if due_d < today:
                    overdue = True
            except ValueError:
                pass

        tasks.append({
            "text": clean_text,
            "raw": line.strip(),
            "section": current_section,
            "completed": completed,
            "priority": priority,
            "due": due,
            "completed_date": completed_date,
            "link": link,
            "overdue": overdue,
        })

    return tasks


def filter_tasks(
    tasks: list[dict[str, Any]], filter_by: str | None = None
) -> list[dict[str, Any]]:
    """Filter structured tasks by status or section."""
    if filter_by is None or not filter_by.strip():
        return tasks

    f_norm = filter_by.strip().lower()
    if f_norm in ("pending", "todo", "incomplete", "open"):
        return [t for t in tasks if not t["completed"]]
    if f_norm in ("completed", "done"):
        return [t for t in tasks if t["completed"]]
    if f_norm == "overdue":
        return [t for t in tasks if t["overdue"]]
    if f_norm == "all":
        return tasks

    # Try matching section name
    section_matches = [
        t
        for t in tasks
        if t["section"] is not None
        and (
            t["section"].strip().lower() == f_norm
            or f_norm in t["section"].lower()
            or f_norm in re.sub(r"^[^\w\s]+", "", t["section"]).strip().lower()
        )
    ]
    return section_matches
