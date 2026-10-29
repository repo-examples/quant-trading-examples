"""Standard Technical Analysis Baseline Indicators (RSI, EMA, ATR, MACD, KAMA) with Numba + SymPy ASTs."""

from __future__ import annotations

import numba
import numpy as np
import sympy as sp

from quantlab.indicators.registry import (
    CLOSE,
    EMA,
    HIGH,
    LOW,
    REGISTRY,
    RMA,
    Change,
    IndicatorSpec,
    Lag,
    Nz,
    OHLCVInputs,
    SymbolicRecurrence,
    TrueRange,
)


@numba.njit(cache=True)
def _ema_kernel(series: np.ndarray, period: int) -> np.ndarray:
    n = len(series)
    out = np.empty(n, dtype=np.float64)
    if n == 0:
        return out
    alpha = 2.0 / (float(max(1, period)) + 1.0)
    out[0] = series[0]
    for t in range(1, n):
        out[t] = alpha * series[t] + (1.0 - alpha) * out[t - 1]
    return out


@numba.njit(cache=True)
def _rma_kernel(series: np.ndarray, period: int) -> np.ndarray:
    n = len(series)
    out = np.empty(n, dtype=np.float64)
    if n == 0:
        return out
    alpha = 1.0 / float(max(1, period))
    out[0] = series[0]
    for t in range(1, n):
        out[t] = alpha * series[t] + (1.0 - alpha) * out[t - 1]
    return out


@numba.njit(cache=True)
def _rsi_kernel(close: np.ndarray, period: int) -> np.ndarray:
    n = len(close)
    out = np.empty(n, dtype=np.float64)
    if n == 0:
        return out
    out[0] = 50.0
    alpha = 1.0 / float(max(1, period))
    avg_gain = 0.0
    avg_loss = 0.0
    for t in range(1, n):
        delta = close[t] - close[t - 1]
        gain = delta if delta > 0.0 else 0.0
        loss = -delta if delta < 0.0 else 0.0
        if t == 1:
            avg_gain = gain
            avg_loss = loss
        else:
            avg_gain = alpha * gain + (1.0 - alpha) * avg_gain
            avg_loss = alpha * loss + (1.0 - alpha) * avg_loss
        denom = avg_gain + avg_loss
        if denom < 1e-15:
            out[t] = 50.0
        else:
            out[t] = 100.0 * (avg_gain / denom)
    return out


@numba.njit(cache=True)
def _atr_kernel(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    n = len(close)
    tr = np.empty(n, dtype=np.float64)
    if n == 0:
        return tr
    tr[0] = high[0] - low[0]
    for t in range(1, n):
        hl = high[t] - low[t]
        hc = abs(high[t] - close[t - 1])
        lc = abs(low[t] - close[t - 1])
        tr[t] = max(hl, max(hc, lc))
    return _rma_kernel(tr, period)


@numba.njit(cache=True)
def _macd_hist_kernel(close: np.ndarray, fast_period: int, slow_period: int, signal_period: int) -> np.ndarray:
    fast_ema = _ema_kernel(close, fast_period)
    slow_ema = _ema_kernel(close, slow_period)
    macd_line = fast_ema - slow_ema
    signal_line = _ema_kernel(macd_line, signal_period)
    return macd_line - signal_line


@numba.njit(cache=True)
def _kama_kernel(close: np.ndarray, er_period: int, fast_period: int, slow_period: int) -> np.ndarray:
    n = len(close)
    out = np.empty(n, dtype=np.float64)
    if n == 0:
        return out
    fast_sc = 2.0 / (float(max(1, fast_period)) + 1.0)
    slow_sc = 2.0 / (float(max(2, slow_period)) + 1.0)
    p = max(1, er_period)
    out[0] = close[0]
    for t in range(1, n):
        lookback = t if t < p else p
        direction = abs(close[t] - close[t - lookback])
        volatility = 0.0
        for k in range(t - lookback + 1, t + 1):
            volatility += abs(close[k] - close[k - 1])
        er = direction / volatility if volatility > 1e-15 else 0.0
        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
        out[t] = out[t - 1] + sc * (close[t] - out[t - 1])
    return out


# 1. RSI
def _compute_rsi(inputs: OHLCVInputs, params: dict[str, int | float]) -> np.ndarray:
    return _rsi_kernel(inputs.close, int(params["period"]))


def _symbolic_rsi(params: dict[str, int | float]) -> sp.Expr:
    period = sp.Symbol("period", integer=True, positive=True)
    delta = Change(CLOSE, 1)
    gain = sp.Max(delta, sp.Float(0.0))
    loss = sp.Max(-delta, sp.Float(0.0))
    avg_gain = RMA(gain, period)
    avg_loss = RMA(loss, period)
    return sp.Float(100.0) * avg_gain / sp.Max(avg_gain + avg_loss, sp.Float(1e-12))


RSI_SPEC = REGISTRY.register(
    IndicatorSpec(
        name="RSI",
        title="Wilder Relative Strength Index",
        category="baseline",
        description="Normalized Wilder RMA ratio of upward to total price velocity over period N.",
        default_params={"period": 14},
        compute_fn=_compute_rsi,
        symbolic_fn=_symbolic_rsi,
        overlay=False,
        param_descriptions={"period": "Wilder smoothing lookback length"},
    )
)


# 2. EMA
def _compute_ema(inputs: OHLCVInputs, params: dict[str, int | float]) -> np.ndarray:
    return _ema_kernel(inputs.close, int(params["period"]))


def _symbolic_ema(params: dict[str, int | float]) -> sp.Expr:
    period = sp.Symbol("period", integer=True, positive=True)
    return EMA(CLOSE, period)


EMA_SPEC = REGISTRY.register(
    IndicatorSpec(
        name="EMA",
        title="Exponential Moving Average",
        category="baseline",
        description="First-order causal IIR low-pass filter with smoothing factor alpha = 2 / (N + 1).",
        default_params={"period": 20},
        compute_fn=_compute_ema,
        symbolic_fn=_symbolic_ema,
        overlay=True,
        param_descriptions={"period": "EMA span in bars"},
    )
)


# 3. ATR
def _compute_atr(inputs: OHLCVInputs, params: dict[str, int | float]) -> np.ndarray:
    return _atr_kernel(inputs.high, inputs.low, inputs.close, int(params["period"]))


def _symbolic_atr(params: dict[str, int | float]) -> sp.Expr:
    period = sp.Symbol("period", integer=True, positive=True)
    return RMA(TrueRange(HIGH, LOW, CLOSE), period)


ATR_SPEC = REGISTRY.register(
    IndicatorSpec(
        name="ATR",
        title="Average True Range",
        category="baseline",
        description="Wilder RMA of True Range capturing gap-adjusted intrabar volatility.",
        default_params={"period": 14},
        compute_fn=_compute_atr,
        symbolic_fn=_symbolic_atr,
        overlay=False,
        param_descriptions={"period": "ATR smoothing period"},
    )
)


# 4. MACD (Histogram / Oscillator)
def _compute_macd(inputs: OHLCVInputs, params: dict[str, int | float]) -> np.ndarray:
    return _macd_hist_kernel(
        inputs.close,
        int(params["fast_period"]),
        int(params["slow_period"]),
        int(params["signal_period"]),
    )


def _symbolic_macd(params: dict[str, int | float]) -> sp.Expr:
    fast_p = sp.Symbol("fast_period", integer=True, positive=True)
    slow_p = sp.Symbol("slow_period", integer=True, positive=True)
    sig_p = sp.Symbol("signal_period", integer=True, positive=True)
    macd_line = EMA(CLOSE, fast_p) - EMA(CLOSE, slow_p)
    return macd_line - EMA(macd_line, sig_p)


MACD_SPEC = REGISTRY.register(
    IndicatorSpec(
        name="MACD",
        title="MACD Histogram Band-Pass Oscillator",
        category="baseline",
        description="Difference between dual-EMA band-pass MACD line and its EMA signal line.",
        default_params={"fast_period": 12, "slow_period": 26, "signal_period": 9},
        compute_fn=_compute_macd,
        symbolic_fn=_symbolic_macd,
        overlay=False,
        param_descriptions={
            "fast_period": "Fast EMA period",
            "slow_period": "Slow EMA period",
            "signal_period": "Signal EMA period",
        },
    )
)


# 5. KAMA (Kaufman Adaptive Moving Average)
def _compute_kama(inputs: OHLCVInputs, params: dict[str, int | float]) -> np.ndarray:
    return _kama_kernel(
        inputs.close,
        int(params["er_period"]),
        int(params["fast_period"]),
        int(params["slow_period"]),
    )


def _symbolic_kama(params: dict[str, int | float]) -> sp.Expr:
    return sp.Symbol("kama_state", real=True)


def _recurrences_kama(params: dict[str, int | float]) -> tuple[SymbolicRecurrence, ...]:
    er_p = sp.Symbol("er_period", integer=True, positive=True)
    fast_p = sp.Symbol("fast_period", integer=True, positive=True)
    slow_p = sp.Symbol("slow_period", integer=True, positive=True)

    direction = sp.Abs(CLOSE - Lag(CLOSE, er_p))
    volatility = sp.Max(er_p * RMA(sp.Abs(Change(CLOSE, 1)), er_p), sp.Float(1e-12))
    er = direction / volatility
    fast_sc = sp.Float(2.0) / (fast_p + sp.Float(1.0))
    slow_sc = sp.Float(2.0) / (slow_p + sp.Float(1.0))
    sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
    prev_kama = Nz(Lag(sp.Symbol("kama_state", real=True), 1), CLOSE)
    update_expr = prev_kama + sc * (CLOSE - prev_kama)

    return (
        SymbolicRecurrence(
            state_name="kama_state",
            init_expr=CLOSE,
            update_expr=update_expr,
            description="Kaufman Efficiency-Ratio adaptive state update",
        ),
    )


KAMA_SPEC = REGISTRY.register(
    IndicatorSpec(
        name="KAMA",
        title="Kaufman Adaptive Moving Average",
        category="baseline",
        description="Nonlinear adaptive low-pass filter scaling bandwidth by Efficiency Ratio (signal/noise).",
        default_params={"er_period": 10, "fast_period": 2, "slow_period": 30},
        compute_fn=_compute_kama,
        symbolic_fn=_symbolic_kama,
        recurrences_fn=_recurrences_kama,
        overlay=True,
        param_descriptions={
            "er_period": "Efficiency Ratio lookback window",
            "fast_period": "Fastest EMA equivalent period",
            "slow_period": "Slowest EMA equivalent period",
        },
    )
)

__all__ = [
    "ATR_SPEC",
    "EMA_SPEC",
    "KAMA_SPEC",
    "MACD_SPEC",
    "RSI_SPEC",
    "_atr_kernel",
    "_ema_kernel",
    "_kama_kernel",
    "_macd_hist_kernel",
    "_rma_kernel",
    "_rsi_kernel",
]
