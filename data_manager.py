"""JSON-backed persistence layer for TrueTestAuth.

Files under data/:
  users.json            — user accounts (faculty + students)
  exams.json            — exam definitions
  labs.json             — lab problem definitions
  submissions.json      — student exam submissions + auth logs
  lab_submissions.json  — student lab submissions + test results
  auth_logs.json        — per-session behavioural auth timeline
  cp_logs.json          — copy-paste event logs
  enrollments.json      — which students are in which faculty's course
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional


# ── File paths ───────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
EXAMS_FILE = os.path.join(DATA_DIR, "exams.json")
LABS_FILE = os.path.join(DATA_DIR, "labs.json")
SUBMISSIONS_FILE = os.path.join(DATA_DIR, "submissions.json")
LAB_SUBMISSIONS_FILE = os.path.join(DATA_DIR, "lab_submissions.json")
AUTH_LOG_FILE = os.path.join(DATA_DIR, "auth_logs.json")
CP_LOG_FILE = os.path.join(DATA_DIR, "cp_logs.json")
ENROLL_FILE = os.path.join(DATA_DIR, "enrollments.json")

DEFAULT_STARTER_CODE: str = """#include <iostream>
using namespace std;

int main() {
    // your code here
    return 0;
}
"""


# ── JSON helpers ─────────────────────────────────────────────────────────────
def _ensure_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _read_json(path: str, default: Any) -> Any:
    _ensure_dir()
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path: str, payload: Any) -> None:
    _ensure_dir()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    os.replace(tmp, path)


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


# ── DataManager ──────────────────────────────────────────────────────────────
class DataManager:
    """Single facade for all JSON-file CRUD across the app."""

    # ── Users ───────────────────────────────────────────────────────────────
    def load_users(self) -> Dict[str, Dict]:
        return _read_json(USERS_FILE, {})

    def save_users(self, users: Dict[str, Dict]) -> None:
        _write_json(USERS_FILE, users)

    def user_exists(self, username: str) -> bool:
        return username in self.load_users()

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
        users = self.load_users()
        if username in users:
            return False
        users[username] = {
            "username": username,
            "password_hash": _hash(password),
            "full_name": full_name,
            "role": role,
            "course_name": course_name,
            "enrollment_no": enrollment_no,
            "created_at": time.time(),
            "samples": [],
            "enrolled": False,
        }
        self.save_users(users)
        return True

    def login_user(
        self, username: str, password: str, role: str
    ) -> Optional[Dict[str, Any]]:
        users = self.load_users()
        u = users.get(username)
        if not u:
            return None
        if u.get("password_hash") != _hash(password):
            return None
        if u.get("role") != role:
            return None
        return u

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        return self.load_users().get(username)

    def update_user(self, username: str, updates: Dict[str, Any]) -> bool:
        users = self.load_users()
        if username not in users:
            return False
        users[username].update(updates)
        self.save_users(users)
        return True

    def get_all_students(self) -> List[Dict]:
        return [u for u in self.load_users().values() if u.get("role") == "student"]

    def get_all_faculty(self) -> List[Dict]:
        """Return list of all users with role='faculty'."""
        return [u for u in self.load_users().values() if u.get("role") == "faculty"]

    def all_enrolled_users(self) -> List[str]:
        return [u for u, p in self.load_users().items() if p.get("enrolled")]

    # ── Keystroke samples (for ML enrolment) ────────────────────────────────
    def add_sample(self, username: str, features: Any) -> int:
        """Append one keystroke-feature sample for `username`; returns count.
        Accepts both list and dict formats."""
        users = self.load_users()
        if username not in users:
            return 0
        # Convert dict features to ordered list if needed
        if isinstance(features, dict):
            feature_order = [
                "mean_dwell", "std_dwell", "median_dwell", "max_dwell",
                "mean_flight", "std_flight", "median_flight", "min_flight",
                "typing_speed_wpm", "dwell_flight_ratio",
                "rhythm_consistency", "total_time_ms", "n_keys",
            ]
            features = [float(features.get(k, 0)) for k in feature_order]
        users[username].setdefault("samples", []).append(features)
        count = len(users[username]["samples"])
        if count >= 10:
            users[username]["enrolled"] = True
        self.save_users(users)
        return count

    def save_keystroke_samples(self, username: str, samples: List[Any]) -> int:
        """Bulk-save multiple keystroke samples. Returns final count."""
        for s in samples:
            self.add_sample(username, s)
        return len(self.get_samples(username))

    def get_samples(self, username: str) -> List[List[float]]:
        return self.load_users().get(username, {}).get("samples", [])

    # ── Enrolments ──────────────────────────────────────────────────────────
    def _load_enrollments(self) -> List[Dict]:
        return _read_json(ENROLL_FILE, [])

    def enroll_student(self, student_username: str, faculty_username: str) -> bool:
        rows = self._load_enrollments()
        if any(
            r["student"] == student_username and r["faculty"] == faculty_username
            for r in rows
        ):
            return True
        rows.append(
            {
                "student": student_username,
                "faculty": faculty_username,
                "since": time.time(),
            }
        )
        _write_json(ENROLL_FILE, rows)
        return True

    def get_student_courses(self, student_username: str) -> List[Dict]:
        rows = self._load_enrollments()
        users = self.load_users()
        out = []
        for r in rows:
            if r["student"] == student_username:
                f = users.get(r["faculty"])
                if f:
                    out.append(f)
        return out

    def get_faculty_students(self, faculty_username: str) -> List[Dict]:
        rows = self._load_enrollments()
        users = self.load_users()
        return [
            users[r["student"]]
            for r in rows
            if r["faculty"] == faculty_username and r["student"] in users
        ]

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
    def load_exams(self) -> Dict[str, Dict]:
        return _read_json(EXAMS_FILE, {})

    def save_exams(self, exams: Dict[str, Dict]) -> None:
        _write_json(EXAMS_FILE, exams)

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
        exams = self.load_exams()
        eid = uuid.uuid4().hex[:8]
        exams[eid] = {
            "exam_id": eid,
            "faculty": faculty_username,
            "title": title,
            "subject": subject,
            "date": date,
            "start_time": start_time,
            "duration_mins": int(duration_mins),
            "instructions": instructions,
            "questions": questions,
            "status": "upcoming",
            "created_at": time.time(),
        }
        self.save_exams(exams)
        return eid

    def get_exam(self, exam_id: str) -> Optional[Dict]:
        return self.load_exams().get(exam_id)

    def get_exams(self, faculty_username: Optional[str] = None) -> List[Dict]:
        exams = list(self.load_exams().values())
        if faculty_username:
            exams = [e for e in exams if e.get("faculty") == faculty_username]
        exams.sort(key=lambda e: e.get("created_at", 0), reverse=True)
        return exams

    def update_exam(self, exam_id: str, updates: Dict[str, Any]) -> bool:
        exams = self.load_exams()
        if exam_id not in exams:
            return False
        exams[exam_id].update(updates)
        self.save_exams(exams)
        return True

    def delete_exam(self, exam_id: str) -> bool:
        exams = self.load_exams()
        if exam_id not in exams:
            return False
        exams.pop(exam_id)
        self.save_exams(exams)
        return True

    # ── Exam submissions ────────────────────────────────────────────────────
    def _load_subs(self) -> Dict[str, Dict]:
        return _read_json(SUBMISSIONS_FILE, {})

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
        subs = self._load_subs()
        key = f"{username}::{exam_id}"
        avg_conf = (
            sum(a["confidence"] for a in auth_log) / len(auth_log)
            if auth_log
            else 0.0
        )
        subs[key] = {
            "username": username,
            "exam_id": exam_id,
            "session_id": session_id,
            "answers": answers,
            "score": score,
            "integrity": integrity,
            "avg_conf": avg_conf,
            "cp_count": len(cp_log),
            "timestamp": time.time(),
        }
        _write_json(SUBMISSIONS_FILE, subs)
        return key

    def get_exam_submission(
        self, username: str, exam_id: str
    ) -> Optional[Dict]:
        return self._load_subs().get(f"{username}::{exam_id}")

    def get_exam_submissions(
        self,
        exam_id: Optional[str] = None,
        username: Optional[str] = None,
    ) -> List[Dict]:
        rows = list(self._load_subs().values())
        if exam_id:
            rows = [r for r in rows if r["exam_id"] == exam_id]
        if username:
            rows = [r for r in rows if r["username"] == username]
        rows.sort(key=lambda r: r.get("timestamp", 0), reverse=True)
        return rows

    # ── Labs ────────────────────────────────────────────────────────────────
    def load_labs(self) -> Dict[str, Dict]:
        return _read_json(LABS_FILE, {})

    def save_labs(self, labs: Dict[str, Dict]) -> None:
        _write_json(LABS_FILE, labs)

    def create_lab(
        self,
        faculty_username: str,
        title: str,
        course: str,
        deadline: str,
        description: str,
        problems: List[Dict],
    ) -> str:
        labs = self.load_labs()
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
        labs[lid] = {
            "lab_id": lid,
            "faculty": faculty_username,
            "title": title,
            "course": course,
            "deadline": deadline,
            "description": description,
            "problems": prepared,
            "created_at": time.time(),
        }
        self.save_labs(labs)
        return lid

    def get_lab(self, lab_id: str) -> Optional[Dict]:
        return self.load_labs().get(lab_id)

    def get_labs(self, faculty_username: Optional[str] = None) -> List[Dict]:
        labs = list(self.load_labs().values())
        if faculty_username:
            labs = [lab for lab in labs if lab.get("faculty") == faculty_username]
        labs.sort(key=lambda lab: lab.get("created_at", 0), reverse=True)
        return labs

    # ── Lab submissions ─────────────────────────────────────────────────────
    def _load_lab_subs(self) -> List[Dict]:
        return _read_json(LAB_SUBMISSIONS_FILE, [])

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
        subs = self._load_lab_subs()
        attempts = sum(
            1
            for s in subs
            if s["username"] == username and s["problem_id"] == problem_id
        ) + 1
        rec = {
            "submission_id": uuid.uuid4().hex[:10],
            "username": username,
            "lab_id": lab_id,
            "problem_id": problem_id,
            "code": code,
            "results": test_results,
            "score": int(score),
            "max_score": int(max_score),
            "passed": sum(1 for r in test_results if r.get("status") == "pass"),
            "total": len(test_results),
            "compile_error": compile_error,
            "engine_used": engine_used,
            "attempts": attempts,
            "timestamp": time.time(),
        }
        subs.append(rec)
        _write_json(LAB_SUBMISSIONS_FILE, subs)
        return rec["submission_id"]

    def get_lab_submissions(
        self,
        lab_id: Optional[str] = None,
        username: Optional[str] = None,
        problem_id: Optional[str] = None,
    ) -> List[Dict]:
        rows = self._load_lab_subs()
        if lab_id:
            rows = [r for r in rows if r["lab_id"] == lab_id]
        if username:
            rows = [r for r in rows if r["username"] == username]
        if problem_id:
            rows = [r for r in rows if r["problem_id"] == problem_id]
        rows.sort(key=lambda r: r.get("timestamp", 0), reverse=True)
        return rows

    def get_best_lab_submission(
        self, username: str, problem_id: str
    ) -> Optional[Dict]:
        rows = self.get_lab_submissions(username=username, problem_id=problem_id)
        if not rows:
            return None
        return max(rows, key=lambda r: r.get("score", 0))

    # ── Auth logs ───────────────────────────────────────────────────────────
    def _load_auth(self) -> List[Dict]:
        return _read_json(AUTH_LOG_FILE, [])

    def log_auth_check(
        self,
        username: str,
        session_id: str,
        confidence: float,
        status: str,
        engine: str = "continuous",
    ) -> None:
        rows = self._load_auth()
        rows.append(
            {
                "username": username,
                "session_id": session_id,
                "confidence": float(confidence),
                "status": status,
                "engine": engine,
                "timestamp": time.time(),
            }
        )
        _write_json(AUTH_LOG_FILE, rows)

    def get_auth_log(self, username: str, session_id: str) -> List[Dict]:
        return [
            r
            for r in self._load_auth()
            if r["username"] == username and r["session_id"] == session_id
        ]

    def get_student_auth_summary(self, username: str) -> Dict[str, Any]:
        rows = [r for r in self._load_auth() if r["username"] == username]
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
        users = self.load_users()
        out: List[Dict] = []
        for s in self.get_exam_submissions():
            exam = self.get_exam(s["exam_id"])
            if not exam or exam.get("faculty") != faculty_username:
                continue
            student = users.get(s["username"], {})
            out.append(
                {
                    "kind": f"exam: {exam['title']}",
                    "username": s["username"],
                    "student_name": student.get("full_name", s["username"]),
                    "timestamp": s["timestamp"],
                }
            )
        for s in self.get_lab_submissions():
            lab = self.get_lab(s["lab_id"])
            if not lab or lab.get("faculty") != faculty_username:
                continue
            student = users.get(s["username"], {})
            out.append(
                {
                    "kind": f"lab: {lab['title']}",
                    "username": s["username"],
                    "student_name": student.get("full_name", s["username"]),
                    "timestamp": s["timestamp"],
                }
            )
        out.sort(key=lambda r: r["timestamp"], reverse=True)
        return out[:limit]

    def get_flagged_recent(
        self, faculty_username: str, hours: int = 24
    ) -> List[Dict]:
        users = self.load_users()
        student_set = {
            r["student"]
            for r in self._load_enrollments()
            if r["faculty"] == faculty_username
        }
        cutoff = time.time() - hours * 3600
        rows = []
        for r in self._load_auth():
            if (
                r["username"] in student_set
                and r["status"] == "Flagged"
                and r["timestamp"] >= cutoff
            ):
                u = users.get(r["username"], {})
                rows.append(
                    {
                        **r,
                        "student_name": u.get("full_name", r["username"]),
                    }
                )
        rows.sort(key=lambda r: r["timestamp"], reverse=True)
        return rows

    # ── Copy-paste logs ─────────────────────────────────────────────────────
    def _load_cp(self) -> List[Dict]:
        return _read_json(CP_LOG_FILE, [])

    def log_cp_event(
        self,
        username: str,
        session_id: str,
        event_type: str,
        question_id: str,
        chars: int,
    ) -> None:
        rows = self._load_cp()
        rows.append(
            {
                "username": username,
                "session_id": session_id,
                "event_type": event_type,
                "question_id": question_id,
                "chars": int(chars),
                "timestamp": time.time(),
            }
        )
        _write_json(CP_LOG_FILE, rows)

    def get_cp_log(self, username: str, session_id: str) -> List[Dict]:
        return [
            r
            for r in self._load_cp()
            if r["username"] == username and r["session_id"] == session_id
        ]

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
