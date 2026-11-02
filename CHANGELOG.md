# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Quantitative Pipeline Loading Status & Skeleton UI (`SPEC-QUANT-LOAD-01` — `quantlab.dashboard.loading_state`, `quantlab.dashboard.app`)**:
  - `PipelineStageStatus`, `PipelineExecutionTelemetry`, and `PipelineCancelledError` immutable state models with weighted 4-stage progress calculation (`0% -> 20% -> 40% -> 85% -> 100%`) and live per-surrogate telemetry (`40% + 45% * (i / N)`).
  - Multi-Stage Pipeline Status Card (`render_pipeline_status_card_html`) with linear-gradient progress bar (`#7C4DFF -> #FF4B4B`), parameter context pills, mid-run parameter restart amber badge, long-running warning state (`bars > 1500`, `n_surrogates > 60`, or `elapsed > 15s`), and step-level failure recovery controls (`Retry Run`, `Reset to Default Seed`, `Cancel Run`).
  - Cold-Load Structural Shimmer Skeletons (`render_shimmer_skeletons_html`) with 4 responsive KPI skeleton cards (`height: 96px`) and a 360px primary chart skeleton (`"Awaiting surrogate convergence..."`), Warm-State chart dimming (`45%` opacity, `filter: blur(1px)`), post-load collapsible summary bar with expandable execution log, stage-throttled `aria-live="polite"` announcements, and `@media (prefers-reduced-motion: reduce)` support.
  - `tests/test_loading_state_ui.py`: Unit and integration test suite covering `SPEC-QUANT-LOAD-01` progress math, telemetry sequence, shimmer skeletons, warm reload, error/cancel states, and accessibility.
- **Claude Code Review & CI Workflows (`.github/workflows/`)**:
  - `ci.yml`: Automated `CI` workflow running `ruff check src tests`, `pytest -v`, and `quantlab dashboard --check` on Python 3.11.
  - `claude.yml`: Interactive `@claude` GitHub App workflow powered by Claude Opus 5.5 High (`anthropics/claude-code-action@v1`).
  - `pr-review.yml` & `prompts/pr-review.md`: Automated Pull Request review, in-place auto-fix (`[skip pr-review]`), zero-token `merge_only` fast path, self-healing label governance, exact-SHA `CI` gating, squash-merge, and parent-story closure tailored to `quantlab`.
  - `tests/test_claude_workflows.py`: Static contract tests validating the Claude Code Review and CI workflows.
- **Point-in-Time Market Data & Fractional Stationarity (`quantlab.data`)**:
  - `loader.py`: `OHLCVDataset` with strict PIT invariant verification, local `.cache/parquet/` caching, `yfinance` and `ccxt` fetchers, and deterministic `synthetic` stochastic generators (`SYNTH:COUPLED_OU` coupled Ornstein-Uhlenbeck + Heston regime-switching process and `SYNTH:WHITE_NOISE` null control).
  - `stationarity.py`: `@numba.njit` Fixed-Width Window Fractional Differentiation (`frac_diff_ffd`), Augmented Dickey-Fuller (`adf_test`) with MacKinnon response-surface $p$-values, and automated minimum stationary order $d^*$ search (`find_min_ffd_d`).
- **Dual Neuro-Symbolic Indicator Registry (`quantlab.indicators`)**:
  - `registry.py`: Custom `sympy.Function` time-series AST operators (`Lag`, `Change`, `SMA`, `EMA`, `RMA`, `WMA`, `Stdev`, `Highest`, `Lowest`, `TrueRange`, `Nz`, `RollingEntropy`), `SymbolicRecurrence`, `IndicatorSpec`, and `IndicatorRegistry`.
  - `baselines.py`: Vectorized `@numba.njit` kernels and symbolic ASTs for `RSI`, `EMA`, `ATR`, `MACD`, and `KAMA`.
  - `custom_examples.py`: Physics-inspired `@numba.njit` kernels and symbolic/recurrence ASTs for `KalmanFilter` (1D kinematic velocity filter), `PhaseSpaceEnergy` (Takens 3D delay-embedding Hamiltonian energy flux), and `EntropyFlow` (rolling Shannon information coherence order flow).
- **Information-Theoretic, Statistical & DSP Proof Suite (`quantlab.proofs`)**:
  - `entropy.py`: Miller-Madow Shannon entropy, Bandt-Pompe permutation entropy, vectorized `cKDTree` Kraskov-Stögbauer-Grassberger (KSG) k-NN Mutual Information, Symbolic & k-NN Transfer Entropy, and Monte Carlo IAAFT / Block-Shuffle surrogate significance gates.
  - `stats_gate.py`: Multi-horizon Spearman Rank IC decay, 1-Wasserstein bull/bear regime separation distance, regularized Variance Inflation Factor (VIF) orthogonality gate, and unified `run_proof_suite` / `evaluate_multiple_indicators`.
  - `dsp.py`: `@numba.njit` causal EMA detrending, Analytic signal Hilbert Transform phase-lag diagnostics, Welch cross-spectral Bode magnitude/phase response, 3rd-derivative Jerk smoothness energy, and 2D `(Phase Lag, Jerk)` Pareto frontier detection.
- **SymPy-to-Pine Script v6 Transpiler (`quantlab.transpiler.pine_v6`)**:
  - Recursive AST compiler (`PineV6Transpiler`, `transpile_to_pine_v6`) generating `//@version=6` TradingView scripts and self-contained Markdown Research Cards (`generate_research_card`).
- **CLI & 4-Quadrant Diagnostic Dashboard (`quantlab.cli`, `quantlab.dashboard.app`)**:
  - `typer` + `rich` CLI supporting `fetch`, `indicators`, `evaluate`, `prove`, `transpile`, and `dashboard`.
  - Dark-mode 4-Quadrant Streamlit + Plotly + TradingView Lightweight Charts HTML5 web application.
