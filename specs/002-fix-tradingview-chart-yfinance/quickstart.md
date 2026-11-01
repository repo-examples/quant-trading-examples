# Quickstart & Verification Guide: Fix TradingView Lightweight Charts Rendering Across Market Data Providers

## Prerequisites

- Python 3.11+ with `uv` installed (`uv sync --all-extras`).

## Verification Scenarios

### 1. Verify Unix Timestamp Extraction Across All Providers & Index Units

```powershell
uv run pytest tests/test_cli_and_dashboard.py tests/test_data_stationarity.py -v
```

### 2. Verify `yfinance` Dashboard Bundle & TradingView Canvas Payload

```powershell
uv run python -c "from quantlab.dashboard.app import build_dashboard_bundle; b = build_dashboard_bundle(symbol='SPY', provider='yfinance', timeframe='1d', bars=600, indicator_name='KalmanFilter', n_surrogates=10, seed=42); assert '1718078400' in b.lightweight_charts_html; print('OK:', b.dataset.n_bars)"
```

### 3. Launch Interactive Streamlit Dashboard

```powershell
uv run quantlab dashboard
```

Switch **Market Data Provider** to `yfinance` (`SPY`, `1d`, `600` bars) and confirm the **TradingView Lightweight Charts HTML5 Canvas** renders all 600 candlesticks, the active indicator trace, and calendar dates on the horizontal time axis.
