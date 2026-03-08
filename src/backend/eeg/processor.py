"""
EEG band power processor.

Computes alpha, beta, theta, gamma, delta band powers from a window
of EEG samples using FFT. Applies artifact rejection before computing.

Band definitions (Hz):
    delta: 0.5 – 4
    theta: 4 – 8
    alpha: 8 – 13
    beta:  13 – 30
    gamma: 30 – 50

Artifact rejection:
    Samples where any channel exceeds ARTIFACT_THRESHOLD_UV are excluded.
    This removes blink artifacts, muscle noise, and headband slippage.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import numpy as np
from scipy import signal as sp_signal

logger = logging.getLogger(__name__)

# Muse headband sample rate (Hz)
SAMPLE_RATE = 256.0

# Artifact rejection threshold in microvolts
# Blinks / jaw clench produce >100µV transients
ARTIFACT_THRESHOLD_UV = 100.0

# Frequency band definitions (Hz): (low, high)
BANDS = {
    "delta": (0.5, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 13.0),
    "beta": (13.0, 30.0),
    "gamma": (30.0, 50.0),
}

# EEG channels to use for averaging (exclude AUX channel index 4)
EEG_CHANNELS = [0, 1, 2, 3]  # TP9, AF7, AF8, TP10


@dataclass
class BandPowers:
    delta: float
    theta: float
    alpha: float
    beta: float
    gamma: float
    timestamp: float


class EEGProcessor:
    """
    Computes band powers from a buffer of EEG samples.

    Usage:
        processor = EEGProcessor(sample_rate=256.0)
        powers = processor.compute(samples)  # list[EEGSample]
        if powers:
            print(powers.beta, powers.theta)
    """

    def __init__(
        self,
        sample_rate: float = SAMPLE_RATE,
        artifact_threshold_uv: float = ARTIFACT_THRESHOLD_UV,
        min_samples: int = 64,  # minimum clean samples needed
    ) -> None:
        self.sample_rate = sample_rate
        self.artifact_threshold_uv = artifact_threshold_uv
        self.min_samples = min_samples

    def compute(self, samples: list) -> BandPowers | None:
        """
        Compute band powers from a list of EEGSample objects.

        Returns None if not enough clean samples remain after artifact rejection.
        """
        if not samples:
            return None

        # Stack samples into array: shape (N, channels)
        try:
            arr = np.stack([s.channels for s in samples], axis=0)  # (N, 5)
        except (AttributeError, ValueError) as exc:
            logger.warning("Failed to stack EEG samples: %s", exc)
            return None

        # Use only EEG channels, exclude AUX
        eeg = arr[:, EEG_CHANNELS]  # (N, 4)

        # Artifact rejection: exclude rows where any channel exceeds threshold
        clean_mask = np.all(np.abs(eeg) < self.artifact_threshold_uv, axis=1)
        clean = eeg[clean_mask]

        rejected = len(eeg) - len(clean)
        if rejected > 0:
            logger.debug("Artifact rejection: removed %d/%d samples", rejected, len(eeg))

        if len(clean) < self.min_samples:
            logger.debug(
                "Not enough clean samples after artifact rejection: %d < %d",
                len(clean),
                self.min_samples,
            )
            return None

        # Average across channels → 1D signal
        mono = clean.mean(axis=1)  # (N,)

        # Compute band powers via Welch periodogram (robust to noise)
        freqs, psd = sp_signal.welch(
            mono,
            fs=self.sample_rate,
            nperseg=min(256, len(mono)),
            scaling="density",
        )

        powers = {}
        for band_name, (low, high) in BANDS.items():
            mask = (freqs >= low) & (freqs <= high)
            if not mask.any():
                powers[band_name] = 0.0
            else:
                # Integrate PSD over the band (trapezoidal rule)
                powers[band_name] = float(np.trapz(psd[mask], freqs[mask]))

        # Normalize to avoid scale issues (relative band powers)
        total = sum(powers.values()) + 1e-10
        powers = {k: v / total for k, v in powers.items()}

        return BandPowers(
            delta=powers["delta"],
            theta=powers["theta"],
            alpha=powers["alpha"],
            beta=powers["beta"],
            gamma=powers["gamma"],
            timestamp=time.time(),
        )
