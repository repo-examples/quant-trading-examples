"""Integration tests for QuantLab CLI subcommands and the 4-Quadrant Diagnostic Dashboard."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from quantlab.cli import app
from quantlab.dashboard.app import build_dashboard_bundle, run_dashboard_self_check

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
