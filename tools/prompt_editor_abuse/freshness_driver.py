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

from PySide6.QtCore import QEventLoop
from PySide6.QtGui import QGuiApplication

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
    while True:
        elapsed_ms = (perf_counter() - started_at) * 1_000.0
        source_text = str(prompt_editor.toPlainText())
        if projection_ms is None and _projection_is_current(prompt_editor, source_text):
            projection_ms = elapsed_ms
        if semantic_ms is None and _semantics_are_current(prompt_editor, source_text):
            semantic_ms = elapsed_ms
        if projection_ms is not None and semantic_ms is not None:
            return PromptAbuseFreshnessSample(
                action_index=action_index,
                label=label,
                projection_ms=projection_ms,
                semantic_ms=semantic_ms,
                fully_current_ms=max(projection_ms, semantic_ms),
                projection_was_immediate=projection_ms < 0.1,
                semantic_was_immediate=semantic_ms < 0.1,
                timed_out=False,
            )
        if elapsed_ms >= _FRESHNESS_TIMEOUT_MS:
            return PromptAbuseFreshnessSample(
                action_index=action_index,
                label=label,
                projection_ms=(elapsed_ms if projection_ms is None else projection_ms),
                semantic_ms=(elapsed_ms if semantic_ms is None else semantic_ms),
                fully_current_ms=elapsed_ms,
                projection_was_immediate=(
                    projection_ms is not None and projection_ms < 0.1
                ),
                semantic_was_immediate=(semantic_ms is not None and semantic_ms < 0.1),
                timed_out=True,
            )
        app = QGuiApplication.instance()
        if app is not None:
            app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 1)


def _projection_is_current(editor: Any, source_text: str) -> bool:
    """Return whether projection source and pending-work state are current."""

    surface = editor._surface
    return bool(
        surface._projection_document.source_text == source_text
        and not surface._projection_freshness_controller.has_pending_update()
    )


def _semantics_are_current(editor: Any, source_text: str) -> bool:
    """Return whether semantic source and pending task state are current."""

    interaction = editor._interaction_controller
    refresh = interaction._semantic_refresh
    return bool(
        interaction._syntax_state.document_view.source_text == source_text
        and refresh._pending_request is None
        and refresh._active_task_identity is None
    )


__all__ = ["capture_freshness_diagnostics"]
