"""Unit and Zero-Lookahead tests for all 8 Baseline and Physics Indicators."""

from __future__ import annotations

import numpy as np
import pytest
import sympy as sp

from quantlab.data.loader import generate_synthetic_ohlcv
from quantlab.indicators.custom_examples import reconstruct_phase_space_3d
from quantlab.indicators.registry import OHLCVInputs, get_registry, parse_symbolic_expression


def test_registry_has_all_8_indicators_and_symbolic_asts() -> None:
    reg = get_registry()
    names = reg.names()
    expected = {
        "RSI",
        "EMA",
        "ATR",
        "MACD",
        "KAMA",
        "KalmanFilter",
        "PhaseSpaceEnergy",
        "EntropyFlow",
    }
    assert expected.issubset(set(names))
    assert len(reg.list_all("baseline")) == 5
    assert len(reg.list_all("physics")) == 3

    for spec in reg.list_all():
        ast = spec.symbolic_ast()
        assert isinstance(ast, sp.Expr)


@pytest.mark.parametrize(
    "indicator_name",
    ["RSI", "EMA", "ATR", "MACD", "KAMA", "KalmanFilter", "PhaseSpaceEnergy", "EntropyFlow"],
)
def test_indicator_strict_zero_lookahead_invariance(indicator_name: str) -> None:
    reg = get_registry()
    spec = reg.get(indicator_name)

    df = generate_synthetic_ohlcv(bars=300, seed=42)
    inputs_full = OHLCVInputs.from_dataframe(df)
    out_full = spec.evaluate(inputs_full)
    assert len(out_full) == 300
    assert np.all(np.isfinite(out_full))

    cutoff = 180
    # Prefix slice test
    inputs_prefix = inputs_full.slice_to(cutoff)
    out_prefix = spec.evaluate(inputs_prefix)
    assert np.max(np.abs(out_full[:cutoff] - out_prefix)) < 1e-12

    # Future mutation test
    mutated_df = df.copy()
    for col in ("open", "high", "low", "close", "volume"):
        mutated_df.iloc[cutoff:, mutated_df.columns.get_loc(col)] *= 25.0
    out_mutated = spec.evaluate(mutated_df)
    assert np.max(np.abs(out_full[:cutoff] - out_mutated[:cutoff])) < 1e-12


def test_constant_series_edge_case_no_nan_or_inf() -> None:
    reg = get_registry()
    n = 120
    const = np.full(n, 100.0, dtype=np.float64)
    inputs = OHLCVInputs(open=const, high=const, low=const, close=const, volume=const)
    for spec in reg.list_all():
        vals = spec.evaluate(inputs)
        assert np.all(np.isfinite(vals)), f"{spec.name} produced non-finite values on constant series"


def test_reconstruct_phase_space_3d_and_symbolic_parser() -> None:
    x = np.linspace(0.0, 10.0, 50)
    x0, x1, x2 = reconstruct_phase_space_3d(x, delay=4)
    assert len(x0) == len(x1) == len(x2) == 50
    assert x1[10] == pytest.approx(x[6])
    assert x2[10] == pytest.approx(x[2])

    expr = parse_symbolic_expression("(close - EMA(close, length)) / Max(Stdev(close, length), 1e-8)", {"length": 20})
    assert isinstance(expr, sp.Expr)
