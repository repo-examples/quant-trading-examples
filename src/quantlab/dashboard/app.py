"""4-Quadrant Interactive Quant Diagnostic Dashboard (Streamlit + Plotly + TradingView Lightweight Charts)."""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from quantlab.data.loader import DataProvider, OHLCVDataset, fetch_ohlcv
from quantlab.indicators.custom_examples import reconstruct_phase_space_3d
from quantlab.indicators.registry import get_registry
from quantlab.proofs.stats_gate import (
    ProofSuiteResult,
    evaluate_multiple_indicators,
    run_proof_suite,
)
from quantlab.transpiler.pine_v6 import TranspilationArtifact, transpile_to_pine_v6

DARK_BG = "#0B0F19"
PANEL_BG = "#111827"
GRID_COLOR = "#1F2937"
CYAN = "#00F5D4"
MAGENTA = "#FF2A85"
AMBER = "#F59E0B"
EMERALD = "#10B981"
SLATE = "#94A3B8"


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
    timestamps = dataset.unix_timestamps.tolist()
    open_arr = np.nan_to_num(df["open"].to_numpy(dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    high_arr = np.nan_to_num(df["high"].to_numpy(dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    low_arr = np.nan_to_num(df["low"].to_numpy(dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    close_arr = np.nan_to_num(df["close"].to_numpy(dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    ind_arr = np.nan_to_num(proof.raw_series, nan=0.0, posinf=0.0, neginf=0.0)
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
            open_arr,
            high_arr,
            low_arr,
            close_arr,
            strict=False,
        )
    ]
    ind_points = [
        {"time": int(ts), "value": float(v)}
        for ts, v in zip(timestamps, ind_arr, strict=False)
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
    autoSize: true,
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


def build_dashboard_bundle(
    symbol: str = "SYNTH:COUPLED_OU",
    provider: DataProvider = "synthetic",
    timeframe: str = "1d",
    bars: int = 500,
    indicator_name: str = "KalmanFilter",
    custom_expr: str | None = None,
    n_surrogates: int = 30,
    seed: int = 42,
) -> DashboardBundle:
    """Compute and assemble all data, proofs, figures, and Pine Script v6 artifacts for the 4 quadrants."""
    dataset = fetch_ohlcv(
        symbol=symbol,
        provider=provider,
        timeframe=timeframe,
        bars=bars,
        seed=seed,
    )
    registry = get_registry()
    all_specs = registry.list_all()
    all_proofs = evaluate_multiple_indicators(
        specs=all_specs,
        dataset=dataset,
        n_surrogates=n_surrogates,
        seed=seed,
    )
    proof_map = {p.indicator_name.lower(): p for p in all_proofs}
    active_spec = registry.get(indicator_name)
    active_proof = proof_map.get(
        active_spec.name.lower(),
        run_proof_suite(active_spec, dataset, n_surrogates=n_surrogates, seed=seed),
    )

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


def run_dashboard_self_check() -> dict[str, object]:
    """Validate that all 4 Quadrants build cleanly in headless mode."""
    bundle = build_dashboard_bundle(
        symbol="SYNTH:COUPLED_OU",
        provider="synthetic",
        bars=300,
        indicator_name="KalmanFilter",
        n_surrogates=15,
        seed=42,
    )
    return {
        "status": "ok",
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

    with st.sidebar:
        st.header("🔬 Research Controls")
        provider = st.selectbox("Market Data Provider", ["synthetic", "yfinance", "ccxt"], index=0)
        default_sym = "SYNTH:COUPLED_OU" if provider == "synthetic" else ("SPY" if provider == "yfinance" else "BTC/USDT")
        symbol = st.text_input(
            "Symbol / Stochastic Process",
            value=default_sym,
            key=f"symbol_input_{provider}",
        )
        timeframe = st.selectbox("Timeframe", ["1d", "4h", "1h", "15m"], index=0)
        bars = int(st.slider("PIT History Bars", min_value=200, max_value=2000, value=600, step=100))
        selected_ind = st.selectbox("Active Indicator", indicator_names, index=indicator_names.index("KalmanFilter"))
        n_surr = int(st.slider("Monte Carlo Surrogates", min_value=15, max_value=100, value=30, step=5))
        seed = int(st.number_input("Deterministic Seed", value=42, step=1))

    bundle = build_dashboard_bundle(
        symbol=symbol,
        provider=provider,  # type: ignore[arg-type]
        timeframe=timeframe,
        bars=bars,
        indicator_name=selected_ind,
        n_surrogates=n_surr,
        seed=seed,
    )

    p = bundle.active_proof
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("FracDiff d* (ADF p)", f"d*={p.stationarity.d_optimal:.2f}", f"p={p.stationarity.p_value:.4f}")
    col2.metric("Transfer Entropy TE(X->R)", f"{p.entropy.symbolic_te:.5f}", f"Z={p.entropy.z_score:.2f} (p={p.entropy.p_value:.3f})")
    col3.metric("Max |Spearman Rank IC|", f"{p.stats_gate.max_abs_ic:.4f}", f"Horizon h={p.stats_gate.best_horizon}")
    col4.metric("Baseline Orthogonality VIF", f"{p.stats_gate.vif_score:.2f}", "PASS (<5.0)" if p.stats_gate.vif_passed else "HIGH")
    col5.metric("DSP Phase Lag / Jerk", f"{p.dsp.mean_phase_lag_bars:.2f} bars", f"Jerk={p.dsp.jerk_energy:.3f}")

    tab_q1, tab_q2, tab_q3, tab_q4 = st.tabs(
        [
            "📐 Q1: OHLCV Canvas & 3D Phase-Space",
            "🔀 Q2: Entropy & Surrogate Proofs",
            "📊 Q3: Statistical & DSP Pareto Frontier",
            "⚙️ Q4: SymPy AST & Pine Script v6 Studio",
        ]
    )

    with tab_q1:
        st.subheader("TradingView Lightweight Charts HTML5 Canvas")
        components.html(bundle.lightweight_charts_html, height=440)
        q1_left, q1_right = st.columns(2)
        with q1_left:
            st.plotly_chart(bundle.fig_q1_ohlcv, use_container_width=True)
        with q1_right:
            st.plotly_chart(bundle.fig_q1_phase_space, use_container_width=True)

    with tab_q2:
        q2_left, q2_right = st.columns(2)
        with q2_left:
            st.plotly_chart(bundle.fig_q2_rolling_entropy, use_container_width=True)
        with q2_right:
            st.plotly_chart(bundle.fig_q2_surrogates, use_container_width=True)

    with tab_q3:
        q3_top_l, q3_top_r = st.columns(2)
        with q3_top_l:
            st.plotly_chart(bundle.fig_q3_ic_vif, use_container_width=True)
        with q3_top_r:
            st.plotly_chart(bundle.fig_q3_wasserstein, use_container_width=True)
        st.plotly_chart(bundle.fig_q3_pareto_bode, use_container_width=True)

    with tab_q4:
        st.subheader("Live Neuro-Symbolic SymPy AST Editor -> TradingView Pine Script v6")
        active_spec = reg.get(selected_ind)
        default_formula = str(active_spec.symbolic_ast())
        expr_input = st.text_input("Symbolic Expression (SymPy AST):", value=default_formula)
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
            st.latex(f"\\mathcal{{I}}_t = {live_art.latex_expr}")
            c_pine, c_card = st.columns(2)
            with c_pine:
                st.markdown("#### Generated Pine Script v6 (`//@version=6`)")
                st.code(live_art.pine_code, language="pine")
                st.download_button(
                    "⬇️ Download Pine Script v6 (.pine)",
                    data=live_art.pine_code,
                    file_name=f"{live_art.indicator_name.lower()}_v6.pine",
                    mime="text/plain",
                )
            with c_card:
                st.markdown("#### Auditable Markdown Research Card")
                st.markdown(live_art.research_card_md)
                st.download_button(
                    "⬇️ Download Research Card (.md)",
                    data=live_art.research_card_md,
                    file_name=f"{live_art.indicator_name.lower()}_research_card.md",
                    mime="text/markdown",
                )
        except Exception as exc:
            st.error(f"Symbolic AST Transpilation Error: {exc}")


# Canonical aliases matching Spec-Kit Task T017 contract names
build_dashboard_state = build_dashboard_bundle
render_dashboard = render_streamlit_app


if __name__ == "__main__":
    render_streamlit_app()
