# Feature Specification: QuantLab Chart UX, Multi-Timeframe Controls & Contextual Help (`SPEC-CHART-TV-01` / `SPEC-CTRL-TF-02` / `SPEC-UI-HELP-03`)

**Feature Branch**: `feat/004-chart-ux-timeframes`

**Created**: 2026-11-10

**Status**: Approved

**Input**: User description: "Implement QuantLab Chart UX and Timeframe Specification from https://share.gemini.google/7HfYtRWINioU: (1) SPEC-CHART-TV-01 fix blank TradingView Lightweight Charts canvas under market data providers, sanitize warm-up NaNs, add OHLCV+Indicator hover legend and empty/error states; (2) SPEC-CTRL-TF-02 expand Timeframe selector with 15m, 1h, 4h, 1D, 1W, 1M, 3M (default 1D) plus synced Q1 quick-switcher bar, max-history fetching, clamped-history amber notice when 35 <= bars < requested, insufficient-history guard (< 35 bars), and unsupported-interval resampling notice; (3) SPEC-UI-HELP-03 add standardized Chart Header Bar with anchored ? help popover across all 8 charts in Q1–Q3 plus Q4 SymPy AST Studio header and resolve subplot/legend toolbar collisions."

## Clarifications

### Session 2026-11-10

- Q: How should the multi-timeframe selector (`SPEC-CTRL-TF-02`) present timeframes and quick-switching in the dashboard? → A: Keep intraday + higher timeframes (`15m`, `1h`, `4h`, `1D`, `1W`, `1M`, `3M` — default `1D`) in the sidebar AND add a synced quick-switcher pill bar (`1D | 1W | 1M | 3M`) above the Q1 TradingView chart.
- Q: How should the per-chart Help (`?`) button (`SPEC-UI-HELP-03`) display explanations and which panels should include it? → A: Anchored floating popover (`st.popover("?")`) in a standardized header bar above all 8 charts in Q1–Q3 (`TV-01`, `Q1A`, `Q1B`, `Q2A`, `Q2B`, `Q3A`, `Q3B`, `Q3C`) + Q4 Studio header (`Q4A`), with plain-English intuition and key math thresholds.
- Q: How should QuantLab handle shorter available history on higher timeframes (`1W`, `1M`, `3M`) and providers without native `3M` intervals? → A: Fetch max history on `1D`/`1W`/`1M`/`3M`; auto-clamp with an amber info badge when `35 <= available < requested` bars, show a guarded inline error callout when `< 35` bars, and auto-resample unsupported provider intervals (e.g., `3M` on `ccxt`) with a notice badge.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reliable Multi-Provider Financial Chart Rendering (`SPEC-CHART-TV-01`) (Priority: P1)

When a quantitative researcher selects Yahoo Finance (or any supported market data provider) and loads an asset such as `SPY`, the primary interactive candlestick and indicator chart in Quadrant 1 must reliably paint all historical OHLC candlesticks, chronological X-axis date/time ticks, and the active indicator trace—complete with a live crosshair OHLC + indicator legend, warm-up gap handling, screen-reader summary, and explicit empty/error states if zero valid points are available.

**Why this priority**: Previously, selecting external market data providers caused the primary financial chart canvas to appear completely blank (showing stranded axis tags without candlesticks or dates) even while the pipeline banner reported green completion, blocking visual verification of price-indicator alignment.

**Independent Test**: Load `SPY` on Yahoo Finance across daily (`1D`), weekly (`1W`), monthly (`1M`), quarterly (`3M`), and intraday (`1h`) timeframes with an indicator containing warm-up bars (such as `MACD` or `EMA`), and verify that non-empty ascending candlesticks, indicator points, chronological X-axis labels, crosshair hover readout, and accessible summary attributes render without blank canvases or artificial zero spikes during indicator warm-up.

**Acceptance Scenarios**:

1. **Given** a researcher selects an external market data provider (e.g., Yahoo Finance with `SPY`) and any supported timeframe, **When** the pipeline completes, **Then** the primary financial chart renders all valid historical OHLC candlesticks on the right price axis, the active indicator trace on the left scale (or overlaid on the right scale for price-overlay indicators), chronological X-axis date/time labels, and auto-fits the full series into the viewport.
2. **Given** an active indicator produces leading non-finite (`NaN`) values during its initial warm-up window, **When** the primary financial chart renders, **Then** warm-up timestamps remain aligned with their corresponding price candlesticks as blank whitespace entries rather than coercing warm-up bars to `0.0` or aborting chart rendering.
3. **Given** a researcher hovers or moves the crosshair across the primary financial chart, **When** inspecting individual bars, **Then** a dynamic top-left legend readout updates with the symbol, timeframe, open/high/low/close values, and active indicator value, while touch viewports allow vertical page scrolling without trapping single-finger gestures.
4. **Given** a market data request or chart payload yields zero valid renderable bars (or encounters a client rendering failure), **When** the chart container mounts, **Then** a clear bordered diagnostic state card with a recovery message is shown inside the chart region rather than an empty grid.

---

### User Story 2 - Interactive Multi-Timeframe Selection & History Sample Guards (`SPEC-CTRL-TF-02`) (Priority: P2)

When analyzing an asset across short-term tactical and long-term macro horizons, a researcher must be able to choose and switch seamlessly across intraday and higher timeframes (`15m`, `1h`, `4h`, `1D`, `1W`, `1M`, `3M`, defaulting to `1D`) from either the left Research Controls sidebar or a synchronized quick-switcher bar above Quadrant 1—automatically retrieving maximum available history for daily and higher timeframes, displaying an amber availability notice when available history is shorter than requested (`35 <= available < requested`), halting proofs cleanly with an inline guidance callout when history is below the statistical minimum (`< 35` bars), and resampling automatically with a notice badge when a provider lacks native higher-timeframe bars.

**Why this priority**: Researchers could not select timeframes above `1d` (`1W`, `1M`, `3M`), and switching to monthly or quarterly bars without provider interval translation and sample-size guards either raised provider errors or starved stationarity and surrogate proofs on assets with finite trading history.

**Independent Test**: Switch timeframes interactively across `1D`, `1W`, `1M`, `3M`, and `1h` via both the sidebar selector and the Q1 quick-switcher bar; verify bidirectional state synchronization, uppercase display labels in status pills, amber clamped-history notice when requesting `600` bars on `SPY` `3M` (~135 available bars), guarded inline error callout when an asset has `< 35` bars, and automatic OHLCV resampling notice when `3M` is requested from a provider without native quarterly candles.

**Acceptance Scenarios**:

1. **Given** the Research Controls sidebar and Quadrant 1 workspace are open, **When** a researcher views or changes the Timeframe control (`15m`, `1h`, `4h`, `1D`, `1W`, `1M`, `3M`, default `1D`) in either the sidebar dropdown or the Q1 quick-switcher bar, **Then** both controls stay synchronized, URL query parameters reflect the active context (`provider`, `symbol`, `tf`), and the entire quantitative pipeline and all 4 quadrants recompute for the newly selected timeframe.
2. **Given** a researcher selects `1M` or `3M` with `600` requested history bars on an asset that has between `35` and `599` total historical bars (e.g., `SPY` with ~135 quarterly `3M` bars), **When** data is loaded, **Then** the pipeline executes on all available historical bars and displays a non-blocking amber info badge stating `"Using all {available} available {timeframe} bars for {symbol} (requested {requested})."` alongside the status summary bar.
3. **Given** a researcher selects a symbol and timeframe combination returning fewer than `35` historical bars (e.g., a recent listing on `3M`), **When** the pipeline evaluates sample sufficiency, **Then** proof computation halts before producing misleading metrics and displays a clear inline callout: `"Insufficient history: {symbol} only has {available} bars on {timeframe} (minimum 35 required for indicator & stationarity proofs). Switch to 1W or 1D."`
4. **Given** a researcher selects a timeframe not natively served by the chosen provider (such as `3M` on an exchange feed or `4h` on daily/hourly feeds), **When** market data is fetched, **Then** the loader causally aggregates lower-timeframe OHLCV bars (`Open=first`, `High=max`, `Low=min`, `Close=last`, `Volume=sum`) with zero lookahead bias and surfaces a notice badge (`"Resampled {timeframe} bars from {source_timeframe} history."`).

---

### User Story 3 - Per-Chart Contextual Help Popovers & Collision-Free Headers (`SPEC-UI-HELP-03`) (Priority: P3)

When examining any diagnostic chart across Quadrants 1–3 (`TV-01`, `Q1A`, `Q1B`, `Q2A`, `Q2B`, `Q3A`, `Q3B`, `Q3C`) or the Quadrant 4 Neuro-Symbolic Pine v6 Studio (`Q4A`), a researcher must see a standardized header bar above each panel with the panel title on the left and a right-aligned `?` Help trigger button that opens an anchored floating popover explaining **1. What It Is**, **2. Axes & Visuals**, and **3. How to Interpret** (including active parameter context and quantitative pass/fail thresholds), while eliminating title, legend, and interactive toolbar overlaps inside the charts.

**Why this priority**: Quantitative diagnostics such as Takens 3D delay embeddings, IAAFT Transfer Entropy surrogates, Rank IC / VIF orthogonality bars, Wasserstein regime densities, and Hilbert Bode-Jerk frontiers are mathematically dense; inline contextual explanations make every chart immediately interpretable while moving titles out of plot margins resolves legend/toolbar collisions.

**Independent Test**: Inspect all 8 charts across Tabs `Q1`, `Q2`, and `Q3` plus the `Q4` Studio header; verify that every panel renders a collision-free header row with a uniquely labeled `?` popover trigger, that opening each `?` trigger renders the 3-part structured explanation (`What It Is`, `Axes & Visuals`, `How to Interpret`) with dynamic parameter/threshold context, that missing help keys degrade gracefully to a fallback summary instead of failing, and that chart legends/toolbars no longer overlap subplot titles.

**Acceptance Scenarios**:

1. **Given** any diagnostic chart in Tabs `Q1` (`TV-01`, `Q1A`, `Q1B`), `Q2` (`Q2A`, `Q2B`), `Q3` (`Q3A`, `Q3B`, `Q3C`), or the `Q4` Symbolic Studio (`Q4A`), **When** the workspace renders, **Then** a dedicated header bar appears directly above each panel with the panel title on the left and an accessible `?` help trigger on the right, and chart subplot margins/legends are positioned so interactive hover toolbars and legends never collide with titles.
2. **Given** a researcher clicks, taps, or activates `?` via keyboard on any chart header, **When** the anchored popover opens, **Then** it displays three structured sections (**1. What It Is**, **2. Axes & Visuals**, **3. How to Interpret**) tailored to that specific chart along with active run context (e.g., symbol, timeframe, indicator, phase delay `tau`, or proof gate thresholds such as `ADF p < 0.05`, `|IC| > 0.02`, `VIF < 5.0`) without shifting page scroll position.
3. **Given** a future or custom panel requests help using an unregistered identifier, **When** the header bar renders its `?` popover, **Then** it displays a graceful fallback guide (`"Quantitative diagnostic chart for {indicator}. Detailed guide pending."`) rather than raising an error.
4. **Given** users with color-vision deficiency (deuteranopia/protanopia) or assistive screen readers inspect the workspace, **When** viewing `Q3B` Regime Distribution Separation and chart headers, **Then** bull and bear regime distributions are distinguishable via distinct border/pattern styling in addition to color, and every `?` control and financial canvas carries descriptive accessible labels.

---

### Edge Cases

- **Multi-Column / Tuple Provider Responses**: When an external market data feed returns nested or multi-level column headers for a single ticker, column names are flattened cleanly before extracting `open`, `high`, `low`, `close`, and `volume`.
- **Mixed Timestamp Resolutions & Timezones**: Whether a data source provides timestamps in seconds, milliseconds, microseconds, or nanoseconds—or with exchange-local timezone offsets—daily and higher-timeframe candles serialize as unique ascending calendar dates (`YYYY-MM-DD`) and intraday candles serialize as strictly increasing UTC epoch seconds.
- **Indicator Warm-Up & All-NaN Series**: Indicators with multi-bar lookback windows (e.g., `MACD` 26-bar EMA + 9-bar signal) preserve timestamp alignment via whitespace entries during warm-up; if an entire series is non-finite or empty, the canvas surfaces an explicit diagnostic empty/error card rather than stranding corrupt axis tags.
- **Clamped vs. Insufficient History on `1M` / `3M`**: Assets with `35 <= available_bars < requested_bars` proceed automatically with an amber clamped-history notice pill, whereas assets with `< 35` bars stop cleanly before stationarity/entropy estimation and present an actionable inline recovery message.
- **CLI Backwards Compatibility**: Lowercase CLI timeframe flags (e.g., `quantlab fetch --timeframe 1d` or `1w` / `1mo` / `3mo`) and canonical uppercase labels (`1D`, `1W`, `1M`, `3M`) both resolve seamlessly through the shared timeframe normalization contract.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The market data loader MUST normalize multi-level provider columns, deduplicate and sort timestamps in strictly ascending Point-in-Time (PIT) order, filter out non-finite OHLCV rows, and maintain full backwards compatibility with both uppercase UI timeframe labels (`15m`, `1h`, `4h`, `1D`, `1W`, `1M`, `3M`) and lowercase CLI aliases (`1d`, `1w`, `1wk`, `1mo`, `3mo`).
- **FR-002**: Canonical timeframe mappings MUST translate `1D -> 1d`, `1W -> 1wk`, `1M -> 1mo`, and `3M -> 3mo` with maximum available history retrieval (`max` lookback before slicing to the requested PIT bar count) so `1M` is never misinterpreted as 1-minute intraday data.
- **FR-003**: When a selected data provider does not natively serve a requested higher timeframe (such as `3M` on exchange feeds or `4h` on hourly feeds), the loader MUST causally aggregate lower-timeframe OHLCV bars (`open=first`, `high=max`, `low=min`, `close=last`, `volume=sum`) and record resampling metadata so the UI can display a `"Resampled {timeframe} bars from {source} history."` notice badge.
- **FR-004**: Dataset metadata MUST track `requested_bars`, `available_bars` (`n_bars`), `is_clamped` (`35 <= n_bars < requested_bars`), and `resampled_from` so downstream CLI and dashboard views can distinguish full samples from clamped or resampled series.
- **FR-005**: Before running statistical stationarity, surrogate transfer entropy, and orthogonality proofs in the dashboard, the pipeline MUST enforce a minimum sample floor of `35` bars; if fewer than `35` bars are returned and synthetic fallback is not active, the dashboard MUST halt proof execution and display an inline recovery callout (`"Insufficient history: {symbol} only has {n_bars} bars on {timeframe} (minimum 35 required for indicator & stationarity proofs). Switch to 1W or 1D."`) instead of misleading zeroed KPIs.
- **FR-006**: When `35 <= n_bars < requested_bars` (partial/clamped history on higher timeframes such as `1M` or `3M`), the pipeline MUST execute on all `n_bars` available bars and render a non-blocking amber notice badge (`"Using all {n_bars} available {timeframe} bars for {symbol} (requested {requested_bars})."`) adjacent to the pipeline completion banner.
- **FR-007**: The primary financial canvas (`SPEC-CHART-TV-01`) MUST serialize `1D`, `1W`, `1M`, and `3M` bar timestamps as unique ascending `YYYY-MM-DD` date strings and intraday (`15m`, `1h`, `4h`) bar timestamps as strictly increasing integer UTC epoch seconds, ensuring valid X-axis rendering across all providers and pandas timestamp resolutions.
- **FR-008**: The primary financial canvas MUST map non-finite (`NaN`/`Inf`) indicator warm-up values to time-aligned whitespace entries (`{"time": bar_time}`) rather than `0.0` or `null`, invoke automatic viewport fitting (`fitContent()`), respond dynamically to container resizing, and render a live top-left OHLCV + indicator crosshair hover legend.
- **FR-009**: If zero valid candlestick points are available or the client chart library fails to mount, the primary financial canvas MUST display an inline diagnostic state card inside the `420px` container rather than leaving an empty plot grid; the canvas wrapper MUST also include `role="img"` and a dynamic `aria-label` summarizing symbol, timeframe, bar count, date range, and latest close price, plus touch scroll protection (`vertTouchDrag: false`) on mobile/tablet viewports.
- **FR-010**: The Research Controls sidebar `Timeframe` selector MUST support `["15m", "1h", "4h", "1D", "1W", "1M", "3M"]` with `1D` selected by default, paired with a synchronized quick-switcher control (`1D`, `1W`, `1M`, `3M`) above the Quadrant 1 primary financial chart and URL query-parameter synchronization (`provider`, `symbol`, `tf`).
- **FR-011**: Changing the timeframe from either the sidebar selector or the Q1 quick-switcher MUST invalidate stale cached bundles for previous timeframes, recompute the full 4-quadrant bundle, and display the canonical timeframe label across status banners and parameter context pills.
- **FR-012**: Every diagnostic chart across Tabs `Q1` (`TV-01`, `Q1A`, `Q1B`), `Q2` (`Q2A`, `Q2B`), and `Q3` (`Q3A`, `Q3B`, `Q3C`), as well as the `Q4` Neuro-Symbolic Studio (`Q4A`), MUST be preceded by a standardized header bar displaying the panel title on the left and an anchored `?` Help popover trigger on the right (`SPEC-UI-HELP-03`).
- **FR-013**: A centralized `CHART_HELP_REGISTRY` MUST provide structured 3-part educational microcopy (**1. What It Is**, **2. Axes & Visuals**, **3. How to Interpret**) plus dynamic active-parameter/threshold context for all 9 panel IDs (`TV-01`, `Q1A`, `Q1B`, `Q2A`, `Q2B`, `Q3A`, `Q3B`, `Q3C`, `Q4A`), with a safe fallback entry if an unknown chart ID is queried.
- **FR-014**: Subplot figures (`Q1A`, `Q1B`, `Q2A`, `Q2B`, `Q3A`, `Q3B`, `Q3C`) MUST remove redundant top-level figure titles (now rendered in the standardized header bar) and adjust top margins and horizontal legend placement so interactive chart toolbars and legends never overlap subplot headings.
- **FR-015**: Regime distribution histograms (`Q3B`) MUST pair color fills with distinct border strokes/patterns so Bull / Low-Vol and Bear / High-Vol distributions remain visually distinguishable under color-vision deficiency, and dark-mode visual tokens MUST remain consistent regardless of browser light/dark preference.

### Key Entities

- **`TimeframeSpec`**: Canonical timeframe descriptor mapping canonical label (`15m`, `1h`, `4h`, `1D`, `1W`, `1M`, `3M`) and lowercase aliases (`1d`, `1wk`, `1mo`, `3mo`) to provider interval tokens, lookback periods, calendar vs. intraday serialization mode (`business_day` vs. `unix_seconds`), synthetic frequency, and default/recommended bar bounds.
- **`OHLCVDataset` (Extended Metadata)**: Validated Point-in-Time OHLCV dataset enriched with canonical `timeframe` label, `requested_bars`, `is_clamped` flag, `resampled_from` source interval (when aggregated), calendar date strings (`YYYY-MM-DD`), and UTC Unix timestamps.
- **`ChartHelpEntry`**: Immutable help specification (`chart_id`, `title`, `what_it_is`, `axes_and_visuals`, `how_to_interpret`, `thresholds_note`) stored in `CHART_HELP_REGISTRY` with safe fallback lookup and dynamic runtime context formatting.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of supported market data providers and timeframes (`15m`, `1h`, `4h`, `1D`, `1W`, `1M`, `3M`) produce non-empty, chronologically ordered candlestick and indicator series on the primary financial chart whenever at least 1 valid bar exists, with zero blank-canvas failures on valid symbol histories.
- **SC-002**: 100% of leading indicator warm-up `NaN` values render as non-distorting whitespace gaps rather than artificial `0.0` spikes, keeping indicator Y-axis bounds accurate to within the true finite range of the indicator.
- **SC-003**: Researchers can switch between `1D`, `1W`, `1M`, and `3M` in 1 click via the Q1 quick-switcher (or 2 clicks via the sidebar selector), with 100% state parity between sidebar controls, quick-switcher pills, status badges, and URL query parameters.
- **SC-004**: 100% of higher-timeframe requests returning partial history (`35 <= available < requested` bars) complete without error and display an accurate clamped-history bar count notice, while 100% of requests with `< 35` bars surface a clear, non-crashing insufficient-history recovery message.
- **SC-005**: 100% of the 8 diagnostic charts across Tabs `Q1`–`Q3` and the `Q4` Studio header expose a keyboard-accessible `?` help popover containing all 3 explanation sections (`What It Is`, `Axes & Visuals`, `How to Interpret`) with zero visual overlap between chart titles, legends, and hover toolbars.

## Assumptions

- When running in interactive dashboard mode with an external provider (`yfinance` or `ccxt`) selected by the user, explicit insufficient-history (`< 35` bars) or empty-ticker states should be surfaced clearly to the researcher rather than silently masking ticker typos with synthetic Ornstein-Uhlenbeck data, whereas programmatic/CLI callers using `fallback_to_synthetic=True` retain existing offline resilience when network access is unavailable.
- Synthetic stochastic benchmarks (`SYNTH:COUPLED_OU`, `SYNTH:WHITE_NOISE`) support all canonical timeframes (`15m`, `1h`, `4h`, `1D`, `1W`, `1M`, `3M`) deterministically using matching calendar/intraday timestamp spacing so offline tests and headless self-checks (`quantlab dashboard --check`) verify every timeframe without network calls.
