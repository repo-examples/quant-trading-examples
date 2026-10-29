# Phase 1 Data Model: QuantLab

## Core Entities & Immutable Value Objects

### 1. `OHLCVDataset` (`src/quantlab/data/loader.py`)
Represents a Point-in-Time (PIT) validated market or synthetic OHLCV dataset.
- `symbol: str` — Ticker or synthetic process identifier (e.g., `"SPY"`, `"BTC/USDT"`, `"SYNTH:COUPLED_OU"`).
- `provider: Literal["yfinance", "ccxt", "synthetic"]` — Data origin.
- `timeframe: str` — Bar interval (e.g., `"1d"`, `"1h"`).
- `df: pd.DataFrame` — Monotonically increasing UTC `DatetimeIndex` with `float64` columns `["open", "high", "low", "close", "volume"]` and optional ground-truth driver column `["driver_signal"]` for synthetic benchmarks.
- `cache_path: Path | None` — Path to the local `.cache/parquet/` file.

**Validation Invariants**:
- Index MUST be strictly monotonic increasing (`df.index.is_monotonic_increasing`) with zero duplicate timestamps.
- `high >= max(open, close)` and `low <= min(open, close)` for all bars.
- Zero `NaN` or `Inf` values in OHLCV columns.

---

### 2. `StationarityResult` (`src/quantlab/data/stationarity.py`)
Encapsulates Fixed-Width Window Fractional Differentiation (FFD) and ADF stationarity analysis.
- `d_optimal: float` — Minimum fractional differentiation order $d^* \in [0.0, 1.0]$ achieving `p_value < alpha`.
- `adf_stat: float` — Augmented Dickey-Fuller test statistic at $d^*$.
- `p_value: float` — MacKinnon approximate $p$-value at $d^*$.
- `critical_values: dict[str, float]` — `{"1%": ..., "5%": ..., "10%": ...}`.
- `memory_correlation: float` — Pearson correlation between causal FFD series at $d^*$ and original log-price series on valid post-warmup indices.
- `weights: np.ndarray` — Causal FFD filter weights $w_0, w_1, \dots, w_{K-1}$.
- `series: np.ndarray` — Resulting 1D `float64` stationary time series aligned to input length (leading warm-up indices padded causally or marked via `warmup_bars`).
- `warmup_bars: int` — Number of initial bars required by the causal filter window.
- `passed: bool` — `True` iff `p_value < alpha` (default `alpha = 0.05`).

---

### 3. `IndicatorSpec` & `IndicatorOutput` (`src/quantlab/indicators/registry.py`)
Defines the dual neuro-symbolic representation of a technical or physics indicator.
- `name: str` — Canonical identifier (`"RSI"`, `"EMA"`, `"ATR"`, `"MACD"`, `"KAMA"`, `"KalmanFilter"`, `"PhaseSpaceEnergy"`, `"EntropyFlow"`).
- `title: str` — Human-readable title.
- `category: Literal["baseline", "physics", "custom"]` — Taxonomy classification.
- `description: str` — Mathematical description of the indicator.
- `default_params: dict[str, int | float]` — Default parameter values (e.g., `{"period": 14}`).
- `overlay: bool` — Whether the indicator plots on the price scale (`True`) or in a separate oscillator pane (`False`).
- `compute_fn: Callable[[OHLCVInputs, dict[str, float]], np.ndarray]` — Vectorized/Numba numerical evaluation kernel.
- `symbolic_fn: Callable[[dict[str, float]], sympy.Expr]` — Symbolic `sympy.Expr` AST builder.
- `state_recurrences: tuple[SymbolicRecurrence, ...]` — Optional recursive state definitions for stateful IIR/Kalman indicators.

---

### 4. `EntropyProofResult` (`src/quantlab/proofs/entropy.py`)
Information-theoretic evaluation of an indicator $X_t$ against future target return $R_{t+h}$.
- `shannon_entropy: float` — Plug-in Miller-Madow corrected Shannon entropy $H(X)$ in nats/bits.
- `permutation_entropy: float` — Normalized Bandt-Pompe ordinal permutation entropy $\mathcal{H}_p \in [0, 1]$.
- `mutual_information: float` — Causal Mutual Information $I(X_t; R_{t+h})$.
- `symbolic_te: float` — Symbolic Transfer Entropy $TE_{\text{sym}}(X \to R)$.
- `knn_te: float` — Conditional k-NN / quantile Transfer Entropy $TE(X \to R)$.
- `reverse_te: float` — Reverse Transfer Entropy $TE(R \to X)$ for directional net information flow $\Delta TE = TE(X \to R) - TE(R \to X)$.
- `surrogate_method: Literal["iaaft", "block_shuffle"]` — Null model generator used.
- `surrogate_te_samples: np.ndarray` — Array of $M$ surrogate Transfer Entropy values.
- `surrogate_mean: float` — Mean of null distribution.
- `surrogate_std: float` — Standard deviation of null distribution.
- `z_score: float` — $(TE_{\text{obs}} - \mu_{\text{surr}}) / \sigma_{\text{surr}}$.
- `p_value: float` — Empirical Monte Carlo $p$-value.
- `rolling_entropy: np.ndarray` — Causal rolling Shannon entropy series.
- `passed: bool` — `True` iff `p_value < 0.05` and `knn_te > 0`.

---

### 5. `StatsGateResult` (`src/quantlab/proofs/stats_gate.py`)
Statistical predictive power, regime sensitivity, and multicollinearity orthogonality results.
- `ic_by_horizon: dict[int, float]` — Spearman Rank IC for forward horizons $h \in \{1, 5, 10, 20\}$.
- `ic_t_stat_by_horizon: dict[int, float]` — Student-$t$ statistic for each horizon's Rank IC.
- `max_abs_ic: float` — Maximum $|\text{Rank IC}|$ across evaluated horizons.
- `rolling_ic: np.ndarray` — Causal rolling Spearman Rank IC ($h=1$ or primary horizon).
- `wasserstein_regime_distance: float` — 1-Wasserstein distance $W_1(P_{\text{bull}}, P_{\text{bear}})$ between z-scored indicator distributions in bull vs. bear regimes.
- `vif_score: float` — Variance Inflation Factor of the indicator regressed against the baseline indicator matrix.
- `baseline_correlations: dict[str, float]` — Pairwise Spearman correlations with each baseline indicator.
- `ic_passed: bool` — `max_abs_ic > 0.02`.
- `vif_passed: bool` — `vif_score < 5.0` (or exempted when evaluating a baseline against other baselines).
- `passed: bool` — `ic_passed and vif_passed`.

---

### 6. `DSPResult` (`src/quantlab/proofs/dsp.py`)
Digital Signal Processing (Hilbert analytic signal, Bode response, and Jerk smoothness frontier) diagnostics.
- `instantaneous_amplitude: np.ndarray` — Envelope $|z_t|$ from Hilbert transform.
- `instantaneous_phase: np.ndarray` — Unwrapped phase $\phi_t$ in radians.
- `instantaneous_frequency: np.ndarray` — $\omega_t = \Delta \phi_t$.
- `mean_phase_lag_rad: float` — Mean phase delay (in radians) relative to reference price cycle.
- `mean_phase_lag_bars: float` — Equivalent phase delay in bars.
- `jerk_energy: float` — Mean squared 3rd-order discrete derivative $J = \frac{1}{N-3}\sum (\Delta^3 \hat{x}_t)^2$.
- `bode_frequencies: np.ndarray` — Normalized digital frequencies $\omega \in (0, \pi]$.
- `bode_magnitude_db: np.ndarray` — Empirical transfer function magnitude in dB.
- `bode_phase_deg: np.ndarray` — Empirical transfer function phase lag in degrees.
- `pareto_optimal: bool` — Whether the indicator lies on the non-dominated `(mean_phase_lag_bars, jerk_energy)` Pareto frontier among compared indicators.

---

### 7. `ProofSuiteResult` & `TranspilationArtifact`
- `ProofSuiteResult`: Aggregates `indicator_name`, `symbol`, `stationarity: StationarityResult`, `entropy: EntropyProofResult`, `stats_gate: StatsGateResult`, `dsp: DSPResult`, and `overall_passed: bool`.
- `TranspilationArtifact` (`src/quantlab/transpiler/pine_v6.py`):
  - `indicator_name: str`
  - `sympy_expr: sympy.Expr`
  - `latex_expr: str`
  - `pine_code: str` — Complete `//@version=6` TradingView script.
  - `research_card_md: str` — Complete Markdown Research Card with LaTeX, proof scorecard, and Pine Script v6 code block.
