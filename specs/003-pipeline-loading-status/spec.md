# Feature Specification: Quantitative Pipeline Loading Status & Skeleton UI (`SPEC-QUANT-LOAD-01`)

**Feature Branch**: `feat/003-pipeline-loading-status`

**Created**: 2026-11-02

**Status**: Approved

**Input**: User description: "Implement QuantLab Loading State UI Specification (`SPEC-QUANT-LOAD-01`) from https://share.gemini.google/3AKHTImGhhKI with reactive auto-run on sidebar parameter changes, warm-state chart dimming (45% opacity), mid-run restart badge, 4-stage pipeline telemetry, shimmer skeletons, error recovery CTAs, and post-load collapse into a summary bar with expandable execution log."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Multi-Stage Pipeline Status Card & Cold-Load Shimmer Skeletons (Priority: P1)

When a researcher first opens the QuantLab interactive diagnostic workspace or performs a cold load, the main canvas must immediately display a structured **Multi-Stage Pipeline Status Card** directly below the application subtitle alongside **Structural Shimmer Skeletons** for the KPI metric row and primary chart canvas—eliminating the blank `#0E1117` screen during multi-second quantitative evaluations.

**Why this priority**: Currently, 85% of the viewport remains blank while data synthesis, indicator computation, Monte Carlo surrogate simulations, and DSP frontier analysis execute sequentially, making the application appear frozen or crashed.

**Independent Test**: Open the dashboard on a cold session and verify that the 4-stage Pipeline Status Card and 4-card KPI + 360px primary chart shimmer skeletons render immediately, advance deterministically across all 4 stages (`0% -> 20% -> 40% -> 85% -> 100%`) with live surrogate counter telemetry (`i / N surrogates`), and collapse into a completion summary bar once finished.

**Acceptance Scenarios**:

1. **Given** an initial cold load with active sidebar parameters (`{symbol}`, `{timeframe}`, `{bars}`, `{indicator}`, `{n_surrogates}`, `{seed}`), **When** the quantitative pipeline begins, **Then** the workspace immediately renders the Pipeline Status Card titled `"Running Quantitative Pipeline for {symbol} ({bars} bars)..."` with an animated dual-ring spinner, monospace elapsed timer (`Elapsed: 00:XX.Xs`), weighted percentage readout (`0%–100%`), parameter context pills (`{symbol}`, `{timeframe}`, `{indicator}`), and a 6px gradient progress bar (`#7C4DFF -> #FF4B4B`).
2. **Given** an active cold-load pipeline run, **When** the pipeline advances through the 4 stages, **Then** the 4-Stage Telemetry Checklist updates live:
   - **Stage 1 (`0% -> 20%`)**: Synthesizing / Fetching Market Data (`{symbol} • {timeframe} • {bars} PIT bars`), recording checkmark `✓` and execution duration (`0.Xs`) upon completion.
   - **Stage 2 (`20% -> 40%`)**: Computing Active Indicator (`{indicator}`), recording checkmark `✓` and execution duration (`0.Xs`) upon completion.
   - **Stage 3 (`40% -> 85%`)**: Simulating Monte Carlo Surrogates (`{i} / {N} surrogates • Seed: {seed}`), incrementing progress dynamically per surrogate (`40% + 45% * (i / N)`) with active spinner `⟳` and bold `#FAFAFA` text.
   - **Stage 4 (`85% -> 100%`)**: Evaluating Hilbert Phase-Jerk Frontier & Pine v6 Transpiler, transitioning from pending `○` (`#6E7687`) to active `⟳` and completed `✓`.
3. **Given** an initial cold load where no prior charts exist in the session, **When** the pipeline is executing Stages 1–4, **Then** a 4-column KPI shimmer skeleton row (`height: 96px`, `radius: 10px`) and a primary chart shimmer skeleton (`height: 360px`, `radius: 12px`, watermark `"Awaiting surrogate convergence..."`) are displayed below the status card and replaced by the live KPI metrics and 4-quadrant tabs upon 100% completion.

---

### User Story 2 - Reactive Warm-State Dimming, Mid-Run Restart Telemetry & Post-Load Summary Bar (Priority: P2)

When a researcher modifies any parameter in the Research Controls sidebar after an initial run has completed (warm state) or while a run is in progress (mid-run state), the workspace must reactively re-run without flashing back to an empty screen, preserving previously rendered charts at reduced opacity (`45%` with subtle blur) during warm updates and collapsing the completed status card into a single-line summary bar with an expandable execution log.

**Why this priority**: Quantitative researchers iteratively tune bar counts, indicators, and surrogate counts; preserving visual context during warm re-computation prevents visual jarring and provides an auditable timing breakdown after completion.

**Independent Test**: Complete an initial pipeline run, verify the status card collapses into the compact summary bar (`"✓ Completed in X.Xs • {symbol} ({bars} bars, {n_surrogates} surrogates)"`) with an expandable execution log, then change the active indicator or surrogate count and verify that the status header shows `"Updating {indicator} & {n_surrogates} Surrogates..."` while existing charts remain visible in a dimmed (`45%` opacity) state until the new bundle replaces them.

**Acceptance Scenarios**:

1. **Given** Stage 4 reaches `100%`, **When** computation finishes, **Then** the Pipeline Status Card transitions into a compact collapsible summary bar displaying `"✓ Completed in {total_seconds}s • {symbol} ({bars} bars, {n_surrogates} surrogates)"` with an expandable `"Show Execution Log"` disclosure containing the per-stage timing breakdown and parameter snapshot.
2. **Given** charts and KPIs from a previous run are already rendered in the session (warm state), **When** the user modifies a Research Controls parameter, **Then** the status banner displays `"Updating {indicator} & {n_surrogates} Surrogates..."` (plus a `"Restarted pipeline with updated parameters"` amber badge when parameters changed relative to the prior run) while keeping the existing KPI row and 4-quadrant charts visible at `45%` opacity (`filter: blur(1px)`) instead of clearing back to blank shimmer skeletons.
3. **Given** a user selects a high computational load (`bars > 1500` or `n_surrogates > 60`, or elapsed runtime exceeds `15s`), **When** the pipeline is running, **Then** the elapsed timer badge shifts to semantic amber (`#F59E0B`) and displays the helper warning `"High surrogate count / bar history selected. Computation may take ~25s."`

---

### User Story 3 - Step-Level Error Recovery, User-Initiated Cancellation & Accessibility (Priority: P3)

When a data provider fetch fails, a numerical computation raises an error, or the user cancels an active run, the Pipeline Status Card must surface clear step-level failure diagnostics with one-click recovery actions (`Retry Run`, `Reset to Default Seed`, `Cancel Run`), while adhering to WCAG 2.1 AA contrast, reduced-motion preferences, and throttled screen-reader announcements.

**Why this priority**: Network fetches (`yfinance`/`ccxt`) or extreme parameter combinations can fail or take longer than desired; researchers need non-destructive recovery actions and accessible assistive-technology support.

**Independent Test**: Trigger a simulated or real failure at any pipeline step (or click `Cancel Run`), verify that the progress bar turns semantic red (`#FF4B4B`), the active stage icon becomes `✕`, skeletons hide, and clicking `Retry Run` or `Reset to Default Seed` recovers the pipeline cleanly.

**Acceptance Scenarios**:

1. **Given** an exception occurs during any of the 4 pipeline stages (e.g., network failure in Stage 1 or numerical error in Stage 2/3/4), **When** the exception is caught by the pipeline runner, **Then** the progress bar turns semantic red (`#FF4B4B`), the failed stage displays `✕` with `"Failed at Step {k}: {reason}"`, shimmer skeletons hide, and interactive `Retry Run` and `Reset to Default Seed` recovery buttons are presented.
2. **Given** a pipeline run is actively executing or requested to cancel via the inline `Cancel Run` control, **When** the user triggers `Cancel Run`, **Then** the pipeline aborts remaining stages cleanly and either restores the last cached warm result with a cancelled status notice or displays a cancelled state with a `Retry Run` button.
3. **Given** a user with screen-reader assistive technology or `prefers-reduced-motion: reduce` enabled, **When** the pipeline executes, **Then** the status region exposes `role="region"`, `aria-label="Quantitative Pipeline Execution Status"`, `aria-busy="true"`, a `role="progressbar"` element with `aria-valuenow`/`aria-valuetext`, a visually hidden `aria-live="polite"` region that announces only stage transitions (not every individual surrogate iteration), and CSS media rules that replace sweeping shimmer animations with a static/gentle opacity state under reduced motion.

---

### Edge Cases

- **Rapid Mid-Run Sidebar Parameter Adjustments**: When a user drags a slider (`PIT History Bars` or `Monte Carlo Surrogates`) while a run is in progress, the pipeline detects the parameter hash change, aborts the superseded run, displays an amber `"Restarted pipeline with updated parameters"` badge, and starts cleanly from Stage 1 with the updated parameters.
- **Collapsed Sidebar on Tablet / Mobile (`< 1024px`)**: When the left Research Controls drawer is collapsed on narrow screens, parameter context pills (`{symbol}`, `{timeframe}`, `{indicator}`, `{bars} bars`, `Seed {seed}`) inside the Pipeline Status Card remain visible so the researcher always sees which configuration is loading.
- **Long-Running Computation (`> 15s` or high bar/surrogate counts)**: When `bars > 1500`, `n_surrogates > 60`, or elapsed time exceeds `15.0s`, an amber warning badge and helper note inform the user of the expected duration so the run is not mistaken for a hang.
- **Step-Level Partial Failure**: If Stage 1 succeeds (`✓`) and Stage 2 or Stage 3 fails (`✕`), completed stages retain their green checkmarks and durations while the failing stage is highlighted in red with actionable recovery buttons.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The workspace MUST render a **Multi-Stage Pipeline Status Card** directly below the dashboard subtitle whenever the quantitative pipeline is executing or has completed.
- **FR-002**: The Pipeline Status Card MUST track and display 4 sequential execution stages with weighted determinate progress (`0% -> 100%`):
  1. **Stage 1 (`0% -> 20%`)**: Synthesizing / Fetching Market Data (`{symbol} • {timeframe} • {bars} PIT bars`)
  2. **Stage 2 (`20% -> 40%`)**: Computing Active Indicator (`{indicator}`)
  3. **Stage 3 (`40% -> 85%`)**: Simulating Monte Carlo Surrogates (`{i} / {N} surrogates • Seed: {seed}`), dynamically updating progress per surrogate iteration $i \in [1, N]$ as $40\% + 45\% \times (i / N)$
  4. **Stage 4 (`85% -> 100%`)**: Evaluating Hilbert Phase-Jerk Frontier & Pine v6 Transpiler
- **FR-003**: Each stage row in the 4-Stage Telemetry Checklist MUST display its semantic state icon (`✓` completed in `#21C354` with elapsed seconds, `⟳` active in `#FF4B4B`/`#7C4DFF` with bold `#FAFAFA` label, `○` pending in `#6E7687`, or `✕` failed in `#FF4B4B`).
- **FR-004**: During an **Initial Cold Load** (when no prior `DashboardBundle` exists in the session), the workspace MUST display **Structural Shimmer Skeletons** below the Pipeline Status Card comprising a 4-card KPI skeleton grid (`height: 96px`, `radius: 10px`) and a primary chart skeleton (`height: 360px`, `radius: 12px`, watermark `"Awaiting surrogate convergence..."`).
- **FR-005**: During a **Warm Re-Computation** (when a previous `DashboardBundle` is already cached in session state and the user changes a sidebar parameter), the workspace MUST display `"Updating {indicator} & {n_surrogates} Surrogates..."` in the status card while keeping the previously rendered KPI row and 4-quadrant charts visible in a dimmed state (`45%` opacity, `filter: blur(1px)`) until the new computation finishes.
- **FR-006**: When sidebar parameters are modified relative to an in-flight or prior run, the Pipeline Status Card MUST display an amber `"Restarted pipeline with updated parameters"` badge in the header.
- **FR-007**: Upon reaching `100%` completion, the Pipeline Status Card MUST collapse into a compact summary bar displaying `"✓ Completed in {elapsed}s • {symbol} ({bars} bars, {n_surrogates} surrogates)"` with an expandable `"Show Execution Log"` section listing per-stage durations and active parameter pills.
- **FR-008**: The Pipeline Status Card MUST include parameter context pills (`{symbol}`, `{timeframe}`, `{indicator}`) and responsive breakpoint CSS (`>= 1024px` 4-column KPI skeleton grid, `768px–1023px` 2x2 grid, `< 768px` single-column stack) so context is preserved when the sidebar drawer is collapsed on tablet/mobile viewports.
- **FR-009**: When `bars > 1500`, `n_surrogates > 60`, or elapsed time exceeds `15.0s`, the status card MUST transition the elapsed timer badge to amber (`#F59E0B`) and show a long-running computation warning note.
- **FR-010**: If any stage raises an exception, the status card MUST transition to the **Computation / Fetch Error** state with a red (`#FF4B4B`) progress bar, `✕` icon on the failing stage, descriptive `"Failed at Step {k}: {message}"` copy, hidden skeletons, and interactive `Retry Run` and `Reset to Default Seed` recovery controls.
- **FR-011**: The status card MUST provide an inline `Cancel Run` capability that aborts an active run and either reverts to the last cached warm result or displays a cancelled state with a `Retry Run` action.
- **FR-012**: All status card and skeleton HTML markup MUST include semantic ARIA attributes (`role="region"`, `aria-label="Quantitative Pipeline Execution Status"`, `aria-busy`, `role="progressbar"` with `aria-valuenow`/`aria-valuemin`/`aria-valuemax`/`aria-valuetext`), a stage-throttled visually hidden `aria-live="polite"` announcement region, and `@media (prefers-reduced-motion: reduce)` support.

### Key Entities

- **`PipelineStageStatus`**: Immutable state record for a single stage (`stage_index`, `label`, `detail`, `state` in `pending | active | completed | failed | cancelled`, `duration_seconds`, `progress_fraction`).
- **`PipelineExecutionTelemetry`**: Aggregate telemetry snapshot for an active or completed pipeline run (`symbol`, `provider`, `timeframe`, `bars`, `indicator_name`, `n_surrogates`, `seed`, `overall_progress_pct`, `elapsed_seconds`, `stages`, `current_surrogate`, `restarted_with_updated_params`, `is_warm_reload`, `long_running_warning`, `error_step`, `error_message`, `aria_announcement`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users receive immediate visual feedback (`0%` initial status card + shimmer skeletons or warm dimmed view) within `< 100ms` of initiating or modifying a quantitative research run, eliminating blank-canvas wait states (`0%` blank viewport time during loading).
- **SC-002**: Progress percentage updates deterministically across all 4 stages (`0% -> 20% -> 40% -> 85% -> 100%`), with Stage 3 reflecting exact per-surrogate completion (`40% + 45% * (i / N)`) for 100% of surrogate iterations.
- **SC-003**: Screen reader live announcements (`aria-live="polite"`) fire at most once per stage transition (maximum 5 announcements per full pipeline run regardless of whether `N=15` or `N=100` surrogates are simulated).
- **SC-004**: 100% of error states and user cancellations provide a one-click recovery path (`Retry Run` or `Reset to Default Seed` / cached fallback) without requiring a browser page reload.

## Assumptions

- Existing causal mathematical computations (`fetch_ohlcv`, `run_proof_suite`, `evaluate_multiple_indicators`, `transpile_to_pine_v6`) remain mathematically identical and strictly Point-in-Time (PIT) causal; progress callbacks observe execution without altering numerical outputs or random number generator streams.
- Headless verification (`quantlab dashboard --check` and `pytest`) can validate both the complete `DashboardBundle` and the new multi-stage pipeline telemetry/HTML rendering helpers deterministically without requiring a live browser session.
