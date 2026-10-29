# Interface Contracts: QuantLab CLI & SymPy-to-Pine Script v6 Transpiler

## 1. CLI Contract (`quantlab`)

Entrypoint registered in `pyproject.toml`:
```toml
[project.scripts]
quantlab = "quantlab.cli:app"
```

### Subcommands

#### `quantlab fetch`
Fetches OHLCV data, validates Point-in-Time alignment, caches to Parquet, and optionally runs FracDiff stationarity analysis.
- `--symbol TEXT` (default: `"SYNTH:COUPLED_OU"` or ticker e.g. `"SPY"`, `"BTC/USDT"`)
- `--provider [yfinance|ccxt|synthetic]` (default: `"synthetic"`)
- `--timeframe TEXT` (default: `"1d"`)
- `--bars INTEGER` (default: `1000`)
- `--seed INTEGER` (default: `42`)
- `--fracdiff / --no-fracdiff` (default: `--fracdiff`)

#### `quantlab indicators`
Lists all registered baseline and physics-inspired indicators with their category, default parameters, symbolic AST expression, and overlay mode.
- `--category [all|baseline|physics]` (default: `"all"`)

#### `quantlab evaluate` (Alias: `quantlab prove`)
Executes the full Information-Theoretic, Statistical, and DSP Proof Suite for one or all registered indicators on the specified dataset.
- `--indicator TEXT` (default: `"all"`, or specific name e.g. `"KalmanFilter"`, `"EntropyFlow"`, `"RSI"`)
- `--symbol TEXT` (default: `"SYNTH:COUPLED_OU"`)
- `--provider [yfinance|ccxt|synthetic]` (default: `"synthetic"`)
- `--bars INTEGER` (default: `1000`)
- `--surrogates INTEGER` (default: `50`)
- `--surrogate-method [iaaft|block_shuffle]` (default: `"iaaft"`)
- `--seed INTEGER` (default: `42`)
- `--json-out PATH` (optional JSON export of scorecard)

#### `quantlab transpile`
Compiles a registered indicator or custom SymPy formula into TradingView Pine Script v6 (`//@version=6`) and optionally generates a Markdown Research Card.
- `--indicator TEXT` (default: `"KalmanFilter"`)
- `--expr TEXT` (optional custom symbolic expression, e.g. `"( close - EMA(close, length) ) / Stdev(close, length)"`)
- `--out-pine PATH` (optional output `.pine` file path)
- `--out-card PATH` (optional output `.md` Research Card file path)
- `--evaluate-card / --no-evaluate-card` (default: `--evaluate-card` — runs proof suite and embeds metrics into the Research Card)

#### `quantlab dashboard`
Launches the 4-Quadrant Interactive Quant Diagnostic Dashboard (`streamlit run src/quantlab/dashboard/app.py`).
- `--port INTEGER` (default: `8501`)
- `--headless / --no-headless` (default: `--no-headless`)
- `--check` (runs a self-test of all 4 dashboard quadrants in headless validation mode and exits `0`)

---

## 2. Symbolic AST to Pine Script v6 Translation Grammar (`pine_v6.py`)

| Symbolic `sympy.Expr` Node | Pine Script v6 (`//@version=6`) Output |
|---|---|
| `Symbol("close")`, `Symbol("open")`, `Symbol("high")`, `Symbol("low")`, `Symbol("volume")`, `Symbol("hl2")`, `Symbol("hlc3")` | `close`, `open`, `high`, `low`, `volume`, `hl2`, `hlc3` |
| Parameter `Symbol("period")` in `params` | `int period = input.int(14, "period", minval=1)` / `float alpha = input.float(...)` |
| `Lag(x, n)` | `nz(x[n], x)` |
| `Change(x, n)` | `ta.change(x, n)` |
| `SMA(x, n)` | `ta.sma(x, n)` |
| `EMA(x, n)` | `ta.ema(x, n)` |
| `RMA(x, n)` | `ta.rma(x, n)` |
| `WMA(x, n)` | `ta.wma(x, n)` |
| `Stdev(x, n)` | `ta.stdev(x, n)` |
| `Highest(x, n)` | `ta.highest(x, n)` |
| `Lowest(x, n)` | `ta.lowest(x, n)` |
| `TrueRange()` | `ta.tr(true)` |
| `Abs(x)`, `log(x)`, `sqrt(x)`, `exp(x)`, `Max(a, b)`, `Min(a, b)` | `math.abs(x)`, `math.log(x)`, `math.sqrt(x)`, `math.exp(x)`, `math.max(a, b)`, `math.min(a, b)` |
| `Piecewise((expr1, cond1), (expr2, True))` | `(cond1 ? expr1 : expr2)` |
| `Recurrence(state_var, init_expr, update_expr)` | `var float state_var = init_expr` + `state_var := update_expr` |
