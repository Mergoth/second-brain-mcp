"""Tests for vault.tasks — parsing, formatting, and inserting tasks."""

import datetime

import pytest

from second_brain_mcp.errors import TaskSectionNotFoundError, TaskValidationError
from second_brain_mcp.vault.tasks import (
    filter_tasks,
    find_matching_section,
    format_task,
    insert_task_into_section,
    parse_sections,
    parse_tasks,
)

SAMPLE_TASKS_MD = """# Tasks

## 🔥 Urgent

- [ ] Fix critical bug in login flow ⏫ 📅 2026-08-20

## 📋 Current Sprint

- [ ] Review PR for new feature 🔼
- [x] Update documentation ✅ 2026-08-10

## 📝 Backlog

- [ ] Refactor database layer
- [ ] Add unit tests for auth module
"""


class TestParseSections:
    def test_parses_live_headers(self) -> None:
        sections = parse_sections(SAMPLE_TASKS_MD)
        assert len(sections) == 3
        assert "Urgent" in sections[0]
        assert "Current Sprint" in sections[1]
        assert "Backlog" in sections[2]

    def test_empty_content(self) -> None:
        assert parse_sections("# Title with no h2") == []


class TestFindMatchingSection:
    def test_exact_match(self) -> None:
        sections = ["🔥 Urgent", "📋 Current Sprint", "📝 Backlog"]
        assert find_matching_section("🔥 Urgent", sections) == "🔥 Urgent"
        assert find_matching_section("🔥 urgent", sections) == "🔥 Urgent"

    def test_clean_name_match(self) -> None:
        sections = ["🔥 Urgent", "📋 Current Sprint", "📝 Backlog"]
        assert find_matching_section("Urgent", sections) == "🔥 Urgent"
        assert find_matching_section("urgent", sections) == "🔥 Urgent"
        assert find_matching_section("Current Sprint", sections) == "📋 Current Sprint"
        assert find_matching_section("backlog", sections) == "📝 Backlog"

    def test_no_match_returns_none(self) -> None:
        sections = ["🔥 Urgent", "📋 Current Sprint"]
        assert find_matching_section("NonExistent", sections) is None


class TestFormatTask:
    def test_minimal(self) -> None:
        line = format_task("Buy groceries")
        assert line == "- [ ] Buy groceries"

    def test_priority_names(self) -> None:
        assert format_task("Task 1", priority="urgent") == "- [ ] Task 1 ⏫"
        assert format_task("Task 2", priority="high") == "- [ ] Task 2 🔼"
        assert format_task("Task 3", priority="low") == "- [ ] Task 3 ⏬"

    def test_priority_emojis(self) -> None:
        assert format_task("Task 1", priority="⏫") == "- [ ] Task 1 ⏫"
        assert format_task("Task 2", priority="🔼") == "- [ ] Task 2 🔼"
        assert format_task("Task 3", priority="⏬") == "- [ ] Task 3 ⏬"

    def test_due_date(self) -> None:
        assert format_task("Task", due="2026-08-20") == "- [ ] Task 📅 2026-08-20"
        assert format_task("Task", due="📅 2026-08-20") == "- [ ] Task 📅 2026-08-20"

    def test_link(self) -> None:
        assert format_task("Task", link="MyNote") == "- [ ] Task [[MyNote]]"
        assert format_task("Task", link="[[MyNote]]") == "- [ ] Task [[MyNote]]"

    def test_all_options(self) -> None:
        line = format_task(
            "Fix bug", priority="urgent", due="2026-08-20", link="PR-42"
        )
        assert line == "- [ ] Fix bug ⏫ 📅 2026-08-20 [[PR-42]]"

    def test_invalid_priority_raises(self) -> None:
        with pytest.raises(TaskValidationError):
            format_task("Task", priority="invalid-priority")

    def test_invalid_due_raises(self) -> None:
        with pytest.raises(TaskValidationError):
            format_task("Task", due="not-a-date")

    def test_empty_text_raises(self) -> None:
        with pytest.raises(TaskValidationError):
            format_task("   ")


class TestInsertTaskIntoSection:
    def test_inserts_under_section_not_end_of_file(self) -> None:
        matched, updated = insert_task_into_section(
            SAMPLE_TASKS_MD,
            section="Urgent",
            task_line="- [ ] New urgent task",
        )
        assert "Urgent" in matched
        lines = updated.splitlines()
        # The new task should be before "## 📋 Current Sprint"
        urgent_idx = next(i for i, l in enumerate(lines) if "Urgent" in l)
        sprint_idx = next(i for i, l in enumerate(lines) if "Current Sprint" in l)
        task_idx = next(i for i, l in enumerate(lines) if "New urgent task" in l)
        assert urgent_idx < task_idx < sprint_idx

    def test_inserts_into_last_section(self) -> None:
        matched, updated = insert_task_into_section(
            SAMPLE_TASKS_MD,
            section="Backlog",
            task_line="- [ ] New backlog task",
        )
        assert "Backlog" in matched
        assert updated.rstrip().endswith("- [ ] New backlog task")

    def test_rejects_unknown_section_and_lists_available(self) -> None:
        with pytest.raises(TaskSectionNotFoundError) as exc_info:
            insert_task_into_section(
                SAMPLE_TASKS_MD,
                section="Unknown Section",
                task_line="- [ ] Some task",
            )
        err_msg = str(exc_info.value)
        assert "Unknown Section" in err_msg
        assert "Urgent" in err_msg
        assert "Current Sprint" in err_msg
        assert "Backlog" in err_msg

    def test_preserves_non_ascii_text(self) -> None:
        _matched, updated = insert_task_into_section(
            SAMPLE_TASKS_MD,
            section="Urgent",
            task_line="- [ ] Купить хлеб и молоко ⏫ 📅 2026-08-20",
        )
        assert "Купить хлеб и молоко" in updated


class TestParseTasks:
    def test_parses_tasks_and_flags_overdue(self) -> None:
        fixed_today = datetime.date(2026, 8, 25)
        parsed = parse_tasks(SAMPLE_TASKS_MD, today=fixed_today)
        assert len(parsed) == 5

        # First task is due 2026-08-20 which is < 2026-08-25 -> overdue
        t0 = parsed[0]
        assert t0["text"] == "Fix critical bug in login flow"
        assert t0["priority"] == "urgent"
        assert t0["due"] == "2026-08-20"
        assert t0["completed"] is False
        assert t0["overdue"] is True

        # Second task has high priority, no due date -> not overdue
        t1 = parsed[1]
        assert t1["text"] == "Review PR for new feature"
        assert t1["priority"] == "high"
        assert t1["due"] is None
        assert t1["completed"] is False
        assert t1["overdue"] is False

        # Third task is completed -> not overdue
        t2 = parsed[2]
        assert t2["text"] == "Update documentation"
        assert t2["completed"] is True
        assert t2["completed_date"] == "2026-08-10"
        assert t2["overdue"] is False

    def test_filter_tasks(self) -> None:
        fixed_today = datetime.date(2026, 8, 25)
        all_tasks = parse_tasks(SAMPLE_TASKS_MD, today=fixed_today)

        pending = filter_tasks(all_tasks, "pending")
        assert len(pending) == 4
        assert all(not t["completed"] for t in pending)

        completed = filter_tasks(all_tasks, "completed")
        assert len(completed) == 1
        assert completed[0]["completed"] is True

        overdue = filter_tasks(all_tasks, "overdue")
        assert len(overdue) == 1
        assert overdue[0]["text"] == "Fix critical bug in login flow"

        by_section = filter_tasks(all_tasks, "Urgent")
        assert len(by_section) == 1
        assert "Urgent" in by_section[0]["section"]
