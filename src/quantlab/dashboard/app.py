"""4-Quadrant Interactive Quant Diagnostic Dashboard (Streamlit + Plotly + TradingView Lightweight Charts)."""

from __future__ import annotations

import html
import json
import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from quantlab.dashboard.chart_help import (
    CHART_HELP_REGISTRY,
    SPEC_HELP_ID,
    ChartHelpEntry,
    build_chart_help_css,
    get_chart_help,
    render_chart_header,
    render_chart_help_popover_html,
)
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
    render_insufficient_history_html,
    render_pipeline_status_card_html,
    render_shimmer_skeletons_html,
    render_warm_dimmed_banner_html,
    update_surrogate_telemetry,
)
from quantlab.data.loader import (
    HIGHER_TIMEFRAME_PILLS,
    MIN_PROOF_BARS,
    UI_TIMEFRAMES,
    DataProvider,
    InsufficientHistoryError,
    OHLCVDataset,
    fetch_ohlcv,
    get_timeframe_spec,
    normalize_timeframe,
    validate_minimum_proof_bars,
)
from quantlab.indicators.custom_examples import reconstruct_phase_space_3d
from quantlab.indicators.registry import get_registry
from quantlab.proofs.dsp import DSPResult, identify_pareto_frontier
from quantlab.proofs.stats_gate import (
    ProofSuiteResult,
    run_proof_suite,
)
from quantlab.transpiler.pine_v6 import TranspilationArtifact, transpile_to_pine_v6

SPEC_TV_ID = "SPEC-CHART-TV-01"
SPEC_TF_ID = "SPEC-CTRL-TF-02"

DARK_BG = "#0E1117"
PANEL_BG = "#111827"
GRID_COLOR = "#1E222D"
CYAN = "#00F5D4"
MAGENTA = "#FF2E93"
AMBER = "#F59E0B"
EMERALD = "#10B981"
SLATE = "#94A3B8"
AXIS_TEXT = "#9CA3AF"

__all__ = [
    "CHART_HELP_REGISTRY",
    "DARK_BG",
    "HIGHER_TIMEFRAME_PILLS",
    "MIN_PROOF_BARS",
    "SPEC_HELP_ID",
    "SPEC_ID",
    "SPEC_TF_ID",
    "SPEC_TV_ID",
    "UI_TIMEFRAMES",
    "ChartHelpEntry",
    "DashboardBundle",
    "InsufficientHistoryError",
    "PipelineCancelledError",
    "PipelineExecutionTelemetry",
    "PipelineStageStatus",
    "advance_telemetry_stage",
    "build_chart_help_css",
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
    "get_chart_help",
    "is_long_running_load",
    "render_chart_header",
    "render_chart_help_popover_html",
    "render_completed_summary_bar_html",
    "render_dashboard",
    "render_insufficient_history_html",
    "render_pipeline_status_card_html",
    "render_shimmer_skeletons_html",
    "render_streamlit_app",
    "render_warm_dimmed_banner_html",
    "run_dashboard_self_check",
    "serialize_lightweight_charts_series",
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


def serialize_lightweight_charts_series(
    dataset: OHLCVDataset,
    indicator_series: np.ndarray,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Serialize PIT OHLCV bars and indicator values per SPEC-CHART-TV-01.

    - Calendar intervals (`1D`, `1W`, `1M`, `3M`) emit unique ascending `"YYYY-MM-DD"` strings.
    - Intraday intervals (`1m`, `5m`, `15m`, `1h`, `4h`) emit strictly increasing UTC Unix seconds.
    - Non-finite (`NaN`/`Inf`) indicator warm-up bars emit whitespace dicts `{"time": bar_time}`
      without coercing warm-up bars to `0.0` or `null`.
    """
    df = dataset.df
    if df.empty:
        return [], []

    try:
        is_calendar = get_timeframe_spec(dataset.canonical_timeframe).is_calendar_date
    except ValueError:
        is_calendar = dataset.canonical_timeframe in ("1D", "1W", "1M", "3M")

    raw_times: list[str | int] = (
        dataset.calendar_dates if is_calendar else [int(t) for t in dataset.unix_timestamps.tolist()]
    )

    open_arr = df["open"].to_numpy(dtype=np.float64)
    high_arr = df["high"].to_numpy(dtype=np.float64)
    low_arr = df["low"].to_numpy(dtype=np.float64)
    close_arr = df["close"].to_numpy(dtype=np.float64)

    ind_arr = np.asarray(indicator_series, dtype=np.float64).reshape(-1)
    n_rows = len(df)
    if len(ind_arr) < n_rows:
        padded = np.full(n_rows, np.nan, dtype=np.float64)
        padded[-len(ind_arr) :] = ind_arr
        ind_arr = padded
    elif len(ind_arr) > n_rows:
        ind_arr = ind_arr[-n_rows:]

    dedup_candles: dict[str | int, dict[str, object]] = {}
    dedup_ind: dict[str | int, dict[str, object]] = {}

    for t_key, o_val, h_val, l_val, c_val, i_val in zip(
        raw_times,
        open_arr,
        high_arr,
        low_arr,
        close_arr,
        ind_arr,
        strict=False,
    ):
        if not (np.isfinite(o_val) and np.isfinite(h_val) and np.isfinite(l_val) and np.isfinite(c_val)):
            continue
        dedup_candles[t_key] = {
            "time": t_key,
            "open": float(o_val),
            "high": float(h_val),
            "low": float(l_val),
            "close": float(c_val),
        }
        if np.isfinite(i_val):
            dedup_ind[t_key] = {"time": t_key, "value": float(i_val)}
        else:
            dedup_ind[t_key] = {"time": t_key}

    sorted_keys = sorted(dedup_candles.keys())
    candles = [dedup_candles[k] for k in sorted_keys]
    ind_points = [dedup_ind[k] for k in sorted_keys]
    return candles, ind_points


def build_lightweight_charts_canvas_html(
    dataset: OHLCVDataset,
    proof: ProofSuiteResult,
    overlay: bool = False,
    height: int = 420,
) -> str:
    """Build an interactive HTML5 TradingView Lightweight Charts canvas (SPEC-CHART-TV-01)."""
    candles, ind_points = serialize_lightweight_charts_series(dataset, proof.raw_series)
    tf_label = dataset.canonical_timeframe
    try:
        is_intraday = not get_timeframe_spec(tf_label).is_calendar_date
    except ValueError:
        is_intraday = tf_label not in ("1D", "1W", "1M", "3M")

    if candles:
        start_str = dataset.df.index[0].strftime("%Y-%m-%d")
        end_str = dataset.df.index[-1].strftime("%Y-%m-%d")
        last_close = float(candles[-1]["close"])  # type: ignore[arg-type]
        aria_label = (
            f"TradingView OHLCV and {proof.indicator_name} chart for {dataset.symbol} on "
            f"{tf_label} timeframe, {len(candles)} bars from {start_str} to {end_str}, "
            f"latest close {last_close:.2f}"
        )
    else:
        aria_label = (
            f"Empty TradingView OHLCV chart state for {dataset.symbol} on {tf_label} timeframe "
            f"(0 valid bars)"
        )

    aria_esc = html.escape(aria_label)
    sym_esc = html.escape(dataset.symbol)
    tf_esc = html.escape(tf_label)
    ind_esc = html.escape(proof.indicator_name)

    candles_json = json.dumps(candles)
    ind_json = json.dumps(ind_points)
    sym_js = json.dumps(dataset.symbol)
    tf_js = json.dumps(tf_label)
    ind_js = json.dumps(proof.indicator_name)
    is_overlay_js = "true" if overlay else "false"
    is_intraday_js = "true" if is_intraday else "false"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<script src="https://unpkg.com/lightweight-charts@4.2.1/dist/lightweight-charts.standalone.production.js"></script>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 0;
    background-color: {DARK_BG};
    color: #F8FAFC;
    font-family: "JetBrains Mono", "Source Code Pro", Consolas, monospace;
    overflow: hidden;
  }}
  #tv-wrapper {{
    position: relative;
    width: 100%;
    height: {height}px;
    background-color: {DARK_BG};
    border: 1px solid #2D313E;
    border-radius: 10px;
    overflow: hidden;
  }}
  #tv-chart {{
    width: 100%;
    height: 100%;
  }}
  #tv-legend {{
    position: absolute;
    top: 10px;
    left: 64px;
    z-index: 10;
    pointer-events: none;
    background: rgba(14, 17, 23, 0.82);
    border: 1px solid rgba(55, 65, 81, 0.75);
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11.5px;
    line-height: 16px;
    color: #E5E7EB;
    max-width: calc(100% - 140px);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .tv-state-card {{
    display: none;
    width: 100%;
    height: 100%;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 24px;
    background-color: #161922;
    color: #E5E7EB;
    font-size: 13.5px;
    line-height: 20px;
  }}
  .tv-state-card-inner {{
    max-width: 480px;
    border: 1px solid #374151;
    border-radius: 10px;
    padding: 18px 22px;
    background-color: {DARK_BG};
  }}
  .tv-state-title {{
    color: #FCA5A5;
    font-weight: 700;
    margin-bottom: 6px;
  }}
  @media (max-width: 1023px) {{
    #tv-wrapper {{ height: 360px; }}
  }}
  @media (max-width: 767px) {{
    #tv-wrapper {{ height: 300px; }}
    #tv-legend {{ left: 10px; max-width: calc(100% - 76px); font-size: 10.5px; }}
  }}
</style>
</head>
<body>
<div id="tv-wrapper" role="img" aria-label="{aria_esc}" data-spec-id="{SPEC_TV_ID}">
  <div id="tv-legend" aria-hidden="true">{sym_esc} • {tf_esc} • {ind_esc}</div>
  <div id="tv-chart"></div>
  <div id="tv-empty-state" class="tv-state-card" role="status">
    <div class="tv-state-card-inner">
      <div class="tv-state-title">No Renderable Market Bars</div>
      <div id="tv-empty-copy">No market data returned for {sym_esc} on {tf_esc}. Check the ticker symbol or switch provider.</div>
    </div>
  </div>
</div>
<script>
(function() {{
  const candles = {candles_json};
  const indPoints = {ind_json};
  const sym = {sym_js};
  const tf = {tf_js};
  const indName = {ind_js};
  const isOverlay = {is_overlay_js};
  const isIntraday = {is_intraday_js};

  const container = document.getElementById('tv-chart');
  const legendEl = document.getElementById('tv-legend');
  const emptyEl = document.getElementById('tv-empty-state');
  const emptyCopyEl = document.getElementById('tv-empty-copy');

  function showDiagnosticState(titleText, bodyText) {{
    container.style.display = 'none';
    legendEl.style.display = 'none';
    emptyEl.style.display = 'flex';
    const titleNode = emptyEl.querySelector('.tv-state-title');
    if (titleNode && titleText) titleNode.textContent = titleText;
    if (emptyCopyEl && bodyText) emptyCopyEl.textContent = bodyText;
  }}

  if (!Array.isArray(candles) || candles.length === 0) {{
    showDiagnosticState(
      'No Market Data Returned',
      'No market data returned for ' + sym + ' on ' + tf + '. Check the ticker symbol or switch provider.'
    );
    return;
  }}

  if (typeof LightweightCharts === 'undefined' || !LightweightCharts.createChart) {{
    showDiagnosticState(
      'Chart Renderer Unavailable',
      'Chart renderer failed to mount (LightweightCharts library unavailable offline). Inspect Q1A Plotly canvas below.'
    );
    return;
  }}

  try {{
    const isTouchOrMobile = window.matchMedia && window.matchMedia('(pointer: coarse), (max-width: 768px)').matches;
    const isNarrowMobile = window.innerWidth > 0 && window.innerWidth < 768;

    const chart = LightweightCharts.createChart(container, {{
      autoSize: true,
      layout: {{
        background: {{ type: 'solid', color: '{DARK_BG}' }},
        textColor: '{AXIS_TEXT}'
      }},
      grid: {{
        vertLines: {{ color: '{GRID_COLOR}' }},
        horzLines: {{ color: '{GRID_COLOR}' }}
      }},
      crosshair: {{ mode: 0 }},
      rightPriceScale: {{
        borderColor: '#334155',
        scaleMargins: isNarrowMobile && !isOverlay ? {{ top: 0.06, bottom: 0.34 }} : {{ top: 0.08, bottom: 0.08 }}
      }},
      leftPriceScale: {{
        visible: !isOverlay && !isNarrowMobile,
        borderColor: '#334155'
      }},
      handleScroll: {{
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: !isTouchOrMobile
      }},
      timeScale: {{
        borderColor: '#334155',
        timeVisible: isIntraday,
        secondsVisible: false,
        minBarSpacing: 2
      }}
    }});

    const candleSeries = chart.addCandlestickSeries({{
      upColor: '{EMERALD}',
      downColor: '{MAGENTA}',
      borderUpColor: '{EMERALD}',
      borderDownColor: '{MAGENTA}',
      wickUpColor: '{EMERALD}',
      wickDownColor: '{MAGENTA}'
    }});
    candleSeries.setData(candles);

    const indScaleId = isOverlay ? 'right' : (isNarrowMobile ? 'ind_mobile' : 'left');
    const indSeries = chart.addLineSeries({{
      color: '{CYAN}',
      lineWidth: 2,
      title: indName,
      priceScaleId: indScaleId
    }});
    if (indScaleId === 'ind_mobile') {{
      chart.priceScale('ind_mobile').applyOptions({{
        scaleMargins: {{ top: 0.70, bottom: 0.04 }},
        borderVisible: false
      }});
    }}
    indSeries.setData(indPoints);
    chart.timeScale().fitContent();

    function formatLegend(bar, indVal) {{
      if (!bar) return;
      const o = Number(bar.open).toFixed(2);
      const h = Number(bar.high).toFixed(2);
      const l = Number(bar.low).toFixed(2);
      const c = Number(bar.close).toFixed(2);
      const indTxt = (indVal !== undefined && indVal !== null && Number.isFinite(Number(indVal)))
        ? Number(indVal).toFixed(4)
        : 'warm-up';
      legendEl.textContent = sym + ' • ' + tf + ' • O: ' + o + ' H: ' + h + ' L: ' + l + ' C: ' + c + ' • ' + indName + ': ' + indTxt;
    }}

    const lastBar = candles[candles.length - 1];
    let lastFiniteInd = undefined;
    for (let i = indPoints.length - 1; i >= 0; i--) {{
      if (indPoints[i] && indPoints[i].value !== undefined) {{
        lastFiniteInd = indPoints[i].value;
        break;
      }}
    }}
    formatLegend(lastBar, lastFiniteInd);

    chart.subscribeCrosshairMove(function(param) {{
      if (!param || !param.time || !param.seriesData) {{
        formatLegend(lastBar, lastFiniteInd);
        return;
      }}
      const cData = param.seriesData.get(candleSeries);
      const iData = param.seriesData.get(indSeries);
      if (cData) {{
        formatLegend(cData, iData && iData.value !== undefined ? iData.value : undefined);
      }}
    }});

    if (typeof ResizeObserver !== 'undefined') {{
      const ro = new ResizeObserver(function(entries) {{
        for (const entry of entries) {{
          const cr = entry.contentRect;
          if (cr.width > 0 && cr.height > 0) {{
            chart.applyOptions({{ width: Math.floor(cr.width), height: Math.floor(cr.height) }});
          }}
        }}
      }});
      ro.observe(container);
    }}
  }} catch (err) {{
    showDiagnosticState(
      'Chart Render Error',
      'Chart renderer failed to mount (' + (err && err.message ? err.message : String(err)) + ').'
    );
  }}
}})();
</script>
</body>
</html>"""


def _apply_dark_theme(
    fig: go.Figure,
    title: str,
    height: int = 420,
    show_title: bool = False,
) -> go.Figure:
    """Apply QuantLab dark tokens and collision-free legend/margin geometry (SPEC-UI-HELP-03)."""
    fig.update_layout(
        title={"text": title, "font": {"size": 15, "color": "#F8FAFC"}} if show_title else None,
        meta={"chart_title": title},
        template="plotly_dark",
        paper_bgcolor=DARK_BG,
        plot_bgcolor=PANEL_BG,
        font={"family": "JetBrains Mono, Consolas, monospace", "color": "#CBD5E1", "size": 11},
        height=height,
        margin={"l": 48, "r": 20, "t": 56, "b": 40},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.06,
            "xanchor": "left",
            "x": 0.0,
        },
    )
    return fig


def build_q1_figures(
    dataset: OHLCVDataset,
    proof: ProofSuiteResult,
    overlay: bool = False,
    phase_delay: int = 3,
    show_title: bool = False,
) -> tuple[go.Figure, go.Figure]:
    """Build Q1 Figures: (1) OHLCV + Indicator Canvas and (2) 3D Takens Phase-Space Attractor."""
    df = dataset.df
    fig_ohlcv = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.07,
        row_heights=[0.62, 0.38],
        subplot_titles=(
            f"{dataset.symbol} ({dataset.canonical_timeframe}) OHLCV & FracDiff (d*={proof.stationarity.d_optimal:.2f})",
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
    _apply_dark_theme(
        fig_ohlcv,
        f"Q1A — Causal Point-in-Time Market & Indicator Canvas ({dataset.symbol})",
        height=460,
        show_title=show_title,
    )

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
        show_title=show_title,
    )
    return fig_ohlcv, fig_phase


def build_q2_figures(
    dataset: OHLCVDataset,
    proof: ProofSuiteResult,
    show_title: bool = False,
) -> tuple[go.Figure, go.Figure]:
    """Build Q2 Figures: (1) Rolling Shannon Entropy & Rolling Rank IC and (2) Surrogate TE Null Distribution."""
    df = dataset.df
    en = proof.entropy
    sg = proof.stats_gate

    fig_ent = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.09,
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
    _apply_dark_theme(
        fig_ent,
        "Q2A — Causal Rolling Information Dynamics",
        height=430,
        show_title=show_title,
    )

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
        show_title=show_title,
    )
    return fig_ent, fig_surr


def build_q3_figures(
    dataset: OHLCVDataset,
    proof: ProofSuiteResult,
    all_proofs: list[ProofSuiteResult],
    show_title: bool = False,
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
        horizontal_spacing=0.10,
        subplot_titles=(
            "Multi-Horizon Spearman Rank IC Decay",
            f"Baseline Orthogonality (VIF={sg.vif_score:.2f})",
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
    _apply_dark_theme(
        fig_ic_vif,
        "Q3A — Predictive Rank IC Decay & Baseline Orthogonality",
        height=390,
        show_title=show_title,
    )

    # Wasserstein Bull vs Bear Regime Separation (with deuteranopia/protanopia border + hatch cues)
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
            marker={
                "color": EMERALD,
                "line": {"color": "#A7F3D0", "width": 1.4},
                "pattern": {"shape": ""},
            },
            opacity=0.65,
            histnorm="probability density",
        )
    )
    fig_wass.add_trace(
        go.Histogram(
            x=bear_vals,
            name="Bear / High-Vol Regime",
            marker={
                "color": MAGENTA,
                "line": {"color": "#FBCFE8", "width": 1.6},
                "pattern": {"shape": "/"},
            },
            opacity=0.62,
            histnorm="probability density",
        )
    )
    fig_wass.update_layout(barmode="overlay")
    _apply_dark_theme(
        fig_wass,
        f"Q3B — Regime Distribution Separation (Wasserstein W1 = {sg.wasserstein_regime_distance:.4f})",
        height=390,
        show_title=show_title,
    )

    # Bode Phase-Lag vs Jerk Pareto Frontier + Active Bode Magnitude/Phase
    fig_dsp = make_subplots(
        rows=1,
        cols=2,
        horizontal_spacing=0.10,
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
                    "line": {
                        "width": 2,
                        "color": MAGENTA if r.indicator_name == proof.indicator_name else "#FFFFFF",
                    },
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
    _apply_dark_theme(
        fig_dsp,
        "Q3C — DSP Hilbert Phase-Lag vs. Smoothness (Jerk) Frontier",
        height=410,
        show_title=show_title,
    )

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
    timeframe: str = "1D",
    bars: int = 500,
    indicator_name: str = "KalmanFilter",
    custom_expr: str | None = None,
    n_surrogates: int = 30,
    seed: int = 42,
    telemetry_callback: Callable[[PipelineExecutionTelemetry], None] | None = None,
    is_warm_reload: bool = False,
    restarted_with_updated_params: bool = False,
    cancel_check: Callable[[], bool] | None = None,
    fallback_to_synthetic: bool = True,
) -> DashboardBundle:
    """Compute and assemble all data, proofs, figures, and Pine Script v6 artifacts for the 4 quadrants.

    Emits SPEC-QUANT-LOAD-01 4-stage telemetry snapshots when `telemetry_callback` is provided
    and enforces SPEC-CTRL-TF-02 `MIN_PROOF_BARS = 35` before executing stationarity/entropy proofs.
    """
    t0 = time.perf_counter()
    canonical_tf = normalize_timeframe(timeframe)
    effective_surrogates = max(10, int(n_surrogates))
    telemetry = build_initial_telemetry(
        symbol=symbol,
        provider=provider,
        timeframe=canonical_tf,
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

    # Stage 1 (0% -> 20%): Synthesizing / Fetching Market Data + Minimum Sample Guard
    _emit(telemetry)
    _check_cancel(telemetry)
    t_stage1 = time.perf_counter()
    try:
        dataset = fetch_ohlcv(
            symbol=symbol,
            provider=provider,
            timeframe=canonical_tf,
            bars=bars,
            seed=seed,
            fallback_to_synthetic=fallback_to_synthetic,
        )
        validate_minimum_proof_bars(
            dataset=dataset,
            min_bars=MIN_PROOF_BARS,
            indicator_name=indicator_name,
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
        fig_q1_ohlcv, fig_q1_phase = build_q1_figures(
            dataset,
            active_proof,
            overlay=active_spec.overlay,
            show_title=False,
        )
        fig_q2_ent, fig_q2_surr = build_q2_figures(dataset, active_proof, show_title=False)
        fig_q3_ic, fig_q3_wass, fig_q3_dsp = build_q3_figures(
            dataset,
            active_proof,
            all_proofs,
            show_title=False,
        )
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
    timeframe: str = "1D",
    bars: int = 500,
    indicator_name: str = "KalmanFilter",
    custom_expr: str | None = None,
    n_surrogates: int = 30,
    seed: int = 42,
    is_warm_reload: bool = False,
    restarted_with_updated_params: bool = False,
    cancel_check: Callable[[], bool] | None = None,
    fallback_to_synthetic: bool = True,
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
        fallback_to_synthetic=fallback_to_synthetic,
    )
    return bundle, snapshots


def run_dashboard_self_check() -> dict[str, object]:
    """Validate all 4 Quadrants, SPEC-QUANT-LOAD-01, SPEC-CHART-TV-01, SPEC-CTRL-TF-02, and SPEC-UI-HELP-03."""
    bundle, snapshots = build_dashboard_bundle_with_telemetry(
        symbol="SYNTH:COUPLED_OU",
        provider="synthetic",
        timeframe="1D",
        bars=300,
        indicator_name="KalmanFilter",
        n_surrogates=15,
        seed=42,
    )
    final_snap = snapshots[-1]

    verified_tfs: list[str] = ["1D"]
    for htf in ("1W", "1M", "3M"):
        ds_htf = fetch_ohlcv(
            symbol="SYNTH:COUPLED_OU",
            provider="synthetic",
            timeframe=htf,
            bars=80,
            seed=42,
        )
        c_pts, i_pts = serialize_lightweight_charts_series(ds_htf, bundle.active_proof.raw_series[:80])
        if len(c_pts) == 80 and len(i_pts) == 80 and isinstance(c_pts[0]["time"], str):
            verified_tfs.append(htf)

    return {
        "status": "ok",
        "loading_spec_id": final_snap.spec_id,
        "tv_chart_spec_id": SPEC_TV_ID,
        "timeframe_spec_id": SPEC_TF_ID,
        "chart_help_spec_id": SPEC_HELP_ID,
        "telemetry_snapshots_count": len(snapshots),
        "telemetry_stages_verified": len(final_snap.stages),
        "final_progress_pct": final_snap.overall_progress_pct,
        "symbol": bundle.dataset.symbol,
        "timeframe": bundle.dataset.canonical_timeframe,
        "supported_timeframes": list(UI_TIMEFRAMES),
        "higher_timeframes_verified": verified_tfs,
        "chart_help_panels_registered": len(CHART_HELP_REGISTRY),
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


def _render_q1_timeframe_quick_switcher(
    st: object,
    active_timeframe: str,
    key_suffix: str,
    disabled: bool = False,
) -> None:
    """Render the synced SPEC-CTRL-TF-02 higher-timeframe quick-switcher (`1D | 1W | 1M | 3M`) above Q1."""
    if hasattr(st, "pills"):
        default_pill = active_timeframe if active_timeframe in HIGHER_TIMEFRAME_PILLS else None
        chosen = st.pills(  # type: ignore[attr-defined]
            "Higher Timeframe Quick-Switch",
            options=list(HIGHER_TIMEFRAME_PILLS),
            default=default_pill,
            key=f"ql_q1_tf_pills_{key_suffix}_{active_timeframe}",
            disabled=disabled,
            label_visibility="collapsed",
        )
        if chosen and chosen != active_timeframe and not disabled:
            st.session_state["ql_timeframe"] = chosen  # type: ignore[attr-defined]
            st.rerun()  # type: ignore[attr-defined]
    else:  # pragma: no cover
        cols = st.columns(len(HIGHER_TIMEFRAME_PILLS))  # type: ignore[attr-defined]
        for col, tf_opt in zip(cols, HIGHER_TIMEFRAME_PILLS, strict=False):
            with col:
                if (
                    st.button(  # type: ignore[attr-defined]
                        tf_opt,
                        key=f"ql_q1_btn_{tf_opt}_{key_suffix}",
                        disabled=disabled or tf_opt == active_timeframe,
                        use_container_width=True,
                    )
                    and not disabled
                ):
                    st.session_state["ql_timeframe"] = tf_opt  # type: ignore[attr-defined]
                    st.rerun()  # type: ignore[attr-defined]


def _render_dashboard_workspace_content(
    st: object,
    components: object,
    bundle: DashboardBundle,
    selected_ind: str,
    dimmed: bool = False,
    key_suffix: str = "live",
) -> None:
    """Render the 5 KPI cards and 4 Diagnostic Quadrants with SPEC-UI-HELP-03 headers."""
    if dimmed:
        st.markdown('<div class="ql-warm-dimmed">', unsafe_allow_html=True)  # type: ignore[attr-defined]

    ds = bundle.dataset
    p = bundle.active_proof
    tf_lbl = ds.canonical_timeframe
    ctx_base = f"{ds.symbol} • {tf_lbl} • {p.indicator_name}"

    col1, col2, col3, col4, col5 = st.columns(5)  # type: ignore[attr-defined]
    col1.metric(
        "FracDiff d* (ADF p)",
        f"d*={p.stationarity.d_optimal:.2f}",
        f"p={p.stationarity.p_value:.4f}",
    )
    col2.metric(
        "Transfer Entropy TE(X->R)",
        f"{p.entropy.symbolic_te:.5f}",
        f"Z={p.entropy.z_score:.2f} (p={p.entropy.p_value:.3f})",
    )
    col3.metric(
        "Max |Spearman Rank IC|",
        f"{p.stats_gate.max_abs_ic:.4f}",
        f"Horizon h={p.stats_gate.best_horizon}",
    )
    col4.metric(
        "Baseline Orthogonality VIF",
        f"{p.stats_gate.vif_score:.2f}",
        "PASS (<5.0)" if p.stats_gate.vif_passed else "HIGH",
    )
    col5.metric(
        "DSP Phase Lag / Jerk",
        f"{p.dsp.mean_phase_lag_bars:.2f} bars",
        f"Jerk={p.dsp.jerk_energy:.3f}",
    )

    tab_q1, tab_q2, tab_q3, tab_q4 = st.tabs(  # type: ignore[attr-defined]
        [
            "📐 Q1: OHLCV Canvas & 3D Phase-Space",
            "🔀 Q2: Entropy & Surrogate Proofs",
            "📊 Q3: Statistical & DSP Pareto Frontier",
            "⚙️ Q4: SymPy AST & Pine Script v6 Studio",
        ]
    )

    with tab_q1:
        _render_q1_timeframe_quick_switcher(
            st,
            active_timeframe=tf_lbl,
            key_suffix=key_suffix,
            disabled=dimmed,
        )
        render_chart_header(
            st,
            chart_id="TV-01",
            title="TradingView Lightweight Charts HTML5 Canvas",
            indicator_name=p.indicator_name,
            context_summary=f"{ctx_base} • {ds.n_bars} bars",
            badge_text=f"{tf_lbl} • {ds.n_bars} bars",
            key_suffix=f"tv01_{key_suffix}",
        )
        components.html(bundle.lightweight_charts_html, height=432)  # type: ignore[attr-defined]

        q1_left, q1_right = st.columns(2)  # type: ignore[attr-defined]
        with q1_left:
            render_chart_header(
                st,
                chart_id="Q1A",
                title=f"Q1A — Causal Point-in-Time Market & Indicator Canvas ({ds.symbol})",
                indicator_name=p.indicator_name,
                context_summary=f"{ctx_base} • d*={p.stationarity.d_optimal:.2f}",
                badge_text=f"d*={p.stationarity.d_optimal:.2f}",
                key_suffix=f"q1a_{key_suffix}",
            )
            st.plotly_chart(  # type: ignore[attr-defined]
                bundle.fig_q1_ohlcv,
                use_container_width=True,
                key=f"q1_ohlcv_{key_suffix}",
            )
        with q1_right:
            render_chart_header(
                st,
                chart_id="Q1B",
                title=f"Q1B — 3D Takens Phase-Space Attractor ({p.indicator_name}, tau=3)",
                indicator_name=p.indicator_name,
                context_summary=f"{ctx_base} • tau=3",
                badge_text="tau=3",
                key_suffix=f"q1b_{key_suffix}",
            )
            st.plotly_chart(  # type: ignore[attr-defined]
                bundle.fig_q1_phase_space,
                use_container_width=True,
                key=f"q1_phase_{key_suffix}",
            )

    with tab_q2:
        q2_left, q2_right = st.columns(2)  # type: ignore[attr-defined]
        with q2_left:
            render_chart_header(
                st,
                chart_id="Q2A",
                title="Q2A — Causal Rolling Information Dynamics",
                indicator_name=p.indicator_name,
                context_summary=f"{ctx_base} • H={p.entropy.shannon_entropy:.3f} nats",
                badge_text=f"H={p.entropy.shannon_entropy:.2f}",
                key_suffix=f"q2a_{key_suffix}",
            )
            st.plotly_chart(  # type: ignore[attr-defined]
                bundle.fig_q2_rolling_entropy,
                use_container_width=True,
                key=f"q2_ent_{key_suffix}",
            )
        with q2_right:
            te_status = "PASS" if p.entropy.passed else "FAIL"
            render_chart_header(
                st,
                chart_id="Q2B",
                title=f"Q2B — Transfer Entropy TE(X -> R) vs Monte Carlo Surrogates ({te_status})",
                indicator_name=p.indicator_name,
                context_summary=f"{ctx_base} • Z={p.entropy.z_score:.2f} • p={p.entropy.p_value:.4f}",
                badge_text=te_status,
                key_suffix=f"q2b_{key_suffix}",
            )
            st.plotly_chart(  # type: ignore[attr-defined]
                bundle.fig_q2_surrogates,
                use_container_width=True,
                key=f"q2_surr_{key_suffix}",
            )

    with tab_q3:
        q3_top_l, q3_top_r = st.columns(2)  # type: ignore[attr-defined]
        with q3_top_l:
            render_chart_header(
                st,
                chart_id="Q3A",
                title="Q3A — Predictive Rank IC Decay & Baseline Orthogonality",
                indicator_name=p.indicator_name,
                context_summary=f"{ctx_base} • Max |IC|={p.stats_gate.max_abs_ic:.4f} • VIF={p.stats_gate.vif_score:.2f}",
                badge_text=f"VIF={p.stats_gate.vif_score:.2f}",
                key_suffix=f"q3a_{key_suffix}",
            )
            st.plotly_chart(  # type: ignore[attr-defined]
                bundle.fig_q3_ic_vif,
                use_container_width=True,
                key=f"q3_ic_{key_suffix}",
            )
        with q3_top_r:
            render_chart_header(
                st,
                chart_id="Q3B",
                title=f"Q3B — Regime Distribution Separation (Wasserstein W1 = {p.stats_gate.wasserstein_regime_distance:.4f})",
                indicator_name=p.indicator_name,
                context_summary=f"{ctx_base} • W1={p.stats_gate.wasserstein_regime_distance:.4f}",
                badge_text=f"W1={p.stats_gate.wasserstein_regime_distance:.3f}",
                key_suffix=f"q3b_{key_suffix}",
            )
            st.plotly_chart(  # type: ignore[attr-defined]
                bundle.fig_q3_wasserstein,
                use_container_width=True,
                key=f"q3_wass_{key_suffix}",
            )

        pareto_lbl = "Pareto-Optimal" if p.dsp.pareto_optimal else "Dominated"
        render_chart_header(
            st,
            chart_id="Q3C",
            title="Q3C — DSP Hilbert Phase-Lag vs. Smoothness (Jerk) Frontier",
            indicator_name=p.indicator_name,
            context_summary=f"{ctx_base} • Lag={p.dsp.mean_phase_lag_bars:.2f}b • Jerk={p.dsp.jerk_energy:.3f}",
            badge_text=pareto_lbl,
            key_suffix=f"q3c_{key_suffix}",
        )
        st.plotly_chart(  # type: ignore[attr-defined]
            bundle.fig_q3_pareto_bode,
            use_container_width=True,
            key=f"q3_dsp_{key_suffix}",
        )

    with tab_q4:
        render_chart_header(
            st,
            chart_id="Q4A",
            title="Q4A — Live Neuro-Symbolic SymPy AST Editor -> TradingView Pine Script v6",
            indicator_name=selected_ind,
            context_summary=f"{ctx_base} • //@version=6",
            badge_text="Pine v6",
            key_suffix=f"q4a_{key_suffix}",
        )
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


def _default_symbol_for_provider(provider: str) -> str:
    if provider == "yfinance":
        return "SPY"
    if provider == "ccxt":
        return "BTC/USDT"
    return "SYNTH:COUPLED_OU"


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
        {build_chart_help_css()}
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

    # Initialize stateful controls from URL query params on first visit (SPEC-CTRL-TF-02)
    qp = st.query_params
    if "ql_provider" not in st.session_state:
        qp_prov = str(qp.get("provider", "synthetic")).strip().lower()
        st.session_state["ql_provider"] = (
            qp_prov if qp_prov in ("synthetic", "yfinance", "ccxt") else "synthetic"
        )
    if "ql_symbol" not in st.session_state:
        qp_sym = str(qp.get("symbol", "")).strip()
        st.session_state["ql_symbol"] = qp_sym or _default_symbol_for_provider(
            st.session_state["ql_provider"]
        )
    if "ql_timeframe" not in st.session_state:
        qp_tf = str(qp.get("tf", "1D")).strip()
        try:
            norm_qp_tf = normalize_timeframe(qp_tf)
            st.session_state["ql_timeframe"] = (
                norm_qp_tf if norm_qp_tf in UI_TIMEFRAMES else "1D"
            )
        except ValueError:
            st.session_state["ql_timeframe"] = "1D"

    default_seed_val = int(st.session_state.get("ql_seed_reset_value", 42))
    providers_list = ["synthetic", "yfinance", "ccxt"]
    tf_options = list(UI_TIMEFRAMES)

    with st.sidebar:
        st.header("🔬 Research Controls")
        prov_idx = providers_list.index(st.session_state["ql_provider"])
        provider = st.selectbox("Market Data Provider", providers_list, index=prov_idx)

        prev_provider = st.session_state.get("ql_prev_provider", provider)
        if provider != prev_provider:
            st.session_state["ql_provider"] = provider
            st.session_state["ql_prev_provider"] = provider
            cur_sym = str(st.session_state.get("ql_symbol", ""))
            if cur_sym in ("", "SYNTH:COUPLED_OU", "SYNTH:WHITE_NOISE", "SPY", "BTC/USDT"):
                st.session_state["ql_symbol"] = _default_symbol_for_provider(provider)
        else:
            st.session_state["ql_prev_provider"] = provider

        symbol_input = st.text_input(
            "Symbol / Stochastic Process",
            value=st.session_state["ql_symbol"],
        )
        symbol = symbol_input.strip() or _default_symbol_for_provider(provider)
        st.session_state["ql_symbol"] = symbol

        active_tf_state = st.session_state.get("ql_timeframe", "1D")
        if active_tf_state not in tf_options:
            active_tf_state = "1D"
        tf_idx = tf_options.index(active_tf_state)
        timeframe = st.selectbox("Timeframe", tf_options, index=tf_idx)
        st.session_state["ql_timeframe"] = timeframe

        bars = int(
            st.slider(
                "PIT History Bars",
                min_value=100,
                max_value=2500,
                value=600,
                step=50,
            )
        )
        selected_ind = st.selectbox(
            "Active Indicator",
            indicator_names,
            index=indicator_names.index("KalmanFilter"),
        )
        n_surr = int(st.slider("Monte Carlo Surrogates", min_value=15, max_value=100, value=30, step=5))
        seed = int(st.number_input("Deterministic Seed", value=default_seed_val, step=1))

    # Sync URL query parameters (SPEC-CTRL-TF-02)
    if (
        qp.get("provider") != provider
        or qp.get("symbol") != symbol
        or qp.get("tf") != timeframe
    ):
        qp["provider"] = provider
        qp["symbol"] = symbol
        qp["tf"] = timeframe

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
                fallback_to_synthetic=(provider == "synthetic"),
            )
            st.session_state["ql_last_bundle"] = bundle
            st.session_state["ql_last_params"] = current_params
            st.session_state["ql_last_telemetry"] = latest_telemetry
        st.session_state["ql_is_running"] = False
    except InsufficientHistoryError as hist_err:
        st.session_state["ql_is_running"] = False
        workspace_slot.markdown(
            render_insufficient_history_html(
                symbol=hist_err.symbol,
                timeframe=hist_err.timeframe,
                available_bars=hist_err.available_bars,
                minimum_bars=hist_err.minimum_bars,
                indicator_name=selected_ind,
            ),
            unsafe_allow_html=True,
        )
        with log_and_controls_slot:
            c_sw_w, c_sw_d, _ = st.columns([1, 1, 4])
            with c_sw_w:
                if st.button("📅 Switch to 1W", key="ql_insuff_switch_1w"):
                    st.session_state["ql_timeframe"] = "1W"
                    st.rerun()
            with c_sw_d:
                if st.button("📅 Switch to 1D", key="ql_insuff_switch_1d"):
                    st.session_state["ql_timeframe"] = "1D"
                    st.rerun()
        return
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
            c_retry, c_reset, c_spy, _ = st.columns([1, 1, 1, 3])
            with c_retry:
                if st.button("🔄 Retry Run", key="ql_error_retry"):
                    st.rerun()
            with c_reset:
                if st.button("🎲 Reset to Default Seed (42)", key="ql_error_reset_seed"):
                    st.session_state["ql_seed_reset_value"] = 42
                    st.rerun()
            with c_spy:
                if provider == "yfinance" and st.button("📈 Reset to SPY (1D)", key="ql_error_reset_spy"):
                    st.session_state["ql_symbol"] = "SPY"
                    st.session_state["ql_timeframe"] = "1D"
                    st.rerun()
        return

    # Post-Load Collapse into Compact Summary Bar + Clamped/Resampled Badges + Execution Log
    if latest_telemetry is not None:
        status_slot.markdown(
            render_completed_summary_bar_html(
                latest_telemetry,
                available_bars=bundle.dataset.n_bars,
                requested_bars=bundle.dataset.requested_bars,
                resampled_from=bundle.dataset.resampled_from,
                timeframe_label=bundle.dataset.canonical_timeframe,
            ),
            unsafe_allow_html=True,
        )
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
