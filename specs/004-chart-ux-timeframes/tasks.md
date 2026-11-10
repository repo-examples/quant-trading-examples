# Tasks: QuantLab Chart UX, Multi-Timeframe Controls & Contextual Help (`SPEC-CHART-TV-01` / `SPEC-CTRL-TF-02` / `SPEC-UI-HELP-03`)

**Input**: Design documents from `/specs/004-chart-ux-timeframes/`

**Prerequisites**: `plan.md` (required), `spec.md` (required for user stories), `research.md`, `data-model.md`, `contracts/chart-ux-and-timeframe-contracts.md`, `quickstart.md`

**Tests**: Included across all user stories in accordance with `plan.md` and the QuantLab Constitution (`pytest -v`, `ruff check src tests`, and `quantlab dashboard --check`).

**Organization**: Tasks are grouped by user story (`US1` -> `US2` -> `US3`) so each story can be implemented, verified, and demonstrated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (`[US1]`, `[US2]`, `[US3]`) for story phases only
- Exact repository file paths are included in every task description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish workspace dark-theme lock and module scaffolding shared across chart UX specifications.

- [X] T001 [P] Create `.streamlit/config.toml` locking dark-mode design tokens (`base = "dark"`, `backgroundColor = "#0E1117"`, `secondaryBackgroundColor = "#1A1D24"`, `primaryColor = "#FF4B4B"`, `textColor = "#F8FAFC"`) so browser light-mode overrides never break hardcoded dark chart surfaces (`FR-015`).
- [X] T002 [P] Scaffold `src/quantlab/dashboard/chart_help.py` and export chart UX spec constants (`SPEC_TV_ID = "SPEC-CHART-TV-01"`, `SPEC_TF_ID = "SPEC-CTRL-TF-02"`, `SPEC_HELP_ID = "SPEC-UI-HELP-03"`) across `src/quantlab/dashboard/chart_help.py` and `src/quantlab/dashboard/app.py`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared Point-in-Time data loader primitives, timeframe descriptors, timestamp normalization, and minimum-sample validation required before user story UI wiring.

**⚠️ CRITICAL**: Complete this phase before starting User Stories 1, 2, and 3.

- [X] T003 Define `TimeframeSpec`, `TIMEFRAME_SPECS`, `UI_TIMEFRAMES = ("15m", "1h", "4h", "1D", "1W", "1M", "3M")`, `HIGHER_TIMEFRAME_PILLS = ("1D", "1W", "1M", "3M")`, `MIN_PROOF_BARS = 35`, `normalize_timeframe()`, and `get_timeframe_spec()` in `src/quantlab/data/loader.py`, enforcing verbatim constraints: preserve exact `"1m"` as `"1m"` (1-minute CLI/synthetic interval) while mapping `"1M"`, `"1mo"`, `"1MO"` to `"1M"` (1 Month); map `"1d"`/`"1D"` -> `"1D"`, `"1w"`/`"1W"`/`"1wk"`/`"1WK"` -> `"1W"`, `"3m"`/`"3M"`/`"3mo"`/`"3MO"` -> `"3M"`, `"4h"`/`"4H"` -> `"4h"`, `"1h"`/`"1H"` -> `"1h"`, `"15m"`/`"15M"` -> `"15m"`, `"5m"`/`"5M"` -> `"5m"`, and raise `ValueError` on unknown timeframe tokens (`FR-001`, `FR-002`).
- [X] T004 Implement `extract_unix_timestamps()`, `extract_calendar_dates()`, and `resample_ohlcv_causal()` (`open=first`, `high=max`, `low=min`, `close=last`, `volume=sum`, dropping incomplete/NaN rows with zero lookahead bias) in `src/quantlab/data/loader.py`, ensuring strictly increasing `int64` UTC Unix epoch seconds across any `DatetimeIndex` unit (`s`, `ms`, `us`, `ns`) and timezone-normalized `"YYYY-MM-DD"` strings for calendar timeframes (`1D`, `1W`, `1M`, `3M`) (`FR-001`, `FR-003`, `FR-007`).
- [X] T005 Extend `OHLCVDataset` (`requested_bars: int | None = None`, `resampled_from: str | None = None`, plus computed properties `canonical_timeframe`, `is_clamped` when `requested_bars is not None and self.n_bars < requested_bars`, `unix_timestamps`, `calendar_dates`) and add `InsufficientHistoryError` (`symbol: str`, `timeframe: str`, `available_bars: int`, `minimum_bars: int = 35`) and `validate_minimum_proof_bars()` in `src/quantlab/data/loader.py` (`FR-004`, `FR-005`).

**Checkpoint**: Foundational loader entities and causal PIT timestamp helpers ready for user story implementation.

---

## Phase 3: User Story 1 - Reliable Multi-Provider Financial Chart Rendering (`SPEC-CHART-TV-01`) (Priority: P1) 🎯 MVP

**Goal**: Eliminate blank TradingView Lightweight Charts HTML5 canvases under external providers (`yfinance`, `ccxt`) by flattening multi-level OHLCV columns, serializing calendar (`YYYY-MM-DD`) vs. intraday (UTC epoch seconds) bar timestamps accurately, converting warm-up `NaN`s to whitespace objects, and adding live OHLCV+indicator hover legends, responsive sizing, screen-reader summaries, and diagnostic empty/error cards.

**Independent Test**: Load `yfinance` (`SPY`, mocked MultiIndex/second-resolution DataFrames and synthetic series) across `1D`, `1W`, `1M`, `3M`, and `1h` with `MACD` (containing warm-up `NaN`s) and verify non-empty ascending candlesticks, whitespace-aligned indicator entries, top-left crosshair legend markup, `role="img"` + dynamic `aria-label`, and inline diagnostic empty-state card when valid bars equal `0`.

### Tests for User Story 1

- [X] T006 [P] [US1] Add unit tests in `tests/test_data_stationarity.py` covering `yfinance` `pd.MultiIndex` column flattening, `datetime64[s, UTC]` / `ms` / `us` / `ns` timestamp extraction without `// 10**9` collapse, and strictly ascending calendar date formatting (`YYYY-MM-DD`).
- [X] T007 [P] [US1] Create `tests/test_chart_ux_and_help.py` with `SPEC-CHART-TV-01` unit tests verifying `serialize_lightweight_charts_series()` (`YYYY-MM-DD` for `1D`/`1W`/`1M`/`3M`, integer UTC seconds for `15m`/`1h`/`4h`, `{"time": bar_time}` whitespace objects without `"value"` or `0.0` for `NaN`/`Inf` warm-up bars) and `build_lightweight_charts_canvas_html()` (`#tv-legend` crosshair readout, `fitContent()`, `ResizeObserver`, `vertTouchDrag: false`, `role="img"` + dynamic `aria-label`, and inline diagnostic card on empty series).

### Implementation for User Story 1

- [X] T008 [US1] Update `_fetch_yfinance()` and `_validate_ohlcv_frame()` in `src/quantlab/data/loader.py` to flatten `pd.MultiIndex` columns (`raw.columns.get_level_values(0)`), strip non-finite OHLCV rows, deduplicate (`keep="last"`), and sort timestamps in strictly ascending PIT order (`FR-001`).
- [X] T009 [US1] Implement `serialize_lightweight_charts_series()` in `src/quantlab/dashboard/app.py` to emit unique ascending `"YYYY-MM-DD"` strings for calendar timeframes (`1D`, `1W`, `1M`, `3M`), strictly increasing integer UTC epoch seconds for intraday timeframes (`1m`, `5m`, `15m`, `1h`, `4h`), finite OHLC candlestick dicts, and `{"time": bar_time}` whitespace dicts for `NaN`/`Inf` indicator warm-up bars (`FR-007`, `FR-008`).
- [X] T010 [US1] Upgrade `build_lightweight_charts_canvas_html()` in `src/quantlab/dashboard/app.py` with design tokens (`#0E1117` surface, `#1E222D` grid, `#10B981` bull, `#FF2E93` bear, `#00F5D4` indicator, `#9CA3AF` axis text), live top-left `#tv-legend` crosshair hover readout, `autoSize: true` + `ResizeObserver` + `minBarSpacing: 2` + `fitContent()`, mobile touch scroll guard (`vertTouchDrag: false`), `role="img"` + dynamic `aria-label`, and bordered inline empty/render-error state cards (`FR-008`, `FR-009`).

**Checkpoint**: User Story 1 (`SPEC-CHART-TV-01`) is independently functional and verified.

---

## Phase 4: User Story 2 - Interactive Multi-Timeframe Selection & History Sample Guards (`SPEC-CTRL-TF-02`) (Priority: P2)

**Goal**: Enable seamless interactive switching across `15m`, `1h`, `4h`, `1D`, `1W`, `1M`, and `3M` (default `1D`) via both the sidebar selector and a synchronized Q1 quick-switcher bar (`1D | 1W | 1M | 3M`), backed by `period="max"` higher-timeframe fetching, causal provider resampling with notice badges, amber clamped-history badges (`35 <= available < requested`), and inline `< 35`-bar proof guards.

**Independent Test**: Switch timeframes across `15m`, `1h`, `4h`, `1D`, `1W`, `1M`, `3M`; verify `1M -> 1mo` / `3M -> 3mo` (`period="max"`), causal resampling (`3M` on `ccxt`, `4h` on `yfinance`), amber clamped-history badge when `35 <= n_bars < requested_bars`, inline `InsufficientHistoryError` callout when `n_bars < 35`, and synchronized sidebar + Q1 quick-switcher + URL query parameters.

### Tests for User Story 2

- [X] T011 [P] [US2] Add unit tests in `tests/test_data_stationarity.py` for `normalize_timeframe()` (`1M` vs `1m` disambiguation), `generate_synthetic_ohlcv()` across `15m`/`1h`/`4h`/`1D`/`1W`/`1M`/`3M`, `_fetch_yfinance()` `period="max"` + `4h` causal resampling, `_fetch_ccxt()` `3M` causal resampling (`resampled_from="1D"`), causal PIT invariance of `resample_ohlcv_causal()`, `OHLCVDataset.is_clamped`, and `validate_minimum_proof_bars()` raising `InsufficientHistoryError` below `35` bars.
- [X] T012 [P] [US2] Add UI state and badge tests in `tests/test_loading_state_ui.py` and `tests/test_chart_ux_and_help.py` verifying amber clamped-history notice (`"Using all {available} available {timeframe} bars for {symbol} (requested {requested})."`), resampled-history notice (`"Resampled {timeframe} bars from {source} history."`), and inline insufficient-history callout rendering (`render_insufficient_history_html()`).

### Implementation for User Story 2

- [X] T013 [US2] Update `generate_synthetic_ohlcv()`, `_fetch_yfinance()`, `_fetch_ccxt()`, and `fetch_ohlcv()` in `src/quantlab/data/loader.py` to support all canonical timeframes (`15m`, `1h`, `4h`, `1D`, `1W`, `1M`, `3M`), use `period="max"` on `1D`/`1W`/`1M`/`3M`, causally resample unsupported intervals (`4h` from `1h` on `yfinance`; `3M` from `1D` on `ccxt`), normalize cross-provider default symbols (`SYNTH:*` -> `"SPY"` on `yfinance`, `"BTC/USDT"` on `ccxt`), and populate `requested_bars` and `resampled_from` (`FR-002`, `FR-003`, `FR-004`).
- [X] T014 [P] [US2] Extend `build_loading_state_css()` and `render_completed_summary_bar_html()` (plus add `render_insufficient_history_html()`) in `src/quantlab/dashboard/loading_state.py` with optional backwards-compatible parameters (`clamped_bars`, `requested_bars`, `resampled_from`, `timeframe_label`) for amber clamped-history pills (`#3B2F13` fill / `#FBBF24` text), resampled badges, inline `< 35`-bar callouts, and responsive `< 1024px` / `< 768px` layout rules (`FR-005`, `FR-006`).
- [X] T015 [US2] Enforce `validate_minimum_proof_bars(dataset)` inside `build_dashboard_bundle()` and wire bidirectional `ql_timeframe` session state, `st.query_params` (`provider`, `symbol`, `tf`), sidebar `Timeframe` selectbox (`["15m", "1h", "4h", "1D", "1W", "1M", "3M"]`, default `"1D"`), Q1 higher-timeframe quick-switcher (`1D | 1W | 1M | 3M`), clamped/resampled summary pills, and guarded `InsufficientHistoryError` callouts in `src/quantlab/dashboard/app.py` (`FR-005`, `FR-006`, `FR-010`, `FR-011`).
- [X] T016 [P] [US2] Update `--timeframe` option descriptions and output metadata in `src/quantlab/cli.py` to document `15m, 1h, 4h, 1D, 1W, 1M, 3M` (while preserving lowercase CLI aliases) and surface clamped/resampled bar details in `quantlab fetch` (`FR-001`, `FR-004`).

**Checkpoint**: User Stories 1 and 2 (`SPEC-CHART-TV-01` + `SPEC-CTRL-TF-02`) work together and independently.

---

## Phase 5: User Story 3 - Per-Chart Contextual Help Popovers & Collision-Free Headers (`SPEC-UI-HELP-03`) (Priority: P3)

**Goal**: Render a standardized Chart Card Header Bar (`Title` left, accessible `?` Help popover trigger right) above all 8 charts in Tabs `Q1`–`Q3` (`TV-01`, `Q1A`, `Q1B`, `Q2A`, `Q2B`, `Q3A`, `Q3B`, `Q3C`) plus the `Q4` Neuro-Symbolic Studio (`Q4A`), backed by `CHART_HELP_REGISTRY` 3-part microcopy + safe fallback, collision-free Plotly layouts, and color-blind safe `Q3B` regime borders/patterns.

**Independent Test**: Query `CHART_HELP_REGISTRY` across all 9 panel IDs and an unregistered fallback ID; verify 3-part explanation HTML (`What It Is`, `Axes & Visuals`, `How to Interpret`) + runtime context, verify `build_q1_figures()` / `build_q2_figures()` / `build_q3_figures()` omit overlapping internal top titles when headerless and keep `margin.t >= 48` with horizontal top-left legends, and verify `Q3B` Bull/Bear traces include distinct border strokes and pattern shapes.

### Tests for User Story 3

- [X] T017 [P] [US3] Add `SPEC-UI-HELP-03` tests in `tests/test_chart_ux_and_help.py` covering all 9 `CHART_HELP_REGISTRY` entries (`TV-01`, `Q1A`, `Q1B`, `Q2A`, `Q2B`, `Q3A`, `Q3B`, `Q3C`, `Q4A`), 3-part microcopy rendering + active parameter context, graceful fallback on unknown chart IDs, headerless collision-free Plotly layout properties (`title.text is None`, `margin.t >= 48`, horizontal legend), and color-blind safe `Q3B` histogram border/pattern attributes.

### Implementation for User Story 3

- [X] T018 [P] [US3] Implement `ChartHelpEntry`, `CHART_HELP_REGISTRY` (all 9 entries: `TV-01`, `Q1A`, `Q1B`, `Q2A`, `Q2B`, `Q3A`, `Q3B`, `Q3C`, `Q4A` with `what_it_is`, `axes_and_visuals`, `how_to_interpret`), `get_chart_help()` fallback (`"Quantitative diagnostic chart for {indicator_name}. Detailed guide pending."`), `build_chart_help_css()`, `render_chart_help_popover_html()`, and `render_chart_header()` (`st.columns([0.92, 0.08], vertical_alignment="center")` + `st.popover("?", ...)`) in `src/quantlab/dashboard/chart_help.py` (`FR-012`, `FR-013`).
- [X] T019 [US3] Update `_apply_dark_theme()`, `build_q1_figures()`, `build_q2_figures()`, and `build_q3_figures()` in `src/quantlab/dashboard/app.py` to support collision-free headerless chart rendering (`show_title: bool = False` in dashboard bundle figures, `margin={"l": 48, "r": 20, "t": 48, "b": 40}`, horizontal legend `x=0.0, xanchor="left", y=1.08, yanchor="bottom"`), add color-blind safe border strokes and pattern shapes on `Q3B` Bull vs. Bear regime histograms, and mount `render_chart_header()` above `TV-01`, `Q1A`, `Q1B`, `Q2A`, `Q2B`, `Q3A`, `Q3B`, `Q3C`, and `Q4A` (`FR-012`, `FR-014`, `FR-015`).

**Checkpoint**: All three user stories (`SPEC-CHART-TV-01`, `SPEC-CTRL-TF-02`, `SPEC-UI-HELP-03`) are complete and independently testable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end headless self-check integration, CLI/dashboard regression tests, linting, and release changelog readiness.

- [X] T020 Extend `run_dashboard_self_check()` in `src/quantlab/dashboard/app.py` and update `tests/test_cli_and_dashboard.py` to validate `SPEC-CHART-TV-01` canvas serialization, `SPEC-CTRL-TF-02` higher-timeframe (`1W`, `1M`, `3M`) execution, and `SPEC-UI-HELP-03` 9-panel registry completeness alongside `SPEC-QUANT-LOAD-01`.
- [X] T021 [P] Update `README.md` and `CHANGELOG.md` (`## [Unreleased]`) documenting `SPEC-CHART-TV-01`, `SPEC-CTRL-TF-02`, and `SPEC-UI-HELP-03`.
- [X] T022 Run full validation suite (`uv run pytest -v`, `uv run ruff check src tests`, and `uv run quantlab dashboard --check`) per `specs/004-chart-ux-timeframes/quickstart.md` and confirm 100% green execution.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Starts immediately (`T001`, `T002` in parallel).
- **Phase 2 (Foundational)**: Depends on Phase 1; blocks User Stories 1–3 (`T003` -> `T004` -> `T005` in `src/quantlab/data/loader.py`).
- **Phase 3 (US1 - `SPEC-CHART-TV-01`, P1 🎯 MVP)**: Depends on Phase 2; delivers fixed multi-provider HTML5 candlestick + indicator rendering.
- **Phase 4 (US2 - `SPEC-CTRL-TF-02`, P2)**: Depends on Phase 2 (and integrates smoothly with US1's Q1 canvas); delivers `15m`–`3M` controls, `period="max"`, causal resampling, and `< 35` / clamped guards.
- **Phase 5 (US3 - `SPEC-UI-HELP-03`, P3)**: `chart_help.py` (`T018`) can run in parallel after Phase 2; `app.py` wiring (`T019`) integrates cleanly above Q1–Q4 panels.
- **Phase 6 (Polish)**: Depends on Phases 3–5 completion (`T020`–`T022`).

### User Story Dependencies

- **User Story 1 (P1)**: Independent after Foundational Phase 2.
- **User Story 2 (P2)**: Loader/CLI/badge logic (`T013`, `T014`, `T016`) is independent after Phase 2; dashboard wiring (`T015`) builds on Q1 workspace in `app.py`.
- **User Story 3 (P3)**: Help registry & popover component (`T018`) is completely independent in `chart_help.py`; figure layout & header mounting (`T019`) integrates into `app.py`.

### Parallel Opportunities

- `T001` (`.streamlit/config.toml`) and `T002` (`chart_help.py` scaffold) run in parallel.
- `T006` (`tests/test_data_stationarity.py`) and `T007` (`tests/test_chart_ux_and_help.py`) run in parallel.
- `T014` (`loading_state.py`), `T016` (`cli.py`), and `T018` (`chart_help.py`) touch disjoint files and can execute in parallel with `loader.py` (`T013`).

---

## Parallel Example: User Story 2 & User Story 3

```bash
# Execute disjoint module tasks in parallel once Phase 2 is complete:
Task T014: "Extend build_loading_state_css() and render_completed_summary_bar_html() in src/quantlab/dashboard/loading_state.py"
Task T016: "Update --timeframe option descriptions and output metadata in src/quantlab/cli.py"
Task T018: "Implement ChartHelpEntry, CHART_HELP_REGISTRY, and render_chart_header() in src/quantlab/dashboard/chart_help.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) + Phase 2 (Foundational loader primitives).
2. Complete Phase 3 (`US1` — `SPEC-CHART-TV-01` canvas serialization & empty/hover states).
3. Validate `US1` independently via `pytest tests/test_chart_ux_and_help.py`.

### Incremental Delivery

1. **Increment 1 (`US1`)**: Fix blank TradingView canvas, `MultiIndex` flattening, warm-up whitespace sanitization, hover legend, and `role="img"` accessibility.
2. **Increment 2 (`US2`)**: Unlock `15m`–`3M` multi-timeframe switching, Q1 quick-switcher pills, `period="max"`, causal resampling, amber clamped notices, and `< 35`-bar guards.
3. **Increment 3 (`US3`)**: Mount collision-free Chart Header Bars + `?` popovers across all 9 panels (`TV-01`, `Q1A`–`Q3C`, `Q4A`) and color-blind safe `Q3B` styling.
4. **Polish**: Verify `quantlab dashboard --check`, `ruff`, `pytest`, and `CHANGELOG.md`.
