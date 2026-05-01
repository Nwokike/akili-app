"""Database manager — KTV connection-pooling pattern.

Single persistent connection with WAL mode for concurrent reads.
All methods use the shared connection instead of opening new ones.
"""

import json
import os
from datetime import date, datetime

import aiosqlite


class DatabaseManager:
    def __init__(self, db_path: str = "storage/data/akili.db"):
        self.db_path = os.path.abspath(db_path)
        self._conn = None

    async def _get_conn(self):
        """Lazy-init persistent connection (KTV pattern)."""
        if self._conn is None:
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            self._conn = await aiosqlite.connect(self.db_path)
            await self._conn.execute("PRAGMA journal_mode=WAL;")
        return self._conn

    async def init_db(self):
        """Create all tables."""
        db = await self._get_conn()

        await db.execute("""
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                education_level TEXT NOT NULL,
                avatar_index INTEGER DEFAULT 0,
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

        await db.execute("""
            CREATE TABLE IF NOT EXISTS quiz_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id INTEGER REFERENCES modules(id),
                score INTEGER,
                total INTEGER,
                questions_json TEXT,
                passed INTEGER DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER REFERENCES courses(id),
                score INTEGER,
                total INTEGER,
                grade TEXT,
                duration_seconds INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id INTEGER REFERENCES modules(id),
                messages_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        await db.commit()

    # ── Settings (KTV pattern) ───────────────────────────────────

    async def set_setting(self, key: str, value: str):
        db = await self._get_conn()
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
        await db.commit()

    async def get_setting(self, key: str, default=None):
        db = await self._get_conn()
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default

    # ── Profile ──────────────────────────────────────────────────

    async def save_profile(self, name: str, education_level: str, avatar_index: int = 0):
        db = await self._get_conn()
        await db.execute("DELETE FROM profile")  # Single user app
        await db.execute(
            "INSERT INTO profile (name, education_level, avatar_index) VALUES (?, ?, ?)",
            (name, education_level, avatar_index),
        )
        await db.commit()

    async def get_profile(self) -> dict | None:
        db = await self._get_conn()
        async with db.execute(
            "SELECT name, education_level, avatar_index FROM profile LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"name": row[0], "education_level": row[1], "avatar_index": row[2]}
        return None

    # ── Courses ──────────────────────────────────────────────────

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
        async with db.execute(
            "SELECT id, subject, level, curriculum_json, progress_pct, color_index FROM courses ORDER BY created_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "id": r[0], "subject": r[1], "level": r[2],
                    "curriculum_json": r[3], "progress_pct": r[4], "color_index": r[5],
                }
                for r in rows
            ]

    async def update_course_progress(self, course_id: int, progress: float):
        db = await self._get_conn()
        await db.execute("UPDATE courses SET progress_pct = ? WHERE id = ?", (progress, course_id))
        await db.commit()

    async def delete_course(self, course_id: int):
        db = await self._get_conn()
        await db.execute("DELETE FROM modules WHERE course_id = ?", (course_id,))
        await db.execute("DELETE FROM courses WHERE id = ?", (course_id,))
        await db.commit()

    # ── Modules ──────────────────────────────────────────────────

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
                    "id": r[0], "title": r[1], "topics_json": r[2], "lesson_cache": r[3],
                    "order_num": r[4], "is_unlocked": r[5], "is_completed": r[6],
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
        await db.execute(
            "UPDATE modules SET is_completed = 1 WHERE id = ?", (module_id,)
        )
        await db.commit()

    # ── Quiz Attempts ────────────────────────────────────────────

    async def save_quiz_attempt(self, module_id: int, score: int, total: int, questions_json: str, passed: int):
        db = await self._get_conn()
        await db.execute(
            "INSERT INTO quiz_attempts (module_id, score, total, questions_json, passed) VALUES (?, ?, ?, ?, ?)",
            (module_id, score, total, questions_json, passed),
        )
        await db.commit()

    async def get_quiz_stats(self) -> dict:
        db = await self._get_conn()
        async with db.execute(
            "SELECT COUNT(*), AVG(CAST(score AS FLOAT) / CAST(total AS FLOAT) * 100) FROM quiz_attempts"
        ) as cursor:
            row = await cursor.fetchone()
            return {"total_attempts": row[0] or 0, "avg_score": row[1] or 0.0}

    # ── Assessments (Mock Exams) ─────────────────────────────────

    async def save_assessment(self, course_id: int, score: int, total: int, grade: str, duration: int):
        db = await self._get_conn()
        await db.execute(
            "INSERT INTO assessments (course_id, score, total, grade, duration_seconds) VALUES (?, ?, ?, ?, ?)",
            (course_id, score, total, grade, duration),
        )
        await db.commit()

    # ── Credits ──────────────────────────────────────────────────

    async def get_credits_used_today(self) -> int:
        db = await self._get_conn()
        today = date.today().isoformat()
        async with db.execute(
            "SELECT SUM(credits_used) FROM credits_log WHERE date = ?", (today,)
        ) as cursor:
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

    # ── Gamification ─────────────────────────────────────────────

    async def get_gamification(self) -> dict:
        db = await self._get_conn()
        async with db.execute("SELECT * FROM gamification WHERE id = 1") as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "xp_total": row[1], "level": row[2], "current_streak": row[3],
                    "best_streak": row[4], "badges_json": row[5], "last_active_date": row[6],
                }
        # Initialize if not exists
        await db.execute(
            "INSERT OR IGNORE INTO gamification (id) VALUES (1)"
        )
        await db.commit()
        return {
            "xp_total": 0, "level": "Freshman", "current_streak": 0,
            "best_streak": 0, "badges_json": "[]", "last_active_date": None,
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

    # ── Chat History ─────────────────────────────────────────────

    async def save_chat(self, module_id: int, messages: list):
        db = await self._get_conn()
        msgs_json = json.dumps(messages)
        await db.execute(
            """INSERT OR REPLACE INTO chat_history (module_id, messages_json, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)""",
            (module_id, msgs_json),
        )
        await db.commit()

    async def get_chat(self, module_id: int) -> list:
        db = await self._get_conn()
        async with db.execute(
            "SELECT messages_json FROM chat_history WHERE module_id = ?", (module_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
        return []

    # ── Lifecycle ────────────────────────────────────────────────

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None


db_manager = DatabaseManager()
