# Implementation Plan: QuantLab Information-Theoretic Indicator Research CLI, Transpiler & Diagnostic Dashboard

**Branch**: `feat/001-quantlab-research-suite` | **Date**: 2026-10-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-quantlab-research-suite/spec.md`

## Summary

Build **`quantlab`**, a modular Python 3.11+ quantitative research package providing:
1. **Point-in-Time Market Data & Fractional Stationarity (`quantlab.data`)**: `yfinance`, `ccxt`, and deterministic `synthetic` stochastic process loaders with local Parquet caching (`loader.py`) plus Fixed-Width Window Fractional Differentiation (FracDiff) and ADF stationarity search (`stationarity.py`).
2. **Dual Neuro-Symbolic Indicator Registry (`quantlab.indicators`)**: Unified registry (`registry.py`) combining `@numba.njit`/vectorized kernels and custom `sympy.Expr` symbolic ASTs across 5 standard baselines (`RSI`, `EMA`, `ATR`, `MACD`, `KAMA` in `baselines.py`) and 3 physics-inspired indicators (`KalmanFilter`, `PhaseSpaceEnergy`, `EntropyFlow` in `custom_examples.py`).
3. **Mathematical Proof Suite (`quantlab.proofs`)**: Causal Shannon/Permutation Entropy, Mutual Information, Symbolic & k-NN Transfer Entropy with IAAFT and block-shuffle surrogates (`entropy.py`), multi-horizon Spearman Rank IC, Wasserstein regime distance, and VIF orthogonality (`stats_gate.py`), plus Hilbert Transform instantaneous phase lag, Bode frequency response, and 3rd-derivative Jerk Pareto frontier (`dsp.py`).
4. **SymPy-to-Pine Script v6 Transpiler (`quantlab.transpiler.pine_v6`)**: AST compiler generating `//@version=6` TradingView Pine Script and Markdown Research Cards.
5. **CLI & 4-Quadrant Diagnostic Dashboard (`quantlab.cli`, `quantlab.dashboard.app`)**: `typer` + `rich` CLI (`fetch`, `indicators`, `evaluate`/`prove`, `transpile`, `dashboard`) and a 4-Quadrant dark-mode Streamlit + Plotly + TradingView Lightweight Charts web app.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: `typer`, `rich`, `sympy`, `numpy`, `scipy`, `numba`, `pandas`, `pyarrow`, `yfinance`, `ccxt`, `streamlit`, `plotly`, `lightweight-charts`

**Storage**: Local Point-in-Time Parquet cache (`.cache/parquet/`) via `pandas` + `pyarrow`

**Testing**: `pytest`, `ruff`

**Target Platform**: Cross-platform CLI & local web dashboard (Windows / Linux / macOS)

**Project Type**: Modular Python library, CLI application, compiler/transpiler, and interactive web dashboard

**Performance Goals**: Numerical evaluation of all 8 indicators on $2,500$ bars in $< 500\text{ ms}$ (post-JIT warm-up); end-to-end proof gate evaluation ($N=1000$, $M=50$ surrogates) in $< 5\text{ s}$

**Constraints**: Zero lookahead bias ($t \le T$ strict causal invariance within $< 10^{-12}$); deterministic offline reproducibility via seeded synthetic stochastic processes; 100% static type annotations

**Scale/Scope**: 11 core production modules under `src/quantlab/` + comprehensive unit and integration test suites under `tests/`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Causal Point-in-Time (PIT) Alignment**: FracDiff uses fixed-width backward weights truncated at $\tau$; all indicators, rolling entropy estimators, and forward return targets enforce strict causal indexing.
- [x] **II. Dual Neuro-Symbolic Indicator Representation**: `IndicatorSpec` mandates both `compute_fn` (`numpy`/`numba`) and `symbolic_fn` (`sympy.Expr`) for every registered indicator.
- [x] **III. Information-Theoretic & Statistical Proof Gating**: Automated pass/fail gates implemented for ADF ($p < 0.05$), Surrogate Transfer Entropy ($p < 0.05$), Spearman Rank IC ($|\text{IC}| > 0.02$), VIF ($< 5.0$), Wasserstein distance, and DSP Phase-Lag vs. Jerk Pareto frontier.
- [x] **IV. Vectorization, JIT Acceleration & Strict Static Typing**: Hot loops (rolling entropy, symbolic permutation patterns, KAMA, Kalman, IAAFT surrogates, FFD convolution) compiled with `@numba.njit(cache=True)` and fully type-annotated.
- [x] **V. CLI-First Architecture & Deterministic Reproducibility**: `quantlab` CLI exposes `fetch`, `indicators`, `evaluate`/`prove`, `transpile`, and `dashboard` backed by Parquet caching and seeded synthetic stochastic benchmarks.

## Project Structure

### Documentation (this feature)

```text
specs/001-quantlab-research-suite/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── cli-and-transpiler-contract.md
├── checklists/
│   ├── requirements.md
│   └── quant-verification.md
└── tasks.md             # Phase 2 output (/speckit-tasks command)
```

### Source Code (repository root)

```text
pyproject.toml
README.md
CHANGELOG.md
src/
└── quantlab/
    ├── __init__.py
    ├── cli.py                  # Typer CLI entrypoint (fetch, indicators, evaluate/prove, transpile, dashboard)
    ├── data/
    │   ├── __init__.py
    │   ├── loader.py           # OHLCV fetcher (yfinance, ccxt, synthetic) + Parquet cache
    │   └── stationarity.py     # Fractional Differentiation (FracDiff) + ADF test
    ├── indicators/
    │   ├── __init__.py
    │   ├── registry.py         # Symbolic (SymPy) + Numba indicator registry & custom AST primitives
    │   ├── baselines.py        # Standard TA baselines (RSI, EMA, ATR, MACD, KAMA)
    │   └── custom_examples.py  # Physics-inspired indicators (KalmanFilter, PhaseSpaceEnergy, EntropyFlow)
    ├── proofs/
    │   ├── __init__.py
    │   ├── entropy.py          # Shannon, Mutual Info, Symbolic & k-NN Transfer Entropy + IAAFT/Block Surrogates
    │   ├── stats_gate.py       # Spearman Rank IC, Wasserstein Distance, Orthogonality VIF/Corr + ProofSuite runner
    │   └── dsp.py              # Hilbert Transform, Bode Phase Lag vs. Smoothness (Jerk) Frontier
    ├── transpiler/
    │   ├── __init__.py
    │   └── pine_v6.py          # SymPy AST -> TradingView Pine Script v6 + Markdown Research Card
    └── dashboard/
        ├── __init__.py
        └── app.py              # 4-Quadrant Interactive Quant Diagnostic Dashboard (Streamlit + Plotly + Lightweight Charts)

tests/
├── __init__.py
├── test_data_stationarity.py   # PIT loader, Parquet cache, FracDiff zero-lookahead & ADF tests
├── test_indicators.py          # Baselines + Physics indicators numerical & zero-lookahead tests
├── test_proofs.py              # Entropy, Surrogate TE ground-truth causality, Stats Gate, DSP Pareto tests
├── test_transpiler.py          # SymPy AST -> Pine Script v6 & Research Card tests
└── test_cli_and_dashboard.py   # CLI commands & 4-Quadrant Dashboard state/chart builder tests
```

**Structure Decision**: Single Python package at repository root using standard `src/quantlab/` layout managed by `uv` and `pyproject.toml`, matching the exact module tree specified in the user request.

## Complexity Tracking

No Constitution Check violations.
