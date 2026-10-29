"""Information-Theoretic Proofs: Shannon, Permutation, KSG Mutual Info, Transfer Entropy & Surrogates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numba
import numpy as np
from scipy.spatial import cKDTree
from scipy.special import digamma

SurrogateMethod = Literal["iaaft", "block_shuffle"]


@dataclass(frozen=True)
class EntropyProofResult:
    """Information-theoretic proof metrics and surrogate hypothesis gate."""

    shannon_entropy: float
    permutation_entropy: float
    mutual_information: float
    symbolic_te: float
    knn_te: float
    reverse_te: float
    net_te: float
    surrogate_method: SurrogateMethod
    surrogate_te_samples: np.ndarray
    surrogate_mean: float
    surrogate_std: float
    z_score: float
    p_value: float
    rolling_entropy: np.ndarray
    passed: bool


def shannon_entropy(series: np.ndarray, bins: int = 12) -> float:
    """Compute plug-in Shannon entropy (in nats) with Miller-Madow bias correction."""
    x = np.asarray(series, dtype=np.float64)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 4 or np.std(x) < 1e-14:
        return 0.0
    b = max(2, int(bins))
    counts, _ = np.histogram(x, bins=b)
    nonzero = counts[counts > 0].astype(np.float64)
    p = nonzero / float(n)
    h_plugin = -float(np.sum(p * np.log(p)))
    # Miller-Madow finite-sample correction
    k_pos = len(nonzero)
    h_mm = h_plugin + float(k_pos - 1) / (2.0 * float(n))
    return max(0.0, h_mm)


@numba.njit(cache=True)
def _permutation_entropy_order3(x: np.ndarray, delay: int) -> float:
    """Normalized Bandt-Pompe ordinal pattern permutation entropy of order m=3."""
    n = len(x)
    tau = max(1, delay)
    if n < 2 * tau + 4:
        return 0.0
    counts = np.zeros(6, dtype=np.float64)
    total = 0.0
    for t in range(2 * tau, n):
        a = x[t - 2 * tau]
        b = x[t - tau]
        c = x[t]
        if a <= b and b <= c:
            idx = 0
        elif a <= c and c < b:
            idx = 1
        elif b < a and a <= c:
            idx = 2
        elif b <= c and c < a:
            idx = 3
        elif c < a and a <= b:
            idx = 4
        else:
            idx = 5
        counts[idx] += 1.0
        total += 1.0
    if total < 1.0:
        return 0.0
    h = 0.0
    for i in range(6):
        if counts[i] > 0.0:
            p = counts[i] / total
            h -= p * np.log(p)
    return h / np.log(6.0)


def permutation_entropy(series: np.ndarray, delay: int = 1) -> float:
    """Compute normalized Bandt-Pompe permutation entropy in [0, 1]."""
    arr = np.ascontiguousarray(series, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if len(arr) < 8 or np.std(arr) < 1e-14:
        return 0.0
    return float(_permutation_entropy_order3(arr, int(delay)))


@numba.njit(cache=True)
def rolling_shannon_entropy(series: np.ndarray, window: int = 32, bins: int = 8) -> np.ndarray:
    """Compute strictly causal sliding-window Shannon entropy (in nats)."""
    n = len(series)
    out = np.zeros(n, dtype=np.float64)
    w = max(6, window)
    b = max(2, bins)
    counts = np.zeros(b, dtype=np.float64)

    for t in range(n):
        start = max(0, t - w + 1)
        win_len = t - start + 1
        if win_len < 4:
            out[t] = 0.0
            continue
        vmin = series[start]
        vmax = series[start]
        for k in range(start + 1, t + 1):
            val = series[k]
            if val < vmin:
                vmin = val
            if val > vmax:
                vmax = val
        span = vmax - vmin
        if span < 1e-14:
            out[t] = 0.0
            continue
        for j in range(b):
            counts[j] = 0.0
        for k in range(start, t + 1):
            idx = int(((series[k] - vmin) / span) * float(b))
            if idx >= b:
                idx = b - 1
            elif idx < 0:
                idx = 0
            counts[idx] += 1.0
        h = 0.0
        inv = 1.0 / float(win_len)
        for j in range(b):
            if counts[j] > 0.0:
                p = counts[j] * inv
                h -= p * np.log(p)
        out[t] = h
    return out


def mutual_information_ksg(x: np.ndarray, y: np.ndarray, k: int = 5) -> float:
    """Kraskov-Stogbauer-Grassberger (KSG-1) k-NN Mutual Information estimator I(X; Y)."""
    x_arr = np.asarray(x, dtype=np.float64)
    y_arr = np.asarray(y, dtype=np.float64)
    mask = np.isfinite(x_arr) & np.isfinite(y_arr)
    x_c = x_arr[mask]
    y_c = y_arr[mask]
    n = len(x_c)
    if n < max(20, k + 5):
        return 0.0
    std_x = float(np.std(x_c))
    std_y = float(np.std(y_c))
    if std_x < 1e-14 or std_y < 1e-14:
        return 0.0

    # Standardize and add tiny deterministic jitter to break exact ties in Chebyshev space
    rng = np.random.default_rng(1337)
    xz = (x_c - np.mean(x_c)) / std_x + 1e-10 * rng.standard_normal(n)
    yz = (y_c - np.mean(y_c)) / std_y + 1e-10 * rng.standard_normal(n)

    joint = np.column_stack([xz, yz])
    tree_xy = cKDTree(joint)
    tree_x = cKDTree(xz[:, None])
    tree_y = cKDTree(yz[:, None])

    dists, _ = tree_xy.query(joint, k=k + 1, p=np.inf)
    radii = np.maximum(dists[:, k] - 1e-13, 1e-14)

    nx = np.array([len(tree_x.query_ball_point([xz[i]], r=radii[i], p=np.inf)) - 1 for i in range(n)], dtype=np.float64)
    ny = np.array([len(tree_y.query_ball_point([yz[i]], r=radii[i], p=np.inf)) - 1 for i in range(n)], dtype=np.float64)

    mi = float(digamma(k) + digamma(n) - np.mean(digamma(nx + 1.0) + digamma(ny + 1.0)))
    return max(0.0, mi)


@numba.njit(cache=True)
def _quantile_discretize(x: np.ndarray, bins: int) -> np.ndarray:
    """Map 1D continuous array into equiprobable quantile states {0, ..., bins-1}."""
    n = len(x)
    out = np.zeros(n, dtype=np.int64)
    if n == 0:
        return out
    order = np.argsort(x)
    for rank_idx in range(n):
        orig_i = order[rank_idx]
        b_idx = int((float(rank_idx) / float(n)) * float(bins))
        if b_idx >= bins:
            b_idx = bins - 1
        out[orig_i] = b_idx
    return out


@numba.njit(cache=True)
def _discrete_transfer_entropy_kernel(
    x_state: np.ndarray,
    y_curr_state: np.ndarray,
    y_next_state: np.ndarray,
    bins: int,
) -> float:
    """Compute conditional mutual information I(Y_{t+1}; X_t | Y_t) from discretized states."""
    n = len(x_state)
    if n < 8:
        return 0.0
    b = bins
    c_yyx = np.zeros((b, b, b), dtype=np.float64)
    c_yy = np.zeros((b, b), dtype=np.float64)
    c_yx = np.zeros((b, b), dtype=np.float64)
    c_y = np.zeros(b, dtype=np.float64)

    for i in range(n):
        yn = y_next_state[i]
        yc = y_curr_state[i]
        xt = x_state[i]
        c_yyx[yn, yc, xt] += 1.0
        c_yy[yn, yc] += 1.0
        c_yx[yc, xt] += 1.0
        c_y[yc] += 1.0

    inv_n = 1.0 / float(n)
    te = 0.0
    for yn in range(b):
        for yc in range(b):
            if c_yy[yn, yc] <= 0.0 or c_y[yc] <= 0.0:
                continue
            for xt in range(b):
                count = c_yyx[yn, yc, xt]
                if count > 0.0 and c_yx[yc, xt] > 0.0:
                    p_yyx = count * inv_n
                    # p(yn | yc, xt) / p(yn | yc) = (c_yyx * c_y) / (c_yx * c_yy)
                    ratio = (count * c_y[yc]) / (c_yx[yc, xt] * c_yy[yn, yc])
                    if ratio > 0.0:
                        te += p_yyx * np.log(ratio)
    return max(0.0, te)


def symbolic_transfer_entropy(
    driver: np.ndarray,
    target_future: np.ndarray,
    target_current: np.ndarray | None = None,
    bins: int = 4,
) -> float:
    """Compute Symbolic/Quantile Transfer Entropy TE(X_t -> Y_{t+h} | Y_t)."""
    x = np.asarray(driver, dtype=np.float64)
    y_fut = np.asarray(target_future, dtype=np.float64)
    if target_current is None:
        y_cur = np.zeros_like(y_fut)
        y_cur[1:] = y_fut[:-1]
    else:
        y_cur = np.asarray(target_current, dtype=np.float64)

    mask = np.isfinite(x) & np.isfinite(y_fut) & np.isfinite(y_cur)
    x_c = x[mask]
    yf_c = y_fut[mask]
    yc_c = y_cur[mask]
    if len(x_c) < 20 or np.std(x_c) < 1e-14 or np.std(yf_c) < 1e-14:
        return 0.0

    b = max(2, int(bins))
    xs = _quantile_discretize(x_c, b)
    ycs = _quantile_discretize(yc_c, b)
    yfs = _quantile_discretize(yf_c, b)
    return float(_discrete_transfer_entropy_kernel(xs, ycs, yfs, b))


def knn_transfer_entropy(
    driver: np.ndarray,
    target_future: np.ndarray,
    target_current: np.ndarray | None = None,
    k: int = 5,
) -> float:
    """Frenzel-Pompe / KSG k-NN Conditional Mutual Information estimator TE(X_t -> Y_{t+h} | Y_t)."""
    x = np.asarray(driver, dtype=np.float64)
    y_fut = np.asarray(target_future, dtype=np.float64)
    if target_current is None:
        y_cur = np.zeros_like(y_fut)
        y_cur[1:] = y_fut[:-1]
    else:
        y_cur = np.asarray(target_current, dtype=np.float64)

    mask = np.isfinite(x) & np.isfinite(y_fut) & np.isfinite(y_cur)
    x_c = x[mask]
    yf_c = y_fut[mask]
    yc_c = y_cur[mask]
    n = len(x_c)
    if n < max(24, k + 6):
        return 0.0

    sx, syf, syc = float(np.std(x_c)), float(np.std(yf_c)), float(np.std(yc_c))
    if sx < 1e-14 or syf < 1e-14:
        return 0.0
    if syc < 1e-14:
        return mutual_information_ksg(x_c, yf_c, k=k)

    rng = np.random.default_rng(2026)
    xz = (x_c - np.mean(x_c)) / sx + 1e-10 * rng.standard_normal(n)
    yfz = (yf_c - np.mean(yf_c)) / syf + 1e-10 * rng.standard_normal(n)
    ycz = (yc_c - np.mean(yc_c)) / syc + 1e-10 * rng.standard_normal(n)

    joint_yyx = np.column_stack([yfz, ycz, xz])
    joint_yy = np.column_stack([yfz, ycz])
    joint_yx = np.column_stack([ycz, xz])
    marg_y = ycz[:, None]

    tree_yyx = cKDTree(joint_yyx)
    tree_yy = cKDTree(joint_yy)
    tree_yx = cKDTree(joint_yx)
    tree_y = cKDTree(marg_y)

    dists, _ = tree_yyx.query(joint_yyx, k=k + 1, p=np.inf)
    radii = np.maximum(dists[:, k] - 1e-13, 1e-14)

    n_yy = np.array(
        [len(tree_yy.query_ball_point(joint_yy[i], r=radii[i], p=np.inf)) - 1 for i in range(n)],
        dtype=np.float64,
    )
    n_yx = np.array(
        [len(tree_yx.query_ball_point(joint_yx[i], r=radii[i], p=np.inf)) - 1 for i in range(n)],
        dtype=np.float64,
    )
    n_y = np.array(
        [len(tree_y.query_ball_point(marg_y[i], r=radii[i], p=np.inf)) - 1 for i in range(n)],
        dtype=np.float64,
    )

    cmi = float(digamma(k) + np.mean(digamma(n_y + 1.0) - digamma(n_yy + 1.0) - digamma(n_yx + 1.0)))
    return max(0.0, cmi)


def generate_iaaft_surrogates(
    series: np.ndarray,
    n_surrogates: int = 50,
    max_iter: int = 15,
    seed: int = 42,
) -> np.ndarray:
    """Generate Iterative Amplitude Adjusted Fourier Transform (IAAFT) surrogates.

    Preserves both the exact empirical amplitude distribution and linear power spectrum
    of `series` while randomizing Fourier phases.
    """
    x = np.asarray(series, dtype=np.float64)
    n = len(x)
    m = max(1, int(n_surrogates))
    rng = np.random.default_rng(seed)
    out = np.empty((m, n), dtype=np.float64)
    if n < 4 or np.std(x) < 1e-14:
        for i in range(m):
            out[i] = x.copy()
        return out

    sorted_x = np.sort(x)
    target_amp = np.abs(np.fft.rfft(x))
    n_freq = len(target_amp)

    for s in range(m):
        current = rng.permutation(x)
        for _ in range(max_iter):
            # Step 1: Enforce exact Fourier power spectrum
            spec = np.fft.rfft(current)
            phases = np.angle(spec)
            adjusted_spec = target_amp * np.exp(1j * phases)
            wave = np.fft.irfft(adjusted_spec, n=n)
            # Step 2: Enforce exact amplitude rank values
            ranks = np.argsort(np.argsort(wave))
            current = sorted_x[ranks]
        # Ensure one final random phase rotation if series had dominant DC/low-freq lock
        if s % 2 == 1:
            rand_phases = rng.uniform(0.0, 2.0 * np.pi, size=n_freq)
            rand_phases[0] = 0.0
            wave = np.fft.irfft(target_amp * np.exp(1j * rand_phases), n=n)
            current = sorted_x[np.argsort(np.argsort(wave))]
        out[s] = current
    return out


def generate_block_shuffle_surrogates(
    series: np.ndarray,
    n_surrogates: int = 50,
    block_size: int = 16,
    seed: int = 42,
) -> np.ndarray:
    """Generate circular block-shuffled surrogates preserving local short-range dependency."""
    x = np.asarray(series, dtype=np.float64)
    n = len(x)
    m = max(1, int(n_surrogates))
    b = max(2, min(int(block_size), max(2, n // 4)))
    rng = np.random.default_rng(seed)
    out = np.empty((m, n), dtype=np.float64)

    n_blocks = (n + b - 1) // b
    for s in range(m):
        shift = int(rng.integers(0, n))
        rolled = np.roll(x, shift)
        blocks = [rolled[i * b : min((i + 1) * b, n)] for i in range(n_blocks)]
        perm = rng.permutation(len(blocks))
        shuffled = np.concatenate([blocks[idx] for idx in perm])[:n]
        out[s] = shuffled
    return out


def evaluate_entropy_proof(
    indicator_series: np.ndarray,
    forward_returns: np.ndarray,
    current_returns: np.ndarray | None = None,
    n_surrogates: int = 50,
    surrogate_method: SurrogateMethod = "iaaft",
    bins: int = 4,
    alpha: float = 0.05,
    seed: int = 42,
) -> EntropyProofResult:
    """Execute the full Information-Theoretic Proof Suite with Monte Carlo surrogate gating."""
    ind = np.asarray(indicator_series, dtype=np.float64)
    fwd = np.asarray(forward_returns, dtype=np.float64)
    if current_returns is None:
        cur = np.zeros_like(fwd)
        cur[1:] = fwd[:-1]
    else:
        cur = np.asarray(current_returns, dtype=np.float64)

    mask = np.isfinite(ind) & np.isfinite(fwd) & np.isfinite(cur)
    x_valid = ind[mask]
    yf_valid = fwd[mask]
    yc_valid = cur[mask]

    roll_ent = rolling_shannon_entropy(np.nan_to_num(ind, nan=0.0), window=32, bins=8)
    h_shannon = shannon_entropy(x_valid, bins=12)
    h_perm = permutation_entropy(x_valid, delay=1)
    mi_val = mutual_information_ksg(x_valid, yf_valid, k=5)

    sym_te = symbolic_transfer_entropy(x_valid, yf_valid, yc_valid, bins=bins)
    knn_te = knn_transfer_entropy(x_valid, yf_valid, yc_valid, k=5)
    # Reverse TE: does future return transfer information to next indicator change (control)?
    rev_te = symbolic_transfer_entropy(yc_valid, x_valid, yc_valid, bins=bins)

    # Combined observed TE test statistic (symbolic + kNN sensitivity)
    obs_stat = 0.5 * sym_te + 0.5 * knn_te

    m = max(10, int(n_surrogates))
    if surrogate_method == "iaaft":
        surrogates = generate_iaaft_surrogates(x_valid, n_surrogates=m, seed=seed)
    else:
        surrogates = generate_block_shuffle_surrogates(x_valid, n_surrogates=m, seed=seed)

    b = max(2, int(bins))
    ycs_disc = _quantile_discretize(yc_valid, b)
    yfs_disc = _quantile_discretize(yf_valid, b)

    surr_te = np.zeros(m, dtype=np.float64)
    for i in range(m):
        xs_disc = _quantile_discretize(surrogates[i], b)
        s_sym = float(_discrete_transfer_entropy_kernel(xs_disc, ycs_disc, yfs_disc, b))
        surr_te[i] = s_sym

    # Align surrogate scale with observed symbolic TE for clean null comparison
    surr_mean = float(np.mean(surr_te))
    surr_std = float(max(np.std(surr_te), 1e-8))
    z_score = float((sym_te - surr_mean) / surr_std)
    exceedances = int(np.sum(surr_te >= sym_te))
    p_val = float((1.0 + exceedances) / (1.0 + m))

    passed = bool((p_val < alpha) and (obs_stat > 0.0))

    return EntropyProofResult(
        shannon_entropy=h_shannon,
        permutation_entropy=h_perm,
        mutual_information=mi_val,
        symbolic_te=sym_te,
        knn_te=knn_te,
        reverse_te=rev_te,
        net_te=float(sym_te - rev_te),
        surrogate_method=surrogate_method,
        surrogate_te_samples=surr_te,
        surrogate_mean=surr_mean,
        surrogate_std=surr_std,
        z_score=z_score,
        p_value=p_val,
        rolling_entropy=roll_ent,
        passed=passed,
    )
