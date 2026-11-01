# Phase 1 Data Model: Fix TradingView Lightweight Charts Rendering Across Market Data Providers

## Entities

### 1. `OHLCVDataset` (`src/quantlab/data/loader.py`)

Validated Point-in-Time (PIT) OHLCV time-series dataset.

| Field / Property | Type | Invariants & Validation |
|---|---|---|
| `symbol` | `str` | Non-empty market ticker or synthetic process identifier |
| `provider` | `DataProvider` (`"yfinance" \| "ccxt" \| "synthetic"`) | Source provider identifier |
| `timeframe` | `str` | Bar interval (`"1d"`, `"4h"`, `"1h"`, `"15m"`, `"5m"`, `"1m"`) |
| `df` | `pd.DataFrame` | UTC `DatetimeIndex` (monotonic increasing, unique), columns `open`, `high`, `low`, `close`, `volume` (`float64`, finite) |
| `unix_timestamps` | `np.ndarray` (`int64`) | 1D array of UTC Unix epoch seconds extracted via resolution-agnostic `.as_unit("s").astype("int64")`, strictly increasing (`ts[i] > ts[i-1]`) |

### 2. `LightweightChartsPayload` (`src/quantlab/dashboard/app.py`)

Serialized JSON structures embedded in the HTML5 TradingView Lightweight Charts canvas.

| Series | Element Schema | Constraints |
|---|---|---|
| `candles` | `{"time": int, "open": float, "high": float, "low": float, "close": float}` | `len(candles) == dataset.n_bars`; `time` in UTC epoch seconds (`> 946684800` for modern dates); strictly ascending (`candles[i]["time"] > candles[i-1]["time"]`); all OHLC values finite floats |
| `ind_points` | `{"time": int, "value": float}` | `len(ind_points) == dataset.n_bars`; `time` aligned 1:1 with `candles`; `value` sanitized with `np.nan_to_num(..., nan=0.0, posinf=0.0, neginf=0.0)` |
