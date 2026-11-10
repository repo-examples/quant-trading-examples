# Phase 0 Research: QuantLab Chart UX, Multi-Timeframe Controls & Contextual Help

## R-01: Root Cause of Blank TradingView Lightweight Charts Canvas under `yfinance` (`SPEC-CHART-TV-01`)

- **Decision**:
  1. Flatten `MultiIndex` columns in `_fetch_yfinance` (`if isinstance(raw.columns, pd.MultiIndex): raw.columns = raw.columns.get_level_values(0)`).
  2. Serialize daily and higher timeframes (`1D`, `1W`, `1M`, `3M`) as unique, strictly ascending `YYYY-MM-DD` business-day strings (`df.index.tz_convert("UTC").strftime("%Y-%m-%d")` deduplicated with `keep="last"`), and serialize intraday timeframes (`5m`, `15m`, `1h`, `4h`, `1m`) as strictly increasing UTC Unix epoch seconds via `.as_unit("s").astype("int64")` (never dividing non-nanosecond `DatetimeIndex` by `10**9`).
  3. Sanitize non-finite OHLCV rows, map non-finite (`NaN`/`Inf`) indicator warm-up values to Lightweight Charts whitespace objects (`{"time": bar_time}`) instead of `0.0`, attach `autoSize: true` + `ResizeObserver` + `chart.timeScale().fitContent()`, render a live top-left crosshair OHLCV + indicator legend, and show an explicit inline empty/error state card inside the `420px` wrapper if `len(candles) == 0` or the Lightweight Charts script fails to mount.
- **Rationale**:
  In `pandas >= 2.2 / 3.1` + `yfinance >= 1.x`, `DatetimeIndex` uses `datetime64[s, tz]` rather than `datetime64[ns, tz]`. The legacy `(df.index.astype("int64") // 10**9)` expression divided epoch seconds (`~1.7e9`) by `10**9`, collapsing every bar's timestamp to `1` and causing `candleSeries.setData(...)` in Lightweight Charts to throw an ascending-time assertion failure after mounting price scale tags. Furthermore, `YYYY-MM-DD` strings natively eliminate weekend/timezone drift on `1D`/`1W`/`1M`/`3M` bars in Lightweight Charts, while whitespace objects (`{"time": t}`) prevent warm-up `NaN` values from either crashing `JSON.parse` or pulling the left indicator Y-axis to an artificial `0.0` spike.
- **Alternatives Considered**:
  - *Coercing all timeframes to Unix integer seconds*: Rejected for `1D`/`1W`/`1M`/`3M` because UTC midnight offsets on exchange-localized `yfinance` bars (`America/New_York`) can shift displayed calendar dates by 1 day and `SPEC-CHART-TV-01` explicitly specifies `YYYY-MM-DD` strings for daily/weekly/monthly/quarterly bars and UTC Unix seconds for intraday bars.
  - *Replacing indicator `NaN` values with `0.0`*: Rejected because indicators whose range is far from zero (e.g., `EMA` at `550.0` or `RSI` around `50.0`) get severe Y-axis compression if warm-up bars are plotted at `0.0`.

## R-02: Canonical Multi-Timeframe Mapping, Resampling & Sample Floor (`SPEC-CTRL-TF-02`)

- **Decision**:
  Introduce an immutable `TimeframeSpec` registry (`TIMEFRAME_MAP` / `TIMEFRAME_SPECS`) supporting canonical UI timeframes `("15m", "1h", "4h", "1D", "1W", "1M", "3M")` (default `"1D"`) plus backwards-compatible lowercase CLI/test aliases (`"1d" -> "1D"`, `"1w"/"1wk" -> "1W"`, `"1mo" -> "1M"`, `"3m"/"3mo" -> "3M"`, `"5m"`, and legacy lowercase `"1m"` kept distinct as 1-minute intraday so `"1M"` is strictly 1-Month `1mo`).
  - For `yfinance`: map `"1D" -> ("1d", "max")`, `"1W" -> ("1wk", "max")`, `"1M" -> ("1mo", "max")`, `"3M" -> ("3mo", "max")`, `"4h" -> ("1h", "730d", resample="4h")`, `"1h" -> ("1h", "730d")`, `"15m" -> ("15m", "60d")`.
  - For `ccxt`: pass native `"15m"`, `"1h"`, `"4h"`, `"1d"`, `"1w"`, `"1M"` when supported by the exchange; for `"3M"` (or whenever an exchange lacks `"1M"`/`"3M"`), fetch `"1d"` (or `"1M"`) history and causally resample (`open=first`, `high=max`, `low=min`, `close=last`, `volume=sum`) using calendar quarter/month boundaries, recording `resampled_from="1D"` on `OHLCVDataset`.
  - For `synthetic`: support all canonical intervals deterministically (`15m`, `1h`, `4h`, `1D`, `1W`, `1M`, `3M`) via pandas frequency offsets (`"15min"`, `"1h"`, `"4h"`, `"1D"`, `"1W-FRI"`, `"MS"`, `"QS"`).
  - Enforce `MIN_PROOF_BARS = 35` in the dashboard pipeline (`InsufficientHistoryError`), surfacing a clean inline guidance callout when `n_bars < 35`, and surfacing a non-blocking amber clamped-history pill when `35 <= n_bars < requested_bars`.
- **Rationale**:
  Passing raw `"1w"` or `"3m"` to `yfinance` raises invalid-interval errors, and passing lowercase `"1m"` fetches 7-day 1-minute bars instead of monthly bars (`"1mo"`). Meanwhile, `SPY` (inception 1993) only has ~135 quarterly (`3M`) bars and ~405 monthly (`1M`) bars; `find_min_ffd_d` requires `>= 32` bars, `knn_transfer_entropy` requires `>= 24` bars, and `MACD(12, 26, 9)` requires `~35` bars to stabilize. Setting `MIN_PROOF_BARS = 35` guarantees numerical stability across all 4 proof gates while allowing `SPY` `3M` (~135 bars) to execute smoothly with an amber availability notice.
- **Alternatives Considered**:
  - *Forcing `bars >= 200` on all timeframes*: Rejected because virtually no modern ETF or equity has 200 quarterly bars (50 years of trading history), which would break `3M` analysis on `SPY`, `QQQ`, and `BTC`.
  - *Silently substituting synthetic data when `yfinance` returns `< 35` bars in the UI*: Rejected by stakeholder clarification in favor of an explicit guarded inline error callout so researchers never confuse synthetic OU series with real market tickers.

## R-03: Bidirectional Sidebar + Q1 Quick-Switcher & Query-Param Sync (`SPEC-CTRL-TF-02`)

- **Decision**:
  Maintain canonical timeframe state in `st.session_state["ql_timeframe"]` (seeded from `st.query_params.get("tf", "1D")` validated via `normalize_timeframe`), bind both the sidebar `Timeframe` selectbox (`["15m", "1h", "4h", "1D", "1W", "1M", "3M"]`) and a Q1 quick-switcher (`st.pills` / segmented button bar for `["1D", "1W", "1M", "3M"]`) via `on_change` callbacks updating `st.session_state["ql_timeframe"]` and syncing `st.query_params` (`provider`, `symbol`, `tf`).
- **Rationale**:
  Streamlit 1.66+ natively provides `st.pills` and `st.query_params`. Driving both widgets from a single canonical `st.session_state["ql_timeframe"]` source prevents widget-key race conditions, keeps the active quadrant view consistent, and allows one-click switching between `1D`, `1W`, `1M`, and `3M` directly above the TradingView canvas.
- **Alternatives Considered**:
  - *Independent sidebar and chart-local timeframe states*: Rejected because letting the TradingView chart diverge from the Q1–Q4 statistical proofs would violate Point-in-Time single-dataset consistency across quadrants.

## R-04: Standardized Chart Card Header, `st.popover("?")` & Plotly Collision Elimination (`SPEC-UI-HELP-03`)

- **Decision**:
  Create a dedicated `src/quantlab/dashboard/chart_help.py` module housing `ChartHelpEntry`, `CHART_HELP_REGISTRY` (covering all 8 charts `TV-01`, `Q1A`, `Q1B`, `Q2A`, `Q2B`, `Q3A`, `Q3B`, `Q3C` plus `Q4A` for the SymPy AST & Pine Script v6 Studio), graceful fallback lookup `get_chart_help(...)`, HTML microcopy formatting, and a reusable `render_chart_header(st, chart_id, title_override=..., context=..., badge_text=...)` component using `st.columns([0.92, 0.08], vertical_alignment="center")` + `st.popover("?", help=...)`.
  Simultaneously update `_apply_dark_theme` in `src/quantlab/dashboard/app.py` to support headerless figure layout (`title=None`, `margin={"t": 44, "r": 20, "l": 48, "b": 40}`, horizontal legend `x=0.0, xanchor="left", y=1.08, yanchor="bottom"`) so Plotly's top-right hover modebar and subplot titles never collide, and add distinct border strokes/pattern styling on `Q3B` Bull vs. Bear regime histograms for color-vision accessibility alongside `.streamlit/config.toml` dark-theme lock.
- **Rationale**:
  `st.popover` in Streamlit 1.66 renders an anchored floating overlay with native `Escape` and click-outside dismissal, zero vertical page layout shift, and full keyboard accessibility. Moving the primary chart title out of the Plotly SVG canvas into the native flex header row alongside `[ ? ]` permanently eliminates the title/legend/modebar overlap observed on `Q3A`.
- **Alternatives Considered**:
  - *Floating HTML `?` button positioned absolutely inside Plotly/iframe containers*: Rejected because absolute-positioned overlays collide with Lightweight Charts' right price axis (`64px`) and Plotly's interactive zoom/export modebar.
  - *`st.expander` inline accordions*: Rejected by stakeholder clarification because expanding an accordion pushes charts downward and disrupts side-by-side 2-column alignment (`Q1A`/`Q1B`, `Q2A`/`Q2B`, `Q3A`/`Q3B`).
