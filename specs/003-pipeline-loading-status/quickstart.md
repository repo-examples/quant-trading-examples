# Quickstart & Validation Guide: Quantitative Pipeline Loading Status & Skeleton UI (`SPEC-QUANT-LOAD-01`)

## Prerequisites

Ensure the Python 3.11+ virtual environment and dependencies are synced via `uv`:

```powershell
uv sync --all-extras
```

## 1. Run Headless Dashboard & Loading State Self-Check

Verify that the 4-Quadrant dashboard bundle AND the 4-Stage Pipeline Loading Telemetry (`SPEC-QUANT-LOAD-01`) build and self-validate cleanly in headless mode:

```powershell
uv run quantlab dashboard --check
```

**Expected Output**:
- JSON payload with `"status": "ok"`, `"loading_spec_id": "SPEC-QUANT-LOAD-01"`, `"telemetry_stages_verified": 4`, and `"final_progress_pct": 100.0`.

## 2. Run Automated Unit & Integration Tests

Execute the full test suite including the new loading telemetry, progress weighting, shimmer skeleton DOM, warm-state dimming, error recovery, cancellation, and accessibility tests:

```powershell
uv run pytest -v
```

## 3. Run Static Analysis & Linter

```powershell
uv run ruff check src tests
```

## 4. Launch Interactive Streamlit Workspace

```powershell
uv run quantlab dashboard
```

**Interactive Verification Scenarios**:
1. **Initial Cold Load**: Observe the Multi-Stage Pipeline Status Card (`0% -> 20% -> 40% -> 85% -> 100%`) with live surrogate counter (`i / N surrogates`) and the 4-card KPI + 360px chart shimmer skeletons below.
2. **Post-Load Collapse**: Verify the status card collapses into `"✓ Completed in X.Xs • SYNTH:COUPLED_OU (600 bars, 30 surrogates)"` with the expandable `"Show Execution Log ▾"` panel.
3. **Warm Re-Computation**: Change `Active Indicator` or `Monte Carlo Surrogates` in the sidebar and observe `"Updating ..."` + `"Restarted pipeline with updated parameters"` badge while existing charts remain visible at 45% opacity.
