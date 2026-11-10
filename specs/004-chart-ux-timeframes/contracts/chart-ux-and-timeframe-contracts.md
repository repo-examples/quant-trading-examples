# Phase 1 Interface Contracts: Chart UX, Multi-Timeframe Controls & Contextual Help

## 1. Market Data Loader & Timeframe Contract (`quantlab.data.loader`)

```python
UI_TIMEFRAMES: tuple[str, ...] = ("15m", "1h", "4h", "1D", "1W", "1M", "3M")
HIGHER_TIMEFRAME_PILLS: tuple[str, ...] = ("1D", "1W", "1M", "3M")
MIN_PROOF_BARS: int = 35

def normalize_timeframe(timeframe: str) -> str: ...
def get_timeframe_spec(timeframe: str) -> TimeframeSpec: ...
def extract_unix_timestamps(index: pd.DatetimeIndex) -> np.ndarray: ...
def resample_ohlcv_causal(df: pd.DataFrame, rule: str) -> pd.DataFrame: ...
```

- **yfinance Contract**:
  - Flattens `pd.MultiIndex` columns (`raw.columns.get_level_values(0)`) before renaming `Open/High/Low/Close/Volume`.
  - Uses `period="max"` for `1D` (`1d`), `1W` (`1wk`), `1M` (`1mo`), and `3M` (`3mo`), slicing `.iloc[-bars:]` only after sorting and deduplicating timestamps.
- **Clamped & Resampled Contract**:
  - `OHLCVDataset.requested_bars` records requested `bars`.
  - `OHLCVDataset.is_clamped` is `True` iff `requested_bars is not None and n_bars < requested_bars`.
  - `OHLCVDataset.resampled_from` records source timeframe (e.g., `"1D"` when `3M` is aggregated on `ccxt`, or `"1h"` when `4h` is aggregated on `yfinance`).
- **Minimum Sample Guard**:
  - `validate_minimum_proof_bars(dataset: OHLCVDataset, min_bars: int = MIN_PROOF_BARS) -> None` raises `InsufficientHistoryError` when `dataset.n_bars < min_bars`.

## 2. TradingView Lightweight Charts HTML5 Canvas Contract (`SPEC-CHART-TV-01`)

```python
def serialize_lightweight_charts_series(
    dataset: OHLCVDataset,
    indicator_series: np.ndarray,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]: ...

def build_lightweight_charts_canvas_html(
    dataset: OHLCVDataset,
    proof: ProofSuiteResult,
    overlay: bool = False,
    height: int = 420,
) -> str: ...
```

- **Time Serialization**:
  - Calendar intervals (`1D`, `1W`, `1M`, `3M`): `"time"` is a strictly ascending unique `"YYYY-MM-DD"` string.
  - Intraday intervals (`1m`, `5m`, `15m`, `1h`, `4h`): `"time"` is a strictly increasing `int` UTC Unix epoch timestamp in seconds.
- **Indicator Warm-Up Sanitization**:
  - Finite values emit `{"time": t, "value": float(v)}`.
  - Non-finite values (`NaN`, `+Inf`, `-Inf`) emit Lightweight Charts whitespace objects `{"time": t}` (no `"value"` key, never `0.0` or `null`).
- **DOM, Interactions & Accessibility**:
  - Outer wrapper carries `role="img"` and dynamic `aria-label="TradingView OHLCV and {indicator} chart for {symbol} on {timeframe} timeframe, {n_bars} bars from {start_date} to {end_date}, latest close {last_close:.2f}"`.
  - Dynamic top-left legend `<div id="tv-legend">` updates on `chart.subscribeCrosshairMove(...)` with `{symbol} • {timeframe} • O / H / L / C • {indicator}: {val}`.
  - Responsive layout uses `autoSize: true` + `ResizeObserver`, `handleScroll: { vertTouchDrag: false }` on touch/narrow viewports, `minBarSpacing: 2`, and `chart.timeScale().fitContent()`.
  - If `len(candles) == 0` or `typeof LightweightCharts === 'undefined'`, renders an inline bordered diagnostic state card inside the `420px` container instead of a blank plot.

## 3. Chart Card Header & Contextual Help Popover Contract (`SPEC-UI-HELP-03`)

```python
CHART_HELP_REGISTRY: dict[str, ChartHelpEntry]

def get_chart_help(chart_id: str, indicator_name: str = "Active Indicator") -> ChartHelpEntry: ...
def render_chart_help_popover_html(
    chart_id: str,
    indicator_name: str = "Active Indicator",
    context_summary: str | None = None,
) -> str: ...
def render_chart_header(
    st: object,
    chart_id: str,
    title: str | None = None,
    indicator_name: str = "Active Indicator",
    context_summary: str | None = None,
    badge_text: str | None = None,
    key_suffix: str = "live",
) -> None: ...
```

- **Registered IDs**: `"TV-01"`, `"Q1A"`, `"Q1B"`, `"Q2A"`, `"Q2B"`, `"Q3A"`, `"Q3B"`, `"Q3C"`, `"Q4A"`.
- **Plotly Headerless Collision-Free Layout**:
  - All dashboard Plotly figures (`Q1A`–`Q3C`) omit redundant internal top-level `layout.title.text` when rendered beneath `render_chart_header` (while keeping descriptive `meta["chart_title"]` and subplot titles spaced cleanly with `margin.t >= 48` and horizontal legend above plot at `x=0.0`) so Plotly's top-right hover modebar never overlaps titles or legends.
  - `Q3B` Bull vs. Bear histograms include distinct marker line borders and pattern shapes so regime distributions remain distinguishable under deuteranopia/protanopia.
