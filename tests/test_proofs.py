"""Unit and Ground-Truth Causal Verification tests for Entropy, Stats Gate, and DSP Proofs."""

from __future__ import annotations

import numpy as np

from quantlab.data.loader import fetch_ohlcv
from quantlab.indicators.registry import get_registry
from quantlab.proofs.dsp import evaluate_dsp_proof, identify_pareto_frontier
from quantlab.proofs.entropy import (
    evaluate_entropy_proof,
    mutual_information_ksg,
    permutation_entropy,
    shannon_entropy,
)
from quantlab.proofs.stats_gate import (
    compute_vif_and_correlations,
    evaluate_multiple_indicators,
    run_proof_suite,
)


def test_entropy_and_causal_transfer_entropy_ground_truth() -> None:
    ds_coupled = fetch_ohlcv(symbol="SYNTH:COUPLED_OU", provider="synthetic", bars=800, seed=42, use_cache=False)
    driver = ds_coupled.df["driver_signal"].to_numpy(dtype=np.float64)
    fwd_ret = ds_coupled.forward_returns(horizon=1)
    cur_ret = ds_coupled.log_returns

    h_s = shannon_entropy(driver)
    h_p = permutation_entropy(driver)
    mi = mutual_information_ksg(driver[:-1], fwd_ret[:-1])
    assert h_s > 0.5
    assert 0.0 < h_p <= 1.0
    assert mi > 0.01

    proof_coupled = evaluate_entropy_proof(
        indicator_series=driver,
        forward_returns=fwd_ret,
        current_returns=cur_ret,
        n_surrogates=40,
        surrogate_method="iaaft",
        seed=42,
    )
    assert proof_coupled.symbolic_te > 0.0
    assert proof_coupled.p_value < 0.05
    assert proof_coupled.passed

    # Null control: uncoupled white noise must NOT pass surrogate gate
    rng = np.random.default_rng(999)
    pure_noise = rng.standard_normal(len(fwd_ret))
    proof_noise = evaluate_entropy_proof(
        indicator_series=pure_noise,
        forward_returns=fwd_ret,
        current_returns=cur_ret,
        n_surrogates=40,
        surrogate_method="block_shuffle",
        seed=999,
    )
    assert proof_noise.p_value > 0.05
    assert not proof_noise.passed


def test_dsp_proof_and_pareto_frontier() -> None:
    t = np.linspace(0.0, 20.0 * np.pi, 500)
    ref = np.sin(t)
    # Low-lag smooth signal vs high-lag noisy signal
    fast_clean = np.sin(t - 0.15)
    slow_noisy = np.sin(t - 1.1) + 0.5 * np.cos(17.0 * t)

    dsp_fast = evaluate_dsp_proof(fast_clean, ref)
    dsp_slow = evaluate_dsp_proof(slow_noisy, ref)

    assert dsp_fast.jerk_energy < dsp_slow.jerk_energy
    assert len(dsp_fast.bode_frequencies) > 0

    frontier = identify_pareto_frontier(
        {
            "fast_clean": (dsp_fast.mean_phase_lag_bars, dsp_fast.jerk_energy),
            "slow_noisy": (dsp_slow.mean_phase_lag_bars, dsp_slow.jerk_energy),
        }
    )
    assert frontier["fast_clean"] is True
    assert frontier["slow_noisy"] is False


def test_run_proof_suite_and_multi_indicator_evaluation() -> None:
    ds = fetch_ohlcv(symbol="SYNTH:COUPLED_OU", provider="synthetic", bars=600, seed=42, use_cache=False)
    reg = get_registry()
    kalman = reg.get("KalmanFilter")

    res = run_proof_suite(spec=kalman, dataset=ds, n_surrogates=30, seed=42)
    assert res.stationarity.passed
    assert res.stats_gate.max_abs_ic > 0.02
    assert res.stats_gate.wasserstein_regime_distance > 0.0
    assert res.stats_gate.vif_score >= 1.0

    subset = [reg.get("RSI"), reg.get("EMA"), reg.get("KalmanFilter"), reg.get("EntropyFlow")]
    multi = evaluate_multiple_indicators(subset, ds, n_surrogates=20, seed=42)
    assert len(multi) == 4
    assert any(r.dsp.pareto_optimal for r in multi)


def test_collinear_vif_capped_without_linalg_error() -> None:
    ds = fetch_ohlcv(symbol="SYNTH:COUPLED_OU", provider="synthetic", bars=300, seed=42, use_cache=False)
    reg = get_registry()
    rsi_series = reg.get("RSI").evaluate(ds.df)
    # Pass a perfectly collinear clone under a non-baseline name
    vif, corrs = compute_vif_and_correlations(
        indicator_name="CollinearRSIClone",
        indicator_series=2.5 * rsi_series + 10.0,
        dataset=ds,
        is_overlay=False,
    )
    assert np.isfinite(vif)
    assert vif <= 1000.0 + 1e-6
    assert vif > 100.0
    assert abs(corrs["RSI"] - 1.0) < 1e-6
