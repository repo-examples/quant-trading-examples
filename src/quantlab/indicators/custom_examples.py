"""Physics-Inspired Indicators (Kalman Kinematic Filter, Takens Phase-Space Energy, Entropy Flow)."""

from __future__ import annotations

import numba
import numpy as np
import sympy as sp

from quantlab.indicators.registry import (
    CLOSE,
    EMA,
    REGISTRY,
    VOLUME,
    Change,
    IndicatorSpec,
    Lag,
    Nz,
    OHLCVInputs,
    RollingEntropy,
    Stdev,
    SymbolicRecurrence,
)


@numba.njit(cache=True)
def _kalman_kinematic_kernel(
    close: np.ndarray,
    process_noise: float,
    measurement_noise: float,
    damping: float,
) -> np.ndarray:
    """Causal 1D Kinematic Kalman Filter (Position + Velocity state-space estimator).

    State vector: [position, velocity]^T on log-prices.
    Returns normalized kinematic velocity state v_t.
    """
    n = len(close)
    out = np.zeros(n, dtype=np.float64)
    if n == 0:
        return out

    q = max(process_noise, 1e-8)
    r = max(measurement_noise, 1e-8)
    gamma = min(max(damping, 0.0), 0.99)

    pos = np.log(max(close[0], 1e-12))
    vel = 0.0
    p00 = 1.0
    p01 = 0.0
    p10 = 0.0
    p11 = 1.0

    for t in range(1, n):
        obs = np.log(max(close[t], 1e-12))
        # Predict step: x_{t|t-1} = F x_{t-1}, F = [[1, 1], [0, 1 - gamma]]
        phi = 1.0 - gamma
        pos_pred = pos + vel
        vel_pred = phi * vel

        # Covariance prediction: P_{t|t-1} = F P F^T + Q
        fp00 = p00 + p10
        fp01 = p01 + p11
        fp10 = phi * p10
        fp11 = phi * p11

        p00_pred = fp00 + fp01 + q
        p01_pred = fp01 * phi + 0.5 * q
        p10_pred = fp10 + fp11 + 0.5 * q
        p11_pred = fp11 * phi + q

        # Innovation & Kalman gain: H = [1, 0]
        innov = obs - pos_pred
        s_cov = p00_pred + r
        k0 = p00_pred / s_cov
        k1 = p10_pred / s_cov

        # Update state
        pos = pos_pred + k0 * innov
        vel = vel_pred + k1 * innov

        # Update covariance: P = (I - K H) P_{t|t-1}
        p00 = (1.0 - k0) * p00_pred
        p01 = (1.0 - k0) * p01_pred
        p10 = p10_pred - k1 * p00_pred
        p11 = p11_pred - k1 * p01_pred

        out[t] = vel * 100.0
    return out


@numba.njit(cache=True)
def _phase_space_energy_kernel(
    close: np.ndarray,
    window: int,
    delay: int,
    stiffness: float,
) -> np.ndarray:
    """Causal Takens Phase-Space Reconstruction Directed Hamiltonian Energy.

    Constructs delay-embedding coordinates (q_t, p_t) where:
      - q_t is normalized log-price displacement from causal EMA
      - p_t is normalized delay-tau kinematic momentum
    Returns directed phase-space flux: p_t * sqrt(0.5 * p_t^2 + 0.5 * k * q_t^2).
    """
    n = len(close)
    out = np.zeros(n, dtype=np.float64)
    if n == 0:
        return out

    w = max(4, window)
    tau = max(1, delay)
    alpha = 2.0 / (float(w) + 1.0)

    log_p = np.empty(n, dtype=np.float64)
    for i in range(n):
        log_p[i] = np.log(max(close[i], 1e-12))

    ema = log_p[0]
    var_q = 1e-6
    var_p = 1e-6

    for t in range(1, n):
        ema = alpha * log_p[t] + (1.0 - alpha) * ema
        disp = log_p[t] - ema
        var_q = alpha * (disp * disp) + (1.0 - alpha) * var_q
        q_norm = disp / np.sqrt(max(var_q, 1e-12))

        idx_lag = t - tau if t >= tau else 0
        mom = log_p[t] - log_p[idx_lag]
        var_p = alpha * (mom * mom) + (1.0 - alpha) * var_p
        p_norm = mom / np.sqrt(max(var_p, 1e-12))

        hamiltonian = 0.5 * (p_norm * p_norm) + 0.5 * stiffness * (q_norm * q_norm)
        # Directed energy flux preserving sign of momentum + restoring force balance
        out[t] = (0.75 * p_norm + 0.25 * q_norm) * np.sqrt(hamiltonian)
    return out


@numba.njit(cache=True)
def _entropy_flow_kernel(
    close: np.ndarray,
    volume: np.ndarray,
    window: int,
    bins: int,
) -> np.ndarray:
    """Causal Rolling Shannon Entropy-Gated Order Flow Indicator.

    Measures local Shannon entropy H_t of returns over a causal sliding window W,
    normalizes by log(B), and gates volume-weighted directional velocity by
    information coherence (1 - H_t / H_max).
    """
    n = len(close)
    out = np.zeros(n, dtype=np.float64)
    if n < 2:
        return out

    w = max(8, window)
    b = max(3, bins)
    log_b = np.log(float(b))

    ret = np.zeros(n, dtype=np.float64)
    for t in range(1, n):
        ret[t] = np.log(max(close[t], 1e-12) / max(close[t - 1], 1e-12))

    alpha = 2.0 / (float( max(4, w // 2) ) + 1.0)
    ema_ret = 0.0
    ema_vol = max(volume[0], 1.0)
    ema_abs_ret = 1e-4

    counts = np.zeros(b, dtype=np.float64)

    for t in range(1, n):
        ema_vol = alpha * volume[t] + (1.0 - alpha) * ema_vol
        vol_weight = min(max(volume[t] / max(ema_vol, 1e-12), 0.2), 3.0)
        ema_ret = alpha * (ret[t] * vol_weight) + (1.0 - alpha) * ema_ret
        ema_abs_ret = alpha * abs(ret[t]) + (1.0 - alpha) * ema_abs_ret

        start_idx = max(1, t - w + 1)
        win_len = t - start_idx + 1
        if win_len < 4:
            out[t] = ema_ret / max(ema_abs_ret, 1e-12)
            continue

        r_min = ret[start_idx]
        r_max = ret[start_idx]
        for k in range(start_idx + 1, t + 1):
            if ret[k] < r_min:
                r_min = ret[k]
            if ret[k] > r_max:
                r_max = ret[k]

        span = r_max - r_min
        if span < 1e-14:
            # Constant return window -> zero entropy (maximal coherence)
            coherence = 1.0
        else:
            for j in range(b):
                counts[j] = 0.0
            for k in range(start_idx, t + 1):
                scaled = (ret[k] - r_min) / span
                bin_idx = int(scaled * float(b))
                if bin_idx >= b:
                    bin_idx = b - 1
                elif bin_idx < 0:
                    bin_idx = 0
                counts[bin_idx] += 1.0

            h_val = 0.0
            inv_n = 1.0 / float(win_len)
            for j in range(b):
                if counts[j] > 0.0:
                    p = counts[j] * inv_n
                    h_val -= p * np.log(p)
            coherence = max(0.05, 1.0 - (h_val / log_b))

        norm_vel = ema_ret / max(ema_abs_ret, 1e-12)
        out[t] = norm_vel * (0.5 + 0.5 * coherence)
    return out


def reconstruct_phase_space_3d(
    series: np.ndarray,
    delay: int = 3,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Construct causal 3D Takens delay-embedding coordinates (x_t, x_{t-tau}, x_{t-2*tau})."""
    arr = np.asarray(series, dtype=np.float64)
    n = len(arr)
    tau = max(1, int(delay))
    if n < 2 * tau + 2:
        raise ValueError(f"Series length {n} too short for 3D delay embedding with tau={tau}")

    x0 = arr.copy()
    x1 = np.empty(n, dtype=np.float64)
    x1[:tau] = arr[0]
    x1[tau:] = arr[:-tau]

    x2 = np.empty(n, dtype=np.float64)
    two_tau = 2 * tau
    x2[:two_tau] = arr[0]
    x2[two_tau:] = arr[:-two_tau]
    return x0, x1, x2


# 1. KalmanFilter registration
def _compute_kalman(inputs: OHLCVInputs, params: dict[str, int | float]) -> np.ndarray:
    return _kalman_kinematic_kernel(
        inputs.close,
        float(params["process_noise"]),
        float(params["measurement_noise"]),
        float(params["damping"]),
    )


def _symbolic_kalman(params: dict[str, int | float]) -> sp.Expr:
    return sp.Float(100.0) * sp.Symbol("kalman_vel", real=True)


def _recurrences_kalman(params: dict[str, int | float]) -> tuple[SymbolicRecurrence, ...]:
    q_sym = sp.Symbol("process_noise", positive=True)
    r_sym = sp.Symbol("measurement_noise", positive=True)
    d_sym = sp.Symbol("damping", nonnegative=True)

    obs = sp.log(sp.Max(CLOSE, sp.Float(1e-12)))
    prev_pos = Nz(Lag(sp.Symbol("kalman_pos", real=True), 1), obs)
    prev_vel = Nz(Lag(sp.Symbol("kalman_vel", real=True), 1), sp.Float(0.0))
    prev_cov = Nz(Lag(sp.Symbol("kalman_cov", real=True), 1), sp.Float(1.0))

    phi = sp.Float(1.0) - d_sym
    pos_pred = prev_pos + prev_vel
    vel_pred = phi * prev_vel
    cov_pred = prev_cov + q_sym
    gain = cov_pred / (cov_pred + r_sym)
    innov = obs - pos_pred

    return (
        SymbolicRecurrence(
            state_name="kalman_pos",
            init_expr=obs,
            update_expr=pos_pred + gain * innov,
            description="Kalman filtered log-price state",
        ),
        SymbolicRecurrence(
            state_name="kalman_vel",
            init_expr=sp.Float(0.0),
            update_expr=vel_pred + (sp.Float(0.5) * gain) * innov,
            description="Kalman kinematic velocity state",
        ),
        SymbolicRecurrence(
            state_name="kalman_cov",
            init_expr=sp.Float(1.0),
            update_expr=(sp.Float(1.0) - gain) * cov_pred,
            description="Kalman posterior error covariance",
        ),
    )


KALMAN_SPEC = REGISTRY.register(
    IndicatorSpec(
        name="KalmanFilter",
        title="1D Kinematic Kalman Velocity Filter",
        category="physics",
        description="Minimum-MSE causal state-space filter estimating instantaneous log-price kinematic velocity.",
        default_params={"process_noise": 0.01, "measurement_noise": 0.10, "damping": 0.08},
        compute_fn=_compute_kalman,
        symbolic_fn=_symbolic_kalman,
        recurrences_fn=_recurrences_kalman,
        overlay=False,
        param_descriptions={
            "process_noise": "State transition covariance Q",
            "measurement_noise": "Observation noise variance R",
            "damping": "Velocity friction coefficient gamma",
        },
    )
)


# 2. PhaseSpaceEnergy registration
def _compute_phase_space(inputs: OHLCVInputs, params: dict[str, int | float]) -> np.ndarray:
    return _phase_space_energy_kernel(
        inputs.close,
        int(params["window"]),
        int(params["delay"]),
        float(params["stiffness"]),
    )


def _symbolic_phase_space(params: dict[str, int | float]) -> sp.Expr:
    w_sym = sp.Symbol("window", integer=True, positive=True)
    tau_sym = sp.Symbol("delay", integer=True, positive=True)
    k_sym = sp.Symbol("stiffness", positive=True)

    log_c = sp.log(sp.Max(CLOSE, sp.Float(1e-12)))
    q_coord = (log_c - EMA(log_c, w_sym)) / sp.Max(Stdev(log_c, w_sym), sp.Float(1e-8))
    mom = log_c - Lag(log_c, tau_sym)
    p_coord = mom / sp.Max(Stdev(mom, w_sym), sp.Float(1e-8))
    hamiltonian = sp.Float(0.5) * (p_coord**2) + sp.Float(0.5) * k_sym * (q_coord**2)
    return (sp.Float(0.75) * p_coord + sp.Float(0.25) * q_coord) * sp.sqrt(hamiltonian)


PHASE_SPACE_SPEC = REGISTRY.register(
    IndicatorSpec(
        name="PhaseSpaceEnergy",
        title="Takens Phase-Space Hamiltonian Energy Flux",
        category="physics",
        description="Reconstructs 3D Takens delay-embedding attractor coordinates and computes directed Hamiltonian energy.",
        default_params={"window": 20, "delay": 3, "stiffness": 1.0},
        compute_fn=_compute_phase_space,
        symbolic_fn=_symbolic_phase_space,
        overlay=False,
        param_descriptions={
            "window": "Normalization window for generalized coordinate q and momentum p",
            "delay": "Takens embedding time delay tau in bars",
            "stiffness": "Harmonic restoring potential constant k",
        },
    )
)


# 3. EntropyFlow registration
def _compute_entropy_flow(inputs: OHLCVInputs, params: dict[str, int | float]) -> np.ndarray:
    return _entropy_flow_kernel(
        inputs.close,
        inputs.volume,
        int(params["window"]),
        int(params["bins"]),
    )


def _symbolic_entropy_flow(params: dict[str, int | float]) -> sp.Expr:
    w_sym = sp.Symbol("window", integer=True, positive=True)
    b_sym = sp.Symbol("bins", integer=True, positive=True)

    ret = Change(sp.log(sp.Max(CLOSE, sp.Float(1e-12))), 1)
    vol_ratio = VOLUME / sp.Max(EMA(VOLUME, w_sym), sp.Float(1.0))
    vel = EMA(ret * vol_ratio, w_sym) / sp.Max(EMA(sp.Abs(ret), w_sym), sp.Float(1e-8))
    h_norm = RollingEntropy(ret, w_sym, b_sym) / sp.log(b_sym)
    coherence = sp.Max(sp.Float(0.05), sp.Float(1.0) - h_norm)
    return vel * (sp.Float(0.5) + sp.Float(0.5) * coherence)


ENTROPY_FLOW_SPEC = REGISTRY.register(
    IndicatorSpec(
        name="EntropyFlow",
        title="Shannon Information Coherence Order Flow",
        category="physics",
        description="Volume-weighted directional velocity modulated by local causal Shannon entropy coherence.",
        default_params={"window": 24, "bins": 6},
        compute_fn=_compute_entropy_flow,
        symbolic_fn=_symbolic_entropy_flow,
        overlay=False,
        param_descriptions={
            "window": "Sliding causal entropy window length W",
            "bins": "Number of histogram partition bins B",
        },
    )
)

__all__ = [
    "ENTROPY_FLOW_SPEC",
    "KALMAN_SPEC",
    "PHASE_SPACE_SPEC",
    "reconstruct_phase_space_3d",
]
