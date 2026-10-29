# Feature Specification: QuantLab Information-Theoretic Indicator Research CLI, Transpiler & Diagnostic Dashboard

**Feature Branch**: `feat/001-quantlab-research-suite`

**Created**: 2026-10-29

**Status**: Approved

**Input**: User description: "Build a production-grade, modular Python application called `quantlab`: an Information-Theoretic Technical Indicator Research CLI & Interactive Dashboard with a SymPy-to-Pine Script v6 Transpiler."

## Clarifications

### Session 2026-10-29

- Q: How should `quantlab` structure its CLI subcommands and `proofs/` pass/fail criteria? → A: Full CLI suite (`fetch`, `indicators`, `evaluate`/`prove`, `transpile`, `dashboard`) with automated Pass/Fail statistical gates (ADF p < 0.05, Surrogate TE p < 0.05, |Rank IC| > 0.02, VIF < 5.0).
- Q: How should the 4-Quadrant Interactive Quant Diagnostic Dashboard (`src/quantlab/dashboard/app.py`) be organized? → A: Q1: Price/OHLCV + Indicator Canvas (TradingView Lightweight Charts & Phase-Space 3D attractor), Q2: Information-Theoretic Proofs (Rolling Entropy, MI, Transfer Entropy vs. IAAFT/Block-Shuffle Surrogates), Q3: Statistical & DSP Frontier (Rank IC Decay, Regime Wasserstein Distance, VIF Orthogonality, Bode Phase-Lag vs. Jerk Pareto Frontier), Q4: Live SymPy AST Editor & Pine Script v6 Transpiler + Research Card Preview.
- Q: How should `registry.py` and `pine_v6.py` bridge SymPy symbolic ASTs with stateful/recursive indicators and where should the package root live? → A: Dual-Representation Registry with vectorized Numba/NumPy kernel + Symbolic SymPy AST (using custom `sympy.Function` nodes like `Lag`, `EMA`, `Stdev`, `Recurrence`) compiling to `//@version=6` Pine Script + Markdown Research Card; package root at repository root (`pyproject.toml` + `src/quantlab/`).
- Q: How should `data/loader.py` handle market data providers, Point-in-Time (PIT) Parquet caching, and offline/ground-truth causal verification? → A: Support `yfinance` and `ccxt` with local `.cache/parquet/` PIT-aligned storage, plus a built-in `synthetic` provider (coupled Ornstein-Uhlenbeck / Heston / regime-switching processes with known ground-truth causal information flow).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Point-in-Time Market Data & Fractional Stationarity Pipeline (Priority: P1)

Quantitative researchers need to ingest historical OHLCV market data (from equity/crypto exchanges or deterministic synthetic stochastic benchmarks), store it locally with strict Point-in-Time (PIT) causal ordering, and transform non-stationary price series into memory-preserving stationary series via Fixed-Width Window Fractional Differentiation (FracDiff) verified by Augmented Dickey-Fuller (ADF) testing.

**Why this priority**: All downstream indicator computation, information-theoretic proofs, and statistical gates depend on clean, lookahead-free, stationary input series.

**Independent Test**: Can be fully tested by running `quantlab fetch` on a synthetic or live ticker and verifying that the cached dataset and optimal minimum fractional differentiation order $d^*$ satisfy the ADF stationarity threshold ($p < 0.05$) while preserving maximum memory correlation with log-prices and exhibiting zero lookahead change when future bars are perturbed.

**Acceptance Scenarios**:

1. **Given** a target symbol, timeframe, and date window (or synthetic stochastic process regime), **When** the researcher invokes the data loader or `quantlab fetch`, **Then** the system retrieves strictly monotonic UTC-indexed OHLCV data, caches it locally, and reports dataset completeness and summary statistics.
2. **Given** a non-stationary log-price series, **When** the researcher runs Fractional Differentiation search across $d \in [0.0, 1.0]$, **Then** the system computes causal fixed-window weights truncated at threshold $\tau$, identifies the minimum $d^*$ achieving ADF $p < 0.05$, and returns the stationary series along with the ADF statistic, $p$-value, and correlation with original log-price.
3. **Given** a time series truncated at time $T$ versus the full time series $[0, T+K]$, **When** FracDiff is applied to both series, **Then** the output values on $[0, T]$ are identical within floating-point precision ($< 10^{-12}$), proving zero lookahead bias.

---

### User Story 2 - Dual Neuro-Symbolic Indicator Registry & Evaluation Gate (Priority: P1)

Quantitative researchers need a unified registry of standard technical baselines (`RSI`, `EMA`, `ATR`, `MACD`, `KAMA`) and physics-inspired indicators (`Kalman Velocity/Filter`, `Phase-Space Reconstruction / Takens Energy`, `Rolling Shannon/Permutation Entropy Flow`) where each indicator exposes both a fast numerical evaluation kernel and a canonical symbolic expression tree, evaluated through an automated Pass/Fail proof suite (`entropy`, `stats_gate`, `dsp`).

**Why this priority**: This is the core scientific engine of `quantlab`, separating true predictive information flow and signal efficiency from spurious technical correlations.

**Independent Test**: Can be fully tested by running `quantlab indicators` and `quantlab evaluate --indicator <name>` on a synthetic coupled stochastic dataset and verifying that every registered indicator produces finite causal series and a complete proof scorecard (ADF, Shannon Entropy, Mutual Information, Symbolic & k-NN Transfer Entropy with IAAFT/block-shuffle surrogate $p$-values, Spearman Rank IC, Wasserstein regime distance, VIF orthogonality, and Hilbert Phase-Lag vs. Jerk frontier).

**Acceptance Scenarios**:

1. **Given** the indicator registry, **When** the researcher queries registered indicators via CLI or API, **Then** all 5 baseline indicators (`RSI`, `EMA`, `ATR`, `MACD`, `KAMA`) and 3 physics-inspired indicators (`KalmanFilter`, `PhaseSpaceEnergy`, `EntropyFlow`) are listed with their parameter schemas, numerical kernels, and symbolic AST expressions.
2. **Given** a coupled driver-target synthetic process where indicator $X_t$ causally drives future return $R_{t+1}$, **When** the researcher executes the Information-Theoretic Proof (`entropy`), **Then** Causal Transfer Entropy $TE(X \to R)$ is strictly positive and statistically significant ($p < 0.05$) against Monte Carlo IAAFT / block-shuffled surrogates, while reverse or uncoupled noise fails the surrogate gate.
3. **Given** an indicator series and OHLCV history, **When** the researcher executes `quantlab evaluate`, **Then** the CLI renders a structured scorecard displaying PASS/FAIL status for Stationarity (ADF $p < 0.05$), Information Flow (Surrogate TE $p < 0.05$), Predictive Power ($|\text{Spearman Rank IC}| > 0.02$), Regime Separation (Wasserstein $W_1$ distance), Multicollinearity Orthogonality ($\text{VIF} < 5.0$ against baselines), and DSP efficiency (Hilbert instantaneous phase lag in radians/bars and third-derivative Jerk energy).

---

### User Story 3 - SymPy-to-Pine Script v6 Transpiler & Markdown Research Card (Priority: P2)

Quantitative researchers need to automatically compile any registered or custom symbolic indicator expression tree into production-ready TradingView Pine Script v6 (`//@version=6`) source code accompanied by an auditable Markdown Research Card embedding the indicator's mathematical formulation, proof scorecard, and deployment script.

**Why this priority**: Bridges theoretical Python research and live charting/execution on TradingView without manual re-coding errors or translation drift.

**Independent Test**: Can be tested independently via `quantlab transpile --indicator <name>` (or custom symbolic formula) and verifying that the generated `.pine` file contains valid `//@version=6` syntax (`indicator()`, `input.*`, `ta.*` or `var float` recursive state updates, `plot()`) and that the generated `.md` Research Card contains the LaTeX formula, proof gate table, and fenced Pine Script v6 code block.

**Acceptance Scenarios**:

1. **Given** any registered baseline or physics-inspired indicator (or custom symbolic expression using `Lag`, `EMA`, `SMA`, `RMA`, `Stdev`, `Highest`, `Lowest`, `Recurrence`), **When** the researcher invokes the Pine v6 transpiler, **Then** the system walks the symbolic AST and emits valid `//@version=6` code with typed `input.int`/`input.float` declarations, causal series bindings, and `plot()` statements.
2. **Given** an indicator evaluation result and transpiled script, **When** the researcher exports a Research Card via `quantlab transpile --card`, **Then** the system writes a self-contained Markdown report containing the symbolic LaTeX equation, Pass/Fail statistical proof metrics, DSP phase-lag/jerk profile, and the complete Pine Script v6 code block.

---

### User Story 4 - 4-Quadrant Interactive Quant Diagnostic Dashboard (Priority: P2)

Quantitative researchers need an interactive, dark-mode local web application launched via `quantlab dashboard` that visualizes all four diagnostic dimensions simultaneously: Q1 (OHLCV + Indicator Canvas & 3D Phase-Space Attractor), Q2 (Information-Theoretic Proofs & Surrogate Distributions), Q3 (Statistical IC Decay, Regime Wasserstein Density, VIF Heatmap & Bode Phase-Lag vs. Jerk Pareto Frontier), and Q4 (Live Symbolic AST Editor, Pine Script v6 Transpiler & Research Card Preview).

**Why this priority**: Enables rapid interactive hypothesis testing, visual confirmation of phase-space trajectories and Bode frontiers, and one-click Pine Script v6 export.

**Independent Test**: Can be tested by importing and executing the dashboard state builder / rendering pipeline across all 4 quadrants and verifying that every chart model, table, and live symbolic-to-Pine v6 transpilation updates without runtime exceptions.

**Acceptance Scenarios**:

1. **Given** the installed CLI, **When** the user runs `quantlab dashboard` (or `--check` in headless verification mode), **Then** the multi-tab / 4-Quadrant dark-mode web application initializes with selected market/synthetic data and active indicators.
2. **Given** Quadrant 1 (Price & Phase-Space) and Quadrant 2 (Information Proofs), **When** an indicator is selected, **Then** Q1 renders the OHLCV + indicator canvas alongside a 3D Takens delay-embedding attractor $(x_t, x_{t-\tau}, x_{t-2\tau})$, and Q2 renders rolling Shannon entropy, Mutual Information across lags, and the Transfer Entropy surrogate null distribution with observed $TE$ vertical threshold.
3. **Given** Quadrant 3 (Statistical & DSP Frontier) and Quadrant 4 (Transpiler Studio), **When** the researcher inspects or edits a symbolic indicator expression, **Then** Q3 displays multi-horizon Spearman Rank IC decay, bull/bear Wasserstein regime distributions, baseline VIF bars, and the Bode Phase-Lag vs. Jerk Pareto scatter plot, while Q4 dynamically transpiles the symbolic AST into Pine Script v6 and renders the downloadable Markdown Research Card.

---

### Edge Cases

- **Constant or Zero-Variance Series**: When an input series or indicator window is constant (zero standard deviation or zero entropy variation), estimators (`RSI`, `KAMA`, `Spearman IC`, `VIF`, `k-NN TE`) MUST avoid division-by-zero (`NaN`/`Inf` propagation) by returning bounded finite fallback values ($0.0$ or $50.0$ for neutral RSI) after warm-up bars.
- **Short Time Series / Insufficient Warm-up**: When the input dataset has fewer bars than required by the fractional differentiation window or rolling entropy window ($N < W_{\min}$), the system MUST raise a descriptive validation error specifying minimum required bars rather than crashing with an index error.
- **Offline / Rate-Limited Market Data Providers**: When `yfinance` or `ccxt` network requests fail or no internet connection is available, `loader.py` MUST gracefully serve cached local datasets if present or allow deterministic fallback to the `synthetic` provider with clear user notification.
- **Non-Transpilable Arbitrary Python Callables**: If a user attempts to transpile an indicator lacking a symbolic AST representation (or containing an unsupported symbolic operator), `pine_v6.py` MUST raise a structured `TranspilationError` naming the unsupported AST node.
- **Collinear Indicator Design Matrix**: When computing VIF on perfectly collinear indicators ($R^2 \to 1.0$), `stats_gate.py` MUST cap VIF at a finite ceiling (e.g., $1000.0$ or `np.inf` handled cleanly) using regularized pseudo-inverse without throwing `LinAlgError`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a Point-in-Time (PIT) market data loader (`quantlab.data.loader`) supporting `yfinance`, `ccxt`, and a deterministic `synthetic` stochastic generator (coupled Ornstein-Uhlenbeck, Heston volatility, and regime-switching jump-diffusion), persisting standardized UTC OHLCV datasets (`open`, `high`, `low`, `close`, `volume`) in local Parquet cache.
- **FR-002**: System MUST implement Fixed-Width Window Fractional Differentiation (`quantlab.data.stationarity`) with causal weight computation $w_k = -w_{k-1} \frac{d - k + 1}{k}$ truncated at threshold $\tau$, an automated grid/binary search for minimum stationary order $d^* \in [0, 1]$ passing the Augmented Dickey-Fuller (ADF) test ($p < 0.05$), and memory correlation retention measurement.
- **FR-003**: System MUST provide a dual Neuro-Symbolic Indicator Registry (`quantlab.indicators.registry`) storing for each indicator: metadata, parameter schema, vectorized numerical evaluation kernel, and symbolic AST builder.
- **FR-004**: System MUST implement 5 standard technical baseline indicators (`quantlab.indicators.baselines`): Relative Strength Index (`RSI`), Exponential Moving Average (`EMA`), Average True Range (`ATR`), Moving Average Convergence Divergence (`MACD`), and Kaufman Adaptive Moving Average (`KAMA`), each with both numerical kernels and symbolic ASTs.
- **FR-005**: System MUST implement 3 physics-inspired custom indicators (`quantlab.indicators.custom_examples`): 1D Kinematical Kalman Filter State/Velocity Estimator (`KalmanFilter`), Takens Phase-Space Reconstruction Hamiltonian/Kinetic Energy (`PhaseSpaceEnergy`), and Rolling Symbolic/Shannon Information Flow (`EntropyFlow`), each with numerical kernels and symbolic/recurrence AST representations.
- **FR-006**: System MUST implement Information-Theoretic proofs (`quantlab.proofs.entropy`) including plug-in and symbolic permutation Shannon Entropy, Mutual Information $I(X_t; R_{t+h})$, Symbolic Transfer Entropy and k-NN (Kraskov-inspired / KDTree) Transfer Entropy $TE(X \to R)$, and Monte Carlo significance testing via Iterative Amplitude Adjusted Fourier Transform (IAAFT) and block-shuffle surrogates.
- **FR-007**: System MUST implement Statistical and Orthogonality gates (`quantlab.proofs.stats_gate`) computing multi-horizon Spearman Rank Information Coefficient (Rank IC) with $t$-statistics, 1-Wasserstein ($W_1$) Earth Mover's Distance between bull and bear volatility/return regimes, and Variance Inflation Factor (VIF) & pairwise correlation matrix against the baseline indicator set.
- **FR-008**: System MUST implement Digital Signal Processing (DSP) diagnostics (`quantlab.proofs.dsp`) computing the causal/windowed Hilbert Transform analytic signal (instantaneous amplitude, phase, frequency, and group/phase lag relative to price), frequency response Bode magnitude/phase curves, and third-order finite-difference smoothness Jerk ($J = \frac{1}{N}\sum |\Delta^3 x_t|^2$) to construct the Phase-Lag vs. Jerk Pareto frontier.
- **FR-009**: System MUST implement a Symbolic-to-Pine Script v6 Transpiler (`quantlab.transpiler.pine_v6`) that traverses a symbolic AST (supporting algebraic operators, `Piecewise`, `Lag`, `SMA`, `EMA`, `RMA`, `WMA`, `Stdev`, `Highest`, `Lowest`, and stateful `Recurrence`) and emits valid `//@version=6` TradingView Pine Script alongside a Markdown Research Card generator.
- **FR-010**: System MUST expose a command-line interface (`quantlab.cli`) with subcommands `fetch`, `indicators`, `evaluate` (aliased as `prove`), `transpile`, and `dashboard`, rendering formatted terminal tables, progress indicators, and PASS/FAIL gate summaries.
- **FR-011**: System MUST provide a 4-Quadrant Interactive Diagnostic Dashboard (`quantlab.dashboard.app`) presenting Q1 (OHLCV Canvas & 3D Phase-Space Attractor), Q2 (Entropy, MI, Transfer Entropy & Surrogate Null Histogram), Q3 (Rank IC Decay, Regime Wasserstein Density, VIF Orthogonality & Bode Phase-Lag vs. Jerk Pareto Frontier), and Q4 (Interactive Symbolic AST Editor, Live Pine Script v6 Transpiler & Markdown Research Card Preview/Download).
- **FR-012**: System MUST enforce strict causal Point-in-Time alignment across all modules such that features at index $t$ depend exclusively on observations at $\{0, \dots, t\}$ and forward target returns $R_{t+h}$ are strictly aligned to $[t+1, t+h]$ without lookahead leakage.

### Key Entities

- **OHLCVDataset**: Standardized, monotonically sorted UTC time-series table (`timestamp`, `open`, `high`, `low`, `close`, `volume`) with provenance metadata (`symbol`, `provider`, `timeframe`, `cache_path`).
- **StationarityResult**: Output of Fractional Differentiation analysis containing optimal order $d^*$, causal weight vector, differentiated series, ADF test statistic, $p$-value, critical values, and log-price memory correlation.
- **IndicatorSpec**: Dual neuro-symbolic descriptor registered in `IndicatorRegistry` holding indicator `name`, `category` (`baseline` | `physics`), default parameters, numerical callable, and symbolic AST factory.
- **ProofSuiteResult**: Immutable aggregate evaluation record combining `StationarityResult`, `EntropyProofResult` (Shannon, MI, TE, surrogate distribution, $p$-value, gate pass), `StatsGateResult` (Rank IC profile, Wasserstein regime distance, VIF vector, gate pass), `DSPResult` (phase lag, jerk, Pareto efficiency score), and overall `passed` status.
- **TranspilationArtifact**: Output of `pine_v6` containing the symbolic expression, LaTeX representation, complete `//@version=6` Pine Script code, and formatted Markdown Research Card.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero lookahead leakage: 100% of registered indicators and fractional differentiation routines produce identical values ($\text{max abs diff} < 10^{-12}$) on $[0, T]$ regardless of whether future bars $[T+1, T+K]$ are present or mutated.
- **SC-002**: Causal Transfer Entropy discrimination: On synthetic coupled driver-response series ($N = 1000$ bars, fixed seed), the Transfer Entropy gate achieves $p < 0.05$ against surrogates for true causal drivers while rejecting uncoupled white-noise series ($p > 0.10$).
- **SC-003**: Complete dual-representation coverage: 100% of registered indicators (5 baselines + 3 physics-inspired) evaluate numerically in under 500 ms for $2,500$ bars (after JIT warm-up) and transpile into valid `//@version=6` Pine Script and Markdown Research Cards with zero unresolved AST nodes.
- **SC-004**: CLI & Gate Usability: Researchers can run end-to-end data ingestion, stationarity transformation, multi-proof evaluation, and Pine Script v6 transpilation from a single CLI command in under 5 seconds on cached/synthetic datasets ($N = 1000$).
- **SC-005**: 4-Quadrant Dashboard Completeness: All 4 diagnostic quadrants construct their chart figures and transpiler artifacts cleanly without runtime errors across both synthetic and cached market datasets.

## Assumptions

- Users execute `quantlab` in a Python 3.11+ environment managed via `uv` or standard `pip`/`venv`.
- For automated tests and offline environments where Yahoo Finance or crypto exchanges may be unreachable, the built-in `synthetic` provider serves as the deterministic reference data source.
- Default statistical gate thresholds (`ADF p < 0.05`, `Surrogate TE p < 0.05`, `|Rank IC| > 0.02`, `VIF < 5.0`) are configurable via CLI flags and function parameters.
