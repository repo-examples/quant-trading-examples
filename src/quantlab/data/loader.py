"""Point-in-Time (PIT) OHLCV Market Data Loader, Parquet Cache & Synthetic Stochastic Generators."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

DataProvider = Literal["yfinance", "ccxt", "synthetic"]

DEFAULT_CACHE_DIR = Path(".cache/parquet")

UI_TIMEFRAMES: tuple[str, ...] = ("15m", "1h", "4h", "1D", "1W", "1M", "3M")
HIGHER_TIMEFRAME_PILLS: tuple[str, ...] = ("1D", "1W", "1M", "3M")
MIN_PROOF_BARS: int = 35


@dataclass(frozen=True)
class TimeframeSpec:
    """Canonical timeframe descriptor decoupling UI/CLI labels from provider API intervals."""

    label: str
    yf_interval: str
    yf_period: str
    yf_resample_rule: str | None
    ccxt_timeframe: str
    ccxt_resample_rule: str | None
    synthetic_freq: str
    is_calendar_date: bool
    default_bars: int
    max_bars: int


TIMEFRAME_SPECS: dict[str, TimeframeSpec] = {
    "1m": TimeframeSpec(
        label="1m",
        yf_interval="1m",
        yf_period="7d",
        yf_resample_rule=None,
        ccxt_timeframe="1m",
        ccxt_resample_rule=None,
        synthetic_freq="1min",
        is_calendar_date=False,
        default_bars=600,
        max_bars=2000,
    ),
    "5m": TimeframeSpec(
        label="5m",
        yf_interval="5m",
        yf_period="60d",
        yf_resample_rule=None,
        ccxt_timeframe="5m",
        ccxt_resample_rule=None,
        synthetic_freq="5min",
        is_calendar_date=False,
        default_bars=600,
        max_bars=2000,
    ),
    "15m": TimeframeSpec(
        label="15m",
        yf_interval="15m",
        yf_period="60d",
        yf_resample_rule=None,
        ccxt_timeframe="15m",
        ccxt_resample_rule=None,
        synthetic_freq="15min",
        is_calendar_date=False,
        default_bars=600,
        max_bars=2000,
    ),
    "1h": TimeframeSpec(
        label="1h",
        yf_interval="1h",
        yf_period="730d",
        yf_resample_rule=None,
        ccxt_timeframe="1h",
        ccxt_resample_rule=None,
        synthetic_freq="1h",
        is_calendar_date=False,
        default_bars=600,
        max_bars=2000,
    ),
    "4h": TimeframeSpec(
        label="4h",
        yf_interval="1h",
        yf_period="730d",
        yf_resample_rule="4h",
        ccxt_timeframe="4h",
        ccxt_resample_rule=None,
        synthetic_freq="4h",
        is_calendar_date=False,
        default_bars=600,
        max_bars=2000,
    ),
    "1D": TimeframeSpec(
        label="1D",
        yf_interval="1d",
        yf_period="max",
        yf_resample_rule=None,
        ccxt_timeframe="1d",
        ccxt_resample_rule=None,
        synthetic_freq="1D",
        is_calendar_date=True,
        default_bars=600,
        max_bars=2500,
    ),
    "1W": TimeframeSpec(
        label="1W",
        yf_interval="1wk",
        yf_period="max",
        yf_resample_rule=None,
        ccxt_timeframe="1w",
        ccxt_resample_rule=None,
        synthetic_freq="W-FRI",
        is_calendar_date=True,
        default_bars=400,
        max_bars=1500,
    ),
    "1M": TimeframeSpec(
        label="1M",
        yf_interval="1mo",
        yf_period="max",
        yf_resample_rule=None,
        ccxt_timeframe="1M",
        ccxt_resample_rule=None,
        synthetic_freq="MS",
        is_calendar_date=True,
        default_bars=240,
        max_bars=600,
    ),
    "3M": TimeframeSpec(
        label="3M",
        yf_interval="3mo",
        yf_period="max",
        yf_resample_rule=None,
        ccxt_timeframe="1d",
        ccxt_resample_rule="QS",
        synthetic_freq="QS",
        is_calendar_date=True,
        default_bars=120,
        max_bars=300,
    ),
}

TIMEFRAME_MAP: dict[str, dict[str, object]] = {
    key: {
        "yf_interval": spec.yf_interval,
        "yf_period": spec.yf_period,
        "default_bars": spec.default_bars,
        "max_bars": spec.max_bars,
        "is_calendar_date": spec.is_calendar_date,
    }
    for key, spec in TIMEFRAME_SPECS.items()
}


def normalize_timeframe(timeframe: str) -> str:
    """Normalize UI timeframe labels and CLI aliases to canonical QuantLab timeframe keys.

    Preserves exact lowercase `"1m"` as 1-minute intraday while mapping `"1M"`, `"1mo"`,
    and `"1MO"` to 1-Month (`"1M"`).
    """
    raw = str(timeframe).strip()
    if not raw:
        raise ValueError("Timeframe cannot be empty.")

    if raw in ("1m", "1min"):
        return "1m"
    if raw == "1M":
        return "1M"

    lowered = raw.lower()
    alias_map: dict[str, str] = {
        "5m": "5m",
        "5min": "5m",
        "15m": "15m",
        "15min": "15m",
        "1h": "1h",
        "60m": "1h",
        "4h": "4h",
        "240m": "4h",
        "1d": "1D",
        "d": "1D",
        "1w": "1W",
        "1wk": "1W",
        "w": "1W",
        "1mo": "1M",
        "1mon": "1M",
        "3m": "3M",
        "3mo": "3M",
        "1q": "3M",
    }
    if lowered in alias_map:
        return alias_map[lowered]
    raise ValueError(
        f"Unsupported timeframe '{timeframe}'. Supported timeframes: {', '.join(UI_TIMEFRAMES)}"
    )


def get_timeframe_spec(timeframe: str) -> TimeframeSpec:
    """Return the canonical `TimeframeSpec` for any supported UI or CLI timeframe token."""
    canonical = normalize_timeframe(timeframe)
    return TIMEFRAME_SPECS[canonical]


def extract_unix_timestamps(index: pd.DatetimeIndex) -> np.ndarray:
    """Convert any pandas `DatetimeIndex` (`s`, `ms`, `us`, `ns`, naive or tz-aware) to UTC Unix seconds."""
    if not isinstance(index, pd.DatetimeIndex):
        raise ValueError("index must be a pandas DatetimeIndex.")
    if len(index) == 0:
        return np.empty(0, dtype=np.int64)

    idx_utc = index.tz_localize("UTC") if index.tz is None else index.tz_convert("UTC")
    epoch = pd.Timestamp("1970-01-01", tz="UTC")
    seconds = (idx_utc - epoch) // pd.Timedelta(seconds=1)
    return seconds.to_numpy(dtype=np.int64)


def extract_calendar_dates(index: pd.DatetimeIndex) -> list[str]:
    """Format a `DatetimeIndex` as timezone-normalized `YYYY-MM-DD` strings for calendar timeframes."""
    if not isinstance(index, pd.DatetimeIndex):
        raise ValueError("index must be a pandas DatetimeIndex.")
    if len(index) == 0:
        return []

    naive_idx = index.tz_localize(None) if index.tz is not None else index
    return [str(d) for d in naive_idx.strftime("%Y-%m-%d")]


def resample_ohlcv_causal(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Causally aggregate lower-timeframe OHLCV bars (`O=first, H=max, L=min, C=last, V=sum`).

    Uses left-closed, left-labeled buckets so bar aggregations never peek across future bucket
    boundaries and mutating future buckets leaves historical resampled bars invariant.
    """
    if df.empty:
        return df.copy()

    sorted_df = df[~df.index.duplicated(keep="last")].sort_index()
    agg_spec: dict[str, str] = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    for opt_col in ("driver_signal", "regime"):
        if opt_col in sorted_df.columns:
            agg_spec[opt_col] = "last"

    resampled = (
        sorted_df.resample(rule, label="left", closed="left")
        .agg(agg_spec)
        .dropna(subset=["open", "high", "low", "close"])
        .copy()
    )
    if resampled.empty:
        return resampled

    resampled["volume"] = np.maximum(resampled["volume"].fillna(0.0).to_numpy(dtype=np.float64), 0.0)
    resampled["high"] = np.maximum(
        resampled["high"].to_numpy(dtype=np.float64),
        np.maximum(resampled["open"].to_numpy(dtype=np.float64), resampled["close"].to_numpy(dtype=np.float64)),
    )
    resampled["low"] = np.minimum(
        resampled["low"].to_numpy(dtype=np.float64),
        np.minimum(resampled["open"].to_numpy(dtype=np.float64), resampled["close"].to_numpy(dtype=np.float64)),
    )
    resampled.index.name = "timestamp"
    return resampled


def _flatten_ohlcv_columns(raw: pd.DataFrame) -> pd.DataFrame:
    """Normalize single-level or MultiIndex OHLCV columns (`yfinance` tuple headers) to lowercase."""
    out = raw.copy()
    target_names = {"open", "high", "low", "close", "volume"}

    if isinstance(out.columns, pd.MultiIndex):
        lvl0 = [str(c).strip().lower() for c in out.columns.get_level_values(0)]
        if len(target_names.intersection(lvl0)) >= 4:
            out.columns = out.columns.get_level_values(0)
        elif out.columns.nlevels > 1:
            out.columns = out.columns.get_level_values(-1)
        else:
            out.columns = out.columns.get_level_values(0)

    rename_map: dict[object, str] = {}
    for col in out.columns:
        low = str(col).strip().lower()
        if low in target_names and low not in rename_map.values():
            rename_map[col] = low
    out = out.rename(columns=rename_map)

    # Handle duplicate columns if MultiIndex contained multiple tickers
    out = out.loc[:, ~out.columns.duplicated(keep="first")]
    if "volume" not in out.columns:
        out["volume"] = 0.0
    return out


class InsufficientHistoryError(ValueError):
    """Raised when a market series has fewer than `MIN_PROOF_BARS` (35) bars for causal proofs."""

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        available_bars: int,
        minimum_bars: int = MIN_PROOF_BARS,
        indicator_name: str | None = None,
    ) -> None:
        self.symbol = symbol
        try:
            self.timeframe = normalize_timeframe(timeframe)
        except ValueError:
            self.timeframe = str(timeframe)
        self.available_bars = int(available_bars)
        self.minimum_bars = int(minimum_bars)
        self.indicator_name = indicator_name
        super().__init__(
            f"Insufficient history: {self.symbol} only has {self.available_bars} bars on "
            f"{self.timeframe} (minimum {self.minimum_bars} required for indicator & stationarity "
            f"proofs). Switch to 1W or 1D."
        )


@dataclass(frozen=True)
class OHLCVDataset:
    """Validated Point-in-Time (PIT) OHLCV time-series dataset."""

    symbol: str
    provider: DataProvider
    timeframe: str
    df: pd.DataFrame
    cache_path: Path | None = None
    requested_bars: int | None = None
    resampled_from: str | None = None

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
    def canonical_timeframe(self) -> str:
        try:
            return normalize_timeframe(self.timeframe)
        except ValueError:
            return self.timeframe

    @property
    def is_clamped(self) -> bool:
        return bool(self.requested_bars is not None and self.n_bars < int(self.requested_bars))

    @property
    def unix_timestamps(self) -> np.ndarray:
        return extract_unix_timestamps(self.df.index)  # type: ignore[arg-type]

    @property
    def calendar_dates(self) -> list[str]:
        return extract_calendar_dates(self.df.index)  # type: ignore[arg-type]

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


def validate_minimum_proof_bars(
    dataset: OHLCVDataset,
    min_bars: int = MIN_PROOF_BARS,
    indicator_name: str | None = None,
) -> None:
    """Enforce the minimum bar floor (`35` bars) before running stationarity & surrogate proofs."""
    if dataset.n_bars < int(min_bars):
        raise InsufficientHistoryError(
            symbol=dataset.symbol,
            timeframe=dataset.canonical_timeframe,
            available_bars=dataset.n_bars,
            minimum_bars=min_bars,
            indicator_name=indicator_name,
        )


def _sanitize_cache_key(symbol: str, provider: str, timeframe: str, bars: int, seed: int) -> str:
    safe_sym = "".join(ch if ch.isalnum() else "_" for ch in symbol).strip("_")
    safe_tf = "".join(ch if ch.isalnum() else "_" for ch in timeframe).strip("_")
    return f"{provider}_{safe_sym}_{safe_tf}_{bars}_s{seed}.parquet"


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

    try:
        pd_freq = get_timeframe_spec(timeframe).synthetic_freq
    except ValueError:
        pd_freq = "1D"
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
    volume = base_vol * (
        1.0 + 35.0 * np.abs(returns) + 20.0 * vol_state + 0.25 * np.abs(rng.standard_normal(bars))
    )

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


def _clean_provider_ohlcv(raw: pd.DataFrame, is_calendar_date: bool) -> pd.DataFrame:
    """Flatten columns, coerce finite OHLCV floats, preserve exchange calendar dates, and sort PIT."""
    flat = _flatten_ohlcv_columns(raw)
    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in flat.columns]
    if missing:
        raise RuntimeError(f"Market data response missing OHLCV columns: {missing}")

    df = flat[required].copy()
    for col in required:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["volume"] = df["volume"].fillna(0.0)
    df = df.dropna(subset=["open", "high", "low", "close"])

    finite_mask = np.all(np.isfinite(df[required].to_numpy(dtype=np.float64)), axis=1)
    df = df.loc[finite_mask].copy()
    if df.empty:
        raise RuntimeError("Market data response contains zero valid finite OHLCV rows.")

    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, utc=True)

    if is_calendar_date:
        # Preserve the exchange-local trading calendar date at 00:00:00 UTC before deduplicating
        local_dates = df.index.tz_localize(None) if df.index.tz is not None else df.index
        df.index = local_dates.normalize().tz_localize("UTC")
    else:
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")

    df = df[~df.index.duplicated(keep="last")].sort_index()
    for col in required:
        df[col] = df[col].astype(np.float64)
    df["high"] = np.maximum(df["high"], np.maximum(df["open"], df["close"]))
    df["low"] = np.minimum(df["low"], np.minimum(df["open"], df["close"]))
    df["volume"] = np.maximum(df["volume"], 0.0)
    df.index.name = "timestamp"
    return df


def _fetch_yfinance(symbol: str, timeframe: str, bars: int) -> tuple[pd.DataFrame, str | None]:
    import yfinance as yf

    spec = get_timeframe_spec(timeframe)
    ticker = yf.Ticker(symbol)
    raw = ticker.history(period=spec.yf_period, interval=spec.yf_interval, auto_adjust=True)
    if raw is None or raw.empty:
        raise RuntimeError(f"yfinance returned empty dataset for symbol='{symbol}' on {spec.label}")

    df = _clean_provider_ohlcv(raw, is_calendar_date=spec.is_calendar_date)
    resampled_from: str | None = None
    if spec.yf_resample_rule is not None:
        df = resample_ohlcv_causal(df, spec.yf_resample_rule)
        resampled_from = spec.yf_interval
        if df.empty:
            raise RuntimeError(
                f"yfinance causal resampling ({spec.yf_resample_rule}) produced 0 bars for '{symbol}'"
            )

    if len(df) > bars:
        df = df.iloc[-bars:].copy()
    return df, resampled_from


def _fetch_ccxt(
    symbol: str,
    timeframe: str,
    bars: int,
    exchange_id: str = "binance",
) -> tuple[pd.DataFrame, str | None]:
    import ccxt

    spec = get_timeframe_spec(timeframe)
    exchange_cls = getattr(ccxt, exchange_id)
    exchange = exchange_cls({"enableRateLimit": True})

    req_tf = spec.ccxt_timeframe
    resample_rule = spec.ccxt_resample_rule
    resampled_from: str | None = None

    exchange_timeframes = getattr(exchange, "timeframes", None)
    if isinstance(exchange_timeframes, dict) and req_tf not in exchange_timeframes:
        # Fall back to daily candles and causally resample when exchange lacks native 1M/1W
        req_tf = "1d"
        resample_rule = spec.synthetic_freq

    fetch_limit = bars
    if resample_rule is not None:
        # Fetch enough daily/source candles to aggregate quarterly or monthly bars
        multiplier = 95 if spec.label == "3M" else (32 if spec.label == "1M" else 8)
        fetch_limit = min(2000, max(bars * multiplier, 365))
        resampled_from = normalize_timeframe(req_tf)

    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=req_tf, limit=fetch_limit)
    if not ohlcv:
        raise RuntimeError(f"ccxt ({exchange_id}) returned empty OHLCV for '{symbol}' on {spec.label}")

    raw = pd.DataFrame(
        ohlcv,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], unit="ms", utc=True)
    raw = raw.set_index("timestamp")

    df = _clean_provider_ohlcv(raw, is_calendar_date=spec.is_calendar_date)
    if resample_rule is not None:
        df = resample_ohlcv_causal(df, resample_rule)
        if df.empty:
            raise RuntimeError(
                f"ccxt causal resampling ({resample_rule}) produced 0 bars for '{symbol}'"
            )

    if len(df) > bars:
        df = df.iloc[-bars:].copy()
    return df, resampled_from


def _inferred_resampled_source(provider: DataProvider, spec: TimeframeSpec) -> str | None:
    if provider == "yfinance" and spec.yf_resample_rule is not None:
        return spec.yf_interval
    if provider == "ccxt" and spec.ccxt_resample_rule is not None:
        return normalize_timeframe(spec.ccxt_timeframe)
    return None


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
    spec = get_timeframe_spec(timeframe)
    canonical_tf = spec.label

    effective_symbol = str(symbol).strip()
    if provider == "yfinance" and effective_symbol.upper().startswith("SYNTH:") and not fallback_to_synthetic:
        effective_symbol = "SPY"
    elif provider == "ccxt" and effective_symbol.upper().startswith("SYNTH:") and not fallback_to_synthetic:
        effective_symbol = "BTC/USDT"

    cache_root = Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_file = cache_root / _sanitize_cache_key(effective_symbol, provider, canonical_tf, bars, seed)

    if use_cache and cache_file.exists():
        cached_df = pd.read_parquet(cache_file)
        if not isinstance(cached_df.index, pd.DatetimeIndex):
            cached_df.index = pd.to_datetime(cached_df.index, utc=True)
        return OHLCVDataset(
            symbol=effective_symbol,
            provider=provider,
            timeframe=canonical_tf,
            df=cached_df,
            cache_path=cache_file,
            requested_bars=bars,
            resampled_from=_inferred_resampled_source(provider, spec),
        )

    effective_provider: DataProvider = provider
    resampled_from: str | None = None
    if provider == "synthetic" or (effective_symbol.upper().startswith("SYNTH:") and fallback_to_synthetic):
        effective_provider = "synthetic"
        df = generate_synthetic_ohlcv(
            symbol=effective_symbol,
            timeframe=canonical_tf,
            bars=bars,
            seed=seed,
        )
    elif provider == "yfinance":
        try:
            df, resampled_from = _fetch_yfinance(
                symbol=effective_symbol,
                timeframe=canonical_tf,
                bars=bars,
            )
        except Exception:
            if not fallback_to_synthetic:
                raise
            effective_provider = "synthetic"
            df = generate_synthetic_ohlcv(
                symbol=effective_symbol,
                timeframe=canonical_tf,
                bars=bars,
                seed=seed,
            )
    elif provider == "ccxt":
        try:
            df, resampled_from = _fetch_ccxt(
                symbol=effective_symbol,
                timeframe=canonical_tf,
                bars=bars,
            )
        except Exception:
            if not fallback_to_synthetic:
                raise
            effective_provider = "synthetic"
            df = generate_synthetic_ohlcv(
                symbol=effective_symbol,
                timeframe=canonical_tf,
                bars=bars,
                seed=seed,
            )
    else:
        raise ValueError(f"Unsupported provider: '{provider}'")

    df.to_parquet(cache_file, index=True)
    return OHLCVDataset(
        symbol=effective_symbol,
        provider=effective_provider,
        timeframe=canonical_tf,
        df=df,
        cache_path=cache_file,
        requested_bars=bars,
        resampled_from=resampled_from,
    )
