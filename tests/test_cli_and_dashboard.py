"""Integration tests for QuantLab CLI subcommands and the 4-Quadrant Diagnostic Dashboard."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
from typer.testing import CliRunner

from quantlab.cli import app
from quantlab.dashboard.app import (
    build_dashboard_bundle,
    build_lightweight_charts_canvas_html,
    run_dashboard_self_check,
)
from quantlab.data.loader import OHLCVDataset, generate_synthetic_ohlcv
from quantlab.indicators.registry import get_registry
from quantlab.proofs.stats_gate import run_proof_suite

runner = CliRunner()


def test_cli_indicators_and_fetch() -> None:
    res_ind = runner.invoke(app, ["indicators", "--category", "all"])
    assert res_ind.exit_code == 0
    assert "KalmanFilter" in res_ind.stdout
    assert "PhaseSpaceEnergy" in res_ind.stdout
    assert "EntropyFlow" in res_ind.stdout
    assert "KAMA" in res_ind.stdout

    res_fetch = runner.invoke(
        app,
        ["fetch", "--provider", "synthetic", "--symbol", "SYNTH:COUPLED_OU", "--bars", "250", "--fracdiff"],
    )
    assert res_fetch.exit_code == 0
    assert "SYNTH:COUPLED_OU" in res_fetch.stdout
    assert "Stationarity Gate" in res_fetch.stdout


def test_cli_evaluate_and_prove_json_export(tmp_path: Path) -> None:
    json_file = tmp_path / "scorecard.json"
    res_eval = runner.invoke(
        app,
        [
            "evaluate",
            "--indicator",
            "KalmanFilter",
            "--bars",
            "350",
            "--surrogates",
            "15",
            "--json-out",
            str(json_file),
        ],
    )
    assert res_eval.exit_code == 0
    assert json_file.exists()
    assert "KalmanFilter" in res_eval.stdout

    res_prove = runner.invoke(
        app,
        ["prove", "--indicator", "RSI", "--bars", "300", "--surrogates", "15"],
    )
    assert res_prove.exit_code == 0
    assert "RSI" in res_prove.stdout


def test_cli_transpile_indicator_and_custom_expr(tmp_path: Path) -> None:
    pine_file = tmp_path / "entropy.pine"
    card_file = tmp_path / "entropy_card.md"

    res_tr = runner.invoke(
        app,
        [
            "transpile",
            "--indicator",
            "EntropyFlow",
            "--bars",
            "300",
            "--out-pine",
            str(pine_file),
            "--out-card",
            str(card_file),
        ],
    )
    assert res_tr.exit_code == 0
    assert pine_file.exists()
    assert card_file.exists()
    assert "//@version=6" in pine_file.read_text(encoding="utf-8")
    assert "f_rolling_entropy" in pine_file.read_text(encoding="utf-8")
    assert "QuantLab Research Card" in card_file.read_text(encoding="utf-8")

    res_custom = runner.invoke(
        app,
        ["transpile", "--expr", "(close - SMA(close, 14)) / Max(Stdev(close, 14), 1e-8)"],
    )
    assert res_custom.exit_code == 0
    assert "ta.sma(close, 14)" in res_custom.stdout


def test_cli_dashboard_check_and_4_quadrant_bundle() -> None:
    res_dash = runner.invoke(app, ["dashboard", "--check"])
    assert res_dash.exit_code == 0
    assert '"status": "ok"' in res_dash.stdout

    check_dict = run_dashboard_self_check()
    assert check_dict["status"] == "ok"
    assert check_dict["indicators_evaluated"] == 8

    bundle = build_dashboard_bundle(
        symbol="SYNTH:COUPLED_OU",
        provider="synthetic",
        bars=250,
        indicator_name="PhaseSpaceEnergy",
        custom_expr="(close - EMA(close, window)) / Max(Stdev(close, window), 1e-8)",
        n_surrogates=12,
        seed=42,
    )
    assert "LightweightCharts.createChart" in bundle.lightweight_charts_html
    assert len(bundle.fig_q1_ohlcv.data) >= 2
    assert len(bundle.fig_q1_phase_space.data) == 1
    assert len(bundle.fig_q2_rolling_entropy.data) == 2
    assert len(bundle.fig_q2_surrogates.data) == 1
    assert len(bundle.fig_q3_ic_vif.data) == 2
    assert len(bundle.fig_q3_wasserstein.data) == 2
    assert len(bundle.fig_q3_pareto_bode.data) >= 8
    assert bundle.transpilation.pine_code.startswith("//@version=6")


def test_lightweight_charts_canvas_yfinance_ms_timestamps_and_intraday() -> None:
    # Simulate yfinance DatetimeIndex with millisecond resolution (datetime64[ms, UTC])
    df_ms = generate_synthetic_ohlcv(symbol="SPY", timeframe="1d", bars=120, seed=42)
    df_ms.index = df_ms.index.as_unit("ms")
    ds_yf = OHLCVDataset(symbol="SPY", provider="yfinance", timeframe="1d", df=df_ms)

    reg = get_registry()
    kalman_spec = reg.get("KalmanFilter")
    proof = run_proof_suite(kalman_spec, ds_yf, n_surrogates=10, seed=42)

    html = build_lightweight_charts_canvas_html(ds_yf, proof, overlay=kalman_spec.overlay)
    assert "autoSize: true" in html

    m_candles = re.search(r"candleSeries\.setData\((\[.*?\])\);", html)
    m_ind = re.search(r"indSeries\.setData\((\[.*?\])\);", html)
    assert m_candles is not None and m_ind is not None

    candles = json.loads(m_candles.group(1))
    ind_points = json.loads(m_ind.group(1))
    assert len(candles) == 120
    assert len(ind_points) == 120

    candle_times = [c["time"] for c in candles]
    ind_times = [p["time"] for p in ind_points]
    assert candle_times == ind_times
    assert len(set(candle_times)) == 120
    assert all(b > a for a, b in zip(candle_times, candle_times[1:], strict=False))
    assert candle_times[0] > 1_700_000_000

    # Also verify intraday 15m timeframe produces strictly increasing unique timestamps
    df_15m = generate_synthetic_ohlcv(symbol="SPY", timeframe="15m", bars=80, seed=42)
    df_15m.index = df_15m.index.as_unit("ms")
    ds_15m = OHLCVDataset(symbol="SPY", provider="yfinance", timeframe="15m", df=df_15m)
    html_15m = build_lightweight_charts_canvas_html(ds_15m, proof, overlay=True)
    m_c15 = re.search(r"candleSeries\.setData\((\[.*?\])\);", html_15m)
    assert m_c15 is not None
    candles_15m = json.loads(m_c15.group(1))
    times_15m = [c["time"] for c in candles_15m]
    assert len(set(times_15m)) == 80
    assert np.all(np.diff(times_15m) == 900)
