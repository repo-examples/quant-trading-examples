# Phase 1 Data Model: QuantLab Chart UX, Multi-Timeframe Controls & Contextual Help

## 1. `TimeframeSpec` & `TIMEFRAME_SPECS` (`src/quantlab/data/loader.py`)

Immutable descriptor decoupling UI timeframe labels and CLI aliases from provider-specific API interval parameters and serialization rules.

| Field | Type | Description |
| :--- | :--- | :--- |
| `label` | `str` | Canonical display label (`"15m"`, `"1h"`, `"4h"`, `"1D"`, `"1W"`, `"1M"`, `"3M"`, plus CLI-supported `"5m"`, `"1m"`). |
| `yf_interval` | `str` | Yahoo Finance interval token (`"15m"`, `"1h"`, `"1h"` for `4h`, `"1d"`, `"1wk"`, `"1mo"`, `"3mo"`). |
| `yf_period` | `str` | Yahoo Finance history lookback (`"max"` for `1D`/`1W`/`1M`/`3M`; `"730d"` for `1h`/`4h`; `"60d"` for `15m`/`5m`; `"7d"` for `1m`). |
| `yf_resample_rule` | `str \| None` | Causal pandas resample rule if `yfinance` requires aggregation (`"4h"` for `4h`, else `None`). |
| `ccxt_timeframe` | `str` | Primary CCXT timeframe request token (`"15m"`, `"1h"`, `"4h"`, `"1d"`, `"1w"`, `"1M"`, or `"1d"` fallback source for `"3M"`). |
| `ccxt_resample_rule` | `str \| None` | Causal pandas resample rule when CCXT lacks native aggregation (`"QS"` for `"3M"`, else `None`). |
| `synthetic_freq` | `str` | Deterministic pandas `date_range` frequency (`"15min"`, `"1h"`, `"4h"`, `"1D"`, `"W-FRI"`, `"MS"`, `"QS"`). |
| `is_calendar_date` | `bool` | `True` for `1D`, `1W`, `1M`, `3M` (serialized as `"YYYY-MM-DD"` in Lightweight Charts); `False` for intraday (serialized as UTC Unix epoch seconds). |
| `default_bars` | `int` | Recommended default bar count (`600` for `1D`/`1h`/`4h`/`15m`, `400` for `1W`, `240` for `1M`, `120` for `3M`). |
| `max_bars` | `int` | Upper reference bound (`2500` for `1D`, `1500` for `1W`, `600` for `1M`, `300` for `3M`, `2000` for intraday). |

### Validation & Normalization Rules
- `UI_TIMEFRAMES: tuple[str, ...] = ("15m", "1h", "4h", "1D", "1W", "1M", "3M")`
- `HIGHER_TIMEFRAME_PILLS: tuple[str, ...] = ("1D", "1W", "1M", "3M")`
- `MIN_PROOF_BARS: int = 35`
- `normalize_timeframe(tf: str) -> str`:
  - Preserves exact `"1m"` as `"1m"` (1-minute CLI/synthetic interval) while mapping `"1M"`, `"1mo"`, `"1MO"` to `"1M"` (1 Month).
  - Maps `"1d"`, `"1D"` -> `"1D"`; `"1w"`, `"1W"`, `"1wk"`, `"1WK"` -> `"1W"`; `"3m"`, `"3M"`, `"3mo"`, `"3MO"` -> `"3M"`; `"4h"`, `"4H"` -> `"4h"`; `"1h"`, `"1H"` -> `"1h"`; `"15m"`, `"15M"` -> `"15m"`; `"5m"`, `"5M"` -> `"5m"`.
  - Raises `ValueError` on unknown timeframe tokens.

---

## 2. `OHLCVDataset` (Extended Immutable Entity in `src/quantlab/data/loader.py`)

Extends the existing `dataclass(frozen=True)` `OHLCVDataset` without breaking existing positional/keyword construction:

| Field / Property | Type | Default / Computed | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | `str` | *(required)* | Ticker or synthetic stochastic identifier. |
| `provider` | `DataProvider` | *(required)* | `"synthetic"`, `"yfinance"`, or `"ccxt"`. |
| `timeframe` | `str` | *(required)* | Canonical or caller-supplied timeframe string. |
| `df` | `pd.DataFrame` | *(required)* | Validated monotonic PIT DataFrame (`open`, `high`, `low`, `close`, `volume`). |
| `cache_path` | `Path \| None` | `None` | Local `.cache/parquet/` path. |
| `requested_bars` | `int \| None` | `None` | Bar count originally requested by the caller (`bars`). |
| `resampled_from` | `str \| None` | `None` | Source interval label when causally aggregated (e.g., `"1D"` -> `"3M"` or `"1h"` -> `"4h"`). |
| `canonical_timeframe` | `str` *(property)* | Computed | Normalized canonical timeframe label via `normalize_timeframe(self.timeframe)`. |
| `is_clamped` | `bool` *(property)* | Computed | `True` when `requested_bars is not None and self.n_bars < requested_bars`. |
| `unix_timestamps` | `np.ndarray` *(property)* | Computed | Strictly increasing `int64` UTC Unix epoch seconds across any `DatetimeIndex` unit (`s`, `ms`, `us`, `ns`). |
| `calendar_dates` | `list[str]` *(property)* | Computed | Timezone-normalized `"YYYY-MM-DD"` strings for calendar timeframes (`1D`, `1W`, `1M`, `3M`). |

---

## 3. `InsufficientHistoryError` (`src/quantlab/data/loader.py`)

Typed `ValueError` subclass raised when a dataset contains fewer than `MIN_PROOF_BARS` (`35`) bars required for causal stationarity, indicator warm-up, and surrogate proofs:
- Attributes: `symbol: str`, `timeframe: str`, `available_bars: int`, `minimum_bars: int = 35`, `indicator_name: str | None = None`.
- Formatted message: `"Insufficient history: {symbol} only has {available_bars} bars on {timeframe} (minimum {minimum_bars} required for indicator & stationarity proofs). Switch to 1W or 1D."` (with optional active indicator context shown in the UI callout).

---

## 4. `ChartHelpEntry` & `CHART_HELP_REGISTRY` (`src/quantlab/dashboard/chart_help.py`)

Immutable specification for per-chart contextual `?` popovers (`SPEC-UI-HELP-03`):

| Field | Type | Description |
| :--- | :--- | :--- |
| `chart_id` | `str` | Canonical identifier (`"TV-01"`, `"Q1A"`, `"Q1B"`, `"Q2A"`, `"Q2B"`, `"Q3A"`, `"Q3B"`, `"Q3C"`, `"Q4A"`). |
| `header_title` | `str` | Standardized left-aligned header title displayed in `ChartHeaderRow`. |
| `what_it_is` | `str` | Block 1: Plain-language summary of what the chart/panel measures. |
| `axes_and_visuals` | `str` | Block 2: Explanation of X/Y/Z axes, panes, colors, and regime strokes. |
| `how_to_interpret` | `str` | Block 3: Quantitative signal interpretation & pass/fail proof thresholds (`d*`, `ADF p < 0.05`, `TE p < 0.05`, `|IC| > 0.02`, `VIF < 5.0`, Pareto dominance). |

### State Transitions (`SPEC-UI-HELP-03`)
1. **Closed (Default)**: Header row renders title + optional badge on the left and compact `?` popover trigger (`Explain this chart`, accessible label) on the right.
2. **Open (Active)**: Clicking/tapping/pressing `Enter` or `Space` on `?` opens anchored popover (`max-width: 380px`, scrollable up to `60vh`) rendering the 3 blocks + live parameter context pill (`{symbol} • {timeframe} • {indicator}`).
3. **Missing Registry Key**: Querying `get_chart_help(unknown_id, indicator_name)` returns a valid fallback `ChartHelpEntry` (`"Quantitative diagnostic chart for {indicator_name}. Detailed guide pending."`) without raising `KeyError`.
