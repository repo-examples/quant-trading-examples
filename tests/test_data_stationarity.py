"""Unit and Causal Zero-Lookahead tests for QuantLab Data Loader and Fractional Stationarity."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from quantlab.data.loader import (
    UI_TIMEFRAMES,
    InsufficientHistoryError,
    OHLCVDataset,
    _clean_provider_ohlcv,
    _fetch_ccxt,
    _fetch_yfinance,
    extract_calendar_dates,
    extract_unix_timestamps,
    fetch_ohlcv,
    generate_synthetic_ohlcv,
    get_timeframe_spec,
    normalize_timeframe,
    resample_ohlcv_causal,
    validate_minimum_proof_bars,
)
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
    assert ds.canonical_timeframe == "1D"
    assert ds.cache_path is not None and ds.cache_path.exists()
    assert ds.df.index.is_monotonic_increasing
    assert not ds.df.index.has_duplicates
    assert "driver_signal" in ds.df.columns

    # Reload from Parquet cache
    ds_cached = fetch_ohlcv(
        symbol="SYNTH:COUPLED_OU",
        provider="synthetic",
        timeframe="1D",
        bars=500,
        seed=42,
        cache_dir=tmp_path,
        use_cache=True,
    )
    np.testing.assert_allclose(
        ds.df["close"].to_numpy(), ds_cached.df["close"].to_numpy(), rtol=0, atol=1e-12
    )


def test_timeframe_normalization_and_1m_vs_1M_disambiguation() -> None:
    assert normalize_timeframe("1m") == "1m"
    assert normalize_timeframe("1min") == "1m"
    assert normalize_timeframe("1M") == "1M"
    assert normalize_timeframe("1mo") == "1M"
    assert normalize_timeframe("1MO") == "1M"
    assert normalize_timeframe("1d") == "1D"
    assert normalize_timeframe("1D") == "1D"
    assert normalize_timeframe("1w") == "1W"
    assert normalize_timeframe("1wk") == "1W"
    assert normalize_timeframe("1W") == "1W"
    assert normalize_timeframe("3m") == "3M"
    assert normalize_timeframe("3mo") == "3M"
    assert normalize_timeframe("3M") == "3M"
    assert normalize_timeframe("4h") == "4h"
    assert normalize_timeframe("1h") == "1h"
    assert normalize_timeframe("15m") == "15m"

    assert get_timeframe_spec("1M").yf_interval == "1mo"
    assert get_timeframe_spec("1M").yf_period == "max"
    assert get_timeframe_spec("1m").yf_interval == "1m"
    assert get_timeframe_spec("3M").yf_interval == "3mo"
    assert get_timeframe_spec("1W").yf_interval == "1wk"

    with pytest.raises(ValueError, match="Unsupported timeframe"):
        normalize_timeframe("2y")


def test_all_ui_timeframes_synthetic_generation() -> None:
    for tf in UI_TIMEFRAMES:
        df = generate_synthetic_ohlcv(timeframe=tf, bars=60, seed=11)
        assert len(df) == 60
        assert df.index.is_monotonic_increasing
        assert not df.index.has_duplicates


def test_multiindex_flattening_and_timestamp_units_extraction() -> None:
    # Simulate yfinance MultiIndex (Price, Ticker) with datetime64[s, America/New_York]
    base_idx = pd.date_range("2025-05-01", periods=5, freq="1D", tz="Europe/Berlin").as_unit("s")
    multi_cols = pd.MultiIndex.from_product([["Open", "High", "Low", "Close", "Volume"], ["SAP.DE"]])
    raw = pd.DataFrame(
        [
            [100.0, 102.0, 99.0, 101.0, 10000.0],
            [101.0, 103.0, 100.0, 102.5, 12000.0],
            [102.5, 104.0, 101.0, 103.0, 11000.0],
            [103.0, 105.0, 102.0, 104.0, 13000.0],
            [104.0, 106.0, 103.0, 105.5, 14000.0],
        ],
        index=base_idx,
        columns=multi_cols,
    )
    cleaned = _clean_provider_ohlcv(raw, is_calendar_date=True)
    assert list(cleaned.columns) == ["open", "high", "low", "close", "volume"]
    dates = extract_calendar_dates(cleaned.index)
    assert dates == ["2025-05-01", "2025-05-02", "2025-05-03", "2025-05-04", "2025-05-05"]

    # Verify unix timestamp extraction is identical across s, ms, us, ns units (never collapsing to 1)
    intraday_ns = pd.date_range("2025-05-01 09:30:00", periods=4, freq="1h", tz="UTC").as_unit("ns")
    ts_ns = extract_unix_timestamps(intraday_ns)
    for unit in ("s", "ms", "us"):
        ts_unit = extract_unix_timestamps(intraday_ns.as_unit(unit))
        np.testing.assert_array_equal(ts_ns, ts_unit)
    assert ts_ns[0] > 1_700_000_000
    assert np.all(np.diff(ts_ns) == 3600)


def test_causal_resampling_pit_zero_lookahead_and_provider_mocks(monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. Verify causal PIT zero-lookahead invariance on quarterly resampling
    daily_df = generate_synthetic_ohlcv(timeframe="1D", bars=220, seed=21)
    q_orig = resample_ohlcv_causal(daily_df, "QS")
    assert len(q_orig) >= 2

    # Mutate all bars in the final quarter bucket drastically and verify prior quarters are unchanged
    last_q_start = q_orig.index[-1]
    mutated_daily = daily_df.copy()
    future_mask = mutated_daily.index >= last_q_start
    mutated_daily.loc[future_mask, ["open", "high", "low", "close"]] *= 50.0
    q_mutated = resample_ohlcv_causal(mutated_daily, "QS")

    np.testing.assert_allclose(
        q_orig.iloc[:-1][["open", "high", "low", "close", "volume"]].to_numpy(),
        q_mutated.iloc[:-1][["open", "high", "low", "close", "volume"]].to_numpy(),
        rtol=0.0,
        atol=1e-12,
    )

    # 2. Mock yfinance for 3M (period="max", interval="3mo", clamped history) and 4h resampling
    recorded_calls: list[tuple[str, str]] = []

    class FakeTicker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        def history(self, period: str, interval: str, auto_adjust: bool = True) -> pd.DataFrame:
            _ = auto_adjust
            recorded_calls.append((period, interval))
            if interval == "3mo":
                idx = pd.date_range("1993-03-01", periods=132, freq="QS", tz="America/New_York").as_unit("s")
            else:
                idx = pd.date_range("2025-01-01", periods=200, freq="1h", tz="UTC").as_unit("s")
            cols = pd.MultiIndex.from_product([["Open", "High", "Low", "Close", "Volume"], [self.symbol]])
            vals = np.column_stack(
                [
                    np.linspace(100.0, 200.0, len(idx)),
                    np.linspace(102.0, 203.0, len(idx)),
                    np.linspace(98.0, 198.0, len(idx)),
                    np.linspace(101.0, 201.0, len(idx)),
                    np.full(len(idx), 500_000.0),
                ]
            )
            return pd.DataFrame(vals, index=idx, columns=cols)

    fake_yf = types.ModuleType("yfinance")
    fake_yf.Ticker = FakeTicker  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)

    df_3m, res_src_3m = _fetch_yfinance("SPY", "3M", bars=600)
    assert ("max", "3mo") in recorded_calls
    assert len(df_3m) == 132
    assert res_src_3m is None

    ds_clamped = OHLCVDataset(
        symbol="SPY",
        provider="yfinance",
        timeframe="3M",
        df=df_3m,
        requested_bars=600,
        resampled_from=res_src_3m,
    )
    assert ds_clamped.is_clamped is True

    df_4h, res_src_4h = _fetch_yfinance("SPY", "4h", bars=600)
    assert ("730d", "1h") in recorded_calls
    assert res_src_4h == "1h"
    assert len(df_4h) == 50

    # 3. Mock ccxt for 3M causal resampling from daily candles
    class FakeBinance:
        timeframes = {"15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d", "1w": "1w", "1M": "1M"}

        def __init__(self, config: dict[str, object]) -> None:
            self.config = config

        def fetch_ohlcv(self, symbol: str, timeframe: str = "1d", limit: int = 500) -> list[list[float]]:
            _ = symbol
            assert timeframe == "1d"
            n = min(limit, 500)
            idx = pd.date_range("2024-01-01", periods=n, freq="1D", tz="UTC")
            ms = (extract_unix_timestamps(idx) * 1000).tolist()
            return [[float(t), 40000.0, 41000.0, 39500.0, 40500.0, 1200.0] for t in ms]

    fake_ccxt = types.ModuleType("ccxt")
    fake_ccxt.binance = FakeBinance  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "ccxt", fake_ccxt)

    df_ccxt_3m, ccxt_res_src = _fetch_ccxt("BTC/USDT", "3M", bars=120)
    assert ccxt_res_src == "1D"
    assert len(df_ccxt_3m) >= 5


def test_minimum_proof_bars_guard_raises_insufficient_history() -> None:
    short_df = generate_synthetic_ohlcv(timeframe="3M", bars=32, seed=9)
    ds_short = OHLCVDataset(symbol="NEWIPO", provider="yfinance", timeframe="3M", df=short_df, requested_bars=600)
    with pytest.raises(InsufficientHistoryError, match="minimum 35 required"):
        validate_minimum_proof_bars(ds_short)


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
