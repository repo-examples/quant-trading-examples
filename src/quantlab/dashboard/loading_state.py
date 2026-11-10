"""Quantitative Pipeline Loading Status & Skeleton UI (SPEC-QUANT-LOAD-01).

Provides immutable multi-stage telemetry state machines, weighted determinate progress
calculators, responsive dark-theme CSS tokens, structural shimmer skeletons, warm-state
chart dimming helpers, step-level error recovery banners, and stage-throttled ARIA
live announcements for the QuantLab diagnostic workspace.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, replace
from typing import Literal

SPEC_ID = "SPEC-QUANT-LOAD-01"

# Design Tokens (SPEC-QUANT-LOAD-01 Section 3)
CANVAS_BG_DARK = "#0E1117"
CARD_SURFACE_DARK = "#1A1D24"
CARD_BORDER_DARK = "#2D313E"
PROGRESS_GRADIENT_START = "#7C4DFF"
PROGRESS_GRADIENT_END = "#FF4B4B"
PROGRESS_TRACK_DARK = "#262730"
STATUS_SUCCESS_DARK = "#21C354"
STATUS_ACTIVE_CORAL = "#FF4B4B"
STATUS_ACTIVE_PURPLE = "#7C4DFF"
STATUS_WARNING_AMBER = "#F59E0B"
TEXT_PRIMARY_DARK = "#FAFAFA"
TEXT_MUTED_DARK = "#6E7687"
TEXT_TELEMETRY_MONO = "#A3A8B8"
SKELETON_BASE_DARK = "#161922"
SKELETON_SWEEP_DARK = "#1F2430"

StageState = Literal["pending", "active", "completed", "failed", "cancelled"]
PipelineSystemState = Literal[
    "cold_load",
    "warm_reload",
    "mid_run_restart",
    "completed",
    "error",
    "cancelled",
]

STAGE_WEIGHT_BOUNDS: dict[int, tuple[float, float]] = {
    1: (0.0, 20.0),
    2: (20.0, 40.0),
    3: (40.0, 85.0),
    4: (85.0, 100.0),
}


class PipelineCancelledError(RuntimeError):
    """Raised when the user cancels an in-flight quantitative pipeline execution."""


@dataclass(frozen=True)
class PipelineStageStatus:
    """Immutable state record for one row of the 4-Stage Telemetry Checklist."""

    stage_index: int
    title: str
    detail: str
    state: StageState
    duration_seconds: float | None = None
    weight_start_pct: float = 0.0
    weight_end_pct: float = 100.0


@dataclass(frozen=True)
class PipelineExecutionTelemetry:
    """Aggregate telemetry snapshot for an active, completed, failed, or cancelled pipeline run."""

    spec_id: str
    system_state: PipelineSystemState
    symbol: str
    provider: str
    timeframe: str
    bars: int
    indicator_name: str
    n_surrogates: int
    seed: int
    overall_progress_pct: float
    elapsed_seconds: float
    stages: tuple[PipelineStageStatus, ...]
    current_surrogate: int = 0
    restarted_with_updated_params: bool = False
    is_warm_reload: bool = False
    long_running_warning: bool = False
    error_step: int | None = None
    error_message: str | None = None
    aria_announcement: str = ""


def compute_stage_progress_pct(
    stage_index: int,
    stage_fraction: float = 0.0,
    current_surrogate: int = 0,
    total_surrogates: int = 30,
) -> float:
    """Compute weighted determinate progress percentage in [0.0, 100.0] per SPEC-QUANT-LOAD-01.

    - Stage 1 (Data Synthesis / Fetch): 0% -> 20%
    - Stage 2 (Active Indicator Calculation): 20% -> 40%
    - Stage 3 (Monte Carlo Surrogates Loop): 40% -> 85% (40% + 45% * (i / N))
    - Stage 4 (Hilbert Phase-Jerk & Pine v6 Transpilation): 85% -> 100%
    """
    if stage_index <= 0:
        return 0.0
    if stage_index > 4:
        return 100.0

    start_pct, end_pct = STAGE_WEIGHT_BOUNDS[stage_index]
    span = end_pct - start_pct

    if stage_index == 3:
        denom = max(1, int(total_surrogates))
        frac = min(1.0, max(0.0, float(current_surrogate) / float(denom)))
    else:
        frac = min(1.0, max(0.0, float(stage_fraction)))

    return float(min(100.0, max(0.0, start_pct + span * frac)))


def is_long_running_load(
    bars: int,
    n_surrogates: int,
    elapsed_seconds: float = 0.0,
) -> bool:
    """Return True when computational load or elapsed runtime triggers the amber warning state."""
    return bool(int(bars) > 1500 or int(n_surrogates) > 60 or float(elapsed_seconds) > 15.0)


def format_elapsed_timer(elapsed_seconds: float) -> str:
    """Format elapsed seconds as `MM:SS.ds` (e.g., `00:03.4s`)."""
    sec = max(0.0, float(elapsed_seconds))
    minutes = int(sec // 60)
    rem = sec - (minutes * 60)
    return f"{minutes:02d}:{rem:04.1f}s"


def _stage1_title(provider: str) -> str:
    return "Synthesizing Market Data" if provider == "synthetic" else "Fetching Market Data"


def build_initial_telemetry(
    symbol: str = "SYNTH:COUPLED_OU",
    provider: str = "synthetic",
    timeframe: str = "1d",
    bars: int = 600,
    indicator_name: str = "KalmanFilter",
    n_surrogates: int = 30,
    seed: int = 42,
    is_warm_reload: bool = False,
    restarted_with_updated_params: bool = False,
) -> PipelineExecutionTelemetry:
    """Create the initial Stage 1 (0%) telemetry snapshot."""
    s1_title = _stage1_title(provider)
    stages = (
        PipelineStageStatus(
            stage_index=1,
            title=s1_title,
            detail=f"{symbol} • {timeframe} • {bars} PIT bars",
            state="active",
            duration_seconds=None,
            weight_start_pct=0.0,
            weight_end_pct=20.0,
        ),
        PipelineStageStatus(
            stage_index=2,
            title="Computing Active Indicator",
            detail=f"{indicator_name}",
            state="pending",
            duration_seconds=None,
            weight_start_pct=20.0,
            weight_end_pct=40.0,
        ),
        PipelineStageStatus(
            stage_index=3,
            title="Simulating Monte Carlo Surrogates",
            detail=f"0 / {n_surrogates} surrogates • Seed: {seed}",
            state="pending",
            duration_seconds=None,
            weight_start_pct=40.0,
            weight_end_pct=85.0,
        ),
        PipelineStageStatus(
            stage_index=4,
            title="Evaluating Hilbert Phase-Jerk Frontier & Pine v6 Transpiler",
            detail=f"{indicator_name} -> Pine Script v6",
            state="pending",
            duration_seconds=None,
            weight_start_pct=85.0,
            weight_end_pct=100.0,
        ),
    )
    if restarted_with_updated_params:
        sys_state: PipelineSystemState = "mid_run_restart"
    elif is_warm_reload:
        sys_state = "warm_reload"
    else:
        sys_state = "cold_load"

    return PipelineExecutionTelemetry(
        spec_id=SPEC_ID,
        system_state=sys_state,
        symbol=symbol,
        provider=provider,
        timeframe=timeframe,
        bars=int(bars),
        indicator_name=indicator_name,
        n_surrogates=int(n_surrogates),
        seed=int(seed),
        overall_progress_pct=0.0,
        elapsed_seconds=0.0,
        stages=stages,
        current_surrogate=0,
        restarted_with_updated_params=bool(restarted_with_updated_params),
        is_warm_reload=bool(is_warm_reload),
        long_running_warning=is_long_running_load(bars, n_surrogates, 0.0),
        error_step=None,
        error_message=None,
        aria_announcement=f"Step 1 of 4: {s1_title} for {symbol} ({bars} bars)",
    )


def advance_telemetry_stage(
    telemetry: PipelineExecutionTelemetry,
    active_stage: int,
    elapsed_seconds: float,
    completed_stage_duration: float | None = None,
) -> PipelineExecutionTelemetry:
    """Transition the pipeline to `active_stage` (2, 3, or 4), marking prior stages completed."""
    target = min(4, max(1, int(active_stage)))
    updated_stages: list[PipelineStageStatus] = []
    active_title = ""

    for st_item in telemetry.stages:
        idx = st_item.stage_index
        if idx < target:
            dur = st_item.duration_seconds
            if idx == target - 1 and completed_stage_duration is not None:
                dur = max(0.0, float(completed_stage_duration))
            elif dur is None:
                dur = 0.0
            updated_stages.append(
                replace(
                    st_item,
                    state="completed",
                    duration_seconds=dur,
                )
            )
        elif idx == target:
            active_title = st_item.title
            detail = st_item.detail
            if idx == 3:
                detail = f"0 / {telemetry.n_surrogates} surrogates • Seed: {telemetry.seed}"
            updated_stages.append(
                replace(
                    st_item,
                    state="active",
                    detail=detail,
                )
            )
        else:
            updated_stages.append(replace(st_item, state="pending"))

    pct = compute_stage_progress_pct(
        stage_index=target,
        stage_fraction=0.0,
        current_surrogate=0,
        total_surrogates=telemetry.n_surrogates,
    )
    return replace(
        telemetry,
        overall_progress_pct=pct,
        elapsed_seconds=max(0.0, float(elapsed_seconds)),
        stages=tuple(updated_stages),
        current_surrogate=0 if target < 3 else telemetry.current_surrogate,
        long_running_warning=is_long_running_load(
            telemetry.bars,
            telemetry.n_surrogates,
            elapsed_seconds,
        ),
        aria_announcement=f"Step {target} of 4: {active_title}",
    )


def update_surrogate_telemetry(
    telemetry: PipelineExecutionTelemetry,
    current_surrogate: int,
    elapsed_seconds: float,
) -> PipelineExecutionTelemetry:
    """Update Stage 3 progress dynamically per surrogate i/N without flooding ARIA live announcements."""
    cur = min(telemetry.n_surrogates, max(0, int(current_surrogate)))
    pct = compute_stage_progress_pct(
        stage_index=3,
        current_surrogate=cur,
        total_surrogates=telemetry.n_surrogates,
    )
    updated_stages: list[PipelineStageStatus] = []
    for st_item in telemetry.stages:
        if st_item.stage_index == 3:
            updated_stages.append(
                replace(
                    st_item,
                    state="active",
                    detail=f"{cur} / {telemetry.n_surrogates} surrogates • Seed: {telemetry.seed}",
                )
            )
        else:
            updated_stages.append(st_item)

    # Keep aria_announcement throttled to the Stage 3 start announcement
    return replace(
        telemetry,
        overall_progress_pct=pct,
        elapsed_seconds=max(0.0, float(elapsed_seconds)),
        stages=tuple(updated_stages),
        current_surrogate=cur,
        long_running_warning=is_long_running_load(
            telemetry.bars,
            telemetry.n_surrogates,
            elapsed_seconds,
        ),
        aria_announcement="Step 3 of 4: Simulating Monte Carlo Surrogates",
    )


def complete_telemetry(
    telemetry: PipelineExecutionTelemetry,
    elapsed_seconds: float,
    stage4_duration: float,
) -> PipelineExecutionTelemetry:
    """Transition the pipeline to 100% completed state."""
    updated_stages: list[PipelineStageStatus] = []
    for st_item in telemetry.stages:
        if st_item.stage_index == 4:
            updated_stages.append(
                replace(
                    st_item,
                    state="completed",
                    duration_seconds=max(0.0, float(stage4_duration)),
                )
            )
        elif st_item.stage_index == 3:
            updated_stages.append(
                replace(
                    st_item,
                    state="completed",
                    detail=f"{telemetry.n_surrogates} / {telemetry.n_surrogates} surrogates • Seed: {telemetry.seed}",
                    duration_seconds=st_item.duration_seconds or 0.0,
                )
            )
        else:
            updated_stages.append(
                replace(
                    st_item,
                    state="completed",
                    duration_seconds=st_item.duration_seconds or 0.0,
                )
            )

    total_sec = max(0.0, float(elapsed_seconds))
    return replace(
        telemetry,
        system_state="completed",
        overall_progress_pct=100.0,
        elapsed_seconds=total_sec,
        stages=tuple(updated_stages),
        current_surrogate=telemetry.n_surrogates,
        long_running_warning=is_long_running_load(
            telemetry.bars,
            telemetry.n_surrogates,
            total_sec,
        ),
        aria_announcement=(
            f"Completed in {total_sec:.1f} seconds for {telemetry.symbol} "
            f"({telemetry.bars} bars, {telemetry.n_surrogates} surrogates)"
        ),
    )


def fail_telemetry(
    telemetry: PipelineExecutionTelemetry,
    error_step: int,
    error_message: str,
    elapsed_seconds: float,
) -> PipelineExecutionTelemetry:
    """Transition the pipeline to the semantic red step-level failure state."""
    step_idx = min(4, max(1, int(error_step)))
    msg = str(error_message).strip() or "Unexpected pipeline execution error"
    updated_stages: list[PipelineStageStatus] = []
    for st_item in telemetry.stages:
        if st_item.stage_index < step_idx:
            updated_stages.append(
                replace(
                    st_item,
                    state="completed",
                    duration_seconds=st_item.duration_seconds or 0.0,
                )
            )
        elif st_item.stage_index == step_idx:
            updated_stages.append(
                replace(
                    st_item,
                    state="failed",
                    detail=msg,
                )
            )
        else:
            updated_stages.append(replace(st_item, state="pending"))

    return replace(
        telemetry,
        system_state="error",
        elapsed_seconds=max(0.0, float(elapsed_seconds)),
        stages=tuple(updated_stages),
        error_step=step_idx,
        error_message=msg,
        aria_announcement=f"Failed at Step {step_idx}: {msg}",
    )


def cancel_telemetry(
    telemetry: PipelineExecutionTelemetry,
    elapsed_seconds: float,
) -> PipelineExecutionTelemetry:
    """Transition an in-flight pipeline run to the user-cancelled state."""
    updated_stages: list[PipelineStageStatus] = []
    for st_item in telemetry.stages:
        if st_item.state == "active":
            updated_stages.append(
                replace(
                    st_item,
                    state="cancelled",
                    detail=f"{st_item.detail} (Cancelled by user)",
                )
            )
        else:
            updated_stages.append(st_item)

    return replace(
        telemetry,
        system_state="cancelled",
        elapsed_seconds=max(0.0, float(elapsed_seconds)),
        stages=tuple(updated_stages),
        aria_announcement=f"Pipeline run cancelled at {telemetry.overall_progress_pct:.0f} percent",
    )


def build_loading_theme_css() -> str:
    """Return the <style> block for SPEC-QUANT-LOAD-01 tokens, responsive layouts, shimmer & reduced motion."""
    return f"""
<style>
.ql-sr-only {{
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}}
.ql-status-card {{
  background-color: {CARD_SURFACE_DARK};
  border: 1px solid {CARD_BORDER_DARK};
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 24px;
  color: {TEXT_PRIMARY_DARK};
  font-family: "Inter", "Source Sans Pro", -apple-system, BlinkMacSystemFont, sans-serif;
}}
.ql-status-header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}}
.ql-status-title-cluster {{
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  color: {TEXT_PRIMARY_DARK};
}}
.ql-spinner {{
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2.5px solid {PROGRESS_GRADIENT_START};
  border-top-color: {PROGRESS_GRADIENT_END};
  display: inline-block;
  animation: ql-spin 0.9s linear infinite;
  flex-shrink: 0;
}}
.ql-telemetry-cluster {{
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: "JetBrains Mono", "Source Code Pro", Consolas, monospace;
  font-size: 13px;
  color: {TEXT_TELEMETRY_MONO};
}}
.ql-elapsed-badge {{
  background: {PROGRESS_TRACK_DARK};
  border: 1px solid {CARD_BORDER_DARK};
  border-radius: 6px;
  padding: 2px 8px;
}}
.ql-elapsed-badge-amber {{
  background: rgba(245, 158, 11, 0.16);
  border: 1px solid {STATUS_WARNING_AMBER};
  color: {STATUS_WARNING_AMBER};
  border-radius: 6px;
  padding: 2px 8px;
  font-weight: 600;
}}
.ql-restart-badge {{
  background: rgba(245, 158, 11, 0.14);
  border: 1px solid {STATUS_WARNING_AMBER};
  color: {STATUS_WARNING_AMBER};
  border-radius: 6px;
  padding: 3px 9px;
  font-size: 12px;
  font-weight: 500;
  margin-bottom: 10px;
  display: inline-block;
}}
.ql-context-pills {{
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}}
.ql-context-pill {{
  background: {PROGRESS_TRACK_DARK};
  border: 1px solid {CARD_BORDER_DARK};
  border-radius: 9999px;
  padding: 2px 10px;
  font-family: "JetBrains Mono", "Source Code Pro", Consolas, monospace;
  font-size: 12px;
  color: {TEXT_TELEMETRY_MONO};
}}
.ql-progress-track {{
  width: 100%;
  height: 6px;
  background-color: {PROGRESS_TRACK_DARK};
  border-radius: 9999px;
  overflow: hidden;
  margin-bottom: 14px;
}}
.ql-progress-fill {{
  height: 100%;
  border-radius: 9999px;
  background: linear-gradient(90deg, {PROGRESS_GRADIENT_START} 0%, {PROGRESS_GRADIENT_END} 100%);
  transition: width 250ms ease-out;
}}
.ql-progress-fill-error {{
  height: 100%;
  border-radius: 9999px;
  background: {STATUS_ACTIVE_CORAL};
  transition: width 250ms ease-out;
}}
.ql-progress-fill-success {{
  height: 100%;
  border-radius: 9999px;
  background: {STATUS_SUCCESS_DARK};
  transition: width 250ms ease-out;
}}
.ql-stage-list {{
  display: flex;
  flex-direction: column;
  gap: 8px;
}}
.ql-stage-row {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 14px;
}}
.ql-stage-completed {{
  color: {TEXT_PRIMARY_DARK};
}}
.ql-stage-completed .ql-stage-icon {{
  color: {STATUS_SUCCESS_DARK};
  font-weight: 700;
}}
.ql-stage-active {{
  color: {TEXT_PRIMARY_DARK};
  font-weight: 700;
}}
.ql-stage-active .ql-stage-icon {{
  color: {STATUS_ACTIVE_CORAL};
  font-weight: 700;
}}
.ql-stage-pending {{
  color: {TEXT_MUTED_DARK};
  font-weight: 400;
}}
.ql-stage-failed {{
  color: {STATUS_ACTIVE_CORAL};
  font-weight: 700;
}}
.ql-stage-duration {{
  font-family: "JetBrains Mono", "Source Code Pro", Consolas, monospace;
  font-size: 12px;
  color: {TEXT_TELEMETRY_MONO};
}}
.ql-long-warning-note {{
  margin-top: 10px;
  padding: 6px 10px;
  border-radius: 6px;
  background: rgba(245, 158, 11, 0.12);
  border-left: 3px solid {STATUS_WARNING_AMBER};
  color: {STATUS_WARNING_AMBER};
  font-size: 12.5px;
}}
.ql-summary-bar {{
  min-height: 40px;
  background-color: {CARD_SURFACE_DARK};
  border: 1px solid {CARD_BORDER_DARK};
  border-radius: 10px;
  padding: 8px 16px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 14px;
  color: {TEXT_PRIMARY_DARK};
}}
.ql-summary-bar-check {{
  color: {STATUS_SUCCESS_DARK};
  font-weight: 700;
  margin-right: 6px;
}}
.ql-clamped-pill {{
  display: inline-block;
  background-color: #3B2F13;
  border: 1px solid #F59E0B;
  color: #FBBF24;
  border-radius: 9999px;
  padding: 3px 11px;
  font-family: "JetBrains Mono", "Source Code Pro", Consolas, monospace;
  font-size: 12px;
  font-weight: 500;
}}
.ql-resampled-pill {{
  display: inline-block;
  background-color: #1F2937;
  border: 1px solid #38BDF8;
  color: #BAE6FD;
  border-radius: 9999px;
  padding: 3px 11px;
  font-family: "JetBrains Mono", "Source Code Pro", Consolas, monospace;
  font-size: 12px;
  font-weight: 500;
}}
.ql-insufficient-callout {{
  background-color: #26151B;
  border: 1px solid {STATUS_ACTIVE_CORAL};
  border-left: 4px solid {STATUS_ACTIVE_CORAL};
  border-radius: 10px;
  padding: 16px 20px;
  margin-bottom: 16px;
  color: {TEXT_PRIMARY_DARK};
  font-size: 14px;
  line-height: 20px;
}}
.ql-insufficient-callout-title {{
  font-weight: 700;
  color: #FCA5A5;
  margin-bottom: 6px;
}}
.ql-kpi-skeleton-grid {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}}
.ql-kpi-skeleton-card {{
  height: 96px;
  border-radius: 10px;
  padding: 14px 16px;
  border: 1px solid {CARD_BORDER_DARK};
  background: linear-gradient(110deg, {SKELETON_BASE_DARK} 25%, {SKELETON_SWEEP_DARK} 45%, {SKELETON_BASE_DARK} 65%);
  background-size: 200% 100%;
  animation: ql-shimmer-sweep 1.6s infinite linear;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}}
.ql-chart-skeleton {{
  height: 360px;
  border-radius: 12px;
  border: 1px solid {CARD_BORDER_DARK};
  background: linear-gradient(110deg, {SKELETON_BASE_DARK} 25%, {SKELETON_SWEEP_DARK} 45%, {SKELETON_BASE_DARK} 65%);
  background-size: 200% 100%;
  animation: ql-shimmer-sweep 1.6s infinite linear;
  position: relative;
  padding: 20px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}}
.ql-skeleton-watermark {{
  align-self: flex-end;
  font-family: "JetBrains Mono", "Source Code Pro", Consolas, monospace;
  font-size: 12px;
  color: {TEXT_TELEMETRY_MONO};
}}
.ql-warm-dimmed {{
  opacity: 0.45;
  filter: blur(1px);
  transition: opacity 200ms ease-out;
}}
@keyframes ql-spin {{
  from {{ transform: rotate(0deg); }}
  to {{ transform: rotate(360deg); }}
}}
@keyframes ql-shimmer-sweep {{
  0% {{ background-position: 200% 0; }}
  100% {{ background-position: -200% 0; }}
}}
@media (min-width: 768px) and (max-width: 1023px) {{
  .ql-kpi-skeleton-grid {{
    grid-template-columns: repeat(2, 1fr);
  }}
  div[data-testid="stHorizontalBlock"] {{
    flex-wrap: wrap !important;
  }}
  div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {{
    min-width: 46% !important;
  }}
}}
@media (max-width: 767px) {{
  .ql-kpi-skeleton-grid {{
    grid-template-columns: 1fr;
  }}
  .ql-status-header {{
    flex-direction: column;
    align-items: flex-start;
  }}
  div[data-testid="stHorizontalBlock"] {{
    flex-wrap: wrap !important;
  }}
  div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {{
    min-width: 100% !important;
  }}
}}
@media (prefers-reduced-motion: reduce) {{
  .ql-kpi-skeleton-card,
  .ql-chart-skeleton {{
    animation: none !important;
    background: {SKELETON_BASE_DARK} !important;
  }}
  .ql-spinner {{
    animation: none !important;
    opacity: 0.85;
  }}
}}
</style>
"""


def _active_stage_for_telemetry(telemetry: PipelineExecutionTelemetry) -> PipelineStageStatus:
    for st_item in telemetry.stages:
        if st_item.state in ("active", "failed", "cancelled"):
            return st_item
    return telemetry.stages[-1]


def render_pipeline_status_card_html(telemetry: PipelineExecutionTelemetry) -> str:
    """Render the SPEC-QUANT-LOAD-01 Multi-Stage Pipeline Status Card HTML."""
    sym_esc = html.escape(telemetry.symbol)
    tf_esc = html.escape(telemetry.timeframe)
    ind_esc = html.escape(telemetry.indicator_name)
    prov_esc = html.escape(telemetry.provider)
    aria_esc = html.escape(telemetry.aria_announcement)

    is_running = telemetry.system_state in ("cold_load", "warm_reload", "mid_run_restart")
    aria_busy = "true" if is_running else "false"
    pct_int = int(round(telemetry.overall_progress_pct))
    active_stage = _active_stage_for_telemetry(telemetry)
    valuetext = html.escape(
        f"Step {active_stage.stage_index} of 4: {active_stage.title}, {pct_int} percent complete"
    )

    if telemetry.system_state == "error":
        header_title = html.escape(
            f"Failed at Step {telemetry.error_step}: {telemetry.error_message or 'Execution Error'}"
        )
        lead_icon_html = f'<span style="color:{STATUS_ACTIVE_CORAL};font-weight:700;">✕</span>'
        fill_class = "ql-progress-fill-error"
    elif telemetry.system_state == "cancelled":
        header_title = f"Cancelled Pipeline Run for {sym_esc} ({telemetry.bars} bars)"
        lead_icon_html = f'<span style="color:{STATUS_WARNING_AMBER};font-weight:700;">⊘</span>'
        fill_class = "ql-progress-fill"
    elif telemetry.system_state == "completed":
        header_title = (
            f"✓ Completed in {telemetry.elapsed_seconds:.1f}s • "
            f"{sym_esc} ({telemetry.bars} bars, {telemetry.n_surrogates} surrogates)"
        )
        lead_icon_html = f'<span style="color:{STATUS_SUCCESS_DARK};font-weight:700;">✓</span>'
        fill_class = "ql-progress-fill-success"
    elif telemetry.is_warm_reload:
        header_title = f"Updating {ind_esc} &amp; {telemetry.n_surrogates} Surrogates..."
        lead_icon_html = '<span class="ql-spinner" aria-hidden="true"></span>'
        fill_class = "ql-progress-fill"
    else:
        header_title = f"Running Quantitative Pipeline for {sym_esc} ({telemetry.bars} bars)..."
        lead_icon_html = '<span class="ql-spinner" aria-hidden="true"></span>'
        fill_class = "ql-progress-fill"

    elapsed_cls = "ql-elapsed-badge-amber" if telemetry.long_running_warning else "ql-elapsed-badge"
    elapsed_str = format_elapsed_timer(telemetry.elapsed_seconds)

    restart_badge_html = ""
    if telemetry.restarted_with_updated_params:
        restart_badge_html = (
            '<div class="ql-restart-badge">'
            f"Restarted pipeline with updated parameters (Monte Carlo Surrogates: {telemetry.n_surrogates})"
            "</div>"
        )

    stage_rows_html: list[str] = []
    for st_item in telemetry.stages:
        if st_item.state == "completed":
            row_cls = "ql-stage-row ql-stage-completed"
            icon_txt = "✓"
        elif st_item.state == "active":
            row_cls = "ql-stage-row ql-stage-active"
            icon_txt = "⟳"
        elif st_item.state == "failed":
            row_cls = "ql-stage-row ql-stage-failed"
            icon_txt = "✕"
        elif st_item.state == "cancelled":
            row_cls = "ql-stage-row ql-stage-pending"
            icon_txt = "⊘"
        else:
            row_cls = "ql-stage-row ql-stage-pending"
            icon_txt = "○"

        dur_html = (
            f'<span class="ql-stage-duration">({st_item.duration_seconds:.2f}s)</span>'
            if st_item.duration_seconds is not None and st_item.state == "completed"
            else ""
        )
        title_esc = html.escape(st_item.title)
        detail_esc = html.escape(st_item.detail)
        stage_rows_html.append(
            f'<div class="{row_cls}" data-stage="{st_item.stage_index}">'
            f'<span><span class="ql-stage-icon">{icon_txt}</span> '
            f"{title_esc} (<span>{detail_esc}</span>)</span>"
            f"{dur_html}</div>"
        )

    long_warning_html = ""
    if telemetry.long_running_warning and is_running:
        long_warning_html = (
            '<div class="ql-long-warning-note">'
            "High surrogate count or bar history selected. Computation may take ~25s."
            "</div>"
        )

    return f"""
<div class="ql-status-card" role="region" aria-label="Quantitative Pipeline Execution Status" aria-busy="{aria_busy}" data-spec-id="{telemetry.spec_id}">
  <div class="ql-sr-only" aria-live="polite" aria-atomic="true">{aria_esc}</div>
  {restart_badge_html}
  <div class="ql-status-header">
    <div class="ql-status-title-cluster">
      {lead_icon_html}
      <span>{header_title}</span>
    </div>
    <div class="ql-telemetry-cluster">
      <span class="{elapsed_cls}">Elapsed: {elapsed_str}</span>
      <span>{pct_int}%</span>
    </div>
  </div>
  <div class="ql-context-pills" aria-label="Active Pipeline Parameters">
    <span class="ql-context-pill">{prov_esc}</span>
    <span class="ql-context-pill">{sym_esc}</span>
    <span class="ql-context-pill">{tf_esc}</span>
    <span class="ql-context-pill">{telemetry.bars} bars</span>
    <span class="ql-context-pill">{ind_esc}</span>
    <span class="ql-context-pill">{telemetry.n_surrogates} surrogates</span>
    <span class="ql-context-pill">Seed: {telemetry.seed}</span>
  </div>
  <div class="ql-progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{pct_int}" aria-valuetext="{valuetext}">
    <div class="{fill_class}" style="width: {telemetry.overall_progress_pct:.1f}%;"></div>
  </div>
  <div class="ql-stage-list">
    {"".join(stage_rows_html)}
  </div>
  {long_warning_html}
</div>
"""


def render_shimmer_skeletons_html(symbol: str = "SYNTH:COUPLED_OU") -> str:
    """Render Cold-Load Structural Shimmer Skeletons (4 KPI cards + 360px primary chart canvas)."""
    sym_esc = html.escape(symbol)
    kpi_labels = (
        "Stationarity p-value (FracDiff d*)",
        "Transfer Entropy TE(X → R)",
        "Phase-Jerk Frontier & Lag",
        "Filter SNR & Orthogonality VIF",
    )
    kpi_cards = "".join(
        f"""
        <div class="ql-kpi-skeleton-card" aria-hidden="true">
          <div style="font-size:12px;color:{TEXT_MUTED_DARK};">{label}</div>
          <div style="height:22px;width:62%;background:{CARD_BORDER_DARK};border-radius:4px;"></div>
          <div style="height:12px;width:45%;background:{PROGRESS_TRACK_DARK};border-radius:4px;"></div>
        </div>
        """
        for label in kpi_labels
    )
    return f"""
<div class="ql-skeleton-workspace" data-skeleton-symbol="{sym_esc}" aria-hidden="true">
  <div class="ql-kpi-skeleton-grid">
    {kpi_cards}
  </div>
  <div class="ql-chart-skeleton">
    <div style="font-size:13px;color:{TEXT_MUTED_DARK};">
      Preparing Causal Point-in-Time Canvas ({sym_esc})...
    </div>
    <svg viewBox="0 0 600 120" width="100%" height="140" preserveAspectRatio="none" style="opacity:0.25;">
      <path d="M0,70 Q75,20 150,65 T300,55 T450,75 T600,40" fill="none" stroke="{PROGRESS_GRADIENT_START}" stroke-width="3" />
      <path d="M0,90 Q75,50 150,80 T300,70 T450,85 T600,60" fill="none" stroke="{PROGRESS_GRADIENT_END}" stroke-width="2" stroke-dasharray="5,5" />
    </svg>
    <div class="ql-skeleton-watermark">Awaiting surrogate convergence...</div>
  </div>
</div>
"""


def render_completed_summary_bar_html(
    telemetry: PipelineExecutionTelemetry,
    *,
    available_bars: int | None = None,
    requested_bars: int | None = None,
    resampled_from: str | None = None,
    timeframe_label: str | None = None,
) -> str:
    """Render the compact post-load 40px summary bar and optional SPEC-CTRL-TF-02 history pills."""
    sym_esc = html.escape(telemetry.symbol)
    ind_esc = html.escape(telemetry.indicator_name)
    tf_esc = html.escape(timeframe_label or telemetry.timeframe)
    shown_bars = telemetry.bars if available_bars is None else int(available_bars)

    extra_badges: list[str] = []
    if available_bars is not None and requested_bars is not None and int(available_bars) < int(requested_bars):
        extra_badges.append(
            f'<span class="ql-clamped-pill">'
            f"Using all {int(available_bars)} available {tf_esc} bars for {sym_esc} "
            f"(requested {int(requested_bars)})."
            f"</span>"
        )
    if resampled_from and resampled_from.strip():
        src_esc = html.escape(resampled_from.strip())
        extra_badges.append(
            f'<span class="ql-resampled-pill">'
            f"Resampled {tf_esc} bars from {src_esc} history."
            f"</span>"
        )

    extra_html = (
        f'<div class="ql-context-pills" style="margin-top:6px;margin-bottom:0;">{"".join(extra_badges)}</div>'
        if extra_badges
        else ""
    )

    return f"""
<div class="ql-summary-bar" role="status" aria-live="polite" aria-label="Pipeline Execution Summary" data-spec-id="{telemetry.spec_id}">
  <div>
    <span class="ql-summary-bar-check">✓</span>
    <strong>Completed in {telemetry.elapsed_seconds:.1f}s</strong>
    <span> • {sym_esc} ({shown_bars} bars, {telemetry.n_surrogates} surrogates)</span>
    {extra_html}
  </div>
  <div class="ql-context-pills" style="margin-bottom:0;">
    <span class="ql-context-pill">{sym_esc}</span>
    <span class="ql-context-pill">{tf_esc}</span>
    <span class="ql-context-pill">{ind_esc}</span>
    <span class="ql-context-pill">Seed: {telemetry.seed}</span>
  </div>
</div>
"""


def render_insufficient_history_html(
    symbol: str,
    timeframe: str,
    available_bars: int,
    minimum_bars: int = 35,
    indicator_name: str | None = None,
) -> str:
    """Render the SPEC-CTRL-TF-02 inline callout when returned bars fall below minimum proof floor."""
    sym_esc = html.escape(symbol)
    tf_esc = html.escape(timeframe)
    ind_note = f" (active indicator: {html.escape(indicator_name)})" if indicator_name else ""
    return f"""
<div class="ql-insufficient-callout" role="alert" data-spec-id="SPEC-CTRL-TF-02">
  <div class="ql-insufficient-callout-title">⚠️ Insufficient Historical Sample on {tf_esc}</div>
  <div>
    Insufficient history: {sym_esc} only has {int(available_bars)} bars on {tf_esc}
    (minimum {int(minimum_bars)} required for indicator &amp; stationarity proofs){ind_note}.
    Switch to 1W or 1D.
  </div>
</div>
"""


def render_warm_dimmed_banner_html(telemetry: PipelineExecutionTelemetry) -> str:
    """Render the compact warm-state re-computation status bar above dimmed charts."""
    ind_esc = html.escape(telemetry.indicator_name)
    sym_esc = html.escape(telemetry.symbol)
    pct_int = int(round(telemetry.overall_progress_pct))
    return f"""
<div class="ql-summary-bar" role="status" aria-live="polite" data-warm-reload="true">
  <div class="ql-status-title-cluster" style="font-size:14px;">
    <span class="ql-spinner" aria-hidden="true"></span>
    <span>Updating {ind_esc} &amp; {telemetry.n_surrogates} Surrogates ({sym_esc})...</span>
  </div>
  <div class="ql-telemetry-cluster">
    <span>{pct_int}%</span>
    <span class="ql-elapsed-badge">Elapsed: {format_elapsed_timer(telemetry.elapsed_seconds)}</span>
  </div>
</div>
"""
