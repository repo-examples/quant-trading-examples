"""Unit and integration tests for SPEC-CHART-TV-01, SPEC-CTRL-TF-02, and SPEC-UI-HELP-03."""

from __future__ import annotations

import json
import re
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from quantlab.dashboard.app import (
    CHART_HELP_REGISTRY,
    SPEC_HELP_ID,
    SPEC_TF_ID,
    SPEC_TV_ID,
    InsufficientHistoryError,
    _render_dashboard_workspace_content,
    build_chart_help_css,
    build_dashboard_bundle,
    build_initial_telemetry,
    build_lightweight_charts_canvas_html,
    complete_telemetry,
    get_chart_help,
    render_chart_header,
    render_chart_help_popover_html,
    render_completed_summary_bar_html,
    render_insufficient_history_html,
    serialize_lightweight_charts_series,
)
from quantlab.data.loader import OHLCVDataset, generate_synthetic_ohlcv


def test_spec_chart_tv_01_calendar_and_intraday_serialization_with_warmup_whitespace() -> None:
    """Verify YYYY-MM-DD strings on 1D/1W/1M/3M, int UTC seconds on intraday, and whitespace warm-up dicts."""
    for cal_tf in ("1D", "1W", "1M", "3M"):
        df_cal = generate_synthetic_ohlcv(timeframe=cal_tf, bars=50, seed=42)
        ds_cal = OHLCVDataset(symbol="SPY", provider="yfinance", timeframe=cal_tf, df=df_cal)
        ind = np.linspace(-2.0, 3.5, 50)
        ind[:12] = np.nan
        ind[15] = np.inf

        candles, ind_pts = serialize_lightweight_charts_series(ds_cal, ind)
        assert len(candles) == 50
        assert len(ind_pts) == 50

        times = [c["time"] for c in candles]
        assert all(isinstance(t, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", t) for t in times)
        assert times == sorted(set(times))

        # Leading warm-up NaNs and Inf become Lightweight Charts whitespace objects (no 'value', never 0.0)
        for idx in range(12):
            assert ind_pts[idx] == {"time": times[idx]}
            assert "value" not in ind_pts[idx]
        assert ind_pts[15] == {"time": times[15]}
        assert "value" in ind_pts[12] and np.isfinite(float(ind_pts[12]["value"]))  # type: ignore[arg-type]

    # Intraday 1h uses strictly increasing UTC Unix epoch seconds
    df_1h = generate_synthetic_ohlcv(timeframe="1h", bars=45, seed=42)
    ds_1h = OHLCVDataset(symbol="SPY", provider="yfinance", timeframe="1h", df=df_1h)
    c_1h, i_1h = serialize_lightweight_charts_series(ds_1h, np.ones(45))
    intraday_times = [c["time"] for c in c_1h]
    assert all(isinstance(t, int) and t > 1_700_000_000 for t in intraday_times)
    assert intraday_times == sorted(set(intraday_times))
    assert len(i_1h) == 45


def test_spec_chart_tv_01_canvas_html_legend_a11y_and_empty_state() -> None:
    """Verify Lightweight Charts HTML5 canvas tokens, legend, ResizeObserver, touch guard, a11y, and empty card."""
    bundle = build_dashboard_bundle(
        symbol="SYNTH:COUPLED_OU",
        provider="synthetic",
        timeframe="1W",
        bars=120,
        indicator_name="MACD",
        n_surrogates=10,
        seed=42,
    )
    html_str = bundle.lightweight_charts_html
    assert f'data-spec-id="{SPEC_TV_ID}"' in html_str
    assert 'role="img"' in html_str
    assert "TradingView OHLCV and MACD chart for SYNTH:COUPLED_OU on 1W timeframe, 120 bars" in html_str
    assert 'id="tv-legend"' in html_str
    assert "subscribeCrosshairMove" in html_str
    assert "ResizeObserver" in html_str
    assert "chart.timeScale().fitContent()" in html_str
    assert "vertTouchDrag: !isTouchOrMobile" in html_str
    assert "minBarSpacing: 2" in html_str
    assert "#10B981" in html_str
    assert "#FF2E93" in html_str
    assert "#1E222D" in html_str
    assert "#9CA3AF" in html_str

    # Verify MACD warm-up bars in serialized JSON do not coerce NaNs to 0.0 if NaNs exist, and JSON parses cleanly
    match = re.search(r"const candles = (\[.*?\]);", html_str, flags=re.DOTALL)
    assert match is not None
    parsed_candles = json.loads(match.group(1))
    assert len(parsed_candles) == 120
    assert isinstance(parsed_candles[0]["time"], str)

    # Simulate empty/corrupted non-finite rows after dataset construction to trigger 0-candle empty card
    mut_df = bundle.dataset.df.copy()
    object.__setattr__(bundle.dataset, "df", mut_df.iloc[0:0])
    empty_html = build_lightweight_charts_canvas_html(bundle.dataset, bundle.active_proof)
    assert "Empty TradingView OHLCV chart state" in empty_html
    assert "No market data returned for SYNTH:COUPLED_OU on 1W" in empty_html


def test_spec_ctrl_tf_02_pipeline_35_bar_guard_and_clamped_badges(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify < 35 bar datasets halt proof execution at Stage 1 and clamped/resampled pills render cleanly."""
    assert SPEC_TF_ID == "SPEC-CTRL-TF-02"

    short_df = generate_synthetic_ohlcv(timeframe="3M", bars=32, seed=5)
    short_ds = OHLCVDataset(
        symbol="RECENT_IPO",
        provider="yfinance",
        timeframe="3M",
        df=short_df,
        requested_bars=600,
    )
    monkeypatch.setattr("quantlab.dashboard.app.fetch_ohlcv", lambda **kwargs: short_ds)

    telemetry_events = []
    with pytest.raises(InsufficientHistoryError, match="RECENT_IPO only has 32 bars on 3M"):
        build_dashboard_bundle(
            symbol="RECENT_IPO",
            provider="yfinance",
            timeframe="3M",
            bars=600,
            indicator_name="MACD",
            n_surrogates=10,
            seed=42,
            telemetry_callback=telemetry_events.append,
            fallback_to_synthetic=False,
        )

    assert telemetry_events[-1].system_state == "error"
    assert telemetry_events[-1].error_step == 1

    callout_html = render_insufficient_history_html(
        symbol="RECENT_IPO",
        timeframe="3M",
        available_bars=32,
        minimum_bars=35,
        indicator_name="MACD",
    )
    assert 'role="alert"' in callout_html
    assert "Insufficient history: RECENT_IPO only has 32 bars on 3M" in callout_html
    assert "Switch to 1W or 1D." in callout_html

    tel = complete_telemetry(
        build_initial_telemetry(symbol="SPY", provider="yfinance", timeframe="3M", bars=600, indicator_name="MACD"),
        elapsed_seconds=1.8,
        stage4_duration=0.3,
    )
    summary_clamped = render_completed_summary_bar_html(
        tel,
        available_bars=135,
        requested_bars=600,
        resampled_from="1D",
        timeframe_label="3M",
    )
    assert "Using all 135 available 3M bars for SPY (requested 600)." in summary_clamped
    assert "Resampled 3M bars from 1D history." in summary_clamped
    assert "ql-clamped-pill" in summary_clamped
    assert "ql-resampled-pill" in summary_clamped


def test_spec_ui_help_03_registry_fallback_headers_and_collision_free_plotly() -> None:
    """Verify all 9 CHART_HELP_REGISTRY panels, fallback copy, header rendering, Plotly layout, and dark config."""
    expected_ids = {"TV-01", "Q1A", "Q1B", "Q2A", "Q2B", "Q3A", "Q3B", "Q3C", "Q4A"}
    assert set(CHART_HELP_REGISTRY.keys()) == expected_ids

    for cid in expected_ids:
        entry = get_chart_help(cid, indicator_name="KalmanFilter")
        assert entry.what_it_is
        assert entry.axes_and_visuals
        assert entry.how_to_interpret

        pop_html = render_chart_help_popover_html(
            chart_id=cid,
            indicator_name="KalmanFilter",
            context_summary="SPY • 1W • KalmanFilter",
        )
        assert f'data-spec-id="{SPEC_HELP_ID}"' in pop_html
        assert "1. What It Is:" in pop_html
        assert "2. Axes &amp; Visuals:" in pop_html
        assert "3. How to Interpret:" in pop_html
        assert "SPY • 1W • KalmanFilter" in pop_html

    # Missing registry key fallback
    fallback = get_chart_help("UNREGISTERED-99", indicator_name="PhaseSpaceEnergy")
    assert "Quantitative diagnostic chart for PhaseSpaceEnergy. Detailed guide pending." in fallback.what_it_is

    css_text = build_chart_help_css()
    assert "min-width: 36px" in css_text
    assert "min-width: 44px" in css_text
    assert "max-height: 60vh" in css_text

    # Verify .streamlit/config.toml dark-mode lock exists
    config_toml = (Path(__file__).resolve().parents[1] / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'base = "dark"' in config_toml
    assert 'backgroundColor = "#0E1117"' in config_toml

    # Verify headerless collision-free Plotly figures & color-blind safe Q3B styling
    bundle = build_dashboard_bundle(
        symbol="SYNTH:COUPLED_OU",
        provider="synthetic",
        timeframe="1D",
        bars=200,
        indicator_name="KalmanFilter",
        n_surrogates=10,
        seed=42,
    )
    for fig in (
        bundle.fig_q1_ohlcv,
        bundle.fig_q1_phase_space,
        bundle.fig_q2_rolling_entropy,
        bundle.fig_q2_surrogates,
        bundle.fig_q3_ic_vif,
        bundle.fig_q3_wasserstein,
        bundle.fig_q3_pareto_bode,
    ):
        assert fig.layout.title.text is None
        assert fig.layout.margin.t >= 48
        assert fig.layout.legend.orientation == "h"
        assert fig.layout.legend.x == 0.0

    bull_trace, bear_trace = bundle.fig_q3_wasserstein.data
    assert bull_trace.marker.line.width > 0
    assert bear_trace.marker.line.width > 0
    assert bear_trace.marker.pattern.shape == "/"

    # Verify full workspace render mounts all 9 chart headers & popovers cleanly
    class MockColumn:
        def __init__(self, parent: MockStreamlit) -> None:
            self._p = parent

        def __enter__(self) -> MockColumn:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def metric(self, *args: object, **kwargs: object) -> None:
            self._p.metrics.append((args, kwargs))

    class MockStreamlit:
        def __init__(self) -> None:
            self.session_state: dict[str, Any] = {"ql_timeframe": "1D"}
            self.markdowns: list[str] = []
            self.popovers: list[tuple[str, str | None]] = []
            self.metrics: list[Any] = []
            self.plotly_keys: list[str] = []

        def markdown(self, body: str, **kwargs: object) -> None:
            _ = kwargs
            self.markdowns.append(body)

        def columns(self, spec: int | list[float], **kwargs: object) -> list[MockColumn]:
            _ = kwargs
            n = spec if isinstance(spec, int) else len(spec)
            return [MockColumn(self) for _ in range(n)]

        def tabs(self, names: list[str]) -> list[Any]:
            return [nullcontext() for _ in names]

        def popover(self, label: str, help: str | None = None, **kwargs: object) -> Any:
            _ = kwargs
            self.popovers.append((label, help))
            return nullcontext()

        def pills(self, label: str, options: list[str], default: str | None = None, **kwargs: object) -> str | None:
            _ = (label, options, kwargs)
            return default

        def plotly_chart(self, fig: object, **kwargs: object) -> None:
            _ = fig
            self.plotly_keys.append(str(kwargs.get("key", "")))

        def text_input(self, label: str, value: str = "", **kwargs: object) -> str:
            _ = (label, kwargs)
            return value

        def latex(self, body: str) -> None:
            self.markdowns.append(body)

        def code(self, body: str, **kwargs: object) -> None:
            _ = kwargs
            self.markdowns.append(body)

        def download_button(self, *args: object, **kwargs: object) -> bool:
            _ = (args, kwargs)
            return False

        def error(self, msg: str) -> None:
            raise AssertionError(f"Unexpected st.error: {msg}")

        def rerun(self) -> None:
            return None

    class MockComponents:
        def __init__(self) -> None:
            self.html_calls: list[str] = []

        def html(self, body: str, **kwargs: object) -> None:
            _ = kwargs
            self.html_calls.append(body)

    mock_st = MockStreamlit()
    mock_comp = MockComponents()
    render_chart_header(mock_st, "TV-01", indicator_name="KalmanFilter")
    assert len(mock_st.popovers) == 1

    mock_st_ws = MockStreamlit()
    _render_dashboard_workspace_content(
        mock_st_ws,
        mock_comp,
        bundle,
        selected_ind="KalmanFilter",
        dimmed=False,
        key_suffix="test",
    )
    assert len(mock_st_ws.popovers) == 9
    assert len(mock_comp.html_calls) == 1
    assert len(mock_st_ws.plotly_keys) == 7
