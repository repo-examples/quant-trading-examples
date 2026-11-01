# Contract: TradingView Lightweight Charts HTML5 Canvas & PIT Timestamp Extraction

## 1. Python API Contract (`quantlab.data.loader` & `quantlab.dashboard.app`)

```python
def extract_unix_timestamps(index: pd.DatetimeIndex) -> np.ndarray:
    """Convert any pandas DatetimeIndex (s, ms, us, ns, tz-naive or tz-aware) to strictly increasing UTC Unix epoch seconds (int64)."""

def build_lightweight_charts_canvas_html(
    dataset: OHLCVDataset,
    proof: ProofSuiteResult,
    overlay: bool = False,
    height: int = 420,
) -> str:
    """Build an interactive HTML5 TradingView Lightweight Charts v4.2.0 canvas with OHLCV candlesticks and indicator line series."""
```

## 2. Behavioral Invariants

1. **Resolution Independence**: Given identical calendar timestamps stored as `datetime64[s, UTC]`, `datetime64[ms, UTC]`, `datetime64[us, UTC]`, or `datetime64[ns, UTC]`, `extract_unix_timestamps(index)` MUST return the exact same `int64` array of Unix epoch seconds.
2. **Strict Monotonicity**: Every adjacent pair of timestamps `(t_0, t_1)` in the `candles` and `ind_points` JSON payloads MUST satisfy `t_0 < t_1`.
3. **Finite Serialization**: Neither `candles` nor `ind_points` may contain `NaN`, `Infinity`, or `-Infinity` tokens in the serialized JSON.
4. **Responsive Layout**: The Lightweight Charts configuration MUST include `autoSize: true` (or `ResizeObserver` fallback) so the canvas fills its container width when switching Streamlit tabs or providers.
