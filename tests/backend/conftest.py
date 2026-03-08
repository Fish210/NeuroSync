"""
Pytest fixtures for NeuroSync backend tests.

All EEG fixtures are synthetic — no real hardware required.
Tests run in standard pytest with asyncio support.
"""
from __future__ import annotations

import asyncio
import time
from typing import Generator
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Synthetic EEG data fixtures
# ---------------------------------------------------------------------------

def _make_eeg_sample(
    alpha: float = 0.35,
    beta: float = 0.42,
    theta: float = 0.20,
    gamma: float = 0.28,
    delta: float = 0.22,
    noise_scale: float = 0.01,
    n_channels: int = 5,
    sample_rate: float = 256.0,
    n_samples: int = 512,
) -> list:
    """
    Generate synthetic EEG samples with target band power profile.

    Creates a time-domain signal by summing sinusoids at representative
    frequencies for each band, then adding Gaussian noise.
    Returns a list of (n_samples, n_channels) arrays (one per sample).
    """
    t = np.linspace(0, n_samples / sample_rate, n_samples)

    # Representative frequencies per band
    freqs = {
        "delta": 2.0,
        "theta": 6.0,
        "alpha": 10.0,
        "beta": 20.0,
        "gamma": 40.0,
    }
    powers = {"delta": delta, "theta": theta, "alpha": alpha, "beta": beta, "gamma": gamma}

    # Sum sinusoids weighted by target band powers
    signal_1d = np.zeros(n_samples)
    for band, freq in freqs.items():
        amplitude = np.sqrt(powers[band])
        signal_1d += amplitude * np.sin(2 * np.pi * freq * t)

    signal_1d += np.random.normal(0, noise_scale, n_samples)

    # Tile to n_channels (all channels identical for simplicity)
    signal = np.tile(signal_1d[:, None], (1, n_channels)).astype(np.float32)

    # Return as list of per-sample arrays (matching EEGSample.channels shape)
    return [signal[i] for i in range(n_samples)]


@pytest.fixture
def focused_samples():
    """Synthetic EEG samples representative of FOCUSED state (high beta/theta ratio)."""
    return _make_eeg_sample(alpha=0.30, beta=0.55, theta=0.15, gamma=0.25, delta=0.15)


@pytest.fixture
def overloaded_samples():
    """Synthetic EEG samples representative of OVERLOADED state (high beta+gamma)."""
    return _make_eeg_sample(alpha=0.15, beta=0.65, theta=0.15, gamma=0.55, delta=0.10)


@pytest.fixture
def disengaged_samples():
    """Synthetic EEG samples representative of DISENGAGED state (high alpha, low beta)."""
    return _make_eeg_sample(alpha=0.60, beta=0.20, theta=0.40, gamma=0.15, delta=0.30)


@pytest.fixture
def artifact_samples():
    """Samples with blink artifact (high-amplitude transient on channel 1)."""
    samples = _make_eeg_sample()
    # Inject 150µV artifact spike in first 32 samples
    for i in range(32):
        samples[i] = samples[i].copy()
        samples[i][0] = 150.0  # TP9 channel spike
    return samples


@pytest.fixture
def event_loop():
    """Create an asyncio event loop for each test."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
