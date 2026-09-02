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

"""Verify prompt field actions through the production node-card cog."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget
from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
    RoundMenu,
)

from substitute.presentation.editor.panel.node_card.action_menu import (
    NodeCardActionMenuButton,
)
from tests.presentation.editor.node_card.support import title_row_for
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_node_cog_contains_prompt_actions_without_editor_commands(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The mounted cog should project prompt semantics but not text-edit chrome."""

    scenario = PromptEditorRealShellScenario(artifact_root=tmp_path)
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)
    try:
        field = scenario.workflows.add_prompt_workflow(initial_text="portrait")
        panel = scenario.shell.editor_panels[field.workflow.workflow_id]
        wrapper = cast(
            QWidget,
            cast(Any, panel).card_wrappers[
                (field.workflow.cube_alias, field.node_name)
            ],
        )
        title_row = title_row_for(wrapper)
        button = title_row.findChild(NodeCardActionMenuButton)
        assert button is not None

        button.click()

        binding = getattr(title_row, "_node_card_action_menu_binding")
        root_menu = cast(Any, binding)._active_menu
        top_level_labels = _top_level_labels(root_menu)
        assert "Rich prompt rendering" in top_level_labels
        assert "Value" not in top_level_labels
        assert top_level_labels.isdisjoint(
            {"Undo", "Redo", "Cut", "Copy", "Paste", "Select all"}
        )
    finally:
        scenario.close()


def _top_level_labels(menu: Any) -> set[str]:
    """Return action and submenu labels rendered directly in one menu."""

    labels: set[str] = set()
    for row in range(menu.view.count()):
        value = menu.view.item(row).data(Qt.ItemDataRole.UserRole)
        if isinstance(value, QAction):
            labels.add(value.text())
            continue
        title = getattr(value, "title", None)
        if callable(title):
            labels.add(str(title()))
    return labels
