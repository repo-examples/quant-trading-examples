# Phase 1 Data Model: Quantitative Pipeline Loading Status & Skeleton UI (`SPEC-QUANT-LOAD-01`)

## Entities & Immutable Value Objects (`src/quantlab/dashboard/loading_state.py`)

All entities are implemented as `@dataclass(frozen=True)` with strict Python 3.11+ static type annotations in compliance with Constitution Principle IV.

### 1. `StageState` & `PipelineSystemState`

```python
StageState = Literal["pending", "active", "completed", "failed", "cancelled"]
PipelineSystemState = Literal[
    "cold_load",
    "warm_reload",
    "mid_run_restart",
    "completed",
    "error",
    "cancelled",
]
```

### 2. `PipelineStageStatus`

Represents a single row in the 4-Stage Telemetry Checklist (`SPEC-QUANT-LOAD-01` Section 4).

| Field | Type | Description | Validation / Invariants |
|-------|------|-------------|-------------------------|
| `stage_index` | `int` | 1-based stage number (`1..4`) | `1 <= stage_index <= 4` |
| `title` | `str` | Human-readable stage title (e.g., `"Synthesizing Market Data"`) | Non-empty string |
| `detail` | `str` | Parameter-bound context detail (e.g., `"SYNTH:COUPLED_OU • 1d • 600 PIT bars"`) | Non-empty string |
| `state` | `StageState` | Current execution status of this stage | `"pending" \| "active" \| "completed" \| "failed" \| "cancelled"` |
| `duration_seconds` | `float \| None` | Elapsed time spent in this stage once completed | `>= 0.0` when `state == "completed"` |
| `weight_start_pct` | `float` | Lower bound of overall progress bar weight | `0.0`, `20.0`, `40.0`, or `85.0` |
| `weight_end_pct` | `float` | Upper bound of overall progress bar weight | `20.0`, `40.0`, `85.0`, or `100.0` |

### 3. `PipelineExecutionTelemetry`

Aggregate state snapshot emitted at each stage transition and surrogate tick during `build_dashboard_bundle`.

| Field | Type | Description | Validation / Invariants |
|-------|------|-------------|-------------------------|
| `spec_id` | `str` | Specification identifier | Always `"SPEC-QUANT-LOAD-01"` |
| `system_state` | `PipelineSystemState` | Active state in the System States Matrix | Valid `PipelineSystemState` literal |
| `symbol` | `str` | Active market symbol or stochastic process | Non-empty string |
| `provider` | `str` | Market data provider (`synthetic`, `yfinance`, `ccxt`) | Non-empty string |
| `timeframe` | `str` | Bar timeframe (`1d`, `4h`, `1h`, `15m`) | Non-empty string |
| `bars` | `int` | Number of Point-in-Time history bars | `>= 50` |
| `indicator_name` | `str` | Active indicator name from registry | Registered indicator identifier |
| `n_surrogates` | `int` | Total Monte Carlo surrogates to simulate | `>= 1` |
| `seed` | `int` | Deterministic RNG seed | Integer |
| `overall_progress_pct` | `float` | Weighted determinate progress percentage | Clamped to `[0.0, 100.0]` |
| `elapsed_seconds` | `float` | Total elapsed wall-clock seconds | `>= 0.0` |
| `stages` | `tuple[PipelineStageStatus, ...]` | Exactly 4 ordered stage records | `len(stages) == 4` |
| `current_surrogate` | `int` | Completed surrogate count in Stage 3 | `0 <= current_surrogate <= n_surrogates` |
| `restarted_with_updated_params` | `bool` | Whether parameters changed mid-run / since prior run | Boolean |
| `is_warm_reload` | `bool` | Whether a cached `DashboardBundle` is dimmed below | Boolean |
| `long_running_warning` | `bool` | True when `bars > 1500`, `n_surrogates > 60`, or `elapsed_seconds > 15.0` | Boolean |
| `error_step` | `int \| None` | 1-based stage index where failure occurred | `1..4` when `system_state == "error"` else `None` |
| `error_message` | `str \| None` | Actionable failure message | Non-empty when `system_state == "error"` |
| `aria_announcement` | `str` | Stage-throttled screen reader announcement text | Updates only on stage/state transitions |

## State Transitions & Weighted Progress Formula

1. **Stage 1 (`stage_index = 1`, `0% -> 20%`)**:
   - Active at `0%` (`"Synthesizing Market Data ({symbol} • {timeframe} • {bars} PIT bars)"` for `synthetic`, or `"Fetching Market Data ..."` for external providers).
   - Completion sets Stage 1 `state="completed"`, records `duration_seconds`, and advances `overall_progress_pct` to `20.0%`.
2. **Stage 2 (`stage_index = 2`, `20% -> 40%`)**:
   - Active at `20%` (`"Computing Active Indicator ({indicator_name})"`).
   - Evaluates the active indicator's stationarity and statistical gates; completion sets Stage 2 `state="completed"` and advances `overall_progress_pct` to `40.0%`.
3. **Stage 3 (`stage_index = 3`, `40% -> 85%`)**:
   - Active from `40%` to `85%` (`"Simulating Monte Carlo Surrogates ({i} / {n_surrogates} surrogates • Seed: {seed})"`).
   - For each surrogate $i \in \{1, \dots, N\}$, updates `current_surrogate = i` and:
     $$\text{overall\_progress\_pct} = 40.0 + 45.0 \times \frac{i}{N}$$
   - `aria_announcement` remains anchored to `"Step 3 of 4: Simulating Monte Carlo Surrogates"` without re-triggering on each $i$.
4. **Stage 4 (`stage_index = 4`, `85% -> 100%`)**:
   - Active at `85%` (`"Evaluating Hilbert Phase-Jerk Frontier & Pine v6 Transpiler"`).
   - Completes baseline Pareto frontier comparison, Pine Script v6 transpilation, and figure assembly; completion sets Stage 4 `state="completed"`, `system_state="completed"`, and `overall_progress_pct = 100.0%`.
5. **Error / Cancelled Transitions**:
   - Any exception at Stage $k \in \{1, 2, 3, 4\}$ transitions Stage $k$ to `state="failed"`, `system_state="error"`, `error_step=k`, `error_message=str(exc)`, and preserves prior completed stages `1..k-1`.
   - User cancellation transitions active stage to `state="cancelled"` and `system_state="cancelled"`.
