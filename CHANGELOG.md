# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
