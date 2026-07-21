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

from PySide6.QtCore import QEventLoop
from PySide6.QtGui import QGuiApplication
from tests.real_shell_prompt_editor_harness import (
    PromptFieldHandle,
    RealShellPromptEditorHarness,
)

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
            harness.process_events(cycles=4)
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
    while not _editor_is_current(editor, expected_source):
        elapsed_ms = (perf_counter() - started_at) * 1_000.0
        if elapsed_ms >= _SETTLE_TIMEOUT_MS:
            return elapsed_ms, False
        app = QGuiApplication.instance()
        if app is not None:
            app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 1)
    return (perf_counter() - started_at) * 1_000.0, True


def _editor_is_current(editor: object, expected_source: str) -> bool:
    """Return whether source, projection, and semantic-refresh owners agree."""

    prompt_editor = cast(Any, editor)
    if prompt_editor.toPlainText() != expected_source:
        return False
    surface = prompt_editor._surface
    if surface._projection_document.source_text != expected_source:
        return False
    if surface._projection_freshness_controller.has_pending_update():
        return False
    semantic_refresh = prompt_editor._interaction_controller._semantic_refresh
    semantic_source = (
        prompt_editor._interaction_controller._syntax_state.document_view.source_text
    )
    return (
        semantic_source == expected_source
        and semantic_refresh._pending_request is None
        and semantic_refresh._active_task_identity is None
    )


def _capture_real_shell_correctness(
    harness: RealShellPromptEditorHarness,
    field: PromptFieldHandle,
    *,
    scenario: PromptAbuseScenario,
    repetition: int,
) -> PromptAbuseCorrectnessSnapshot:
    """Capture authoritative real-shell editor state and invariant failures."""

    snapshot = harness.capture_state_snapshot(
        field,
        label=f"{scenario.name}-repetition-{repetition}",
    )
    prompt_editor = cast(Any, field.editor)
    return PromptAbuseCorrectnessSnapshot(
        actual_text=snapshot.source_text,
        projection_current=(
            prompt_editor._surface._projection_document.source_text
            == scenario.expected_text
        ),
        semantic_current=(
            prompt_editor._interaction_controller._syntax_state.document_view.source_text
            == scenario.expected_text
        ),
        invariant_violations=harness.invariant_violations(snapshot),
    )


__all__ = ["qt_platform_name", "run_real_shell_scenario"]
