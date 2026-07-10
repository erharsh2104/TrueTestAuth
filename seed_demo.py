"""Seed demo data: 1 faculty + 3 students + 1 exam + 1 lab + enrolments + ML model.

Run once before a presentation:
    python seed_demo.py
"""

from __future__ import annotations

import os
import random
from typing import Dict, List

import numpy as np

from data_manager import DEFAULT_STARTER_CODE, DataManager
from ml_model import BehavioralAuthModel


# ── Per-user typing profiles ─────────────────────────────────────────────────
PROFILES: Dict[str, Dict[str, float]] = {
    "alice_cs": {"dwell_mean": 95, "dwell_std": 12, "flight_mean": 75, "flight_std": 18},
    "bob_cs":   {"dwell_mean": 130, "dwell_std": 22, "flight_mean": 110, "flight_std": 28},
    "charlie":  {"dwell_mean": 70, "dwell_std": 9, "flight_mean": 55, "flight_std": 14},
}

STUDENTS = [
    ("alice_cs", "Alice Reddy",   "EN21CS001"),
    ("bob_cs",   "Bob Kumar",     "EN21CS002"),
    ("charlie",  "Charlie Singh", "EN21CS003"),
]

FACULTY_USERNAME = "prof_sharma"
FACULTY_NAME = "Dr. Priya Sharma"
COURSE_NAME = "CS301 - Data Structures"
DEMO_PASSWORD = "demo123"

PHRASE = "the quick brown fox jumps"
N_KEYS = len(PHRASE)
N_SAMPLES_PER_USER = 15


def _synthesize_sample(profile: Dict[str, float]) -> List[float]:
    """Return one synthetic 13-feature keystroke vector for `profile`."""
    rng = np.random.default_rng()
    dwells = rng.normal(profile["dwell_mean"], profile["dwell_std"], N_KEYS).clip(40, 400)
    flights = rng.normal(profile["flight_mean"], profile["flight_std"], N_KEYS - 1).clip(20, 400)
    mean_dwell = float(np.mean(dwells))
    std_dwell = float(np.std(dwells))
    median_dwell = float(np.median(dwells))
    max_dwell = float(np.max(dwells))
    mean_flight = float(np.mean(flights))
    std_flight = float(np.std(flights))
    median_flight = float(np.median(flights))
    min_flight = float(np.min(flights))
    total_time_ms = float(dwells.sum() + flights.sum())
    typing_speed_wpm = (N_KEYS / 5.0) / (total_time_ms / 60000.0)
    dwell_flight_ratio = mean_dwell / mean_flight if mean_flight > 0 else 0.0
    rhythm_consistency = max(0.0, min(1.0, 1.0 - (std_dwell / mean_dwell)))
    return [
        mean_dwell, std_dwell, median_dwell, max_dwell,
        mean_flight, std_flight, median_flight, min_flight,
        typing_speed_wpm, dwell_flight_ratio,
        rhythm_consistency, total_time_ms, float(N_KEYS),
    ]


def seed_users(dm: DataManager) -> None:
    """Create faculty + students + populate keystroke samples."""
    if not dm.user_exists(FACULTY_USERNAME):
        dm.register_user(
            username=FACULTY_USERNAME,
            password=DEMO_PASSWORD,
            full_name=FACULTY_NAME,
            role="faculty",
            course_name=COURSE_NAME,
        )
        print(f"Created faculty {FACULTY_USERNAME}")
    for username, full_name, enroll_no in STUDENTS:
        if not dm.user_exists(username):
            dm.register_user(
                username=username,
                password=DEMO_PASSWORD,
                full_name=full_name,
                role="student",
                enrollment_no=enroll_no,
            )
            print(f"Created student {username}")
        # Pre-seed keystroke samples
        existing = len(dm.get_samples(username))
        for _ in range(max(0, N_SAMPLES_PER_USER - existing)):
            dm.add_sample(username, _synthesize_sample(PROFILES[username]))
        print(f"  samples for {username}: {len(dm.get_samples(username))}")
        dm.enroll_student(username, FACULTY_USERNAME)


def train_initial_model(dm: DataManager, model_path: str) -> None:
    """Train the RF + SVM ensemble across every enrolled student."""
    X: List[List[float]] = []
    y: List[str] = []
    for username, *_ in STUDENTS:
        for feats in dm.get_samples(username):
            X.append(feats)
            y.append(username)
    model = BehavioralAuthModel()
    metrics = model.fit(X, y)
    model.save(model_path)
    print(f"Trained model: {metrics}")


def seed_demo_exam(dm: DataManager) -> str:
    """Create the demo mid-sem exam, or return the existing one."""
    for e in dm.get_exams(faculty_username=FACULTY_USERNAME):
        if e["title"] == "Mid-Semester Exam — Data Structures":
            print("Demo exam already present")
            return e["exam_id"]
    eid = dm.create_exam(
        faculty_username=FACULTY_USERNAME,
        title="Mid-Semester Exam — Data Structures",
        subject=COURSE_NAME,
        date="2026-05-15",
        start_time="10:00",
        duration_mins=60,
        instructions=(
            "Answer all questions. Continuous behavioural verification is "
            "active. Copy-paste is disabled and any attempts will be logged."
        ),
        questions=[
            {
                "q_id": "q1",
                "type": "Descriptive",
                "text": (
                    "Explain the difference between a stack and a queue, "
                    "and give one real-world use case for each."
                ),
                "marks": 10,
                "options": [],
                "correct": "",
            },
            {
                "q_id": "q2",
                "type": "Descriptive",
                "text": (
                    "Describe how a circular queue avoids the limitation of "
                    "a regular array-based queue. Include pseudocode."
                ),
                "marks": 15,
                "options": [],
                "correct": "",
            },
            {
                "q_id": "q3",
                "type": "Descriptive",
                "text": (
                    "Implement binary search recursively in C++. State the "
                    "preconditions and explain the time complexity."
                ),
                "marks": 15,
                "options": [],
                "correct": "",
            },
        ],
    )
    print(f"Created exam id={eid}")
    return eid


def seed_demo_lab(dm: DataManager) -> str:
    """Create a 3-problem demo lab (Hello / Sum-N / Palindrome)."""
    for lab in dm.get_labs(faculty_username=FACULTY_USERNAME):
        if lab["title"] == "Lab 1 — Basic C++ Programming":
            print("Demo lab already present")
            return lab["lab_id"]
    hello_starter = """#include <iostream>
using namespace std;
int main() {
    // print Hello, World!
    return 0;
}
"""
    sum_starter = """#include <iostream>
using namespace std;
int main() {
    int n;
    cin >> n;
    long long s = 0;
    // read n integers and accumulate
    cout << s << endl;
    return 0;
}
"""
    palin_starter = """#include <iostream>
#include <string>
using namespace std;
int main() {
    string s;
    cin >> s;
    // print YES / NO
    return 0;
}
"""
    problems = [
        {
            "title": "Hello, World!",
            "difficulty": "Easy",
            "statement": (
                "Print exactly:\n\n```\nHello, World!\n```\n\n"
                "Trailing newline allowed. No extra spaces."
            ),
            "time_limit_s": 2,
            "memory_limit_mb": 32,
            "samples": [{"input": "", "expected_output": "Hello, World!"}],
            "test_cases": [
                {"input": "", "expected_output": "Hello, World!", "points": 10},
            ],
            "starter_code": hello_starter,
        },
        {
            "title": "Sum of N Numbers",
            "difficulty": "Medium",
            "statement": (
                "Read **N**, then **N** integers from stdin. Print their sum.\n\n"
                "**Constraints:** 1 ≤ N ≤ 10⁵, |Aᵢ| ≤ 10⁹."
            ),
            "time_limit_s": 2,
            "memory_limit_mb": 64,
            "samples": [{"input": "3\n1 2 3", "expected_output": "6"}],
            "test_cases": [
                {"input": "3\n1 2 3", "expected_output": "6", "points": 7},
                {"input": "1\n42", "expected_output": "42", "points": 6},
                {"input": "5\n10 20 30 40 50", "expected_output": "150", "points": 7},
            ],
            "starter_code": sum_starter,
        },
        {
            "title": "Palindrome Check",
            "difficulty": "Hard",
            "statement": (
                "Read one space-free string from stdin. Print **YES** if it "
                "reads the same forwards and backwards, otherwise **NO**.\n\n"
                "Comparison is case-sensitive."
            ),
            "time_limit_s": 3,
            "memory_limit_mb": 64,
            "samples": [{"input": "racecar", "expected_output": "YES"}],
            "test_cases": [
                {"input": "racecar", "expected_output": "YES", "points": 10},
                {"input": "hello", "expected_output": "NO", "points": 10},
                {"input": "a", "expected_output": "YES", "points": 10},
            ],
            "starter_code": palin_starter,
        },
    ]
    lid = dm.create_lab(
        faculty_username=FACULTY_USERNAME,
        title="Lab 1 — Basic C++ Programming",
        course=COURSE_NAME,
        deadline="2026-05-30 23:59",
        description=(
            "Three short C++ problems to warm up. Each is auto-graded against "
            "hidden test cases. Continuous behavioural auth runs throughout."
        ),
        problems=problems,
    )
    print(f"Created lab id={lid}")
    return lid


def main() -> None:
    """Seed everything in one shot."""
    random.seed(42)
    np.random.seed(42)
    dm = DataManager()
    seed_users(dm)
    model_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "models",
        "behavioral_auth_model.pkl",
    )
    train_initial_model(dm, model_path)
    seed_demo_exam(dm)
    seed_demo_lab(dm)
    print(
        "\nDone. Demo creds:"
        f"\n  Faculty: {FACULTY_USERNAME} / {DEMO_PASSWORD}"
        f"\n  Students: alice_cs | bob_cs | charlie  (password: {DEMO_PASSWORD})"
    )


if __name__ == "__main__":
    main()
