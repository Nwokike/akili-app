"""Course store — JSON-backed courses, modules, and assignments.

Replaces v1's SQLite DatabaseManager for the course domain. One
StorageService key holds the whole structure; the method names mirror
v1's manager so behaviour (unlock cascade, progress recompute, duplicate
guard) is identical.

Assignments live here too because lesson generation auto-creates one
(v1 parity); the assessment screens consume them in Phase 4.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, timedelta

from core.constants import STORAGE_COURSES

logger = logging.getLogger(__name__)


def _empty() -> dict:
    return {
        "courses": [],
        "modules": [],
        "assignments": [],
        "quiz_attempts": [],
        "assessments": [],
        "timetable": [],
        "next_course_id": 1,
        "next_module_id": 1,
        "next_assignment_id": 1,
        "next_attempt_id": 1,
        "next_assessment_id": 1,
        "next_timetable_id": 1,
    }


WEEKDAY_ORDER = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def canonical_day(day: str) -> str:
    """Normalise a day name: case-insensitive, accepts 3-letter prefixes."""
    text = (day or "").strip().lower()
    if not text:
        return ""
    for name in WEEKDAY_ORDER:
        if name.lower() == text or name.lower().startswith(text[:3]):
            return name
    return ""


def weekday_index(day: str) -> int:
    """Sort key for timetable entries (unknown days sort last)."""
    try:
        return WEEKDAY_ORDER.index(day)
    except ValueError:
        return len(WEEKDAY_ORDER)


class CourseStore:
    """JSON-backed course/module/assignment store."""

    def __init__(self, storage=None):
        self._storage = storage
        self._data = _empty()
        self._lock = asyncio.Lock()
        self._loaded = False

    async def initialize(self) -> None:
        """Load the store from storage."""
        if self._loaded:
            return
        raw = await self._storage.get(STORAGE_COURSES) if self._storage else None
        if raw:
            try:
                loaded = json.loads(raw)
                self._data = {**_empty(), **loaded}
            except Exception:
                logger.warning("course store unreadable; starting fresh", exc_info=True)
                self._data = _empty()
        self._loaded = True

    async def _save(self) -> None:
        if self._storage is not None:
            await self._storage.set(STORAGE_COURSES, json.dumps(self._data, ensure_ascii=False))

    # ── Courses ─────────────────────────────────────────────────────────

    async def add_course(self, subject: str, level: str, curriculum: dict, color_index: int = 0) -> int:
        async with self._lock:
            cid = self._data["next_course_id"]
            self._data["next_course_id"] = cid + 1
            self._data["courses"].append(
                {
                    "id": cid,
                    "subject": subject,
                    "level": level,
                    "curriculum": curriculum,
                    "progress_pct": 0.0,
                    "color_index": color_index,
                    "created_at": date.today().isoformat(),
                }
            )
        await self._save()
        return cid

    async def get_courses(self) -> list[dict]:
        return list(self._data["courses"])

    async def get_course(self, course_id: int) -> dict | None:
        return next((c for c in self._data["courses"] if c["id"] == course_id), None)

    async def get_course_by_subject_level(self, subject: str, level: str) -> dict | None:
        """Case/space-insensitive lookup — the duplicate guard."""
        want_s = (subject or "").strip().lower()
        want_l = (level or "").strip().lower()
        for c in self._data["courses"]:
            if (c.get("subject") or "").strip().lower() == want_s and (c.get("level") or "").strip().lower() == want_l:
                return c
        return None

    async def update_course_progress(self, course_id: int, progress: float) -> None:
        async with self._lock:
            for c in self._data["courses"]:
                if c["id"] == course_id:
                    c["progress_pct"] = float(progress)
                    break
        await self._save()

    async def delete_course(self, course_id: int) -> None:
        async with self._lock:
            gone_modules = {m["id"] for m in self._data["modules"] if m["course_id"] == course_id}
            self._data["courses"] = [c for c in self._data["courses"] if c["id"] != course_id]
            self._data["modules"] = [m for m in self._data["modules"] if m["course_id"] != course_id]
            self._data["assignments"] = [a for a in self._data["assignments"] if a["course_id"] != course_id]
            # Cascade the history too, or Quiz History shows ghost entries
            # for a course that no longer exists.
            self._data["quiz_attempts"] = [qa for qa in self._data["quiz_attempts"] if qa.get("module_id") not in gone_modules]
            self._data["assessments"] = [a for a in self._data["assessments"] if a.get("course_id") != course_id]
        await self._save()

    # ── Modules ─────────────────────────────────────────────────────────

    async def add_module(self, course_id: int, title: str, topics: list, order_num: int, unlocked: bool = False) -> int:
        async with self._lock:
            mid = self._data["next_module_id"]
            self._data["next_module_id"] = mid + 1
            self._data["modules"].append(
                {
                    "id": mid,
                    "course_id": course_id,
                    "title": title,
                    "topics": list(topics or []),
                    "lesson_cache": None,
                    "order_num": order_num,
                    "is_unlocked": bool(unlocked),
                    "is_completed": False,
                }
            )
        await self._save()
        return mid

    async def get_modules(self, course_id: int) -> list[dict]:
        mods = [m for m in self._data["modules"] if m["course_id"] == course_id]
        return sorted(mods, key=lambda m: m.get("order_num", 0))

    async def get_module(self, module_id: int) -> dict | None:
        return next((m for m in self._data["modules"] if m["id"] == module_id), None)

    async def save_lesson(self, module_id: int, content: str) -> None:
        async with self._lock:
            for m in self._data["modules"]:
                if m["id"] == module_id:
                    m["lesson_cache"] = content
                    break
        await self._save()

    async def unlock_module(self, module_id: int) -> None:
        async with self._lock:
            for m in self._data["modules"]:
                if m["id"] == module_id:
                    m["is_unlocked"] = True
                    break
        await self._save()

    async def complete_module(self, module_id: int) -> None:
        """Mark complete and recompute the owning course's progress."""
        async with self._lock:
            course_id = None
            for m in self._data["modules"]:
                if m["id"] == module_id:
                    m["is_completed"] = True
                    m["is_unlocked"] = True
                    course_id = m["course_id"]
                    break
            if course_id is not None:
                mods = [m for m in self._data["modules"] if m["course_id"] == course_id]
                total = len(mods)
                done = sum(1 for m in mods if m.get("is_completed"))
                pct = (done / total * 100) if total else 0.0
                for c in self._data["courses"]:
                    if c["id"] == course_id:
                        c["progress_pct"] = pct
                        break
        await self._save()

    # ── Assignments ─────────────────────────────────────────────────────

    async def create_assignment(
        self,
        module_id: int,
        course_id: int,
        title: str,
        description: str,
        questions: list,
        due_days: int = 3,
    ) -> int:
        async with self._lock:
            aid = self._data["next_assignment_id"]
            self._data["next_assignment_id"] = aid + 1
            self._data["assignments"].append(
                {
                    "id": aid,
                    "module_id": module_id,
                    "course_id": course_id,
                    "title": title,
                    "description": description,
                    "questions": list(questions or []),
                    "status": "pending",
                    "due_date": (date.today() + timedelta(days=due_days)).isoformat(),
                    "submitted_at": None,
                    "graded_at": None,
                    "submission": [],
                    "evaluation": [],
                    "score": None,
                    "max_score": 100,
                    "feedback": "",
                    "created_at": date.today().isoformat(),
                }
            )
        await self._save()
        return aid

    async def get_assignment(self, assignment_id: int) -> dict | None:
        return next((a for a in self._data["assignments"] if a["id"] == assignment_id), None)

    async def get_module_assignment(self, module_id: int) -> dict | None:
        """The pending/latest assignment for a module, for the indicator."""
        for a in reversed(self._data["assignments"]):
            if a["module_id"] == module_id:
                return a
        return None

    async def get_all_assignments(self, course_id: int | None = None) -> list[dict]:
        items = self._data["assignments"]
        if course_id is not None:
            items = [a for a in items if a["course_id"] == course_id]
        return list(items)

    async def get_pending_assignments(self, course_id: int | None = None) -> list[dict]:
        items = await self.get_all_assignments(course_id)
        return [a for a in items if a.get("status") == "pending"]

    async def submit_assignment(self, assignment_id: int, submission: list) -> None:
        async with self._lock:
            for a in self._data["assignments"]:
                if a["id"] == assignment_id:
                    a["submission"] = list(submission or [])
                    a["status"] = "submitted"
                    a["submitted_at"] = date.today().isoformat()
                    break
        await self._save()

    async def grade_assignment(self, assignment_id: int, evaluation: list, score: float, feedback: str) -> None:
        async with self._lock:
            for a in self._data["assignments"]:
                if a["id"] == assignment_id:
                    a["evaluation"] = list(evaluation or [])
                    a["score"] = float(score)
                    a["feedback"] = feedback
                    a["status"] = "graded"
                    a["graded_at"] = date.today().isoformat()
                    break
        await self._save()

    async def can_complete_course(self, course_id: int) -> tuple[bool, int]:
        """True when no assignment is left ungraded; also returns the count pending."""
        pending = [a for a in self._data["assignments"] if a["course_id"] == course_id and a.get("status") != "graded"]
        return (len(pending) == 0, len(pending))

    async def get_assignment_counts(self) -> dict:
        counts = {"pending": 0, "submitted": 0, "graded": 0, "overdue": 0}
        today = date.today().isoformat()
        for a in self._data["assignments"]:
            status = a.get("status", "pending")
            if status in counts:
                counts[status] += 1
            if status != "graded" and (a.get("due_date") or "") < today:
                counts["overdue"] += 1
        return counts

    # ── Attempts (consumed by Phase 4) ──────────────────────────────────

    async def save_quiz_attempt(self, module_id: int, score: float, total: float, questions: list, passed: bool, answers: list | None = None, evaluations: list | None = None) -> None:
        async with self._lock:
            self._data["quiz_attempts"].append(
                {
                    "id": self._data["next_attempt_id"],
                    "module_id": module_id,
                    "score": float(score),
                    "total": float(total),
                    "questions": list(questions or []),
                    "answers": list(answers or []),
                    "evaluations": list(evaluations or []),
                    "passed": bool(passed),
                    "timestamp": date.today().isoformat(),
                }
            )
            self._data["next_attempt_id"] += 1
        await self._save()

    async def get_quiz_attempts(self, module_id: int | None = None) -> list[dict]:
        items = self._data["quiz_attempts"]
        if module_id is not None:
            items = [a for a in items if a["module_id"] == module_id]
        return list(items)

    async def save_assessment(self, course_id: int, score: float, total: float, grade: str, duration_seconds: int, questions: list, answers: list | None = None, evaluations: list | None = None) -> None:
        async with self._lock:
            self._data["assessments"].append(
                {
                    "id": self._data["next_assessment_id"],
                    "course_id": course_id,
                    "score": float(score),
                    "total": float(total),
                    "grade": grade,
                    "duration_seconds": int(duration_seconds),
                    "questions": list(questions or []),
                    "answers": list(answers or []),
                    "evaluations": list(evaluations or []),
                    "timestamp": date.today().isoformat(),
                }
            )
            self._data["next_assessment_id"] += 1
        await self._save()

    async def get_assessments(self, course_id: int | None = None) -> list[dict]:
        items = self._data["assessments"]
        if course_id is not None:
            items = [a for a in items if a["course_id"] == course_id]
        return list(items)

    # ── Timetable ───────────────────────────────────────────────────────────

    async def get_timetable(self) -> list[dict]:
        """Entries ordered Monday→Sunday, then by time_slot (fixes v1's
        alphabetical day sort)."""
        items = list(self._data.get("timetable", []))
        items.sort(key=lambda e: (weekday_index(e.get("day", "")), str(e.get("time_slot", ""))))
        return items

    async def add_timetable_entry(self, day: str, time_slot: str, subject: str, note: str = "") -> int:
        """Add a class. Raises ValueError with a human message on bad input
        (v1 silently returned)."""
        clean_day = canonical_day(day)
        if not clean_day:
            raise ValueError("Pick a day of the week.")
        if not (time_slot or "").strip():
            raise ValueError("Enter a time (e.g. 09:00).")
        if not (subject or "").strip():
            raise ValueError("Enter a subject.")
        async with self._lock:
            eid = self._data["next_timetable_id"]
            self._data["next_timetable_id"] = eid + 1
            self._data.setdefault("timetable", []).append(
                {
                    "id": eid,
                    "day": clean_day,
                    "time_slot": time_slot.strip(),
                    "subject": subject.strip(),
                    "note": (note or "").strip(),
                }
            )
        await self._save()
        return eid

    async def update_timetable_entry(self, entry_id: int, day: str, time_slot: str, subject: str, note: str = "") -> bool:
        """Edit a class. New in v2 (v1 has no edit path). Returns found."""
        clean_day = canonical_day(day)
        if not clean_day:
            raise ValueError("Pick a day of the week.")
        if not (time_slot or "").strip():
            raise ValueError("Enter a time (e.g. 09:00).")
        if not (subject or "").strip():
            raise ValueError("Enter a subject.")
        found = False
        async with self._lock:
            for entry in self._data.get("timetable", []):
                if entry.get("id") == entry_id:
                    entry.update(
                        {
                            "day": clean_day,
                            "time_slot": time_slot.strip(),
                            "subject": subject.strip(),
                            "note": (note or "").strip(),
                        }
                    )
                    found = True
                    break
        if found:
            await self._save()
        return found

    async def delete_timetable_entry(self, entry_id: int) -> None:
        async with self._lock:
            self._data["timetable"] = [e for e in self._data.get("timetable", []) if e.get("id") != entry_id]
        await self._save()

    async def get_completed_module_count(self) -> int:
        return sum(1 for m in self._data["modules"] if m.get("is_completed"))

    async def get_on_time_assignment_count(self) -> int:
        """Graded assignments submitted on or before their due date."""
        count = 0
        for a in self._data["assignments"]:
            if a.get("status") != "graded":
                continue
            submitted, due = a.get("submitted_at") or "", a.get("due_date") or ""
            if not due or (submitted and submitted <= due):
                count += 1
        return count

    async def reset(self) -> None:
        """Clear everything (Reset App)."""
        async with self._lock:
            self._data = _empty()
        await self._save()


def init_course_store(storage) -> CourseStore:
    """Create the course store (called once by AppController)."""
    return CourseStore(storage=storage)
