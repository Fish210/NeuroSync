# EEG Training GUI + Pretrained Classifier Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a standalone Tkinter GUI that guides one person through a 12-minute EEG recording protocol, labels data by task, trains an SVM classifier, and saves it so the main app uses it instead of heuristics.

**Architecture:** Three scripts in `scripts/training/` (`collect.py`, `train.py`, `train_gui.py`) are fully standalone — no FastAPI, no asyncio. They import from `src/backend/eeg/` via `sys.path` injection. The trained model is saved to `config/backend/` and loaded by the updated `src/backend/eeg/classifier.py` at import time, falling back to heuristics if missing.

**Tech Stack:** Python 3.11+, pylsl, scikit-learn 1.4+, joblib, tkinter (stdlib), numpy, scipy (already in pyproject.toml)

---

## Task 1: Add scikit-learn dependency + create directory

**Files:**
- Modify: `src/backend/pyproject.toml`
- Create: `scripts/training/.gitkeep` (makes directory visible in git)

**Step 1: Read pyproject.toml**

```bash
cat src/backend/pyproject.toml
```

**Step 2: Add scikit-learn**

In `src/backend/pyproject.toml`, add `"scikit-learn>=1.4"` to the dependencies list (same section as numpy, scipy).

**Step 3: Create scripts/training directory**

```bash
mkdir -p scripts/training
touch scripts/training/__init__.py
```

**Step 4: Verify install (on Mac)**

```bash
cd src/backend && pip install scikit-learn
python -c "import sklearn; print(sklearn.__version__)"
```
Expected: version >= 1.4

**Step 5: Commit**

```bash
git add src/backend/pyproject.toml scripts/training/__init__.py
git commit -m "feat: add scikit-learn dep and training script directory"
```

---

## Task 2: EEG collector (`scripts/training/collect.py`)

**Purpose:** Threaded LSL reader that buffers raw `EEGSample` objects per labeled phase. No asyncio — runs completely standalone.

**Files:**
- Create: `scripts/training/collect.py`

**Step 1: Write the file**

```python
"""
EEG data collector for training sessions.

Runs a background thread reading from a muselsl LSL stream.
Call start_phase(label) / end_phase() to capture labeled windows.
No asyncio — standalone use only.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import numpy as np

# Allow importing from src/backend/eeg without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "backend"))

from eeg.ingestion import EEGSample  # noqa: E402

PULL_MAX_SAMPLES = 32
PULL_TIMEOUT = 0.05
STREAM_TIMEOUT = 15.0


class EEGCollector:
    """
    Threaded EEG collector.

    Usage:
        collector = EEGCollector()
        collector.start()                        # connects to LSL stream
        collector.start_phase("FOCUSED")         # begin labeling
        time.sleep(90)
        samples = collector.end_phase()          # stop labeling, get samples
        collector.stop()
    """

    def __init__(self) -> None:
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # Current phase capture
        self._current_label: str | None = None
        self._phase_buffer: list[EEGSample] = []

        # Full labeled dataset: list of (label, samples)
        self._dataset: list[tuple[str, list[EEGSample]]] = []

        self._inlet = None
        self._connected = threading.Event()
        self._error: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start background collection thread. Blocks until LSL connected or error."""
        self._running = True
        self._thread = threading.Thread(target=self._run, name="eeg-collect", daemon=True)
        self._thread.start()
        # Wait up to STREAM_TIMEOUT for connection
        if not self._connected.wait(timeout=STREAM_TIMEOUT + 2):
            raise RuntimeError("Timed out waiting for EEG LSL stream. Is muselsl running?")
        if self._error:
            raise RuntimeError(self._error)

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)

    def start_phase(self, label: str) -> None:
        """Start capturing samples for a labeled phase."""
        with self._lock:
            self._current_label = label
            self._phase_buffer = []

    def end_phase(self) -> list[EEGSample]:
        """Stop capturing, save phase to dataset, return captured samples."""
        with self._lock:
            samples = list(self._phase_buffer)
            label = self._current_label
            self._current_label = None
            self._phase_buffer = []

        if label and samples:
            self._dataset.append((label, samples))

        return samples

    def get_dataset(self) -> list[tuple[str, list[EEGSample]]]:
        """Return all collected (label, samples) pairs."""
        return list(self._dataset)

    def sample_count(self) -> int:
        """Current phase sample count (thread-safe)."""
        with self._lock:
            return len(self._phase_buffer)

    # ------------------------------------------------------------------
    # Private: background thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        try:
            self._inlet = self._connect()
        except RuntimeError as exc:
            self._error = str(exc)
            self._connected.set()
            return

        self._connected.set()

        while self._running:
            self._pull()

    def _connect(self):
        from pylsl import StreamInlet, resolve_stream
        streams = resolve_stream("type", "EEG", timeout=STREAM_TIMEOUT)
        if not streams:
            raise RuntimeError(
                f"No EEG LSL stream found after {STREAM_TIMEOUT}s.\n"
                "Run: muselsl stream --address XX:XX:XX:XX:XX:XX"
            )
        return StreamInlet(streams[0], max_chunklen=PULL_MAX_SAMPLES)

    def _pull(self) -> None:
        try:
            samples, timestamps = self._inlet.pull_chunk(
                max_samples=PULL_MAX_SAMPLES,
                timeout=PULL_TIMEOUT,
            )
        except Exception:
            return

        if not samples:
            return

        with self._lock:
            if self._current_label is not None:
                for sample, ts in zip(samples, timestamps):
                    arr = np.asarray(sample, dtype=np.float32)
                    self._phase_buffer.append(EEGSample(channels=arr, timestamp=ts))
```

**Step 2: Smoke test (no headband)**

```python
# test: collector imports and init without crashing
import sys
sys.path.insert(0, "scripts/training")
from collect import EEGCollector
c = EEGCollector()
print("OK")
```

Run: `python -c "import sys; sys.path.insert(0,'scripts/training'); from collect import EEGCollector; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add scripts/training/collect.py
git commit -m "feat: add threaded EEG collector for training pipeline"
```

---

## Task 3: Feature extraction + model training (`scripts/training/train.py`)

**Purpose:** Takes labeled raw EEG samples, slides a 2-second window with 50% overlap, extracts 9 features per window, trains SVM with cross-validation, saves model + scaler.

**Files:**
- Create: `scripts/training/train.py`

**Step 1: Write the file**

```python
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
SCALER_PATH = Path(__file__).parent.parent.parent / "config" / "backend" / "scaler.joblib"


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
        classes: list of class names (index → name)
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
```

**Step 2: Unit test feature extraction**

Create `tests/backend/test_train_features.py`:

```python
"""Unit tests for training feature extraction."""
import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "training"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "backend"))

from eeg.ingestion import EEGSample
from train import extract_features, build_dataset, EPS


def _make_samples(n: int = 600, amplitude: float = 10.0) -> list[EEGSample]:
    """Generate synthetic EEG samples (below artifact threshold)."""
    rng = np.random.default_rng(42)
    return [
        EEGSample(
            channels=rng.normal(0, amplitude, size=(5,)).astype(np.float32),
            timestamp=float(i) / 256.0,
        )
        for i in range(n)
    ]


def test_extract_features_returns_9_values():
    samples = _make_samples(600)
    feat = extract_features(samples[:512])
    assert feat is not None
    assert feat.shape == (9,)


def test_extract_features_no_nans():
    samples = _make_samples(600)
    feat = extract_features(samples[:512])
    assert feat is not None
    assert not np.any(np.isnan(feat))


def test_extract_features_too_few_samples():
    # Fewer than min_samples (64) clean samples → should return None
    samples = _make_samples(10)
    feat = extract_features(samples)
    assert feat is None


def test_build_dataset_shape():
    phase_data = [
        ("FOCUSED", _make_samples(1000)),
        ("OVERLOADED", _make_samples(1000)),
        ("DISENGAGED", _make_samples(1000)),
    ]
    X, y, classes = build_dataset(phase_data)
    assert X.shape[1] == 9
    assert len(X) == len(y)
    assert set(classes) == {"FOCUSED", "OVERLOADED", "DISENGAGED"}
    assert len(classes) == 3


def test_build_dataset_all_classes_represented():
    phase_data = [
        ("FOCUSED", _make_samples(800)),
        ("OVERLOADED", _make_samples(800)),
        ("DISENGAGED", _make_samples(800)),
    ]
    X, y, classes = build_dataset(phase_data)
    for i in range(len(classes)):
        assert (y == i).sum() > 0
```

**Step 3: Run tests**

```bash
cd /path/to/BISV-Hacks
python -m pytest tests/backend/test_train_features.py -v
```
Expected: all 5 tests PASS

**Step 4: Commit**

```bash
git add scripts/training/train.py tests/backend/test_train_features.py
git commit -m "feat: add EEG feature extraction and SVM training pipeline"
```

---

## Task 4: Training GUI (`scripts/training/train_gui.py`)

**Purpose:** Full-screen Tkinter GUI. Guides through 8 phases (settle → DISENGAGED → FOCUSED → OVERLOADED × 2 rounds). Shows countdown, task instructions, Stroop words, or N-back letters. Calls collect → train → save on completion.

**Files:**
- Create: `scripts/training/train_gui.py`

**Step 1: Write the file**

```python
"""
NeuroSync EEG Training GUI
--------------------------
Run: python scripts/training/train_gui.py

Requires muselsl streaming first:
  muselsl stream --address XX:XX:XX:XX:XX:XX

Protocol (12 min total):
  Settle (30s) → DISENGAGED (90s) → FOCUSED (90s) → OVERLOADED (90s)
  → Break (30s) → DISENGAGED (90s) → FOCUSED (90s) → OVERLOADED (90s)
  → Training → Done
"""
from __future__ import annotations

import random
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont

sys.path.insert(0, str(Path(__file__).parent))

from collect import EEGCollector
from train import train_and_save

# ── Protocol definition ───────────────────────────────────────────────────────
PHASES = [
    {"label": None,         "name": "SETTLE",      "duration": 30,  "task": "settle"},
    {"label": "DISENGAGED", "name": "DISENGAGED",  "duration": 90,  "task": "rest"},
    {"label": "FOCUSED",    "name": "FOCUSED",     "duration": 90,  "task": "stroop_1"},
    {"label": "OVERLOADED", "name": "OVERLOADED",  "duration": 90,  "task": "nback_2"},
    {"label": None,         "name": "BREAK",       "duration": 30,  "task": "break"},
    {"label": "DISENGAGED", "name": "DISENGAGED",  "duration": 90,  "task": "rest"},
    {"label": "FOCUSED",    "name": "FOCUSED",     "duration": 90,  "task": "stroop_2"},
    {"label": "OVERLOADED", "name": "OVERLOADED",  "duration": 90,  "task": "nback_3"},
]

# Stroop stimuli: (word, display_color)
STROOP_SET_1 = [
    ("RED", "blue"), ("BLUE", "green"), ("GREEN", "red"),
    ("YELLOW", "purple"), ("PURPLE", "yellow"), ("ORANGE", "red"),
    ("RED", "green"), ("GREEN", "blue"), ("BLUE", "red"),
]
STROOP_SET_2 = [
    ("PINK", "orange"), ("ORANGE", "blue"), ("CYAN", "red"),
    ("RED", "cyan"), ("BLUE", "pink"), ("GREEN", "orange"),
    ("YELLOW", "blue"), ("PURPLE", "green"), ("ORANGE", "purple"),
]

NBACK_LETTERS = list("BCDFGHJKLMNPQRSTVWXYZ")


# ── GUI ───────────────────────────────────────────────────────────────────────

class TrainingGUI:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("NeuroSync — EEG Training")
        self.root.configure(bg="#0d0d0d")
        self.root.attributes("-fullscreen", True)

        self._collector = EEGCollector()
        self._phase_idx = 0
        self._phase_start = 0.0
        self._task_job: str | None = None  # tkinter after() handle
        self._nback_sequence: list[str] = []
        self._nback_idx = 0
        self._nback_n = 2
        self._nback_job: str | None = None

        # Fonts
        big = tkfont.Font(family="Helvetica", size=72, weight="bold")
        med = tkfont.Font(family="Helvetica", size=36)
        small = tkfont.Font(family="Helvetica", size=24)
        label_font = tkfont.Font(family="Helvetica", size=18)

        # Layout: phase indicator top, main task middle, countdown bottom
        self.phase_label = tk.Label(
            self.root, text="", font=label_font, bg="#0d0d0d", fg="#555555"
        )
        self.phase_label.pack(pady=(40, 0))

        self.main_text = tk.Label(
            self.root, text="", font=med, bg="#0d0d0d", fg="#ffffff",
            wraplength=900, justify="center"
        )
        self.main_text.pack(expand=True)

        # Stroop word (separate label so we can color it)
        self.stroop_label = tk.Label(
            self.root, text="", font=big, bg="#0d0d0d", fg="#ffffff"
        )
        self.stroop_label.pack()

        # Dot for rest phases
        self.dot = tk.Label(
            self.root, text="●", font=tkfont.Font(family="Helvetica", size=96),
            bg="#0d0d0d", fg="#333333"
        )

        self.countdown = tk.Label(
            self.root, text="", font=med, bg="#0d0d0d", fg="#888888"
        )
        self.countdown.pack(pady=(0, 60))

        self.status_bar = tk.Label(
            self.root, text="", font=label_font, bg="#0d0d0d", fg="#444444"
        )
        self.status_bar.pack(pady=(0, 20))

        # Key binding to quit
        self.root.bind("<Escape>", lambda _: self.root.destroy())
        self.root.bind("<space>", self._on_space)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        self._show_connecting()
        self.root.mainloop()

    # ------------------------------------------------------------------
    # Connection phase
    # ------------------------------------------------------------------

    def _show_connecting(self) -> None:
        self.main_text.config(text="Connecting to Muse headband...\n\nMake sure muselsl is running.", fg="#ffffff")
        self.stroop_label.config(text="")
        self.dot.pack_forget()
        threading.Thread(target=self._connect, daemon=True).start()

    def _connect(self) -> None:
        try:
            self._collector.start()
            self.root.after(0, self._on_connected)
        except RuntimeError as exc:
            self.root.after(0, lambda: self._show_error(str(exc)))

    def _on_connected(self) -> None:
        self.main_text.config(
            text="✓ Connected!\n\nPress SPACE to begin the recording protocol.\n\n"
                 "Total time: ~12 minutes.\nSit still. Minimize jaw movement.",
            fg="#00ff88",
        )
        self.root.bind("<space>", lambda _: self._start_protocol())

    # ------------------------------------------------------------------
    # Protocol loop
    # ------------------------------------------------------------------

    def _start_protocol(self) -> None:
        self.root.unbind("<space>")
        self.root.bind("<space>", self._on_space)
        self._phase_idx = 0
        self._run_phase()

    def _run_phase(self) -> None:
        if self._phase_idx >= len(PHASES):
            self._do_training()
            return

        phase = PHASES[self._phase_idx]
        label = phase["label"]
        name = phase["name"]
        duration = phase["duration"]
        task = phase["task"]

        phase_text = f"Phase {self._phase_idx + 1} of {len(PHASES)} — {name}"
        self.phase_label.config(text=phase_text)
        self.status_bar.config(text="Press ESC to cancel")

        # Start data collection for this phase
        if label:
            self._collector.start_phase(label)

        # Show task UI
        self._show_task(task)
        self._phase_start = time.time()

        # Schedule phase end
        self.root.after(duration * 1000, self._end_phase)

        # Start countdown
        self._update_countdown(duration)

    def _end_phase(self) -> None:
        phase = PHASES[self._phase_idx]
        if phase["label"]:
            samples = self._collector.end_phase()
            self.status_bar.config(text=f"Captured {len(samples)} samples for {phase['label']}")

        # Stop any running task animations
        self._stop_task_animation()

        self._phase_idx += 1
        self._run_phase()

    # ------------------------------------------------------------------
    # Task displays
    # ------------------------------------------------------------------

    def _show_task(self, task: str) -> None:
        self.dot.pack_forget()
        self.stroop_label.config(text="")

        if task == "settle":
            self.main_text.config(
                text="Relax and breathe normally.\nWe'll start the protocol shortly.",
                fg="#ffffff"
            )

        elif task == "break":
            self.main_text.config(
                text="SHORT BREAK\n\nRelax and breathe normally.",
                fg="#ffffff"
            )

        elif task == "rest":
            self.main_text.config(text="REST\n\nEyes open, stare at the dot.", fg="#aaaaaa")
            self.dot.config(fg="#444444")
            self.dot.pack(before=self.countdown)

        elif task.startswith("stroop"):
            stimuli = STROOP_SET_1 if task == "stroop_1" else STROOP_SET_2
            self.main_text.config(
                text="STROOP TEST\n\nSay the COLOR of the word out loud — not the word itself.",
                fg="#ffffff"
            )
            self._run_stroop(stimuli)

        elif task.startswith("nback"):
            n = int(task[-1])  # nback_2 → 2, nback_3 → 3
            self._nback_n = n
            self.main_text.config(
                text=f"{n}-BACK TASK\n\nPress SPACE if the current letter matches the one {n} letters ago.",
                fg="#ffffff"
            )
            self._nback_sequence = []
            self._nback_idx = 0
            self._run_nback()

    def _run_stroop(self, stimuli: list[tuple[str, str]]) -> None:
        """Cycle through Stroop stimuli every 2.5 seconds."""
        pairs = list(stimuli) * 10  # enough for 90s
        random.shuffle(pairs)
        self._stroop_pairs = pairs
        self._stroop_idx = 0
        self._show_stroop_item()

    def _show_stroop_item(self) -> None:
        if self._stroop_idx >= len(self._stroop_pairs):
            self._stroop_idx = 0
        word, color = self._stroop_pairs[self._stroop_idx]
        self.stroop_label.config(text=word, fg=color.lower())
        self._stroop_idx += 1
        self._task_job = self.root.after(2500, self._show_stroop_item)

    def _run_nback(self) -> None:
        letter = random.choice(NBACK_LETTERS)
        # Force some targets: if we have enough history, occasionally repeat
        if len(self._nback_sequence) >= self._nback_n and random.random() < 0.25:
            letter = self._nback_sequence[-self._nback_n]
        self._nback_sequence.append(letter)
        self.stroop_label.config(text=letter, fg="#00aaff")
        self._nback_job = self.root.after(2000, self._nback_next)

    def _nback_next(self) -> None:
        self.stroop_label.config(text="", fg="#ffffff")
        self._nback_job = self.root.after(500, self._run_nback)

    def _stop_task_animation(self) -> None:
        if self._task_job:
            self.root.after_cancel(self._task_job)
            self._task_job = None
        if self._nback_job:
            self.root.after_cancel(self._nback_job)
            self._nback_job = None
        self.stroop_label.config(text="")
        self.dot.pack_forget()

    def _update_countdown(self, total_seconds: int) -> None:
        elapsed = time.time() - self._phase_start
        remaining = max(0, total_seconds - int(elapsed))
        self.countdown.config(text=f"{remaining}s")
        if remaining > 0:
            self.root.after(1000, lambda: self._update_countdown(total_seconds))

    def _on_space(self, _event) -> None:
        """N-back response — no-op here (just visual acknowledgement)."""
        pass

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def _do_training(self) -> None:
        self._stop_task_animation()
        self.phase_label.config(text="Training classifier...")
        self.main_text.config(text="Analyzing EEG data and training classifier.\nThis takes a few seconds.", fg="#ffffff")
        self.stroop_label.config(text="")
        self.countdown.config(text="")
        self.status_bar.config(text="")

        dataset = self._collector.get_dataset()
        self._collector.stop()

        threading.Thread(target=self._train_thread, args=(dataset,), daemon=True).start()

    def _train_thread(self, dataset) -> None:
        try:
            accuracy = train_and_save(dataset, verbose=True)
            self.root.after(0, lambda: self._show_done(accuracy))
        except Exception as exc:
            self.root.after(0, lambda: self._show_error(str(exc)))

    def _show_done(self, accuracy: float) -> None:
        self.phase_label.config(text="COMPLETE", fg="#00ff88")
        self.main_text.config(
            text=f"✓ Training complete!\n\nCross-validation accuracy: {accuracy:.1%}\n\n"
                 "Model saved to config/backend/classifier.joblib\n\n"
                 "Press ESC to exit.",
            fg="#00ff88",
        )
        self.countdown.config(text="")

    def _show_error(self, msg: str) -> None:
        self.phase_label.config(text="ERROR", fg="#ff4444")
        self.main_text.config(text=f"Error:\n\n{msg}\n\nPress ESC to exit.", fg="#ff4444")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    gui = TrainingGUI()
    gui.run()
```

**Step 2: Manual test without headband**

```bash
# Verify it launches without crashing (will show "Connecting..." and fail gracefully)
python scripts/training/train_gui.py
```
Expected: Window opens, shows "Connecting to Muse headband...", then shows error message when no stream found. No crash.

**Step 3: Commit**

```bash
git add scripts/training/train_gui.py
git commit -m "feat: add Tkinter EEG training GUI with Stroop + N-back protocol"
```

---

## Task 5: Update classifier to load pretrained model

**Purpose:** `CognitiveStateClassifier.classify()` first tries to load the saved SVM model from `config/backend/classifier.joblib`. If missing → falls back to current heuristics unchanged.

**Files:**
- Modify: `src/backend/eeg/classifier.py`

**Step 1: Read classifier.py** (already done above — understand the current structure)

**Step 2: Add model loading at top of `CognitiveStateClassifier.__init__`**

Replace the existing `CognitiveStateClassifier` class `__init__` and `classify` methods with:

```python
class CognitiveStateClassifier:
    """
    Classifies cognitive state from band powers.

    If config/backend/classifier.joblib exists (trained via scripts/training/train_gui.py),
    uses the pretrained SVM. Otherwise falls back to heuristic band power ratios.
    """

    _MODEL_PATH = Path(__file__).parent.parent.parent.parent / "config" / "backend" / "classifier.joblib"

    def __init__(self) -> None:
        self.calibrator = BaselineCalibrator()
        self._pipeline = None
        self._classes: list[str] = []
        self._load_pretrained()

    def _load_pretrained(self) -> None:
        """Try to load the trained SVM model. Silently falls back to heuristics."""
        try:
            import joblib
            data = joblib.load(self._MODEL_PATH)
            self._pipeline = data["pipeline"]
            self._classes = data["classes"]
            logger.info("Pretrained EEG classifier loaded from %s (classes: %s)", self._MODEL_PATH, self._classes)
        except FileNotFoundError:
            logger.info("No pretrained classifier found at %s — using heuristics", self._MODEL_PATH)
        except Exception as exc:
            logger.warning("Failed to load pretrained classifier: %s — using heuristics", exc)

    @property
    def using_pretrained(self) -> bool:
        return self._pipeline is not None

    def classify(self, powers: BandPowers) -> ClassificationResult:
        """Classify band powers into a cognitive state."""
        if self._pipeline is not None:
            return self._classify_pretrained(powers)
        return self._classify_heuristic(powers)

    def _classify_pretrained(self, powers: BandPowers) -> ClassificationResult:
        """Use the loaded SVM model."""
        import numpy as np
        EPS_LOCAL = 1e-10
        d, t, a, b, g = powers.delta, powers.theta, powers.alpha, powers.beta, powers.gamma
        features = np.array([
            d, t, a, b, g,
            b / max(t, EPS_LOCAL),
            b / max(a, EPS_LOCAL),
            (b + g) / max(a + t, EPS_LOCAL),
            t / max(a, EPS_LOCAL),
        ], dtype=np.float32)

        proba = self._pipeline.predict_proba(features.reshape(1, -1))[0]
        idx = int(np.argmax(proba))
        state = self._classes[idx]
        confidence = float(proba[idx])

        focus_score = b / max(t, EPS_LOCAL)
        cognitive_load = b + g

        return ClassificationResult(
            state=state,
            confidence=round(confidence, 3),
            focus_score=round(focus_score, 4),
            cognitive_load=round(cognitive_load, 4),
            relative_to_baseline=False,
        )

    def _classify_heuristic(self, powers: BandPowers) -> ClassificationResult:
        """Original heuristic classifier (unchanged)."""
        normalized = self.calibrator.normalize(powers)

        rel_beta = normalized["beta"]
        rel_theta = normalized["theta"]
        rel_gamma = normalized["gamma"]

        focus_score = rel_beta / max(rel_theta, EPS)
        cognitive_load = rel_beta + rel_gamma

        has_baseline = self.calibrator.is_ready

        if cognitive_load > LOAD_HIGH_THRESHOLD:
            state = "OVERLOADED"
            confidence = min(1.0, 0.6 + (cognitive_load - LOAD_HIGH_THRESHOLD) * 0.5)
        elif focus_score > FOCUS_HIGH_THRESHOLD:
            state = "FOCUSED"
            confidence = min(1.0, 0.6 + (focus_score - FOCUS_HIGH_THRESHOLD) * 0.3)
        elif focus_score < FOCUS_LOW_THRESHOLD:
            state = "DISENGAGED"
            confidence = min(1.0, 0.6 + (FOCUS_LOW_THRESHOLD - focus_score) * 0.5)
        else:
            state = "FOCUSED"
            confidence = 0.55

        if not has_baseline:
            confidence *= 0.7

        return ClassificationResult(
            state=state,
            confidence=round(confidence, 3),
            focus_score=round(focus_score, 4),
            cognitive_load=round(cognitive_load, 4),
            relative_to_baseline=has_baseline,
        )
```

Also add `from pathlib import Path` to the imports at the top of `classifier.py`.

**Step 3: Write the test**

Add to `tests/backend/test_eeg_processing.py` (or a new file `tests/backend/test_classifier_pretrained.py`):

```python
"""Tests for pretrained model loading and fallback."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "backend"))

from eeg.classifier import CognitiveStateClassifier
from eeg.processor import BandPowers
import time


def _make_powers(**kwargs) -> BandPowers:
    defaults = dict(delta=0.2, theta=0.2, alpha=0.2, beta=0.2, gamma=0.2, timestamp=time.time())
    defaults.update(kwargs)
    return BandPowers(**defaults)


def test_classifier_falls_back_to_heuristics_when_no_model(tmp_path, monkeypatch):
    """When no model file exists, classifier uses heuristics."""
    monkeypatch.setattr(
        "eeg.classifier.CognitiveStateClassifier._MODEL_PATH",
        tmp_path / "nonexistent.joblib",
    )
    clf = CognitiveStateClassifier()
    assert not clf.using_pretrained


def test_heuristic_classify_returns_valid_state():
    clf = CognitiveStateClassifier()
    # Force heuristic path
    clf._pipeline = None

    powers = _make_powers(beta=0.5, theta=0.1, gamma=0.3)
    result = clf.classify(powers)
    assert result.state in ("FOCUSED", "OVERLOADED", "DISENGAGED")
    assert 0.0 <= result.confidence <= 1.0


def test_classify_result_fields():
    clf = CognitiveStateClassifier()
    clf._pipeline = None
    result = clf.classify(_make_powers())
    assert hasattr(result, "state")
    assert hasattr(result, "confidence")
    assert hasattr(result, "focus_score")
    assert hasattr(result, "cognitive_load")
```

**Step 4: Run tests**

```bash
python -m pytest tests/backend/test_classifier_pretrained.py -v
```
Expected: all tests PASS

**Step 5: Commit**

```bash
git add src/backend/eeg/classifier.py tests/backend/test_classifier_pretrained.py
git commit -m "feat: classifier loads pretrained SVM model, falls back to heuristics"
```

---

## Task 6: Add run script + usage instructions

**Files:**
- Modify: `scripts/backend/mock.sh` — add note about training
- Create: `scripts/training/README_TRAINING.txt`

**Step 1: Write README_TRAINING.txt**

```
NeuroSync EEG Training — Quick Start
=====================================

Prerequisites (Mac):
  pip install muselsl pylsl scikit-learn joblib numpy scipy

Step 1: Start Muse stream
  muselsl stream --address XX:XX:XX:XX:XX:XX
  (replace with your Muse BLE address — find it with: muselsl list)

Step 2: Run training GUI (separate terminal)
  python scripts/training/train_gui.py

Step 3: Follow GUI instructions (~12 minutes)
  - Settle (30s): relax
  - DISENGAGED (90s x2): stare at dot, do nothing
  - FOCUSED (90s x2): Stroop test — say the COLOR not the word
  - OVERLOADED (90s x2): N-back — press SPACE when letter matches N ago

Step 4: Model saved automatically
  config/backend/classifier.joblib

Step 5: Restart the backend
  The main app loads the model on startup automatically.
  No code changes needed.

Tips:
  - Sit still, minimize jaw movement during recording
  - For DISENGAGED: truly do nothing, let mind wander
  - For OVERLOADED: try hard on the N-back — don't give up
  - For FOCUSED: say each color out loud clearly
```

**Step 2: Commit**

```bash
git add scripts/training/README_TRAINING.txt
git commit -m "docs: add EEG training quick-start instructions"
```

---

## Summary

After all tasks, the flow is:

```
muselsl stream  →  python scripts/training/train_gui.py
                         ↓ (12 min protocol)
                   config/backend/classifier.joblib
                         ↓ (auto-loaded on import)
                   src/backend/eeg/classifier.py
                         ↓
                   main app uses pretrained model
```

Test coverage: feature extraction, dataset building, classifier fallback logic.
No headband required to run unit tests.
