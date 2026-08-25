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

"""Verify real-shell prompt-editor owner-state observability."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget
from qfluentwidgets import ToolTipFilter  # type: ignore[import-untyped]

from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_captures_headless_editor_and_popup_state(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Capture shell, editor, and popup state without screenshot dependencies."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text_and_wait_for_autocomplete(field, "re")
    snapshot = real_shell_scenario.snapshots.capture(field, label="after-re")

    assert snapshot.geometries["shell"] is not None
    assert snapshot.geometries["editor"] is not None
    assert snapshot.popup_widget_exists
    assert snapshot.popup_state_visible
    assert snapshot.popup_visual_visible
    assert snapshot.autocomplete_gateway_calls


def test_real_shell_moves_ambient_hover_to_neutral_target(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Cancel delayed shell tooltips before driving prompt keyboard input."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    tooltip_owner = next(
        widget
        for widget in real_shell_scenario.shell.findChildren(QWidget)
        if widget.isVisible()
        and bool(widget.toolTip())
        and widget.findChildren(ToolTipFilter)
    )
    tooltip_filters = tooltip_owner.findChildren(ToolTipFilter)
    QTest.mouseMove(tooltip_owner, tooltip_owner.rect().center())
    assert any(tooltip_filter.timer.isActive() for tooltip_filter in tooltip_filters)

    real_shell_scenario.input.focus_editor(field)

    assert all(
        not tooltip_filter.timer.isActive() for tooltip_filter in tooltip_filters
    )


def test_real_shell_can_disable_hot_path_owner_tracing(tmp_path: Path) -> None:
    """Allow primary performance probes to omit deep owner-call tracing."""

    real_shell_scenario = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        observe_owner_calls=False,
    )
    try:
        field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
        real_shell_scenario.input.type_text(field, "fast exact input")
        snapshot = real_shell_scenario.snapshots.capture(field, label="untraced")

        assert snapshot.source_text == "fast exact input"
        assert snapshot.recent_observed_events == ()
        assert snapshot.observed_event_end_index == 0
        assert not snapshot_invariant_violations(snapshot)
    finally:
        real_shell_scenario.close()
