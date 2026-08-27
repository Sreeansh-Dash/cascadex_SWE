"""
CascadeX Dose Scheduler — Phase 07.

Provides a pure function `due_reminders()` for testability and an
`start_scheduler()` function that wires APScheduler into the FastAPI
lifespan.

Design:
- `due_reminders()` is pure (no I/O, no side effects) — fully tested
  in test_dose_scheduler.py without mocking time libraries.
- `start_scheduler()` is called once in main.py's lifespan context manager.
  It runs a polling job every minute that queries active schedules and fires
  dose-reminder notifications for any that fall within the ±5-min window.

APScheduler dependency note:
    APScheduler is imported lazily inside `start_scheduler()` so tests that
    import this module without running an async scheduler don't require it.
    Add ``apscheduler>=3.10.0`` to requirements.txt before deploying.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pure helper — testable without any I/O
# ---------------------------------------------------------------------------

WINDOW_MINUTES = 5


def due_reminders(
    now: datetime,
    schedules: list[dict],
) -> list[dict]:
    """Return schedules that are due within ±WINDOW_MINUTES of *now*.

    A schedule is "due" when:
    1. ``now.weekday()`` (0=Monday) is listed in ``schedule["days_of_week"]``
       (empty list means every day).
    2. The ``schedule["time_of_day"]`` (``"HH:MM"``) falls within
       [now - WINDOW_MINUTES, now + WINDOW_MINUTES] (inclusive on both ends).
    3. The schedule has NOT already been logged today (caller is responsible
       for pre-filtering ``schedules`` to exclude already-logged ones before
       passing them in).

    Args:
        now: Current UTC datetime (naive or aware — comparison is time-only).
        schedules: List of schedule dicts.  Each must contain:
            - ``"schedule_id"`` (str)
            - ``"time_of_day"`` (str, ``"HH:MM"`` 24-hour format)
            - ``"days_of_week"`` (list[int], 0=Mon…6=Sun; empty = every day)
            - ``"entry_id"`` (str, the MedicationEntry it belongs to)
            - ``"user_id"`` (str)

    Returns:
        Subset of ``schedules`` whose ``time_of_day`` falls in the window.
    """
    window_start = (now - timedelta(minutes=WINDOW_MINUTES)).time()
    window_end   = (now + timedelta(minutes=WINDOW_MINUTES)).time()
    today_dow    = now.weekday()  # 0 = Monday

    due: list[dict] = []
    for sched in schedules:
        # Day-of-week filter
        days = sched.get("days_of_week") or []
        if days and today_dow not in days:
            continue

        # Parse time_of_day
        try:
            h, m = map(int, sched["time_of_day"].split(":"))
        except (ValueError, KeyError):
            logger.warning("Skipping malformed schedule time_of_day: %s", sched.get("time_of_day"))
            continue

        from datetime import time as _time  # local import to avoid shadowing
        sched_time = _time(h, m)

        # Handle midnight-crossing windows
        if window_start <= window_end:
            in_window = window_start <= sched_time <= window_end
        else:
            # e.g. window spans 23:55–00:05
            in_window = sched_time >= window_start or sched_time <= window_end

        if in_window:
            due.append(sched)

    return due


# ---------------------------------------------------------------------------
# Scheduler lifecycle (wired into main.py lifespan)
# ---------------------------------------------------------------------------

async def start_scheduler(app) -> None:  # noqa: ANN001 — FastAPI app
    """Start the APScheduler AsyncIOScheduler for dose reminders.

    Called once inside the FastAPI lifespan context manager.  Schedules a
    job that runs every minute and sends dose-reminder notifications to users
    whose schedule falls in the ±5-min window.

    The scheduler is stored on ``app.state.scheduler`` so it can be shut down
    cleanly in the lifespan finally block.

    APScheduler dependency:
        pip install apscheduler>=3.10.0

    Args:
        app: The running FastAPI application instance.
    """
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError:
        logger.warning(
            "APScheduler not installed — dose reminder scheduler disabled. "
            "Install with: pip install apscheduler>=3.10.0"
        )
        return

    from app.db.neo4j_session import get_driver
    from app.services import notification_service

    scheduler = AsyncIOScheduler()

    async def _poll_reminders() -> None:
        """Query active DoseSchedule nodes and fire due reminders."""
        now = datetime.utcnow()
        driver = get_driver()
        async with driver.session() as session:
            # Fetch all active schedules (not yet logged today)
            result = await session.run(
                """
                MATCH (u:User)-[:HAS_MEDICATION]->(me:MedicationEntry)-[:HAS_SCHEDULE]->(s:DoseSchedule)
                WHERE me.is_active = true
                AND NOT EXISTS {
                    MATCH (me)-[:HAS_DOSE_LOG]->(l:DoseIntakeLog)
                    WHERE l.scheduled_time STARTS WITH $today
                }
                RETURN s.schedule_id AS schedule_id,
                       s.time_of_day  AS time_of_day,
                       s.days_of_week AS days_of_week,
                       me.entry_id    AS entry_id,
                       me.generic_name AS generic_name,
                       u.user_id      AS user_id
                """,
                {"today": now.strftime("%Y-%m-%d")},
            )
            schedules = await result.data()

        due = due_reminders(now, schedules)
        for sched in due:
            async with driver.session() as session:
                await notification_service.send(
                    session=session,
                    user_id=sched["user_id"],
                    type_="dose_reminder",
                    message=f"Time to take {sched.get('generic_name', 'your medication')} ({sched['time_of_day']}).",
                )

    scheduler.add_job(_poll_reminders, "interval", minutes=1)
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("Dose reminder scheduler started — polling every minute.")
