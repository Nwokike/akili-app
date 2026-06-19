"""Database manager — single persistent connection with WAL mode."""

import json
import os
import uuid
from datetime import date, datetime, timedelta

import aiosqlite


class DatabaseManager:
    def __init__(self, db_path: str = "storage/data/akili.db"):
        self.db_path = os.path.abspath(db_path)
        self._conn = None

    async def _get_conn(self):
        if self._conn is None:
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            self._conn = await aiosqlite.connect(self.db_path)
            self._conn.row_factory = aiosqlite.Row
            await self._conn.execute("PRAGMA journal_mode=WAL;")
            await self._conn.execute("PRAGMA foreign_keys=ON;")
        return self._conn

    async def init_db(self):
        db = await self._get_conn()

        await db.execute("""
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                education_level TEXT NOT NULL,
                education_levels TEXT DEFAULT '[]',
                avatar_index INTEGER DEFAULT 0,
                country TEXT DEFAULT '',
                education_system TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                level TEXT NOT NULL,
                curriculum_json TEXT,
                progress_pct REAL DEFAULT 0.0,
                color_index INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS modules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                topics_json TEXT,
                lesson_cache TEXT,
                order_num INTEGER DEFAULT 0,
                is_unlocked INTEGER DEFAULT 0,
                is_completed INTEGER DEFAULT 0
            )
        """)

        # v2: supports mixed question types + student answers + AI evaluations
        await db.execute("""
            CREATE TABLE IF NOT EXISTS quiz_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id INTEGER REFERENCES modules(id),
                score REAL,
                total REAL,
                questions_json TEXT,
                answers_json TEXT,
                evaluations_json TEXT,
                passed INTEGER DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # v2: mock exams store full questions/answers/evaluations
        await db.execute("""
            CREATE TABLE IF NOT EXISTS assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER REFERENCES courses(id),
                score REAL,
                total REAL,
                grade TEXT,
                duration_seconds INTEGER,
                questions_json TEXT,
                answers_json TEXT,
                evaluations_json TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # v2: assignments system
        await db.execute("""
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id INTEGER REFERENCES modules(id) ON DELETE CASCADE,
                course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT,
                questions_json TEXT,
                status TEXT DEFAULT 'pending',
                due_date TEXT,
                submitted_at TIMESTAMP,
                graded_at TIMESTAMP,
                submission_json TEXT,
                evaluation_json TEXT,
                score REAL,
                max_score REAL DEFAULT 100,
                feedback TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS credits_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                credits_used INTEGER DEFAULT 0,
                action TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS gamification (
                id INTEGER PRIMARY KEY DEFAULT 1,
                xp_total INTEGER DEFAULT 0,
                level TEXT DEFAULT 'Freshman',
                current_streak INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0,
                badges_json TEXT DEFAULT '[]',
                last_active_date TEXT
            )
        """)

        # v2: chat history is session-based, not module-scoped
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                messages_json TEXT,
                context_snapshot TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS timetable (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL,
                time_slot TEXT NOT NULL,
                subject TEXT NOT NULL,
                note TEXT DEFAULT ''
            )
        """)

        # Indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_modules_course ON modules(course_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_quiz_module ON quiz_attempts(module_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_credits_date ON credits_log(date)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_assessments_course ON assessments(course_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_assignments_module ON assignments(module_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_assignments_course ON assignments(course_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_assignments_status ON assignments(status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_history(session_id)")

        await db.commit()

    # ── Settings ──────────────────────────────────────────────

    async def set_setting(self, key: str, value: str):
        db = await self._get_conn()
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        await db.commit()

    async def get_setting(self, key: str, default=None):
        db = await self._get_conn()
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default

    # ── Profile ───────────────────────────────────────────────

    async def save_profile(
        self,
        name: str,
        education_level: str,
        education_levels: list[dict] | None = None,
        avatar_index: int = 0,
        country: str = "",
        education_system: str = "",
    ):
        db = await self._get_conn()
        await db.execute("DELETE FROM profile")
        levels_json = json.dumps(education_levels) if education_levels else "[]"
        await db.execute(
            "INSERT INTO profile (name, education_level, education_levels, avatar_index, country, education_system) VALUES (?, ?, ?, ?, ?, ?)",
            (name, education_level, levels_json, avatar_index, country, education_system),
        )
        await db.commit()

    async def get_profile(self) -> dict | None:
        db = await self._get_conn()
        async with db.execute("SELECT name, education_level, education_levels, avatar_index, country, education_system FROM profile LIMIT 1") as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "name": row[0],
                    "education_level": row[1],
                    "education_levels": json.loads(row[2]) if row[2] else [],
                    "avatar_index": row[3],
                    "country": row[4] or "",
                    "education_system": row[5] or "",
                }
        return None

    # ── Courses ───────────────────────────────────────────────

    async def add_course(self, subject: str, level: str, curriculum_json: str, color_index: int = 0) -> int:
        db = await self._get_conn()
        cursor = await db.execute(
            "INSERT INTO courses (subject, level, curriculum_json, color_index) VALUES (?, ?, ?, ?)",
            (subject, level, curriculum_json, color_index),
        )
        course_id = cursor.lastrowid
        await db.commit()
        return course_id

    async def get_courses(self) -> list[dict]:
        db = await self._get_conn()
        async with db.execute("SELECT id, subject, level, curriculum_json, progress_pct, color_index FROM courses ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "id": r[0],
                    "subject": r[1],
                    "level": r[2],
                    "curriculum_json": r[3],
                    "progress_pct": r[4],
                    "color_index": r[5],
                }
                for r in rows
            ]

    async def update_course_progress(self, course_id: int, progress: float):
        db = await self._get_conn()
        await db.execute("UPDATE courses SET progress_pct = ? WHERE id = ?", (progress, course_id))
        await db.commit()

    async def get_course_by_subject_level(self, subject: str, level: str) -> dict | None:
        """Find an existing course matching subject + level (case/space-insensitive).

        Used to prevent duplicate course creation — e.g. a second "Biology" at the
        same class/level. A different level for the same subject is allowed.
        """
        db = await self._get_conn()
        async with db.execute(
            """SELECT id, subject, level, curriculum_json, progress_pct, color_index
               FROM courses
               WHERE LOWER(TRIM(subject)) = LOWER(TRIM(?)) AND LOWER(TRIM(level)) = LOWER(TRIM(?))
               LIMIT 1""",
            (subject, level),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "subject": row[1],
                "level": row[2],
                "curriculum_json": row[3],
                "progress_pct": row[4],
                "color_index": row[5],
            }

    async def delete_course(self, course_id: int):
        db = await self._get_conn()
        await db.execute("DELETE FROM modules WHERE course_id = ?", (course_id,))
        await db.execute("DELETE FROM assignments WHERE course_id = ?", (course_id,))
        await db.execute("DELETE FROM courses WHERE id = ?", (course_id,))
        await db.commit()

    # ── Modules ───────────────────────────────────────────────

    async def add_module(self, course_id: int, title: str, topics_json: str, order_num: int, unlocked: int = 0):
        db = await self._get_conn()
        await db.execute(
            "INSERT INTO modules (course_id, title, topics_json, order_num, is_unlocked) VALUES (?, ?, ?, ?, ?)",
            (course_id, title, topics_json, order_num, unlocked),
        )
        await db.commit()

    async def get_modules(self, course_id: int) -> list[dict]:
        db = await self._get_conn()
        async with db.execute(
            """SELECT id, title, topics_json, lesson_cache, order_num, is_unlocked, is_completed
               FROM modules WHERE course_id = ? ORDER BY order_num""",
            (course_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "id": r[0],
                    "title": r[1],
                    "topics_json": r[2],
                    "lesson_cache": r[3],
                    "order_num": r[4],
                    "is_unlocked": r[5],
                    "is_completed": r[6],
                }
                for r in rows
            ]

    async def save_lesson(self, module_id: int, content: str):
        db = await self._get_conn()
        await db.execute("UPDATE modules SET lesson_cache = ? WHERE id = ?", (content, module_id))
        await db.commit()

    async def unlock_module(self, module_id: int):
        db = await self._get_conn()
        await db.execute("UPDATE modules SET is_unlocked = 1 WHERE id = ?", (module_id,))
        await db.commit()

    async def complete_module(self, module_id: int):
        db = await self._get_conn()
        await db.execute("UPDATE modules SET is_completed = 1 WHERE id = ?", (module_id,))
        await db.commit()

        # Recalculate overall course progress
        async with db.execute("SELECT course_id FROM modules WHERE id = ?", (module_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                course_id = row[0]
                async with db.execute(
                    "SELECT COUNT(*), SUM(CASE WHEN is_completed = 1 THEN 1 ELSE 0 END) FROM modules WHERE course_id = ?",
                    (course_id,),
                ) as cursor2:
                    m_row = await cursor2.fetchone()
                    if m_row and m_row[0] > 0:
                        total_m = m_row[0]
                        comp_m = m_row[1] or 0
                        pct = (comp_m / total_m) * 100.0
                        await db.execute("UPDATE courses SET progress_pct = ? WHERE id = ?", (pct, course_id))
                        await db.commit()

    # ── Quiz Attempts ─────────────────────────────────────────

    async def save_quiz_attempt(
        self,
        module_id: int,
        score: float,
        total: float,
        questions_json: str,
        passed: int,
        answers_json: str = "[]",
        evaluations_json: str = "[]",
    ):
        db = await self._get_conn()
        await db.execute(
            "INSERT INTO quiz_attempts (module_id, score, total, questions_json, answers_json, evaluations_json, passed) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (module_id, score, total, questions_json, answers_json, evaluations_json, passed),
        )
        await db.commit()

    async def get_quiz_stats(self) -> dict:
        db = await self._get_conn()
        async with db.execute("SELECT COUNT(*), AVG(CASE WHEN total > 0 THEN score / total * 100 ELSE 0 END) FROM quiz_attempts") as cursor:
            row = await cursor.fetchone()
            return {"total_attempts": row[0] or 0, "avg_score": row[1] or 0.0}

    async def get_recent_quiz_scores(self, limit: int = 10) -> list[dict]:
        """Get recent quiz results with subject info for tutor context."""
        db = await self._get_conn()
        async with db.execute(
            """SELECT c.subject, m.title, q.score, q.total, q.passed, q.timestamp
               FROM quiz_attempts q
               JOIN modules m ON q.module_id = m.id
               JOIN courses c ON m.course_id = c.id
               ORDER BY q.timestamp DESC LIMIT ?""",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "subject": r[0],
                    "module": r[1],
                    "score": r[2],
                    "total": r[3],
                    "passed": r[4],
                    "pct": round((r[2] / r[3]) * 100) if r[3] else 0,
                    "date": r[5][:10] if r[5] else "",
                }
                for r in rows
            ]

    async def get_quiz_history(self) -> list[dict]:
        db = await self._get_conn()
        async with db.execute("""
            SELECT c.subject, q.score, q.total, q.timestamp
            FROM quiz_attempts q
            JOIN modules m ON q.module_id = m.id
            JOIN courses c ON m.course_id = c.id
            ORDER BY q.timestamp DESC
        """) as cursor:
            rows = await cursor.fetchall()
            return [{"course": r[0], "score": f"{int((r[1] / r[2]) * 100)}%" if r[2] else "0%", "date": r[3][:10]} for r in rows]

    # ── Assessments (Mock Exams) ──────────────────────────────

    async def save_assessment(
        self,
        course_id: int,
        score: float,
        total: float,
        grade: str = "N/A",
        duration_seconds: int = 0,
        questions_json: str = "[]",
        answers_json: str = "[]",
        evaluations_json: str = "[]",
    ):
        db = await self._get_conn()
        await db.execute(
            "INSERT INTO assessments (course_id, score, total, grade, duration_seconds, questions_json, answers_json, evaluations_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (course_id, score, total, grade, duration_seconds, questions_json, answers_json, evaluations_json),
        )
        await db.commit()

    # ── Assignments ───────────────────────────────────────────

    async def create_assignment(
        self,
        module_id: int,
        course_id: int,
        title: str,
        description: str,
        questions_json: str,
        due_days: int = 3,
    ) -> int:
        db = await self._get_conn()
        due_date = (datetime.now() + timedelta(days=due_days)).isoformat()
        cursor = await db.execute(
            """INSERT INTO assignments (module_id, course_id, title, description, questions_json, due_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (module_id, course_id, title, description, questions_json, due_date),
        )
        assignment_id = cursor.lastrowid
        await db.commit()
        return assignment_id

    async def get_pending_assignments(self, course_id: int | None = None) -> list[dict]:
        db = await self._get_conn()
        if course_id:
            query = """SELECT a.id, a.module_id, a.course_id, a.title, a.description, a.status, a.due_date, a.score, a.max_score, a.created_at, c.subject
                       FROM assignments a JOIN courses c ON a.course_id = c.id
                       WHERE a.course_id = ? AND a.status = 'pending' ORDER BY a.due_date"""
            cursor = db.execute(query, (course_id,))
        else:
            query = """SELECT a.id, a.module_id, a.course_id, a.title, a.description, a.status, a.due_date, a.score, a.max_score, a.created_at, c.subject
                       FROM assignments a JOIN courses c ON a.course_id = c.id
                       WHERE a.status = 'pending' ORDER BY a.due_date"""
            cursor = db.execute(query)
        async with cursor as cur:
            rows = await cur.fetchall()
            return [
                {
                    "id": r[0],
                    "module_id": r[1],
                    "course_id": r[2],
                    "title": r[3],
                    "description": r[4],
                    "status": r[5],
                    "due_date": r[6],
                    "score": r[7],
                    "max_score": r[8],
                    "created_at": r[9],
                    "subject": r[10],
                }
                for r in rows
            ]

    async def get_all_assignments(self, course_id: int | None = None) -> list[dict]:
        db = await self._get_conn()
        if course_id:
            query = """SELECT a.id, a.module_id, a.course_id, a.title, a.status, a.due_date, a.score, a.max_score, a.feedback, c.subject
                       FROM assignments a JOIN courses c ON a.course_id = c.id
                       WHERE a.course_id = ? ORDER BY a.created_at DESC"""
            cursor = db.execute(query, (course_id,))
        else:
            query = """SELECT a.id, a.module_id, a.course_id, a.title, a.status, a.due_date, a.score, a.max_score, a.feedback, c.subject
                       FROM assignments a JOIN courses c ON a.course_id = c.id
                       ORDER BY a.created_at DESC"""
            cursor = db.execute(query)
        async with cursor as cur:
            rows = await cur.fetchall()
            return [
                {
                    "id": r[0],
                    "module_id": r[1],
                    "course_id": r[2],
                    "title": r[3],
                    "status": r[4],
                    "due_date": r[5],
                    "score": r[6],
                    "max_score": r[7],
                    "feedback": r[8],
                    "subject": r[9],
                }
                for r in rows
            ]

    async def get_assignment(self, assignment_id: int) -> dict | None:
        db = await self._get_conn()
        async with db.execute(
            """SELECT a.*, c.subject FROM assignments a
               JOIN courses c ON a.course_id = c.id WHERE a.id = ?""",
            (assignment_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "module_id": row[1],
                "course_id": row[2],
                "title": row[3],
                "description": row[4],
                "questions_json": row[5],
                "status": row[6],
                "due_date": row[7],
                "submitted_at": row[8],
                "graded_at": row[9],
                "submission_json": row[10],
                "evaluation_json": row[11],
                "score": row[12],
                "max_score": row[13],
                "feedback": row[14],
                "created_at": row[15],
                "subject": row[16],
            }

    async def submit_assignment(self, assignment_id: int, submission_json: str):
        db = await self._get_conn()
        now = datetime.now().isoformat()
        await db.execute(
            "UPDATE assignments SET submission_json = ?, submitted_at = ?, status = 'submitted' WHERE id = ?",
            (submission_json, now, assignment_id),
        )
        await db.commit()

    async def grade_assignment(self, assignment_id: int, evaluation_json: str, score: float, feedback: str):
        db = await self._get_conn()
        now = datetime.now().isoformat()
        await db.execute(
            "UPDATE assignments SET evaluation_json = ?, score = ?, feedback = ?, graded_at = ?, status = 'graded' WHERE id = ?",
            (evaluation_json, score, feedback, now, assignment_id),
        )
        await db.commit()

    async def get_assignment_counts(self) -> dict:
        """Get assignment counts by status for notification badge."""
        db = await self._get_conn()
        counts = {"pending": 0, "submitted": 0, "graded": 0, "overdue": 0}
        async with db.execute("SELECT status, COUNT(*) FROM assignments GROUP BY status") as cursor:
            async for row in cursor:
                counts[row[0]] = row[1]
        # Count overdue separately
        now = datetime.now().isoformat()
        async with db.execute("SELECT COUNT(*) FROM assignments WHERE status = 'pending' AND due_date < ?", (now,)) as cursor:
            row = await cursor.fetchone()
            counts["overdue"] = row[0] if row else 0
        return counts

    async def get_module_assignment(self, module_id: int) -> dict | None:
        """Check if a module already has an assignment."""
        db = await self._get_conn()
        async with db.execute("SELECT id, status FROM assignments WHERE module_id = ? LIMIT 1", (module_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"id": row[0], "status": row[1]}
        return None

    async def can_complete_course(self, course_id: int) -> tuple[bool, int]:
        """Check if all module assignments are graded. Returns (can_complete, pending_count)."""
        db = await self._get_conn()
        async with db.execute(
            "SELECT COUNT(*) FROM assignments WHERE course_id = ? AND status != 'graded'",
            (course_id,),
        ) as cursor:
            row = await cursor.fetchone()
            pending = row[0] if row else 0
            return pending == 0, pending

    # ── Chat History ──────────────────────────────────────────

    async def save_chat(self, session_id: str, messages: list, context_snapshot: str = ""):
        db = await self._get_conn()
        msgs_json = json.dumps(messages)
        # Check if session exists
        async with db.execute("SELECT id FROM chat_history WHERE session_id = ?", (session_id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            await db.execute(
                "UPDATE chat_history SET messages_json = ?, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
                (msgs_json, session_id),
            )
        else:
            await db.execute(
                "INSERT INTO chat_history (session_id, messages_json, context_snapshot) VALUES (?, ?, ?)",
                (session_id, msgs_json, context_snapshot),
            )
        await db.commit()

    async def get_chat(self, session_id: str) -> list:
        db = await self._get_conn()
        async with db.execute("SELECT messages_json FROM chat_history WHERE session_id = ?", (session_id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
        return []

    async def get_chat_sessions(self) -> list[dict]:
        db = await self._get_conn()
        async with db.execute("SELECT session_id, messages_json, updated_at FROM chat_history ORDER BY updated_at DESC") as cursor:
            rows = await cursor.fetchall()
            sessions = []
            for r in rows:
                session_id = r[0]
                messages = json.loads(r[1]) if r[1] else []
                updated_at = r[2]
                snippet = "New Conversation"
                for msg in messages:
                    if msg.get("role") == "user" and msg.get("content"):
                        content = msg["content"]
                        if "[Voice Note Transcription]:" in content:
                            content = content.split("[Voice Note Transcription]:")[-1]
                        snippet = content[:60].strip() + ("..." if len(content) > 60 else "")
                        break
                sessions.append({"session_id": session_id, "snippet": snippet, "updated_at": updated_at})
            return sessions

    async def delete_chat_session(self, session_id: str):
        db = await self._get_conn()
        await db.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
        await db.commit()

    async def get_latest_chat_session(self) -> str:
        """Get or create a chat session ID."""
        db = await self._get_conn()
        async with db.execute("SELECT session_id FROM chat_history ORDER BY updated_at DESC LIMIT 1") as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
        return str(uuid.uuid4())

    async def new_chat_session(self) -> str:
        return str(uuid.uuid4())

    async def clear_all_chats(self):
        db = await self._get_conn()
        await db.execute("DELETE FROM chat_history")
        await db.commit()

    # ── Student Snapshot (for Tutor Context) ──────────────────

    async def get_student_snapshot(self) -> dict:
        """Comprehensive student data for tutor AI context. Lightweight — no raw lesson content."""
        profile = await self.get_profile() or {}
        courses = await self.get_courses()
        recent_quizzes = await self.get_recent_quiz_scores(10)
        assignment_counts = await self.get_assignment_counts()
        gamification = await self.get_gamification()
        credits_used = await self.get_credits_used_today()

        # Per-course module progress
        course_details = []
        for c in courses:
            modules = await self.get_modules(c["id"])
            total_m = len(modules)
            done_m = sum(1 for m in modules if m["is_completed"])
            course_details.append(
                {
                    "subject": c["subject"],
                    "level": c["level"],
                    "progress_pct": c["progress_pct"],
                    "modules_done": done_m,
                    "modules_total": total_m,
                }
            )

        # Identify weak areas from failed quizzes
        weak_areas = []
        for q in recent_quizzes:
            if not q["passed"]:
                weak_areas.append(f"{q['subject']}: {q['module']}")

        # Pending assignments
        pending_assignments = await self.get_pending_assignments()

        from core.constants import DAILY_CREDITS

        return {
            "profile": profile,
            "courses": course_details,
            "recent_quizzes": recent_quizzes[:5],
            "weak_areas": weak_areas[:5],
            "pending_assignments": pending_assignments,
            "assignment_counts": assignment_counts,
            "gamification": {
                "xp": gamification["xp_total"],
                "level": gamification["level"],
                "streak": gamification["current_streak"],
                "best_streak": gamification["best_streak"],
            },
            "credits_remaining": max(0, DAILY_CREDITS - credits_used),
        }

    # ── Credits ───────────────────────────────────────────────

    async def get_credits_used_today(self) -> int:
        db = await self._get_conn()
        today = date.today().isoformat()
        async with db.execute("SELECT SUM(credits_used) FROM credits_log WHERE date = ?", (today,)) as cursor:
            row = await cursor.fetchone()
            return row[0] or 0

    async def log_credit_usage(self, credits: int, action: str):
        db = await self._get_conn()
        today = date.today().isoformat()
        await db.execute(
            "INSERT INTO credits_log (date, credits_used, action) VALUES (?, ?, ?)",
            (today, credits, action),
        )
        await db.commit()

    # ── Gamification ──────────────────────────────────────────

    async def get_gamification(self) -> dict:
        db = await self._get_conn()
        async with db.execute("SELECT xp_total, level, current_streak, best_streak, badges_json, last_active_date FROM gamification WHERE id = 1") as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "xp_total": row[0],
                    "level": row[1],
                    "current_streak": row[2],
                    "best_streak": row[3],
                    "badges_json": row[4],
                    "last_active_date": row[5],
                }
        await db.execute("INSERT OR IGNORE INTO gamification (id) VALUES (1)")
        await db.commit()
        return {
            "xp_total": 0,
            "level": "Freshman",
            "current_streak": 0,
            "best_streak": 0,
            "badges_json": "[]",
            "last_active_date": None,
        }

    async def update_gamification(self, xp: int, level: str, streak: int, best_streak: int, badges: list):
        db = await self._get_conn()
        today = date.today().isoformat()
        await db.execute(
            """INSERT OR REPLACE INTO gamification
               (id, xp_total, level, current_streak, best_streak, badges_json, last_active_date)
               VALUES (1, ?, ?, ?, ?, ?, ?)""",
            (xp, level, streak, best_streak, json.dumps(badges), today),
        )
        await db.commit()

    # ── Parent / Stats ────────────────────────────────────────

    async def get_parent_stats(self) -> dict:
        db = await self._get_conn()
        stats = {"total_quizzes": 0, "avg_score": "0%", "last_active": "Never"}

        async with db.execute("SELECT COUNT(*), AVG(CASE WHEN total > 0 THEN score / total * 100 ELSE 0 END) FROM quiz_attempts") as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                stats["total_quizzes"] = row[0]
                stats["avg_score"] = f"{int(row[1])}%" if row[1] else "0%"

        async with db.execute("SELECT last_active_date FROM gamification WHERE id = 1") as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                stats["last_active"] = row[0]

        return stats

    # ── Misc ──────────────────────────────────────────────────

    async def update_login_timestamp(self):
        now = datetime.now().isoformat()
        await self.set_setting("last_login", now)

    async def check_daily_reward_eligibility(self) -> bool:
        last_login_str = await self.get_setting("last_login")
        if not last_login_str:
            return True
        last_login = datetime.fromisoformat(last_login_str)
        delta = datetime.now() - last_login
        return delta.total_seconds() > 86400

    # ── Timetable ─────────────────────────────────────────────

    async def get_timetable(self) -> list[dict]:
        db = await self._get_conn()
        async with db.execute("SELECT id, day, time_slot, subject, note FROM timetable ORDER BY day, time_slot") as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "day": r[1], "time_slot": r[2], "subject": r[3], "note": r[4]} for r in rows]

    async def add_timetable_entry(self, day: str, time_slot: str, subject: str, note: str = "") -> int:
        db = await self._get_conn()
        cursor = await db.execute(
            "INSERT INTO timetable (day, time_slot, subject, note) VALUES (?, ?, ?, ?)",
            (day, time_slot, subject, note),
        )
        await db.commit()
        return cursor.lastrowid

    async def delete_timetable_entry(self, entry_id: int):
        db = await self._get_conn()
        await db.execute("DELETE FROM timetable WHERE id = ?", (entry_id,))
        await db.commit()

    async def reset_database(self):
        db = await self._get_conn()
        # Temporarily disable foreign keys to avoid IntegrityError
        await db.execute("PRAGMA foreign_keys=OFF;")
        tables = [
            "profile",
            "courses",
            "modules",
            "quiz_attempts",
            "assessments",
            "assignments",
            # "credits_log" is preserved to prevent users resetting to refill daily tokens
            "gamification",
            "chat_history",
            "settings",
            "timetable",
        ]
        for t in tables:
            await db.execute(f"DELETE FROM {t}")
        await db.commit()
        # Re-enable foreign keys
        await db.execute("PRAGMA foreign_keys=ON;")

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None


db_manager = DatabaseManager()
