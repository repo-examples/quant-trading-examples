# Phase 0 Research: Quantitative Pipeline Loading Status & Skeleton UI (`SPEC-QUANT-LOAD-01`)

## 1. Non-Invasive Telemetry Instrumentation of `build_dashboard_bundle`

- **Decision**: Introduce an optional `telemetry_callback: Callable[[PipelineExecutionTelemetry], None] | None = None` and `cancel_check: Callable[[], bool] | None = None` into `build_dashboard_bundle` (and `surrogate_progress_callback: Callable[[int, int], None] | None = None` into `run_proof_suite` and `evaluate_entropy_proof`).
- **Rationale**:
  - Preserves 100% backward compatibility with all existing callers (`run_dashboard_self_check`, CLI commands, and existing unit tests).
  - Avoids mutating any mathematical state or random number generator (`np.random.default_rng(seed)`) inside `generate_iaaft_surrogates`, `generate_block_shuffle_surrogates`, or `evaluate_entropy_proof`, guaranteeing strict Point-in-Time (PIT) causal invariance and identical numerical outputs.
  - Enables fine-grained Stage 3 progress updates (`40% + 45% * (i / N)`) after each surrogate iteration `i` of the active indicator.
- **Alternatives Considered**:
  - Running the pipeline in a background OS thread and polling from Streamlit: rejected because Streamlit's ScriptRunContext requires UI container updates (`st.empty().markdown(...)`) on the main script thread, and deterministic synchronous callbacks update `st.empty()` placeholders immediately at zero threading overhead.

## 2. Two-Tier Loading UI Architecture in Streamlit (`st.empty` + Design-Token HTML/CSS)

- **Decision**: Create `src/quantlab/dashboard/loading_state.py` providing pure, testable HTML/CSS builders and immutable telemetry state machines (`PipelineStageStatus`, `PipelineExecutionTelemetry`), wired into `render_streamlit_app()` via dedicated `st.empty()` slots directly below the dashboard subtitle.
- **Rationale**:
  - Native `st.spinner` or default `st.status` cannot render custom linear-gradient progress bars (`#7C4DFF -> #FF4B4B`), responsive 4-column shimmer skeletons (`#161922 -> #1F2430` $110^\circ$ sweep), parameter context pills, warm-state 45% opacity chart dimming (`filter: blur(1px)`), or custom ARIA live regions (`role="progressbar"`, throttled `aria-live="polite"`).
  - Rendering structured HTML/CSS into `st.empty()` placeholders allows sub-millisecond updates on every stage transition and surrogate tick while making the exact DOM output 100% unit-testable in headless `pytest` without launching a browser.
- **Alternatives Considered**:
  - Custom React component via `components.html` iframe for the loading card: rejected because iframes isolate CSS media queries, break main-canvas document flow, trap keyboard focus away from the sidebar, and prevent smooth cross-fading into the main Streamlit layout.

## 3. Warm-State Re-Computation vs. Cold-Load Shimmer Skeletons

- **Decision**: Cache the last successful `DashboardBundle` and active parameter signature `(provider, symbol, timeframe, bars, indicator_name, n_surrogates, seed)` in `st.session_state`.
  - When no prior bundle exists (**Initial Cold Load**), render `render_shimmer_skeletons_html()` (4 KPI skeleton cards + 360px chart skeleton with `"Awaiting surrogate convergence..."` watermark) in the workspace placeholder while the status card progresses from `0% -> 100%`.
  - When a prior bundle exists and parameters change (**Warm Re-Computation**), display the status card with `"Updating {indicator_name} & {n_surrogates} Surrogates..."` and `"Restarted pipeline with updated parameters"` badge while rendering a dimmed preview (`opacity: 0.45; filter: blur(1px)`) until the new bundle is ready.
- **Rationale**: Directly fulfills `SPEC-QUANT-LOAD-01` Section 2 (Conflict 1 & 2) and Section 5 (Exhaustive System States Matrix) as confirmed with the user during Phase 1 discovery.
- **Alternatives Considered**:
  - Clearing the canvas to shimmer skeletons on every parameter tweak: rejected because it causes jarring layout flashes when iteratively comparing indicators.

## 4. Screen-Reader Live Announcement Throttling & Reduced Motion

- **Decision**: Compute `aria_announcement` inside `PipelineExecutionTelemetry` only when `stage_index` or `system_state` transitions (maximum 5 announcements per run: Stage 1, Stage 2, Stage 3 start, Stage 4, Completed/Error/Cancelled). Include `@media (prefers-reduced-motion: reduce)` CSS rules to disable keyframe shimmer sweeps and SVG spinner rotations.
- **Rationale**: Streaming `1/30, 2/30, ...` to `aria-live="polite"` would flood assistive screen readers; throttling to stage boundaries satisfies WCAG 2.1 AA and `SPEC-QUANT-LOAD-01` Section 6.
