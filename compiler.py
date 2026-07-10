"""C++ compiler facade — Judge0 → Piston → local g++ fallback.

JUDGE0 SETUP (free):
  1. https://rapidapi.com/judge0-official/api/judge0-ce  → subscribe to Basic
  2. Set env var JUDGE0_API_KEY=your_key  (or place it in a .env file)
  3. Without a key the engine is silently skipped → Piston is used.

PISTON: no setup; endpoint https://emkc.org/api/v2/piston/execute
LOCAL g++: install MinGW (Windows) or `apt install g++` / `brew install gcc`.
"""

from __future__ import annotations

import base64
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    import requests  # type: ignore
except ImportError:
    requests = None  # type: ignore

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except ImportError:
    pass


logger = logging.getLogger(__name__)


# ── Constants ────────────────────────────────────────────────────────────────
JUDGE0_URL = "https://judge0-ce.p.rapidapi.com/submissions"
JUDGE0_HOST = "judge0-ce.p.rapidapi.com"
JUDGE0_CPP17_ID = 54
PISTON_URL = "https://emkc.org/api/v2/piston/execute"
PISTON_CPP_VERSION = "10.2.0"

ENGINE_JUDGE0 = "Judge0"
ENGINE_PISTON = "Piston"
ENGINE_LOCAL = "Local g++"
ENGINE_NONE = "None"

DEFAULT_TIMEOUT = 5


@dataclass(frozen=True)
class CompileResult:
    """Unified result returned by every compile engine."""

    stdout: str
    stderr: str
    compile_error: str
    exit_code: int
    engine_used: str
    time_ms: int
    success: bool

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-safe plain dict."""
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "compile_error": self.compile_error,
            "exit_code": self.exit_code,
            "engine_used": self.engine_used,
            "time_ms": self.time_ms,
            "success": self.success,
        }


def _empty(engine: str, msg: str) -> CompileResult:
    """Quick constructor for an error CompileResult on a given engine."""
    return CompileResult("", msg, "", -1, engine, 0, False)


class CppCompiler:
    """3-engine compile-and-run facade with automatic fallback."""

    def __init__(self, prefer_local: bool = False) -> None:
        """Pick judge0/piston/local order; cache available paths once."""
        self.prefer_local = prefer_local
        self.judge0_key = os.environ.get("JUDGE0_API_KEY", "").strip()
        self._gcc_path = shutil.which("g++") or shutil.which("clang++")

    # ── Public API ──────────────────────────────────────────────────────────
    def compile_and_run(
        self,
        code: str,
        stdin: str = "",
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Dict[str, Any]:
        """Try every available engine in order; return the first usable result."""
        if not code or not code.strip():
            return _empty(ENGINE_NONE, "Empty source code.").to_dict()

        last: Optional[CompileResult] = None
        for engine in self._engine_order():
            try:
                if engine == ENGINE_JUDGE0:
                    res = self._judge0(code, stdin, timeout)
                elif engine == ENGINE_PISTON:
                    res = self._piston(code, stdin, timeout)
                elif engine == ENGINE_LOCAL:
                    res = self._local(code, stdin, timeout)
                else:
                    continue
            except Exception as exc:
                logger.warning("%s engine error: %s", engine, exc)
                last = _empty(engine, f"{engine} failed: {exc}")
                continue
            if res is None:
                continue
            if res.success or res.compile_error or res.stdout or res.stderr:
                return res.to_dict()
            last = res
        if last is not None:
            return last.to_dict()
        return _empty(ENGINE_NONE, "No compilation engine available.").to_dict()

    def available_engines(self) -> Dict[str, bool]:
        """Return which engines are usable in this environment."""
        return {
            ENGINE_JUDGE0: bool(self.judge0_key) and requests is not None,
            ENGINE_PISTON: requests is not None,
            ENGINE_LOCAL: bool(self._gcc_path),
        }

    # ── Engine ordering ─────────────────────────────────────────────────────
    def _engine_order(self) -> List[str]:
        """Pick the engines to try in priority order."""
        base = [ENGINE_LOCAL, ENGINE_PISTON, ENGINE_JUDGE0] if self.prefer_local else [
            ENGINE_JUDGE0,
            ENGINE_PISTON,
            ENGINE_LOCAL,
        ]
        return [
            e
            for e in base
            if (e == ENGINE_LOCAL and self._gcc_path)
            or (e == ENGINE_JUDGE0 and self.judge0_key and requests is not None)
            or (e == ENGINE_PISTON and requests is not None)
        ]

    # ── Judge0 ──────────────────────────────────────────────────────────────
    def _judge0(self, code: str, stdin: str, timeout: int) -> Optional[CompileResult]:
        """Submit + poll Judge0 RapidAPI; return normalised CompileResult."""
        if not (self.judge0_key and requests is not None):
            return None
        headers = {
            "content-type": "application/json",
            "x-rapidapi-host": JUDGE0_HOST,
            "x-rapidapi-key": self.judge0_key,
        }
        body = {
            "language_id": JUDGE0_CPP17_ID,
            "source_code": base64.b64encode(code.encode("utf-8")).decode("ascii"),
            "stdin": base64.b64encode(stdin.encode("utf-8")).decode("ascii"),
            "cpu_time_limit": str(timeout),
        }
        params = {"base64_encoded": "true", "wait": "false"}
        start = time.time()
        r = requests.post(JUDGE0_URL, json=body, headers=headers, params=params, timeout=10)
        if r.status_code >= 400:
            return _empty(ENGINE_JUDGE0, f"HTTP {r.status_code}: {r.text[:160]}")
        token = r.json().get("token")
        if not token:
            return _empty(ENGINE_JUDGE0, "no token from Judge0")
        for _ in range(15):
            time.sleep(1)
            poll = requests.get(
                f"{JUDGE0_URL}/{token}",
                headers=headers,
                params={"base64_encoded": "true"},
                timeout=10,
            )
            if poll.status_code >= 400:
                return _empty(ENGINE_JUDGE0, f"poll HTTP {poll.status_code}")
            data = poll.json()
            sid = (data.get("status") or {}).get("id", 0)
            if sid > 2:
                return _judge0_normalize(data, int((time.time() - start) * 1000))
        return _empty(ENGINE_JUDGE0, "timed out polling")

    # ── Piston ──────────────────────────────────────────────────────────────
    def _piston(self, code: str, stdin: str, timeout: int) -> Optional[CompileResult]:
        """Hit Piston API once and parse its compile + run blocks."""
        if requests is None:
            return None
        body = {
            "language": "cpp",
            "version": PISTON_CPP_VERSION,
            "files": [{"name": "main.cpp", "content": code}],
            "stdin": stdin,
            "run_timeout": int(timeout * 1000),
            "compile_timeout": 10000,
        }
        start = time.time()
        r = requests.post(PISTON_URL, json=body, timeout=20)
        if r.status_code >= 400:
            return _empty(ENGINE_PISTON, f"HTTP {r.status_code}: {r.text[:160]}")
        data = r.json()
        comp = data.get("compile") or {}
        run = data.get("run") or {}
        compile_error = ""
        if int(comp.get("code", 0) or 0) != 0:
            compile_error = comp.get("stderr") or comp.get("output") or ""
        stdout = run.get("stdout") or ""
        stderr = run.get("stderr") or ""
        exit_code = int(run.get("code", 0) or 0)
        return CompileResult(
            stdout=stdout,
            stderr=stderr,
            compile_error=compile_error,
            exit_code=exit_code,
            engine_used=ENGINE_PISTON,
            time_ms=int((time.time() - start) * 1000),
            success=not compile_error and exit_code == 0,
        )

    # ── Local g++ ───────────────────────────────────────────────────────────
    def _local(self, code: str, stdin: str, timeout: int) -> Optional[CompileResult]:
        """Compile with g++/clang++ subprocess and run the binary."""
        if not self._gcc_path:
            return None
        suffix = ".exe" if sys.platform.startswith("win") else ""
        tag = uuid.uuid4().hex[:8]
        tmp = tempfile.gettempdir()
        src = os.path.join(tmp, f"tp_{tag}.cpp")
        out = os.path.join(tmp, f"tp_{tag}{suffix}")
        try:
            with open(src, "w", encoding="utf-8") as fh:
                fh.write(code)
            start = time.time()
            comp = subprocess.run(
                [self._gcc_path, "-std=c++17", "-O2", "-pipe", "-o", out, src],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if comp.returncode != 0:
                return CompileResult(
                    "", "", comp.stderr, comp.returncode, ENGINE_LOCAL,
                    int((time.time() - start) * 1000), False,
                )
            try:
                run = subprocess.run(
                    [out],
                    input=stdin,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return CompileResult(
                    "", f"Time limit exceeded ({timeout}s).", "",
                    124, ENGINE_LOCAL, timeout * 1000, False,
                )
            return CompileResult(
                run.stdout, run.stderr, "",
                run.returncode, ENGINE_LOCAL,
                int((time.time() - start) * 1000),
                run.returncode == 0,
            )
        finally:
            for p in (src, out):
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except OSError:
                    pass


def _judge0_normalize(data: Dict[str, Any], elapsed_ms: int) -> CompileResult:
    """Decode base64 fields + map Judge0 status codes to CompileResult."""
    def _b64(s: Optional[str]) -> str:
        if not s:
            return ""
        try:
            return base64.b64decode(s).decode("utf-8", errors="replace")
        except Exception:
            return s

    stdout = _b64(data.get("stdout"))
    stderr = _b64(data.get("stderr"))
    comp = _b64(data.get("compile_output"))
    msg = _b64(data.get("message"))
    sid = int((data.get("status") or {}).get("id", 0))
    success = sid == 3
    compile_error = comp if sid == 6 else ""
    if not stderr and msg and not success and sid != 6:
        stderr = msg
    return CompileResult(
        stdout, stderr, compile_error,
        0 if success else 1, ENGINE_JUDGE0, elapsed_ms, success,
    )


# ── Test-case grading ────────────────────────────────────────────────────────
def grade_submission(
    compiler: CppCompiler,
    code: str,
    test_cases: List[Dict[str, Any]],
    time_limit: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """Run `code` against each test case; return per-test results + score."""
    results: List[Dict[str, Any]] = []
    score = 0
    max_score = sum(int(tc.get("points", 0)) for tc in test_cases)
    compile_error = ""
    engine_used = ENGINE_NONE
    for tc in test_cases:
        stdin = tc.get("input", "") or ""
        expected = (tc.get("expected_output") or tc.get("expected") or "").strip()
        points = int(tc.get("points", 0))
        run = compiler.compile_and_run(code, stdin=stdin, timeout=time_limit)
        engine_used = run.get("engine_used") or engine_used
        if run.get("compile_error"):
            compile_error = run["compile_error"]
            results.append(
                {
                    "input": stdin,
                    "expected": expected,
                    "got": "",
                    "points": points,
                    "awarded": 0,
                    "status": "compile_error",
                    "stderr": run["compile_error"],
                    "time_ms": run.get("time_ms", 0),
                }
            )
            break
        got_raw = run.get("stdout") or ""
        got = got_raw.rstrip("\n")
        passed = got.strip() == expected
        if passed:
            score += points
        results.append(
            {
                "input": stdin,
                "expected": expected,
                "got": got,
                "points": points,
                "awarded": points if passed else 0,
                "status": "pass" if passed else "fail",
                "stderr": run.get("stderr", ""),
                "time_ms": run.get("time_ms", 0),
            }
        )
    return {
        "results": results,
        "score": score,
        "max_score": max_score,
        "passed": sum(1 for r in results if r["status"] == "pass"),
        "total": len(test_cases),
        "compile_error": compile_error,
        "engine_used": engine_used,
        "all_passed": (
            score == max_score and bool(test_cases) and not compile_error
        ),
    }
