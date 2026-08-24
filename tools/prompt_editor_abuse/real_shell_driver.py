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

"""Measure hostile input through the production-mounted real-shell editor."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from time import perf_counter
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication
from substitute.shared.logging.logger import get_logger
from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.models import PromptFieldHandle
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition

from .execution import execute_mounted_scenario
from .models import (
    PromptAbuseCorrectnessSnapshot,
    PromptAbuseScenario,
    PromptAbuseScenarioResult,
)
from .qt_exception_capture import PromptAbuseQtExceptionCapture
from .real_shell_mount import (
    create_prompt_abuse_real_shell_harness,
    prepare_prompt_abuse_real_shell_mount,
)
from .reorder_visual_correctness import capture_prompt_reorder_visual_violations

_SETTLE_TIMEOUT_MS = 3_000.0
_LOGGER = get_logger(__name__)


def run_real_shell_scenario(
    scenario: PromptAbuseScenario,
    *,
    repetition: int,
    artifact_root: Path,
    deep_trace: bool = False,
) -> PromptAbuseScenarioResult:
    """Run one scenario through real key events and return measured evidence."""

    if scenario.editor_kind != "prompt":
        from .wildcard_driver import run_wildcard_scenario

        return run_wildcard_scenario(
            scenario,
            repetition=repetition,
            artifact_root=artifact_root,
            deep_trace=deep_trace,
        )
    harness = create_prompt_abuse_real_shell_harness(
        scenario,
        artifact_root=artifact_root,
    )
    exception_capture = PromptAbuseQtExceptionCapture()
    try:
        with exception_capture:
            mounted = prepare_prompt_abuse_real_shell_mount(
                harness,
                scenario,
                alias=f"abuse-{scenario.name}-{repetition}",
            )
            field = mounted.field
            result = execute_mounted_scenario(
                scenario,
                repetition=repetition,
                editor=field.editor,
                target=mounted.target,
                settle=lambda expected: _settle_editor(field.editor, expected),
                capture_correctness=lambda: _capture_real_shell_correctness(
                    harness,
                    field,
                    scenario=scenario,
                    repetition=repetition,
                ),
                deep_trace_enabled=deep_trace,
                action_host=mounted.action_host,
            )
            harness.wait_for_queued_delivery()
    finally:
        harness.close()
    visual_violations = capture_prompt_reorder_visual_violations(
        scenario,
        artifact_root=artifact_root,
    )
    if visual_violations:
        result = replace(
            result,
            invariant_violations=tuple(
                dict.fromkeys(result.invariant_violations + visual_violations)
            ),
        )
    if exception_capture.violations:
        result = replace(
            result,
            invariant_violations=tuple(
                dict.fromkeys(
                    result.invariant_violations + exception_capture.violations
                )
            ),
        )
    if deep_trace:
        from .diagnostic_driver import capture_scenario_diagnostics
        from .freshness_driver import capture_freshness_diagnostics

        diagnostics = capture_scenario_diagnostics(
            scenario,
            repetition=repetition,
            artifact_root=artifact_root,
        )
        result = replace(
            result,
            diagnostics=replace(
                diagnostics,
                freshness_samples=capture_freshness_diagnostics(
                    scenario,
                    repetition=repetition,
                    artifact_root=artifact_root,
                ),
            ),
        )
    return result


def qt_platform_name() -> str:
    """Return the Qt platform used by the real-shell campaign."""

    return str(QGuiApplication.platformName())


def _settle_editor(editor: object, expected_source: str) -> tuple[float, bool]:
    """Process queued work until authoritative prompt owners become current."""

    started_at = perf_counter()
    try:
        wait_for_qt_condition(
            lambda: _editor_is_current(editor, expected_source),
            timeout_ms=int(_SETTLE_TIMEOUT_MS),
            description="prompt abuse semantic, projection, and shell owners to settle",
            state=lambda: _editor_settlement_state(editor, expected_source),
        )
    except AssertionError as error:
        elapsed_ms = (perf_counter() - started_at) * 1_000.0
        _LOGGER.warning("Prompt abuse editor settlement timed out: %s", error)
        return elapsed_ms, False
    return (perf_counter() - started_at) * 1_000.0, True


def _editor_is_current(editor: object, expected_source: str) -> bool:
    """Return whether semantic, projection, and shell-geometry owners are idle."""

    prompt_editor = cast(Any, editor)
    if prompt_editor.toPlainText() != expected_source:
        return False
    surface = prompt_editor._surface
    if surface.projection_document().source_text != expected_source:
        return False
    if (
        surface._projection_freshness_controller.has_pending_update()
        or surface.has_stale_projection_geometry()
        or prompt_editor._sizing.layout_work_pending
        or prompt_editor._scroll_delegate.geometry_sync_pending
        or prompt_editor._scroll_delegate.geometry_follow_up_pending
    ):
        return False
    semantic_refresh = prompt_editor._interaction_controller._semantic_refresh
    semantic_source = surface.editor_state.semantic.document.source_text
    return (
        semantic_source == expected_source
        and semantic_refresh._pending_request is None
        and semantic_refresh._active_task_identity is None
    )


def _editor_settlement_state(editor: object, expected_source: str) -> dict[str, object]:
    """Return exact owner state when bounded prompt settlement fails."""

    prompt_editor = cast(Any, editor)
    surface = prompt_editor._surface
    sizing = prompt_editor._sizing
    scroll_delegate = prompt_editor._scroll_delegate
    semantic_refresh = prompt_editor._interaction_controller._semantic_refresh
    return {
        "source_current": prompt_editor.toPlainText() == expected_source,
        "projection_current": (
            surface.projection_document().source_text == expected_source
        ),
        "projection_update_pending": (
            surface._projection_freshness_controller.has_pending_update()
        ),
        "projection_geometry_stale": surface.has_stale_projection_geometry(),
        "sizing_work_pending": sizing.layout_work_pending,
        "shell_geometry_sync_pending": scroll_delegate.geometry_sync_pending,
        "shell_geometry_follow_up_pending": (
            scroll_delegate.geometry_follow_up_pending
        ),
        "semantic_current": (
            surface.editor_state.semantic.document.source_text == expected_source
        ),
        "semantic_refresh_pending": semantic_refresh._pending_request is not None,
        "semantic_refresh_active": semantic_refresh._active_task_identity is not None,
    }


def _capture_real_shell_correctness(
    harness: PromptEditorRealShellScenario,
    field: PromptFieldHandle,
    *,
    scenario: PromptAbuseScenario,
    repetition: int,
) -> PromptAbuseCorrectnessSnapshot:
    """Capture authoritative real-shell editor state and invariant failures."""

    snapshot = harness.snapshots.capture(
        field,
        label=f"{scenario.name}-repetition-{repetition}",
    )
    prompt_editor = cast(Any, field.editor)
    return PromptAbuseCorrectnessSnapshot(
        actual_text=snapshot.source_text,
        projection_current=(
            prompt_editor._surface.projection_document().source_text
            == scenario.expected_text
        ),
        semantic_current=(
            prompt_editor._surface.editor_state.semantic.document.source_text
            == scenario.expected_text
        ),
        invariant_violations=snapshot_invariant_violations(snapshot),
    )


__all__ = ["qt_platform_name", "run_real_shell_scenario"]
