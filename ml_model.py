"""BehavioralAuthModel — RF + SVM ensemble over 13 keystroke-dynamics features.

Kept API-compatible with the original behavioral_auth mini-project so that
existing pickles under models/behavioral_auth_model.pkl keep loading.
"""

from __future__ import annotations

import os
import statistics
from typing import Dict, List, Sequence, Tuple

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


# ── Constants ────────────────────────────────────────────────────────────────
FEATURE_NAMES: Tuple[str, ...] = (
    "mean_dwell",
    "std_dwell",
    "median_dwell",
    "max_dwell",
    "mean_flight",
    "std_flight",
    "median_flight",
    "min_flight",
    "typing_speed_wpm",
    "dwell_flight_ratio",
    "rhythm_consistency",
    "total_time_ms",
    "n_keys",
)

RF_WEIGHT = 0.60
SVM_WEIGHT = 0.40
AUTH_THRESHOLD = 0.45


# ── Feature extraction ───────────────────────────────────────────────────────
def extract_features(keystrokes: Sequence[Dict]) -> List[float]:
    """Compute the 13-dim feature vector from a list of {key, downTime, upTime}."""
    if not keystrokes or len(keystrokes) < 2:
        return [0.0] * 13

    dwell = [max(0.0, k["upTime"] - k["downTime"]) for k in keystrokes]
    flight: List[float] = []
    for i in range(len(keystrokes) - 1):
        f = keystrokes[i + 1]["downTime"] - keystrokes[i]["upTime"]
        flight.append(f)

    def _std(xs: List[float]) -> float:
        return float(statistics.pstdev(xs)) if len(xs) > 1 else 0.0

    def _median(xs: List[float]) -> float:
        return float(statistics.median(xs)) if xs else 0.0

    mean_dwell = float(np.mean(dwell)) if dwell else 0.0
    std_dwell = _std(dwell)
    median_dwell = _median(dwell)
    max_dwell = float(max(dwell)) if dwell else 0.0

    pos_flight = [f for f in flight if f >= 0]
    mean_flight = float(np.mean(pos_flight)) if pos_flight else 0.0
    std_flight = _std(pos_flight)
    median_flight = _median(pos_flight)
    min_flight = float(min(pos_flight)) if pos_flight else 0.0

    n_keys = len(keystrokes)
    total_time_ms = float(keystrokes[-1]["upTime"] - keystrokes[0]["downTime"])
    total_time_ms = max(total_time_ms, 1.0)

    typing_speed_wpm = (n_keys / 5.0) / (total_time_ms / 60000.0)
    dwell_flight_ratio = mean_dwell / mean_flight if mean_flight > 0 else 0.0
    rhythm_consistency = 1.0 - (std_dwell / mean_dwell) if mean_dwell > 0 else 0.0
    rhythm_consistency = max(0.0, min(1.0, rhythm_consistency))

    return [
        mean_dwell,
        std_dwell,
        median_dwell,
        max_dwell,
        mean_flight,
        std_flight,
        median_flight,
        min_flight,
        typing_speed_wpm,
        dwell_flight_ratio,
        rhythm_consistency,
        total_time_ms,
        float(n_keys),
    ]


# ── Model wrapper ────────────────────────────────────────────────────────────
class BehavioralAuthModel:
    """Random-Forest + SVM soft-voting ensemble over 13 keystroke features."""

    def __init__(self) -> None:
        """Create empty RF/SVM pair — call fit() before predicting."""
        self.scaler = StandardScaler()
        self.rf = RandomForestClassifier(
            n_estimators=100, max_depth=10, random_state=42, n_jobs=-1
        )
        self.svm = SVC(kernel="rbf", probability=True, C=1.0, gamma="scale", random_state=42)
        self.classes_: List[str] = []
        self.is_trained: bool = False

    # ----------- training -----------
    def fit(self, X: List[List[float]], y: List[str]) -> Dict[str, float]:
        """Train both learners; returns basic train-accuracy metrics."""
        if len(set(y)) < 2:
            raise ValueError("Need at least two distinct users to train the ensemble.")

        X_arr = np.asarray(X, dtype=float)
        y_arr = np.asarray(y)
        self.classes_ = sorted(set(y_arr.tolist()))

        X_scaled = self.scaler.fit_transform(X_arr)
        self.rf.fit(X_scaled, y_arr)
        self.svm.fit(X_scaled, y_arr)
        self.is_trained = True

        rf_acc = float(self.rf.score(X_scaled, y_arr))
        svm_acc = float(self.svm.score(X_scaled, y_arr))
        return {"rf_acc": rf_acc, "svm_acc": svm_acc, "n_users": len(self.classes_)}

    # ----------- prediction -----------
    def predict(self, features: List[float], username: str) -> Dict[str, float]:
        """Return {confidence, decision, rf_prob, svm_prob} for `username`."""
        if not self.is_trained or username not in self.classes_:
            return {
                "confidence": 0.0,
                "decision": False,
                "rf_prob": 0.0,
                "svm_prob": 0.0,
            }

        X_scaled = self.scaler.transform(np.asarray([features], dtype=float))
        idx = self.rf.classes_.tolist().index(username)

        rf_prob = float(self.rf.predict_proba(X_scaled)[0][idx])
        svm_idx = self.svm.classes_.tolist().index(username)
        svm_prob = float(self.svm.predict_proba(X_scaled)[0][svm_idx])

        confidence = RF_WEIGHT * rf_prob + SVM_WEIGHT * svm_prob
        return {
            "confidence": float(confidence),
            "decision": bool(confidence >= AUTH_THRESHOLD),
            "rf_prob": rf_prob,
            "svm_prob": svm_prob,
        }

    # ----------- persistence -----------
    def save(self, path: str) -> None:
        """Serialise the whole model object (scaler + rf + svm) to `path`."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(
            {
                "scaler": self.scaler,
                "rf": self.rf,
                "svm": self.svm,
                "classes_": self.classes_,
                "is_trained": self.is_trained,
            },
            path,
        )

    @classmethod
    def load(cls, path: str) -> "BehavioralAuthModel":
        """Load a previously-saved ensemble from `path`; returns a ready model."""
        obj = cls()
        if not os.path.exists(path):
            return obj
        data = joblib.load(path)
        obj.scaler = data["scaler"]
        obj.rf = data["rf"]
        obj.svm = data["svm"]
        obj.classes_ = data["classes_"]
        obj.is_trained = data["is_trained"]
        return obj
