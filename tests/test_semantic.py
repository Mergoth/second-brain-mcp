"""Integration tests for semantic MCP tools.

Tests the five adapters: capture_thought, list_task_sections, add_task,
get_tasks, and append_log.
"""

from pathlib import Path

import pytest

from second_brain_mcp.errors import InvalidDomainError, TaskSectionNotFoundError
from second_brain_mcp.tools.semantic import (
    add_task,
    append_log,
    capture_thought,
    get_tasks,
    list_task_sections,
)
from second_brain_mcp.vault import paths, store


def test_capture_thought_writes_correct_filename_and_frontmatter(vault: Path) -> None:
    rel_path = capture_thought(
        text="Remember to check the garden humidity",
        source="voice",
        domain="plants",
    )
    assert rel_path.startswith("raw/thoughts/")
    assert rel_path.endswith(".md")

    resolved = paths.resolve(rel_path)
    assert resolved.is_file()

    content = store.read_note(resolved)
    assert "source: voice" in content
    assert "status: raw" in content
    assert "tags: [type/note, domain/plants]" in content
    assert "Remember to check the garden humidity" in content


def test_capture_thought_rejects_domain_outside_closed_list(vault: Path) -> None:
    with pytest.raises(InvalidDomainError):
        capture_thought(
            text="Thinking about an unknown domain",
            source="text",
            domain="non-existent-domain",
        )


def test_capture_thought_never_writes_to_root_or_bare_raw(vault: Path) -> None:
    rel_path = capture_thought(text="Voice memo", source="voice")
    # Must be in raw/thoughts/, not raw/ or root
    assert rel_path.startswith("raw/thoughts/")
    p = Path(rel_path)
    assert len(p.parts) == 3
    assert p.parts[0] == "raw"
    assert p.parts[1] == "thoughts"


def test_list_task_sections_reads_live_headers(vault: Path) -> None:
    sections = list_task_sections()
    assert any("Urgent" in s for s in sections)
    assert any("Current Sprint" in s for s in sections)
    assert any("Backlog" in s for s in sections)

    # Modify Tasks.md live by adding a new header
    tasks_path = paths.resolve("Tasks.md")
    original = store.read_note(tasks_path)
    new_content = original + "\n## 🚀 Next Milestone\n\n- [ ] Plan sprint\n"
    store.write_note(tasks_path, new_content, mode="overwrite")

    updated_sections = list_task_sections()
    assert any("Next Milestone" in s for s in updated_sections)


def test_add_task_rejects_unknown_section_and_lists_available(vault: Path) -> None:
    with pytest.raises(TaskSectionNotFoundError) as exc_info:
        add_task(text="Do something", section="NonExistentSection")
    err_msg = str(exc_info.value)
    assert "NonExistentSection" in err_msg
    assert "Urgent" in err_msg
    assert "Current Sprint" in err_msg


def test_add_task_never_invents_date_or_priority(vault: Path) -> None:
    add_task(text="Simple task with no extras", section="Backlog")
    tasks_path = paths.resolve("Tasks.md")
    content = store.read_note(tasks_path)
    assert "- [ ] Simple task with no extras\n" in content
    # Verify no date or priority emoji was added to this line
    for line in content.splitlines():
        if "Simple task with no extras" in line:
            assert line == "- [ ] Simple task with no extras"


def test_add_task_reports_markers_it_added(vault: Path) -> None:
    res = add_task(
        text="Fix payment gateway bug",
        section="Urgent",
        priority="urgent",
        due="2026-08-30",
        link="InvoiceSpec",
    )
    assert "⏫" in res
    assert "📅 2026-08-30" in res
    assert "[[InvoiceSpec]]" in res


def test_add_task_inserts_under_section_not_end_of_file(vault: Path) -> None:
    add_task(text="Urgent hotfix item", section="Urgent")
    tasks_path = paths.resolve("Tasks.md")
    content = store.read_note(tasks_path)
    lines = content.splitlines()

    urgent_idx = next(i for i, l in enumerate(lines) if "Urgent" in l)
    sprint_idx = next(i for i, l in enumerate(lines) if "Current Sprint" in l)
    task_idx = next(i for i, l in enumerate(lines) if "Urgent hotfix item" in l)

    assert urgent_idx < task_idx < sprint_idx


def test_add_task_preserves_non_ascii_text(vault: Path) -> None:
    add_task(
        text="Купить билеты в Мариинский театр",
        section="Current Sprint",
        priority="high",
    )
    tasks_path = paths.resolve("Tasks.md")
    content = store.read_note(tasks_path)
    assert "Купить билеты в Мариинский театр" in content


def test_get_tasks_flags_overdue(vault: Path) -> None:
    add_task(
        text="Past due action item",
        section="Urgent",
        due="2020-01-01",
    )
    tasks = get_tasks()
    overdue_tasks = [t for t in tasks if t["text"] == "Past due action item"]
    assert len(overdue_tasks) == 1
    assert overdue_tasks[0]["overdue"] is True

    # Completed tasks should not be overdue
    completed = [t for t in tasks if t["completed"]]
    assert all(t["overdue"] is False for t in completed)


def test_get_tasks_parses_priority_due_and_link(vault: Path) -> None:
    add_task(
        text="Complex task with metadata",
        section="Backlog",
        priority="high",
        due="2026-09-01",
        link="ArchitectureDoc",
    )
    tasks = get_tasks()
    matching = [t for t in tasks if t["text"] == "Complex task with metadata"]
    assert len(matching) == 1
    task = matching[0]
    assert task["priority"] == "high"
    assert task["due"] == "2026-09-01"
    assert task["link"] == "ArchitectureDoc"
    assert task["completed"] is False


def test_append_log_is_append_only(vault: Path) -> None:
    log_path = paths.resolve("meta/log.md")
    initial_content = store.read_note(log_path)

    res = append_log("2026-08-16: Re-indexed tags and verified backlinks")
    assert "Re-indexed tags" in res

    new_content = store.read_note(log_path)
    assert new_content.startswith(initial_content)
    assert new_content.endswith(
        "2026-08-16: Re-indexed tags and verified backlinks\n"
    )


def test_append_log_does_not_add_a_bullet_prefix(vault: Path) -> None:
    log_path = paths.resolve("meta/log.md")
    append_log("2026-08-16 20:45 | test | x")
    content = store.read_note(log_path)
    last_line = content.splitlines()[-1]
    assert last_line == "2026-08-16 20:45 | test | x"
    assert not last_line.startswith("- ")


def test_append_log_preserves_existing_line_format(vault: Path) -> None:
    log_path = paths.resolve("meta/log.md")
    initial_content = store.read_note(log_path)
    append_log("2026-08-16 20:45 | test | new entry")
    updated = store.read_note(log_path)
    assert updated[: len(initial_content)] == initial_content

