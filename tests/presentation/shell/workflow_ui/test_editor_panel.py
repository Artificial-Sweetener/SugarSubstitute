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

"""Verify editor-panel composition for workflow surfaces."""

from __future__ import annotations

from typing import cast

import pytest

from substitute.presentation.shell.workflow_ui_factory import WorkflowUiFactory
from tests.presentation.shell.workflow_ui.support import (
    FakeEditorPanel,
    build_workflow_shell,
    install_signal_binder,
)


def test_create_editor_panel_passes_shell_dependencies_and_wires_panel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preserve editor dependencies and shell signal wiring."""
    created_panels: list[FakeEditorPanel] = []

    def editor_panel_factory(**kwargs: object) -> FakeEditorPanel:
        """Create and record one editor panel."""
        panel = FakeEditorPanel(**kwargs)
        created_panels.append(panel)
        return panel

    monkeypatch.setattr(
        "substitute.presentation.shell.workflow_ui_factory.EditorPanel",
        editor_panel_factory,
    )
    shell = build_workflow_shell()
    install_signal_binder(monkeypatch, shell)

    panel = WorkflowUiFactory(shell).create_editor_panel("wf-1")

    fake_panel = cast(FakeEditorPanel, panel)
    assert fake_panel is created_panels[0]
    assert fake_panel.kwargs["workflow_id"] == "wf-1"
    assert fake_panel.kwargs["node_definition_gateway"] is shell.node_definition_gateway
    assert fake_panel.kwargs["node_presentation_service"] is (
        shell.node_presentation_service
    )
    assert fake_panel.kwargs["wheel_adjustment_mode"] == "precise"
    assert fake_panel.kwargs["error_presenter"] is shell._error_presenter
    assert fake_panel.kwargs["editor_panel_execution_factories"] is (
        shell.editor_panel_execution_factories
    )
    contributors = cast(
        tuple[object, ...],
        fake_panel.kwargs["node_card_body_contributors"],
    )
    assert len(contributors) == 1
    assert fake_panel.mainwindow is shell
    assert fake_panel.minimum_widths == [412]
    assert shell.connected_editor_panels == [fake_panel]
