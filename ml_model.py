"""BehavioralAuthModel — LSTM over 13 keystroke-dynamics features.

Uses an LSTM network to model the sequential nature of keystroke timing
patterns for user authentication.  API-compatible with the original
RF+SVM ensemble so the rest of the application keeps working unchanged.
"""

from __future__ import annotations

import json
import os
import statistics
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

# Suppress TF info/warnings before import
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
import tensorflow as tf  # noqa: E402
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
        """Apply stored z-score normalisation."""
        return (X - self._mean) / (self._std + 1e-8)

    def _fit_scaler(self, X: np.ndarray) -> np.ndarray:
        """Compute mean/std from training data and return scaled version."""
        self._mean = X.mean(axis=0)
        self._std = X.std(axis=0)
        return self._scale(X)

    # ----------- training -----------
    def fit(self, X: List[List[float]], y: List[str]) -> Dict[str, float]:
        """Train the LSTM; returns basic train-accuracy metrics."""
        if len(set(y)) < 2:
            raise ValueError("Need at least two distinct users to train the model.")

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

        # Gather metrics
        final_acc = float(history.history["accuracy"][-1])
        val_acc = (
            float(history.history["val_accuracy"][-1])
            if "val_accuracy" in history.history
            else final_acc
        )
        return {
            "lstm_train_acc": final_acc,
            "lstm_val_acc": val_acc,
            "n_users": len(self.classes_),
        }

    # ----------- prediction -----------
    def predict(self, features: List[float], username: str) -> Dict[str, float]:
        """Return {confidence, decision, lstm_prob} for `username`."""
        if not self.is_trained or username not in self.classes_:
            return {
                "confidence": 0.0,
                "decision": False,
                "lstm_prob": 0.0,
            }

        X_arr = np.asarray([features], dtype=np.float32)
        X_scaled = self._scale(X_arr)
        X_seq = X_scaled.reshape(-1, self.N_FEATURES, 1)

        probs = self.model.predict(X_seq, verbose=0)[0]
        idx = self.classes_.index(username)
        lstm_prob = float(probs[idx])

        return {
            "confidence": lstm_prob,
            "decision": bool(lstm_prob >= AUTH_THRESHOLD),
            "lstm_prob": lstm_prob,
        }

    # ----------- persistence -----------
    def save(self, path: str) -> None:
        """Save the LSTM model weights + metadata to `path` directory."""
        # Use the pkl path as a base; create a sibling directory for LSTM
        save_dir = path.replace(".pkl", "_lstm")
        os.makedirs(save_dir, exist_ok=True)

        # Save the Keras model
        self.model.save(os.path.join(save_dir, "lstm_model.keras"))

        # Save metadata (classes, scaler params)
        meta = {
            "classes_": self.classes_,
            "is_trained": self.is_trained,
            "mean": self._mean.tolist() if self._mean is not None else None,
            "std": self._std.tolist() if self._std is not None else None,
        }
        with open(os.path.join(save_dir, "metadata.json"), "w") as f:
            json.dump(meta, f)

    @classmethod
    def load(cls, path: str) -> "BehavioralAuthModel":
        """Load a previously-saved LSTM model; returns a ready model."""
        obj = cls()
        load_dir = path.replace(".pkl", "_lstm")
        meta_path = os.path.join(load_dir, "metadata.json")
        model_path = os.path.join(load_dir, "lstm_model.keras")

        if not os.path.exists(meta_path) or not os.path.exists(model_path):
            return obj  # return empty/untrained shell

        with open(meta_path, "r") as f:
            meta = json.load(f)

        obj.classes_ = meta["classes_"]
        obj.is_trained = meta["is_trained"]
        obj._mean = np.array(meta["mean"], dtype=np.float32) if meta["mean"] is not None else None
        obj._std = np.array(meta["std"], dtype=np.float32) if meta["std"] is not None else None
        obj.model = keras.models.load_model(model_path)
        return obj
