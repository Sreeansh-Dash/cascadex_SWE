"""
Phase 07 — test_dose_scheduler.py

Unit tests for `dose_reminders()`. Pure function — no I/O, no mocking.

Covers:
1. Schedule due exactly at trigger time → included
2. Schedule at window boundary (WINDOW_MINUTES before now) → included
3. Schedule just outside window (WINDOW_MINUTES + 1 min before now) → excluded
4. Schedule on wrong day-of-week → excluded
5. Schedule on correct day-of-week → included
6. Empty schedule list → returns empty list
"""

from __future__ import annotations

from datetime import datetime

from app.services.dose_scheduler import WINDOW_MINUTES, due_reminders

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sched(time_of_day: str, days: list[int] | None = None, entry_id: str = "e1", user_id: str = "u1") -> dict:
    return {
        "schedule_id": f"sched_{time_of_day}",
        "time_of_day": time_of_day,
        "days_of_week": days if days is not None else [],
        "entry_id": entry_id,
        "user_id": user_id,
        "generic_name": "Test Drug",
    }


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestDueReminders:
    """Tests for the pure due_reminders() function."""

    def test_exact_match_included(self):
        """Schedule at exact trigger time → included."""
        now = datetime(2024, 1, 15, 8, 30)   # Monday 08:30
        schedules = [_sched("08:30")]
        result = due_reminders(now, schedules)
        assert len(result) == 1
        assert result[0]["time_of_day"] == "08:30"

    def test_boundary_start_included(self):
        """Schedule at exactly window_start (now - WINDOW_MINUTES) → included."""
        now = datetime(2024, 1, 15, 8, 30)
        edge_time = f"0{8}:{30 - WINDOW_MINUTES:02d}"  # 08:25
        schedules = [_sched(edge_time)]
        result = due_reminders(now, schedules)
        assert len(result) == 1

    def test_boundary_end_included(self):
        """Schedule at exactly window_end (now + WINDOW_MINUTES) → included."""
        now = datetime(2024, 1, 15, 8, 30)
        edge_time = f"0{8}:{30 + WINDOW_MINUTES:02d}"  # 08:35
        schedules = [_sched(edge_time)]
        result = due_reminders(now, schedules)
        assert len(result) == 1

    def test_just_outside_window_excluded(self):
        """Schedule at WINDOW_MINUTES + 1 min after now → excluded."""
        now = datetime(2024, 1, 15, 8, 30)
        outside_time = f"0{8}:{30 + WINDOW_MINUTES + 1:02d}"  # 08:36
        schedules = [_sched(outside_time)]
        result = due_reminders(now, schedules)
        assert result == []

    def test_just_before_window_excluded(self):
        """Schedule at WINDOW_MINUTES + 1 min before now → excluded."""
        now = datetime(2024, 1, 15, 8, 30)
        outside_time = f"0{8}:{30 - WINDOW_MINUTES - 1:02d}"  # 08:24
        schedules = [_sched(outside_time)]
        result = due_reminders(now, schedules)
        assert result == []

    def test_wrong_day_excluded(self):
        """Schedule restricted to Wednesday but today is Monday → excluded."""
        now = datetime(2024, 1, 15, 8, 30)  # Monday (weekday=0)
        schedules = [_sched("08:30", days=[2])]  # Wednesday only
        result = due_reminders(now, schedules)
        assert result == []

    def test_correct_day_included(self):
        """Schedule on Monday (0), today is Monday → included."""
        now = datetime(2024, 1, 15, 8, 30)  # Monday
        schedules = [_sched("08:30", days=[0, 2, 4])]  # Mon, Wed, Fri
        result = due_reminders(now, schedules)
        assert len(result) == 1

    def test_empty_days_means_every_day(self):
        """Empty days_of_week list → schedule fires every day."""
        now = datetime(2024, 1, 15, 8, 30)  # Monday
        schedules = [_sched("08:30", days=[])]
        result = due_reminders(now, schedules)
        assert len(result) == 1

    def test_empty_schedule_list(self):
        """Empty input → empty output."""
        now = datetime(2024, 1, 15, 8, 30)
        assert due_reminders(now, []) == []

    def test_multiple_schedules_filters_correctly(self):
        """Multiple schedules: only those in window are returned."""
        now = datetime(2024, 1, 15, 8, 30)
        schedules = [
            _sched("08:28"),   # in window
            _sched("08:30"),   # exact
            _sched("08:32"),   # in window
            _sched("08:36"),   # outside
            _sched("08:24"),   # outside
        ]
        result = due_reminders(now, schedules)
        times = {s["time_of_day"] for s in result}
        assert times == {"08:28", "08:30", "08:32"}
