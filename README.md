# ⚛️ QuantLab (`quantlab`)

**Information-Theoretic Technical Indicator Research CLI, SymPy-to-Pine Script v6 Transpiler & 4-Quadrant Interactive Diagnostic Dashboard**

`quantlab` is a modular Python 3.11+ quantitative research framework engineered for mathematical physicists and quantitative developers. It enforces strict **Point-in-Time (PIT) causal alignment** (zero lookahead bias), **dual neuro-symbolic indicator representation** (`@numba.njit` vectorized kernels paired with canonical `sympy.Expr` Abstract Syntax Trees), **falsifiable information-theoretic and statistical proof gates**, and **automated compilation to TradingView Pine Script v6 (`//@version=6`)**.

---

## 🏗️ System Architecture

```text
quantlab/
├── pyproject.toml
├── README.md
├── CHANGELOG.md
└── src/
    └── quantlab/
        ├── cli.py                      # Typer + Rich CLI entrypoint
        ├── data/
        │   ├── loader.py               # PIT OHLCV fetcher (yfinance, ccxt, synthetic) + Parquet cache
        │   └── stationarity.py         # Fixed-Width Window Fractional Differentiation (FracDiff) + ADF test
        ├── indicators/
        │   ├── registry.py             # Dual Symbolic (SymPy) + Numba indicator registry & custom AST nodes
        │   ├── baselines.py            # Standard TA baselines (RSI, EMA, ATR, MACD, KAMA)
        │   └── custom_examples.py      # Physics-inspired indicators (KalmanFilter, PhaseSpaceEnergy, EntropyFlow)
        ├── proofs/
        │   ├── entropy.py              # Shannon, Permutation, KSG Mutual Info, Symbolic & k-NN Transfer Entropy + Surrogates
        │   ├── stats_gate.py           # Spearman Rank IC, Wasserstein Regime Distance, Orthogonality VIF & Proof Suite
        │   └── dsp.py                  # Hilbert Transform, Bode Response & Phase-Lag vs. Smoothness (Jerk) Frontier
        ├── transpiler/
        │   └── pine_v6.py              # SymPy AST -> TradingView Pine Script v6 + Markdown Research Card
        └── dashboard/
            ├── loading_state.py        # SPEC-QUANT-LOAD-01 4-Stage Pipeline Telemetry, Shimmer Skeletons & Warm Dimming
            └── app.py                  # 4-Quadrant Interactive Quant Diagnostic Dashboard (Streamlit + Plotly + Lightweight Charts)
```

---

## 🔬 Mathematical Core & Proof Gates

1. **Fixed-Width Window Fractional Differentiation (`quantlab.data.stationarity`)**:
   - Computes causal binomial weights $w_0 = 1,\ w_k = -w_{k-1} \frac{d - k + 1}{k}$ truncated at threshold $\tau$.
   - Searches for the minimum order $d^* \in [0, 1]$ passing the Augmented Dickey-Fuller (ADF) unit-root gate ($p < 0.05$) while preserving maximum memory correlation with raw series.
2. **Information-Theoretic Causality (`quantlab.proofs.entropy`)**:
   - **Shannon & Bandt-Pompe Permutation Entropy**: Miller-Madow bias-corrected plug-in entropy and order-3 ordinal pattern entropy.
   - **Mutual Information $I(X_t; R_{t+h})$**: Kraskov-Stögbauer-Grassberger (KSG-1) continuous k-NN digamma estimator in Chebyshev space.
   - **Causal Transfer Entropy $TE(X \to R)$**: Conditional mutual information $I(R_{t+1}; X_t \mid R_t)$ tested against **Iterative Amplitude Adjusted Fourier Transform (IAAFT)** and **Block-Shuffle** Monte Carlo surrogates ($p < 0.05$).
3. **Statistical & Orthogonality Gates (`quantlab.proofs.stats_gate`)**:
   - Multi-horizon **Spearman Rank IC** ($h \in \{1, 5, 10, 20\}$, gate $|\text{IC}| > 0.02$).
   - **1-Wasserstein ($W_1$) Earth Mover's Distance** measuring distributional shift between bull and bear volatility regimes.
   - **Variance Inflation Factor ($\text{VIF} < 5.0$)** and Spearman correlation matrix against the 5 standard baselines (`RSI`, `EMA`, `ATR`, `MACD`, `KAMA`).
4. **Digital Signal Processing Frontier (`quantlab.proofs.dsp`)**:
   - Analytic signal via **Hilbert Transform** $z_t = \tilde{x}_t + i\mathcal{H}\{\tilde{x}_t\}$ extracting instantaneous amplitude, unwrapped phase lag (in radians and equivalent bars), empirical **Bode magnitude/phase transfer curves**, and 3rd-order discrete **Jerk energy** $J = \frac{1}{N-3}\sum (\Delta^3 \hat{x}_t)^2$ to identify Pareto-optimal filters.

---

## 🚀 Quickstart & CLI Usage

### Installation

```powershell
uv sync --all-extras
```

### 1. List Registered Neuro-Symbolic Indicators

```powershell
uv run quantlab indicators
```

### 2. Fetch PIT Market Data & Run FracDiff Stationarity Search

```powershell
# Deterministic coupled Ornstein-Uhlenbeck + Heston volatility regime benchmark
uv run quantlab fetch --provider synthetic --symbol SYNTH:COUPLED_OU --bars 1000 --fracdiff

# Yahoo Finance or CCXT crypto exchange with local Parquet caching
uv run quantlab fetch --provider yfinance --symbol SPY --timeframe 1d --bars 1000
```

### 3. Run the Mathematical Proof Suite (`evaluate` / `prove`)

```powershell
# Evaluate a single physics-inspired indicator against IAAFT surrogates
uv run quantlab evaluate --indicator KalmanFilter --provider synthetic --bars 1000 --surrogates 50

# Evaluate all 8 baseline & physics indicators and identify the DSP Pareto frontier
uv run quantlab evaluate --indicator all --provider synthetic --bars 800 --surrogates 30
```

### 4. Transpile SymPy AST to TradingView Pine Script v6 & Research Card

```powershell
# Transpile a registered indicator and export both .pine and .md Research Card
uv run quantlab transpile --indicator PhaseSpaceEnergy --out-pine artifacts/phase_space.pine --out-card artifacts/phase_space_card.md

# Transpile an arbitrary custom SymPy formula directly
uv run quantlab transpile --expr "(close - EMA(close, 20)) / Max(Stdev(close, 20), 1e-8)"
```

### 5. Launch the 4-Quadrant Interactive Quant Diagnostic Dashboard

```powershell
# Run headless self-verification of all 4 quadrants and SPEC-QUANT-LOAD-01 loading telemetry
uv run quantlab dashboard --check

# Launch live interactive Streamlit web app on http://localhost:8501
uv run quantlab dashboard
```

---

## 🧪 Testing & Verification

```powershell
uv run pytest -v
uv run ruff check src tests
```
