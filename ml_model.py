"""BehavioralAuthModel — per-user keystroke profile + LSTM over 13 features.

Verification answers "is this sample *this user's*?" rather than "who is this?":

* Each enrolled user gets a personal profile (mean / spread of their enrolment
  samples). A new sample is scored by its normalised distance from that profile,
  so adding or retraining other users never changes your score and a single
  enrolled user is enough.
* The LSTM (multi-class, trained on all enrolled users) is kept as a secondary
  signal on fixed-phrase samples: final = 0.75 * profile score + 0.25 * LSTM.
  Because its weight is small it can neither lock out a genuine user on its own
  nor let an impostor in on its own.
"""

from __future__ import annotations

import json
import os
import statistics
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

# Suppress TF info/warnings before import
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
from tensorflow import keras  # noqa: E402
from tensorflow.keras import layers  # noqa: E402


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

AUTH_THRESHOLD = 0.45

# Keystroke gaps longer than this are treated as pauses (thinking / reading),
# not typing rhythm, so windowed free-text samples stay comparable to the
# fixed-phrase enrolment samples.
PAUSE_MS = 1500.0

_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MODEL_DIR: str = os.environ.get(
    "MODEL_PATH", os.path.join(_ROOT, "models", "behavioral_auth_model_lstm")
)


def _model_dir(path: str) -> str:
    """Resolve a model location to its directory (legacy `.pkl` paths still work)."""
    if path.endswith(".pkl"):
        return path[: -len(".pkl")] + "_lstm"
    return path


# ── Feature extraction ───────────────────────────────────────────────────────
# ── Per-user profile scoring ─────────────────────────────────────────────────
_IDX = {n: i for i, n in enumerate(FEATURE_NAMES)}

# Features compared for fixed-phrase samples (login / exam gate), with the
# minimum tolerated spread as a fraction of the user's mean. The floor stops a
# very consistent typist (tiny enrolment variance) from being over-strict.
PHRASE_FEATURES: Dict[str, float] = {
    "mean_dwell": 0.07,
    "median_dwell": 0.07,
    "std_dwell": 0.30,
    "mean_flight": 0.08,
    "median_flight": 0.08,
    "std_flight": 0.30,
    "typing_speed_wpm": 0.08,
    "dwell_flight_ratio": 0.10,
}
# Free text (exam answers / code) has a different flight rhythm than the
# enrolment phrase, so only key-hold time is compared, with wider tolerance.
FREE_FEATURES: Tuple[str, ...] = ("mean_dwell", "median_dwell")
FREE_TOLERANCE_MULT = 1.6

MIN_PROFILE_SAMPLES = 5
PROFILE_WEIGHT = 0.75
LSTM_WEIGHT = 0.25
_SCORE_SCALE = 2.0  # RMS z-distance at which the score has fallen to ~0.61


def build_profile(samples: Sequence[Sequence[float]]) -> Optional[Dict[str, object]]:
    """Mean / std per feature from a user's enrolment samples (None if too few)."""
    X = np.asarray(samples, dtype=np.float64)
    if X.ndim != 2 or X.shape[0] < MIN_PROFILE_SAMPLES or X.shape[1] != len(FEATURE_NAMES):
        return None
    return {
        "mean": X.mean(axis=0).tolist(),
        "std": X.std(axis=0, ddof=1).tolist(),
        "n": int(X.shape[0]),
    }


def distance_score(
    features: Sequence[float], profile: Dict[str, object], context: str = "phrase"
) -> Tuple[float, float]:
    """Return (score in 0..1, RMS z-distance) of `features` from `profile`."""
    mean = np.asarray(profile["mean"], dtype=np.float64)
    std = np.asarray(profile["std"], dtype=np.float64)
    x = np.asarray(features, dtype=np.float64)
    if context == "phrase":
        spec = PHRASE_FEATURES
    else:
        spec = {n: PHRASE_FEATURES[n] * FREE_TOLERANCE_MULT for n in FREE_FEATURES}
    z = []
    for name, rel_floor in spec.items():
        i = _IDX[name]
        spread = max(std[i], rel_floor * abs(mean[i]), 1e-6)
        z.append((x[i] - mean[i]) / spread)
    d = float(np.sqrt(np.mean(np.square(z))))
    return float(np.exp(-0.5 * (d / _SCORE_SCALE) ** 2)), d


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

    pos_flight = [f for f in flight if 0 <= f <= PAUSE_MS]
    mean_flight = float(np.mean(pos_flight)) if pos_flight else 0.0
    std_flight = _std(pos_flight)
    median_flight = _median(pos_flight)
    min_flight = float(min(pos_flight)) if pos_flight else 0.0

    n_keys = len(keystrokes)
    # Active typing time: key-hold time plus non-pause gaps.
    total_time_ms = float(sum(dwell) + sum(pos_flight))
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
    """LSTM-based classifier over 13 keystroke-dynamics features.

    Each 13-dim feature vector is reshaped into a sequence of 13 timesteps
    with 1 feature each, letting the LSTM capture the ordering/dependency
    across the feature dimensions (dwell → flight → speed → rhythm …).
    """

    N_FEATURES = 13
    # LSTM architecture hyper-parameters
    LSTM_UNITS = 64
    DENSE_UNITS = 32
    DROPOUT = 0.3
    EPOCHS = 80
    BATCH_SIZE = 16

    def __init__(self) -> None:
        """Create an empty model shell — call fit() before predicting."""
        self.model: Optional[keras.Model] = None
        self.classes_: List[str] = []
        self.is_trained: bool = False
        # username -> {"mean": [...], "std": [...], "n": int}
        self.profiles: Dict[str, Dict[str, object]] = {}
        # Per-feature mean/std for manual scaling (avoid sklearn dependency)
        self._mean: Optional[np.ndarray] = None
        self._std: Optional[np.ndarray] = None

    # -------- internal helpers --------
    def _build_model(self, n_classes: int) -> keras.Model:
        """Construct and compile the Keras LSTM model."""
        model = keras.Sequential([
            layers.Input(shape=(self.N_FEATURES, 1)),
            layers.LSTM(self.LSTM_UNITS, return_sequences=True),
            layers.Dropout(self.DROPOUT),
            layers.LSTM(self.LSTM_UNITS // 2),
            layers.Dropout(self.DROPOUT),
            layers.Dense(self.DENSE_UNITS, activation="relu"),
            layers.Dropout(self.DROPOUT / 2),
            layers.Dense(n_classes, activation="softmax"),
        ])
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=1e-3),
            loss="sparse_categorical_crossentropy",
            metrics=["accuracy"],
        )
        return model

    def _scale(self, X: np.ndarray) -> np.ndarray:
        """Apply stored z-score normalisation.

        Features that were constant in training (std ~ 0, e.g. n_keys when every
        enrolment sample has the same length) carry no information; dividing by
        ~1e-8 would blow any different value up to ~1e9, so they are zeroed.
        """
        std = np.asarray(self._std, dtype=np.float32)
        const = std < 1e-6
        scaled = (X - self._mean) / np.where(const, 1.0, std + 1e-8)
        scaled[..., const] = 0.0
        return np.clip(scaled, -8.0, 8.0)

    def _fit_scaler(self, X: np.ndarray) -> np.ndarray:
        """Compute mean/std from training data and return scaled version."""
        self._mean = X.mean(axis=0)
        self._std = X.std(axis=0)
        return self._scale(X)

    # ----------- profiles -----------
    def set_profile(self, username: str, samples: Sequence[Sequence[float]]) -> bool:
        """(Re)build one user's profile; returns False if there are too few samples."""
        prof = build_profile(samples)
        if prof is None:
            return False
        self.profiles[username] = prof
        self.is_trained = True
        return True

    def has_profile(self, username: str) -> bool:
        return username in self.profiles

    # ----------- training -----------
    def fit(self, X: List[List[float]], y: List[str]) -> Dict[str, float]:
        """Build every user's profile, then train the LSTM when >= 2 users exist."""
        by_user: Dict[str, List[List[float]]] = {}
        for feats, label in zip(X, y):
            by_user.setdefault(label, []).append(feats)
        for user, rows in by_user.items():
            self.set_profile(user, rows)
        metrics: Dict[str, float] = {"n_profiles": float(len(self.profiles))}
        if len(by_user) < 2:
            # A single user can still be verified by their profile alone.
            self.model, self.classes_ = None, []
            return metrics

        X_arr = np.asarray(X, dtype=np.float32)
        self.classes_ = sorted(set(y))
        label_map = {c: i for i, c in enumerate(self.classes_)}
        y_int = np.array([label_map[label] for label in y], dtype=np.int32)

        # Scale features and reshape → (samples, timesteps=13, features=1)
        X_scaled = self._fit_scaler(X_arr)
        X_seq = X_scaled.reshape(-1, self.N_FEATURES, 1)

        self.model = self._build_model(len(self.classes_))
        history = self.model.fit(
            X_seq, y_int,
            epochs=self.EPOCHS,
            batch_size=self.BATCH_SIZE,
            validation_split=0.15 if len(y_int) >= 10 else 0.0,
            verbose=0,
        )
        self.is_trained = True
        final_acc = float(history.history["accuracy"][-1])
        val_acc = (
            float(history.history["val_accuracy"][-1])
            if "val_accuracy" in history.history
            else final_acc
        )
        metrics.update(
            {"lstm_train_acc": final_acc, "lstm_val_acc": val_acc,
             "n_users": float(len(self.classes_))}
        )
        return metrics

    # ----------- prediction -----------
    def _lstm_prob(self, features: List[float], username: str) -> Optional[float]:
        """LSTM probability for `username`, or None if the LSTM can't score them."""
        if self.model is None or self._mean is None or username not in self.classes_:
            return None
        X_seq = self._scale(np.asarray([features], dtype=np.float32)).reshape(
            -1, self.N_FEATURES, 1
        )
        probs = self.model.predict(X_seq, verbose=0)[0]
        return float(probs[self.classes_.index(username)])

    def predict(
        self, features: List[float], username: str, context: str = "phrase"
    ) -> Dict[str, float]:
        """Score `features` as `username`.

        context="phrase": fixed enrolment phrase (profile + LSTM).
        context="free":   free text / code (profile on key-hold time only).
        """
        prof = self.profiles.get(username)
        lstm_prob = self._lstm_prob(features, username) if context == "phrase" else None
        if prof is not None:
            score, dist = distance_score(features, prof, context)
            conf = score if lstm_prob is None else (
                PROFILE_WEIGHT * score + LSTM_WEIGHT * lstm_prob
            )
        elif lstm_prob is not None:
            score, dist, conf = 0.0, float("nan"), lstm_prob  # legacy: LSTM-only user
        else:
            return {"confidence": 0.0, "decision": False, "lstm_prob": 0.0,
                    "profile_score": 0.0, "distance": float("nan")}
        return {
            "confidence": float(conf),
            "decision": bool(conf >= AUTH_THRESHOLD),
            "lstm_prob": float(lstm_prob or 0.0),
            "profile_score": float(score),
            "distance": float(dist),
        }

    # ----------- persistence -----------
    def save(self, path: str) -> None:
        """Save profiles (+ LSTM weights and scaler when trained) to the `path` directory."""
        save_dir = _model_dir(path)
        os.makedirs(save_dir, exist_ok=True)
        self.save_profiles(path)
        if self.model is not None:
            self.model.save(os.path.join(save_dir, "lstm_model.keras"))
            meta = {
                "classes_": self.classes_,
                "is_trained": True,
                "mean": self._mean.tolist() if self._mean is not None else None,
                "std": self._std.tolist() if self._std is not None else None,
            }
            with open(os.path.join(save_dir, "metadata.json"), "w") as f:
                json.dump(meta, f)

    def save_profiles(self, path: str) -> None:
        """Write only the per-user profiles (cheap; no LSTM involved)."""
        save_dir = _model_dir(path)
        os.makedirs(save_dir, exist_ok=True)
        with open(os.path.join(save_dir, "profiles.json"), "w") as f:
            json.dump(self.profiles, f)

    @classmethod
    def load(cls, path: str) -> "BehavioralAuthModel":
        """Load profiles and (if present) the LSTM; returns a ready model."""
        obj = cls()
        load_dir = _model_dir(path)
        prof_path = os.path.join(load_dir, "profiles.json")
        meta_path = os.path.join(load_dir, "metadata.json")
        model_path = os.path.join(load_dir, "lstm_model.keras")

        if os.path.exists(prof_path):
            with open(prof_path, "r") as f:
                obj.profiles = json.load(f)
        if os.path.exists(meta_path) and os.path.exists(model_path):
            with open(meta_path, "r") as f:
                meta = json.load(f)
            obj.classes_ = meta["classes_"]
            obj._mean = np.array(meta["mean"], dtype=np.float32) if meta["mean"] is not None else None
            obj._std = np.array(meta["std"], dtype=np.float32) if meta["std"] is not None else None
            obj.model = keras.models.load_model(model_path)
        obj.is_trained = bool(obj.profiles) or obj.model is not None
        return obj
