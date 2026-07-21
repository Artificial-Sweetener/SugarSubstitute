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

"""Measure hostile input in the production wildcard-management editor."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from time import perf_counter
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop
from PySide6.QtGui import QGuiApplication

from substitute.application.managed_text_assets.wildcard_csv_document_parser import (
    parse_wildcard_csv_document,
)
from substitute.application.prompt_editor import PromptDiagnosticKind
from .execution import execute_mounted_scenario
from .models import (
    PromptAbuseCorrectnessSnapshot,
    PromptAbuseScenario,
    PromptAbuseScenarioResult,
)
from .qt_exception_capture import PromptAbuseQtExceptionCapture
from .reorder_action_host import PromptReorderAbuseActionHost
from .wildcard_mount import mount_wildcard_editor, process_events
from .wildcard_visual_correctness import capture_wildcard_visual_violations

_SETTLE_TIMEOUT_MS = 3_000.0


def run_wildcard_scenario(
    scenario: PromptAbuseScenario,
    *,
    repetition: int,
    artifact_root: Path,
    deep_trace: bool = False,
) -> PromptAbuseScenarioResult:
    """Run one TXT or CSV scenario through the production wildcard modal."""

    exception_capture = PromptAbuseQtExceptionCapture()
    with exception_capture:
        with mount_wildcard_editor(scenario, artifact_root=artifact_root) as mounted:
            editor = mounted.editor
            result = execute_mounted_scenario(
                scenario,
                repetition=repetition,
                editor=editor,
                target=editor,
                settle=lambda expected: _settle_editor(editor, expected),
                capture_correctness=lambda: _capture_correctness(editor, scenario),
                deep_trace_enabled=deep_trace,
                action_host=PromptReorderAbuseActionHost(),
            )
            process_events(cycles=4)
        visual_violations = capture_wildcard_visual_violations(
            scenario,
            artifact_root=artifact_root,
        )
    result = replace(
        result,
        invariant_violations=tuple(
            dict.fromkeys(
                result.invariant_violations
                + visual_violations
                + exception_capture.violations
            )
        ),
    )
    if deep_trace:
        from .wildcard_diagnostic_driver import (
            capture_wildcard_scenario_diagnostics,
        )

        result = replace(
            result,
            diagnostics=capture_wildcard_scenario_diagnostics(
                scenario,
                artifact_root=artifact_root,
            ),
        )
    return result


def _settle_editor(editor: Any, expected_source: str) -> tuple[float, bool]:
    """Drain queued work until wildcard source, projection, and semantics agree."""

    started_at = perf_counter()
    while not _editor_is_current(editor, expected_source):
        elapsed_ms = (perf_counter() - started_at) * 1_000.0
        if elapsed_ms >= _SETTLE_TIMEOUT_MS:
            return elapsed_ms, False
        app = QGuiApplication.instance()
        if app is not None:
            app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 1)
    return (perf_counter() - started_at) * 1_000.0, True


def _editor_is_current(editor: Any, expected_source: str) -> bool:
    """Return whether every wildcard editor source owner is current."""

    surface = editor._surface
    interaction = editor._interaction_controller
    semantic_refresh = interaction._semantic_refresh
    return bool(
        editor.toPlainText() == expected_source
        and surface._projection_document.source_text == expected_source
        and not surface._projection_freshness_controller.has_pending_update()
        and interaction._syntax_state.document_view.source_text == expected_source
        and semantic_refresh._pending_request is None
        and semantic_refresh._active_task_identity is None
    )


def _capture_correctness(
    editor: Any,
    scenario: PromptAbuseScenario,
) -> PromptAbuseCorrectnessSnapshot:
    """Capture wildcard semantics, diagnostics, and projection invariants."""

    editor._diagnostics_feature_controller.refresh_now()
    process_events(cycles=8)
    source_text = str(editor.toPlainText())
    projection = editor._surface.projection_document()
    diagnostics = editor._diagnostics_feature_controller.snapshot.diagnostics
    violations: list[str] = []
    if any(token.kind.value == "scene" for token in projection.tokens):
        violations.append("wildcard_projected_scene_token")
    if "**" in scenario.expected_text and not any(
        diagnostic.kind is PromptDiagnosticKind.UNSUPPORTED_SCENE_MARKER
        for diagnostic in diagnostics
    ):
        violations.append("wildcard_scene_marker_missing_error")
    if (
        scenario.editor_kind == "wildcard_csv"
        and not parse_wildcard_csv_document(source_text).valid
    ):
        violations.append("wildcard_csv_became_invalid")
    return PromptAbuseCorrectnessSnapshot(
        actual_text=source_text,
        projection_current=projection.source_text == scenario.expected_text,
        semantic_current=(
            editor._interaction_controller._syntax_state.document_view.source_text
            == scenario.expected_text
        ),
        invariant_violations=tuple(violations),
    )


__all__ = ["run_wildcard_scenario"]
