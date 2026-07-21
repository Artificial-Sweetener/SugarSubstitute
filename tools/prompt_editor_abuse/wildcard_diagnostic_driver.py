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

"""Capture actionable profiler evidence from production wildcard editors."""

from __future__ import annotations

import cProfile
from pathlib import Path
from typing import Any, cast

from .action_driver import dispatch_action
from .models import (
    PromptAbuseActionProfile,
    PromptAbuseDiagnostics,
    PromptAbuseScenario,
)
from .profile_summary import summarize_combined_hotspots, summarize_hotspots
from .reorder_action_host import PromptReorderAbuseActionHost
from .wildcard_mount import mount_wildcard_editor


def capture_wildcard_scenario_diagnostics(
    scenario: PromptAbuseScenario,
    *,
    artifact_root: Path,
) -> PromptAbuseDiagnostics:
    """Replay one wildcard scenario with profiler and overlay-owner counters."""

    with mount_wildcard_editor(scenario, artifact_root=artifact_root) as mounted:
        host = PromptReorderAbuseActionHost()
        action_profilers: list[cProfile.Profile] = []
        action_profiles: list[PromptAbuseActionProfile] = []
        reorder_overlay: Any | None = None
        for action_index, action in enumerate(scenario.actions):
            profiler = cProfile.Profile()
            profiler.enable()
            try:
                dispatch_action(
                    host,
                    mounted.editor,
                    mounted.editor,
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
            active_overlay = cast(Any, mounted.editor)._segment_overlay
            if active_overlay is not None:
                reorder_overlay = active_overlay
        counters = (
            ()
            if reorder_overlay is None
            else _numeric_owner_counters(reorder_overlay.reorder_performance_counters())
        )
    return PromptAbuseDiagnostics(
        canonical_rebuild_count=0,
        apply_path_counts=(),
        incremental_rejection_counts=(),
        layout_rejection_counts=(),
        hotspots=summarize_combined_hotspots(action_profilers),
        owner_counters=counters,
        action_profiles=tuple(action_profiles),
    )


def _numeric_owner_counters(
    counters: dict[str, object],
) -> tuple[tuple[str, float], ...]:
    """Return deterministic numeric counters suitable for JSON diagnostics."""

    return tuple(
        (name, float(value))
        for name, value in sorted(counters.items())
        if isinstance(value, int | float) and not isinstance(value, bool)
    )


__all__ = ["capture_wildcard_scenario_diagnostics"]
