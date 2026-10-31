"""Dual Neuro-Symbolic Indicator Registry & Custom SymPy Time-Series AST Primitives."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import numpy as np
import pandas as pd
import sympy as sp

if TYPE_CHECKING:
    pass

# Canonical Symbolic Time-Series Variables
OPEN = sp.Symbol("open", real=True)
HIGH = sp.Symbol("high", real=True)
LOW = sp.Symbol("low", real=True)
CLOSE = sp.Symbol("close", real=True)
VOLUME = sp.Symbol("volume", real=True)
HL2 = sp.Symbol("hl2", real=True)
HLC3 = sp.Symbol("hlc3", real=True)
OHLC4 = sp.Symbol("ohlc4", real=True)
BAR_INDEX = sp.Symbol("bar_index", integer=True, nonnegative=True)


# Custom Symbolic Time-Series AST Function Nodes
class Lag(sp.Function):
    """Causal lag operator: Lag(x, k) represents x_{t-k} (Pine v6: nz(x[k], x))."""

    nargs = (2,)


class Change(sp.Function):
    """Causal finite difference: Change(x, k) = x_t - x_{t-k} (Pine v6: ta.change(x, k))."""

    nargs = (1, 2)


class SMA(sp.Function):
    """Causal Simple Moving Average over window n (Pine v6: ta.sma(x, n))."""

    nargs = (2,)


class EMA(sp.Function):
    """Causal Exponential Moving Average over window n (Pine v6: ta.ema(x, n))."""

    nargs = (2,)


class RMA(sp.Function):
    """Causal Wilder's Moving Average over window n (Pine v6: ta.rma(x, n))."""

    nargs = (2,)


class WMA(sp.Function):
    """Causal Weighted Moving Average over window n (Pine v6: ta.wma(x, n))."""

    nargs = (2,)


class Stdev(sp.Function):
    """Causal Rolling Standard Deviation over window n (Pine v6: ta.stdev(x, n))."""

    nargs = (2,)


class Highest(sp.Function):
    """Causal Rolling Maximum over window n (Pine v6: ta.highest(x, n))."""

    nargs = (2,)


class Lowest(sp.Function):
    """Causal Rolling Minimum over window n (Pine v6: ta.lowest(x, n))."""

    nargs = (2,)


class TrueRange(sp.Function):
    """Causal True Range (Pine v6: ta.tr(true))."""

    nargs = (0, 3)


class Nz(sp.Function):
    """Null/NaN coalescing operator (Pine v6: nz(x, fallback))."""

    nargs = (1, 2)


class RollingEntropy(sp.Function):
    """Causal Rolling Shannon Entropy over window n and bins b."""

    nargs = (3,)


@dataclass(frozen=True)
class SymbolicRecurrence:
    """Represents a causal recursive state variable `var float <state_name> = <init_expr>`."""

    state_name: str
    init_expr: sp.Expr | float | int
    update_expr: sp.Expr
    is_Temporary: bool = False
    description: str = ""


@dataclass(frozen=True)
class OHLCVInputs:
    """Point-in-Time aligned 1D float64 OHLCV arrays for indicator evaluation."""

    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray

    def __post_init__(self) -> None:
        n = len(self.close)
        for name, arr in (
            ("open", self.open),
            ("high", self.high),
            ("low", self.low),
            ("close", self.close),
            ("volume", self.volume),
        ):
            if arr.ndim != 1 or len(arr) != n:
                raise ValueError(f"OHLCVInputs.{name} must be 1D array of length {n}, got {arr.shape}")

    @property
    def length(self) -> int:
        return int(len(self.close))

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> OHLCVInputs:
        required = ("open", "high", "low", "close", "volume")
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"DataFrame missing required OHLCV columns: {missing}")
        return cls(
            open=np.ascontiguousarray(df["open"].to_numpy(dtype=np.float64)),
            high=np.ascontiguousarray(df["high"].to_numpy(dtype=np.float64)),
            low=np.ascontiguousarray(df["low"].to_numpy(dtype=np.float64)),
            close=np.ascontiguousarray(df["close"].to_numpy(dtype=np.float64)),
            volume=np.ascontiguousarray(df["volume"].to_numpy(dtype=np.float64)),
        )

    def slice_to(self, end_bar: int) -> OHLCVInputs:
        """Return causal prefix [0:end_bar] for zero-lookahead verification."""
        return OHLCVInputs(
            open=np.ascontiguousarray(self.open[:end_bar].copy()),
            high=np.ascontiguousarray(self.high[:end_bar].copy()),
            low=np.ascontiguousarray(self.low[:end_bar].copy()),
            close=np.ascontiguousarray(self.close[:end_bar].copy()),
            volume=np.ascontiguousarray(self.volume[:end_bar].copy()),
        )


IndicatorCategory = Literal["baseline", "physics", "custom"]


@dataclass(frozen=True)
class IndicatorSpec:
    """Dual Neuro-Symbolic specification for a technical or physics-inspired indicator."""

    name: str
    title: str
    category: IndicatorCategory
    description: str
    default_params: dict[str, int | float]
    compute_fn: Callable[[OHLCVInputs, dict[str, int | float]], np.ndarray]
    symbolic_fn: Callable[[dict[str, int | float]], sp.Expr]
    recurrences_fn: Callable[[dict[str, int | float]], tuple[SymbolicRecurrence, ...]] | None = None
    overlay: bool = False
    param_descriptions: dict[str, str] = field(default_factory=dict)

    def resolve_params(self, overrides: dict[str, int | float] | None = None) -> dict[str, int | float]:
        merged: dict[str, int | float] = dict(self.default_params)
        if overrides:
            for k, v in overrides.items():
                if k in merged:
                    default_val = merged[k]
                    merged[k] = int(v) if isinstance(default_val, int) and not isinstance(default_val, bool) else float(v)
                else:
                    merged[k] = v
        return merged

    def evaluate(
        self,
        data: OHLCVInputs | pd.DataFrame,
        **override_params: int | float,
    ) -> np.ndarray:
        """Evaluate the numerical indicator kernel causally on OHLCV data."""
        inputs = OHLCVInputs.from_dataframe(data) if isinstance(data, pd.DataFrame) else data
        params = self.resolve_params(override_params)
        result = self.compute_fn(inputs, params)
        return np.asarray(result, dtype=np.float64)

    def symbolic_ast(self, **override_params: int | float) -> sp.Expr:
        """Return the canonical SymPy symbolic AST for this indicator."""
        params = self.resolve_params(override_params)
        return self.symbolic_fn(params)

    def state_recurrences(self, **override_params: int | float) -> tuple[SymbolicRecurrence, ...]:
        """Return symbolic state recurrence steps if the indicator uses stateful IIR/Kalman memory."""
        if self.recurrences_fn is None:
            return ()
        params = self.resolve_params(override_params)
        return self.recurrences_fn(params)


class IndicatorRegistry:
    """Central registry for dual neuro-symbolic indicators."""

    def __init__(self) -> None:
        self._specs: dict[str, IndicatorSpec] = {}
        self._lookup_lower: dict[str, str] = {}

    def register(self, spec: IndicatorSpec) -> IndicatorSpec:
        self._specs[spec.name] = spec
        self._lookup_lower[spec.name.lower()] = spec.name
        return spec

    def get(self, name: str) -> IndicatorSpec:
        key = name.strip()
        if key in self._specs:
            return self._specs[key]
        canonical = self._lookup_lower.get(key.lower())
        if canonical is not None:
            return self._specs[canonical]
        available = ", ".join(sorted(self._specs.keys()))
        raise KeyError(f"Unknown indicator '{name}'. Available indicators: [{available}]")

    def list_all(self, category: IndicatorCategory | Literal["all"] = "all") -> list[IndicatorSpec]:
        specs = list(self._specs.values())
        if category == "all":
            return specs
        return [s for s in specs if s.category == category]

    def names(self) -> list[str]:
        return list(self._specs.keys())


REGISTRY = IndicatorRegistry()
_BOOTSTRAPPED = False


def get_registry() -> IndicatorRegistry:
    """Return the global IndicatorRegistry with all baseline and physics indicators loaded."""
    global _BOOTSTRAPPED
    if not _BOOTSTRAPPED:
        from quantlab.indicators import baselines, custom_examples  # noqa: F401

        _BOOTSTRAPPED = True
    return REGISTRY


SYMBOLIC_NAMESPACE: dict[str, object] = {
    "open": OPEN,
    "high": HIGH,
    "low": LOW,
    "close": CLOSE,
    "volume": VOLUME,
    "hl2": HL2,
    "hlc3": HLC3,
    "ohlc4": OHLC4,
    "bar_index": BAR_INDEX,
    "Lag": Lag,
    "Change": Change,
    "SMA": SMA,
    "EMA": EMA,
    "RMA": RMA,
    "WMA": WMA,
    "Stdev": Stdev,
    "Highest": Highest,
    "Lowest": Lowest,
    "TrueRange": TrueRange,
    "Nz": Nz,
    "RollingEntropy": RollingEntropy,
    "Abs": sp.Abs,
    "Max": sp.Max,
    "Min": sp.Min,
    "log": sp.log,
    "sqrt": sp.sqrt,
    "exp": sp.exp,
    "sin": sp.sin,
    "cos": sp.cos,
    "tanh": sp.tanh,
    "Piecewise": sp.Piecewise,
}


def parse_symbolic_expression(
    expr_str: str,
    params: dict[str, int | float] | None = None,
) -> sp.Expr:
    """Safely parse a string formula into a QuantLab SymPy AST expression."""
    local_dict = dict(SYMBOLIC_NAMESPACE)
    if params:
        for k in params:
            local_dict[k] = sp.Symbol(k, real=True)
    try:
        parsed = sp.sympify(expr_str, locals=local_dict, evaluate=False)
    except Exception as exc:
        raise ValueError(f"Failed to parse symbolic expression '{expr_str}': {exc}") from exc
    if not isinstance(parsed, sp.Expr):
        raise ValueError(f"Parsed object '{expr_str}' is not a valid SymPy Expr: {type(parsed)}")
    return parsed
