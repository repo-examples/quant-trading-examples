# Quickstart & Validation Guide: Chart UX, Multi-Timeframe Controls & Contextual Help

## Prerequisites

- Python 3.11+ with `uv` installed.
- Sync workspace dependencies:
  ```powershell
  uv sync --all-extras
  ```

## 1. Verify Multi-Timeframe PIT Data Fetching (`1D`, `1W`, `1M`, `3M`)

Run deterministic synthetic and external provider fetches across the new higher timeframes:

```powershell
# Weekly, Monthly, and Quarterly deterministic synthetic benchmarks
uv run quantlab fetch --provider synthetic --symbol SYNTH:COUPLED_OU --timeframe 1W --bars 400 --fracdiff
uv run quantlab fetch --provider synthetic --symbol SYNTH:COUPLED_OU --timeframe 1M --bars 240 --fracdiff
uv run quantlab fetch --provider synthetic --symbol SYNTH:COUPLED_OU --timeframe 3M --bars 120 --fracdiff

# Yahoo Finance higher-timeframe fetch (auto-clamps when requested > available, e.g., SPY 3M)
uv run quantlab fetch --provider yfinance --symbol SPY --timeframe 3M --bars 600 --fracdiff
```

**Expected Outcome**:
- Uppercase canonical timeframe labels (`1W`, `1M`, `3M`) resolve cleanly (`1wk`, `1mo`, `3mo` on `yfinance` with `period="max"`).
- `OHLCVDataset` enforces monotonic Point-in-Time timestamps and reports clamped/resampled metadata when applicable.

## 2. Verify Headless Dashboard & Self-Check (`SPEC-CHART-TV-01`, `SPEC-CTRL-TF-02`, `SPEC-UI-HELP-03`)

```powershell
uv run quantlab dashboard --check
```

**Expected Outcome**:
- Exits with code `0` and prints JSON summary verifying:
  - `status: "ok"`
  - `loading_spec_id: "SPEC-QUANT-LOAD-01"`
  - `chart_tv_spec_id: "SPEC-CHART-TV-01"`
  - `timeframe_spec_id: "SPEC-CTRL-TF-02"`
  - `chart_help_spec_id: "SPEC-UI-HELP-03"`
  - `chart_help_entries_verified: 9`
  - Validated `YYYY-MM-DD` Lightweight Charts calendar serialization and `CHART_HELP_REGISTRY` coverage across Q1–Q4.

## 3. Launch Interactive 4-Quadrant Dashboard

```powershell
uv run quantlab dashboard
```

**Interactive Verification Checklist**:
1. Switch `Market Data Provider` to `yfinance` (`SPY`) and verify the **TradingView Lightweight Charts HTML5 Canvas** in Tab Q1 paints OHLC candlesticks, active indicator trace, chronological X-axis dates, and top-left hover legend (`SPEC-CHART-TV-01`).
2. Switch timeframes between `1D`, `1W`, `1M`, and `3M` using either the left sidebar `Timeframe` selector or the synced quick-switcher pill bar above the Q1 chart (`SPEC-CTRL-TF-02`); confirm `SPY` on `3M` (`600` requested bars) displays the amber clamped-history notice pill (`Using all ... available 3M bars for SPY`).
3. Click the right-aligned `?` Help popover trigger on every chart header across Tabs `Q1` (`TV-01`, `Q1A`, `Q1B`), `Q2` (`Q2A`, `Q2B`), `Q3` (`Q3A`, `Q3B`, `Q3C`), and `Q4` (`Q4A`), confirming 3-part explanations open without shifting layout and Plotly modebars/legends do not collide with titles (`SPEC-UI-HELP-03`).

## 4. Run Full Test & Lint Suite

```powershell
uv run pytest -v
uv run ruff check src tests
```
