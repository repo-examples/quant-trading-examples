"""QuantLab Typer + Rich Command-Line Interface."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from quantlab.dashboard.app import run_dashboard_self_check
from quantlab.data.loader import DataProvider, fetch_ohlcv
from quantlab.data.stationarity import find_min_ffd_d
from quantlab.indicators.registry import get_registry
from quantlab.proofs.entropy import SurrogateMethod
from quantlab.proofs.stats_gate import (
    ProofSuiteResult,
    evaluate_multiple_indicators,
    run_proof_suite,
)
from quantlab.transpiler.pine_v6 import transpile_to_pine_v6

app = typer.Typer(
    name="quantlab",
    help="Information-Theoretic Technical Indicator Research CLI & SymPy-to-Pine Script v6 Transpiler.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


def _badge(passed: bool) -> str:
    return "[bold green]PASS[/bold green]" if passed else "[bold red]FAIL[/bold red]"


@app.command("fetch")
def cmd_fetch(
    symbol: str = typer.Option("SYNTH:COUPLED_OU", "--symbol", "-s", help="Ticker or synthetic stochastic process"),
    provider: str = typer.Option("synthetic", "--provider", "-p", help="Data provider: synthetic | yfinance | ccxt"),
    timeframe: str = typer.Option("1D", "--timeframe", "-t", help="Bar timeframe (15m, 1h, 4h, 1D, 1W, 1M, 3M)"),
    bars: int = typer.Option(1000, "--bars", "-n", help="Number of historical PIT bars"),
    seed: int = typer.Option(42, "--seed", help="Random seed for deterministic synthetic processes"),
    fracdiff: bool = typer.Option(True, "--fracdiff/--no-fracdiff", help="Run FracDiff + ADF stationarity search"),
) -> None:
    """Fetch Point-in-Time (PIT) OHLCV market data, cache to Parquet, and verify stationarity."""
    prov: DataProvider = provider if provider in ("yfinance", "ccxt", "synthetic") else "synthetic"  # type: ignore[assignment]
    ds = fetch_ohlcv(symbol=symbol, provider=prov, timeframe=timeframe, bars=bars, seed=seed)

    table = Table(title=f"QuantLab PIT Dataset — {ds.symbol} ({ds.provider})", show_lines=True)
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    table.add_row("Symbol / Provider", f"{ds.symbol} ({ds.provider})")
    tf_bars_val = f"{ds.timeframe} / {ds.n_bars}"
    if ds.is_clamped and ds.requested_bars is not None:
        tf_bars_val += f" (clamped from {ds.requested_bars} requested)"
    if ds.resampled_from:
        tf_bars_val += f" [resampled from {ds.resampled_from}]"
    table.add_row("Timeframe / Bars", tf_bars_val)
    table.add_row("Start UTC", str(ds.df.index[0]))
    table.add_row("End UTC", str(ds.df.index[-1]))
    table.add_row("Close Range", f"[{ds.df['close'].min():.4f}, {ds.df['close'].max():.4f}]")
    table.add_row("Parquet Cache", str(ds.cache_path))

    if fracdiff:
        st_res = find_min_ffd_d(ds.log_close)
        table.add_row("Optimal FracDiff d*", f"{st_res.d_optimal:.4f} (window={len(st_res.weights)} bars)")
        table.add_row("ADF Stat / p-value", f"{st_res.adf_stat:.4f} / p={st_res.p_value:.4e}")
        table.add_row("Memory Correlation", f"{st_res.memory_correlation:.4f}")
        table.add_row("Stationarity Gate", _badge(st_res.passed))

    console.print(table)


@app.command("indicators")
def cmd_indicators(
    category: str = typer.Option("all", "--category", "-c", help="Filter by category: all | baseline | physics"),
) -> None:
    """List all registered dual neuro-symbolic indicators and their SymPy AST expressions."""
    reg = get_registry()
    cat_filter = category.lower()
    if cat_filter not in ("all", "baseline", "physics", "custom"):
        raise typer.BadParameter("Category must be one of: all, baseline, physics")

    specs = reg.list_all(category=cat_filter)  # type: ignore[arg-type]
    table = Table(title="QuantLab Neuro-Symbolic Indicator Registry", show_lines=True)
    table.add_column("Name", style="bold cyan", no_wrap=True)
    table.add_column("Category", style="magenta", no_wrap=True)
    table.add_column("Overlay", justify="center")
    table.add_column("Default Params", style="yellow")
    table.add_column("Canonical SymPy AST", style="white")

    for spec in specs:
        ast_str = str(spec.symbolic_ast())
        rec_count = len(spec.state_recurrences())
        if rec_count > 0:
            ast_str += f" [+{rec_count} state recurrence(s)]"
        table.add_row(
            spec.name,
            spec.category,
            "Yes" if spec.overlay else "No",
            json.dumps(spec.default_params),
            ast_str,
        )
    console.print(table)


def _render_proof_results(results: list[ProofSuiteResult]) -> None:
    table = Table(title="QuantLab Information-Theoretic, Statistical & DSP Proof Scorecard", show_lines=True)
    table.add_column("Indicator", style="bold cyan", no_wrap=True)
    table.add_column("Cat", style="magenta")
    table.add_column("Stationarity\n(d* / ADF p)", justify="center")
    table.add_column("Transfer Entropy\n(TE / Surr p)", justify="center")
    table.add_column("Predictive IC\n(Max |IC| @ h)", justify="center")
    table.add_column("Regime W1", justify="right")
    table.add_column("Ortho VIF", justify="center")
    table.add_column("DSP Lag / Jerk", justify="center")
    table.add_column("Gate", justify="center")

    for r in results:
        st = r.stationarity
        en = r.entropy
        sg = r.stats_gate
        dp = r.dsp
        pareto_tag = "[bold cyan]PARETO[/bold cyan]" if dp.pareto_optimal else "[dim]DOM[/dim]"
        table.add_row(
            r.indicator_name,
            r.category,
            f"d*={st.d_optimal:.2f}\np={st.p_value:.3f} {_badge(st.passed)}",
            f"TE={en.symbolic_te:.4f}\np={en.p_value:.3f} {_badge(en.passed)}",
            f"|IC|={sg.max_abs_ic:.4f} (h={sg.best_horizon})\n{_badge(sg.ic_passed)}",
            f"{sg.wasserstein_regime_distance:.4f}",
            f"VIF={sg.vif_score:.2f}\n{_badge(sg.vif_passed)}",
            f"Lag={dp.mean_phase_lag_bars:.2f}b | J={dp.jerk_energy:.3f}\n{pareto_tag}",
            _badge(r.overall_passed),
        )
    console.print(table)


@app.command("evaluate")
def cmd_evaluate(
    indicator: str = typer.Option("all", "--indicator", "-i", help="Indicator name or 'all'"),
    symbol: str = typer.Option("SYNTH:COUPLED_OU", "--symbol", "-s", help="Symbol or synthetic process"),
    provider: str = typer.Option("synthetic", "--provider", "-p", help="Data provider: synthetic | yfinance | ccxt"),
    timeframe: str = typer.Option("1D", "--timeframe", "-t", help="Timeframe (15m, 1h, 4h, 1D, 1W, 1M, 3M)"),
    bars: int = typer.Option(1000, "--bars", "-n", help="Number of historical bars"),
    surrogates: int = typer.Option(50, "--surrogates", "-m", help="Number of Monte Carlo surrogates"),
    surrogate_method: str = typer.Option("iaaft", "--surrogate-method", help="Null generator: iaaft | block_shuffle"),
    seed: int = typer.Option(42, "--seed", help="Random seed"),
    json_out: Path | None = typer.Option(None, "--json-out", help="Optional path to export JSON scorecard"),
) -> None:
    """Run the Stationarity, Transfer Entropy Surrogate, Rank IC, VIF, and DSP Proof Suite."""
    prov: DataProvider = provider if provider in ("yfinance", "ccxt", "synthetic") else "synthetic"  # type: ignore[assignment]
    s_method: SurrogateMethod = "block_shuffle" if surrogate_method == "block_shuffle" else "iaaft"

    ds = fetch_ohlcv(symbol=symbol, provider=prov, timeframe=timeframe, bars=bars, seed=seed)
    reg = get_registry()

    if indicator.lower() == "all":
        specs = reg.list_all()
        results = evaluate_multiple_indicators(
            specs=specs,
            dataset=ds,
            n_surrogates=surrogates,
            surrogate_method=s_method,
            seed=seed,
        )
    else:
        spec = reg.get(indicator)
        results = [
            run_proof_suite(
                spec=spec,
                dataset=ds,
                n_surrogates=surrogates,
                surrogate_method=s_method,
                seed=seed,
            )
        ]

    _render_proof_results(results)

    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "indicator": r.indicator_name,
                "category": r.category,
                "symbol": r.symbol,
                "timeframe": ds.timeframe,
                "bars": ds.n_bars,
                "overall_passed": r.overall_passed,
                "stationarity": {
                    "d_optimal": r.stationarity.d_optimal,
                    "adf_stat": r.stationarity.adf_stat,
                    "p_value": r.stationarity.p_value,
                    "memory_correlation": r.stationarity.memory_correlation,
                    "passed": r.stationarity.passed,
                },
                "entropy": {
                    "shannon_entropy": r.entropy.shannon_entropy,
                    "permutation_entropy": r.entropy.permutation_entropy,
                    "mutual_information": r.entropy.mutual_information,
                    "symbolic_te": r.entropy.symbolic_te,
                    "knn_te": r.entropy.knn_te,
                    "z_score": r.entropy.z_score,
                    "p_value": r.entropy.p_value,
                    "passed": r.entropy.passed,
                },
                "stats_gate": {
                    "max_abs_ic": r.stats_gate.max_abs_ic,
                    "best_horizon": r.stats_gate.best_horizon,
                    "wasserstein_regime_distance": r.stats_gate.wasserstein_regime_distance,
                    "vif_score": r.stats_gate.vif_score,
                    "passed": r.stats_gate.passed,
                },
                "dsp": {
                    "mean_phase_lag_bars": r.dsp.mean_phase_lag_bars,
                    "jerk_energy": r.dsp.jerk_energy,
                    "pareto_optimal": r.dsp.pareto_optimal,
                },
            }
            for r in results
        ]
        json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        console.print(f"[green]Saved JSON scorecard to {json_out}[/green]")


@app.command("prove")
def cmd_prove(
    indicator: str = typer.Option("all", "--indicator", "-i", help="Indicator name or 'all'"),
    symbol: str = typer.Option("SYNTH:COUPLED_OU", "--symbol", "-s", help="Symbol or synthetic process"),
    provider: str = typer.Option("synthetic", "--provider", "-p", help="Data provider"),
    timeframe: str = typer.Option("1D", "--timeframe", "-t", help="Timeframe (15m, 1h, 4h, 1D, 1W, 1M, 3M)"),
    bars: int = typer.Option(1000, "--bars", "-n", help="Number of historical bars"),
    surrogates: int = typer.Option(50, "--surrogates", "-m", help="Number of Monte Carlo surrogates"),
    seed: int = typer.Option(42, "--seed", help="Random seed"),
) -> None:
    """Alias for `quantlab evaluate`: run the mathematical proof suite."""
    cmd_evaluate(
        indicator=indicator,
        symbol=symbol,
        provider=provider,
        timeframe=timeframe,
        bars=bars,
        surrogates=surrogates,
        surrogate_method="iaaft",
        seed=seed,
        json_out=None,
    )


@app.command("transpile")
def cmd_transpile(
    indicator: str = typer.Option("KalmanFilter", "--indicator", "-i", help="Registered indicator name"),
    expr: str | None = typer.Option(None, "--expr", "-e", help="Custom SymPy formula string to transpile"),
    symbol: str = typer.Option("SYNTH:COUPLED_OU", "--symbol", "-s", help="Dataset for Research Card scorecard"),
    bars: int = typer.Option(600, "--bars", "-n", help="Number of bars for Research Card evaluation"),
    evaluate_card: bool = typer.Option(True, "--evaluate-card/--no-evaluate-card", help="Embed proof scorecard"),
    out_pine: Path | None = typer.Option(None, "--out-pine", help="Optional path to save .pine file"),
    out_card: Path | None = typer.Option(None, "--out-card", help="Optional path to save .md Research Card"),
) -> None:
    """Compile a registered indicator or custom SymPy AST to TradingView Pine Script v6 + Research Card."""
    reg = get_registry()
    if expr is not None and expr.strip():
        artifact = transpile_to_pine_v6(
            expr.strip(),
            name="CustomFormula",
            title="QuantLab Custom Symbolic Formula",
        )
    else:
        spec = reg.get(indicator)
        proof_res = None
        if evaluate_card:
            ds = fetch_ohlcv(symbol=symbol, provider="synthetic", bars=bars, seed=42)
            proof_res = run_proof_suite(spec=spec, dataset=ds, n_surrogates=25, seed=42)
        artifact = transpile_to_pine_v6(spec, proof_result=proof_res)

    console.print(Panel(artifact.pine_code, title=f"Pine Script v6 — {artifact.title}", border_style="cyan"))

    if out_pine is not None:
        out_pine.parent.mkdir(parents=True, exist_ok=True)
        out_pine.write_text(artifact.pine_code, encoding="utf-8")
        console.print(f"[green]Saved Pine Script v6 to {out_pine}[/green]")

    if out_card is not None:
        out_card.parent.mkdir(parents=True, exist_ok=True)
        out_card.write_text(artifact.research_card_md, encoding="utf-8")
        console.print(f"[green]Saved Markdown Research Card to {out_card}[/green]")


@app.command("dashboard")
def cmd_dashboard(
    port: int = typer.Option(8501, "--port", help="Local port for Streamlit dashboard"),
    headless: bool = typer.Option(False, "--headless/--no-headless", help="Run Streamlit in headless server mode"),
    check: bool = typer.Option(False, "--check", help="Validate all 4 dashboard quadrants in headless check mode"),
) -> None:
    """Launch the 4-Quadrant Interactive Quant Diagnostic Dashboard (`streamlit`)."""
    if check:
        summary = run_dashboard_self_check()
        console.print(
            Panel(
                json.dumps(summary, indent=2),
                title="QuantLab 4-Quadrant Dashboard Self-Check Passed",
                border_style="green",
            )
        )
        return

    app_path = Path(__file__).resolve().parent / "dashboard" / "app.py"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(port),
        "--theme.base",
        "dark",
    ]
    if headless:
        cmd.extend(["--server.headless", "true"])
    console.print(f"[bold cyan]Launching QuantLab 4-Quadrant Dashboard on http://localhost:{port} ...[/bold cyan]")
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    app()
