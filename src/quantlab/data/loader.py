"""Point-in-Time (PIT) OHLCV Market Data Loader, Parquet Cache & Synthetic Stochastic Generators."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

DataProvider = Literal["yfinance", "ccxt", "synthetic"]

DEFAULT_CACHE_DIR = Path(".cache/parquet")


@dataclass(frozen=True)
class OHLCVDataset:
    """Validated Point-in-Time (PIT) OHLCV time-series dataset."""

    symbol: str
    provider: DataProvider
    timeframe: str
    df: pd.DataFrame
    cache_path: Path | None = None

    def __post_init__(self) -> None:
        self.validate_pit()

    def validate_pit(self) -> None:
        """Enforce strict Point-in-Time (PIT) structural and numerical invariants."""
        required_cols = ("open", "high", "low", "close", "volume")
        missing = [c for c in required_cols if c not in self.df.columns]
        if missing:
            raise ValueError(f"OHLCVDataset missing required columns: {missing}")
        if len(self.df) == 0:
            raise ValueError("OHLCVDataset cannot be empty.")
        if not isinstance(self.df.index, pd.DatetimeIndex):
            raise ValueError("OHLCVDataset index must be a pandas DatetimeIndex.")
        if not self.df.index.is_monotonic_increasing:
            raise ValueError("OHLCVDataset index violates Point-in-Time monotonic ordering.")
        if self.df.index.has_duplicates:
            raise ValueError("OHLCVDataset index contains duplicate timestamps.")

        vals = self.df[list(required_cols)].to_numpy(dtype=np.float64)
        if not np.all(np.isfinite(vals)):
            raise ValueError("OHLCVDataset contains NaN or Inf values in OHLCV columns.")

        open_p = self.df["open"].to_numpy(dtype=np.float64)
        high_p = self.df["high"].to_numpy(dtype=np.float64)
        low_p = self.df["low"].to_numpy(dtype=np.float64)
        close_p = self.df["close"].to_numpy(dtype=np.float64)
        vol = self.df["volume"].to_numpy(dtype=np.float64)

        eps = 1e-9
        if np.any(high_p + eps < np.maximum(open_p, close_p)):
            raise ValueError("OHLCVDataset invariant violated: high < max(open, close).")
        if np.any(low_p - eps > np.minimum(open_p, close_p)):
            raise ValueError("OHLCVDataset invariant violated: low > min(open, close).")
        if np.any(vol < 0.0):
            raise ValueError("OHLCVDataset invariant violated: negative volume.")

    @property
    def n_bars(self) -> int:
        return int(len(self.df))

    @property
    def log_close(self) -> np.ndarray:
        return np.log(np.maximum(self.df["close"].to_numpy(dtype=np.float64), 1e-12))

    @property
    def log_returns(self) -> np.ndarray:
        lc = self.log_close
        ret = np.zeros_like(lc)
        ret[1:] = np.diff(lc)
        return ret

    def forward_returns(self, horizon: int = 1) -> np.ndarray:
        """Compute strictly aligned future log-returns R_{t -> t+h} = log(C_{t+h} / C_t).

        The last `horizon` bars are set to NaN so features at time t never peek beyond t+h,
        and callers must mask trailing NaNs when computing IC or Transfer Entropy.
        """
        if horizon < 1:
            raise ValueError(f"Horizon must be >= 1, got {horizon}")
        lc = self.log_close
        n = len(lc)
        out = np.full(n, np.nan, dtype=np.float64)
        if n > horizon:
            out[:-horizon] = lc[horizon:] - lc[:-horizon]
        return out


def _sanitize_cache_key(symbol: str, provider: str, timeframe: str, bars: int, seed: int) -> str:
    safe_sym = "".join(ch if ch.isalnum() else "_" for ch in symbol).strip("_")
    return f"{provider}_{safe_sym}_{timeframe}_{bars}_s{seed}.parquet"


def generate_synthetic_ohlcv(
    symbol: str = "SYNTH:COUPLED_OU",
    timeframe: str = "1d",
    bars: int = 1000,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate a deterministic, causally coupled stochastic process for offline quant verification.

    Modes (selected via `symbol`):
    - `SYNTH:WHITE_NOISE`: Pure Geometric Brownian Motion with zero temporal predictability (null control).
    - `SYNTH:COUPLED_OU` (or any other symbol): Coupled Ornstein-Uhlenbeck velocity state + two-state
      volatility regime switching where latent kinematic velocity `driver_signal[t]` causally drives
      next-bar return `r[t+1]`.
    """
    if bars < 32:
        raise ValueError(f"Minimum bars required is 32, got {bars}")

    rng = np.random.default_rng(seed)
    sym_upper = symbol.upper()
    is_white_noise = "WHITE_NOISE" in sym_upper or "RANDOM_WALK" in sym_upper

    # Deterministic UTC timestamp grid ending at a fixed reference date for reproducibility
    freq_map = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1h", "4h": "4h", "1d": "1D"}
    pd_freq = freq_map.get(timeframe, "1D")
    idx = pd.date_range(end=pd.Timestamp("2026-01-01", tz="UTC"), periods=bars, freq=pd_freq)

    driver = np.zeros(bars, dtype=np.float64)
    regime = np.zeros(bars, dtype=np.float64)  # 0 = low-vol bull, 1 = high-vol bear
    returns = np.zeros(bars, dtype=np.float64)
    vol_state = np.zeros(bars, dtype=np.float64)

    sigma_base = 0.011
    vol_state[0] = sigma_base

    if is_white_noise:
        driver[:] = rng.standard_normal(bars)
        returns[1:] = sigma_base * rng.standard_normal(bars - 1)
        vol_state[:] = sigma_base
    else:
        # Coupled Ornstein-Uhlenbeck velocity + Heston-style volatility regime process
        theta_ou = 0.14  # Mean-reversion rate (persistence = 0.86)
        sigma_ou = 0.009
        coupling_beta = 0.62  # Causal transfer strength from driver[t] -> return[t+1]

        cur_regime = 0
        for t in range(1, bars):
            # Markov regime transition (bull=0 -> bear=1 w.p. 0.025; bear=1 -> bull=0 w.p. 0.05)
            u_trans = rng.random()
            if cur_regime == 0 and u_trans < 0.025:
                cur_regime = 1
            elif cur_regime == 1 and u_trans < 0.055:
                cur_regime = 0
            regime[t] = float(cur_regime)

            target_vol = 0.0085 if cur_regime == 0 else 0.021
            vol_state[t] = 0.85 * vol_state[t - 1] + 0.15 * target_vol

            regime_drift = 0.0012 if cur_regime == 0 else -0.0016
            # Update causal OU velocity state at time t
            cyc = 0.0025 * np.sin(2.0 * np.pi * t / 48.0)
            driver[t] = (
                (1.0 - theta_ou) * driver[t - 1]
                + regime_drift
                + cyc
                + sigma_ou * rng.standard_normal()
            )
            # Return at time t is causally driven by driver[t - 1] (strictly t-1 -> t)
            innovation = vol_state[t] * rng.standard_normal()
            returns[t] = coupling_beta * driver[t - 1] + 0.25 * returns[t - 1] + innovation

    log_close = np.log(100.0) + np.cumsum(returns)
    close_p = np.exp(log_close)

    open_p = np.empty(bars, dtype=np.float64)
    open_p[0] = close_p[0] * (1.0 - 0.001 * rng.standard_normal())
    open_p[1:] = close_p[:-1] * np.exp(0.0015 * rng.standard_normal(bars - 1))

    intrabar_spread = np.abs(returns) + vol_state * np.abs(0.6 + 0.4 * rng.standard_normal(bars))
    high_p = np.maximum(open_p, close_p) * np.exp(0.65 * intrabar_spread)
    low_p = np.minimum(open_p, close_p) * np.exp(-0.65 * intrabar_spread)

    base_vol = 1_000_000.0
    volume = base_vol * (1.0 + 35.0 * np.abs(returns) + 20.0 * vol_state + 0.25 * np.abs(rng.standard_normal(bars)))

    df = pd.DataFrame(
        {
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "volume": volume,
            "driver_signal": driver,
            "regime": regime,
        },
        index=idx,
    )
    df.index.name = "timestamp"
    return df


def _fetch_yfinance(symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
    import yfinance as yf

    interval_map = {"1d": "1d", "1h": "1h", "15m": "15m", "5m": "5m"}
    interval = interval_map.get(timeframe, "1d")
    period = "max" if interval == "1d" else "60d"
    ticker = yf.Ticker(symbol)
    raw = ticker.history(period=period, interval=interval, auto_adjust=True)
    if raw is None or raw.empty:
        raise RuntimeError(f"yfinance returned empty dataset for symbol='{symbol}'")

    df = raw.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )[["open", "high", "low", "close", "volume"]].copy()
    df = df.dropna()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    df = df[~df.index.duplicated(keep="last")].sort_index()
    if len(df) > bars:
        df = df.iloc[-bars:].copy()
    # Enforce OHLC envelope consistency after floating adjustments
    df["high"] = np.maximum(df["high"], np.maximum(df["open"], df["close"]))
    df["low"] = np.minimum(df["low"], np.minimum(df["open"], df["close"]))
    df["volume"] = np.maximum(df["volume"], 0.0)
    df.index.name = "timestamp"
    return df


def _fetch_ccxt(symbol: str, timeframe: str, bars: int, exchange_id: str = "binance") -> pd.DataFrame:
    import ccxt

    exchange_cls = getattr(ccxt, exchange_id)
    exchange = exchange_cls({"enableRateLimit": True})
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=bars)
    if not ohlcv:
        raise RuntimeError(f"ccxt ({exchange_id}) returned empty OHLCV for '{symbol}'")

    df = pd.DataFrame(
        ohlcv,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype(np.float64)
    df["high"] = np.maximum(df["high"], np.maximum(df["open"], df["close"]))
    df["low"] = np.minimum(df["low"], np.minimum(df["open"], df["close"]))
    if len(df) > bars:
        df = df.iloc[-bars:].copy()
    return df


def fetch_ohlcv(
    symbol: str = "SYNTH:COUPLED_OU",
    provider: DataProvider = "synthetic",
    timeframe: str = "1d",
    bars: int = 1000,
    seed: int = 42,
    cache_dir: Path | str = DEFAULT_CACHE_DIR,
    use_cache: bool = True,
    fallback_to_synthetic: bool = True,
) -> OHLCVDataset:
    """Fetch or load Point-in-Time (PIT) OHLCV market data with local Parquet caching."""
    cache_root = Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_file = cache_root / _sanitize_cache_key(symbol, provider, timeframe, bars, seed)

    if use_cache and cache_file.exists():
        cached_df = pd.read_parquet(cache_file)
        if not isinstance(cached_df.index, pd.DatetimeIndex):
            cached_df.index = pd.to_datetime(cached_df.index, utc=True)
        return OHLCVDataset(
            symbol=symbol,
            provider=provider,
            timeframe=timeframe,
            df=cached_df,
            cache_path=cache_file,
        )

    effective_provider: DataProvider = provider
    if provider == "synthetic" or symbol.upper().startswith("SYNTH:"):
        effective_provider = "synthetic"
        df = generate_synthetic_ohlcv(symbol=symbol, timeframe=timeframe, bars=bars, seed=seed)
    elif provider == "yfinance":
        try:
            df = _fetch_yfinance(symbol=symbol, timeframe=timeframe, bars=bars)
        except Exception:
            if not fallback_to_synthetic:
                raise
            effective_provider = "synthetic"
            df = generate_synthetic_ohlcv(symbol=symbol, timeframe=timeframe, bars=bars, seed=seed)
    elif provider == "ccxt":
        try:
            df = _fetch_ccxt(symbol=symbol, timeframe=timeframe, bars=bars)
        except Exception:
            if not fallback_to_synthetic:
                raise
            effective_provider = "synthetic"
            df = generate_synthetic_ohlcv(symbol=symbol, timeframe=timeframe, bars=bars, seed=seed)
    else:
        raise ValueError(f"Unsupported provider: '{provider}'")

    df.to_parquet(cache_file, index=True)
    return OHLCVDataset(
        symbol=symbol,
        provider=effective_provider,
        timeframe=timeframe,
        df=df,
        cache_path=cache_file,
    )
