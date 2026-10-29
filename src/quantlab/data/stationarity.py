"""Fixed-Width Window Fractional Differentiation (FracDiff) & Augmented Dickey-Fuller (ADF) Stationarity."""

from __future__ import annotations

from dataclasses import dataclass

import numba
import numpy as np
from scipy import special


@dataclass(frozen=True)
class StationarityResult:
    """Result of Fractional Differentiation (FFD) and ADF stationarity verification."""

    d_optimal: float
    adf_stat: float
    p_value: float
    critical_values: dict[str, float]
    memory_correlation: float
    weights: np.ndarray
    series: np.ndarray
    warmup_bars: int
    passed: bool


def compute_ffd_weights(
    d: float,
    threshold: float = 1e-4,
    max_window: int = 256,
) -> np.ndarray:
    """Compute causal Fixed-Width Window Fractional Differentiation weights.

    Recurrence:
        w_0 = 1
        w_k = -w_{k-1} * (d - k + 1) / k
    Truncated when |w_k| < threshold or k reaches max_window.
    """
    if d < 0.0:
        raise ValueError(f"Fractional differentiation order d must be >= 0, got {d}")
    if d == 0.0:
        return np.array([1.0], dtype=np.float64)

    weights = [1.0]
    for k in range(1, max_window):
        w_next = -weights[-1] * (d - k + 1.0) / float(k)
        if abs(w_next) < threshold:
            break
        weights.append(w_next)
    return np.asarray(weights, dtype=np.float64)


@numba.njit(cache=True)
def _causal_ffd_convolve(series: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Strictly causal Fixed-Width Window Fractional Differentiation kernel.

    Uses Neumann boundary clamping (x_{t-k} = x_0 for t - k < 0) during warm-up bars
    so every index t depends exclusively on {x_0, ..., x_t} with zero scale jump.
    """
    n = len(series)
    k_len = len(weights)
    out = np.empty(n, dtype=np.float64)
    x0 = series[0]
    for t in range(n):
        acc = 0.0
        for k in range(k_len):
            idx = t - k
            val = series[idx] if idx >= 0 else x0
            acc += weights[k] * val
        out[t] = acc
    return out


def frac_diff_ffd(
    series: np.ndarray,
    d: float,
    threshold: float = 1e-4,
    max_window: int = 256,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply Fixed-Width Window Fractional Differentiation of order d to a 1D series.

    Returns:
        (differentiated_series, weights)
    """
    arr = np.ascontiguousarray(series, dtype=np.float64)
    if arr.ndim != 1 or len(arr) < 8:
        raise ValueError(f"Input series must be 1D with length >= 8, got shape {arr.shape}")
    weights = compute_ffd_weights(d=d, threshold=threshold, max_window=max_window)
    diff_series = _causal_ffd_convolve(arr, weights)
    return diff_series, weights


def _mackinnon_p_value_c(tau: float) -> float:
    """MacKinnon (1994/2010) approximate p-value for ADF regression with constant (no trend)."""
    # Critical value response surface for constant-only ADF (N -> inf):
    # 1%: -3.4335, 5%: -2.8621, 10%: -2.5671
    if not np.isfinite(tau):
        return 1.0
    if tau >= 0.5:
        return 0.999
    if tau <= -12.0:
        return 1e-10

    # Polynomial coefficients from MacKinnon (1994) Table 1 & 2 for N_vars=1 (constant)
    if tau <= -1.61:
        # Small p-value region (left tail)
        c0, c1, c2 = 2.1659, 1.4412, 0.038269
        z = c0 + c1 * tau + c2 * (tau**2)
    else:
        # Large p-value region (right tail)
        c0, c1, c2 = 1.7339, 0.93202, -0.12745
        z = c0 + c1 * tau + c2 * (tau**2)

    p = float(special.ndtr(z))
    return float(np.clip(p, 1e-10, 0.9999))


def adf_test(
    series: np.ndarray,
    max_lags: int | None = None,
) -> tuple[float, float, dict[str, float]]:
    """Perform the Augmented Dickey-Fuller (ADF) unit-root test with constant drift.

    Regression:
        Delta y_t = alpha + beta * y_{t-1} + sum_{i=1}^p gamma_i * Delta y_{t-i} + eps_t

    Returns:
        (adf_t_statistic, p_value, critical_values)
    """
    y = np.asarray(series, dtype=np.float64)
    y = y[np.isfinite(y)]
    n = len(y)
    crit = {"1%": -3.4335, "5%": -2.8621, "10%": -2.5671}
    if n < 16:
        raise ValueError(f"ADF test requires at least 16 finite observations, got {n}")

    if np.std(y) < 1e-14:
        return 0.0, 0.999, crit

    dy = np.diff(y)
    if max_lags is None:
        # Schwert (1989) rule of thumb capped for stability
        p = int(min(max(1, int(4.0 * ((n / 100.0) ** 0.25))), max(1, n // 6)))
    else:
        p = max(0, int(max_lags))

    n_eff = len(dy) - p
    if n_eff < p + 4:
        p = 0
        n_eff = len(dy)

    target = dy[p:]
    y_lag1 = y[p : p + n_eff]

    cols = [np.ones(n_eff, dtype=np.float64), y_lag1]
    for lag in range(1, p + 1):
        cols.append(dy[p - lag : p - lag + n_eff])

    x_mat = np.column_stack(cols)
    # Solve OLS via QR/SVD least squares
    params, _, _, _ = np.linalg.lstsq(x_mat, target, rcond=None)
    residuals = target - x_mat @ params
    dof = max(1, n_eff - x_mat.shape[1])
    sigma2 = float(np.dot(residuals, residuals) / dof)

    xtx_inv = np.linalg.pinv(x_mat.T @ x_mat)
    se_beta = float(np.sqrt(max(sigma2 * xtx_inv[1, 1], 1e-24)))
    adf_stat = float(params[1] / se_beta)
    p_val = _mackinnon_p_value_c(adf_stat)
    return adf_stat, p_val, crit


def find_min_ffd_d(
    series: np.ndarray,
    alpha: float = 0.05,
    threshold: float = 1e-4,
    max_window: int = 256,
    grid_steps: int = 21,
) -> StationarityResult:
    """Find the minimum Fractional Differentiation order d* in [0, 1] achieving ADF p < alpha."""
    arr = np.ascontiguousarray(series, dtype=np.float64)
    if arr.ndim != 1 or len(arr) < 32:
        raise ValueError(f"find_min_ffd_d requires a 1D series of length >= 32, got {arr.shape}")

    d_candidates = np.linspace(0.0, 1.0, grid_steps)
    best_d = 1.0
    best_series = arr.copy()
    best_weights = np.array([1.0], dtype=np.float64)
    best_stat = 0.0
    best_p = 1.0
    best_crit = {"1%": -3.4335, "5%": -2.8621, "10%": -2.5671}
    found = False

    for d_val in d_candidates:
        d_float = float(np.round(d_val, 4))
        ffd_series, weights = frac_diff_ffd(arr, d=d_float, threshold=threshold, max_window=max_window)
        warmup = max(0, len(weights) - 1)
        eval_slice = ffd_series[warmup:] if len(ffd_series) - warmup >= 20 else ffd_series
        stat, p_val, crit = adf_test(eval_slice)
        if p_val < alpha:
            best_d = d_float
            best_series = ffd_series
            best_weights = weights
            best_stat = stat
            best_p = p_val
            best_crit = crit
            found = True
            break

    if not found:
        best_d = 1.0
        best_series, best_weights = frac_diff_ffd(arr, d=1.0, threshold=threshold, max_window=max_window)
        warmup = max(0, len(best_weights) - 1)
        eval_slice = best_series[warmup:] if len(best_series) - warmup >= 20 else best_series
        best_stat, best_p, best_crit = adf_test(eval_slice)

    warmup_bars = max(0, len(best_weights) - 1)
    eff_warmup = warmup_bars if len(arr) - warmup_bars >= 16 else 0
    valid_orig = arr[eff_warmup:]
    valid_ffd = best_series[eff_warmup:]
    if len(valid_orig) >= 4 and np.std(valid_orig) > 1e-12 and np.std(valid_ffd) > 1e-12:
        corr = float(np.corrcoef(valid_orig, valid_ffd)[0, 1])
    else:
        corr = 0.0

    return StationarityResult(
        d_optimal=best_d,
        adf_stat=best_stat,
        p_value=best_p,
        critical_values=best_crit,
        memory_correlation=corr,
        weights=best_weights,
        series=best_series,
        warmup_bars=warmup_bars,
        passed=bool(best_p < alpha),
    )
