# UI & API Contracts: Quantitative Pipeline Loading Status & Skeleton UI (`SPEC-QUANT-LOAD-01`)

## 1. Python Module Contracts (`quantlab.dashboard.loading_state` & `quantlab.dashboard.app`)

### `compute_stage_progress_pct`
```python
def compute_stage_progress_pct(
    stage_index: int,
    stage_fraction: float = 0.0,
    current_surrogate: int = 0,
    total_surrogates: int = 30,
) -> float:
    """Compute weighted determinate progress percentage in [0.0, 100.0] per SPEC-QUANT-LOAD-01."""
```

### `build_initial_telemetry` & Transition Helpers
```python
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
) -> PipelineExecutionTelemetry: ...

def advance_telemetry_stage(
    telemetry: PipelineExecutionTelemetry,
    active_stage: int,
    elapsed_seconds: float,
    completed_stage_duration: float | None = None,
) -> PipelineExecutionTelemetry: ...

def update_surrogate_telemetry(
    telemetry: PipelineExecutionTelemetry,
    current_surrogate: int,
    elapsed_seconds: float,
) -> PipelineExecutionTelemetry: ...

def complete_telemetry(
    telemetry: PipelineExecutionTelemetry,
    elapsed_seconds: float,
    stage4_duration: float,
) -> PipelineExecutionTelemetry: ...

def fail_telemetry(
    telemetry: PipelineExecutionTelemetry,
    error_step: int,
    error_message: str,
    elapsed_seconds: float,
) -> PipelineExecutionTelemetry: ...

def cancel_telemetry(
    telemetry: PipelineExecutionTelemetry,
    elapsed_seconds: float,
) -> PipelineExecutionTelemetry: ...
```

### HTML/CSS Renderers
```python
def build_loading_theme_css() -> str:
    """Return the <style> block defining SPEC-QUANT-LOAD-01 tokens, responsive breakpoints, shimmer, and reduced-motion rules."""

def render_pipeline_status_card_html(telemetry: PipelineExecutionTelemetry) -> str:
    """Render the Multi-Stage Pipeline Status Card HTML with ARIA progressbar, throttled aria-live region, and 4-stage checklist."""

def render_shimmer_skeletons_html(symbol: str = "SYNTH:COUPLED_OU") -> str:
    """Render the 4-column KPI shimmer skeleton row (96px height) and primary chart skeleton (360px height)."""

def render_completed_summary_bar_html(telemetry: PipelineExecutionTelemetry) -> str:
    """Render the post-load compact 40px summary bar and execution log breakdown HTML."""

def render_warm_dimmed_banner_html(telemetry: PipelineExecutionTelemetry) -> str:
    """Render warm-state re-computation status banner while existing charts remain visible at 45% opacity."""
```

### Instrumented Dashboard Bundle Builder
```python
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
) -> DashboardBundle: ...

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
) -> tuple[DashboardBundle, list[PipelineExecutionTelemetry]]: ...
```

## 2. DOM, Design Token & Accessibility Contract (`SPEC-QUANT-LOAD-01`)

- **Status Card Container**:
  - Attributes: `role="region"`, `aria-label="Quantitative Pipeline Execution Status"`, `aria-busy="true"` (when running) or `aria-busy="false"` (when completed/error/cancelled).
  - Styling: `#1A1D24` background, `1px solid #2D313E` border, `12px` border radius, `20px` padding, `24px` bottom margin.
- **Progress Bar**:
  - Attributes: `role="progressbar"`, `aria-valuemin="0"`, `aria-valuemax="100"`, `aria-valuenow="{int(overall_progress_pct)}"`, `aria-valuetext="Step {k} of 4: {stage_title}, {int(overall_progress_pct)} percent complete"`.
  - Styling: `#262730` track (`height: 6px; border-radius: 9999px;`), fill `linear-gradient(90deg, #7C4DFF 0%, #FF4B4B 100%)` (or `#FF4B4B` solid on error, `#21C354` on completion).
- **Screen-Reader Live Region**:
  - Visually hidden element with `aria-live="polite"` and `aria-atomic="true"` containing `telemetry.aria_announcement`.
- **Responsive Shimmer Skeletons**:
  - `.ql-kpi-skeleton-grid`: `grid-template-columns: repeat(4, 1fr)` on desktop (`>= 1024px`), `repeat(2, 1fr)` on tablet (`768px–1023px`), `1fr` on mobile (`< 768px`), `16px` gap, cards `height: 96px; border-radius: 10px;`.
  - `.ql-chart-skeleton`: `height: 360px; border-radius: 12px;` with `"Awaiting surrogate convergence..."` watermark.
  - `@media (prefers-reduced-motion: reduce)`: disables `ql-shimmer-sweep` and `ql-spin` animations.
