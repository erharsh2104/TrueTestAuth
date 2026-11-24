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
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Tuple


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
MIN_PASSWORD_LENGTH = 8  # enforced when changing / resetting a password

# Attempt limits, stored in the database so a page refresh, a new tab or
# restarting the exam cannot reset them: (failures allowed, window in seconds).
# A lock lifts by itself once enough of the failures are older than the window.
LOCKOUT_RULES: Dict[str, Tuple[int, int]] = {
    "password": (5, 15 * 60),      # wrong username/password at the login form
    "login_phrase": (3, 15 * 60),  # failed typing check right after login
    "exam_gate": (3, 15 * 60),     # failed identity check before one exam (scope = exam_id)
}

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
    created_at    REAL NOT NULL,
    window_mins   INTEGER,
    max_leaves    INTEGER,
    require_fullscreen INTEGER
);
CREATE INDEX IF NOT EXISTS idx_exams_faculty ON exams(faculty);

CREATE TABLE IF NOT EXISTS exam_drafts (
    username   TEXT NOT NULL,
    exam_id    TEXT NOT NULL,
    session_id TEXT NOT NULL,
    answers    TEXT NOT NULL,
    started_at REAL NOT NULL,
    deadline   REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (username, exam_id)
);

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

CREATE TABLE IF NOT EXISTS focus_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT NOT NULL,
    exam_id    TEXT NOT NULL,
    session_id TEXT NOT NULL,
    kind       TEXT NOT NULL,
    episode    INTEGER NOT NULL,
    away_ms    INTEGER NOT NULL DEFAULT 0,
    excused    INTEGER NOT NULL DEFAULT 0,
    timestamp  REAL NOT NULL,
    UNIQUE (session_id, episode)
);
CREATE INDEX IF NOT EXISTS idx_focus_user_exam ON focus_events(username, exam_id);

CREATE TABLE IF NOT EXISTS exam_monitor (
    username  TEXT NOT NULL,
    exam_id   TEXT NOT NULL,
    last_beat REAL NOT NULL,
    max_gap   REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (username, exam_id)
);

CREATE TABLE IF NOT EXISTS verify_attempts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT NOT NULL,
    kind       TEXT NOT NULL,
    scope      TEXT NOT NULL DEFAULT '',
    ok         INTEGER NOT NULL,
    confidence REAL,
    timestamp  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_verify_lookup ON verify_attempts(username, kind, scope);

CREATE TABLE IF NOT EXISTS materials (
    material_id TEXT PRIMARY KEY,
    faculty     TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    filename    TEXT,
    slides      TEXT NOT NULL,
    topics      TEXT NOT NULL,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_materials_faculty ON materials(faculty);

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
    "instructions", "questions", "status", "window_mins", "max_leaves", "require_fullscreen",
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


def exam_window(exam: Dict[str, Any]) -> Tuple[float, float]:
    """(opens_ts, closes_ts) in server-local time.

    Students may start between the two. `window_mins` is how long the exam stays
    open to start; when unset it equals the duration. An unparseable date means
    "always open" so old data can never lock students out.
    """
    try:
        opens = datetime.strptime(
            f"{exam['date']} {exam.get('start_time') or '00:00'}", "%Y-%m-%d %H:%M"
        ).timestamp()
    except (ValueError, TypeError, KeyError):
        return 0.0, float("inf")
    span = int(exam.get("window_mins") or exam.get("duration_mins") or 0)
    return opens, opens + span * 60


def exam_state(exam: Dict[str, Any], now: Optional[float] = None) -> str:
    """'upcoming', 'open' or 'closed' for the exam's start window."""
    now = time.time() if now is None else now
    opens, closes = exam_window(exam)
    if now < opens:
        return "upcoming"
    return "open" if now < closes else "closed"


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
            # Databases created before the exam window existed need the new column.
            cols = {r["name"] for r in con.execute("PRAGMA table_info(exams)")}
            for col in ("window_mins", "max_leaves", "require_fullscreen"):
                if col not in cols:
                    con.execute(f"ALTER TABLE exams ADD COLUMN {col} INTEGER")
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
                # Usernames are stored lowercase by the sign-up forms, so accept
                # "Alice_CS" for "alice_cs" (only when exactly one account fits).
                matches = con.execute(
                    "SELECT * FROM users WHERE lower(username) = lower(?)", (username,)
                ).fetchall()
                row = matches[0] if len(matches) == 1 else None
            if not row:
                return None
            username = row["username"]  # canonical spelling for the rest of the login
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

    def change_password(self, username: str, current: str, new: str) -> bool:
        """Change a password after checking the current one (False if it is wrong)."""
        with self._conn() as con:
            row = con.execute(
                "SELECT password_hash FROM users WHERE username = ?", (username,)
            ).fetchone()
            if not row or not _verify(current, row["password_hash"]):
                return False
            con.execute(
                "UPDATE users SET password_hash = ? WHERE username = ?",
                (_hash(new), username),
            )
        return True

    def reset_password(self, username: str, new_password: str) -> bool:
        """Set a new password (admin use) and clear that account's attempt lock.

        The app has no self-service reset; `reset_password.py` is the way to
        recover an account. Returns False if the username does not exist.
        """
        if not self.update_user(username, {"password_hash": _hash(new_password)}):
            return False
        with self._conn() as con:
            con.execute(
                "DELETE FROM verify_attempts WHERE username = ?", (self._attempt_key(username),)
            )
        return True

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

    def unenroll_student(self, student_username: str, faculty_username: str) -> bool:
        """Remove a student from a faculty's course (their past work is kept)."""
        with self._conn() as con:
            return con.execute(
                "DELETE FROM enrollments WHERE student = ? AND faculty = ?",
                (student_username, faculty_username),
            ).rowcount > 0

    def is_enrolled(self, student_username: str, faculty_username: str) -> bool:
        with self._conn() as con:
            return con.execute(
                "SELECT 1 FROM enrollments WHERE student = ? AND faculty = ?",
                (student_username, faculty_username),
            ).fetchone() is not None

    def get_unenrolled_students(self, faculty_username: str) -> List[Dict]:
        """Registered students who are not (yet) in this faculty's course."""
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM users WHERE role = 'student' AND username NOT IN"
                " (SELECT student FROM enrollments WHERE faculty = ?) ORDER BY rowid",
                (faculty_username,),
            ).fetchall()
            return [self._user_dict(con, r, with_samples=False) for r in rows]

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
        window_mins: Optional[int] = None,
        max_leaves: int = 0,
        require_fullscreen: bool = False,
    ) -> str:
        """`max_leaves`: leaving the exam tab this many times auto-submits (0 = off)."""
        eid = uuid.uuid4().hex[:8]
        with self._conn() as con:
            con.execute(
                "INSERT INTO exams (exam_id, faculty, title, subject, date, start_time,"
                " duration_mins, instructions, questions, status, created_at, window_mins,"
                " max_leaves, require_fullscreen)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'upcoming', ?, ?, ?, ?)",
                (eid, faculty_username, title, subject, date, start_time,
                 int(duration_mins), instructions, _dump(questions), time.time(),
                 int(window_mins) if window_mins else None,
                 max(0, int(max_leaves)), int(bool(require_fullscreen))),
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

    # ── In-progress exam drafts (answers survive refresh / crash) ───────────
    @staticmethod
    def _draft(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d["answers"] = _load(d["answers"]) or {}
        return d

    def start_draft(
        self, username: str, exam_id: str, session_id: str, started_at: float, deadline: float
    ) -> Dict[str, Any]:
        """Create the draft for an attempt (keeps an existing one) and return it."""
        with self._conn() as con:
            con.execute(
                "INSERT OR IGNORE INTO exam_drafts (username, exam_id, session_id, answers,"
                " started_at, deadline, updated_at) VALUES (?, ?, ?, '{}', ?, ?, ?)",
                (username, exam_id, session_id, started_at, deadline, time.time()),
            )
            return self._draft(con.execute(
                "SELECT * FROM exam_drafts WHERE username = ? AND exam_id = ?",
                (username, exam_id),
            ).fetchone())

    def update_draft_answers(self, username: str, exam_id: str, answers: Dict[str, str]) -> bool:
        """Save answers into an existing draft only (never recreates a finished one)."""
        with self._conn() as con:
            return con.execute(
                "UPDATE exam_drafts SET answers = ?, updated_at = ?"
                " WHERE username = ? AND exam_id = ?",
                (_dump(answers), time.time(), username, exam_id),
            ).rowcount > 0

    def get_draft(self, username: str, exam_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM exam_drafts WHERE username = ? AND exam_id = ?",
                (username, exam_id),
            ).fetchone()
            return self._draft(row) if row else None

    def delete_draft(self, username: str, exam_id: str) -> None:
        with self._conn() as con:
            con.execute(
                "DELETE FROM exam_drafts WHERE username = ? AND exam_id = ?",
                (username, exam_id),
            )

    def get_expired_drafts(
        self, username: Optional[str] = None, exam_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Drafts whose deadline has passed (they still need to be submitted)."""
        where, args = ["deadline <= ?"], [time.time()]
        if username:
            where.append("username = ?")
            args.append(username)
        if exam_id:
            where.append("exam_id = ?")
            args.append(exam_id)
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM exam_drafts WHERE " + " AND ".join(where), args
            ).fetchall()
            return [self._draft(r) for r in rows]

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

    # ── Lecture materials (slides + topics) ─────────────────────────────────
    def create_material(
        self,
        faculty_username: str,
        title: str,
        filename: str,
        slides: List[Dict],
        topics: List[Dict],
    ) -> str:
        mid = uuid.uuid4().hex[:8]
        with self._conn() as con:
            con.execute(
                "INSERT INTO materials (material_id, faculty, title, filename, slides,"
                " topics, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (mid, faculty_username, title, filename, _dump(slides), _dump(topics),
                 time.time()),
            )
        return mid

    @staticmethod
    def _material(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d["slides"] = _load(d["slides"]) or []
        d["topics"] = _load(d["topics"]) or []
        return d

    def get_materials(self, faculty_username: str) -> List[Dict]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM materials WHERE faculty = ? ORDER BY created_at DESC, rowid",
                (faculty_username,),
            ).fetchall()
            return [self._material(r) for r in rows]

    def delete_material(self, material_id: str, faculty_username: str) -> bool:
        with self._conn() as con:
            return con.execute(
                "DELETE FROM materials WHERE material_id = ? AND faculty = ?",
                (material_id, faculty_username),
            ).rowcount > 0

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
            avg = sum(a["confidence"] for a in log) / len(log) if log else None
            mn = min((a["confidence"] for a in log), default=None)
            exam = self.get_exam(s["exam_id"])
            out.append(
                {
                    "Exam": exam["title"] if exam else s["exam_id"],
                    "Avg confidence": f"{avg*100:.1f}%" if log else "—",
                    "Min confidence": f"{mn*100:.1f}%" if log else "—",
                    "Checks": len(log),
                    "Flags": sum(1 for a in log if a["status"] == "Flagged"),
                    "Pastes": len(cp),
                    "Tab leaves": self.count_focus_leaves(username, s["exam_id"]),
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

    # ── Verification attempts: limits + faculty alerts ──────────────────────
    @staticmethod
    def _attempt_key(username: str) -> str:
        """Normalise a typed username so 'Alice' and 'alice ' share one counter."""
        return (username or "").strip().lower()[:64]

    def record_attempt(
        self, username: str, kind: str, ok: bool, scope: str = "",
        confidence: Optional[float] = None,
    ) -> None:
        """Remember one password / typing-check attempt (a success resets the count)."""
        if kind not in LOCKOUT_RULES:
            raise ValueError(f"unknown attempt kind: {kind!r}")
        now = time.time()
        conf = float(confidence) if confidence is not None and confidence == confidence else None
        with self._conn() as con:
            con.execute(
                "INSERT INTO verify_attempts (username, kind, scope, ok, confidence, timestamp)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (self._attempt_key(username), kind, scope or "", int(bool(ok)), conf, now),
            )
            con.execute("DELETE FROM verify_attempts WHERE timestamp < ?", (now - 7 * 86400,))

    def lockout_state(self, username: str, kind: str, scope: str = "") -> Dict[str, Any]:
        """Is this person locked out of `kind` right now?

        Counts failures since the last success inside the sliding window. Once the
        limit is reached the lock lasts until enough of those failures age out.
        Returns {locked, fails, max_fails, remaining_s}.
        """
        max_fails, window = LOCKOUT_RULES[kind]
        now = time.time()
        with self._conn() as con:
            rows = con.execute(
                "SELECT ok, timestamp FROM verify_attempts"
                " WHERE username = ? AND kind = ? AND scope = ? AND timestamp >= ?"
                " ORDER BY id DESC",
                (self._attempt_key(username), kind, scope or "", now - window),
            ).fetchall()
        fails: List[float] = []
        for r in rows:  # newest first; stop at the most recent success
            if r["ok"]:
                break
            fails.append(r["timestamp"])
        locked = len(fails) >= max_fails
        remaining = int(fails[max_fails - 1] + window - now) + 1 if locked else 0
        return {
            "locked": locked,
            "fails": len(fails),
            "max_fails": max_fails,
            "remaining_s": max(0, remaining),
        }

    def get_verification_alerts(
        self, faculty_username: str, hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Students of this faculty who hit an attempt limit recently (newest first).

        A single typo that was followed by a success is not an alert; only a run
        of failures that reached the limit is.
        """
        since = time.time() - hours * 3600
        sql = """
            SELECT a.username, a.kind, a.scope, a.ok, a.confidence, a.timestamp,
                   COALESCE(u.full_name, a.username) AS student_name
            FROM verify_attempts a
            JOIN enrollments e ON e.student = a.username AND e.faculty = ?
            LEFT JOIN users u ON u.username = a.username
            WHERE a.timestamp >= ?
            ORDER BY a.id
        """
        with self._conn() as con:
            rows = con.execute(sql, (faculty_username, since)).fetchall()
            titles = {
                r["exam_id"]: r["title"]
                for r in con.execute(
                    "SELECT exam_id, title FROM exams WHERE faculty = ?", (faculty_username,)
                )
            }
        runs: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        alerts: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        for r in rows:
            key = (r["username"], r["kind"], r["scope"])
            if r["ok"]:
                runs.pop(key, None)
                continue
            run = runs.setdefault(key, {"fails": 0, "min_conf": None})
            run["fails"] += 1
            if r["confidence"] is not None:
                run["min_conf"] = (
                    r["confidence"] if run["min_conf"] is None
                    else min(run["min_conf"], r["confidence"])
                )
            if run["fails"] >= LOCKOUT_RULES[r["kind"]][0]:
                alerts[key] = {
                    "username": r["username"],
                    "student_name": r["student_name"],
                    "kind": r["kind"],
                    "scope": r["scope"],
                    "exam_title": titles.get(r["scope"], ""),
                    "fails": run["fails"],
                    "min_conf": run["min_conf"],
                    "timestamp": r["timestamp"],
                }
        out = list(alerts.values())
        for a in out:
            a["locked_now"] = self.lockout_state(a["username"], a["kind"], a["scope"])["locked"]
        return sorted(out, key=lambda a: a["timestamp"], reverse=True)

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

    # ── Leaving the exam tab (focus events) ─────────────────────────────────
    def record_focus_event(
        self, username: str, exam_id: str, session_id: str, kind: str,
        episode: int, away_ms: int = 0,
    ) -> Tuple[int, bool]:
        """Store one "left the exam" episode. Returns (leaves counted so far, is_new).

        An episode is reported twice by the browser for safety; the (session,
        episode) pair is unique, so the repeat is ignored and counts once.
        """
        with self._conn() as con:
            cur = con.execute(
                "INSERT OR IGNORE INTO focus_events"
                " (username, exam_id, session_id, kind, episode, away_ms, timestamp)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (username, exam_id, session_id, kind, int(episode), int(away_ms), time.time()),
            )
            is_new = cur.rowcount > 0
            n = con.execute(
                "SELECT COUNT(*) FROM focus_events WHERE username = ? AND exam_id = ? AND excused = 0",
                (username, exam_id),
            ).fetchone()[0]
        return n, is_new

    def count_focus_leaves(self, username: str, exam_id: str) -> int:
        """Leaves that count against this student (excused ones are not included)."""
        with self._conn() as con:
            return con.execute(
                "SELECT COUNT(*) FROM focus_events WHERE username = ? AND exam_id = ? AND excused = 0",
                (username, exam_id),
            ).fetchone()[0]

    def update_focus_away(self, username: str, exam_id: str, episode: int, away_ms: int) -> None:
        """Record how long a leave actually lasted (sent when the student comes back)."""
        with self._conn() as con:
            con.execute(
                "UPDATE focus_events SET away_ms = MAX(away_ms, ?)"
                " WHERE username = ? AND exam_id = ? AND episode = ?",
                (int(away_ms), username, exam_id, int(episode)),
            )

    def get_focus_events(self, username: str, exam_id: str) -> List[Dict[str, Any]]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT kind, away_ms, excused, timestamp FROM focus_events"
                " WHERE username = ? AND exam_id = ? ORDER BY id",
                (username, exam_id),
            ).fetchall()
            return [dict(r) for r in rows]

    def beat(self, username: str, exam_id: str) -> None:
        """Heartbeat from the exam page; remembers the longest silence between beats."""
        now = time.time()
        with self._conn() as con:
            row = con.execute(
                "SELECT last_beat, max_gap FROM exam_monitor WHERE username = ? AND exam_id = ?",
                (username, exam_id),
            ).fetchone()
            if row:
                last, gap = row["last_beat"], row["max_gap"]
            else:  # first beat: measure from when the attempt started
                d = con.execute(
                    "SELECT started_at FROM exam_drafts WHERE username = ? AND exam_id = ?",
                    (username, exam_id),
                ).fetchone()
                last, gap = (d["started_at"] if d else now), 0.0
            con.execute(
                "INSERT OR REPLACE INTO exam_monitor (username, exam_id, last_beat, max_gap)"
                " VALUES (?, ?, ?, ?)",
                (username, exam_id, now, max(gap, now - last)),
            )

    def get_monitor_gap(self, username: str, exam_id: str, upto: float) -> float:
        """Longest stretch (seconds) the exam page was silent, up to `upto`."""
        with self._conn() as con:
            row = con.execute(
                "SELECT last_beat, max_gap FROM exam_monitor WHERE username = ? AND exam_id = ?",
                (username, exam_id),
            ).fetchone()
            if row:
                return max(row["max_gap"], upto - row["last_beat"])
            d = con.execute(
                "SELECT started_at FROM exam_drafts WHERE username = ? AND exam_id = ?",
                (username, exam_id),
            ).fetchone()
            return max(0.0, upto - d["started_at"]) if d else 0.0

    def reopen_attempt(self, username: str, exam_id: str, remaining_s: int) -> bool:
        """Undo an automatic submission (false alarm): the student resumes where they stopped.

        Their saved answers become a draft again with `remaining_s` seconds left, the
        submission is removed, and the earlier leaves are marked excused (kept for the
        record, no longer counted).
        """
        exam = self.get_exam(exam_id)
        sub = self.get_exam_submission(username, exam_id)
        if not exam or not sub:
            return False
        now = time.time()
        deadline = now + max(60, int(remaining_s))
        with self._conn() as con:
            con.execute("DELETE FROM exam_submissions WHERE username = ? AND exam_id = ?",
                        (username, exam_id))
            con.execute(
                "INSERT OR REPLACE INTO exam_drafts (username, exam_id, session_id, answers,"
                " started_at, deadline, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (username, exam_id, sub["session_id"], _dump(sub["answers"]),
                 deadline - int(exam["duration_mins"]) * 60, deadline, now),
            )
            con.execute("UPDATE focus_events SET excused = 1 WHERE username = ? AND exam_id = ?",
                        (username, exam_id))
            con.execute("DELETE FROM exam_monitor WHERE username = ? AND exam_id = ?",
                        (username, exam_id))
        return True

    # ── Integrity score ─────────────────────────────────────────────────────
    @staticmethod
    def calculate_integrity_score(
        avg_confidence: Optional[float], paste_count: int, leaves: int = 0
    ) -> Dict[str, Any]:
        """Grade an attempt from its typing confidence and paste attempts.

        `avg_confidence=None` means no typing check ran (e.g. an MCQ-only exam,
        where nothing is typed). That is *missing evidence*, not 0% confidence,
        so the grade then rests on the paste and tab-leave record alone. `leaves` is
        how many times the student left the exam tab or window.
        """
        paste_penalty = {0: 100, 1: 80, 2: 55}.get(paste_count, 20 if paste_count else 100)
        if paste_count >= 3:
            paste_penalty = 20
        leave_penalty = 100 if leaves <= 0 else (70 if leaves == 1 else 30)
        conduct = min(paste_penalty, leave_penalty)  # the worse of the two records
        checked = avg_confidence is not None
        if checked:
            behavioral_score = max(0.0, min(100.0, avg_confidence * 100))
            integrity_score = behavioral_score * 0.6 + conduct * 0.4
        else:
            behavioral_score = None
            integrity_score = float(conduct)
        if integrity_score >= 70:
            grade = "High"
        elif integrity_score >= 40:
            grade = "Suspicious"
        else:
            grade = "Flagged"
        return {
            "behavioral_score": behavioral_score,
            "paste_penalty": paste_penalty,
            "leaves": leaves,
            "leave_penalty": leave_penalty,
            "integrity_score": integrity_score,
            "grade": grade,
            "behavioral_checked": checked,
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
