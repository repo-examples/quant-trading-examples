"""4-Quadrant Interactive Quant Diagnostic Dashboard (Streamlit + Plotly + TradingView Lightweight Charts)."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from quantlab.dashboard.loading_state import (
    SPEC_ID,
    PipelineCancelledError,
    PipelineExecutionTelemetry,
    PipelineStageStatus,
    advance_telemetry_stage,
    build_initial_telemetry,
    build_loading_theme_css,
    cancel_telemetry,
    complete_telemetry,
    compute_stage_progress_pct,
    fail_telemetry,
    is_long_running_load,
    render_completed_summary_bar_html,
    render_pipeline_status_card_html,
    render_shimmer_skeletons_html,
    render_warm_dimmed_banner_html,
    update_surrogate_telemetry,
)
from quantlab.data.loader import DataProvider, OHLCVDataset, fetch_ohlcv
from quantlab.indicators.custom_examples import reconstruct_phase_space_3d
from quantlab.indicators.registry import get_registry
from quantlab.proofs.dsp import DSPResult, identify_pareto_frontier
from quantlab.proofs.stats_gate import (
    ProofSuiteResult,
    run_proof_suite,
)
from quantlab.transpiler.pine_v6 import TranspilationArtifact, transpile_to_pine_v6

DARK_BG = "#0E1117"
PANEL_BG = "#111827"
GRID_COLOR = "#1F2937"
CYAN = "#00F5D4"
MAGENTA = "#FF2A85"
AMBER = "#F59E0B"
EMERALD = "#10B981"
SLATE = "#94A3B8"

__all__ = [
    "DARK_BG",
    "SPEC_ID",
    "DashboardBundle",
    "PipelineCancelledError",
    "PipelineExecutionTelemetry",
    "PipelineStageStatus",
    "advance_telemetry_stage",
    "build_dashboard_bundle",
    "build_dashboard_bundle_with_telemetry",
    "build_dashboard_state",
    "build_initial_telemetry",
    "build_lightweight_charts_canvas_html",
    "build_loading_theme_css",
    "build_q1_figures",
    "build_q2_figures",
    "build_q3_figures",
    "cancel_telemetry",
    "complete_telemetry",
    "compute_stage_progress_pct",
    "fail_telemetry",
    "is_long_running_load",
    "render_completed_summary_bar_html",
    "render_dashboard",
    "render_pipeline_status_card_html",
    "render_shimmer_skeletons_html",
    "render_streamlit_app",
    "render_warm_dimmed_banner_html",
    "run_dashboard_self_check",
    "update_surrogate_telemetry",
]


@dataclass(frozen=True)
class DashboardBundle:
    """Precomputed state and Plotly/Lightweight-Charts artifacts for all 4 Diagnostic Quadrants."""

    dataset: OHLCVDataset
    active_proof: ProofSuiteResult
    all_proofs: list[ProofSuiteResult]
    transpilation: TranspilationArtifact
    lightweight_charts_html: str
    fig_q1_ohlcv: go.Figure
    fig_q1_phase_space: go.Figure
    fig_q2_rolling_entropy: go.Figure
    fig_q2_surrogates: go.Figure
    fig_q3_ic_vif: go.Figure
    fig_q3_wasserstein: go.Figure
    fig_q3_pareto_bode: go.Figure


def build_lightweight_charts_canvas_html(
    dataset: OHLCVDataset,
    proof: ProofSuiteResult,
    overlay: bool = False,
    height: int = 420,
) -> str:
    """Build an interactive HTML5 TradingView Lightweight Charts canvas with OHLCV + Indicator."""
    df = dataset.df
    timestamps = (df.index.astype("int64") // 10**9).tolist()
    candles = [
        {
            "time": int(ts),
            "open": float(open_v),
            "high": float(high_v),
            "low": float(low_v),
            "close": float(close_v),
        }
        for ts, open_v, high_v, low_v, close_v in zip(
            timestamps,
            df["open"].to_numpy(),
            df["high"].to_numpy(),
            df["low"].to_numpy(),
            df["close"].to_numpy(),
            strict=False,
        )
    ]
    ind_points = [
        {"time": int(ts), "value": float(v)}
        for ts, v in zip(timestamps, np.nan_to_num(proof.raw_series, nan=0.0), strict=False)
    ]

    candles_json = json.dumps(candles)
    ind_json = json.dumps(ind_points)
    ind_title = json.dumps(f"{proof.indicator_name}")
    is_overlay_js = "true" if overlay else "false"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
<style>
  body {{ margin: 0; padding: 0; background-color: {DARK_BG}; color: #E2E8F0; font-family: monospace; }}
  #tv-chart {{ width: 100%; height: {height}px; }}
</style>
</head>
<body>
<div id="tv-chart"></div>
<script>
  const container = document.getElementById('tv-chart');
  const chart = LightweightCharts.createChart(container, {{
    layout: {{ background: {{ type: 'solid', color: '{DARK_BG}' }}, textColor: '#CBD5E1' }},
    grid: {{ vertLines: {{ color: '{GRID_COLOR}' }}, horzLines: {{ color: '{GRID_COLOR}' }} }},
    rightPriceScale: {{ borderColor: '#334155' }},
    timeScale: {{ borderColor: '#334155', timeVisible: true }}
  }});
  const candleSeries = chart.addCandlestickSeries({{
    upColor: '{EMERALD}', downColor: '{MAGENTA}',
    borderUpColor: '{EMERALD}', borderDownColor: '{MAGENTA}',
    wickUpColor: '{EMERALD}', wickDownColor: '{MAGENTA}'
  }});
  candleSeries.setData({candles_json});
  const indSeries = chart.addLineSeries({{
    color: '{CYAN}',
    lineWidth: 2,
    title: {ind_title},
    priceScaleId: {is_overlay_js} ? 'right' : 'left'
  }});
  if (!{is_overlay_js}) {{
    chart.priceScale('left').applyOptions({{ visible: true, borderColor: '#334155' }});
  }}
  indSeries.setData({ind_json});
  chart.timeScale().fitContent();
</script>
</body>
</html>"""


def _apply_dark_theme(fig: go.Figure, title: str, height: int = 420) -> go.Figure:
    fig.update_layout(
        title={"text": title, "font": {"size": 15, "color": "#F8FAFC"}},
        template="plotly_dark",
        paper_bgcolor=DARK_BG,
        plot_bgcolor=PANEL_BG,
        font={"family": "JetBrains Mono, Consolas, monospace", "color": "#CBD5E1", "size": 11},
        height=height,
        margin={"l": 45, "r": 30, "t": 50, "b": 40},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1.0},
    )
    return fig


def build_q1_figures(
    dataset: OHLCVDataset,
    proof: ProofSuiteResult,
    overlay: bool = False,
    phase_delay: int = 3,
) -> tuple[go.Figure, go.Figure]:
    """Build Q1 Figures: (1) OHLCV + Indicator Canvas and (2) 3D Takens Phase-Space Attractor."""
    df = dataset.df
    fig_ohlcv = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.62, 0.38],
        subplot_titles=(
            f"{dataset.symbol} OHLCV & FracDiff Stationarity (d*={proof.stationarity.d_optimal:.2f})",
            f"{proof.indicator_title} ({proof.indicator_name})",
        ),
    )
    fig_ohlcv.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="OHLCV",
            increasing_line_color=EMERALD,
            decreasing_line_color=MAGENTA,
        ),
        row=1,
        col=1,
    )
    if overlay:
        fig_ohlcv.add_trace(
            go.Scatter(
                x=df.index,
                y=proof.raw_series,
                mode="lines",
                name=proof.indicator_name,
                line={"color": CYAN, "width": 2},
            ),
            row=1,
            col=1,
        )
        fig_ohlcv.add_trace(
            go.Scatter(
                x=df.index,
                y=proof.stationary_series,
                mode="lines",
                name=f"{proof.indicator_name} (Stationary Displacement)",
                line={"color": AMBER, "width": 1.6},
            ),
            row=2,
            col=1,
        )
    else:
        fig_ohlcv.add_trace(
            go.Scatter(
                x=df.index,
                y=proof.raw_series,
                mode="lines",
                name=proof.indicator_name,
                line={"color": CYAN, "width": 2},
            ),
            row=2,
            col=1,
        )
    fig_ohlcv.update_layout(xaxis_rangeslider_visible=False)
    _apply_dark_theme(fig_ohlcv, f"Q1A — Causal Point-in-Time Market & Indicator Canvas ({dataset.symbol})", height=460)

    # 3D Takens Delay-Embedding Attractor
    x0, x1, x2 = reconstruct_phase_space_3d(proof.stationary_series, delay=max(1, phase_delay))
    time_color = np.linspace(0.0, 1.0, len(x0))
    fig_phase = go.Figure(
        data=[
            go.Scatter3d(
                x=x0,
                y=x1,
                z=x2,
                mode="lines+markers",
                name="Phase Trajectory",
                line={"color": time_color, "colorscale": "Viridis", "width": 3},
                marker={"size": 2.5, "color": time_color, "colorscale": "Turbo", "opacity": 0.85},
            )
        ]
    )
    fig_phase.update_layout(
        scene={
            "xaxis_title": "x(t)",
            "yaxis_title": f"x(t - {phase_delay})",
            "zaxis_title": f"x(t - {2 * phase_delay})",
            "bgcolor": PANEL_BG,
        }
    )
    _apply_dark_theme(
        fig_phase,
        f"Q1B — 3D Takens Phase-Space Attractor ({proof.indicator_name}, tau={phase_delay})",
        height=460,
    )
    return fig_ohlcv, fig_phase


def build_q2_figures(
    dataset: OHLCVDataset,
    proof: ProofSuiteResult,
) -> tuple[go.Figure, go.Figure]:
    """Build Q2 Figures: (1) Rolling Shannon Entropy & Rolling Rank IC and (2) Surrogate TE Null Distribution."""
    df = dataset.df
    en = proof.entropy
    sg = proof.stats_gate

    fig_ent = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=(
            f"Causal Rolling Shannon Entropy H_t (Mean H={en.shannon_entropy:.3f} nats, Perm H={en.permutation_entropy:.3f})",
            f"Causal Rolling Spearman Rank IC (Max |IC|={sg.max_abs_ic:.4f} at h={sg.best_horizon})",
        ),
    )
    fig_ent.add_trace(
        go.Scatter(
            x=df.index,
            y=en.rolling_entropy,
            mode="lines",
            name="Rolling Shannon Entropy",
            line={"color": CYAN, "width": 1.8},
            fill="tozeroy",
            fillcolor="rgba(0, 245, 212, 0.12)",
        ),
        row=1,
        col=1,
    )
    fig_ent.add_trace(
        go.Scatter(
            x=df.index,
            y=sg.rolling_ic,
            mode="lines",
            name="Rolling Spearman IC",
            line={"color": AMBER, "width": 1.8},
        ),
        row=2,
        col=1,
    )
    fig_ent.add_hline(y=sg.ic_threshold, line_dash="dash", line_color=EMERALD, row=2, col=1)
    fig_ent.add_hline(y=-sg.ic_threshold, line_dash="dash", line_color=EMERALD, row=2, col=1)
    _apply_dark_theme(fig_ent, "Q2A — Causal Rolling Information Dynamics", height=430)

    # Surrogate Transfer Entropy Null Histogram vs Observed TE
    fig_surr = go.Figure()
    fig_surr.add_trace(
        go.Histogram(
            x=en.surrogate_te_samples,
            nbinsx=20,
            name=f"Surrogate Null ({en.surrogate_method.upper()})",
            marker_color="#3B82F6",
            opacity=0.75,
        )
    )
    fig_surr.add_vline(
        x=en.symbolic_te,
        line_width=3,
        line_dash="solid",
        line_color=MAGENTA,
        annotation_text=f"Observed TE={en.symbolic_te:.5f} (Z={en.z_score:.2f}, p={en.p_value:.4f})",
        annotation_position="top right",
    )
    _apply_dark_theme(
        fig_surr,
        f"Q2B — Transfer Entropy TE(X -> R) vs Monte Carlo Surrogates ({'PASS' if en.passed else 'FAIL'})",
        height=430,
    )
    return fig_ent, fig_surr


def build_q3_figures(
    dataset: OHLCVDataset,
    proof: ProofSuiteResult,
    all_proofs: list[ProofSuiteResult],
) -> tuple[go.Figure, go.Figure, go.Figure]:
    """Build Q3 Figures: (1) Multi-Horizon Rank IC & Baseline Correlations, (2) Wasserstein Regimes, (3) Bode & Pareto Frontier."""
    sg = proof.stats_gate
    horizons = [f"h={h}" for h in sorted(sg.ic_by_horizon.keys())]
    ic_vals = [sg.ic_by_horizon[h] for h in sorted(sg.ic_by_horizon.keys())]

    base_names = list(sg.baseline_correlations.keys())
    base_corrs = [sg.baseline_correlations[k] for k in base_names]

    fig_ic_vif = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            "Multi-Horizon Spearman Rank IC Decay",
            f"Baseline Orthogonality Correlations (VIF={sg.vif_score:.2f})",
        ),
    )
    fig_ic_vif.add_trace(
        go.Bar(
            x=horizons,
            y=ic_vals,
            name="Rank IC",
            marker_color=[EMERALD if abs(v) > sg.ic_threshold else SLATE for v in ic_vals],
        ),
        row=1,
        col=1,
    )
    fig_ic_vif.add_trace(
        go.Bar(
            x=base_names,
            y=base_corrs,
            name="Spearman Corr",
            marker_color=CYAN,
        ),
        row=1,
        col=2,
    )
    _apply_dark_theme(fig_ic_vif, "Q3A — Predictive Rank IC Decay & Baseline Orthogonality", height=380)

    # Wasserstein Bull vs Bear Regime Separation
    sig = proof.stationary_series
    sig_z = (sig - np.mean(sig)) / max(float(np.std(sig)), 1e-12)
    if "regime" in dataset.df.columns:
        reg = dataset.df["regime"].to_numpy(dtype=np.float64)
        bull_vals = sig_z[reg < 0.5]
        bear_vals = sig_z[reg >= 0.5]
    else:
        ret = dataset.log_returns
        med = float(np.median(ret))
        bull_vals = sig_z[ret >= med]
        bear_vals = sig_z[ret < med]

    fig_wass = go.Figure()
    fig_wass.add_trace(
        go.Histogram(
            x=bull_vals,
            name="Bull / Low-Vol Regime",
            marker_color=EMERALD,
            opacity=0.6,
            histnorm="probability density",
        )
    )
    fig_wass.add_trace(
        go.Histogram(
            x=bear_vals,
            name="Bear / High-Vol Regime",
            marker_color=MAGENTA,
            opacity=0.6,
            histnorm="probability density",
        )
    )
    fig_wass.update_layout(barmode="overlay")
    _apply_dark_theme(
        fig_wass,
        f"Q3B — Regime Distribution Separation (Wasserstein W1 = {sg.wasserstein_regime_distance:.4f})",
        height=380,
    )

    # Bode Phase-Lag vs Jerk Pareto Frontier + Active Bode Magnitude/Phase
    fig_dsp = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            "Phase-Lag (Bars) vs. Jerk Energy Pareto Frontier",
            f"Empirical Bode Phase Response ({proof.indicator_name})",
        ),
    )
    for r in all_proofs:
        is_p = r.dsp.pareto_optimal
        fig_dsp.add_trace(
            go.Scatter(
                x=[r.dsp.mean_phase_lag_bars],
                y=[r.dsp.jerk_energy],
                mode="markers+text",
                text=[r.indicator_name],
                textposition="top center",
                name=f"{r.indicator_name} ({'Pareto' if is_p else 'Dom'})",
                marker={
                    "size": 14 if r.indicator_name == proof.indicator_name else 10,
                    "color": CYAN if is_p else SLATE,
                    "symbol": "diamond" if is_p else "circle",
                    "line": {"width": 2, "color": MAGENTA if r.indicator_name == proof.indicator_name else "#FFFFFF"},
                },
            ),
            row=1,
            col=1,
        )
    fig_dsp.update_xaxes(title_text="Hilbert Mean Phase Lag (Bars)", row=1, col=1)
    fig_dsp.update_yaxes(title_text="3rd-Derivative Jerk Energy", row=1, col=1)

    fig_dsp.add_trace(
        go.Scatter(
            x=proof.dsp.bode_frequencies,
            y=proof.dsp.bode_phase_deg,
            mode="lines",
            name="Bode Phase (deg)",
            line={"color": AMBER, "width": 2},
        ),
        row=1,
        col=2,
    )
    fig_dsp.update_xaxes(title_text="Frequency omega (rad/sample)", row=1, col=2)
    fig_dsp.update_yaxes(title_text="Phase Response (deg)", row=1, col=2)
    _apply_dark_theme(fig_dsp, "Q3C — DSP Hilbert Phase-Lag vs. Smoothness (Jerk) Frontier", height=400)

    return fig_ic_vif, fig_wass, fig_dsp


def _update_pareto_results(
    preliminary: list[ProofSuiteResult],
) -> list[ProofSuiteResult]:
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


def build_dashboard_bundle(
    symbol: str = "SYNTH:COUPLED_OU",
    provider: DataProvider = "synthetic",
    timeframe: str = "1d",
    bars: int = 500,
    indicator_name: str = "KalmanFilter",
    custom_expr: str | None = None,
    n_surrogates: int = 30,
    seed: int = 42,
    telemetry_callback: Callable[[PipelineExecutionTelemetry], None] | None = None,
    is_warm_reload: bool = False,
    restarted_with_updated_params: bool = False,
    cancel_check: Callable[[], bool] | None = None,
) -> DashboardBundle:
    """Compute and assemble all data, proofs, figures, and Pine Script v6 artifacts for the 4 quadrants.

    Emits SPEC-QUANT-LOAD-01 4-stage telemetry snapshots when `telemetry_callback` is provided.
    """
    t0 = time.perf_counter()
    effective_surrogates = max(10, int(n_surrogates))
    telemetry = build_initial_telemetry(
        symbol=symbol,
        provider=provider,
        timeframe=timeframe,
        bars=bars,
        indicator_name=indicator_name,
        n_surrogates=effective_surrogates,
        seed=seed,
        is_warm_reload=is_warm_reload,
        restarted_with_updated_params=restarted_with_updated_params,
    )

    def _emit(state: PipelineExecutionTelemetry) -> None:
        if telemetry_callback is not None:
            telemetry_callback(state)

    def _check_cancel(current_state: PipelineExecutionTelemetry) -> None:
        if cancel_check is not None and cancel_check():
            cancelled = cancel_telemetry(current_state, elapsed_seconds=time.perf_counter() - t0)
            _emit(cancelled)
            raise PipelineCancelledError("Quantitative pipeline run cancelled by user.")

    # Stage 1 (0% -> 20%): Synthesizing / Fetching Market Data
    _emit(telemetry)
    _check_cancel(telemetry)
    t_stage1 = time.perf_counter()
    try:
        dataset = fetch_ohlcv(
            symbol=symbol,
            provider=provider,
            timeframe=timeframe,
            bars=bars,
            seed=seed,
        )
    except PipelineCancelledError:
        raise
    except Exception as exc:
        failed = fail_telemetry(
            telemetry,
            error_step=1,
            error_message=str(exc),
            elapsed_seconds=time.perf_counter() - t0,
        )
        _emit(failed)
        raise
    d_stage1 = time.perf_counter() - t_stage1

    # Stage 2 (20% -> 40%): Computing Active Indicator
    telemetry = advance_telemetry_stage(
        telemetry,
        active_stage=2,
        elapsed_seconds=time.perf_counter() - t0,
        completed_stage_duration=d_stage1,
    )
    _emit(telemetry)
    _check_cancel(telemetry)
    t_stage2 = time.perf_counter()
    try:
        registry = get_registry()
        active_spec = registry.get(indicator_name)
        _ = active_spec.evaluate(dataset.df)
    except PipelineCancelledError:
        raise
    except Exception as exc:
        failed = fail_telemetry(
            telemetry,
            error_step=2,
            error_message=str(exc),
            elapsed_seconds=time.perf_counter() - t0,
        )
        _emit(failed)
        raise
    d_stage2 = time.perf_counter() - t_stage2

    # Stage 3 (40% -> 85%): Simulating Monte Carlo Surrogates for Active Indicator
    telemetry = advance_telemetry_stage(
        telemetry,
        active_stage=3,
        elapsed_seconds=time.perf_counter() - t0,
        completed_stage_duration=d_stage2,
    )
    _emit(telemetry)
    _check_cancel(telemetry)
    t_stage3 = time.perf_counter()

    def _on_surrogate(cur_idx: int, _total: int) -> None:
        nonlocal telemetry
        _check_cancel(telemetry)
        telemetry = update_surrogate_telemetry(
            telemetry,
            current_surrogate=cur_idx,
            elapsed_seconds=time.perf_counter() - t0,
        )
        _emit(telemetry)

    try:
        active_prelim = run_proof_suite(
            spec=active_spec,
            dataset=dataset,
            n_surrogates=effective_surrogates,
            seed=seed,
            surrogate_progress_callback=_on_surrogate,
        )
    except PipelineCancelledError:
        raise
    except Exception as exc:
        failed = fail_telemetry(
            telemetry,
            error_step=3,
            error_message=str(exc),
            elapsed_seconds=time.perf_counter() - t0,
        )
        _emit(failed)
        raise
    d_stage3 = time.perf_counter() - t_stage3

    # Stage 4 (85% -> 100%): Evaluating Hilbert Phase-Jerk Frontier & Pine v6 Transpiler
    telemetry = advance_telemetry_stage(
        telemetry,
        active_stage=4,
        elapsed_seconds=time.perf_counter() - t0,
        completed_stage_duration=d_stage3,
    )
    _emit(telemetry)
    _check_cancel(telemetry)
    t_stage4 = time.perf_counter()
    try:
        all_specs = registry.list_all()
        preliminary: list[ProofSuiteResult] = []
        for s in all_specs:
            _check_cancel(telemetry)
            if s.name.lower() == active_spec.name.lower():
                preliminary.append(active_prelim)
            else:
                preliminary.append(
                    run_proof_suite(
                        spec=s,
                        dataset=dataset,
                        n_surrogates=effective_surrogates,
                        seed=seed,
                    )
                )
        all_proofs = _update_pareto_results(preliminary)
        proof_map = {p.indicator_name.lower(): p for p in all_proofs}
        active_proof = proof_map.get(active_spec.name.lower(), active_prelim)

        if custom_expr and custom_expr.strip():
            transpilation = transpile_to_pine_v6(
                custom_expr.strip(),
                params=active_spec.default_params,
                name=f"Custom_{active_spec.name}",
                title=f"Custom {active_spec.title}",
                overlay=active_spec.overlay,
                recurrences=active_spec.state_recurrences(),
                proof_result=active_proof,
            )
        else:
            transpilation = transpile_to_pine_v6(active_spec, proof_result=active_proof)

        lw_html = build_lightweight_charts_canvas_html(dataset, active_proof, overlay=active_spec.overlay)
        fig_q1_ohlcv, fig_q1_phase = build_q1_figures(dataset, active_proof, overlay=active_spec.overlay)
        fig_q2_ent, fig_q2_surr = build_q2_figures(dataset, active_proof)
        fig_q3_ic, fig_q3_wass, fig_q3_dsp = build_q3_figures(dataset, active_proof, all_proofs)
    except PipelineCancelledError:
        raise
    except Exception as exc:
        failed = fail_telemetry(
            telemetry,
            error_step=4,
            error_message=str(exc),
            elapsed_seconds=time.perf_counter() - t0,
        )
        _emit(failed)
        raise

    d_stage4 = time.perf_counter() - t_stage4
    telemetry = complete_telemetry(
        telemetry,
        elapsed_seconds=time.perf_counter() - t0,
        stage4_duration=d_stage4,
    )
    _emit(telemetry)

    return DashboardBundle(
        dataset=dataset,
        active_proof=active_proof,
        all_proofs=all_proofs,
        transpilation=transpilation,
        lightweight_charts_html=lw_html,
        fig_q1_ohlcv=fig_q1_ohlcv,
        fig_q1_phase_space=fig_q1_phase,
        fig_q2_rolling_entropy=fig_q2_ent,
        fig_q2_surrogates=fig_q2_surr,
        fig_q3_ic_vif=fig_q3_ic,
        fig_q3_wasserstein=fig_q3_wass,
        fig_q3_pareto_bode=fig_q3_dsp,
    )


def build_dashboard_bundle_with_telemetry(
    symbol: str = "SYNTH:COUPLED_OU",
    provider: DataProvider = "synthetic",
    timeframe: str = "1d",
    bars: int = 500,
    indicator_name: str = "KalmanFilter",
    custom_expr: str | None = None,
    n_surrogates: int = 30,
    seed: int = 42,
    is_warm_reload: bool = False,
    restarted_with_updated_params: bool = False,
    cancel_check: Callable[[], bool] | None = None,
) -> tuple[DashboardBundle, list[PipelineExecutionTelemetry]]:
    """Build the 4-Quadrant DashboardBundle and return the full sequence of SPEC-QUANT-LOAD-01 telemetry states."""
    snapshots: list[PipelineExecutionTelemetry] = []
    bundle = build_dashboard_bundle(
        symbol=symbol,
        provider=provider,
        timeframe=timeframe,
        bars=bars,
        indicator_name=indicator_name,
        custom_expr=custom_expr,
        n_surrogates=n_surrogates,
        seed=seed,
        telemetry_callback=snapshots.append,
        is_warm_reload=is_warm_reload,
        restarted_with_updated_params=restarted_with_updated_params,
        cancel_check=cancel_check,
    )
    return bundle, snapshots


def run_dashboard_self_check() -> dict[str, object]:
    """Validate that all 4 Quadrants and SPEC-QUANT-LOAD-01 telemetry build cleanly in headless mode."""
    bundle, snapshots = build_dashboard_bundle_with_telemetry(
        symbol="SYNTH:COUPLED_OU",
        provider="synthetic",
        bars=300,
        indicator_name="KalmanFilter",
        n_surrogates=15,
        seed=42,
    )
    final_snap = snapshots[-1]
    return {
        "status": "ok",
        "loading_spec_id": final_snap.spec_id,
        "telemetry_snapshots_count": len(snapshots),
        "telemetry_stages_verified": len(final_snap.stages),
        "final_progress_pct": final_snap.overall_progress_pct,
        "symbol": bundle.dataset.symbol,
        "bars": bundle.dataset.n_bars,
        "active_indicator": bundle.active_proof.indicator_name,
        "indicators_evaluated": len(bundle.all_proofs),
        "pine_v6_header": bundle.transpilation.pine_code.splitlines()[0],
        "q1_traces": len(bundle.fig_q1_ohlcv.data) + len(bundle.fig_q1_phase_space.data),
        "q2_traces": len(bundle.fig_q2_rolling_entropy.data) + len(bundle.fig_q2_surrogates.data),
        "q3_traces": (
            len(bundle.fig_q3_ic_vif.data)
            + len(bundle.fig_q3_wasserstein.data)
            + len(bundle.fig_q3_pareto_bode.data)
        ),
    }


def _render_dashboard_workspace_content(
    st: object,
    components: object,
    bundle: DashboardBundle,
    selected_ind: str,
    dimmed: bool = False,
    key_suffix: str = "live",
) -> None:
    """Render the 5 KPI cards and 4 Diagnostic Quadrants (optionally wrapped in warm-dimmed state)."""
    if dimmed:
        st.markdown('<div class="ql-warm-dimmed">', unsafe_allow_html=True)  # type: ignore[attr-defined]

    p = bundle.active_proof
    col1, col2, col3, col4, col5 = st.columns(5)  # type: ignore[attr-defined]
    col1.metric("FracDiff d* (ADF p)", f"d*={p.stationarity.d_optimal:.2f}", f"p={p.stationarity.p_value:.4f}")
    col2.metric(
        "Transfer Entropy TE(X->R)",
        f"{p.entropy.symbolic_te:.5f}",
        f"Z={p.entropy.z_score:.2f} (p={p.entropy.p_value:.3f})",
    )
    col3.metric("Max |Spearman Rank IC|", f"{p.stats_gate.max_abs_ic:.4f}", f"Horizon h={p.stats_gate.best_horizon}")
    col4.metric(
        "Baseline Orthogonality VIF",
        f"{p.stats_gate.vif_score:.2f}",
        "PASS (<5.0)" if p.stats_gate.vif_passed else "HIGH",
    )
    col5.metric("DSP Phase Lag / Jerk", f"{p.dsp.mean_phase_lag_bars:.2f} bars", f"Jerk={p.dsp.jerk_energy:.3f}")

    tab_q1, tab_q2, tab_q3, tab_q4 = st.tabs(  # type: ignore[attr-defined]
        [
            "📐 Q1: OHLCV Canvas & 3D Phase-Space",
            "🔀 Q2: Entropy & Surrogate Proofs",
            "📊 Q3: Statistical & DSP Pareto Frontier",
            "⚙️ Q4: SymPy AST & Pine Script v6 Studio",
        ]
    )

    with tab_q1:
        st.subheader("TradingView Lightweight Charts HTML5 Canvas")  # type: ignore[attr-defined]
        components.html(bundle.lightweight_charts_html, height=440)  # type: ignore[attr-defined]
        q1_left, q1_right = st.columns(2)  # type: ignore[attr-defined]
        with q1_left:
            st.plotly_chart(  # type: ignore[attr-defined]
                bundle.fig_q1_ohlcv,
                use_container_width=True,
                key=f"q1_ohlcv_{key_suffix}",
            )
        with q1_right:
            st.plotly_chart(  # type: ignore[attr-defined]
                bundle.fig_q1_phase_space,
                use_container_width=True,
                key=f"q1_phase_{key_suffix}",
            )

    with tab_q2:
        q2_left, q2_right = st.columns(2)  # type: ignore[attr-defined]
        with q2_left:
            st.plotly_chart(  # type: ignore[attr-defined]
                bundle.fig_q2_rolling_entropy,
                use_container_width=True,
                key=f"q2_ent_{key_suffix}",
            )
        with q2_right:
            st.plotly_chart(  # type: ignore[attr-defined]
                bundle.fig_q2_surrogates,
                use_container_width=True,
                key=f"q2_surr_{key_suffix}",
            )

    with tab_q3:
        q3_top_l, q3_top_r = st.columns(2)  # type: ignore[attr-defined]
        with q3_top_l:
            st.plotly_chart(  # type: ignore[attr-defined]
                bundle.fig_q3_ic_vif,
                use_container_width=True,
                key=f"q3_ic_{key_suffix}",
            )
        with q3_top_r:
            st.plotly_chart(  # type: ignore[attr-defined]
                bundle.fig_q3_wasserstein,
                use_container_width=True,
                key=f"q3_wass_{key_suffix}",
            )
        st.plotly_chart(  # type: ignore[attr-defined]
            bundle.fig_q3_pareto_bode,
            use_container_width=True,
            key=f"q3_dsp_{key_suffix}",
        )

    with tab_q4:
        st.subheader("Live Neuro-Symbolic SymPy AST Editor -> TradingView Pine Script v6")  # type: ignore[attr-defined]
        reg = get_registry()
        active_spec = reg.get(selected_ind)
        default_formula = str(active_spec.symbolic_ast())
        expr_input = st.text_input(  # type: ignore[attr-defined]
            "Symbolic Expression (SymPy AST):",
            value=default_formula,
            key=f"ast_expr_{key_suffix}",
        )
        try:
            live_art = transpile_to_pine_v6(
                expr_input,
                params=active_spec.default_params,
                name=active_spec.name,
                title=active_spec.title,
                overlay=active_spec.overlay,
                recurrences=active_spec.state_recurrences(),
                proof_result=bundle.active_proof,
            )
            st.latex(f"\\mathcal{{I}}_t = {live_art.latex_expr}")  # type: ignore[attr-defined]
            c_pine, c_card = st.columns(2)  # type: ignore[attr-defined]
            with c_pine:
                st.markdown("#### Generated Pine Script v6 (`//@version=6`)")  # type: ignore[attr-defined]
                st.code(live_art.pine_code, language="pine")  # type: ignore[attr-defined]
                st.download_button(  # type: ignore[attr-defined]
                    "⬇️ Download Pine Script v6 (.pine)",
                    data=live_art.pine_code,
                    file_name=f"{live_art.indicator_name.lower()}_v6.pine",
                    mime="text/plain",
                    key=f"dl_pine_{key_suffix}",
                )
            with c_card:
                st.markdown("#### Auditable Markdown Research Card")  # type: ignore[attr-defined]
                st.markdown(live_art.research_card_md)  # type: ignore[attr-defined]
                st.download_button(  # type: ignore[attr-defined]
                    "⬇️ Download Research Card (.md)",
                    data=live_art.research_card_md,
                    file_name=f"{live_art.indicator_name.lower()}_research_card.md",
                    mime="text/markdown",
                    key=f"dl_card_{key_suffix}",
                )
        except Exception as exc:
            st.error(f"Symbolic AST Transpilation Error: {exc}")  # type: ignore[attr-defined]

    if dimmed:
        st.markdown("</div>", unsafe_allow_html=True)  # type: ignore[attr-defined]


def render_streamlit_app() -> None:
    """Render the 4-Quadrant Interactive Quant Diagnostic Dashboard in Streamlit."""
    import streamlit as st
    import streamlit.components.v1 as components

    st.set_page_config(
        page_title="QuantLab — Information-Theoretic Indicator Research & Pine v6 Transpiler",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(
        f"""
        <style>
        .stApp {{ background-color: {DARK_BG}; color: #F8FAFC; }}
        </style>
        {build_loading_theme_css()}
        """,
        unsafe_allow_html=True,
    )

    st.title("⚛️ QuantLab: Information-Theoretic Indicator Research & Pine v6 Studio")
    st.caption(
        "Causal Point-in-Time (PIT) Stationarity • Surrogate Transfer Entropy • "
        "Hilbert Phase-Jerk Frontier • SymPy-to-Pine Script v6 Transpiler"
    )

    reg = get_registry()
    indicator_names = reg.names()

    default_seed_val = int(st.session_state.get("ql_seed_reset_value", 42))

    with st.sidebar:
        st.header("🔬 Research Controls")
        provider = st.selectbox("Market Data Provider", ["synthetic", "yfinance", "ccxt"], index=0)
        default_sym = (
            "SYNTH:COUPLED_OU"
            if provider == "synthetic"
            else ("SPY" if provider == "yfinance" else "BTC/USDT")
        )
        symbol = st.text_input("Symbol / Stochastic Process", value=default_sym)
        timeframe = st.selectbox("Timeframe", ["1d", "4h", "1h", "15m"], index=0)
        bars = int(st.slider("PIT History Bars", min_value=200, max_value=2000, value=600, step=100))
        selected_ind = st.selectbox(
            "Active Indicator",
            indicator_names,
            index=indicator_names.index("KalmanFilter"),
        )
        n_surr = int(st.slider("Monte Carlo Surrogates", min_value=15, max_value=100, value=30, step=5))
        seed = int(st.number_input("Deterministic Seed", value=default_seed_val, step=1))

    current_params = (provider, symbol, timeframe, bars, selected_ind, n_surr, seed)
    last_params = st.session_state.get("ql_last_params")
    cached_bundle: DashboardBundle | None = st.session_state.get("ql_last_bundle")
    was_running: bool = bool(st.session_state.get("ql_is_running", False))

    is_warm_reload = cached_bundle is not None and last_params is not None and last_params != current_params
    restarted_mid_run = (was_running and last_params != current_params) or is_warm_reload

    status_slot = st.empty()
    log_and_controls_slot = st.container()
    workspace_slot = st.empty()

    # Check if user clicked Cancel Run on the previous interaction
    if st.session_state.get("ql_cancel_requested", False):
        st.session_state["ql_cancel_requested"] = False
        cancelled_tel = cancel_telemetry(
            build_initial_telemetry(
                symbol=symbol,
                provider=provider,
                timeframe=timeframe,
                bars=bars,
                indicator_name=selected_ind,
                n_surrogates=n_surr,
                seed=seed,
            ),
            elapsed_seconds=0.0,
        )
        status_slot.markdown(render_pipeline_status_card_html(cancelled_tel), unsafe_allow_html=True)
        with log_and_controls_slot:
            if st.button("🔄 Retry Run", key="ql_retry_after_cancel"):
                st.rerun()
        if cached_bundle is not None:
            with workspace_slot.container():
                _render_dashboard_workspace_content(
                    st,
                    components,
                    cached_bundle,
                    selected_ind,
                    dimmed=True,
                    key_suffix="cancelled_cached",
                )
        return

    # Show Cold-Load Shimmer Skeletons or Warm-State Dimmed Charts while pipeline runs
    if cached_bundle is None:
        workspace_slot.markdown(render_shimmer_skeletons_html(symbol), unsafe_allow_html=True)
    elif is_warm_reload:
        with workspace_slot.container():
            _render_dashboard_workspace_content(
                st,
                components,
                cached_bundle,
                selected_ind,
                dimmed=True,
                key_suffix="warm_preview",
            )

    st.session_state["ql_is_running"] = True
    latest_telemetry: PipelineExecutionTelemetry | None = None

    def _on_telemetry(tel: PipelineExecutionTelemetry) -> None:
        nonlocal latest_telemetry
        latest_telemetry = tel
        status_slot.markdown(render_pipeline_status_card_html(tel), unsafe_allow_html=True)

    try:
        if cached_bundle is not None and last_params == current_params and st.session_state.get("ql_last_telemetry"):
            bundle = cached_bundle
            latest_telemetry = st.session_state["ql_last_telemetry"]
        else:
            bundle = build_dashboard_bundle(
                symbol=symbol,
                provider=provider,  # type: ignore[arg-type]
                timeframe=timeframe,
                bars=bars,
                indicator_name=selected_ind,
                n_surrogates=n_surr,
                seed=seed,
                telemetry_callback=_on_telemetry,
                is_warm_reload=is_warm_reload,
                restarted_with_updated_params=restarted_mid_run,
            )
            st.session_state["ql_last_bundle"] = bundle
            st.session_state["ql_last_params"] = current_params
            st.session_state["ql_last_telemetry"] = latest_telemetry
        st.session_state["ql_is_running"] = False
    except Exception as exc:
        st.session_state["ql_is_running"] = False
        workspace_slot.empty()
        if latest_telemetry is None or latest_telemetry.system_state != "error":
            err_tel = fail_telemetry(
                build_initial_telemetry(
                    symbol=symbol,
                    provider=provider,
                    timeframe=timeframe,
                    bars=bars,
                    indicator_name=selected_ind,
                    n_surrogates=n_surr,
                    seed=seed,
                ),
                error_step=1,
                error_message=str(exc),
                elapsed_seconds=0.0,
            )
            status_slot.markdown(render_pipeline_status_card_html(err_tel), unsafe_allow_html=True)
        with log_and_controls_slot:
            c_retry, c_reset, _ = st.columns([1, 1, 4])
            with c_retry:
                if st.button("🔄 Retry Run", key="ql_error_retry"):
                    st.rerun()
            with c_reset:
                if st.button("🎲 Reset to Default Seed (42)", key="ql_error_reset_seed"):
                    st.session_state["ql_seed_reset_value"] = 42
                    st.rerun()
        return

    # Post-Load Collapse into Compact Summary Bar + Expandable Execution Log
    if latest_telemetry is not None:
        status_slot.markdown(render_completed_summary_bar_html(latest_telemetry), unsafe_allow_html=True)
        with log_and_controls_slot, st.expander("Show Execution Log ▾", expanded=False):
            st.markdown(render_pipeline_status_card_html(latest_telemetry), unsafe_allow_html=True)
            if st.button("⏹️ Cancel / Clear Cached Run", key="ql_cancel_run_btn"):
                st.session_state["ql_cancel_requested"] = True
                st.rerun()

    with workspace_slot.container():
        _render_dashboard_workspace_content(
            st,
            components,
            bundle,
            selected_ind,
            dimmed=False,
            key_suffix="live",
        )


# Canonical aliases matching Spec-Kit Task T017 contract names
build_dashboard_state = build_dashboard_bundle
render_dashboard = render_streamlit_app


if __name__ == "__main__":
    render_streamlit_app()
