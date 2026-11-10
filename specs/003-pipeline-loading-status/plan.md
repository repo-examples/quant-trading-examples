# Implementation Plan: Quantitative Pipeline Loading Status & Skeleton UI (`SPEC-QUANT-LOAD-01`)

**Branch**: `feat/003-pipeline-loading-status` | **Date**: 2026-11-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-pipeline-loading-status/spec.md`

## Summary

Implement the **QuantLab Loading State UI Specification (`SPEC-QUANT-LOAD-01`)** to eliminate blank-canvas wait states during market data synthesis, technical indicator evaluation, Monte Carlo surrogate simulations, and DSP/Pine Script v6 compilation. The implementation introduces:
1. A pure, typed telemetry state machine and HTML/CSS component renderer in `src/quantlab/dashboard/loading_state.py` implementing the 4-stage weighted progress bar (`0% -> 20% -> 40% -> 85% -> 100%`), per-surrogate progress telemetry (`40% + 45% * (i / N)`), parameter context pills, responsive 4-column KPI & 360px primary chart shimmer skeletons, warm-state 45% opacity chart dimming, mid-run parameter restart badges, long-running warnings (`> 15s` or high bars/surrogates), post-load collapsible summary bar with execution log, error recovery CTAs (`Retry Run`, `Reset to Default Seed`, `Cancel Run`), and WCAG 2.1 AA accessibility (`role="progressbar"`, stage-throttled `aria-live="polite"`, `prefers-reduced-motion: reduce`).
2. Non-invasive callback instrumentation in `src/quantlab/proofs/entropy.py`, `src/quantlab/proofs/stats_gate.py`, and `src/quantlab/dashboard/app.py` that streams live `PipelineExecutionTelemetry` snapshots without altering causal Point-in-Time (PIT) alignment or deterministic random number generation.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: `streamlit`, `plotly`, `numpy`, `scipy`, `numba`, `sympy`, `typer`, `rich`

**Storage**: Local Parquet OHLCV cache (`quantlab.data.loader`) + Streamlit `st.session_state` for warm-reload bundle caching and execution telemetry

**Testing**: `pytest` + `ruff`

**Target Platform**: Responsive Web Desktop (`>= 1024px`), Tablet (`768px–1023px`), and Mobile (`< 768px`) via Streamlit Dark Theme (`#0E1117` / `#0B0F19`)

**Project Type**: CLI + Interactive 4-Quadrant Quantitative Research Web Application

**Performance Goals**: `< 100ms` initial loading card + skeleton render; zero overhead on Numba/vectorized mathematical kernels; stage-throttled ARIA announcements (`<= 5` per run)

**Constraints**: Strict causal Point-in-Time (PIT) invariance; deterministic RNG reproducibility across identical seeds; immutable `@dataclass(frozen=True)` telemetry structures

**Scale/Scope**: 4 pipeline stages, up to 2,000 PIT bars and 100 Monte Carlo surrogates per indicator across 8 registered baseline and physics indicators

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Causal Point-in-Time (PIT) Alignment (NON-NEGOTIABLE)**: **PASS** — Telemetry callbacks only observe stage boundaries and completed surrogate iterations; no future bar data ($t > T$) or RNG state is modified.
- **II. Dual Neuro-Symbolic Indicator Representation**: **PASS** — All 8 registered indicators preserve their `@numba.njit` kernels and `sympy.Expr` AST transpilation to Pine Script v6 (`//@version=6`).
- **III. Information-Theoretic & Statistical Proof Gating**: **PASS** — Stationarity (ADF), Entropy/TE (IAAFT/block-shuffle surrogates), Stats/VIF, and Hilbert DSP Pareto gates remain unchanged and are surfaced in the 4-stage telemetry checklist.
- **IV. Vectorization, JIT Acceleration & Strict Static Typing**: **PASS** — All new state structures (`PipelineStageStatus`, `PipelineExecutionTelemetry`) use `@dataclass(frozen=True)` with full Python 3.11+ type annotations and pass `ruff` checks cleanly.
- **V. CLI-First Architecture & Deterministic Reproducibility**: **PASS** — `quantlab dashboard --check` verifies both the 4-quadrant bundle and the 4-stage `SPEC-QUANT-LOAD-01` telemetry sequence deterministically offline.

## Project Structure

### Documentation (this feature)

```text
specs/003-pipeline-loading-status/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── loading-ui-contract.md
├── checklists/
│   ├── requirements.md
│   └── ux-loading.md    # Phase 6 output (/speckit-checklist command)
└── tasks.md             # Phase 7 output (/speckit-tasks command)
```

### Source Code (repository root)

```text
src/
└── quantlab/
    ├── cli.py
    ├── data/
    │   ├── loader.py
    │   └── stationarity.py
    ├── indicators/
    │   ├── baselines.py
    │   ├── custom_examples.py
    │   └── registry.py
    ├── proofs/
    │   ├── dsp.py
    │   ├── entropy.py           # + optional surrogate_progress_callback
    │   └── stats_gate.py        # + optional surrogate_progress_callback pass-through
    ├── transpiler/
    │   └── pine_v6.py
    └── dashboard/
        ├── loading_state.py     # NEW: SPEC-QUANT-LOAD-01 telemetry state machine & HTML/CSS builders
        └── app.py               # Updated: 4-stage instrumented pipeline + warm/cold/error/collapsed UI states

tests/
├── test_cli_and_dashboard.py    # Updated: CLI dashboard --check & bundle telemetry integration tests
└── test_loading_state_ui.py     # NEW: Comprehensive unit tests for SPEC-QUANT-LOAD-01 states, progress math, skeletons & ARIA
```

**Structure Decision**: Single Python package under `src/quantlab/` with a dedicated `src/quantlab/dashboard/loading_state.py` module for `SPEC-QUANT-LOAD-01` state models and HTML/CSS renderers, integrated into `src/quantlab/dashboard/app.py` and tested in `tests/test_loading_state_ui.py` and `tests/test_cli_and_dashboard.py`.

## Complexity Tracking

No Constitution violations exist.
