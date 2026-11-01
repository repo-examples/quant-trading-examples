# Feature Specification: Fix TradingView Lightweight Charts Rendering Across Market Data Providers

**Feature Branch**: `feat/002-fix-tradingview-chart-yfinance`

**Created**: 2026-11-01

**Status**: Draft

**Input**: User description: "when I change to yfinance the chart in trading view dissapears. Let's fit it"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Render TradingView Lightweight Charts Canvas for `yfinance` and `ccxt` Datasets (Priority: P1)

When a quantitative researcher switches the Market Data Provider in the QuantLab Diagnostic Dashboard from `synthetic` to `yfinance` (e.g., `SPY` on `1d`, `4h`, `1h`, or `15m` timeframes) or `ccxt` (e.g., `BTC/USDT`), the Quadrant 1 TradingView Lightweight Charts HTML5 Canvas must render the full historical candlestick series, the active indicator line series, and the horizontal time axis labels without disappearing or collapsing into duplicate timestamps.

**Why this priority**: This directly resolves the primary user-reported defect where selecting `yfinance` causes the TradingView Lightweight Charts HTML5 canvas to go blank (showing only Y-axis price badges with no candlesticks, no indicator curve, and no X-axis time scale labels).

**Independent Test**: Can be independently tested by loading a `yfinance` dataset (`SPY`, `1d`, `600` bars) and verifying that the generated TradingView Lightweight Charts payload contains 600 strictly ascending, unique Unix epoch second timestamps matching the true historical dates and renders both candlestick and indicator series.

**Acceptance Scenarios**:

1. **Given** the QuantLab dashboard is open and the user selects `yfinance` as the Market Data Provider with symbol `SPY` and timeframe `1d`, **When** Quadrant 1 (`Q1: OHLCV Canvas & 3D Phase-Space`) renders, **Then** the TradingView Lightweight Charts HTML5 Canvas displays all `N` OHLCV candlesticks, the active indicator line trace, and formatted calendar dates along the bottom time scale.
2. **Given** any dataset whose underlying timestamp index uses second (`s`), millisecond (`ms`), microsecond (`us`), or nanosecond (`ns`) resolution, **When** the TradingView chart data payload is constructed, **Then** every bar timestamp is converted to exact UTC Unix epoch seconds with strictly increasing ordering (`t[i] > t[i-1]`) and zero duplicate timestamps.
3. **Given** the user switches between non-overlay indicators (e.g., `KalmanFilter`, `RSI`, `EntropyFlow`) and overlay indicators (e.g., `EMA`, `KAMA`) on a `yfinance` dataset, **When** the TradingView canvas updates, **Then** both the candlestick series (right price scale) and indicator series (left or right price scale) remain visible and properly scaled.

---

### User Story 2 - Seamless Provider & Timeframe Switching in Research Controls Sidebar (Priority: P2)

When a researcher switches between `synthetic`, `yfinance`, and `ccxt` providers or selects any supported dashboard timeframe (`1d`, `4h`, `1h`, `15m`), the symbol input and data loader must cleanly transition to the selected provider's default symbol (unless overridden for that provider) and support all four dashboard timeframes without silent timestamp corruption or stale symbol state.

**Why this priority**: Prevents secondary failure modes when switching providers or selecting the `4h` timeframe with `yfinance` in the Research Controls sidebar.

**Independent Test**: Can be independently tested by switching providers (`synthetic` -> `yfinance` -> `ccxt`) and selecting each timeframe (`1d`, `4h`, `1h`, `15m`), confirming that valid Point-in-Time OHLCV bars and strictly increasing Unix epoch second timestamps are produced for every combination.

**Acceptance Scenarios**:

1. **Given** the user switches Market Data Provider from `synthetic` to `yfinance`, **When** the sidebar updates, **Then** the symbol input defaults cleanly to `SPY` (without retaining a stale `SYNTH:` prefix) and fetches/loads the `yfinance` dataset.
2. **Given** `yfinance` is selected as the Market Data Provider and the user selects timeframe `4h`, **When** data is fetched, **Then** the loader retrieves intraday data and resamples/normalizes it to valid 4-hour Point-in-Time OHLCV bars (or falls back cleanly when offline) with strictly ascending UTC timestamps.

---

### Edge Cases

- **Multi-resolution DatetimeIndex (`s`, `ms`, `us`, `ns`)**: Parquet caches and data providers (`yfinance` returning `datetime64[ms, UTC]` or `datetime64[s, UTC]`, `ccxt` returning `datetime64[ms, UTC]`, `synthetic` returning `datetime64[us, UTC]`) must all produce identical Unix epoch second semantics without integer division truncation (`// 10**9` on non-nanosecond indices).
- **Intraday timeframes (`15m`, `1h`, `4h`)**: Consecutive bars separated by 900 to 14,400 seconds must remain strictly distinct in Unix epoch seconds rather than collapsing to identical values.
- **Duplicate or non-finite indicator values**: Any `NaN` or `Inf` values in an indicator series must be sanitized so the JSON payload passed to TradingView Lightweight Charts contains only valid finite JSON numbers.
- **Container resizing inside tabbed layout**: The TradingView chart container must automatically size itself to the available width of the Quadrant 1 tab.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST convert `OHLCVDataset` timestamps to UTC Unix epoch seconds accurately across all timestamp resolutions (`s`, `ms`, `us`, `ns`) so that 100% of bars in `yfinance`, `ccxt`, and `synthetic` datasets map to their true historical epoch second values.
- **FR-002**: System MUST guarantee strictly ascending, duplicate-free `time` values in the candlestick and indicator data arrays passed to the TradingView Lightweight Charts canvas.
- **FR-003**: System MUST sanitize any non-finite values (`NaN`, `Inf`, `-Inf`) in candlestick and indicator series before serializing to the TradingView chart payload and enable responsive chart auto-sizing within the dashboard layout.
- **FR-004**: System MUST support all dashboard-selectable timeframes (`1d`, `4h`, `1h`, `15m`) for `yfinance` (including `1h`-to-`4h` OHLCV aggregation when `4h` is requested) while preserving Point-in-Time causal invariants.
- **FR-005**: System MUST isolate or reset the sidebar symbol input per provider in the dashboard so switching between `synthetic`, `yfinance`, and `ccxt` automatically populates the appropriate default symbol (`SYNTH:COUPLED_OU`, `SPY`, `BTC/USDT`).

### Key Entities

- **OHLCVDataset**: Point-in-Time validated market dataset containing UTC `DatetimeIndex` and `open`, `high`, `low`, `close`, `volume` columns, extended with resolution-independent Unix epoch second extraction.
- **TradingView Canvas Payload**: Serialized candlestick (`{time, open, high, low, close}`) and indicator (`{time, value}`) series consumed by Lightweight Charts in Quadrant 1.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of bars in `yfinance`, `ccxt`, and `synthetic` datasets across `1d`, `4h`, `1h`, and `15m` timeframes produce unique, strictly increasing Unix epoch second timestamps (`len(set(timestamps)) == len(timestamps)` and `all(a < b for a, b in pairwise(timestamps))`).
- **SC-002**: Selecting `yfinance` (`SPY`, `1d`, `600` bars) in the dashboard renders all 600 candlesticks and 600 indicator points in the TradingView Lightweight Charts canvas with visible calendar dates (2024–2026) on the time axis.
- **SC-003**: Automated regression tests verify Unix timestamp extraction and TradingView HTML canvas generation across `datetime64[s, UTC]`, `datetime64[ms, UTC]`, `datetime64[us, UTC]`, and `datetime64[ns, UTC]` indices with zero failures.

## Assumptions

- TradingView Lightweight Charts v4.2.0 accepts UTC Unix timestamp integers in seconds (`UTCTimestamp`) in strictly ascending order.
- Existing cached Parquet files in `.cache/parquet/` may contain `datetime64[ms, UTC]` or `datetime64[us, UTC]` indices and must work seamlessly without requiring manual cache deletion by the user.
