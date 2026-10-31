# Phase 0 Research: QuantLab Information-Theoretic Indicator Research CLI, Transpiler & Diagnostic Dashboard

## 1. Fixed-Width Window Fractional Differentiation (FracDiff) & ADF Stationarity
- **Decision**: Implement Marcos López de Prado's Fixed-Width Window Fractional Differentiation (FFD) using causal binomial series weights $w_0 = 1, w_k = -w_{k-1} \frac{d - k + 1}{k}$ truncated when $|w_k| < \tau$ (default $\tau = 10^{-4}$, capped at `max_window = 256`). Couple with Augmented Dickey-Fuller (ADF) regression with AIC/fixed lag selection (via `scipy` / self-contained OLS t-statistic with MacKinnon approximate $p$-value and optional `statsmodels.tsa.stattools.adfuller` integration).
- **Rationale**: Standard integer differentiation ($d = 1$, log returns) erases long-memory trend information. FFD applies an invariant causal finite impulse response (FIR) filter across all bars $t \ge l^*$, guaranteeing zero lookahead bias while finding the minimum $d^* \in [0.0, 1.0]$ that achieves $p_{\text{ADF}} < 0.05$ and preserves high Pearson/Spearman correlation with original log-prices.
- **Alternatives Considered**: Expanding-window fractional differentiation (rejected due to non-constant weight drift and heavy $O(N^2)$ tail cost).

## 2. Dual Neuro-Symbolic Indicator Registry & Custom SymPy AST Operators
- **Decision**: Define custom `sympy.Function` subclasses (`Lag(x, n)`, `SMA(x, n)`, `EMA(x, n)`, `RMA(x, n)`, `WMA(x, n)`, `Stdev(x, n)`, `Highest(x, n)`, `Lowest(x, n)`, `Change(x, n)`, `TrueRange(h, l, c)`, `Recurrence(init, step_expr, state_name)`) alongside standard `sympy` algebraic (`Add`, `Mul`, `Pow`, `Abs`, `log`, `sqrt`, `Max`, `Min`, `Piecewise`) nodes. Every `IndicatorSpec` in `quantlab.indicators.registry` registers both a `@numba.njit` (with pure-NumPy fallback) numerical kernel and a symbolic `sympy.Expr` factory.
- **Rationale**: Pure algebraic SymPy trees cannot natively express recursive infinite-impulse-response (IIR) filters like EMA, Wilder's RMA, KAMA's adaptive smoothing, or 1D Kalman state-space recurrences. Explicit symbolic time-series operator nodes preserve exact mathematical semantics, allow symbolic inspection/LaTeX rendering, and map 1-to-1 to TradingView Pine Script v6 (`ta.ema`, `ta.rma`, `ta.stdev`, or `var float state = ...` recurrences).
- **Alternatives Considered**: String-template Pine Script generation (rejected because it violates neuro-symbolic separation and cannot transpile arbitrary user-composed SymPy expressions in Quadrant 4).

## 3. Information-Theoretic Proofs & Monte Carlo Surrogate Testing
- **Decision**: Implement three complementary causal estimators in `quantlab.proofs.entropy`:
  1. **Shannon & Permutation Entropy**: Quantile-binned plug-in + Miller-Madow bias correction and Bandt-Pompe ordinal pattern permutation entropy in `@numba.njit`.
  2. **Mutual Information $I(X_t; R_{t+h})$**: Both equifrequency quantile-contingency MI and Kraskov-Stögbauer-Grassberger (KSG-1) k-NN digamma estimator using `scipy.spatial.cKDTree` + `scipy.special.digamma`.
  3. **Causal Transfer Entropy $TE(X \to Y)$**: Conditioning on target history $Y_t^{(k)}$, computed via Symbolic Transfer Entropy (ordinal pattern state transitions in `@numba.njit`) and conditional k-NN / quantile-binned CMI $I(Y_{t+h}; X_t^{(l)} \mid Y_t^{(k)})$.
  4. **Surrogate Hypothesis Gate**: Iterative Amplitude Adjusted Fourier Transform (IAAFT) preserving both exact amplitude distribution and power spectrum of $X_t$, plus circular block-shuffle surrogates, computing empirical one-sided $p\text{-value} = \frac{1 + \#\{TE_{\text{surr}} \ge TE_{\text{obs}}\}}{1 + M}$.
- **Rationale**: Raw Transfer Entropy on finite noisy financial series exhibits positive finite-sample bias. Comparing against IAAFT and block-shuffled surrogates isolates genuine nonlinear/directed temporal coupling beyond autocorrelation and marginal distribution artifacts.
- **Alternatives Considered**: Gaussian Granger causality only (rejected because it misses nonlinear tail and regime dependencies).

## 4. Statistical Orthogonality & DSP Phase-Smoothness Frontier
- **Decision**:
  - `quantlab.proofs.stats_gate`: Compute Spearman Rank IC across horizons $h \in \{1, 5, 10, 20\}$ with Newey-West / Student-$t$ significance, 1-Wasserstein distance (`scipy.stats.wasserstein_distance`) between normalized indicator distributions conditioned on bull vs. bear realized volatility/return regimes, and Variance Inflation Factor $\text{VIF}_j = \frac{1}{1 - R_j^2}$ (via regularized OLS / QR decomposition) against the 5 standard baselines.
  - `quantlab.proofs.dsp`: Compute the analytic signal $z_t = \tilde{x}_t + i \mathcal{H}\{\tilde{x}_t\}$ via `scipy.signal.hilbert` (and causal windowed FIR Hilbert approximation for point-in-time instantaneous phase), extract unwrapped instantaneous phase lag $\Delta \phi$ (in radians and equivalent bars) relative to band-passed log-price, compute frequency response Bode magnitude/phase curves, and evaluate 3rd-order discrete Jerk energy $J = \frac{1}{N-3}\sum_{t=3}^{N-1} (\Delta^3 \hat{x}_t)^2$. Identify Pareto-optimal indicators on the $(\text{Phase Lag}, \text{Jerk})$ frontier.
- **Rationale**: Retail technical indicators trade lag for smoothness along a suboptimal curve. Measuring instantaneous Hilbert phase lag against 3rd-derivative Jerk exposes whether a physics filter (e.g., Kalman kinematic estimator) Pareto-dominates traditional moving averages.
- **Alternatives Considered**: Cross-correlation peak lag only (rejected because cross-correlation conflates amplitude distortion with phase delay across frequencies).

## 5. SymPy-to-Pine Script v6 Transpiler & 4-Quadrant Dashboard
- **Decision**:
  - `quantlab.transpiler.pine_v6`: Recursive AST visitor translating `sympy.Expr` + `IndicatorSpec` into `//@version=6` syntax (`indicator("...", overlay=...)`, `input.int`/`input.float`, `ta.*` built-ins, `var float` state recurrences, `nz()`, and `plot()`), plus a Markdown Research Card generator embedding LaTeX equations, proof gate tables, and Pine Script v6 code.
  - `quantlab.dashboard.app`: Multi-tab / 4-Quadrant dark-mode Streamlit dashboard integrating `lightweight-charts` (`streamlit_lightweight_charts` / HTML5 TradingView Lightweight Charts component with Plotly fallback) and `plotly.graph_objects` for 3D Takens phase-space attractors, surrogate histograms, Bode plots, and live SymPy-to-Pine v6 transpilation.
- **Rationale**: Fulfils the exact specification in Section 1 of the prompt (`streamlit` + `plotly` + `lightweight-charts-python`) and allows immediate launch via `quantlab dashboard`.
- **Alternatives Considered**: Standalone React SPA (rejected in favor of integrated Python CLI + Streamlit workflow).
