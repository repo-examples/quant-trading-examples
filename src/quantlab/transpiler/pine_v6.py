"""SymPy AST to TradingView Pine Script v6 Transpiler & Markdown Research Card Generator."""

from __future__ import annotations

from dataclasses import dataclass

import sympy as sp

from quantlab.indicators.registry import (
    EMA,
    RMA,
    SMA,
    WMA,
    Change,
    Highest,
    IndicatorSpec,
    Lag,
    Lowest,
    Nz,
    RollingEntropy,
    Stdev,
    SymbolicRecurrence,
    TrueRange,
    get_registry,
    parse_symbolic_expression,
)
from quantlab.proofs.stats_gate import ProofSuiteResult


class TranspilationError(ValueError):
    """Raised when a SymPy AST contains an unsupported operator or symbol."""


@dataclass(frozen=True)
class TranspilationArtifact:
    """Output of the SymPy-to-Pine Script v6 compiler and Research Card builder."""

    indicator_name: str
    title: str
    sympy_expr: sp.Expr
    latex_expr: str
    pine_code: str
    research_card_md: str


BUILTIN_PINE_SERIES = {
    "open",
    "high",
    "low",
    "close",
    "volume",
    "hl2",
    "hlc3",
    "ohlc4",
    "bar_index",
}

ROLLING_ENTROPY_PINE_HELPER = """// Causal Rolling Shannon Entropy Helper (Pine Script v6)
f_rolling_entropy(series float src, simple int win, simple int bins) =>
    float vmin = ta.lowest(src, win)
    float vmax = ta.highest(src, win)
    float span = vmax - vmin
    float h_out = 0.0
    if span > 1e-12
        array<float> counts = array.new_float(bins, 0.0)
        for k = 0 to win - 1
            float v = nz(src[k], src)
            int b_idx = math.min(bins - 1, math.max(0, int(math.floor(((v - vmin) / span) * float(bins)))))
            array.set(counts, b_idx, array.get(counts, b_idx) + 1.0)
        float inv_n = 1.0 / float(win)
        for j = 0 to bins - 1
            float c = array.get(counts, j)
            if c > 0.0
                float p = c * inv_n
                h_out -= p * math.log(p)
    h_out
"""


class PineV6Transpiler:
    """Recursive AST compiler translating SymPy expressions into TradingView Pine Script v6."""

    def __init__(
        self,
        allowed_symbols: set[str] | None = None,
    ) -> None:
        self.allowed_symbols = set(BUILTIN_PINE_SERIES)
        if allowed_symbols:
            self.allowed_symbols.update(allowed_symbols)
        self.uses_rolling_entropy = False

    def compile_expr(self, expr: sp.Basic) -> str:
        """Recursively compile a SymPy AST node into a Pine Script v6 expression string."""
        if isinstance(expr, sp.Integer):
            return str(int(expr))
        if isinstance(expr, (sp.Float, sp.Rational, sp.Number)):
            val = float(expr)
            if val.is_integer() and abs(val) < 1e9:
                return f"{val:.1f}"
            return f"{val:.8g}"
        if isinstance(expr, sp.Symbol):
            name = expr.name
            if name not in self.allowed_symbols:
                raise TranspilationError(
                    f"Unbound symbol '{name}' in AST. Allowed symbols: {sorted(self.allowed_symbols)}"
                )
            return name

        if isinstance(expr, sp.Add):
            parts: list[str] = []
            for idx, arg in enumerate(expr.args):
                compiled = self.compile_expr(arg)
                if idx == 0:
                    parts.append(compiled)
                elif compiled.startswith("-"):
                    parts.append(f"- {compiled[1:].strip()}")
                else:
                    parts.append(f"+ {compiled}")
            return "(" + " ".join(parts) + ")"

        if isinstance(expr, sp.Mul):
            num_factors: list[str] = []
            den_factors: list[str] = []
            sign_negative = False

            for arg in expr.args:
                if arg == sp.Integer(-1):
                    sign_negative = not sign_negative
                    continue
                if isinstance(arg, sp.Number) and float(arg) < 0:
                    sign_negative = not sign_negative
                    pos_num = -arg
                    if pos_num != sp.Integer(1):
                        num_factors.append(self.compile_expr(pos_num))
                    continue
                if isinstance(arg, sp.Pow) and isinstance(arg.args[1], sp.Number) and float(arg.args[1]) < 0:
                    base, neg_exp = arg.args
                    pos_exp = -neg_exp
                    if pos_exp == sp.Integer(1):
                        den_factors.append(self.compile_expr(base))
                    else:
                        den_factors.append(self.compile_expr(sp.Pow(base, pos_exp, evaluate=False)))
                else:
                    num_factors.append(self.compile_expr(arg))

            num_str = " * ".join(num_factors) if num_factors else "1.0"
            if len(num_factors) > 1:
                num_str = f"({num_str})"
            if den_factors:
                den_str = " * ".join(den_factors)
                if len(den_factors) > 1:
                    den_str = f"({den_str})"
                combined = f"({num_str} / {den_str})"
            else:
                combined = num_str
            return f"-{combined}" if sign_negative else combined

        if isinstance(expr, sp.Pow):
            base, exp = expr.args
            b_str = self.compile_expr(base)
            if exp == sp.Integer(-1):
                return f"(1.0 / {b_str})"
            if exp == sp.Rational(1, 2) or (isinstance(exp, sp.Float) and abs(float(exp) - 0.5) < 1e-12):
                return f"math.sqrt({b_str})"
            if exp == sp.Integer(2):
                return f"math.pow({b_str}, 2.0)"
            e_str = self.compile_expr(exp)
            return f"math.pow({b_str}, {e_str})"

        # Custom QuantLab Time-Series AST Functions
        if isinstance(expr, Lag):
            src, lag_n = expr.args
            src_str = self.compile_expr(src)
            lag_str = self._compile_int_arg(lag_n)
            if isinstance(src, sp.Symbol):
                return f"nz({src_str}[{lag_str}], {src_str})"
            return f"nz(({src_str})[{lag_str}], {src_str})"

        if isinstance(expr, Change):
            if len(expr.args) == 1:
                return f"ta.change({self.compile_expr(expr.args[0])})"
            src, lag_n = expr.args
            return f"ta.change({self.compile_expr(src)}, {self._compile_int_arg(lag_n)})"

        if isinstance(expr, SMA):
            src, win = expr.args
            return f"ta.sma({self.compile_expr(src)}, {self._compile_int_arg(win)})"

        if isinstance(expr, EMA):
            src, win = expr.args
            return f"ta.ema({self.compile_expr(src)}, {self._compile_int_arg(win)})"

        if isinstance(expr, RMA):
            src, win = expr.args
            return f"ta.rma({self.compile_expr(src)}, {self._compile_int_arg(win)})"

        if isinstance(expr, WMA):
            src, win = expr.args
            return f"ta.wma({self.compile_expr(src)}, {self._compile_int_arg(win)})"

        if isinstance(expr, Stdev):
            src, win = expr.args
            return f"ta.stdev({self.compile_expr(src)}, {self._compile_int_arg(win)})"

        if isinstance(expr, Highest):
            src, win = expr.args
            return f"ta.highest({self.compile_expr(src)}, {self._compile_int_arg(win)})"

        if isinstance(expr, Lowest):
            src, win = expr.args
            return f"ta.lowest({self.compile_expr(src)}, {self._compile_int_arg(win)})"

        if isinstance(expr, TrueRange):
            return "ta.tr(true)"

        if isinstance(expr, Nz):
            if len(expr.args) == 1:
                return f"nz({self.compile_expr(expr.args[0])})"
            return f"nz({self.compile_expr(expr.args[0])}, {self.compile_expr(expr.args[1])})"

        if isinstance(expr, RollingEntropy):
            self.uses_rolling_entropy = True
            src, win, bins = expr.args
            return (
                f"f_rolling_entropy({self.compile_expr(src)}, "
                f"{self._compile_int_arg(win)}, {self._compile_int_arg(bins)})"
            )

        # Standard Mathematical Functions
        if isinstance(expr, sp.Abs):
            return f"math.abs({self.compile_expr(expr.args[0])})"
        if isinstance(expr, sp.log):
            return f"math.log({self.compile_expr(expr.args[0])})"
        if isinstance(expr, sp.exp):
            return f"math.exp({self.compile_expr(expr.args[0])})"
        if isinstance(expr, sp.sin):
            return f"math.sin({self.compile_expr(expr.args[0])})"
        if isinstance(expr, sp.cos):
            return f"math.cos({self.compile_expr(expr.args[0])})"
        if isinstance(expr, sp.tanh):
            arg_s = self.compile_expr(expr.args[0])
            return f"((math.exp(2.0 * {arg_s}) - 1.0) / (math.exp(2.0 * {arg_s}) + 1.0))"

        if isinstance(expr, (sp.Max, sp.Min)):
            fn_name = "math.max" if isinstance(expr, sp.Max) else "math.min"
            compiled_args = [self.compile_expr(a) for a in expr.args]
            res = compiled_args[0]
            for nxt in compiled_args[1:]:
                res = f"{fn_name}({res}, {nxt})"
            return res

        if isinstance(expr, sp.Piecewise):
            return self._compile_piecewise(expr)

        # Relational operators
        if isinstance(expr, sp.StrictGreaterThan):
            return f"({self.compile_expr(expr.args[0])} > {self.compile_expr(expr.args[1])})"
        if isinstance(expr, sp.GreaterThan):
            return f"({self.compile_expr(expr.args[0])} >= {self.compile_expr(expr.args[1])})"
        if isinstance(expr, sp.StrictLessThan):
            return f"({self.compile_expr(expr.args[0])} < {self.compile_expr(expr.args[1])})"
        if isinstance(expr, sp.LessThan):
            return f"({self.compile_expr(expr.args[0])} <= {self.compile_expr(expr.args[1])})"
        if isinstance(expr, sp.Equality):
            return f"({self.compile_expr(expr.args[0])} == {self.compile_expr(expr.args[1])})"

        raise TranspilationError(
            f"Unsupported SymPy AST operator '{type(expr).__name__}' in expression '{expr}'"
        )

    def _compile_int_arg(self, node: sp.Basic) -> str:
        if isinstance(node, (sp.Integer, sp.Number)):
            return str(int(round(float(node))))
        return self.compile_expr(node)

    def _compile_piecewise(self, pw: sp.Piecewise) -> str:
        pairs = list(pw.args)
        if not pairs:
            raise TranspilationError("Empty Piecewise node cannot be transpiled")
        # Build right-to-left ternary chain
        last_expr, _ = pairs[-1]
        acc = self.compile_expr(last_expr)
        for val_expr, cond_expr in reversed(pairs[:-1]):
            if cond_expr is sp.true or cond_expr is True:
                acc = self.compile_expr(val_expr)
            else:
                c_str = self.compile_expr(cond_expr)
                v_str = self.compile_expr(val_expr)
                acc = f"({c_str} ? {v_str} : {acc})"
        return acc


def transpile_to_pine_v6(
    spec_or_expr: IndicatorSpec | sp.Expr | str,
    params: dict[str, int | float] | None = None,
    name: str = "CustomIndicator",
    title: str = "QuantLab Custom Symbolic Indicator",
    overlay: bool = False,
    recurrences: tuple[SymbolicRecurrence, ...] = (),
    proof_result: ProofSuiteResult | None = None,
) -> TranspilationArtifact:
    """Compile an IndicatorSpec, SymPy Expr, or formula string into Pine Script v6 + Research Card."""
    if isinstance(spec_or_expr, IndicatorSpec):
        spec = spec_or_expr
        resolved_params = spec.resolve_params(params)
        sym_expr = spec.symbolic_ast(**resolved_params)
        recs = spec.state_recurrences(**resolved_params)
        ind_name = spec.name
        ind_title = spec.title
        ind_overlay = spec.overlay
    elif isinstance(spec_or_expr, str):
        # Check if string is a registered indicator name first
        reg = get_registry()
        try:
            spec = reg.get(spec_or_expr)
            return transpile_to_pine_v6(spec, params=params, proof_result=proof_result)
        except KeyError:
            resolved_params = dict(params or {})
            sym_expr = parse_symbolic_expression(spec_or_expr, params=resolved_params)
            recs = recurrences
            ind_name = name
            ind_title = title
            ind_overlay = overlay
    elif isinstance(spec_or_expr, sp.Expr):
        resolved_params = dict(params or {})
        sym_expr = spec_or_expr
        recs = recurrences
        ind_name = name
        ind_title = title
        ind_overlay = overlay
    else:
        raise TranspilationError(f"Unsupported input type for transpilation: {type(spec_or_expr)}")

    allowed_syms = set(BUILTIN_PINE_SERIES) | set(resolved_params.keys()) | {r.state_name for r in recs}
    transpiler = PineV6Transpiler(allowed_symbols=allowed_syms)

    # Compile recurrences first so helper flags (like RollingEntropy) are detected
    compiled_recurrences: list[tuple[SymbolicRecurrence, str, str]] = []
    for rec in recs:
        init_node = sp.sympify(rec.init_expr)
        init_str = transpiler.compile_expr(init_node)
        upd_str = transpiler.compile_expr(rec.update_expr)
        compiled_recurrences.append((rec, init_str, upd_str))

    signal_expr_str = transpiler.compile_expr(sym_expr)

    lines: list[str] = [
        "//@version=6",
        f"// Generated by QuantLab Neuro-Symbolic Transpiler — {ind_title}",
        f'indicator(title="QuantLab: {ind_title}", shorttitle="QL_{ind_name}", overlay={"true" if ind_overlay else "false"}, precision=4)',
        "",
    ]

    if resolved_params:
        lines.append("// --- Symbolic Model Parameters ---")
        for p_name, p_val in resolved_params.items():
            if isinstance(p_val, int) and not isinstance(p_val, bool):
                lines.append(f'int {p_name} = input.int({p_val}, "{p_name}", minval=1)')
            else:
                lines.append(f'float {p_name} = input.float({float(p_val):.6g}, "{p_name}")')
        lines.append("")

    if transpiler.uses_rolling_entropy:
        lines.append(ROLLING_ENTROPY_PINE_HELPER)

    if compiled_recurrences:
        lines.append("// --- Causal State-Space Recurrences ---")
        for rec, init_str, _ in compiled_recurrences:
            if rec.description:
                lines.append(f"// {rec.description}")
            lines.append(f"var float {rec.state_name} = {init_str}")
        for rec, _, upd_str in compiled_recurrences:
            lines.append(f"{rec.state_name} := {upd_str}")
        lines.append("")

    lines.extend(
        [
            "// --- Symbolic AST Evaluation ---",
            f"float ql_signal = {signal_expr_str}",
            "",
            "// --- Visualization ---",
            f'plot(ql_signal, title="{ind_name}", color=color.new(#00F5D4, 0), linewidth=2)',
        ]
    )
    if not ind_overlay:
        lines.append('hline(0.0, title="Zero Equilibrium", color=color.new(#8892B0, 60), linestyle=hline.style_dashed)')

    pine_code = "\n".join(lines) + "\n"
    latex_str = sp.latex(sym_expr)
    card_md = generate_research_card(
        indicator_name=ind_name,
        title=ind_title,
        sympy_expr=sym_expr,
        latex_expr=latex_str,
        pine_code=pine_code,
        params=resolved_params,
        recurrences=recs,
        proof_result=proof_result,
    )
    return TranspilationArtifact(
        indicator_name=ind_name,
        title=ind_title,
        sympy_expr=sym_expr,
        latex_expr=latex_str,
        pine_code=pine_code,
        research_card_md=card_md,
    )


def generate_research_card(
    indicator_name: str,
    title: str,
    sympy_expr: sp.Expr,
    latex_expr: str,
    pine_code: str,
    params: dict[str, int | float] | None = None,
    recurrences: tuple[SymbolicRecurrence, ...] = (),
    proof_result: ProofSuiteResult | None = None,
) -> str:
    """Render an auditable Markdown Research Card with LaTeX, Proof Gate Scorecard & Pine Script v6."""
    md: list[str] = [
        f"# QuantLab Research Card: {title} (`{indicator_name}`)",
        "",
        "## 1. Symbolic Mathematical Specification",
        "",
        "**Canonical SymPy AST**:",
        f"```text\n{sympy_expr}\n```",
        "",
        "**Closed-Form / Output Equation**:",
        "$$",
        f"\\mathcal{{I}}_t = {latex_expr}",
        "$$",
        "",
    ]

    if recurrences:
        md.append("**Causal State-Space Recurrences**:")
        for rec in recurrences:
            md.append(f"- `{rec.state_name}`: $\\text{{init}} = {sp.latex(sp.sympify(rec.init_expr))}$, update: `$${sp.latex(rec.update_expr)}$$`")
        md.append("")

    if params:
        md.append("**Default Hyperparameters**:")
        for k, v in params.items():
            md.append(f"- `{k}`: `{v}`")
        md.append("")

    if proof_result is not None:
        st = proof_result.stationarity
        en = proof_result.entropy
        sg = proof_result.stats_gate
        dp = proof_result.dsp
        overall_badge = "PASS" if proof_result.overall_passed else "FAIL"

        md.extend(
            [
                f"## 2. Quantitative Proof Suite Scorecard — **{overall_badge}** (Dataset: `{proof_result.symbol}`)",
                "",
                "| Gate / Diagnostic | Metric | Value | Threshold | Status |",
                "| :--- | :--- | :---: | :---: | :---: |",
                f"| **Stationarity (FracDiff + ADF)** | Min $d^*$ / ADF $p$-value | $d^*={st.d_optimal:.2f},\\ p={st.p_value:.4f}$ | $p < 0.05$ | {'PASS' if st.passed else 'FAIL'} |",
                f"| **Memory Preservation** | Corr with Raw Series | ${st.memory_correlation:.4f}$ | Informational | INFO |",
                f"| **Causal Transfer Entropy** | $TE(X \\to R)$ vs Surrogates ({en.surrogate_method}) | $TE={en.symbolic_te:.5f},\\ Z={en.z_score:.2f},\\ p={en.p_value:.4f}$ | $p < 0.05$ | {'PASS' if en.passed else 'FAIL'} |",
                f"| **Mutual Information & Shannon** | $I(X_t; R_{{t+1}})$ / $H(X)$ | $MI={en.mutual_information:.4f},\\ H={en.shannon_entropy:.3f}$ | $MI > 0$ | INFO |",
                f"| **Predictive Rank IC** | Max $|\\text{{Spearman IC}}|$ ($h={sg.best_horizon}$) | ${sg.max_abs_ic:.4f}$ | $|\\text{{IC}}| > {sg.ic_threshold:.2f}$ | {'PASS' if sg.ic_passed else 'FAIL'} |",
                f"| **Regime Separation** | Wasserstein-1 Distance $W_1$ | ${sg.wasserstein_regime_distance:.4f}$ | $W_1 > 0$ | INFO |",
                f"| **Orthogonality (Multicollinearity)** | Baseline VIF | ${sg.vif_score:.2f}$ | $\\text{{VIF}} < {sg.vif_threshold:.1f}$ | {'PASS' if sg.vif_passed else 'FAIL'} |",
                f"| **DSP Phase-Smoothness Frontier** | Hilbert Lag / Jerk Energy | $\\text{{Lag}}={dp.mean_phase_lag_bars:.2f}\\text{{ bars}},\\ J={dp.jerk_energy:.4f}$ | Pareto Frontier | {'PARETO' if dp.pareto_optimal else 'DOMINATED'} |",
                "",
            ]
        )

    md.extend(
        [
            "## 3. TradingView Pine Script v6 Implementation",
            "",
            "```pine",
            pine_code.rstrip(),
            "```",
            "",
        ]
    )
    return "\n".join(md)
