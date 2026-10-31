---
description: "Task list for QuantLab Information-Theoretic Indicator Research CLI, Transpiler & Diagnostic Dashboard"
---

# Tasks: QuantLab Information-Theoretic Indicator Research CLI, Transpiler & Diagnostic Dashboard

**Input**: Design documents from `/specs/001-quantlab-research-suite/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/cli-and-transpiler-contract.md`

**Tests**: Automated `pytest` suites are included for every user story to verify causal Point-in-Time (PIT) zero-lookahead invariance, ground-truth Transfer Entropy discrimination, SymPy-to-Pine v6 compilation, CLI commands, and 4-Quadrant Dashboard state/chart construction.

**Organization**: Tasks are grouped by user story (`US1`..`US4`) following Setup and Foundational phases.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story label (`[US1]`, `[US2]`, `[US3]`, `[US4]`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize Python 3.11+ package structure, dependencies (`pyproject.toml`), and subpackage initializers.

- [X] T001 Create `pyproject.toml` at repository root with `quantlab` metadata, dependencies (`typer`, `rich`, `sympy`, `numpy`, `scipy`, `numba`, `pandas`, `pyarrow`, `yfinance`, `ccxt`, `streamlit`, `plotly`, `lightweight-charts`), `[project.scripts] quantlab = "quantlab.cli:app"`, and `pytest`/`ruff` dev dependencies in `pyproject.toml`
- [X] T002 [P] Create package and subpackage initializers in `src/quantlab/__init__.py`, `src/quantlab/data/__init__.py`, `src/quantlab/indicators/__init__.py`, `src/quantlab/proofs/__init__.py`, `src/quantlab/transpiler/__init__.py`, `src/quantlab/dashboard/__init__.py`, and `tests/__init__.py`
- [X] T003 [P] Configure `.gitignore` at repository root to exclude `.venv/`, `.cache/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `dist/`, and `*.egg-info/` in `.gitignore`

---

## Phase 2: Foundational (Core Neuro-Symbolic Registry Primitives)

**Purpose**: Establish the dual Neuro-Symbolic Indicator Registry and custom `sympy.Function` time-series AST primitives required by all downstream indicator, proof, transpiler, CLI, and dashboard modules.

- [X] T004 Implement custom `sympy.Function` AST operators (`Lag`, `Change`, `SMA`, `EMA`, `RMA`, `WMA`, `Stdev`, `Highest`, `Lowest`, `TrueRange`, `SymbolicRecurrence`), `OHLCVInputs`, `IndicatorSpec`, and `IndicatorRegistry` in `src/quantlab/indicators/registry.py`

**Checkpoint**: Foundation ready — User Story phases can now execute.

---

## Phase 3: User Story 1 - Point-in-Time Market Data & Fractional Stationarity Pipeline (Priority: P1) 🎯 MVP

**Goal**: Deliver PIT-validated OHLCV data ingestion (`yfinance`, `ccxt`, and deterministic coupled `synthetic` stochastic processes) with local `.cache/parquet/` storage and Fixed-Width Window Fractional Differentiation (FracDiff) with ADF stationarity search.

**Independent Test**: Run `pytest tests/test_data_stationarity.py` and verify Parquet caching, synthetic coupled process generation, minimum stationary fractional differentiation order $d^*$ ($p_{\text{ADF}} < 0.05$), and strict zero-lookahead invariance ($\text{max abs diff} < 10^{-12}$).

### Implementation for User Story 1

- [X] T005 [P] [US1] Implement `OHLCVDataset`, local `.cache/parquet/` read/write persistence, `yfinance` and `ccxt` fetchers with offline fallback, and deterministic `synthetic` stochastic generator (coupled Ornstein-Uhlenbeck, Heston volatility, and regime-switching jump-diffusion with ground-truth causal driver) in `src/quantlab/data/loader.py`
- [X] T006 [P] [US1] Implement Fixed-Width Window Fractional Differentiation (`compute_ffd_weights`, `frac_diff_ffd` with `@numba.njit` causal convolution), Augmented Dickey-Fuller (`adf_test`) regression with MacKinnon approximate $p$-values, and optimal minimum stationary order search (`find_min_ffd_d`, `StationarityResult`) in `src/quantlab/data/stationarity.py`
- [X] T007 [US1] Create unit and zero-lookahead invariance tests for `loader.py` and `stationarity.py` in `tests/test_data_stationarity.py`

**Checkpoint**: User Story 1 is complete and independently verified.

---

## Phase 4: User Story 2 - Dual Neuro-Symbolic Indicator Registry & Evaluation Gate (Priority: P1)

**Goal**: Implement the 5 standard TA baselines (`RSI`, `EMA`, `ATR`, `MACD`, `KAMA`), 3 physics-inspired indicators (`KalmanFilter`, `PhaseSpaceEnergy`, `EntropyFlow`), and the 3 mathematical proof modules (`entropy.py`, `stats_gate.py`, `dsp.py`) with automated Pass/Fail gates.

**Independent Test**: Run `pytest tests/test_indicators.py tests/test_proofs.py` and verify that all 8 indicators compute causally with zero lookahead leakage, and that Transfer Entropy against IAAFT/block-shuffle surrogates, Spearman Rank IC, Wasserstein regime distance, VIF orthogonality, and Hilbert/Bode/Jerk DSP frontier gates operate accurately.

### Implementation for User Story 2

- [X] T008 [P] [US2] Implement vectorized/`@numba.njit` kernels and symbolic `sympy.Expr` AST builders for the 5 baseline indicators (`RSI`, `EMA`, `ATR`, `MACD`, `KAMA`) and register them in `src/quantlab/indicators/baselines.py`
- [X] T009 [P] [US2] Implement `@numba.njit` kernels and symbolic/recurrence AST builders for the 3 physics-inspired indicators (`KalmanFilter` 1D kinematic state/velocity filter, `PhaseSpaceEnergy` Takens delay-embedding Hamiltonian energy, and `EntropyFlow` rolling Shannon/ordinal information flow) and register them in `src/quantlab/indicators/custom_examples.py`
- [X] T010 [P] [US2] Implement Information-Theoretic estimators (`shannon_entropy`, `permutation_entropy`, `rolling_shannon_entropy`, `mutual_information_ksg`, `symbolic_transfer_entropy`, `knn_transfer_entropy`) and Monte Carlo surrogate generators (`generate_iaaft_surrogates`, `generate_block_shuffle_surrogates`, `evaluate_entropy_proof`, `EntropyProofResult`) in `src/quantlab/proofs/entropy.py`
- [X] T011 [P] [US2] Implement Digital Signal Processing diagnostics (`compute_hilbert_diagnostics`, `compute_bode_response`, `compute_jerk_energy`, `identify_pareto_frontier`, `evaluate_dsp_proof`, `DSPResult`) in `src/quantlab/proofs/dsp.py`
- [X] T012 [US2] Implement Statistical & Orthogonality gates (`compute_rank_ic_profile`, `compute_wasserstein_regime_distance`, `compute_vif_and_correlations`, `evaluate_stats_gate`, `StatsGateResult`) and the unified `ProofSuiteResult` / `run_proof_suite` orchestrator in `src/quantlab/proofs/stats_gate.py`
- [X] T013 [P] [US2] Create unit and zero-lookahead tests for all 8 baseline and physics indicators in `tests/test_indicators.py`
- [X] T014 [US2] Create unit and synthetic ground-truth causal verification tests for `entropy.py`, `stats_gate.py`, and `dsp.py` in `tests/test_proofs.py`

**Checkpoint**: User Stories 1 and 2 are complete and independently verified.

---

## Phase 5: User Story 3 - SymPy-to-Pine Script v6 Transpiler & Markdown Research Card (Priority: P2)

**Goal**: Compile any registered `IndicatorSpec` or custom `sympy.Expr` into valid `//@version=6` TradingView Pine Script and generate a self-contained Markdown Research Card embedding the symbolic LaTeX equation, proof scorecard, and Pine Script v6 source code.

**Independent Test**: Run `pytest tests/test_transpiler.py` and verify that all 8 registered indicators and custom symbolic formulas compile to valid `//@version=6` Pine Script and produce complete Markdown Research Cards, while unsupported AST nodes raise `TranspilationError`.

### Implementation for User Story 3

- [X] T015 [US3] Implement `PineV6Transpiler`, `TranspilationError`, `TranspilationArtifact`, `transpile_to_pine_v6`, and `generate_research_card` in `src/quantlab/transpiler/pine_v6.py`
- [X] T016 [US3] Create unit tests for SymPy-to-Pine Script v6 AST compilation, recursive state generation, error handling, and Markdown Research Card generation in `tests/test_transpiler.py`

**Checkpoint**: User Stories 1, 2, and 3 are complete and independently verified.

---

## Phase 6: User Story 4 - CLI & 4-Quadrant Interactive Quant Diagnostic Dashboard (Priority: P2)

**Goal**: Expose all workflows via the `typer` + `rich` CLI (`quantlab fetch`, `indicators`, `evaluate`/`prove`, `transpile`, `dashboard`) and build the dark-mode 4-Quadrant Interactive Quant Diagnostic Dashboard (`src/quantlab/dashboard/app.py`).

**Independent Test**: Run `pytest tests/test_cli_and_dashboard.py` and execute `uv run quantlab dashboard --check` to verify all CLI subcommands and all 4 dashboard quadrants.

### Implementation for User Story 4

- [X] T017 [P] [US4] Implement the 4-Quadrant Interactive Quant Diagnostic Dashboard (`build_dashboard_state`, Q1 OHLCV + TradingView Lightweight Charts & 3D Takens Phase-Space Attractor, Q2 Entropy/MI/Transfer Entropy & Surrogate Histogram, Q3 Rank IC Decay / Regime Wasserstein Density / VIF / Bode Phase-Lag vs. Jerk Pareto Frontier, Q4 Live SymPy AST Editor & Pine Script v6 Transpiler + Research Card Preview, and `render_dashboard`) in `src/quantlab/dashboard/app.py`
- [X] T018 [US4] Implement the `typer` + `rich` CLI application (`fetch`, `indicators`, `evaluate`/`prove`, `transpile`, `dashboard`) in `src/quantlab/cli.py`
- [X] T019 [US4] Create CLI and 4-Quadrant Dashboard integration tests in `tests/test_cli_and_dashboard.py`

**Checkpoint**: All 4 User Stories are complete and independently verified.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Comprehensive documentation (`README.md`, `CHANGELOG.md`), code quality linting (`ruff`), and end-to-end quickstart verification.

- [X] T020 [P] Write comprehensive architectural, mathematical, CLI, and dashboard documentation in `README.md` and record the initial release features under `## [Unreleased]` in `CHANGELOG.md`
- [X] T021 Run `uv run pytest`, `uv run ruff check src tests`, and `quickstart.md` CLI verification commands to confirm 100% green execution

---

## Dependencies & Execution Order

- **Phase 1 (Setup)**: `T001`–`T003` (no dependencies)
- **Phase 2 (Foundational)**: `T004` (`registry.py` depends on `T001`–`T002`)
- **Phase 3 (US1 - Data & Stationarity)**: `T005`–`T007` (depends on Phase 1)
- **Phase 4 (US2 - Indicators & Proofs)**: `T008`–`T014` (depends on Phase 2 and Phase 3)
- **Phase 5 (US3 - Pine v6 Transpiler)**: `T015`–`T016` (depends on Phase 2 and Phase 4)
- **Phase 6 (US4 - CLI & 4-Quadrant Dashboard)**: `T017`–`T019` (depends on Phases 3, 4, 5)
- **Phase 7 (Polish & Verification)**: `T020`–`T021` (depends on Phase 6)

## Parallel Execution Examples

```text
# Parallel Data & Stationarity (US1):
T005 (src/quantlab/data/loader.py) || T006 (src/quantlab/data/stationarity.py)

# Parallel Indicators & Proofs (US2):
T008 (src/quantlab/indicators/baselines.py) || T009 (src/quantlab/indicators/custom_examples.py) || T010 (src/quantlab/proofs/entropy.py) || T011 (src/quantlab/proofs/dsp.py)
```

## Implementation Strategy

1. **MVP First (US1 + US2)**: Establish PIT data loading, FracDiff stationarity, the dual neuro-symbolic indicator registry, and the information-theoretic/statistical/DSP proof gates.
2. **Transpiler & Research Card (US3)**: Layer the SymPy-to-Pine Script v6 AST compiler and Markdown Research Card generator on top of the registry and proof suite.
3. **Interactive Interfaces (US4)**: Wire the Typer/Rich CLI and 4-Quadrant Streamlit/Plotly/Lightweight-Charts diagnostic dashboard.
