# UX & Data Serialization Requirements Checklist: QuantLab Chart UX, Multi-Timeframe Controls & Contextual Help

**Purpose**: Reviewer-grade requirements quality audit covering `SPEC-CHART-TV-01` (Lightweight Charts serialization & states), `SPEC-CTRL-TF-02` (multi-timeframe mapping & sample guards), and `SPEC-UI-HELP-03` (contextual chart help & header collision prevention)
**Created**: 2026-11-10
**Feature**: [spec.md](../spec.md)

**Note**: Generated using `Depth: Standard`, `Audience: Reviewer (PR)`, `Focus: Multi-Timeframe Serialization & Dashboard UX/Accessibility`.
**Review Ownership**: This checklist is a requirements-quality review artifact audited against `spec.md`, `plan.md`, `data-model.md`, and `contracts/`.
**Marker Semantics**: `[x]` confirms the requirement-quality criterion is explicitly and unambiguously satisfied in the specification and design artifacts.

## Requirement Completeness

- [x] CHK001 Are all supported canonical UI timeframes (`15m`, `1h`, `4h`, `1D`, `1W`, `1M`, `3M`) and backwards-compatible CLI aliases (`1d`, `1w`, `1wk`, `1mo`, `3mo`) explicitly enumerated? [Completeness, Spec §FR-001, §FR-010]
- [x] CHK002 Is the complete inventory of panels requiring standardized headers and `?` help popovers (`TV-01`, `Q1A`, `Q1B`, `Q2A`, `Q2B`, `Q3A`, `Q3B`, `Q3C`, `Q4A`) documented without omissions? [Completeness, Spec §FR-012, §FR-013]
- [x] CHK003 Are all three required microcopy blocks (`1. What It Is`, `2. Axes & Visuals`, `3. How to Interpret`) specified for every entry in `CHART_HELP_REGISTRY`? [Completeness, Spec §FR-013]

## Requirement Clarity

- [x] CHK004 Is the distinction between calendar-date serialization (`YYYY-MM-DD` for `1D`, `1W`, `1M`, `3M`) and UTC Unix epoch-second serialization (for intraday intervals) unambiguously defined? [Clarity, Spec §FR-007]
- [x] CHK005 Is the handling of non-finite (`NaN`/`Inf`) indicator warm-up rows quantified as time-aligned whitespace entries (`{"time": bar_time}`) rather than `0.0` or `null`? [Clarity, Spec §FR-008]
- [x] CHK006 Is the minimum sample-size threshold for statistical proofs (`35` bars) explicitly quantified alongside exact user-facing recovery copy? [Clarity, Spec §FR-005]

## Requirement Consistency

- [x] CHK007 Are provider interval mappings consistent so uppercase `1M` always maps to 1-Month (`1mo`) rather than 1-minute intraday candles across UI and loader layers? [Consistency, Spec §FR-002, Data Model §1]
- [x] CHK008 Are state synchronization requirements consistent between the left sidebar `Timeframe` selector, the Q1 quick-switcher bar, status pills, and URL query parameters? [Consistency, Spec §FR-010, §FR-011]
- [x] CHK009 Do chart header placement requirements align with figure margin and legend adjustments to prevent title/toolbar overlap? [Consistency, Spec §FR-012, §FR-014]

## Acceptance Criteria Quality & Measurability

- [x] CHK010 Can blank-canvas prevention and warm-up axis accuracy be objectively verified across providers and timeframes? [Measurability, Spec §SC-001, §SC-002]
- [x] CHK011 Are timeframe switching click-count and state-parity outcomes measurable without referencing internal implementation mechanics? [Acceptance Criteria, Spec §SC-003]

## Scenario & Edge Case Coverage

- [x] CHK012 Are requirements specified for partial/clamped history (`35 <= available < requested` bars on `1M`/`3M`) vs. insufficient history (`< 35` bars)? [Coverage, Spec §FR-005, §FR-006]
- [x] CHK013 Is causal OHLCV aggregation (`open=first`, `high=max`, `low=min`, `close=last`, `volume=sum`) and user badge notification defined when a provider lacks native higher-timeframe intervals? [Edge Case, Spec §FR-003]
- [x] CHK014 Is graceful fallback behavior defined when an unregistered chart ID is requested from `CHART_HELP_REGISTRY` or when zero valid candles are available? [Exception Flow, Spec §FR-009, §FR-013]

## Non-Functional & Accessibility Requirements

- [x] CHK015 Are screen-reader semantics (`role="img"`, dynamic `aria-label` summary on financial canvas, unique accessible labels on `?` triggers) and mobile touch-scroll guards (`vertTouchDrag: false`) specified? [Non-Functional, Spec §FR-009, §FR-012]
- [x] CHK016 Are color-vision deficiency distinguishability requirements (distinct border strokes/patterns on `Q3B` Bull vs. Bear histograms) and dark-theme lock constraints specified? [Non-Functional, Spec §FR-015]

## Notes

- All 16 requirements-quality checks (`CHK001`–`CHK016`) audited and verified against `spec.md`, `plan.md`, `data-model.md`, and `contracts/chart-ux-and-timeframe-contracts.md`. Gate cleared for `/speckit-tasks` and `/speckit-implement`.
