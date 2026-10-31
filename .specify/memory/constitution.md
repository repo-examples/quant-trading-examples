# QuantLab Constitution

## Core Principles

### I. Causal Point-in-Time (PIT) Alignment (NON-NEGOTIABLE)
Every data ingestion pipeline, fractional differentiation operator, technical indicator kernel, rolling information-theoretic estimator, and statistical proof MUST enforce strict causal Point-in-Time (PIT) alignment ($t \le T$) with zero lookahead bias. Fixed-width window Fractional Differentiation (FracDiff) MUST use causal backwards-looking weights truncated at a deterministic threshold $\tau$, and forward returns used in Rank IC or Transfer Entropy target evaluation MUST be strictly aligned to future horizon $[T+1, T+h]$ without leaking into feature construction at $T$.

### II. Dual Neuro-Symbolic Indicator Representation
Every indicator registered in `quantlab.indicators.registry` MUST provide a dual representation:
1. A vectorized numerical kernel (`numpy` / `@numba.njit`) accepting 1D `float64` arrays for high-throughput evaluation and Monte Carlo surrogate testing.
2. A symbolic `sympy.Expr` Abstract Syntax Tree (AST) constructed from canonical time-series primitives (`Lag`, `EMA`, `SMA`, `RMA`, `WMA`, `Stdev`, `Highest`, `Lowest`, `Abs`, `Log`, `Sqrt`, `Piecewise`, `Recurrence`) that transpiles deterministically into valid TradingView Pine Script v6 (`//@version=6`) code and a self-contained Markdown Research Card.

### III. Information-Theoretic & Statistical Proof Gating
Quantitative indicator research MUST replace visual heuristics with falsifiable mathematical proofs. An indicator evaluation pipeline MUST compute and gate against:
- **Stationarity Gate**: Augmented Dickey-Fuller (ADF) test $p\text{-value} < 0.05$ (after minimum-order FracDiff $d^* \in [0, 1]$ preserving maximum memory correlation with raw log-prices).
- **Information Flow Gate**: Shannon Entropy, Mutual Information $I(X_t; R_{t+h})$, and Causal Transfer Entropy $TE(X \to R)$ (symbolic permutation and Kraskov-Stögbauer-Grassberger k-NN / plug-in binned estimators) tested against phase-randomized IAAFT or block-shuffled Monte Carlo surrogates ($p < 0.05$).
- **Statistical & Orthogonality Gate**: Out-of-sample / rolling Spearman Rank IC ($|\text{IC}| > 0.02$), Wasserstein-1 ($W_1$) bull/bear regime distribution separation, and Variance Inflation Factor ($\text{VIF} < 5.0$) against standard TA baselines (`RSI`, `EMA`, `ATR`, `MACD`, `KAMA`).
- **DSP Phase-Smoothness Gate**: Analytic signal Hilbert Transform instantaneous phase lag and Bode frequency response vs. third-derivative Jerk ($J = \frac{1}{N}\sum |\Delta^3 y_t|^2$) Pareto frontier comparison.

### IV. Vectorization, JIT Acceleration & Strict Static Typing
All time-series, entropy, surrogate, and digital signal processing algorithms MUST be implemented using vectorized `numpy`/`scipy` operations or `@numba.njit(cache=True)` compiled kernels. Uncompiled Python `for` loops over bar indices are prohibited in hot paths unless wrapped in Numba JIT or serving as a transparent fallback when Numba is unavailable. All modules MUST target Python 3.11+ with strict type annotations (`mypy`/`ruff` clean) and immutable `dataclass(frozen=True)` result structures.

### V. CLI-First Architecture & Deterministic Reproducibility
All core workflows (`fetch`, `indicators`, `evaluate`, `transpile`, `dashboard`) MUST be accessible from the `quantlab` CLI (`typer` + `rich`) as well as the 4-Quadrant Interactive Streamlit Diagnostic Dashboard (`quantlab dashboard`). Market data loaders MUST cache OHLCV series locally in Parquet format and include a deterministic `synthetic` stochastic process generator (coupled Ornstein-Uhlenbeck, Heston stochastic volatility, and regime-switching jump-diffusion with known ground-truth directional coupling) so all unit and integration tests execute deterministically offline.

## Technology Stack & Architectural Constraints

- **Language & Packaging**: Python 3.11+, `pyproject.toml` with `src/quantlab/` layout managed via `uv` / `hatchling`.
- **CLI & Terminal UI**: `typer` and `rich` for structured tables, progress bars, and color-coded PASS/FAIL proof scorecards.
- **Interactive Dashboard**: `streamlit`, `plotly`, and `lightweight-charts` (`lightweight-charts-python`) in a dark-mode 4-Quadrant layout launched via `quantlab dashboard`.
- **Mathematical & Symbolic Core**: `sympy` (AST representation and manipulation), `numpy`, `scipy` (signal processing, Hilbert transform, Bode response, ADF/statistical tests, Wasserstein metric), `numba` (JIT kernels for rolling entropy, transfer entropy, KAMA, Kalman, and surrogates).
- **Market Data & Storage**: `yfinance`, `ccxt`, and `pandas`/`pyarrow` (or `polars`) for local Point-in-Time Parquet caching.

## Quality Gates & Development Workflow

- **Zero Lookahead Verification**: Unit tests MUST verify causal invariance by confirming that modifying future bars $t > T$ produces zero change in indicator values, FracDiff series, and rolling causal estimators at index $T$.
- **Ground-Truth Synthetic Verification**: Transfer Entropy and Mutual Information estimators MUST be verified on coupled vs. uncoupled synthetic stochastic processes with fixed random seeds.
- **Transpiler AST Verification**: Every registered baseline and physics indicator MUST transpile to syntactically valid `//@version=6` Pine Script containing required declarations (`indicator(...)`, typed inputs, series expressions, and `plot(...)` calls) alongside a Markdown Research Card.
- **Test & Lint Gate**: All `pytest` unit/integration tests and `ruff` checks MUST pass 100% prior to Pull Request creation.

## Governance

This Constitution supersedes ad-hoc implementation shortcuts. Any modification to core mathematical thresholds, indicator AST contracts, or causal PIT invariants requires a documented constitutional amendment and corresponding test updates. Version numbers follow Semantic Versioning (`MAJOR.MINOR.PATCH`).

**Version**: 1.0.0 | **Ratified**: 2026-10-29 | **Last Amended**: 2026-10-29
