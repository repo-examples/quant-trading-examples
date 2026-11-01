---
description: "Task list for Fix TradingView Lightweight Charts Rendering Across Market Data Providers"
---

# Tasks: Fix TradingView Lightweight Charts Rendering Across Market Data Providers

**Input**: Design documents from `/specs/002-fix-tradingview-chart-yfinance/`

**Prerequisites**: `plan.md` (required), `spec.md` (required for user stories), `research.md`, `data-model.md`, `contracts/lightweight-charts-canvas.md`

**Tests**: Unit and integration regression tests are included in `tests/test_data_stationarity.py` and `tests/test_cli_and_dashboard.py`.

**Organization**: Tasks are grouped by phase and user story to enable independent implementation and verification.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (`[US1]`, `[US2]`)
- Exact file paths are included in every task description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify baseline test suite and inspect existing cached Parquet datasets in `.cache/parquet/`.

- [X] T001 Verify baseline test suite and linter state in `src/quantlab/data/loader.py` and `src/quantlab/dashboard/app.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement resolution-agnostic UTC Unix epoch second extraction and `OHLCVDataset.unix_timestamps` in `src/quantlab/data/loader.py`.

- [X] T002 Implement `extract_unix_timestamps(index: pd.DatetimeIndex) -> np.ndarray` and `OHLCVDataset.unix_timestamps` property in `src/quantlab/data/loader.py` converting `s`, `ms`, `us`, and `ns` `DatetimeIndex` resolutions to strictly increasing UTC Unix epoch seconds (`int64`, `ts[i] > ts[i-1]`)

**Checkpoint**: `OHLCVDataset.unix_timestamps` produces identical, strictly ascending Unix epoch second arrays across all `DatetimeIndex` units.

---

## Phase 3: User Story 1 - Render TradingView Lightweight Charts Canvas for `yfinance` and `ccxt` Datasets (Priority: P1) 🎯 MVP

**Goal**: Fix `build_lightweight_charts_canvas_html` so that `yfinance`, `ccxt`, and `synthetic` datasets across all resolutions render all candlesticks, indicator traces, and time-scale labels on the TradingView Lightweight Charts HTML5 Canvas.

**Independent Test**: Load a `yfinance` (`SPY`, `1d`, `600` bars) dataset and a `datetime64[ms, UTC]` / `datetime64[s, UTC]` / `datetime64[us, UTC]` / `datetime64[ns, UTC]` dataset, call `build_lightweight_charts_canvas_html`, parse the embedded `candles` and `ind_points` JSON arrays, and verify `600` strictly ascending unique Unix epoch seconds (`> 946684800`) and finite values.

### Tests for User Story 1

- [X] T003 [P] [US1] Add unit tests in `tests/test_data_stationarity.py` verifying `extract_unix_timestamps` and `OHLCVDataset.unix_timestamps` across `datetime64[s, UTC]`, `datetime64[ms, UTC]`, `datetime64[us, UTC]`, `datetime64[ns, UTC]`, and tz-naive `DatetimeIndex` inputs
- [X] T004 [P] [US1] Add integration tests in `tests/test_cli_and_dashboard.py` parsing the JSON `candles` and `ind_points` embedded in `build_lightweight_charts_canvas_html` for `yfinance` (`datetime64[ms, UTC]`), `ccxt`, and `synthetic` datasets (including `15m` intraday and overlay/non-overlay indicators) to assert strictly increasing unique `time` values and finite numbers

### Implementation for User Story 1

- [X] T005 [US1] Update `build_lightweight_charts_canvas_html` in `src/quantlab/dashboard/app.py` to use `dataset.unix_timestamps`, sanitize non-finite OHLC and indicator values (`nan=0.0, posinf=0.0, neginf=0.0`), and enable `autoSize: true` on `LightweightCharts.createChart`

**Checkpoint**: User Story 1 is complete and verified — `yfinance` and `ccxt` charts render all candlesticks, indicator traces, and calendar dates in the TradingView canvas.

---

## Phase 4: User Story 2 - Seamless Provider & Timeframe Switching in Research Controls Sidebar (Priority: P2)

**Goal**: Support all dashboard timeframes (`1d`, `4h`, `1h`, `15m`) in `_fetch_yfinance` (via causal `1h`-to-`4h` OHLCV aggregation) and isolate the sidebar symbol input per provider so switching between `synthetic`, `yfinance`, and `ccxt` populates the appropriate default symbol without stale `SYNTH:` state.

**Independent Test**: Verify `_fetch_yfinance` `4h` resampling logic and `fetch_ohlcv` cross-provider symbol sanitization with unit tests in `tests/test_data_stationarity.py` and dashboard bundle tests in `tests/test_cli_and_dashboard.py`.

### Tests for User Story 2

- [X] T006 [P] [US2] Add unit tests in `tests/test_data_stationarity.py` for `_resample_ohlcv_4h` / `_fetch_yfinance` `4h` timeframe aggregation and cross-provider `SYNTH:` symbol fallback sanitization in `fetch_ohlcv`

### Implementation for User Story 2

- [X] T007 [US2] Implement causal `1h`-to-`4h` OHLCV resampling helper `_resample_ohlcv_4h` and `4h` interval support in `_fetch_yfinance`, plus cross-provider `SYNTH:` symbol sanitization in `fetch_ohlcv` within `src/quantlab/data/loader.py`
- [X] T008 [US2] Update `render_streamlit_app` in `src/quantlab/dashboard/app.py` to bind the symbol `st.text_input` with a provider-specific key (`key=f"symbol_input_{provider}"`) so switching providers cleanly switches default symbols (`SYNTH:COUPLED_OU`, `SPY`, `BTC/USDT`)

**Checkpoint**: User Stories 1 and 2 both work independently and pass all tests.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Full test suite, ruff linting, and headless dashboard self-check validation.

- [X] T009 Run `uv run pytest -v`, `uv run ruff check src tests`, and `uv run quantlab dashboard --check` to verify 100% pass rate across `src/` and `tests/`

---

## Dependencies & Execution Order

- **Phase 1 (T001)** → **Phase 2 (T002)** → **Phase 3 (T003, T004, T005)** → **Phase 4 (T006, T007, T008)** → **Phase 5 (T009)**.
- `T003` and `T004` can execute in parallel (`[P]`).
- `T005` depends on `T002`.
- `T007` and `T008` touch different files (`loader.py` vs `app.py`) and can be developed cleanly in sequence or parallel.

## Implementation Strategy

1. Complete Foundational timestamp extraction (`T002`) in `src/quantlab/data/loader.py`.
2. Complete MVP User Story 1 (`T003`–`T005`) in `src/quantlab/dashboard/app.py` and `tests/`.
3. Complete User Story 2 (`T006`–`T008`) for `4h` `yfinance` support and provider-scoped symbol input.
4. Run full verification (`T009`).
