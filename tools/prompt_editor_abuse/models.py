#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Define immutable prompt-editor abuse campaign inputs and results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


type PromptAbuseActionKind = Literal[
    "type",
    "paste",
    "key",
    "key_press",
    "key_release",
    "key_chord",
    "select",
    "move_cursor",
    "resize",
    "scroll",
    "focus_cycle",
    "workflow_round_trip",
    "canvas_round_trip",
    "reorder_drag_press",
    "reorder_drag_threshold",
    "reorder_drag_move",
    "reorder_drag_release",
    "reorder_drag_autoscroll",
    "reorder_drag_cancel",
    "request_paint",
    "display_mode",
    "search_highlights",
    "mouse_caret",
    "mouse_drag_selection",
    "wheel_weight",
    "lora_picker_open",
    "lora_picker_activate",
    "refresh_diagnostics",
    "context_menu",
    "context_menu_trigger",
    "context_menu_trigger_cached",
    "event_turn",
    "drain_events",
]
type PromptAbuseEditorKind = Literal["prompt", "wildcard_txt", "wildcard_csv"]
type PromptAbuseWheelMode = Literal["hover_dwell", "focus_required"]
type PromptAbuseFixtureFeature = Literal[
    "wildcard_catalog",
    "lora_catalog",
    "spellcheck",
    "danbooru_import",
    "danbooru_wiki",
    "scheduled_lora",
]
type PromptAbuseLatencyClass = Literal[
    "text_input",
    "interaction",
    "lifecycle",
    "backlog_drain",
]


@dataclass(frozen=True, slots=True)
class PromptAbuseAction:
    """Describe one user-like interaction and its exact source checkpoint."""

    kind: PromptAbuseActionKind
    value: str = ""
    position: int | None = None
    selection_end: int | None = None
    viewport_size: tuple[int, int] | None = None
    source_ranges: tuple[tuple[int, int], ...] = ()
    active_index: int | None = None
    expected_source: str | None = None
    expected_cursor_position: int | None = None
    expected_anchor_position: int | None = None
    expected_scene_titles: tuple[str, ...] | None = None
    expected_diagnostics: tuple[tuple[str, int, int], ...] | None = None
    expected_context_labels: tuple[str, ...] | None = None
    expected_token_kinds: tuple[str, ...] | None = None
    expected_reorder_chip_texts: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        """Reject action payloads that cannot be dispatched deterministically."""

        if (
            self.kind
            in {
                "type",
                "paste",
                "key",
                "key_press",
                "key_release",
                "key_chord",
                "reorder_drag_press",
                "reorder_drag_move",
                "wheel_weight",
            }
            and not self.value
        ):
            raise ValueError(f"Prompt abuse {self.kind} action requires a value.")
        if (
            self.kind
            in {
                "move_cursor",
                "select",
                "mouse_caret",
                "mouse_drag_selection",
                "context_menu",
                "context_menu_trigger",
            }
            and self.position is None
        ):
            raise ValueError(f"Prompt abuse {self.kind} action requires a position.")
        if (
            self.kind in {"context_menu_trigger", "context_menu_trigger_cached"}
            and not self.value
        ):
            raise ValueError(
                "Prompt abuse context-menu trigger requires an action label."
            )
        if self.kind == "wheel_weight" and self.value not in {"up", "down"}:
            raise ValueError("Prompt abuse wheel-weight action requires up or down.")
        if (
            self.kind in {"select", "mouse_drag_selection"}
            and self.selection_end is None
        ):
            raise ValueError(
                f"Prompt abuse {self.kind} action requires a selection end."
            )
        if self.kind == "resize" and self.viewport_size is None:
            raise ValueError("Prompt abuse resize action requires a viewport size.")
        if self.kind == "display_mode" and self.value not in {"raw", "rich"}:
            raise ValueError("Prompt abuse display mode must be raw or rich.")
        if self.kind == "search_highlights" and self.value not in {"set", "clear"}:
            raise ValueError("Prompt abuse search action must set or clear highlights.")
        if self.kind == "search_highlights" and self.value == "set":
            if not self.source_ranges:
                raise ValueError("Prompt abuse search set requires source ranges.")
            if self.active_index is not None and not (
                0 <= self.active_index < len(self.source_ranges)
            ):
                raise ValueError("Prompt abuse active search index is out of range.")
        if self.kind == "scroll" and self.value not in {"top", "middle", "bottom"}:
            raise ValueError("Prompt abuse scroll action requires a valid target.")


@dataclass(frozen=True, slots=True)
class PromptAbuseScenario:
    """Describe one synthetic production-mounted interaction workload."""

    name: str
    initial_text: str
    actions: tuple[PromptAbuseAction, ...]
    expected_text: str
    cursor_position: int = 0
    viewport_size: tuple[int, int] = (720, 240)
    editor_kind: PromptAbuseEditorKind = "prompt"
    fixture_features: tuple[PromptAbuseFixtureFeature, ...] = ()
    wheel_mode: PromptAbuseWheelMode = "hover_dwell"
    seed: int | None = None

    def __post_init__(self) -> None:
        """Reject scenarios whose edit position lies outside the source."""

        if not self.name:
            raise ValueError("Prompt abuse scenario name must not be empty.")
        if not 0 <= self.cursor_position <= len(self.initial_text):
            raise ValueError("Prompt abuse cursor position lies outside its source.")
        if not self.actions:
            raise ValueError("Prompt abuse scenario requires at least one action.")


@dataclass(frozen=True, slots=True)
class PromptAbuseDispatchSample:
    """Record low-overhead timing and correctness for one dispatched input unit."""

    action_index: int
    unit_index: int
    label: str
    dispatch_ms: float
    source_exact: bool
    caret_exact: bool
    selection_exact: bool = True
    feature_exact: bool = True
    latency_class: PromptAbuseLatencyClass = "text_input"
    actual_source_on_mismatch: str | None = None
    actual_cursor_position: int | None = None
    expected_cursor_position: int | None = None
    actual_anchor_position: int | None = None
    expected_anchor_position: int | None = None
    feature_mismatch: str | None = None
    projection_current_after_dispatch: bool | None = None
    semantic_current_after_dispatch: bool | None = None
    visible_source_current_after_dispatch: bool | None = None
    visible_caret_current_after_dispatch: bool | None = None
    active_projection_ownership_valid: bool | None = None
    layout_projection_ownership_valid: bool | None = None
    layout_fragment_ownership_valid: bool | None = None
    layout_fragment_ownership_mismatch: str | None = None
    caret_transform_depth: int | None = None
    caret_transform_depth_valid: bool | None = None
    transient_overlay_kind: str | None = None
    projection_freshness: str | None = None
    allocated_block_delta: int = 0
    gc_collection_count: int = 0
    gc_collected_objects: int = 0
    gc_pause_ms: float = 0.0
    dispatch_thread_cpu_ms: float | None = None


@dataclass(frozen=True, slots=True)
class PromptAbuseLatencySummary:
    """Summarize one scenario's key-dispatch latency distribution."""

    p50_ms: float
    p95_ms: float
    p99_ms: float
    maximum_ms: float


@dataclass(frozen=True, slots=True)
class PromptAbuseLatencyBreakdown:
    """Separate user input latency from lifecycle and explicit drain costs."""

    text_input: PromptAbuseLatencySummary
    interaction: PromptAbuseLatencySummary
    lifecycle: PromptAbuseLatencySummary
    backlog_drain: PromptAbuseLatencySummary
    text_input_count: int
    interaction_count: int
    lifecycle_count: int
    backlog_drain_count: int


@dataclass(frozen=True, slots=True)
class PromptAbuseHotspot:
    """Describe one cumulative profiler hotspot from a diagnostic replay."""

    function: str
    call_count: int
    own_time_ms: float
    cumulative_time_ms: float
    callers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PromptAbuseActionProfile:
    """Record profiler hotspots attributed to one hostile action."""

    action_index: int
    label: str
    hotspots: tuple[PromptAbuseHotspot, ...]


@dataclass(frozen=True, slots=True)
class PromptAbuseFreshnessSample:
    """Record first-correct owner publication after one instrumented action."""

    action_index: int
    label: str
    projection_ms: float
    semantic_ms: float
    fully_current_ms: float
    projection_was_immediate: bool
    semantic_was_immediate: bool
    timed_out: bool


@dataclass(frozen=True, slots=True)
class PromptAbuseDiagnostics:
    """Record projection decisions and profiler evidence from a replay."""

    canonical_rebuild_count: int
    apply_path_counts: tuple[tuple[str, int], ...]
    incremental_rejection_counts: tuple[tuple[str, int], ...]
    layout_rejection_counts: tuple[tuple[str, int], ...]
    hotspots: tuple[PromptAbuseHotspot, ...]
    freshness_samples: tuple[PromptAbuseFreshnessSample, ...] = ()
    owner_counters: tuple[tuple[str, float], ...] = ()
    action_profiles: tuple[PromptAbuseActionProfile, ...] = ()


@dataclass(frozen=True, slots=True)
class PromptAbuseActionOwnerDelta:
    """Attribute monotonic owner work to one hostile dispatch unit."""

    action_index: int
    unit_index: int
    label: str
    counter_deltas: tuple[tuple[str, float], ...]
    reset_counter_names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PromptAbuseCorrectnessSnapshot:
    """Record final authoritative editor-owner agreement for one scenario."""

    actual_text: str
    projection_current: bool
    semantic_current: bool
    invariant_violations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PromptAbuseScenarioResult:
    """Record correctness and timing evidence from one scenario repetition."""

    scenario: PromptAbuseScenario
    repetition: int
    dispatch_samples: tuple[PromptAbuseDispatchSample, ...]
    latency: PromptAbuseLatencySummary
    burst_dispatch_ms: float
    settle_ms: float
    actual_text_on_mismatch: str | None
    projection_current: bool
    semantic_current: bool
    invariant_violations: tuple[str, ...]
    deep_trace_enabled: bool
    diagnostics: PromptAbuseDiagnostics | None = None
    latency_breakdown: PromptAbuseLatencyBreakdown | None = None
    action_owner_deltas: tuple[PromptAbuseActionOwnerDelta, ...] = ()
    structural_violations: tuple[str, ...] = ()

    @property
    def correct(self) -> bool:
        """Return whether source and editor invariants remained correct."""

        return (
            self.actual_text_on_mismatch is None
            and self.projection_current
            and self.semantic_current
            and not self.invariant_violations
            and all(
                sample.source_exact
                and sample.caret_exact
                and sample.selection_exact
                and sample.feature_exact
                and sample.visible_source_current_after_dispatch is not False
                and sample.visible_caret_current_after_dispatch is not False
                and sample.active_projection_ownership_valid is not False
                and sample.layout_projection_ownership_valid is not False
                and sample.layout_fragment_ownership_valid is not False
                and sample.caret_transform_depth_valid is not False
                for sample in self.dispatch_samples
            )
        )


@dataclass(frozen=True, slots=True)
class PromptAbuseSystemLoad:
    """Record campaign-wide CPU pressure that affects timing confidence."""

    elapsed_seconds: float
    logical_cpu_count: int
    system_cpu_percent: float
    harness_cpu_percent: float
    competing_cpu_percent: float

    @property
    def contended(self) -> bool:
        """Return whether competing work materially contaminated wall timings."""

        return self.competing_cpu_percent >= 20.0


@dataclass(frozen=True, slots=True)
class PromptAbuseCampaignReport:
    """Record reproducible environment and scenario evidence for one run."""

    revision: str
    qt_platform: str
    seed: int
    frame_budget_ms: float
    results: tuple[PromptAbuseScenarioResult, ...]
    covered_operations: tuple[str, ...] = ()
    missing_operations: tuple[str, ...] = ()
    system_load: PromptAbuseSystemLoad | None = None
    structural_probe_enabled: bool = False

    @property
    def correctness_passed(self) -> bool:
        """Return whether every scenario repetition preserved correctness."""

        return all(result.correct for result in self.results)

    @property
    def timing_target_passed(self) -> bool:
        """Return whether observed latencies fit the configured reference target."""

        return all(
            _result_fits_frame_budget(result, self.frame_budget_ms)
            for result in self.results
        )

    @property
    def structural_performance_passed(self) -> bool:
        """Return whether every operation stayed within its owner-work budget."""

        return all(not result.structural_violations for result in self.results)

    @property
    def timing_evidence_representative(self) -> bool:
        """Return whether measured contention permits timing conclusions."""

        return (
            not self.structural_probe_enabled
            and self.system_load is not None
            and not self.system_load.contended
        )


def _result_fits_frame_budget(
    result: PromptAbuseScenarioResult,
    frame_budget_ms: float,
) -> bool:
    """Return whether each populated latency lane stays within one frame."""

    breakdown = result.latency_breakdown
    if breakdown is None:
        return _latency_fits_frame_budget(result.latency, frame_budget_ms)
    lanes = (
        (breakdown.text_input_count, breakdown.text_input),
        (breakdown.interaction_count, breakdown.interaction),
        (breakdown.lifecycle_count, breakdown.lifecycle),
        (breakdown.backlog_drain_count, breakdown.backlog_drain),
    )
    return all(
        count == 0 or _latency_fits_frame_budget(latency, frame_budget_ms)
        for count, latency in lanes
    )


def _latency_fits_frame_budget(
    latency: PromptAbuseLatencySummary,
    frame_budget_ms: float,
) -> bool:
    """Return whether central and tail latency stay within bounded frame costs."""

    return bool(
        latency.p95_ms <= frame_budget_ms
        and latency.p99_ms <= frame_budget_ms * 1.5
        and latency.maximum_ms <= frame_budget_ms * 2.0
    )


__all__ = [
    "PromptAbuseCampaignReport",
    "PromptAbuseCorrectnessSnapshot",
    "PromptAbuseAction",
    "PromptAbuseActionProfile",
    "PromptAbuseActionOwnerDelta",
    "PromptAbuseActionKind",
    "PromptAbuseDispatchSample",
    "PromptAbuseDiagnostics",
    "PromptAbuseEditorKind",
    "PromptAbuseFixtureFeature",
    "PromptAbuseWheelMode",
    "PromptAbuseFreshnessSample",
    "PromptAbuseHotspot",
    "PromptAbuseLatencySummary",
    "PromptAbuseLatencyBreakdown",
    "PromptAbuseLatencyClass",
    "PromptAbuseScenario",
    "PromptAbuseScenarioResult",
    "PromptAbuseSystemLoad",
]
