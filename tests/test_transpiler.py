"""Unit tests for SymPy-to-Pine Script v6 Transpiler and Markdown Research Card generator."""

from __future__ import annotations

import pytest
import sympy as sp

from quantlab.data.loader import fetch_ohlcv
from quantlab.indicators.registry import get_registry
from quantlab.proofs.stats_gate import run_proof_suite
from quantlab.transpiler.pine_v6 import TranspilationError, transpile_to_pine_v6


@pytest.mark.parametrize(
    "indicator_name",
    ["RSI", "EMA", "ATR", "MACD", "KAMA", "KalmanFilter", "PhaseSpaceEnergy", "EntropyFlow"],
)
def test_transpile_all_registered_indicators_to_pine_v6(indicator_name: str) -> None:
    reg = get_registry()
    spec = reg.get(indicator_name)
    artifact = transpile_to_pine_v6(spec)

    assert artifact.pine_code.startswith("//@version=6")
    assert "indicator(" in artifact.pine_code
    assert "float ql_signal =" in artifact.pine_code
    assert "plot(ql_signal" in artifact.pine_code
    assert artifact.indicator_name == indicator_name
    assert len(artifact.latex_expr) > 0
    assert "## 3. TradingView Pine Script v6 Implementation" in artifact.research_card_md


def test_transpile_custom_symbolic_expression_and_piecewise() -> None:
    expr_str = "Piecewise(((close - EMA(close, length)) / Max(Stdev(close, length), 1e-8), close > open), (0.0, True))"
    artifact = transpile_to_pine_v6(
        expr_str,
        params={"length": 20},
        name="CondZScore",
        title="Conditional Z-Score",
    )
    assert "//@version=6" in artifact.pine_code
    assert 'int length = input.int(20, "length", minval=1)' in artifact.pine_code
    assert "ta.ema(close, length)" in artifact.pine_code
    assert "ta.stdev(close, length)" in artifact.pine_code
    assert "?" in artifact.pine_code


def test_transpile_with_embedded_proof_suite_scorecard() -> None:
    ds = fetch_ohlcv(symbol="SYNTH:COUPLED_OU", provider="synthetic", bars=400, seed=42, use_cache=False)
    spec = get_registry().get("PhaseSpaceEnergy")
    proof = run_proof_suite(spec=spec, dataset=ds, n_surrogates=20, seed=42)
    artifact = transpile_to_pine_v6(spec, proof_result=proof)

    assert "Quantitative Proof Suite Scorecard" in artifact.research_card_md
    assert "Stationarity (FracDiff + ADF)" in artifact.research_card_md
    assert "Causal Transfer Entropy" in artifact.research_card_md
    assert "DSP Phase-Smoothness Frontier" in artifact.research_card_md


def test_transpiler_rejects_unbound_symbol_or_unsupported_function() -> None:
    with pytest.raises(TranspilationError, match="Unbound symbol"):
        transpile_to_pine_v6(sp.Symbol("non_existent_future_price") + 1)

    class UnknownQuantumOp(sp.Function):
        nargs = (1,)

    with pytest.raises(TranspilationError, match="Unsupported SymPy AST operator"):
        transpile_to_pine_v6(UnknownQuantumOp(sp.Symbol("close")))
