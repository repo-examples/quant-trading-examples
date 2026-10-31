"""Unit and Causal Zero-Lookahead tests for QuantLab Data Loader and Fractional Stationarity."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantlab.data.loader import OHLCVDataset, fetch_ohlcv, generate_synthetic_ohlcv
from quantlab.data.stationarity import adf_test, compute_ffd_weights, find_min_ffd_d, frac_diff_ffd


def test_synthetic_ohlcv_pit_invariants_and_parquet_cache(tmp_path: Path) -> None:
    ds = fetch_ohlcv(
        symbol="SYNTH:COUPLED_OU",
        provider="synthetic",
        timeframe="1d",
        bars=500,
        seed=42,
        cache_dir=tmp_path,
    )
    assert ds.n_bars == 500
    assert ds.cache_path is not None and ds.cache_path.exists()
    assert ds.df.index.is_monotonic_increasing
    assert not ds.df.index.has_duplicates
    assert "driver_signal" in ds.df.columns

    # Reload from Parquet cache
    ds_cached = fetch_ohlcv(
        symbol="SYNTH:COUPLED_OU",
        provider="synthetic",
        timeframe="1d",
        bars=500,
        seed=42,
        cache_dir=tmp_path,
        use_cache=True,
    )
    np.testing.assert_allclose(ds.df["close"].to_numpy(), ds_cached.df["close"].to_numpy(), rtol=0, atol=1e-12)


def test_pit_validation_rejects_non_monotonic_or_invalid_bars() -> None:
    df = generate_synthetic_ohlcv(bars=64, seed=7)
    # Reverse timestamps to violate monotonic PIT ordering
    bad_df = df.iloc[::-1].copy()
    with pytest.raises(ValueError, match="monotonic"):
        OHLCVDataset(symbol="TEST", provider="synthetic", timeframe="1d", df=bad_df)

    # Corrupt high < close
    bad_hl = df.copy()
    bad_hl.iloc[10, bad_hl.columns.get_loc("high")] = bad_hl.iloc[10]["low"] - 5.0
    with pytest.raises(ValueError, match="high < max"):
        OHLCVDataset(symbol="TEST", provider="synthetic", timeframe="1d", df=bad_hl)


def test_ffd_weights_and_zero_lookahead_invariance() -> None:
    w0 = compute_ffd_weights(d=0.0)
    np.testing.assert_allclose(w0, np.array([1.0]))

    w1 = compute_ffd_weights(d=1.0, threshold=1e-6)
    np.testing.assert_allclose(w1, np.array([1.0, -1.0]))

    df = generate_synthetic_ohlcv(bars=400, seed=101)
    log_p = np.log(df["close"].to_numpy(dtype=np.float64))

    full_ffd, _ = frac_diff_ffd(log_p, d=0.45, threshold=1e-4)
    cutoff = 250
    # Mutate future bars [cutoff:] drastically and verify zero change on [0:cutoff]
    mutated = log_p.copy()
    mutated[cutoff:] = mutated[cutoff:] * 10.0 + 500.0
    mutated_ffd, _ = frac_diff_ffd(mutated, d=0.45, threshold=1e-4)
    prefix_ffd, _ = frac_diff_ffd(log_p[:cutoff], d=0.45, threshold=1e-4)

    assert np.max(np.abs(full_ffd[:cutoff] - mutated_ffd[:cutoff])) < 1e-12
    assert np.max(np.abs(full_ffd[:cutoff] - prefix_ffd)) < 1e-12


def test_adf_and_find_min_ffd_d_stationarity() -> None:
    rng = np.random.default_rng(1234)
    # Random walk is non-stationary
    rw = np.cumsum(rng.standard_normal(600)) + 100.0
    _, p_rw, _ = adf_test(rw)
    assert p_rw > 0.05

    # Stationary white noise passes ADF
    wn = rng.standard_normal(600)
    _, p_wn, _ = adf_test(wn)
    assert p_wn < 0.01

    # Optimal FFD order d* achieves stationarity while preserving memory correlation
    res = find_min_ffd_d(rw, alpha=0.05, threshold=1e-4)
    assert res.passed
    assert res.p_value < 0.05
    assert 0.0 < res.d_optimal <= 1.0
    assert res.memory_correlation > 0.30


def test_short_series_validation_errors() -> None:
    with pytest.raises(ValueError, match="Minimum bars required is 32"):
        generate_synthetic_ohlcv(bars=16)

    with pytest.raises(ValueError, match="length >= 8"):
        frac_diff_ffd(np.ones(4), d=0.5)

    with pytest.raises(ValueError, match="at least 16"):
        adf_test(np.ones(10))

    with pytest.raises(ValueError, match="length >= 32"):
        find_min_ffd_d(np.ones(20))
