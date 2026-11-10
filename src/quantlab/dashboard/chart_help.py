"""Contextual Chart Help Registry, Header Bar & Anchored Popover UI (SPEC-UI-HELP-03).

Provides standardized collision-free chart card headers (`Title` left, `?` Help popover
trigger right) and structured 3-part educational explanations (`1. What It Is`,
`2. Axes & Visuals`, `3. How to Interpret`) across all 8 diagnostic charts in Tabs
`Q1`–`Q3` plus the `Q4` Neuro-Symbolic SymPy AST & Pine Script v6 Studio.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

SPEC_HELP_ID = "SPEC-UI-HELP-03"

# Design Tokens (SPEC-UI-HELP-03 Section 3)
HELP_BTN_BG_DARK = "#1E222D"
HELP_BTN_BORDER_DARK = "#374151"
HELP_BTN_HOVER_BG_DARK = "#2A303C"
HELP_BTN_HOVER_BORDER_CYAN = "#00F5D4"
HELP_FOCUS_CORAL = "#FF4B4B"
HELP_POPOVER_BG_DARK = "#161922"
HELP_POPOVER_BORDER_DARK = "#2D313E"
HELP_POPOVER_TEXT_DARK = "#D1D5DB"
HELP_TITLE_TEXT_DARK = "#F8FAFC"
HELP_MUTED_TEXT_DARK = "#9CA3AF"


@dataclass(frozen=True)
class ChartHelpEntry:
    """Immutable 3-part contextual guide for a QuantLab diagnostic chart or studio panel."""

    chart_id: str
    header_title: str
    what_it_is: str
    axes_and_visuals: str
    how_to_interpret: str
    thresholds_note: str = ""


CHART_HELP_REGISTRY: dict[str, ChartHelpEntry] = {
    "TV-01": ChartHelpEntry(
        chart_id="TV-01",
        header_title="TradingView Lightweight Charts HTML5 Canvas",
        what_it_is=(
            "Interactive multi-scale financial chart pairing raw market price bars with the "
            "selected indicator across your chosen timeframe (15m, 1h, 4h, 1D, 1W, 1M, 3M)."
        ),
        axes_and_visuals=(
            "Right Axis: Asset OHLC candlesticks (emerald up-bars, magenta down-bars). "
            "Left Axis (or right price overlay): Active indicator trace in cyan (#00F5D4). "
            "Bottom Axis: Strictly chronological Point-in-Time bar dates/timestamps."
        ),
        how_to_interpret=(
            "Pan, zoom, and hover the crosshair legend to verify whether indicator turns lead, "
            "coincide with, or lag major price inflections with zero look-ahead bias; leading "
            "indicator warm-up bars remain blank whitespace rather than artificial 0.0 spikes."
        ),
        thresholds_note="Causal PIT alignment (t <= T) • Warm-up NaNs rendered as whitespace gaps",
    ),
    "Q1A": ChartHelpEntry(
        chart_id="Q1A",
        header_title="Q1A — Causal Point-in-Time Market & Indicator Canvas",
        what_it_is=(
            "Synchronized two-pane diagnostic comparing stationarity-adjusted market price "
            "(FracDiff d*) against the causal band-pass or state-space indicator oscillator."
        ),
        axes_and_visuals=(
            "Top Pane: Asset OHLC candlesticks paired with minimum fractional differentiation "
            "order d*. Bottom Pane: Causal point-in-time indicator series (and stationary "
            "displacement when price-overlay mode is active)."
        ),
        how_to_interpret=(
            "Lower d* (near 0.00–0.45) retains long-horizon trend memory while achieving "
            "statistical stationarity (ADF p < 0.05); inspect the bottom pane for clean cycle "
            "isolation without erratic high-frequency whipsaws."
        ),
        thresholds_note="Stationarity Gate: ADF p < 0.05 at minimal FracDiff order d* in [0, 1]",
    ),
    "Q1B": ChartHelpEntry(
        chart_id="Q1B",
        header_title="Q1B — 3D Takens Phase-Space Attractor",
        what_it_is=(
            "3D delay-embedding trajectory (x(t), x(t - tau), x(t - 2*tau)) reconstructing "
            "the indicator's underlying dynamical state-space geometry via Takens' theorem."
        ),
        axes_and_visuals=(
            "X, Y, Z Axes: Current stationary indicator value x(t) plotted against causal "
            "lagged states x(t - tau) and x(t - 2*tau). Color Scale: Temporal progression "
            "from earliest history (dark violet) to latest bar (bright yellow/red)."
        ),
        how_to_interpret=(
            "Coherent, smooth orbital loops or toroidal manifolds indicate deterministic "
            "cyclical structure suitable for phase-aware filtering; an unstructured spherical "
            "cloud indicates memoryless white noise."
        ),
        thresholds_note="Delay embedding lag tau >= 1 bars • Smooth manifold vs. isotropic noise cloud",
    ),
    "Q2A": ChartHelpEntry(
        chart_id="Q2A",
        header_title="Q2A — Causal Rolling Information Dynamics",
        what_it_is=(
            "Dual rolling time-series tracking time-local signal complexity (Shannon Entropy H_t) "
            "alongside rolling out-of-sample predictive rank correlation (Spearman Rank IC)."
        ),
        axes_and_visuals=(
            "Top Pane: Causal rolling Shannon entropy H_t (nats) in cyan with permutation "
            "entropy summary. Bottom Pane: Rolling Spearman Rank IC in amber bounded by "
            "emerald dashed significance thresholds (+/-0.02)."
        ),
        how_to_interpret=(
            "Drops in Shannon entropy reflect compressed, structured market regimes, while "
            "sustained Rolling IC excursions outside the +/-0.02 dashed bands show persistent "
            "forward-return predictive edge rather than isolated one-off outliers."
        ),
        thresholds_note="Predictive IC band: |Rank IC| > 0.02 • Causal rolling window",
    ),
    "Q2B": ChartHelpEntry(
        chart_id="Q2B",
        header_title="Q2B — Transfer Entropy TE(X -> R) vs Monte Carlo Surrogates",
        what_it_is=(
            "Non-parametric hypothesis test comparing directional causal information flow "
            "TE(Indicator -> Future Return) against phase-randomized IAAFT or block-shuffled surrogates."
        ),
        axes_and_visuals=(
            "Blue Histogram: Empirical null distribution of Transfer Entropy across N synthetic "
            "surrogates that destroy causal timing while preserving amplitude/spectrum. "
            "Magenta Vertical Line: Actual observed TE(X -> R) with Z-score and p-value."
        ),
        how_to_interpret=(
            "When the magenta Observed TE marker sits well to the right of the blue surrogate "
            "null bulk (Z > 1.96, p < 0.05), the indicator transfers statistically significant "
            "predictive information into future returns beyond random chance."
        ),
        thresholds_note="Information Flow Gate: Surrogate p < 0.05 (Z-score right-tail separation)",
    ),
    "Q3A": ChartHelpEntry(
        chart_id="Q3A",
        header_title="Q3A — Predictive Rank IC Decay & Baseline Orthogonality",
        what_it_is=(
            "Dual validation test measuring multi-horizon forward return predictive power "
            "(Rank IC) alongside multicollinearity redundancy against classic indicators (VIF)."
        ),
        axes_and_visuals=(
            "Left Bars: Spearman Rank Correlation between current indicator and forward h-bar "
            "returns (emerald when |IC| > 0.02). Right Bars: Pairwise Spearman correlation and "
            "Variance Inflation Factor (VIF) against baselines (RSI, EMA, ATR, MACD, KAMA)."
        ),
        how_to_interpret=(
            "Strong signals hold higher absolute Rank IC that decays smoothly across horizons "
            "while keeping VIF below 5.0—proving the indicator contributes independent, "
            "non-redundant alpha rather than repackaging RSI or MACD."
        ),
        thresholds_note="Orthogonality & Alpha Gate: Max |IC| > 0.02 and VIF < 5.0",
    ),
    "Q3B": ChartHelpEntry(
        chart_id="Q3B",
        header_title="Q3B — Regime Distribution Separation (Wasserstein W1)",
        what_it_is=(
            "Empirical probability density histogram comparing how differently the standardized "
            "indicator behaves during calm bull regimes versus turbulent bear regimes."
        ),
        axes_and_visuals=(
            "Horizontal Axis: Standardized indicator Z-score. Vertical Axis: Probability density "
            "split into Bull / Low-Vol (emerald solid-bordered bars) and Bear / High-Vol "
            "(magenta patterned/bordered bars for color-blind legibility)."
        ),
        how_to_interpret=(
            "Higher Earth-Mover / Wasserstein-1 distance (W1 > 0.15) and visibly separated "
            "regime peaks mean the indicator reliably discriminates market states; heavy "
            "overlap near zero means the signal is regime-blind."
        ),
        thresholds_note="Regime Separation Metric: Wasserstein-1 distance W1 >= 0 (higher = stronger split)",
    ),
    "Q3C": ChartHelpEntry(
        chart_id="Q3C",
        header_title="Q3C — DSP Hilbert Phase-Lag vs. Smoothness (Jerk) Frontier",
        what_it_is=(
            "Digital signal processing benchmark mapping the fundamental responsiveness-versus-"
            "smoothness trade-off across all registered indicators plus Bode phase response."
        ),
        axes_and_visuals=(
            "Left Pane: Analytic Hilbert Transform mean phase lag (bars, X-axis) vs. 3rd-derivative "
            "Jerk energy (whipsaw roughness, Y-axis); cyan diamonds mark Pareto-optimal filters. "
            "Right Pane: Empirical Bode phase response (degrees) across angular frequency omega."
        ),
        how_to_interpret=(
            "Indicators closer to the bottom-left origin achieve both lower lag and smoother "
            "trajectories (Pareto-optimal); dominated filters (slate circles) suffer strictly "
            "worse lag and/or higher whipsaw jerk than another available filter."
        ),
        thresholds_note="DSP Gate: Minimize Hilbert Phase Lag (bars) & 3rd-Derivative Jerk Energy",
    ),
    "Q4A": ChartHelpEntry(
        chart_id="Q4A",
        header_title="Q4A — Live Neuro-Symbolic SymPy AST & Pine Script v6 Studio",
        what_it_is=(
            "Interactive symbolic compiler translating canonical SymPy time-series Abstract "
            "Syntax Trees (ASTs) directly into production TradingView Pine Script v6 code."
        ),
        axes_and_visuals=(
            "Top Formula Bar & LaTeX Banner: Editable symbolic expression I_t over causal "
            "primitives (EMA, SMA, RMA, WMA, Stdev, Lag, Highest, Lowest). Left Code Pane: "
            "Generated //@version=6 Pine Script. Right Pane: Auditable Markdown Research Card."
        ),
        how_to_interpret=(
            "Edit symbolic expressions live to verify mathematical structure in LaTeX, inspect "
            "zero-lookahead Pine v6 recurrences, and export both the .pine script and the "
            "proof-stamped Research Card for TradingView deployment."
        ),
        thresholds_note="Output Contract: Valid TradingView //@version=6 script + Proof Scorecard",
    ),
}


def get_chart_help(chart_id: str, indicator_name: str = "Active Indicator") -> ChartHelpEntry:
    """Retrieve a `ChartHelpEntry` by ID, returning a safe fallback guide if unregistered."""
    normalized_key = str(chart_id).strip().upper()
    if normalized_key in CHART_HELP_REGISTRY:
        return CHART_HELP_REGISTRY[normalized_key]

    ind_clean = str(indicator_name).strip() or "Active Indicator"
    return ChartHelpEntry(
        chart_id=normalized_key or "UNKNOWN",
        header_title=f"Diagnostic Panel ({ind_clean})",
        what_it_is=f"Quantitative diagnostic chart for {ind_clean}. Detailed guide pending.",
        axes_and_visuals=(
            "Horizontal axis tracks Point-in-Time bars, horizons, or null samples; "
            "vertical axis tracks standardized signal response or density."
        ),
        how_to_interpret=(
            "Compare signal amplitude and stability against QuantLab's causal stationarity, "
            "surrogate entropy, and orthogonality thresholds."
        ),
        thresholds_note="Causal PIT invariant (t <= T)",
    )


def build_chart_help_css() -> str:
    """Return `<style>` rules for SPEC-UI-HELP-03 chart card headers and `?` help popovers."""
    return f"""
<style>
.ql-chart-header-row {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 6px 2px 4px 2px;
  margin-top: 4px;
  margin-bottom: 4px;
}}
.ql-chart-header-title {{
  font-size: 17px;
  line-height: 24px;
  font-weight: 600;
  color: {HELP_TITLE_TEXT_DARK};
  margin: 0;
  overflow-wrap: anywhere;
}}
.ql-chart-header-badge {{
  display: inline-block;
  margin-left: 8px;
  padding: 2px 8px;
  border-radius: 9999px;
  background-color: #1F2937;
  border: 1px solid #374151;
  color: #E5E7EB;
  font-family: "JetBrains Mono", "Source Code Pro", Consolas, monospace;
  font-size: 11.5px;
  font-weight: 500;
  vertical-align: middle;
}}
.ql-help-popover-card {{
  background-color: {HELP_POPOVER_BG_DARK};
  border: 1px solid {HELP_POPOVER_BORDER_DARK};
  border-radius: 10px;
  max-width: 380px;
  max-height: 60vh;
  overflow-y: auto;
  padding: 14px 16px;
  color: {HELP_POPOVER_TEXT_DARK};
  font-size: 13.5px;
  line-height: 19.5px;
}}
.ql-help-popover-heading {{
  font-size: 14.5px;
  font-weight: 700;
  color: {HELP_TITLE_TEXT_DARK};
  margin: 0 0 8px 0;
}}
.ql-help-context-pill {{
  display: inline-block;
  background-color: #1E222D;
  border: 1px solid #374151;
  border-radius: 6px;
  padding: 2px 8px;
  margin-bottom: 10px;
  font-family: "JetBrains Mono", "Source Code Pro", Consolas, monospace;
  font-size: 11.5px;
  color: {HELP_BTN_HOVER_BORDER_CYAN};
}}
.ql-help-section {{
  margin-bottom: 9px;
}}
.ql-help-section strong {{
  color: {HELP_TITLE_TEXT_DARK};
}}
.ql-help-threshold-note {{
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #2D313E;
  font-family: "JetBrains Mono", "Source Code Pro", Consolas, monospace;
  font-size: 11.5px;
  color: {HELP_MUTED_TEXT_DARK};
}}
div[data-testid="stPopover"] > button {{
  min-width: 36px !important;
  min-height: 36px !important;
  background-color: {HELP_BTN_BG_DARK} !important;
  border: 1px solid {HELP_BTN_BORDER_DARK} !important;
  border-radius: 8px !important;
  color: {HELP_TITLE_TEXT_DARK} !important;
  font-weight: 700 !important;
  padding: 4px 10px !important;
}}
div[data-testid="stPopover"] > button:hover {{
  background-color: {HELP_BTN_HOVER_BG_DARK} !important;
  border-color: {HELP_BTN_HOVER_BORDER_CYAN} !important;
  color: {HELP_BTN_HOVER_BORDER_CYAN} !important;
}}
div[data-testid="stPopover"] > button:focus-visible {{
  outline: 2px solid {HELP_FOCUS_CORAL} !important;
  outline-offset: 2px !important;
}}
@media (pointer: coarse), (max-width: 768px) {{
  div[data-testid="stPopover"] > button {{
    min-width: 44px !important;
    min-height: 44px !important;
  }}
  .ql-help-popover-card {{
    max-width: calc(100vw - 32px);
  }}
}}
</style>
"""


def render_chart_help_popover_html(
    chart_id: str,
    indicator_name: str = "Active Indicator",
    context_summary: str | None = None,
) -> str:
    """Render the structured 3-part HTML body inside an anchored `?` Help popover."""
    entry = get_chart_help(chart_id=chart_id, indicator_name=indicator_name)
    safe_id = html.escape(entry.chart_id.lower())
    title_esc = html.escape(entry.header_title)
    what_esc = html.escape(entry.what_it_is)
    axes_esc = html.escape(entry.axes_and_visuals)
    interp_esc = html.escape(entry.how_to_interpret)

    ctx_html = ""
    if context_summary and context_summary.strip():
        ctx_html = f'<div class="ql-help-context-pill">{html.escape(context_summary.strip())}</div>'

    thresh_html = ""
    if entry.thresholds_note:
        thresh_html = f'<div class="ql-help-threshold-note">{html.escape(entry.thresholds_note)}</div>'

    return f"""
<div id="help-{safe_id}" class="ql-help-popover-card" role="region" aria-label="Help: {title_esc}" data-spec-id="{SPEC_HELP_ID}" data-chart-id="{html.escape(entry.chart_id)}">
  <div class="ql-help-popover-heading">What This Chart Shows — {title_esc}</div>
  {ctx_html}
  <div class="ql-help-section"><strong>1. What It Is:</strong> {what_esc}</div>
  <div class="ql-help-section"><strong>2. Axes &amp; Visuals:</strong> {axes_esc}</div>
  <div class="ql-help-section"><strong>3. How to Interpret:</strong> {interp_esc}</div>
  {thresh_html}
</div>
"""


def render_chart_header(
    st: object,
    chart_id: str,
    title: str | None = None,
    indicator_name: str = "Active Indicator",
    context_summary: str | None = None,
    badge_text: str | None = None,
    key_suffix: str = "live",
) -> None:
    """Render a standardized Chart Card Header Bar (`Title` left, `?` Help popover right)."""
    entry = get_chart_help(chart_id=chart_id, indicator_name=indicator_name)
    resolved_title = (title.strip() if title and title.strip() else entry.header_title)
    title_esc = html.escape(resolved_title)
    badge_html = (
        f'<span class="ql-chart-header-badge">{html.escape(badge_text.strip())}</span>'
        if badge_text and badge_text.strip()
        else ""
    )

    try:
        col_title, col_help = st.columns([0.92, 0.08], vertical_alignment="center")  # type: ignore[attr-defined]
    except TypeError:
        col_title, col_help = st.columns([0.92, 0.08])  # type: ignore[attr-defined]

    with col_title:
        st.markdown(  # type: ignore[attr-defined]
            f'<div class="ql-chart-header-row" data-chart-id="{html.escape(entry.chart_id)}">'
            f'<span class="ql-chart-header-title">{title_esc}{badge_html}</span>'
            f"</div>",
            unsafe_allow_html=True,
        )

    popover_html = render_chart_help_popover_html(
        chart_id=chart_id,
        indicator_name=indicator_name,
        context_summary=context_summary,
    )
    help_tooltip = f"Help: {resolved_title} — Explain this chart"
    with col_help:
        if hasattr(st, "popover"):
            try:
                pop = st.popover("?", help=help_tooltip, use_container_width=True)  # type: ignore[attr-defined]
            except TypeError:
                pop = st.popover("?")  # type: ignore[attr-defined]
            with pop:
                st.markdown(popover_html, unsafe_allow_html=True)  # type: ignore[attr-defined]
        else:  # pragma: no cover - fallback for older Streamlit stubs
            _ = key_suffix
            with st.expander("?", expanded=False):  # type: ignore[attr-defined]
                st.markdown(popover_html, unsafe_allow_html=True)  # type: ignore[attr-defined]
