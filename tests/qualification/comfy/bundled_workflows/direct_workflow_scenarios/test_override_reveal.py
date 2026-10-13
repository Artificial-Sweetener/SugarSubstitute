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

"""Qualify retained node controls after global overrides relinquish visibility."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from PySide6.QtGui import QAction

from substitute.application.direct_workflows import DirectWorkflowGenerationPlanService
from substitute.domain.workspace_snapshot.codecs import workflow_state_to_json
from substitute.presentation.widgets import DoubleSpinBox, SeedBox
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.overrides import (
    override_surface,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.shell import (
    DirectWorkflowShell,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.workflows import (
    load_direct_workflow,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_scenarios.support import (
    deterministic_sdxl_fixture,
)


@pytest.mark.parametrize(
    ("override", "field", "value"), [("seed", "noise_seed", 42), ("cfg", "cfg", 6.25)]
)
def test_unpin_reveals_current_numeric_values_without_editing_workflow(
    tmp_path: Path, override: str, field: str, value: int | float
) -> None:
    """Unpinning must expose the applied graph value, preserving locks and edits."""

    harness = DirectWorkflowShell(tmp_path)
    try:
        fixture = deterministic_sdxl_fixture()
        load_direct_workflow(
            harness,
            fixture.path,
            node_definitions=fixture.node_definitions,
            expected_node_names=frozenset(
                prompt.node_name for prompt in fixture.expected_prompts
            )
            | {"11"},
        )
        shell = harness.shell
        manager = shell.active_override_manager
        panel = shell.active_editor_panel
        workflow = shell.get_active_workflow()
        assert manager is not None and workflow is not None and panel is not None
        assert workflow.direct_workflow is not None
        fields = cast(
            dict[tuple[str, str, str], object],
            getattr(panel, "input_widgets_by_field_key"),
        )
        controls = [
            cast(SeedBox | DoubleSpinBox, widget)
            for key, widget in fields.items()
            if key[2] == field
        ]
        assert len(controls) == 2
        for widget in controls:
            if isinstance(widget, SeedBox):
                widget.setMode("fixed")
        action = QAction(parent=panel)
        action.setData({"override_key": override})
        action.setCheckable(True)
        action.setChecked(True)
        manager._on_override_menu_toggled(action)
        _, toolbar = override_surface(harness, harness.direct_workflow_id, override)
        if isinstance(toolbar, SeedBox):
            toolbar.setValue(int(value))
        else:
            cast(DoubleSpinBox, toolbar).setValue(float(value))
        harness.process_events()
        emitted: list[object] = []
        for widget in controls:
            widget.valueChanged.connect(emitted.append)
        before = workflow_state_to_json(workflow)
        graph = DirectWorkflowGenerationPlanService().build(workflow.direct_workflow)
        action.setChecked(False)
        manager._on_override_menu_toggled(action)
        harness.wait_until(
            lambda: not panel.is_projection_active(), description="unpin reveal"
        )
        assert all(
            widget.isVisible() and widget.value() == value for widget in controls
        )
        assert not emitted
        for widget in controls:
            if isinstance(widget, SeedBox):
                assert widget.mode() == "fixed"
        after = workflow_state_to_json(workflow)
        # Unpin owns override participation; graph, modes and dirty state stay put.
        before.pop("global_overrides")
        after.pop("global_overrides")
        before.pop("global_override_selections")
        after.pop("global_override_selections")
        assert after == before
        assert (
            DirectWorkflowGenerationPlanService()
            .build(workflow.direct_workflow)
            .authored_api_graph
            == graph.authored_api_graph
        )
    finally:
        harness.close()
