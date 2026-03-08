"""
EEG classifier training pipeline.

Input:  labeled dataset from EEGCollector.get_dataset()
Output: config/backend/classifier.joblib + config/backend/scaler.joblib

Features per window (9 total):
  Band powers: delta, theta, alpha, beta, gamma        (5, already normalized)
  Ratios:      beta/theta, beta/alpha,
               (beta+gamma)/(alpha+theta), theta/alpha  (4)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "backend"))

from eeg.ingestion import EEGSample          # noqa: E402
from eeg.processor import EEGProcessor       # noqa: E402

# Window: 2 seconds at 256 Hz = 512 samples; 50% overlap = 256 step
WINDOW_SAMPLES = 512
STEP_SAMPLES = 256
EPS = 1e-10

MODEL_PATH = Path(__file__).parent.parent.parent / "config" / "backend" / "classifier.joblib"


def extract_features(samples: list[EEGSample]) -> np.ndarray | None:
    """
    Extract a single 9-feature vector from a window of EEG samples.
    Returns None if the processor rejects the window (artifact / too few clean samples).
    """
    processor = EEGProcessor()
    powers = processor.compute(samples)
    if powers is None:
        return None

    d, t, a, b, g = powers.delta, powers.theta, powers.alpha, powers.beta, powers.gamma

    features = np.array([
        d, t, a, b, g,                          # 5 relative band powers
        b / max(t, EPS),                        # focus score (beta/theta)
        b / max(a, EPS),                        # engagement (beta/alpha)
        (b + g) / max(a + t, EPS),              # cognitive engagement
        t / max(a, EPS),                        # mental fatigue proxy
    ], dtype=np.float32)

    return features


def build_dataset(
    phase_data: list[tuple[str, list[EEGSample]]],
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """
    Slide windows over each labeled phase, extract features.

    Returns:
        X: shape (n_windows, 9)
        y: shape (n_windows,)  — integer label indices
        classes: list of class names (index -> name)
    """
    label_map: dict[str, int] = {}
    X_rows: list[np.ndarray] = []
    y_rows: list[int] = []

    for label, samples in phase_data:
        if label not in label_map:
            label_map[label] = len(label_map)
        label_idx = label_map[label]

        # Slide window
        for start in range(0, len(samples) - WINDOW_SAMPLES + 1, STEP_SAMPLES):
            window = samples[start : start + WINDOW_SAMPLES]
            feat = extract_features(window)
            if feat is not None:
                X_rows.append(feat)
                y_rows.append(label_idx)

    if not X_rows:
        raise ValueError("No valid windows extracted — check EEG data quality")

    X = np.stack(X_rows)
    y = np.array(y_rows, dtype=np.int32)
    classes = [name for name, _ in sorted(label_map.items(), key=lambda x: x[1])]

    return X, y, classes


def train_and_save(
    phase_data: list[tuple[str, list[EEGSample]]],
    *,
    verbose: bool = True,
) -> float:
    """
    Train SVM on phase_data, save model + scaler, return cross-val accuracy.
    """
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    import joblib

    X, y, classes = build_dataset(phase_data)

    if verbose:
        print(f"\nDataset: {len(X)} windows, {len(classes)} classes: {classes}")
        for i, cls in enumerate(classes):
            print(f"  {cls}: {(y == i).sum()} windows")

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("svc", SVC(kernel="rbf", C=1.0, gamma="scale", probability=True)),
    ])

    # Cross-validation
    cv = StratifiedKFold(n_splits=min(5, min((y == i).sum() for i in range(len(classes)))))
    scores = cross_val_score(pipeline, X, y, cv=cv, scoring="accuracy")

    if verbose:
        print(f"\nCross-val accuracy: {scores.mean():.1%} ± {scores.std():.1%}")

    # Final fit on all data
    pipeline.fit(X, y)

    # Save
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipeline, "classes": classes}, MODEL_PATH)
    if verbose:
        print(f"Model saved → {MODEL_PATH}")

    return float(scores.mean())


def load_model(model_path: Path = MODEL_PATH):
    """Load saved model. Returns (pipeline, classes) or (None, None) if not found."""
    try:
        import joblib
        data = joblib.load(model_path)
        return data["pipeline"], data["classes"]
    except FileNotFoundError:
        return None, None


def predict(pipeline, classes: list[str], features: np.ndarray) -> tuple[str, float]:
    """Predict state from a 9-feature vector. Returns (state_name, confidence)."""
    proba = pipeline.predict_proba(features.reshape(1, -1))[0]
    idx = int(np.argmax(proba))
    return classes[idx], float(proba[idx])
