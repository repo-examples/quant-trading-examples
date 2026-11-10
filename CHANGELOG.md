# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Contextual Chart Help & Collision-Free Header Bars (`SPEC-UI-HELP-03` — `quantlab.dashboard.chart_help`, `quantlab.dashboard.app`, `.streamlit/config.toml`)**:
  - `ChartHelpEntry`, `CHART_HELP_REGISTRY`, `get_chart_help`, `render_chart_help_popover_html`, and `render_chart_header` providing standardized header bars (`Title` left, anchored `st.popover("?")` trigger right) with 3-part educational microcopy (`1. What It Is`, `2. Axes & Visuals`, `3. How to Interpret`) across all 8 diagnostic charts (`TV-01`, `Q1A`, `Q1B`, `Q2A`, `Q2B`, `Q3A`, `Q3B`, `Q3C`) plus the `Q4` Neuro-Symbolic Studio (`Q4A`) and graceful missing-key fallback.
  - Headerless collision-free Plotly layouts (`title=None`, horizontal top-left legends, `margin.t >= 56`), color-blind safe border/hatch differentiation on `Q3B` Bull vs. Bear regime histograms, and `.streamlit/config.toml` dark-theme lock (`#0E1117`).
- **Multi-Timeframe Selector & History Sample Guards (`SPEC-CTRL-TF-02` — `quantlab.data.loader`, `quantlab.dashboard.app`, `quantlab.dashboard.loading_state`, `quantlab.cli`)**:
  - `TimeframeSpec`, `TIMEFRAME_SPECS`, `normalize_timeframe` (preserving `1m` 1-minute vs. `1M`/`1mo` 1-month disambiguation), and expanded timeframe controls (`15m`, `1h`, `4h`, `1D`, `1W`, `1M`, `3M`, default `1D`) paired with a synced Q1 quick-switcher bar (`1D | 1W | 1M | 3M`) and URL query-parameter sync (`provider`, `symbol`, `tf`).
  - Maximum-history fetching (`period="max"`) on `1D`/`1W`/`1M`/`3M`, zero-lookahead causal OHLCV resampling (`resample_ohlcv_causal`) for unsupported provider intervals (`3M` on `ccxt`, `4h` on `yfinance`), amber clamped-history summary pills (`35 <= available < requested`), and `InsufficientHistoryError` `< 35`-bar proof sample guard (`validate_minimum_proof_bars`).
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

### Fixed
- **TradingView Lightweight Charts HTML5 Canvas Rendering (`SPEC-CHART-TV-01` — `quantlab.data.loader`, `quantlab.dashboard.app`)**:
  - Resolved blank HTML5 canvas under `yfinance`/`ccxt` by flattening `pd.MultiIndex` columns, fixing `datetime64[s, UTC]` timestamp division collapse, serializing `1D`/`1W`/`1M`/`3M` bars as unique ascending `YYYY-MM-DD` strings and intraday bars as UTC Unix epoch seconds, and mapping non-finite (`NaN`/`Inf`) indicator warm-up bars to Lightweight Charts whitespace objects (`{"time": bar_time}`).
  - Added live top-left crosshair OHLCV + indicator hover legend (`#tv-legend`), `autoSize: true` + `ResizeObserver` + `fitContent()`, mobile touch scroll protection (`vertTouchDrag`), `role="img"` + dynamic `aria-label` summary, and inline diagnostic empty/error state cards.
