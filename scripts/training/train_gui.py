"""
NeuroSync EEG Training GUI
--------------------------
Run: python scripts/training/train_gui.py

Requires muselsl streaming first:
  muselsl stream --address XX:XX:XX:XX:XX:XX

Protocol (12 min total):
  Settle (30s) -> DISENGAGED (90s) -> FOCUSED (90s) -> OVERLOADED (90s)
  -> Break (30s) -> DISENGAGED (90s) -> FOCUSED (90s) -> OVERLOADED (90s)
  -> Training -> Done
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

# -- Protocol definition -------------------------------------------------------
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


# -- GUI -----------------------------------------------------------------------

class TrainingGUI:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("NeuroSync — EEG Training")
        self.root.configure(bg="#0d0d0d")
        self.root.attributes("-fullscreen", True)

        self._collector = EEGCollector()
        self._phase_idx = 0
        self._phase_start = 0.0
        self._task_job: str | None = None
        self._nback_sequence: list[str] = []
        self._nback_idx = 0
        self._nback_n = 2
        self._nback_job: str | None = None
        self._stroop_pairs: list[tuple[str, str]] = []
        self._stroop_idx = 0

        # Fonts
        big = tkfont.Font(family="Helvetica", size=72, weight="bold")
        med = tkfont.Font(family="Helvetica", size=36)
        label_font = tkfont.Font(family="Helvetica", size=18)

        self.phase_label = tk.Label(
            self.root, text="", font=label_font, bg="#0d0d0d", fg="#555555"
        )
        self.phase_label.pack(pady=(40, 0))

        self.main_text = tk.Label(
            self.root, text="", font=med, bg="#0d0d0d", fg="#ffffff",
            wraplength=900, justify="center"
        )
        self.main_text.pack(expand=True)

        self.stroop_label = tk.Label(
            self.root, text="", font=big, bg="#0d0d0d", fg="#ffffff"
        )
        self.stroop_label.pack()

        self.dot = tk.Label(
            self.root, text="\u25cf",
            font=tkfont.Font(family="Helvetica", size=96),
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
        self.main_text.config(
            text="Connecting to Muse headband...\n\nMake sure muselsl is running.",
            fg="#ffffff"
        )
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
            text="Connected!\n\nPress SPACE to begin the recording protocol.\n\n"
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

        if label:
            self._collector.start_phase(label)

        self._show_task(task)
        self._phase_start = time.time()

        self.root.after(duration * 1000, self._end_phase)
        self._update_countdown(duration)

    def _end_phase(self) -> None:
        phase = PHASES[self._phase_idx]
        if phase["label"]:
            samples = self._collector.end_phase()
            self.status_bar.config(
                text=f"Captured {len(samples)} samples for {phase['label']}"
            )

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
            self.main_text.config(
                text="REST\n\nEyes open, stare at the dot.",
                fg="#aaaaaa"
            )
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
            n = int(task[-1])
            self._nback_n = n
            self.main_text.config(
                text=f"{n}-BACK TASK\n\n"
                     f"Press SPACE if the current letter matches the one {n} letters ago.",
                fg="#ffffff"
            )
            self._nback_sequence = []
            self._nback_idx = 0
            self._run_nback()

    def _run_stroop(self, stimuli: list[tuple[str, str]]) -> None:
        pairs = list(stimuli) * 10
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
        if (
            len(self._nback_sequence) >= self._nback_n
            and random.random() < 0.25
        ):
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
        pass

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def _do_training(self) -> None:
        self._stop_task_animation()
        self.phase_label.config(text="Training classifier...")
        self.main_text.config(
            text="Analyzing EEG data and training classifier.\nThis takes a few seconds.",
            fg="#ffffff"
        )
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
            text=f"Training complete!\n\n"
                 f"Cross-validation accuracy: {accuracy:.1%}\n\n"
                 "Model saved to config/backend/classifier.joblib\n\n"
                 "Press ESC to exit.",
            fg="#00ff88",
        )
        self.countdown.config(text="")

    def _show_error(self, msg: str) -> None:
        self.phase_label.config(text="ERROR", fg="#ff4444")
        self.main_text.config(
            text=f"Error:\n\n{msg}\n\nPress ESC to exit.",
            fg="#ff4444"
        )


# -- Entry point ---------------------------------------------------------------

if __name__ == "__main__":
    gui = TrainingGUI()
    gui.run()
