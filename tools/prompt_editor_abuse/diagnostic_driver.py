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

"""Replay one hostile scenario with isolated actionable instrumentation."""

from __future__ import annotations

import cProfile
from pathlib import Path
from typing import Any, cast

from substitute.presentation.editor.prompt_editor.layout.contracts import (
    PromptLayoutDamage,
)
from substitute.presentation.editor.prompt_editor.layout.models import (
    PromptProjectionLineSnapshot,
)

from .action_driver import dispatch_action
from .models import (
    PromptAbuseActionProfile,
    PromptAbuseDiagnostics,
    PromptAbuseScenario,
)
from .profile_summary import (
    summarize_combined_hotspots,
    summarize_counts,
    summarize_hotspots,
)
from .real_shell_mount import (
    create_prompt_abuse_real_shell_harness,
    prepare_prompt_abuse_real_shell_mount,
)


def capture_scenario_diagnostics(
    scenario: PromptAbuseScenario,
    *,
    repetition: int,
    artifact_root: Path,
) -> PromptAbuseDiagnostics:
    """Return projection-path and profiler evidence from an isolated replay."""

    harness = create_prompt_abuse_real_shell_harness(
        scenario,
        artifact_root=artifact_root,
    )
    try:
        mounted = prepare_prompt_abuse_real_shell_mount(
            harness,
            scenario,
            alias=f"diagnose-{scenario.name}-{repetition}",
        )
        field = mounted.field
        target = mounted.target
        action_host = mounted.action_host
        surface = cast(Any, field.editor)._surface
        edit_pipeline = surface._edit_pipeline
        original_rebuild = surface._projection_applicator.rebuild_projection
        original_apply = edit_pipeline.apply
        original_incremental_paint = (
            surface._update_incremental_plain_text_projection_paint
        )
        canonical_rebuild_count = 0
        apply_paths: list[str] = []
        incremental_rejections: list[str] = []
        layout_rejections: list[str] = []
        reflowed_line_counts: list[int] = []
        reflow_mismatch_reasons: list[str] = []
        layout_coordinator = surface._layout

        def counted_rebuild(*args: Any, **kwargs: Any) -> object:
            """Count and invoke one production canonical projection rebuild."""

            nonlocal canonical_rebuild_count
            canonical_rebuild_count += 1
            return original_rebuild(*args, **kwargs)

        def recorded_apply(request: object) -> object:
            """Record the projection decision and its local rejection evidence."""

            outcome = original_apply(request)
            apply_paths.append(str(outcome.apply_path.value))
            incremental_rejections.append(str(outcome.incremental_rejection_reason))
            return outcome

        def recorded_incremental_paint(
            layout_result: PromptLayoutDamage,
        ) -> object:
            """Record bounded-reflow scope before invoking production painting."""

            reflowed_line_counts.append(int(layout_result.reflowed_line_count))
            return original_incremental_paint(layout_result)

        def record_line_mismatch(
            next_line: PromptProjectionLineSnapshot,
            previous_line: PromptProjectionLineSnapshot,
            *,
            source_delta: int,
            projection_delta: int,
        ) -> None:
            """Record why one diagnostic suffix-convergence probe missed."""

            reflow_mismatch_reasons.append(
                _line_reflow_mismatch_reason(
                    next_line,
                    previous_line,
                    source_delta=source_delta,
                    projection_delta=projection_delta,
                )
            )

        def record_layout_rejection(reason: str) -> None:
            """Record one rejected incremental frame transition."""

            layout_rejections.append(reason)

        surface._projection_applicator.rebuild_projection = counted_rebuild
        edit_pipeline.apply = recorded_apply
        surface._update_incremental_plain_text_projection_paint = (
            recorded_incremental_paint
        )
        layout_coordinator.set_reflow_mismatch_observer(record_line_mismatch)
        layout_coordinator.set_incremental_rejection_observer(record_layout_rejection)
        action_profilers: list[cProfile.Profile] = []
        action_profiles: list[PromptAbuseActionProfile] = []
        try:
            for action_index, action in enumerate(scenario.actions):
                profiler = cProfile.Profile()
                profiler.enable()
                try:
                    dispatch_action(
                        action_host,
                        field.editor,
                        target,
                        action,
                        action_index=action_index,
                        runtime_telemetry=True,
                    )
                finally:
                    profiler.disable()
                action_profilers.append(profiler)
                action_profiles.append(
                    PromptAbuseActionProfile(
                        action_index=action_index,
                        label=f"{action.kind}:{action.value or ''}",
                        hotspots=summarize_hotspots(profiler),
                    )
                )
        finally:
            surface._projection_applicator.rebuild_projection = original_rebuild
            edit_pipeline.apply = original_apply
            surface._update_incremental_plain_text_projection_paint = (
                original_incremental_paint
            )
            layout_coordinator.set_reflow_mismatch_observer(None)
            layout_coordinator.set_incremental_rejection_observer(None)

        return PromptAbuseDiagnostics(
            canonical_rebuild_count=canonical_rebuild_count,
            apply_path_counts=summarize_counts(apply_paths),
            incremental_rejection_counts=summarize_counts(incremental_rejections),
            layout_rejection_counts=summarize_counts(layout_rejections),
            hotspots=summarize_combined_hotspots(action_profilers),
            owner_counters=(
                ("projection.reflow_count", float(len(reflowed_line_counts))),
                (
                    "projection.reflowed_lines_total",
                    float(sum(reflowed_line_counts)),
                ),
                (
                    "projection.reflowed_lines_max",
                    float(max(reflowed_line_counts, default=0)),
                ),
                *tuple(
                    (f"projection.reflow_{index}_lines", float(line_count))
                    for index, line_count in enumerate(reflowed_line_counts)
                ),
                *tuple(
                    (f"projection.mismatch.{reason}", float(count))
                    for reason, count in summarize_counts(reflow_mismatch_reasons)
                ),
            ),
            action_profiles=tuple(action_profiles),
        )
    finally:
        harness.close()


def _line_reflow_mismatch_reason(
    next_line: PromptProjectionLineSnapshot,
    previous_line: PromptProjectionLineSnapshot,
    *,
    source_delta: int,
    projection_delta: int,
) -> str:
    """Return the first actionable reason two diagnostic lines did not converge."""

    if abs(next_line.height - previous_line.height) > 0.01:
        return "line_height"
    source_fields = (
        "source_start",
        "source_end",
        "source_content_start",
        "source_content_end",
    )
    if any(
        getattr(next_line, field) != getattr(previous_line, field) + source_delta
        for field in source_fields
    ):
        return "source_bounds"
    if len(next_line.fragments) != len(previous_line.fragments):
        return "fragment_count"
    for next_fragment, previous_fragment in zip(
        next_line.fragments,
        previous_line.fragments,
        strict=True,
    ):
        if type(next_fragment) is not type(previous_fragment):
            return "fragment_type"
        if next_fragment.run_id != previous_fragment.run_id:
            return "run_id"
        if next_fragment.token_id != previous_fragment.token_id:
            return "token_id"
        if (
            next_fragment.projection_start
            != previous_fragment.projection_start + projection_delta
            or next_fragment.projection_end
            != previous_fragment.projection_end + projection_delta
        ):
            return "projection_bounds"
        if len(next_fragment.source_positions) != len(
            previous_fragment.source_positions
        ) or any(
            next_position != previous_position + source_delta
            for next_position, previous_position in zip(
                next_fragment.source_positions,
                previous_fragment.source_positions,
                strict=True,
            )
        ):
            return "fragment_source_positions"
        if (
            abs(next_fragment.rect.left() - previous_fragment.rect.left()) > 0.01
            or abs(next_fragment.rect.width() - previous_fragment.rect.width()) > 0.01
            or abs(next_fragment.rect.height() - previous_fragment.rect.height()) > 0.01
        ):
            return "fragment_geometry"
    if len(next_line.caret_stops) != len(previous_line.caret_stops):
        return "caret_count"
    if any(
        next_stop.projection_position
        != previous_stop.projection_position + projection_delta
        for next_stop, previous_stop in zip(
            next_line.caret_stops,
            previous_line.caret_stops,
            strict=True,
        )
    ):
        return "caret_position"
    return "caret_geometry_or_flags"


__all__ = ["capture_scenario_diagnostics"]
