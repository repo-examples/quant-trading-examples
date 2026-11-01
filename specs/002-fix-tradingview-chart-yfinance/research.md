# Phase 0 Research: Fix TradingView Lightweight Charts Rendering Across Market Data Providers

## 1. Root Cause Analysis of TradingView Canvas Disappearance on `yfinance`

- **Decision**: Replace `df.index.astype("int64") // 10**9` with resolution-agnostic UTC Unix epoch second extraction (`idx_utc.as_unit("s").astype("int64")`) plus strict monotonicity enforcement.
- **Rationale**:
  - In Pandas 2.x/3.x, `DatetimeIndex.astype("int64")` returns raw integer timestamps in the index's native unit (`s`, `ms`, `us`, or `ns`) rather than always nanoseconds (`ns`).
  - `yfinance` and `ccxt` return `DatetimeIndex` with millisecond resolution (`datetime64[ms, UTC]`), where values are `~1.718e12`. Dividing by `10**9` produces `1718` for ~11.5 consecutive days (`600` daily bars collapse into `76` distinct integers `[1718..1793]` with `524` duplicates).
  - `generate_synthetic_ohlcv` (`pd.date_range`) produces `datetime64[us, UTC]`, where dividing by `10**9` produces `~1,715,472` (Jan 1970) and collapses intraday timeframes (`15m`, `5m`, `1m`) into duplicate timestamps.
  - TradingView Lightweight Charts v4.2.0 (`lightweight-charts.standalone.production.js`) requires strictly ascending `time` values (`t[i] > t[i-1]`). When duplicate timestamps are passed to `candleSeries.setData(...)` and `indSeries.setData(...)`, the internal time-scale binary search corrupts and renders zero candlesticks, zero line segments, and zero X-axis labels while still displaying the last bar's Y-axis price badges (`755.72` and `0.07`).
- **Alternatives Considered**:
  - Formatting timestamps as `"YYYY-MM-DD"` strings: Rejected because Lightweight Charts only supports `"YYYY-MM-DD"` business day strings for daily bars and fails on intraday (`4h`, `1h`, `15m`) timeframes, whereas UTC Unix epoch second integers (`UTCTimestamp`) work uniformly across all daily and intraday timeframes.

## 2. Support for `4h` Timeframe in `yfinance` Loader

- **Decision**: Support `4h` in `_fetch_yfinance` by fetching `1h` bars (`period="730d"` or `"60d"`) and causally aggregating to `4h` OHLCV bars (`open="first"`, `high="max"`, `low="min"`, `close="last"`, `volume="sum"`, dropping empty market-closed bins) when `timeframe == "4h"`.
- **Rationale**: The Streamlit sidebar exposes `["1d", "4h", "1h", "15m"]`, and Yahoo Finance does not natively provide a `4h` interval string in `ticker.history` (or falls back silently to `1d` in `interval_map.get(timeframe, "1d")`). Causal `4h` resampling of `1h` bars preserves Point-in-Time invariants.
- **Alternatives Considered**: Removing `4h` from the dashboard: Rejected because `4h` is a standard quantitative research timeframe already supported by `synthetic` and `ccxt`.

## 3. Sidebar Symbol Input Isolation Across Providers

- **Decision**: Bind the Streamlit symbol `st.text_input` widget with a provider-scoped key (`key=f"symbol_input_{provider}"`) and sanitize cross-provider symbol prefixes in `fetch_ohlcv` when `provider != "synthetic"`.
- **Rationale**: Prevents a previously entered `SYNTH:...` symbol from persisting when the user switches the Market Data Provider dropdown to `yfinance` or `ccxt`.
- **Alternatives Considered**: Manual `st.session_state` callback: `key=f"symbol_input_{provider}"` is cleaner, declarative, and preserves each provider's custom symbol independently during a session.
