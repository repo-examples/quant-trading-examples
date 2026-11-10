# Implementation Plan: QuantLab Chart UX, Multi-Timeframe Controls & Contextual Help (`SPEC-CHART-TV-01` / `SPEC-CTRL-TF-02` / `SPEC-UI-HELP-03`)

**Branch**: `feat/004-chart-ux-timeframes` | **Date**: 2026-11-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-chart-ux-timeframes/spec.md`

## Summary

Resolve blank TradingView Lightweight Charts HTML5 Canvas rendering under `yfinance`/`ccxt` (`SPEC-CHART-TV-01`), expand interactive multi-timeframe support across `15m`, `1h`, `4h`, `1D`, `1W`, `1M`, and `3M` with bidirectional sidebar + Q1 quick-switcher synchronization and `35`-bar / clamped-history / resampled guards (`SPEC-CTRL-TF-02`), and introduce standardized collision-free chart header bars with anchored `?` contextual help popovers across all 8 diagnostic charts in Tabs `Q1`–`Q3` plus the `Q4` Neuro-Symbolic Pine v6 Studio (`SPEC-UI-HELP-03`).

## Technical Context

**Language/Version**: Python 3.11+ (tested on Python 3.11 / 3.12 with `pandas` 2.2+ / 3.1+, `numpy` 1.26+, `numba` 0.59+)

**Primary Dependencies**: `streamlit>=1.35.0` (1.66+ `st.popover`, `st.pills`, `st.query_params`), `plotly>=5.22.0`, TradingView Lightweight Charts (`lightweight-charts@4.2.1` HTML5 standalone canvas), `yfinance>=0.2.38`, `ccxt>=4.2.0`, `typer>=0.12.0`, `rich>=13.7.0`

**Storage**: Local Point-in-Time Parquet cache (`.cache/parquet/`) keyed by `(provider, symbol, canonical_timeframe, bars, seed)`

**Testing**: `pytest>=8.2.0` + `ruff>=0.4.0` + headless `quantlab dashboard --check`

**Target Platform**: Responsive Web analytical studio (`streamlit` desktop-first dark mode with tablet `< 1024px` and mobile `< 768px` adaptive breakpoints and `.streamlit/config.toml` dark theme lock) + cross-platform CLI

**Project Type**: Quantitative research CLI library & interactive 4-quadrant diagnostic web application

**Performance Goals**: `< 50ms` chart HTML serialization and header rendering overhead; zero uncompiled Python loops in numerical indicator/proof kernels; immediate 1-click timeframe switching

**Constraints**: Strict Point-in-Time (PIT) causal alignment (`t <= T`, zero lookahead bias in OHLCV resampling and chart serialization); minimum `35`-bar proof sample guard; WCAG AA contrast (`>= 4.5:1`), `role="img"` + dynamic `aria-label` on HTML5 canvas, and color-blind safe regime differentiation on `Q3B`

**Scale/Scope**: 7 canonical UI timeframes (`15m`, `1h`, `4h`, `1D`, `1W`, `1M`, `3M`), 3 market data providers (`synthetic`, `yfinance`, `ccxt`), 8 registered indicators, and 9 contextual help header panels (`TV-01`, `Q1A`, `Q1B`, `Q2A`, `Q2B`, `Q3A`, `Q3B`, `Q3C`, `Q4A`)

## Constitution Check

*GATE: Passed before Phase 0 research and re-verified after Phase 1 design.*

- **I. Causal Point-in-Time (PIT) Alignment (NON-NEGOTIABLE)**: **PASS** — Higher-timeframe resampling (`4h`, `1M`, `3M`) aggregates strictly within causal bar boundaries (`open=first`, `high=max`, `low=min`, `close=last`, `volume=sum`) and drops incomplete/NaN rows without peeking ahead; Lightweight Charts serialization preserves strictly ascending timestamps and maps warm-up `NaN`s to causal whitespace entries (`{"time": bar_time}`).
- **II. Dual Neuro-Symbolic Indicator Representation**: **PASS** — All 8 registered indicators retain their `@numba.njit` kernels and `sympy.Expr` ASTs unchanged; Q4 Studio gains contextual help entry `Q4A`.
- **III. Information-Theoretic & Statistical Proof Gating**: **PASS** — Enforces `MIN_PROOF_BARS = 35` before executing ADF FracDiff, IAAFT Transfer Entropy, Spearman Rank IC / Wasserstein $W_1$ / VIF, and Hilbert Bode-Jerk proofs so higher timeframes (`1M`, `3M`) never evaluate degenerate under-sampled series.
- **IV. Vectorization, JIT Acceleration & Strict Static Typing**: **PASS** — Timestamp extraction (`.as_unit("s").astype("int64")`), calendar formatting, and OHLCV sanitization use vectorized `pandas`/`numpy` operations, strict Python 3.11+ type annotations, and `dataclass(frozen=True)` models (`TimeframeSpec`, `ChartHelpEntry`).
- **V. CLI-First Architecture & Deterministic Reproducibility**: **PASS** — `quantlab fetch`, `quantlab evaluate`, and `quantlab dashboard --check` support all new timeframes (`1W`, `1M`, `3M`) deterministically offline via `synthetic` as well as online via `yfinance`/`ccxt`.

## Project Structure

### Documentation (this feature)

```text
specs/004-chart-ux-timeframes/
├── plan.md                                      # This file (/speckit-plan output)
├── research.md                                  # Phase 0 research decisions & rationale
├── data-model.md                                # Phase 1 entities & state transitions
├── quickstart.md                                # Phase 1 runnable validation guide
├── contracts/
│   └── chart-ux-and-timeframe-contracts.md      # Phase 1 loader, canvas & help contracts
├── checklists/
│   ├── requirements.md                          # Spec quality checklist
│   └── chart-ux-timeframes.md                   # Phase 6 domain quality checklist
└── tasks.md                                     # Phase 7 actionable task breakdown
```

### Source Code (repository root)

```text
.streamlit/
└── config.toml                                  # Dark-theme lock (#0E1117 / #1A1D24 / #FF4B4B)

src/quantlab/
├── cli.py                                       # CLI timeframe help & dashboard self-check integration
├── data/
│   └── loader.py                                # TimeframeSpec, normalize_timeframe, MultiIndex flatten, max history, causal resample, InsufficientHistoryError
└── dashboard/
    ├── chart_help.py                            # NEW: SPEC-UI-HELP-03 ChartHelpEntry, CHART_HELP_REGISTRY (9 panels), header & popover renderer
    ├── loading_state.py                         # Extended summary bar badges for clamped/resampled higher-timeframe runs + responsive CSS
    └── app.py                                   # SPEC-CHART-TV-01 Lightweight Charts serializer/canvas, SPEC-CTRL-TF-02 sidebar + Q1 quick-switcher + query sync + 35-bar guard, collision-free Plotly layouts & Q3B color-blind borders

tests/
├── test_data_stationarity.py                    # Multi-timeframe normalization, MultiIndex, timestamp units, causal resampling & <35 bar guard tests
├── test_chart_ux_and_help.py                    # NEW: Dedicated unit & integration tests for SPEC-CHART-TV-01, SPEC-CTRL-TF-02, and SPEC-UI-HELP-03
├── test_loading_state_ui.py                     # Existing + clamped/resampled summary badge verification
└── test_cli_and_dashboard.py                    # CLI higher-timeframe fetch & headless dashboard self-check verification
```

**Structure Decision**: Extends the single-package `src/quantlab/` architecture cleanly by adding a focused, independently testable `src/quantlab/dashboard/chart_help.py` module for `SPEC-UI-HELP-03` alongside targeted enhancements to `loader.py`, `loading_state.py`, `app.py`, `cli.py`, and `.streamlit/config.toml`.

## Complexity Tracking

No Constitution Check violations exist; no complexity exemptions required.
