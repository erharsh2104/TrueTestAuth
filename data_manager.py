"""SQLite persistence layer for TrueTestAuth.

Everything lives in one file, ``data/truetestauth.db`` (Python's built-in
``sqlite3``, no server and no extra package). Tables:

  users             — accounts (faculty + students), password hash, enrolled flag
  samples           — one row per keystroke-feature sample of a student
  enrollments       — which students are in which faculty's course
  exams             — exam definitions (questions stored as JSON text)
  exam_submissions  — one row per (student, exam): answers, score, integrity
  labs              — lab definitions (problems stored as JSON text)
  lab_submissions   — every lab attempt with its test results
  auth_logs         — behavioural-auth confidence timeline per session
  cp_logs           — copy-paste events per session

If the database is empty and the old ``data/*.json`` files exist, they are
imported once, automatically (the JSON files are left untouched).
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import uuid
from typing import Any, Dict, Iterator, List, Optional


# ── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_FILE = os.path.join(DATA_DIR, "truetestauth.db")

DEFAULT_STARTER_CODE: str = """#include <iostream>
using namespace std;

int main() {
    // your code here
    return 0;
}
"""

FEATURE_ORDER = [
    "mean_dwell", "std_dwell", "median_dwell", "max_dwell",
    "mean_flight", "std_flight", "median_flight", "min_flight",
    "typing_speed_wpm", "dwell_flight_ratio",
    "rhythm_consistency", "total_time_ms", "n_keys",
]
ENROLL_AFTER_SAMPLES = 10

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username      TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    full_name     TEXT NOT NULL DEFAULT '',
    role          TEXT NOT NULL,
    course_name   TEXT,
    enrollment_no TEXT,
    created_at    REAL NOT NULL,
    enrolled      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS samples (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    features TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_samples_user ON samples(username);

CREATE TABLE IF NOT EXISTS enrollments (
    student TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    faculty TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    since   REAL NOT NULL,
    PRIMARY KEY (student, faculty)
);
CREATE INDEX IF NOT EXISTS idx_enroll_faculty ON enrollments(faculty);

CREATE TABLE IF NOT EXISTS exams (
    exam_id       TEXT PRIMARY KEY,
    faculty       TEXT NOT NULL,
    title         TEXT NOT NULL,
    subject       TEXT,
    date          TEXT,
    start_time    TEXT,
    duration_mins INTEGER NOT NULL,
    instructions  TEXT,
    questions     TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'upcoming',
    created_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_exams_faculty ON exams(faculty);

CREATE TABLE IF NOT EXISTS exam_submissions (
    username   TEXT NOT NULL,
    exam_id    TEXT NOT NULL,
    session_id TEXT NOT NULL,
    answers    TEXT NOT NULL,
    score      INTEGER NOT NULL DEFAULT 0,
    integrity  TEXT,
    avg_conf   REAL NOT NULL DEFAULT 0,
    cp_count   INTEGER NOT NULL DEFAULT 0,
    timestamp  REAL NOT NULL,
    PRIMARY KEY (username, exam_id)
);

CREATE TABLE IF NOT EXISTS labs (
    lab_id      TEXT PRIMARY KEY,
    faculty     TEXT NOT NULL,
    title       TEXT NOT NULL,
    course      TEXT,
    deadline    TEXT,
    description TEXT,
    problems    TEXT NOT NULL,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_labs_faculty ON labs(faculty);

CREATE TABLE IF NOT EXISTS lab_submissions (
    submission_id TEXT PRIMARY KEY,
    username      TEXT NOT NULL,
    lab_id        TEXT NOT NULL,
    problem_id    TEXT NOT NULL,
    code          TEXT,
    results       TEXT NOT NULL,
    score         INTEGER NOT NULL DEFAULT 0,
    max_score     INTEGER NOT NULL DEFAULT 0,
    passed        INTEGER NOT NULL DEFAULT 0,
    total         INTEGER NOT NULL DEFAULT 0,
    compile_error TEXT,
    engine_used   TEXT,
    attempts      INTEGER NOT NULL DEFAULT 1,
    timestamp     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_labsub_user_prob ON lab_submissions(username, problem_id);
CREATE INDEX IF NOT EXISTS idx_labsub_lab ON lab_submissions(lab_id);

CREATE TABLE IF NOT EXISTS auth_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT NOT NULL,
    session_id TEXT NOT NULL,
    confidence REAL NOT NULL,
    status     TEXT NOT NULL,
    engine     TEXT NOT NULL DEFAULT 'continuous',
    timestamp  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_auth_user_session ON auth_logs(username, session_id);

CREATE TABLE IF NOT EXISTS cp_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT NOT NULL,
    session_id  TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    question_id TEXT,
    chars       INTEGER NOT NULL DEFAULT 0,
    timestamp   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cp_user_session ON cp_logs(username, session_id);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

_AUTH_COLS = "username, session_id, confidence, status, engine, timestamp"
_CP_COLS = "username, session_id, event_type, question_id, chars, timestamp"
_USER_UPDATABLE = {"password_hash", "full_name", "role", "course_name", "enrollment_no", "enrolled"}
_EXAM_UPDATABLE = {
    "faculty", "title", "subject", "date", "start_time", "duration_mins",
    "instructions", "questions", "status",
}


# ── Password hashing ─────────────────────────────────────────────────────────
_PBKDF2_ITERS = 200_000


def _hash(pw: str) -> str:
    """Salted PBKDF2-HMAC-SHA256 hash, stored as `pbkdf2$iters$salt$digest`."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", pw.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ITERS
    ).hex()
    return f"pbkdf2${_PBKDF2_ITERS}${salt}${digest}"


def _verify(pw: str, stored: str) -> bool:
    """Check `pw` against a stored hash (also accepts legacy unsalted SHA-256)."""
    if not stored:
        return False
    if stored.startswith("pbkdf2$"):
        try:
            _, iters, salt, digest = stored.split("$")
            cand = hashlib.pbkdf2_hmac(
                "sha256", pw.encode("utf-8"), bytes.fromhex(salt), int(iters)
            ).hex()
        except ValueError:
            return False
        return hmac.compare_digest(cand, digest)
    legacy = hashlib.sha256(pw.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy, stored)


# ── Small helpers ────────────────────────────────────────────────────────────
def _dump(obj: Any) -> str:
    return json.dumps(obj)


def _load(text: Optional[str]) -> Any:
    return json.loads(text) if text else None


def _read_legacy_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return default


def _exam(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    d["questions"] = _load(d["questions"]) or []
    return d


def _lab(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    d["problems"] = _load(d["problems"]) or []
    return d


def _exam_sub(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    d["answers"] = _load(d["answers"]) or {}
    d["integrity"] = _load(d["integrity"])
    return d


def _lab_sub(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    d["results"] = _load(d["results"]) or []
    return d


# ── DataManager ──────────────────────────────────────────────────────────────
class DataManager:
    """Single facade for all database access across the app.

    Each call opens its own short connection, so one instance can safely be
    shared by all Streamlit sessions/threads.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or DB_FILE
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        with self._conn() as con:
            con.executescript(_SCHEMA)
        self._auto_import_legacy_json()

    @contextlib.contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.db_path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        try:
            with con:  # commit on success, roll back on error
                yield con
        finally:
            con.close()

    # ── Users ───────────────────────────────────────────────────────────────
    @staticmethod
    def _user_dict(con: sqlite3.Connection, row: sqlite3.Row, with_samples: bool) -> Dict[str, Any]:
        d = dict(row)
        d["enrolled"] = bool(d["enrolled"])
        if with_samples:
            d["samples"] = DataManager._samples(con, d["username"])
        return d

    @staticmethod
    def _samples(con: sqlite3.Connection, username: str) -> List[List[float]]:
        rows = con.execute(
            "SELECT features FROM samples WHERE username = ? ORDER BY id", (username,)
        ).fetchall()
        return [json.loads(r["features"]) for r in rows]

    def user_exists(self, username: str) -> bool:
        with self._conn() as con:
            return con.execute(
                "SELECT 1 FROM users WHERE username = ?", (username,)
            ).fetchone() is not None

    def register_user(
        self,
        username: str,
        password: str,
        full_name: str,
        role: str,
        course_name: Optional[str] = None,
        enrollment_no: Optional[str] = None,
    ) -> bool:
        """Create a new account; returns False if username is taken."""
        try:
            with self._conn() as con:
                con.execute(
                    "INSERT INTO users (username, password_hash, full_name, role, course_name,"
                    " enrollment_no, created_at, enrolled) VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
                    (username, _hash(password), full_name, role, course_name,
                     enrollment_no, time.time()),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def login_user(
        self, username: str, password: str, role: str
    ) -> Optional[Dict[str, Any]]:
        with self._conn() as con:
            row = con.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if not row:
                return None
            if not _verify(password, row["password_hash"]):
                return None
            if row["role"] != role:
                return None
            if not row["password_hash"].startswith("pbkdf2$"):
                # Transparently upgrade legacy unsalted hashes on successful login.
                con.execute(
                    "UPDATE users SET password_hash = ? WHERE username = ?",
                    (_hash(password), username),
                )
                row = con.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            return self._user_dict(con, row, with_samples=True)

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        with self._conn() as con:
            row = con.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            return self._user_dict(con, row, with_samples=True) if row else None

    def update_user(self, username: str, updates: Dict[str, Any]) -> bool:
        unknown = set(updates) - _USER_UPDATABLE
        if unknown:
            raise ValueError(f"cannot update user fields: {sorted(unknown)}")
        if not updates:
            return self.user_exists(username)
        values = dict(updates)
        if "enrolled" in values:
            values["enrolled"] = int(bool(values["enrolled"]))
        sets = ", ".join(f"{k} = ?" for k in values)
        with self._conn() as con:
            cur = con.execute(
                f"UPDATE users SET {sets} WHERE username = ?", (*values.values(), username)
            )
            return cur.rowcount > 0

    def _users_by_role(self, role: str) -> List[Dict]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM users WHERE role = ? ORDER BY rowid", (role,)
            ).fetchall()
            return [self._user_dict(con, r, with_samples=False) for r in rows]

    def get_all_students(self) -> List[Dict]:
        return self._users_by_role("student")

    def get_all_faculty(self) -> List[Dict]:
        """Return list of all users with role='faculty'."""
        return self._users_by_role("faculty")

    def all_enrolled_users(self) -> List[str]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT username FROM users WHERE enrolled = 1 ORDER BY rowid"
            ).fetchall()
            return [r["username"] for r in rows]

    # ── Keystroke samples (for ML enrolment) ────────────────────────────────
    def add_sample(self, username: str, features: Any) -> int:
        """Append one keystroke-feature sample for `username`; returns count.
        Accepts both list and dict formats."""
        if isinstance(features, dict):
            features = [float(features.get(k, 0)) for k in FEATURE_ORDER]
        with self._conn() as con:
            if con.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone() is None:
                return 0
            con.execute(
                "INSERT INTO samples (username, features) VALUES (?, ?)",
                (username, _dump(list(features))),
            )
            count = con.execute(
                "SELECT COUNT(*) FROM samples WHERE username = ?", (username,)
            ).fetchone()[0]
            if count >= ENROLL_AFTER_SAMPLES:
                con.execute("UPDATE users SET enrolled = 1 WHERE username = ?", (username,))
            return count

    def save_keystroke_samples(self, username: str, samples: List[Any]) -> int:
        """Bulk-save multiple keystroke samples. Returns final count."""
        for s in samples:
            self.add_sample(username, s)
        return len(self.get_samples(username))

    def get_samples(self, username: str) -> List[List[float]]:
        with self._conn() as con:
            return self._samples(con, username)

    # ── Enrolments ──────────────────────────────────────────────────────────
    def enroll_student(self, student_username: str, faculty_username: str) -> bool:
        """Put a student in a faculty's course. False if either account is missing."""
        try:
            with self._conn() as con:
                con.execute(
                    "INSERT OR IGNORE INTO enrollments (student, faculty, since) VALUES (?, ?, ?)",
                    (student_username, faculty_username, time.time()),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def get_student_courses(self, student_username: str) -> List[Dict]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT u.* FROM enrollments e JOIN users u ON u.username = e.faculty"
                " WHERE e.student = ? ORDER BY e.rowid",
                (student_username,),
            ).fetchall()
            return [self._user_dict(con, r, with_samples=False) for r in rows]

    def get_faculty_students(self, faculty_username: str) -> List[Dict]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT u.* FROM enrollments e JOIN users u ON u.username = e.student"
                " WHERE e.faculty = ? ORDER BY e.rowid",
                (faculty_username,),
            ).fetchall()
            return [self._user_dict(con, r, with_samples=False) for r in rows]

    def get_exams_for_student(self, student_username: str) -> List[Dict]:
        """Return all exams from courses student is enrolled in."""
        courses = self.get_student_courses(student_username)
        exams = []
        for fac in courses:
            for e in self.get_exams(faculty_username=fac["username"]):
                sub = self.get_exam_submission(student_username, e["exam_id"])
                e_copy = dict(e)
                e_copy["faculty_name"] = fac.get("full_name", "")
                e_copy["course_name"] = fac.get("course_name", "")
                e_copy["submitted"] = sub is not None
                exams.append(e_copy)
        return exams

    def get_labs_for_student(self, student_username: str) -> List[Dict]:
        """Return all labs from courses student is enrolled in."""
        courses = self.get_student_courses(student_username)
        labs = []
        for fac in courses:
            for lab in self.get_labs(faculty_username=fac["username"]):
                lab_copy = dict(lab)
                lab_copy["faculty_name"] = fac.get("full_name", "")
                lab_copy["course_name"] = fac.get("course_name", "")
                labs.append(lab_copy)
        return labs

    def has_student_submitted_exam(self, student_username: str, exam_id: str) -> bool:
        return self.get_exam_submission(student_username, exam_id) is not None

    def has_student_submitted_lab(self, student_username: str, lab_id: str) -> bool:
        subs = self.get_lab_submissions(lab_id=lab_id, username=student_username)
        return len(subs) > 0

    # ── Exams ───────────────────────────────────────────────────────────────
    def create_exam(
        self,
        faculty_username: str,
        title: str,
        subject: str,
        date: str,
        duration_mins: int,
        instructions: str,
        questions: List[Dict],
        start_time: str = "10:00",
    ) -> str:
        eid = uuid.uuid4().hex[:8]
        with self._conn() as con:
            con.execute(
                "INSERT INTO exams (exam_id, faculty, title, subject, date, start_time,"
                " duration_mins, instructions, questions, status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'upcoming', ?)",
                (eid, faculty_username, title, subject, date, start_time,
                 int(duration_mins), instructions, _dump(questions), time.time()),
            )
        return eid

    def get_exam(self, exam_id: str) -> Optional[Dict]:
        with self._conn() as con:
            row = con.execute("SELECT * FROM exams WHERE exam_id = ?", (exam_id,)).fetchone()
            return _exam(row) if row else None

    def get_exams(self, faculty_username: Optional[str] = None) -> List[Dict]:
        sql, args = "SELECT * FROM exams", ()
        if faculty_username:
            sql, args = sql + " WHERE faculty = ?", (faculty_username,)
        with self._conn() as con:
            rows = con.execute(sql + " ORDER BY created_at DESC, rowid", args).fetchall()
            return [_exam(r) for r in rows]

    def update_exam(self, exam_id: str, updates: Dict[str, Any]) -> bool:
        unknown = set(updates) - _EXAM_UPDATABLE
        if unknown:
            raise ValueError(f"cannot update exam fields: {sorted(unknown)}")
        if not updates:
            return self.get_exam(exam_id) is not None
        values = dict(updates)
        if "questions" in values:
            values["questions"] = _dump(values["questions"])
        sets = ", ".join(f"{k} = ?" for k in values)
        with self._conn() as con:
            cur = con.execute(
                f"UPDATE exams SET {sets} WHERE exam_id = ?", (*values.values(), exam_id)
            )
            return cur.rowcount > 0

    def delete_exam(self, exam_id: str) -> bool:
        with self._conn() as con:
            return con.execute("DELETE FROM exams WHERE exam_id = ?", (exam_id,)).rowcount > 0

    # ── Exam submissions ────────────────────────────────────────────────────
    def save_exam_submission(
        self,
        username: str,
        exam_id: str,
        session_id: str,
        answers: Dict[str, str],
        auth_log: List[Dict],
        cp_log: List[Dict],
        score: int = 0,
        integrity: Optional[Dict] = None,
    ) -> str:
        avg_conf = (
            sum(a["confidence"] for a in auth_log) / len(auth_log)
            if auth_log
            else 0.0
        )
        with self._conn() as con:
            con.execute(
                "INSERT OR REPLACE INTO exam_submissions (username, exam_id, session_id,"
                " answers, score, integrity, avg_conf, cp_count, timestamp)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (username, exam_id, session_id, _dump(answers), score, _dump(integrity),
                 avg_conf, len(cp_log), time.time()),
            )
        return f"{username}::{exam_id}"

    def get_exam_submission(self, username: str, exam_id: str) -> Optional[Dict]:
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM exam_submissions WHERE username = ? AND exam_id = ?",
                (username, exam_id),
            ).fetchone()
            return _exam_sub(row) if row else None

    def get_exam_submissions(
        self,
        exam_id: Optional[str] = None,
        username: Optional[str] = None,
    ) -> List[Dict]:
        where, args = [], []
        if exam_id:
            where.append("exam_id = ?")
            args.append(exam_id)
        if username:
            where.append("username = ?")
            args.append(username)
        sql = "SELECT * FROM exam_submissions"
        if where:
            sql += " WHERE " + " AND ".join(where)
        with self._conn() as con:
            rows = con.execute(sql + " ORDER BY timestamp DESC, rowid", args).fetchall()
            return [_exam_sub(r) for r in rows]

    # ── Labs ────────────────────────────────────────────────────────────────
    def create_lab(
        self,
        faculty_username: str,
        title: str,
        course: str,
        deadline: str,
        description: str,
        problems: List[Dict],
    ) -> str:
        lid = uuid.uuid4().hex[:8]
        prepared: List[Dict] = []
        for p in problems:
            prepared.append(
                {
                    "problem_id": p.get("problem_id") or f"prob_{uuid.uuid4().hex[:8]}",
                    "title": p.get("title", ""),
                    "difficulty": p.get("difficulty", "Easy"),
                    "statement": p.get("statement", ""),
                    "time_limit_s": int(p.get("time_limit_s", 3)),
                    "memory_limit_mb": int(p.get("memory_limit_mb", 64)),
                    "samples": p.get("samples", []),
                    "test_cases": p.get("test_cases", []),
                    "starter_code": p.get("starter_code") or DEFAULT_STARTER_CODE,
                    "total_points": sum(
                        int(t.get("points", 0)) for t in p.get("test_cases", [])
                    ),
                }
            )
        with self._conn() as con:
            con.execute(
                "INSERT INTO labs (lab_id, faculty, title, course, deadline, description,"
                " problems, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (lid, faculty_username, title, course, deadline, description,
                 _dump(prepared), time.time()),
            )
        return lid

    def get_lab(self, lab_id: str) -> Optional[Dict]:
        with self._conn() as con:
            row = con.execute("SELECT * FROM labs WHERE lab_id = ?", (lab_id,)).fetchone()
            return _lab(row) if row else None

    def get_labs(self, faculty_username: Optional[str] = None) -> List[Dict]:
        sql, args = "SELECT * FROM labs", ()
        if faculty_username:
            sql, args = sql + " WHERE faculty = ?", (faculty_username,)
        with self._conn() as con:
            rows = con.execute(sql + " ORDER BY created_at DESC, rowid", args).fetchall()
            return [_lab(r) for r in rows]

    # ── Lab submissions ─────────────────────────────────────────────────────
    def save_lab_submission(
        self,
        username: str,
        lab_id: str,
        problem_id: str,
        code: str,
        test_results: List[Dict],
        score: int,
        max_score: int,
        engine_used: str = "",
        compile_error: str = "",
    ) -> str:
        sid = uuid.uuid4().hex[:10]
        with self._conn() as con:
            attempts = con.execute(
                "SELECT COUNT(*) FROM lab_submissions WHERE username = ? AND problem_id = ?",
                (username, problem_id),
            ).fetchone()[0] + 1
            con.execute(
                "INSERT INTO lab_submissions (submission_id, username, lab_id, problem_id, code,"
                " results, score, max_score, passed, total, compile_error, engine_used,"
                " attempts, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sid, username, lab_id, problem_id, code, _dump(test_results), int(score),
                 int(max_score), sum(1 for r in test_results if r.get("status") == "pass"),
                 len(test_results), compile_error, engine_used, attempts, time.time()),
            )
        return sid

    def get_lab_submissions(
        self,
        lab_id: Optional[str] = None,
        username: Optional[str] = None,
        problem_id: Optional[str] = None,
    ) -> List[Dict]:
        where, args = [], []
        for col, val in (("lab_id", lab_id), ("username", username), ("problem_id", problem_id)):
            if val:
                where.append(f"{col} = ?")
                args.append(val)
        sql = "SELECT * FROM lab_submissions"
        if where:
            sql += " WHERE " + " AND ".join(where)
        with self._conn() as con:
            rows = con.execute(sql + " ORDER BY timestamp DESC, rowid", args).fetchall()
            return [_lab_sub(r) for r in rows]

    def get_best_lab_submission(
        self, username: str, problem_id: str
    ) -> Optional[Dict]:
        rows = self.get_lab_submissions(username=username, problem_id=problem_id)
        if not rows:
            return None
        return max(rows, key=lambda r: r.get("score", 0))

    # ── Auth logs ───────────────────────────────────────────────────────────
    def log_auth_check(
        self,
        username: str,
        session_id: str,
        confidence: float,
        status: str,
        engine: str = "continuous",
    ) -> None:
        with self._conn() as con:
            con.execute(
                f"INSERT INTO auth_logs ({_AUTH_COLS}) VALUES (?, ?, ?, ?, ?, ?)",
                (username, session_id, float(confidence), status, engine, time.time()),
            )

    def get_auth_log(self, username: str, session_id: str) -> List[Dict]:
        with self._conn() as con:
            rows = con.execute(
                f"SELECT {_AUTH_COLS} FROM auth_logs WHERE username = ? AND session_id = ?"
                " ORDER BY id",
                (username, session_id),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_student_auth_summary(self, username: str) -> Dict[str, Any]:
        with self._conn() as con:
            rows = [
                dict(r)
                for r in con.execute(
                    f"SELECT {_AUTH_COLS} FROM auth_logs WHERE username = ? ORDER BY id",
                    (username,),
                ).fetchall()
            ]
        if not rows:
            return {
                "avg_conf": 0.0,
                "min_conf": 0.0,
                "total_checks": 0,
                "flag_count": 0,
                "entries": [],
            }
        confs = [r["confidence"] for r in rows]
        return {
            "avg_conf": sum(confs) / len(confs),
            "min_conf": min(confs),
            "total_checks": len(rows),
            "flag_count": sum(1 for r in rows if r["status"] == "Flagged"),
            "entries": rows,
        }

    def get_per_exam_summary(self, username: str) -> List[Dict]:
        out = []
        subs = self.get_exam_submissions(username=username)
        for s in subs:
            log = self.get_auth_log(username, s["session_id"])
            cp = self.get_cp_log(username, s["session_id"])
            avg = sum(a["confidence"] for a in log) / len(log) if log else 0.0
            mn = min((a["confidence"] for a in log), default=0.0)
            exam = self.get_exam(s["exam_id"])
            out.append(
                {
                    "Exam": exam["title"] if exam else s["exam_id"],
                    "Avg confidence": f"{avg*100:.1f}%",
                    "Min confidence": f"{mn*100:.1f}%",
                    "Checks": len(log),
                    "Flags": sum(1 for a in log if a["status"] == "Flagged"),
                    "Pastes": len(cp),
                    "Integrity": (s.get("integrity") or {}).get("grade", "—"),
                }
            )
        return out

    def get_academic_history(self, username: str) -> List[Dict]:
        rows: List[Dict] = []
        for s in self.get_exam_submissions(username=username):
            exam = self.get_exam(s["exam_id"])
            rows.append(
                {
                    "Type": "Exam",
                    "Title": exam["title"] if exam else s["exam_id"],
                    "Score": s.get("score", 0),
                    "Submitted": time.strftime(
                        "%Y-%m-%d %H:%M", time.localtime(s["timestamp"])
                    ),
                }
            )
        for s in self.get_lab_submissions(username=username):
            lab = self.get_lab(s["lab_id"])
            rows.append(
                {
                    "Type": "Lab",
                    "Title": (lab["title"] if lab else s["lab_id"])
                    + " — "
                    + s["problem_id"],
                    "Score": f"{s['score']}/{s['max_score']}",
                    "Submitted": time.strftime(
                        "%Y-%m-%d %H:%M", time.localtime(s["timestamp"])
                    ),
                }
            )
        return rows

    def get_recent_submissions(
        self, faculty_username: str, limit: int = 5
    ) -> List[Dict]:
        sql = """
            SELECT 'exam: ' || e.title AS kind, s.username AS username,
                   COALESCE(u.full_name, s.username) AS student_name, s.timestamp AS timestamp
            FROM exam_submissions s
            JOIN exams e ON e.exam_id = s.exam_id AND e.faculty = ?
            LEFT JOIN users u ON u.username = s.username
            UNION ALL
            SELECT 'lab: ' || l.title, s.username,
                   COALESCE(u.full_name, s.username), s.timestamp
            FROM lab_submissions s
            JOIN labs l ON l.lab_id = s.lab_id AND l.faculty = ?
            LEFT JOIN users u ON u.username = s.username
            ORDER BY timestamp DESC
            LIMIT ?
        """
        with self._conn() as con:
            rows = con.execute(sql, (faculty_username, faculty_username, int(limit))).fetchall()
            return [dict(r) for r in rows]

    def get_flagged_recent(
        self, faculty_username: str, hours: int = 24
    ) -> List[Dict]:
        cutoff = time.time() - hours * 3600
        sql = """
            SELECT a.username, a.session_id, a.confidence, a.status, a.engine, a.timestamp,
                   COALESCE(u.full_name, a.username) AS student_name
            FROM auth_logs a
            JOIN enrollments e ON e.student = a.username AND e.faculty = ?
            LEFT JOIN users u ON u.username = a.username
            WHERE a.status = 'Flagged' AND a.timestamp >= ?
            ORDER BY a.timestamp DESC
        """
        with self._conn() as con:
            return [dict(r) for r in con.execute(sql, (faculty_username, cutoff)).fetchall()]

    # ── Copy-paste logs ─────────────────────────────────────────────────────
    def log_cp_event(
        self,
        username: str,
        session_id: str,
        event_type: str,
        question_id: str,
        chars: int,
    ) -> None:
        with self._conn() as con:
            con.execute(
                f"INSERT INTO cp_logs ({_CP_COLS}) VALUES (?, ?, ?, ?, ?, ?)",
                (username, session_id, event_type, question_id, int(chars), time.time()),
            )

    def get_cp_log(self, username: str, session_id: str) -> List[Dict]:
        with self._conn() as con:
            rows = con.execute(
                f"SELECT {_CP_COLS} FROM cp_logs WHERE username = ? AND session_id = ?"
                " ORDER BY id",
                (username, session_id),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Integrity score ─────────────────────────────────────────────────────
    @staticmethod
    def calculate_integrity_score(
        avg_confidence: float, paste_count: int
    ) -> Dict[str, Any]:
        behavioral_score = max(0.0, min(100.0, avg_confidence * 100))
        paste_penalty = {0: 100, 1: 80, 2: 55}.get(paste_count, 20 if paste_count else 100)
        if paste_count >= 3:
            paste_penalty = 20
        integrity_score = behavioral_score * 0.6 + paste_penalty * 0.4
        if integrity_score >= 70:
            grade = "High"
        elif integrity_score >= 40:
            grade = "Suspicious"
        else:
            grade = "Flagged"
        return {
            "behavioral_score": behavioral_score,
            "paste_penalty": paste_penalty,
            "integrity_score": integrity_score,
            "grade": grade,
        }

    # ── One-time import of the old JSON files ───────────────────────────────
    def _auto_import_legacy_json(self) -> None:
        """Import data/*.json once, if the database is still empty."""
        with self._conn() as con:
            done = con.execute(
                "SELECT 1 FROM meta WHERE key = 'legacy_json_imported'"
            ).fetchone()
            empty = con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        legacy_users = os.path.join(os.path.dirname(os.path.abspath(self.db_path)), "users.json")
        if not done and empty and os.path.exists(legacy_users):
            self.import_json(os.path.dirname(legacy_users))

    def import_json(self, data_dir: str) -> Dict[str, int]:
        """Copy the old JSON files from `data_dir` into the database.

        Returns how many rows were imported per table. Rows that point to a
        user that does not exist are skipped. The JSON files are not changed.
        """
        rd = lambda name, default: _read_legacy_json(os.path.join(data_dir, name), default)
        users = rd("users.json", {})
        enrollments = rd("enrollments.json", [])
        exams = rd("exams.json", {})
        labs = rd("labs.json", {})
        subs = rd("submissions.json", {})
        lab_subs = rd("lab_submissions.json", [])
        auth = rd("auth_logs.json", [])
        cp = rd("cp_logs.json", [])

        n = {k: 0 for k in (
            "users", "samples", "enrollments", "exams", "exam_submissions",
            "labs", "lab_submissions", "auth_logs", "cp_logs")}
        now = time.time()
        with self._conn() as con:
            for name, u in users.items():
                con.execute(
                    "INSERT OR IGNORE INTO users (username, password_hash, full_name, role,"
                    " course_name, enrollment_no, created_at, enrolled) VALUES (?,?,?,?,?,?,?,?)",
                    (u.get("username", name), u.get("password_hash", ""), u.get("full_name", ""),
                     u.get("role", "student"), u.get("course_name"), u.get("enrollment_no"),
                     u.get("created_at", now), int(bool(u.get("enrolled")))),
                )
                n["users"] += 1
                for feats in u.get("samples", []):
                    con.execute(
                        "INSERT INTO samples (username, features) VALUES (?, ?)",
                        (u.get("username", name), _dump(feats)),
                    )
                    n["samples"] += 1
            known = {r[0] for r in con.execute("SELECT username FROM users")}
            for r in enrollments:
                if r.get("student") in known and r.get("faculty") in known:
                    con.execute(
                        "INSERT OR IGNORE INTO enrollments (student, faculty, since) VALUES (?,?,?)",
                        (r["student"], r["faculty"], r.get("since", now)),
                    )
                    n["enrollments"] += 1
            for eid, e in exams.items():
                con.execute(
                    "INSERT OR IGNORE INTO exams (exam_id, faculty, title, subject, date,"
                    " start_time, duration_mins, instructions, questions, status, created_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (e.get("exam_id", eid), e.get("faculty", ""), e.get("title", ""),
                     e.get("subject"), e.get("date"), e.get("start_time", "10:00"),
                     int(e.get("duration_mins", 0)), e.get("instructions"),
                     _dump(e.get("questions", [])), e.get("status", "upcoming"),
                     e.get("created_at", now)),
                )
                n["exams"] += 1
            for lid, lab in labs.items():
                con.execute(
                    "INSERT OR IGNORE INTO labs (lab_id, faculty, title, course, deadline,"
                    " description, problems, created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (lab.get("lab_id", lid), lab.get("faculty", ""), lab.get("title", ""),
                     lab.get("course"), lab.get("deadline"), lab.get("description"),
                     _dump(lab.get("problems", [])), lab.get("created_at", now)),
                )
                n["labs"] += 1
            for s in subs.values():
                con.execute(
                    "INSERT OR REPLACE INTO exam_submissions (username, exam_id, session_id,"
                    " answers, score, integrity, avg_conf, cp_count, timestamp)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (s["username"], s["exam_id"], s.get("session_id", ""),
                     _dump(s.get("answers", {})), int(s.get("score", 0)),
                     _dump(s.get("integrity")), float(s.get("avg_conf", 0.0)),
                     int(s.get("cp_count", 0)), s.get("timestamp", now)),
                )
                n["exam_submissions"] += 1
            for s in lab_subs:
                con.execute(
                    "INSERT OR IGNORE INTO lab_submissions (submission_id, username, lab_id,"
                    " problem_id, code, results, score, max_score, passed, total, compile_error,"
                    " engine_used, attempts, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (s.get("submission_id") or uuid.uuid4().hex[:10], s["username"], s["lab_id"],
                     s["problem_id"], s.get("code", ""), _dump(s.get("results", [])),
                     int(s.get("score", 0)), int(s.get("max_score", 0)),
                     int(s.get("passed", 0)), int(s.get("total", 0)),
                     s.get("compile_error", ""), s.get("engine_used", ""),
                     int(s.get("attempts", 1)), s.get("timestamp", now)),
                )
                n["lab_submissions"] += 1
            for r in auth:
                con.execute(
                    f"INSERT INTO auth_logs ({_AUTH_COLS}) VALUES (?,?,?,?,?,?)",
                    (r["username"], r["session_id"], float(r["confidence"]), r["status"],
                     r.get("engine", "continuous"), r.get("timestamp", now)),
                )
                n["auth_logs"] += 1
            for r in cp:
                con.execute(
                    f"INSERT INTO cp_logs ({_CP_COLS}) VALUES (?,?,?,?,?,?)",
                    (r["username"], r["session_id"], r.get("event_type", ""),
                     r.get("question_id", ""), int(r.get("chars", 0)), r.get("timestamp", now)),
                )
                n["cp_logs"] += 1
            con.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('legacy_json_imported', ?)",
                (_dump(n),),
            )
        return n
