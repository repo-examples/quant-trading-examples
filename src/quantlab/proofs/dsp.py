"""Digital Signal Processing (DSP) Diagnostics: Hilbert Transform, Bode Response & Jerk Pareto Frontier."""

from __future__ import annotations

from dataclasses import dataclass

import numba
import numpy as np
from scipy import signal


@dataclass(frozen=True)
class DSPResult:
    """Hilbert analytic signal, Bode frequency response, and Jerk smoothness metrics."""

    instantaneous_amplitude: np.ndarray
    instantaneous_phase: np.ndarray
    instantaneous_frequency: np.ndarray
    mean_phase_lag_rad: float
    mean_phase_lag_bars: float
    jerk_energy: float
    bode_frequencies: np.ndarray
    bode_magnitude_db: np.ndarray
    bode_phase_deg: np.ndarray
    pareto_optimal: bool = True


def compute_jerk_energy(series: np.ndarray) -> float:
    """Compute normalized third-derivative Jerk energy J = (1 / (N - 3)) * sum(|Delta^3 x_t|^2)."""
    x = np.asarray(series, dtype=np.float64)
    x = x[np.isfinite(x)]
    if len(x) < 6:
        return 0.0
    std = float(np.std(x))
    if std < 1e-14:
        return 0.0
    xz = (x - np.mean(x)) / std
    d3 = xz[3:] - 3.0 * xz[2:-1] + 3.0 * xz[1:-2] - xz[:-3]
    return float(np.mean(d3 * d3))


@numba.njit(cache=True)
def _causal_ema_detrend_kernel(x: np.ndarray, alpha: float) -> np.ndarray:
    n = len(x)
    detrended = np.empty(n, dtype=np.float64)
    ema = x[0]
    detrended[0] = 0.0
    for t in range(1, n):
        ema = alpha * x[t] + (1.0 - alpha) * ema
        detrended[t] = x[t] - ema
    return detrended


def _causal_detrend(series: np.ndarray, period: int = 20) -> np.ndarray:
    """Remove low-frequency drift causally so Hilbert phase measures oscillatory cycle."""
    x = np.ascontiguousarray(series, dtype=np.float64)
    n = len(x)
    if n < 4:
        return np.zeros_like(x)
    alpha = 2.0 / (float(max(2, period)) + 1.0)
    detrended = _causal_ema_detrend_kernel(x, alpha)
    std = float(np.std(detrended))
    if std > 1e-14:
        detrended = detrended / std
    return detrended


def compute_hilbert_diagnostics(
    indicator_series: np.ndarray,
    reference_series: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, float]:
    """Compute Hilbert analytic signal diagnostics and phase lag relative to reference price.

    Returns:
        (inst_amplitude, inst_phase, inst_freq, mean_phase_lag_rad, mean_phase_lag_bars)
    """
    ind = np.nan_to_num(np.asarray(indicator_series, dtype=np.float64), nan=0.0)
    ref = np.nan_to_num(np.asarray(reference_series, dtype=np.float64), nan=0.0)
    n = len(ind)
    if n < 8 or np.std(ind) < 1e-14 or np.std(ref) < 1e-14:
        zeros = np.zeros(n, dtype=np.float64)
        return zeros, zeros, zeros, 0.0, 0.0

    ind_osc = _causal_detrend(ind, period=24)
    ref_osc = _causal_detrend(ref, period=24)

    analytic_ind = signal.hilbert(ind_osc)
    analytic_ref = signal.hilbert(ref_osc)

    inst_amp = np.abs(analytic_ind).astype(np.float64)
    inst_phase = np.unwrap(np.angle(analytic_ind)).astype(np.float64)
    inst_freq = np.zeros(n, dtype=np.float64)
    inst_freq[1:] = np.diff(inst_phase)

    # Cross-analytic phase difference z_ref * conj(z_ind)
    cross = analytic_ref * np.conj(analytic_ind)
    weights = np.abs(cross)
    weight_sum = float(np.sum(weights))
    if weight_sum > 1e-12:
        mean_vec = np.sum(cross) / weight_sum
        phase_lag_rad = float(np.abs(np.angle(mean_vec)))
    else:
        phase_lag_rad = 0.0

    mean_omega = float(np.clip(np.median(np.abs(inst_freq[1:])), 0.05, np.pi))
    phase_lag_bars = float(phase_lag_rad / mean_omega)
    return inst_amp, inst_phase, inst_freq, phase_lag_rad, phase_lag_bars


def compute_bode_response(
    indicator_series: np.ndarray,
    reference_series: np.ndarray,
    nperseg: int = 128,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Estimate empirical Bode magnitude (dB) and phase (degrees) transfer function H(omega)."""
    ind = np.nan_to_num(np.asarray(indicator_series, dtype=np.float64), nan=0.0)
    ref = np.nan_to_num(np.asarray(reference_series, dtype=np.float64), nan=0.0)
    n = len(ind)
    if n < 16 or np.std(ind) < 1e-14 or np.std(ref) < 1e-14:
        freqs = np.linspace(0.01, np.pi, 32)
        return freqs, np.zeros_like(freqs), np.zeros_like(freqs)

    ind_z = (ind - np.mean(ind)) / max(float(np.std(ind)), 1e-12)
    ref_z = (ref - np.mean(ref)) / max(float(np.std(ref)), 1e-12)

    seg = min(int(nperseg), max(16, n // 2))
    freqs_cyc, pxx = signal.welch(ref_z, fs=1.0, nperseg=seg)
    _, pxy = signal.csd(ref_z, ind_z, fs=1.0, nperseg=seg)

    # Exclude DC component (index 0)
    omega = (2.0 * np.pi * freqs_cyc[1:]).astype(np.float64)
    h_tf = pxy[1:] / np.maximum(pxx[1:], 1e-14)
    mag_db = (20.0 * np.log10(np.maximum(np.abs(h_tf), 1e-8))).astype(np.float64)
    phase_deg = np.rad2deg(np.unwrap(np.angle(h_tf))).astype(np.float64)
    return omega, mag_db, phase_deg


def identify_pareto_frontier(
    metrics: dict[str, tuple[float, float]],
) -> dict[str, bool]:
    """Identify Pareto-optimal indicators minimizing both (abs_phase_lag_bars, jerk_energy)."""
    result: dict[str, bool] = {}
    items = list(metrics.items())
    for name_a, (lag_a, jerk_a) in items:
        dominated = False
        for name_b, (lag_b, jerk_b) in items:
            if name_a == name_b:
                continue
            if (lag_b <= lag_a and jerk_b <= jerk_a) and (lag_b < lag_a or jerk_b < jerk_a):
                dominated = True
                break
        result[name_a] = not dominated
    return result


def evaluate_dsp_proof(
    indicator_series: np.ndarray,
    reference_series: np.ndarray,
    pareto_optimal: bool = True,
) -> DSPResult:
    """Compute the full DSP diagnostic suite (Hilbert phase lag, Bode response, and Jerk energy)."""
    inst_amp, inst_phase, inst_freq, lag_rad, lag_bars = compute_hilbert_diagnostics(
        indicator_series, reference_series
    )
    jerk = compute_jerk_energy(indicator_series)
    omega, mag_db, phase_deg = compute_bode_response(indicator_series, reference_series)
    return DSPResult(
        instantaneous_amplitude=inst_amp,
        instantaneous_phase=inst_phase,
        instantaneous_frequency=inst_freq,
        mean_phase_lag_rad=lag_rad,
        mean_phase_lag_bars=lag_bars,
        jerk_energy=jerk,
        bode_frequencies=omega,
        bode_magnitude_db=mag_db,
        bode_phase_deg=phase_deg,
        pareto_optimal=pareto_optimal,
    )
