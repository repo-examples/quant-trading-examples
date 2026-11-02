"""Unit and integration tests for QuantLab Pipeline Loading Status & Skeleton UI (SPEC-QUANT-LOAD-01)."""

from __future__ import annotations

import pytest

from quantlab.dashboard.app import (
    SPEC_ID,
    PipelineCancelledError,
    PipelineExecutionTelemetry,
    advance_telemetry_stage,
    build_dashboard_bundle,
    build_dashboard_bundle_with_telemetry,
    build_initial_telemetry,
    build_loading_theme_css,
    cancel_telemetry,
    complete_telemetry,
    compute_stage_progress_pct,
    fail_telemetry,
    is_long_running_load,
    render_completed_summary_bar_html,
    render_pipeline_status_card_html,
    render_shimmer_skeletons_html,
    render_warm_dimmed_banner_html,
    update_surrogate_telemetry,
)


def test_us1_weighted_stage_progress_math() -> None:
    """Verify SPEC-QUANT-LOAD-01 weighted stage progress (0 -> 20 -> 40 -> 85 -> 100%)."""
    assert compute_stage_progress_pct(0) == 0.0
    assert compute_stage_progress_pct(1, stage_fraction=0.0) == pytest.approx(0.0)
    assert compute_stage_progress_pct(1, stage_fraction=0.5) == pytest.approx(10.0)
    assert compute_stage_progress_pct(1, stage_fraction=1.0) == pytest.approx(20.0)

    assert compute_stage_progress_pct(2, stage_fraction=0.0) == pytest.approx(20.0)
    assert compute_stage_progress_pct(2, stage_fraction=1.0) == pytest.approx(40.0)

    # SPEC-QUANT-LOAD-01 Section 4 formula check: 40% + 45% * (19 / 30) = 68.5%
    assert compute_stage_progress_pct(3, current_surrogate=0, total_surrogates=30) == pytest.approx(40.0)
    assert compute_stage_progress_pct(3, current_surrogate=19, total_surrogates=30) == pytest.approx(68.5)
    assert compute_stage_progress_pct(3, current_surrogate=30, total_surrogates=30) == pytest.approx(85.0)

    assert compute_stage_progress_pct(4, stage_fraction=0.0) == pytest.approx(85.0)
    assert compute_stage_progress_pct(4, stage_fraction=1.0) == pytest.approx(100.0)
    assert compute_stage_progress_pct(5) == pytest.approx(100.0)


def test_us1_cold_load_status_card_and_shimmer_skeletons_dom() -> None:
    """Verify cold-load status card HTML and 4-card KPI + 360px chart shimmer skeleton HTML."""
    tel = build_initial_telemetry(
        symbol="SYNTH:COUPLED_OU",
        provider="synthetic",
        timeframe="1d",
        bars=600,
        indicator_name="KalmanFilter",
        n_surrogates=30,
        seed=42,
    )
    assert tel.spec_id == SPEC_ID
    assert tel.system_state == "cold_load"
    assert tel.overall_progress_pct == 0.0
    assert len(tel.stages) == 4
    assert tel.stages[0].state == "active"
    assert tel.stages[1].state == "pending"

    # Advance to Stage 3 surrogate 19/30 (68.5%)
    tel_s2 = advance_telemetry_stage(tel, active_stage=2, elapsed_seconds=0.4, completed_stage_duration=0.4)
    tel_s3 = advance_telemetry_stage(tel_s2, active_stage=3, elapsed_seconds=1.2, completed_stage_duration=0.8)
    tel_s3_19 = update_surrogate_telemetry(tel_s3, current_surrogate=19, elapsed_seconds=3.4)
    assert tel_s3_19.overall_progress_pct == pytest.approx(68.5)

    card_html = render_pipeline_status_card_html(tel_s3_19)
    assert 'data-spec-id="SPEC-QUANT-LOAD-01"' in card_html
    assert "Running Quantitative Pipeline for SYNTH:COUPLED_OU (600 bars)..." in card_html
    assert "19 / 30 surrogates • Seed: 42" in card_html
    assert "Elapsed: 00:03.4s" in card_html
    assert "68%" in card_html or "69%" in card_html
    assert "SYNTH:COUPLED_OU" in card_html
    assert "KalmanFilter" in card_html

    skeleton_html = render_shimmer_skeletons_html("SYNTH:COUPLED_OU")
    assert skeleton_html.count('class="ql-kpi-skeleton-card"') == 4
    assert 'class="ql-chart-skeleton"' in skeleton_html
    assert "Awaiting surrogate convergence..." in skeleton_html


def test_us1_end_to_end_pipeline_telemetry_sequence() -> None:
    """Verify build_dashboard_bundle_with_telemetry emits monotonic 0 -> 20 -> 40 -> 85 -> 100% snapshots."""
    bundle, snapshots = build_dashboard_bundle_with_telemetry(
        symbol="SYNTH:COUPLED_OU",
        provider="synthetic",
        bars=220,
        indicator_name="KalmanFilter",
        n_surrogates=12,
        seed=42,
    )
    assert bundle.dataset.n_bars == 220
    # 1 (Stage 1 @ 0%) + 1 (Stage 2 @ 20%) + 1 (Stage 3 @ 40%) + 12 surrogates + 1 (Stage 4 @ 85%) + 1 (Complete @ 100%) = 17
    assert len(snapshots) == 17
    progress_values = [s.overall_progress_pct for s in snapshots]
    assert progress_values[0] == pytest.approx(0.0)
    assert progress_values[1] == pytest.approx(20.0)
    assert progress_values[2] == pytest.approx(40.0)
    assert progress_values[-2] == pytest.approx(85.0)
    assert progress_values[-1] == pytest.approx(100.0)
    assert progress_values == sorted(progress_values)

    final_tel = snapshots[-1]
    assert final_tel.system_state == "completed"
    assert all(st_item.state == "completed" for st_item in final_tel.stages)
    assert all((st_item.duration_seconds or 0.0) >= 0.0 for st_item in final_tel.stages)


def test_us2_warm_reload_mid_run_restart_long_warning_and_summary_bar() -> None:
    """Verify warm-state dimming, mid-run restart badge, long-running warning, and post-load summary bar."""
    assert not is_long_running_load(bars=600, n_surrogates=30, elapsed_seconds=3.0)
    assert is_long_running_load(bars=2000, n_surrogates=30, elapsed_seconds=1.0)
    assert is_long_running_load(bars=600, n_surrogates=80, elapsed_seconds=1.0)
    assert is_long_running_load(bars=600, n_surrogates=30, elapsed_seconds=16.0)

    warm_tel = build_initial_telemetry(
        symbol="SYNTH:COUPLED_OU",
        provider="synthetic",
        timeframe="1d",
        bars=1600,
        indicator_name="PhaseSpaceEnergy",
        n_surrogates=75,
        seed=42,
        is_warm_reload=True,
        restarted_with_updated_params=True,
    )
    assert warm_tel.system_state == "mid_run_restart"
    assert warm_tel.long_running_warning is True

    warm_card_html = render_pipeline_status_card_html(warm_tel)
    assert "Updating PhaseSpaceEnergy &amp; 75 Surrogates..." in warm_card_html
    assert "Restarted pipeline with updated parameters (Monte Carlo Surrogates: 75)" in warm_card_html
    assert "ql-elapsed-badge-amber" in warm_card_html
    assert "High surrogate count or bar history selected. Computation may take ~25s." in warm_card_html

    warm_banner = render_warm_dimmed_banner_html(warm_tel)
    assert 'data-warm-reload="true"' in warm_banner
    assert "Updating PhaseSpaceEnergy &amp; 75 Surrogates" in warm_banner

    completed_tel = complete_telemetry(warm_tel, elapsed_seconds=4.2, stage4_duration=0.6)
    summary_html = render_completed_summary_bar_html(completed_tel)
    assert "Completed in 4.2s" in summary_html
    assert "SYNTH:COUPLED_OU (1600 bars, 75 surrogates)" in summary_html


def test_us3_step_error_recovery_cancellation_and_accessibility() -> None:
    """Verify step-level error telemetry, user cancellation, stage-throttled aria-live, and reduced-motion CSS."""
    emitted: list[PipelineExecutionTelemetry] = []
    with pytest.raises(KeyError):
        build_dashboard_bundle(
            symbol="SYNTH:COUPLED_OU",
            provider="synthetic",
            bars=200,
            indicator_name="NonExistentIndicatorXYZ",
            n_surrogates=10,
            seed=42,
            telemetry_callback=emitted.append,
        )
    assert emitted[-1].system_state == "error"
    assert emitted[-1].error_step == 2
    assert emitted[-1].stages[0].state == "completed"
    assert emitted[-1].stages[1].state == "failed"

    err_html = render_pipeline_status_card_html(emitted[-1])
    assert "Failed at Step 2:" in err_html
    assert "ql-progress-fill-error" in err_html
    assert 'aria-busy="false"' in err_html

    # Test user-initiated cancellation during Stage 3
    cancel_emitted: list[PipelineExecutionTelemetry] = []
    call_counter = 0

    def _should_cancel() -> bool:
        nonlocal call_counter
        call_counter += 1
        return call_counter >= 5

    with pytest.raises(PipelineCancelledError):
        build_dashboard_bundle(
            symbol="SYNTH:COUPLED_OU",
            provider="synthetic",
            bars=200,
            indicator_name="KalmanFilter",
            n_surrogates=15,
            seed=42,
            telemetry_callback=cancel_emitted.append,
            cancel_check=_should_cancel,
        )
    assert cancel_emitted[-1].system_state == "cancelled"
    cancel_html = render_pipeline_status_card_html(cancel_emitted[-1])
    assert "Cancelled Pipeline Run" in cancel_html

    # Also verify direct fail_telemetry & cancel_telemetry helpers
    base_tel = build_initial_telemetry()
    direct_cancel = cancel_telemetry(base_tel, elapsed_seconds=1.1)
    assert direct_cancel.system_state == "cancelled"
    direct_fail = fail_telemetry(base_tel, error_step=3, error_message="Matrix singularity", elapsed_seconds=2.5)
    assert direct_fail.error_step == 3
    assert "Failed at Step 3: Matrix singularity" in direct_fail.aria_announcement

    # Verify ARIA progressbar attributes & stage-throttled aria-live announcements (SC-003: <= 5 distinct announcements)
    _, full_snapshots = build_dashboard_bundle_with_telemetry(
        symbol="SYNTH:COUPLED_OU",
        provider="synthetic",
        bars=200,
        indicator_name="RSI",
        n_surrogates=15,
        seed=42,
    )
    distinct_announcements = []
    for snap in full_snapshots:
        if not distinct_announcements or distinct_announcements[-1] != snap.aria_announcement:
            distinct_announcements.append(snap.aria_announcement)
    assert len(distinct_announcements) == 5

    active_card = render_pipeline_status_card_html(full_snapshots[5])
    assert 'role="region"' in active_card
    assert 'aria-label="Quantitative Pipeline Execution Status"' in active_card
    assert 'aria-busy="true"' in active_card
    assert 'role="progressbar"' in active_card
    assert 'aria-valuemin="0"' in active_card
    assert 'aria-valuemax="100"' in active_card
    assert 'aria-live="polite"' in active_card

    theme_css = build_loading_theme_css()
    assert "@media (prefers-reduced-motion: reduce)" in theme_css
    assert "@media (min-width: 768px) and (max-width: 1023px)" in theme_css
    assert "@media (max-width: 767px)" in theme_css
    assert "opacity: 0.45;" in theme_css
    assert "filter: blur(1px);" in theme_css
