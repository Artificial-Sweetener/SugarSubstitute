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

"""Replay actions with per-action projection and semantic publication timing."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any, cast

from tests.support.qt.semantic_wait import wait_for_qt_condition

from .action_driver import dispatch_action
from .models import PromptAbuseFreshnessSample, PromptAbuseScenario
from .real_shell_mount import (
    create_prompt_abuse_real_shell_harness,
    prepare_prompt_abuse_real_shell_mount,
)

_FRESHNESS_TIMEOUT_MS = 3_000.0


def capture_freshness_diagnostics(
    scenario: PromptAbuseScenario,
    *,
    repetition: int,
    artifact_root: Path,
) -> tuple[PromptAbuseFreshnessSample, ...]:
    """Return instrumented first-correct publication timing for each action."""

    harness = create_prompt_abuse_real_shell_harness(
        scenario,
        artifact_root=artifact_root,
    )
    try:
        mounted = prepare_prompt_abuse_real_shell_mount(
            harness,
            scenario,
            alias=f"freshness-{scenario.name}-{repetition}",
        )
        field = mounted.field
        samples: list[PromptAbuseFreshnessSample] = []
        for action_index, action in enumerate(scenario.actions):
            dispatch_action(
                mounted.action_host,
                field.editor,
                mounted.target,
                action,
                action_index=action_index,
            )
            samples.append(
                _wait_for_current_owners(
                    field.editor,
                    action_index=action_index,
                    label=f"{action.kind}:{action.value[:24]}",
                )
            )
        return tuple(samples)
    finally:
        harness.close()


def _wait_for_current_owners(
    editor: object,
    *,
    action_index: int,
    label: str,
) -> PromptAbuseFreshnessSample:
    """Wait until projection and semantics first agree with current source."""

    started_at = perf_counter()
    projection_ms: float | None = None
    semantic_ms: float | None = None
    prompt_editor = cast(Any, editor)

    def observe_current_owners() -> bool:
        """Record each owner's first current observation and report completion."""

        nonlocal projection_ms, semantic_ms
        elapsed_ms = (perf_counter() - started_at) * 1_000.0
        source_text = str(prompt_editor.toPlainText())
        if projection_ms is None and _projection_is_current(prompt_editor, source_text):
            projection_ms = elapsed_ms
        if semantic_ms is None and _semantics_are_current(prompt_editor, source_text):
            semantic_ms = elapsed_ms
        return projection_ms is not None and semantic_ms is not None

    timed_out = False
    try:
        wait_for_qt_condition(
            observe_current_owners,
            timeout_ms=int(_FRESHNESS_TIMEOUT_MS),
            description="prompt projection and semantic owners to become current",
            state=lambda: {
                "projection_ms": projection_ms,
                "semantic_ms": semantic_ms,
            },
        )
    except AssertionError:
        timed_out = True
    elapsed_ms = (perf_counter() - started_at) * 1_000.0
    resolved_projection_ms = elapsed_ms if projection_ms is None else projection_ms
    resolved_semantic_ms = elapsed_ms if semantic_ms is None else semantic_ms
    return PromptAbuseFreshnessSample(
        action_index=action_index,
        label=label,
        projection_ms=resolved_projection_ms,
        semantic_ms=resolved_semantic_ms,
        fully_current_ms=max(resolved_projection_ms, resolved_semantic_ms),
        projection_was_immediate=(projection_ms is not None and projection_ms < 0.1),
        semantic_was_immediate=semantic_ms is not None and semantic_ms < 0.1,
        timed_out=timed_out,
    )


def _projection_is_current(editor: Any, source_text: str) -> bool:
    """Return whether projection source and pending-work state are current."""

    surface = editor._surface
    return bool(
        surface.projection_document().source_text == source_text
        and not surface._projection_freshness_controller.has_pending_update()
    )


def _semantics_are_current(editor: Any, source_text: str) -> bool:
    """Return whether semantic source and pending task state are current."""

    interaction = editor._interaction_controller
    refresh = interaction._semantic_refresh
    return bool(
        editor._surface.editor_state.semantic.document.source_text == source_text
        and refresh._pending_request is None
        and refresh._active_task_identity is None
    )


__all__ = ["capture_freshness_diagnostics"]
