# Quickstart & Validation Guide: QuantLab

## 1. Environment Setup

```powershell
uv sync --all-extras
```

## 2. Verify CLI & Indicator Registry

```powershell
# List all registered baseline and physics-inspired indicators + Symbolic ASTs
uv run quantlab indicators

# Fetch and cache a synthetic coupled stochastic dataset and run FracDiff stationarity search
uv run quantlab fetch --provider synthetic --symbol SYNTH:COUPLED_OU --bars 1000 --fracdiff
```

## 3. Run the Information-Theoretic, Statistical & DSP Proof Suite

```powershell
# Evaluate a specific physics indicator against IAAFT surrogates and baseline VIF
uv run quantlab evaluate --indicator KalmanFilter --provider synthetic --bars 1000 --surrogates 50

# Evaluate all 8 registered indicators and compare Pareto DSP frontier
uv run quantlab evaluate --indicator all --provider synthetic --bars 800 --surrogates 30
```

## 4. Transpile SymPy AST to TradingView Pine Script v6 & Research Card

```powershell
# Transpile a registered indicator and generate its Markdown Research Card
uv run quantlab transpile --indicator PhaseSpaceEnergy --out-pine artifacts/phase_space.pine --out-card artifacts/phase_space_card.md

# Transpile a custom symbolic expression directly
uv run quantlab transpile --expr "(close - EMA(close, 20)) / Max(Stdev(close, 20), 1e-8)"
```

## 5. Launch the 4-Quadrant Interactive Quant Diagnostic Dashboard

```powershell
# Validate all 4 dashboard quadrants in headless check mode
uv run quantlab dashboard --check

# Launch live interactive Streamlit web app on http://localhost:8501
uv run quantlab dashboard
```

## 6. Run Automated Test Suite & Linter

```powershell
uv run pytest -v
uv run ruff check src tests
```
