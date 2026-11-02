# Tasks: Quantitative Pipeline Loading Status & Skeleton UI (`SPEC-QUANT-LOAD-01`)

**Input**: Design documents from `/specs/003-pipeline-loading-status/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/loading-ui-contract.md`

**Tests**: Unit and integration tests are included in `tests/test_loading_state_ui.py` and `tests/test_cli_and_dashboard.py` per Constitution Quality Gates.

**Organization**: Tasks are grouped by phase (`Setup` -> `Foundational` -> `User Story 1 [US1]` -> `User Story 2 [US2]` -> `User Story 3 [US3]` -> `Polish`) to enable independent implementation and verification.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (`[US1]`, `[US2]`, `[US3]`)
- Exact file paths are included in every task description.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize module exports and verify baseline test/lint environment.

- [X] T001 Verify baseline `pytest` and `ruff` workspace status across `src/quantlab/` and `tests/`
- [X] T002 Create `src/quantlab/dashboard/loading_state.py` module scaffold with `SPEC-QUANT-LOAD-01` design token constants (`#0E1117`, `#1A1D24`, `#2D313E`, `#7C4DFF`, `#FF4B4B`, `#262730`, `#21C354`, `#6E7687`, `#F59E0B`, `#161922`, `#1F2430`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core immutable telemetry data models (`PipelineStageStatus`, `PipelineExecutionTelemetry`), weighted progress calculation (`0% -> 20% -> 40% -> 85% -> 100%`), and non-invasive surrogate callback hooks.

- [X] T003 Implement `@dataclass(frozen=True)` entities `PipelineStageStatus` (`1 <= stage_index <= 4`, `state` in `"pending" | "active" | "completed" | "failed" | "cancelled"`, `duration_seconds >= 0.0` when completed, `weight_start_pct`, `weight_end_pct`) and `PipelineExecutionTelemetry` (`spec_id="SPEC-QUANT-LOAD-01"`, `len(stages) == 4`, `0.0 <= overall_progress_pct <= 100.0`, `0 <= current_surrogate <= n_surrogates`) in `src/quantlab/dashboard/loading_state.py`
- [X] T004 Implement `compute_stage_progress_pct`, `is_long_running_load` (`bars > 1500` or `n_surrogates > 60` or `elapsed_seconds > 15.0`), `build_initial_telemetry`, `advance_telemetry_stage`, `update_surrogate_telemetry`, `complete_telemetry`, `fail_telemetry`, and `cancel_telemetry` in `src/quantlab/dashboard/loading_state.py`
- [X] T005 [P] Add optional `surrogate_progress_callback: Callable[[int, int], None] | None = None` to `evaluate_entropy_proof` in `src/quantlab/proofs/entropy.py` and `run_proof_suite` in `src/quantlab/proofs/stats_gate.py` without altering causal PIT calculations or RNG state

**Checkpoint**: Foundational telemetry state machine and callback hooks ready.

---

## Phase 3: User Story 1 - Multi-Stage Pipeline Status Card & Cold-Load Shimmer Skeletons (Priority: P1) 🎯 MVP

**Goal**: Render the 4-Stage Pipeline Status Card (`0% -> 20% -> 40% -> 85% -> 100%`), per-surrogate progress counter (`i / N surrogates`), parameter context pills, and Cold-Load Shimmer Skeletons (4 KPI cards + 360px primary chart skeleton).

**Independent Test**: Run `build_dashboard_bundle_with_telemetry` and verify all 4 stage transitions, exact per-surrogate progress increments (`40% + 45% * (i / N)`), status card HTML, and shimmer skeleton HTML in `tests/test_loading_state_ui.py`.

### Implementation for User Story 1

- [X] T006 [US1] Implement `build_loading_theme_css`, `render_pipeline_status_card_html`, and `render_shimmer_skeletons_html` (4 KPI skeleton cards at `height: 96px, border-radius: 10px` and primary chart skeleton at `height: 360px, border-radius: 12px` with `"Awaiting surrogate convergence..."` watermark and responsive breakpoints `>= 1024px`, `768px-1023px`, `< 768px`) in `src/quantlab/dashboard/loading_state.py`
- [X] T007 [US1] Instrument `build_dashboard_bundle` and add `build_dashboard_bundle_with_telemetry` in `src/quantlab/dashboard/app.py` to emit `PipelineExecutionTelemetry` snapshots across Stage 1 (`fetch_ohlcv`), Stage 2 (`active_spec` evaluation & stationarity/stats gates), Stage 3 (per-surrogate loop via `surrogate_progress_callback`), and Stage 4 (Pareto DSP frontier, `transpile_to_pine_v6`, and figure assembly)
- [X] T008 [US1] Wire Cold-Load status card placeholder and shimmer skeleton placeholder into `render_streamlit_app` in `src/quantlab/dashboard/app.py`
- [X] T009 [P] [US1] Write unit tests for Stage 1–4 weighted progress math, per-surrogate telemetry, status card DOM, and cold-load shimmer skeletons in `tests/test_loading_state_ui.py`

**Checkpoint**: User Story 1 (Cold-Load 4-Stage Status Card + Shimmer Skeletons) is complete and independently verified.

---

## Phase 4: User Story 2 - Reactive Warm-State Dimming, Mid-Run Restart Telemetry & Post-Load Summary Bar (Priority: P2)

**Goal**: Support warm re-computation with dimmed existing charts (`45%` opacity, `filter: blur(1px)`), mid-run parameter restart badge (`"Restarted pipeline with updated parameters"`), long-running amber warning (`> 15s` / high bars or surrogates), and post-load collapse into a single-line summary bar with an expandable execution log.

**Independent Test**: Verify warm-state telemetry headers (`"Updating {indicator} & {N} Surrogates..."`), `.ql-warm-dimmed` CSS/HTML wrapping, mid-run restart badge rendering, long-running warning trigger, and post-load summary bar + execution log HTML in `tests/test_loading_state_ui.py`.

### Implementation for User Story 2

- [X] T010 [US2] Implement `render_completed_summary_bar_html` and `render_warm_dimmed_banner_html` (including stage timing table, parameter context pills, mid-run restart amber badge, and long-running warning notice) in `src/quantlab/dashboard/loading_state.py`
- [X] T011 [US2] Update `render_streamlit_app` in `src/quantlab/dashboard/app.py` to track parameter signatures in `st.session_state`, render warm-state dimmed charts (`opacity: 0.45; filter: blur(1px)`) when a cached `DashboardBundle` exists, and collapse the completed status card into the compact summary bar with `st.expander("Show Execution Log ▾")`
- [X] T012 [P] [US2] Add unit tests for warm-state dimming, mid-run parameter restart badge, long-running warning thresholds, and post-load summary bar rendering in `tests/test_loading_state_ui.py`

**Checkpoint**: User Story 2 (Warm Dimming, Mid-Run Restart Badge, and Post-Load Summary Bar) is complete and independently verified.

---

## Phase 5: User Story 3 - Step-Level Error Recovery, User-Initiated Cancellation & Accessibility (Priority: P3)

**Goal**: Provide step-level error highlighting (`✕`, semantic red `#FF4B4B` progress bar, `"Failed at Step {k}: {reason}"`), recovery CTAs (`Retry Run`, `Reset to Default Seed`, `Cancel Run`), stage-throttled `aria-live="polite"` announcements (`<= 5` per run), and `@media (prefers-reduced-motion: reduce)` support.

**Independent Test**: Trigger simulated step failures and cancellations in `build_dashboard_bundle` and verify error state HTML, cancellation exception handling, ARIA progressbar/region attributes, stage-throttled `aria-live` announcements, and reduced-motion CSS in `tests/test_loading_state_ui.py`.

### Implementation for User Story 3

- [X] T013 [US3] Implement `PipelineCancelledError`, step-level failure catching (`fail_telemetry` at Steps 1–4), and `cancel_check` handling in `src/quantlab/dashboard/loading_state.py` and `src/quantlab/dashboard/app.py`
- [X] T014 [US3] Add `Cancel Run`, `Retry Run`, and `Reset to Default Seed` interactive recovery controls to `render_streamlit_app` in `src/quantlab/dashboard/app.py` and verify ARIA attributes (`role="region"`, `aria-busy`, `role="progressbar"`, throttled `aria-live="polite"`, `@media (prefers-reduced-motion: reduce)`) in `src/quantlab/dashboard/loading_state.py`
- [X] T015 [P] [US3] Add unit tests for step-level error states, user cancellation, stage-throttled `aria-live` announcements, and `prefers-reduced-motion: reduce` CSS in `tests/test_loading_state_ui.py`

**Checkpoint**: All 3 User Stories are complete and independently verified.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Self-check integration (`quantlab dashboard --check`), documentation, and full lint/test verification.

- [X] T016 Update `run_dashboard_self_check` in `src/quantlab/dashboard/app.py` and `test_cli_dashboard_check_and_4_quadrant_bundle` in `tests/test_cli_and_dashboard.py` to validate `SPEC-QUANT-LOAD-01` telemetry stages and progress completion
- [X] T017 [P] Update `README.md` and `CHANGELOG.md` to document the `SPEC-QUANT-LOAD-01` 4-Stage Pipeline Loading Status Card & Shimmer Skeleton UI
- [X] T018 Execute `uv run pytest -v`, `uv run ruff check src tests`, and `uv run quantlab dashboard --check` to confirm 100% green verification

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001–T002 start immediately.
- **Foundational (Phase 2)**: T003–T005 depend on Phase 1 and block User Story phases.
- **User Story 1 (Phase 3 - P1 MVP)**: T006–T009 depend on Phase 2.
- **User Story 2 (Phase 4 - P2)**: T010–T012 build on Phase 2 and extend US1 UI states.
- **User Story 3 (Phase 5 - P3)**: T013–T015 build on Phase 2 and add error/cancellation/a11y resilience.
- **Polish (Phase 6)**: T016–T018 run after all user stories are implemented.

### Parallel Opportunities

- `T005` (`entropy.py` / `stats_gate.py` callback hook) can run in parallel with `T003`–`T004` (`loading_state.py` models).
- Test tasks `T009`, `T012`, `T015` in `tests/test_loading_state_ui.py` map cleanly to their respective story implementations.
