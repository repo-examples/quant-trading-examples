# Implementation Plan: Fix TradingView Lightweight Charts Rendering Across Market Data Providers

**Branch**: `feat/002-fix-tradingview-chart-yfinance` | **Date**: 2026-11-01 | **Spec**: [spec.md](file:///C:/Users/rogal/workspaces/ws-trading/quant-trading-examples/specs/002-fix-tradingview-chart-yfinance/spec.md)

**Input**: Feature specification from `/specs/002-fix-tradingview-chart-yfinance/spec.md`

## Summary

Fix the disappearing TradingView Lightweight Charts HTML5 Canvas when switching the Market Data Provider to `yfinance` (or `ccxt`, or intraday `synthetic` timeframes). In Pandas 2.x/3.x, `df.index.astype("int64") // 10**9` truncates non-nanosecond `DatetimeIndex` units (`datetime64[ms, UTC]` from `yfinance`/`ccxt` and `datetime64[us, UTC]` from `synthetic`) into duplicate integer timestamps (`[1718, 1718, ...]`), causing TradingView Lightweight Charts v4.2.0 to fail its strictly ascending timestamp invariant and render a blank canvas. We introduce resolution-agnostic UTC Unix epoch second extraction (`extract_unix_timestamps` using `.as_unit("s").astype("int64")` with strict monotonicity guarantees), add `4h` intraday resampling support in `_fetch_yfinance`, scope the sidebar symbol input per provider, enable `autoSize: true` on the Lightweight Charts instance, and add comprehensive regression tests across `s`, `ms`, `us`, and `ns` index resolutions.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: `pandas`, `numpy`, `streamlit`, `plotly`, `yfinance`, `ccxt`, TradingView `lightweight-charts@4.2.0`

**Storage**: Local Point-in-Time Parquet cache (`.cache/parquet/`) via `pandas`/`pyarrow`

**Testing**: `pytest` + `ruff`

**Target Platform**: Cross-platform CLI & Streamlit Web Application

**Project Type**: Quantitative Research CLI & Interactive Web Dashboard (`src/quantlab/`)

**Performance Goals**: `< 5ms` timestamp extraction and HTML canvas serialization for `2,000` OHLCV bars

**Constraints**: Strict Point-in-Time (PIT) causal alignment, zero duplicate timestamps, offline deterministic fallback

**Scale/Scope**: `200` to `2,000` bars across `synthetic`, `yfinance`, and `ccxt` providers and `1d`, `4h`, `1h`, `15m` timeframes

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Causal Point-in-Time (PIT) Alignment**: PASS — Timestamp normalization to UTC Unix epoch seconds and `1h`-to-`4h` OHLCV resampling (`label="right", closed="right"` or bar-start aligned without future leakage) preserve strict PIT ordering.
- **II. Dual Neuro-Symbolic Indicator Representation**: PASS — Indicator registry and AST transpiler remain untouched and fully compatible.
- **III. Information-Theoretic & Statistical Proof Gating**: PASS — All 4 proof gates remain active and verified.
- **IV. Vectorization, JIT Acceleration & Strict Static Typing**: PASS — Timestamp extraction uses vectorized `DatetimeIndex.as_unit("s").astype("int64")` and `numpy` operations with strict type annotations.
- **V. CLI-First Architecture & Deterministic Reproducibility**: PASS — Both `quantlab dashboard --check` and live `quantlab dashboard` verify cleanly offline and with cached Parquet datasets.

## Project Structure

### Documentation (this feature)

```text
specs/002-fix-tradingview-chart-yfinance/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── lightweight-charts-canvas.md
└── tasks.md             # Phase 2 output (/speckit-tasks command)
```

### Source Code (repository root)

```text
src/quantlab/
├── cli.py
├── data/
│   ├── loader.py        # extract_unix_timestamps(), OHLCVDataset.unix_timestamps, _fetch_yfinance 4h support
│   └── stationarity.py
├── indicators/
│   ├── baselines.py
│   ├── custom_examples.py
│   └── registry.py
├── proofs/
│   ├── dsp.py
│   ├── entropy.py
│   └── stats_gate.py
├── transpiler/
│   └── pine_v6.py
└── dashboard/
    └── app.py           # build_lightweight_charts_canvas_html() fix, autoSize, provider-keyed symbol input

tests/
├── test_cli_and_dashboard.py
└── test_data_stationarity.py
```

**Structure Decision**: Existing single-package `src/quantlab/` layout is preserved; changes are localized to `src/quantlab/data/loader.py`, `src/quantlab/dashboard/app.py`, and their corresponding test modules in `tests/`.

## Complexity Tracking

No constitution violations.
