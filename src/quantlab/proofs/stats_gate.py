"""Statistical & Orthogonality Gates: Spearman Rank IC, Wasserstein Regime Distance, VIF & Proof Suite."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numba
import numpy as np
from scipy import stats

from quantlab.data.loader import OHLCVDataset
from quantlab.data.stationarity import StationarityResult, find_min_ffd_d
from quantlab.indicators.registry import IndicatorSpec, get_registry
from quantlab.proofs.dsp import DSPResult, evaluate_dsp_proof, identify_pareto_frontier
from quantlab.proofs.entropy import EntropyProofResult, SurrogateMethod, evaluate_entropy_proof


@dataclass(frozen=True)
class StatsGateResult:
    """Statistical predictive power, regime separation, and VIF orthogonality metrics."""

    ic_by_horizon: dict[int, float]
    ic_t_stat_by_horizon: dict[int, float]
    max_abs_ic: float
    best_horizon: int
    rolling_ic: np.ndarray
    wasserstein_regime_distance: float
    bull_regime_mean: float
    bear_regime_mean: float
    vif_score: float
    baseline_correlations: dict[str, float]
    ic_threshold: float
    vif_threshold: float
    ic_passed: bool
    vif_passed: bool
    passed: bool


@dataclass(frozen=True)
class ProofSuiteResult:
    """Complete mathematical proof scorecard for a single indicator."""

    indicator_name: str
    indicator_title: str
    category: str
    symbol: str
    raw_series: np.ndarray
    stationary_series: np.ndarray
    stationarity: StationarityResult
    entropy: EntropyProofResult
    stats_gate: StatsGateResult
    dsp: DSPResult
    overall_passed: bool


def _spearman_corr_and_tstat(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    mask = np.isfinite(x) & np.isfinite(y)
    xc = x[mask]
    yc = y[mask]
    n = len(xc)
    if n < 10 or np.std(xc) < 1e-14 or np.std(yc) < 1e-14:
        return 0.0, 0.0
    res = stats.spearmanr(xc, yc)
    rho = float(res.statistic) if np.isfinite(res.statistic) else 0.0
    denom = max(1.0 - rho * rho, 1e-12)
    t_stat = float(rho * np.sqrt(float(n - 2) / denom))
    return rho, t_stat


@numba.njit(cache=True)
def _rolling_rank_ic_kernel(x: np.ndarray, y: np.ndarray, window: int) -> np.ndarray:
    """Strictly causal rolling Spearman Rank Correlation over `window` bars."""
    n = len(x)
    out = np.zeros(n, dtype=np.float64)
    w = max(8, window)
    for t in range(w, n):
        # Use causal history ending at t-1 so forward return y[t-1] (known at t) is never leaked
        xs = x[t - w : t - 1]
        ys = y[t - w : t - 1]
        m = len(xs)
        if m < 6:
            continue
        # Check finite & non-constant
        valid = True
        for k in range(m):
            if np.isnan(xs[k]) or np.isnan(ys[k]):
                valid = False
                break
        if not valid:
            continue
        rx = np.argsort(np.argsort(xs)).astype(np.float64)
        ry = np.argsort(np.argsort(ys)).astype(np.float64)
        mx = np.mean(rx)
        my = np.mean(ry)
        num = 0.0
        dx2 = 0.0
        dy2 = 0.0
        for k in range(m):
            dx = rx[k] - mx
            dy = ry[k] - my
            num += dx * dy
            dx2 += dx * dx
            dy2 += dy * dy
        denom = np.sqrt(dx2 * dy2)
        if denom > 1e-12:
            out[t] = num / denom
    return out


def compute_rank_ic_profile(
    indicator_series: np.ndarray,
    dataset: OHLCVDataset,
    horizons: tuple[int, ...] = (1, 5, 10, 20),
    rolling_window: int = 64,
) -> tuple[dict[int, float], dict[int, float], np.ndarray]:
    """Compute multi-horizon Spearman Rank IC profile and causal rolling Rank IC."""
    ind = np.asarray(indicator_series, dtype=np.float64)
    ic_map: dict[int, float] = {}
    t_map: dict[int, float] = {}

    for h in horizons:
        fwd = dataset.forward_returns(horizon=h)
        rho, t_stat = _spearman_corr_and_tstat(ind, fwd)
        ic_map[int(h)] = rho
        t_map[int(h)] = t_stat

    fwd_1 = dataset.forward_returns(horizon=1)
    roll_ic = _rolling_rank_ic_kernel(ind, fwd_1, max(12, int(rolling_window)))
    return ic_map, t_map, roll_ic


def compute_wasserstein_regime_distance(
    indicator_series: np.ndarray,
    dataset: OHLCVDataset,
    vol_window: int = 20,
) -> tuple[float, float, float]:
    """Compute 1-Wasserstein Earth Mover's Distance between Bull and Bear regime distributions."""
    ind = np.asarray(indicator_series, dtype=np.float64)
    mask = np.isfinite(ind)
    if np.sum(mask) < 20 or np.std(ind[mask]) < 1e-14:
        return 0.0, 0.0, 0.0

    ind_z = np.zeros_like(ind)
    ind_z[mask] = (ind[mask] - np.mean(ind[mask])) / max(float(np.std(ind[mask])), 1e-12)

    if "regime" in dataset.df.columns:
        reg = dataset.df["regime"].to_numpy(dtype=np.float64)
        bull_mask = mask & (reg < 0.5)
        bear_mask = mask & (reg >= 0.5)
    else:
        ret = dataset.log_returns
        # Causal rolling return + volatility regime partition
        w = max(5, int(vol_window))
        roll_ret = np.convolve(ret, np.ones(w) / float(w), mode="full")[: len(ret)]
        med_ret = float(np.median(roll_ret))
        bull_mask = mask & (roll_ret >= med_ret)
        bear_mask = mask & (roll_ret < med_ret)

    bull_vals = ind_z[bull_mask]
    bear_vals = ind_z[bear_mask]
    if len(bull_vals) < 4 or len(bear_vals) < 4:
        return 0.0, 0.0, 0.0

    w1 = float(stats.wasserstein_distance(bull_vals, bear_vals))
    return w1, float(np.mean(bull_vals)), float(np.mean(bear_vals))


def _stationary_transform_for_orthogonality(series: np.ndarray, is_overlay: bool, close: np.ndarray) -> np.ndarray:
    """Normalize series so VIF measures signal collinearity rather than shared I(1) price level."""
    x = np.nan_to_num(np.asarray(series, dtype=np.float64), nan=0.0)
    if is_overlay:
        c = np.maximum(np.asarray(close, dtype=np.float64), 1e-12)
        rel = (c - x) / c
        return rel
    return x


def compute_vif_and_correlations(
    indicator_name: str,
    indicator_series: np.ndarray,
    dataset: OHLCVDataset,
    is_overlay: bool = False,
) -> tuple[float, dict[str, float]]:
    """Compute Variance Inflation Factor (VIF) and Spearman correlations against baseline indicators."""
    registry = get_registry()
    baselines = registry.list_all(category="baseline")
    close = dataset.df["close"].to_numpy(dtype=np.float64)

    target = _stationary_transform_for_orthogonality(indicator_series, is_overlay=is_overlay, close=close)
    t_std = float(np.std(target))
    if t_std < 1e-14:
        return 1.0, {b.name: 0.0 for b in baselines if b.name.lower() != indicator_name.lower()}

    target_z = (target - np.mean(target)) / t_std
    corrs: dict[str, float] = {}
    cols: list[np.ndarray] = []

    for base_spec in baselines:
        if base_spec.name.lower() == indicator_name.lower():
            continue
        b_raw = base_spec.evaluate(dataset.df)
        b_sig = _stationary_transform_for_orthogonality(b_raw, is_overlay=base_spec.overlay, close=close)
        b_std = float(np.std(b_sig))
        if b_std < 1e-14:
            corrs[base_spec.name] = 0.0
            continue
        b_z = (b_sig - np.mean(b_sig)) / b_std
        rho, _ = _spearman_corr_and_tstat(target_z, b_z)
        corrs[base_spec.name] = rho
        cols.append(b_z)

    if not cols:
        return 1.0, corrs

    x_mat = np.column_stack([np.ones(len(target_z), dtype=np.float64), *cols])
    coeffs, _, _, _ = np.linalg.lstsq(x_mat, target_z, rcond=None)
    y_hat = x_mat @ coeffs
    ss_res = float(np.sum((target_z - y_hat) ** 2))
    ss_tot = float(np.sum((target_z - np.mean(target_z)) ** 2))
    if ss_tot < 1e-14:
        return 1.0, corrs

    r_squared = float(np.clip(1.0 - (ss_res / ss_tot), 0.0, 0.999))
    vif = float(1.0 / (1.0 - r_squared))
    return vif, corrs


def evaluate_stats_gate(
    indicator_name: str,
    indicator_series: np.ndarray,
    dataset: OHLCVDataset,
    is_overlay: bool = False,
    ic_threshold: float = 0.02,
    vif_threshold: float = 5.0,
) -> StatsGateResult:
    """Run the Statistical & Orthogonality Proof Gate on an indicator series."""
    close = dataset.df["close"].to_numpy(dtype=np.float64)
    eval_series = _stationary_transform_for_orthogonality(indicator_series, is_overlay=is_overlay, close=close)

    ic_map, t_map, roll_ic = compute_rank_ic_profile(eval_series, dataset)
    best_h = max(ic_map.keys(), key=lambda h: abs(ic_map[h]))
    max_abs_ic = float(abs(ic_map[best_h]))

    w1, bull_mean, bear_mean = compute_wasserstein_regime_distance(eval_series, dataset)
    vif, corrs = compute_vif_and_correlations(
        indicator_name=indicator_name,
        indicator_series=indicator_series,
        dataset=dataset,
        is_overlay=is_overlay,
    )

    ic_passed = bool(max_abs_ic > ic_threshold)
    vif_passed = bool(vif < vif_threshold)
    return StatsGateResult(
        ic_by_horizon=ic_map,
        ic_t_stat_by_horizon=t_map,
        max_abs_ic=max_abs_ic,
        best_horizon=best_h,
        rolling_ic=roll_ic,
        wasserstein_regime_distance=w1,
        bull_regime_mean=bull_mean,
        bear_regime_mean=bear_mean,
        vif_score=vif,
        baseline_correlations=corrs,
        ic_threshold=ic_threshold,
        vif_threshold=vif_threshold,
        ic_passed=ic_passed,
        vif_passed=vif_passed,
        passed=bool(ic_passed and vif_passed),
    )


def run_proof_suite(
    spec: IndicatorSpec,
    dataset: OHLCVDataset,
    n_surrogates: int = 50,
    surrogate_method: SurrogateMethod = "iaaft",
    adf_alpha: float = 0.05,
    te_alpha: float = 0.05,
    ic_threshold: float = 0.02,
    vif_threshold: float = 5.0,
    seed: int = 42,
    surrogate_progress_callback: Callable[[int, int], None] | None = None,
) -> ProofSuiteResult:
    """Execute the complete Stationarity, Information-Theoretic, Statistical, and DSP Proof Suite."""
    raw_series = spec.evaluate(dataset.df)
    close = dataset.df["close"].to_numpy(dtype=np.float64)

    # For overlay indicators (like EMA/KAMA), evaluate stationarity on causal price-relative displacement
    # or fractional differentiation of the raw indicator series.
    stationarity = find_min_ffd_d(raw_series, alpha=adf_alpha)
    if spec.overlay:
        stat_signal = _stationary_transform_for_orthogonality(raw_series, is_overlay=True, close=close)
    else:
        stat_signal = stationarity.series

    fwd_1 = dataset.forward_returns(horizon=1)
    cur_1 = dataset.log_returns

    entropy_res = evaluate_entropy_proof(
        indicator_series=stat_signal,
        forward_returns=fwd_1,
        current_returns=cur_1,
        n_surrogates=n_surrogates,
        surrogate_method=surrogate_method,
        alpha=te_alpha,
        seed=seed,
        surrogate_progress_callback=surrogate_progress_callback,
    )

    stats_res = evaluate_stats_gate(
        indicator_name=spec.name,
        indicator_series=raw_series,
        dataset=dataset,
        is_overlay=spec.overlay,
        ic_threshold=ic_threshold,
        vif_threshold=vif_threshold,
    )

    dsp_res = evaluate_dsp_proof(
        indicator_series=raw_series,
        reference_series=close,
        pareto_optimal=True,
    )

    overall = bool(stationarity.passed and entropy_res.passed and stats_res.passed)
    return ProofSuiteResult(
        indicator_name=spec.name,
        indicator_title=spec.title,
        category=spec.category,
        symbol=dataset.symbol,
        raw_series=raw_series,
        stationary_series=stat_signal,
        stationarity=stationarity,
        entropy=entropy_res,
        stats_gate=stats_res,
        dsp=dsp_res,
        overall_passed=overall,
    )


def evaluate_multiple_indicators(
    specs: list[IndicatorSpec],
    dataset: OHLCVDataset,
    n_surrogates: int = 50,
    surrogate_method: SurrogateMethod = "iaaft",
    seed: int = 42,
    active_indicator_name: str | None = None,
    surrogate_progress_callback: Callable[[int, int], None] | None = None,
) -> list[ProofSuiteResult]:
    """Evaluate a collection of indicators and update their DSP Pareto-optimality status."""
    preliminary: list[ProofSuiteResult] = [
        run_proof_suite(
            spec=s,
            dataset=dataset,
            n_surrogates=n_surrogates,
            surrogate_method=surrogate_method,
            seed=seed,
            surrogate_progress_callback=(
                surrogate_progress_callback
                if active_indicator_name is not None and s.name.lower() == active_indicator_name.lower()
                else None
            ),
        )
        for s in specs
    ]
    frontier_map = identify_pareto_frontier(
        {r.indicator_name: (r.dsp.mean_phase_lag_bars, r.dsp.jerk_energy) for r in preliminary}
    )
    final_results: list[ProofSuiteResult] = []
    for r in preliminary:
        is_pareto = frontier_map.get(r.indicator_name, True)
        updated_dsp = DSPResult(
            instantaneous_amplitude=r.dsp.instantaneous_amplitude,
            instantaneous_phase=r.dsp.instantaneous_phase,
            instantaneous_frequency=r.dsp.instantaneous_frequency,
            mean_phase_lag_rad=r.dsp.mean_phase_lag_rad,
            mean_phase_lag_bars=r.dsp.mean_phase_lag_bars,
            jerk_energy=r.dsp.jerk_energy,
            bode_frequencies=r.dsp.bode_frequencies,
            bode_magnitude_db=r.dsp.bode_magnitude_db,
            bode_phase_deg=r.dsp.bode_phase_deg,
            pareto_optimal=is_pareto,
        )
        final_results.append(
            ProofSuiteResult(
                indicator_name=r.indicator_name,
                indicator_title=r.indicator_title,
                category=r.category,
                symbol=r.symbol,
                raw_series=r.raw_series,
                stationary_series=r.stationary_series,
                stationarity=r.stationarity,
                entropy=r.entropy,
                stats_gate=r.stats_gate,
                dsp=updated_dsp,
                overall_passed=r.overall_passed,
            )
        )
    return final_results
