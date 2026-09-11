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

"""Exercise shared regional names through the production prompt editor shell."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLineEdit

from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.interactions.region_inline_editor import (
    REGION_NAME_INLINE_EDITOR_OBJECT_NAME,
)
from substitute.presentation.regional.canvas_hover_presenter import (
    RegionalCanvasHoverPresenter,
)
from substitute.presentation.regional.interaction_coordinator import (
    RegionalInteractionCoordinator,
)
from tests.application.workflows.regional_prompt.support import build_workflow
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)
from tests.support.prompt_editor.real_shell.models import (
    PromptFieldHandle,
    PromptWorkflowHandle,
)


class _UnusedMaskColorTarget:
    """Provide the canvas boundary unused by separator-name scenarios."""

    def set_mask_properties(self, _mask_id: UUID, *, color: QColor) -> bool:
        """Reject unused hover projection while satisfying the production port."""

        _ = color
        return False


def test_related_prompt_names_stay_identical_through_restore_undo_and_redo(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Prove mounted peer editors and graph values share every name transition."""

    workflow = build_workflow("P\n[SEP|Subject]\npositive", mask_count=1)
    negative_inputs = _prompt_inputs(workflow, "negative")
    negative_inputs["value"] = "N\n[SEP]\nnegative"
    shell = real_shell_scenario.shell
    shell.node_definition_gateway.install_recorded_definitions(
        {
            "PrimitiveStringMultiline": {
                "input": {
                    "required": {
                        "value": [
                            "STRING",
                            {"multiline": True, "dynamicPrompts": True},
                        ]
                    }
                },
                "output": ["STRING"],
                "output_name": ["value"],
            },
            "SimpleSyrup.LoadMaskBatch": {
                "input": {"required": {"image": ["STRING"]}},
                "output": ["MASK"],
            },
            "SchedulePrompts": {
                "input": {
                    "required": {
                        "positive_prompt": ["STRING"],
                        "negative_prompt": ["STRING"],
                    }
                },
                "output": ["CONDITIONING", "CONDITIONING", "CONDITIONING"],
            },
            "RegionalSampler": {
                "input": {
                    "required": {
                        "region_masks": ["MASK"],
                        "positive": ["CONDITIONING"],
                        "negative": ["CONDITIONING"],
                    }
                },
                "output": ["LATENT"],
            },
        }
    )
    workflow_id = "workflow-shared-region-names"
    shell.workflow_session_service.replace_workflows(
        {workflow_id: workflow},
        active_workflow_id=workflow_id,
    )
    shell.workflow_tabbar.addTab(workflow_id, "shared-region-names")
    shell.install_workflow_surface(workflow_id)
    cast(Any, shell).regional_interaction_coordinator = RegionalInteractionCoordinator(
        workflow=shell.get_active_workflow,
        active_panel=lambda: shell.active_editor_panel,
        canvas_hover=RegionalCanvasHoverPresenter(
            workflow=shell.get_active_workflow,
            color_target=_UnusedMaskColorTarget(),
        ),
    )
    panel = shell.editor_panels[workflow_id]
    shell.editor_panel_container.setCurrentWidget(panel)
    shell.editor_panel = panel
    panel.show()
    panel.load_all_cubes(
        [("Region", workflow.cubes["Region"])],
        cube_states=workflow.cubes,
        stack_order=workflow.stack_order,
    )
    panel.reveal_loaded_cube("Region")
    positive = _wait_for_prompt(real_shell_scenario, panel, "positive")
    negative = _wait_for_prompt(real_shell_scenario, panel, "negative")
    workflow_handle = PromptWorkflowHandle(
        alias="shared-region-names",
        workflow_id=workflow_id,
        cube_alias="Region",
        cube_state=workflow.cubes["Region"],
    )
    positive_field = PromptFieldHandle(
        workflow=workflow_handle,
        node_name="positive",
        field_key="value",
        editor=positive,
    )

    real_shell_scenario.wait_until(
        lambda: negative.toPlainText() == "N\n[SEP|Subject]\nnegative",
        description="initial shared SEP name normalization",
    )
    negative_cursor = negative.textCursor()
    negative_cursor.setPosition(len(negative.toPlainText()))
    negative.setTextCursor(negative_cursor)
    _rename_first_separator(real_shell_scenario, positive_field, "Character")
    real_shell_scenario.wait_until(
        lambda: negative.toPlainText() == "N\n[SEP|Character]\nnegative",
        description="peer prompt rename projection",
        state=lambda: {
            "positive_editor": positive.toPlainText(),
            "negative_editor": negative.toPlainText(),
            "positive_graph": _prompt_inputs(workflow, "positive")["value"],
            "negative_graph": _prompt_inputs(workflow, "negative")["value"],
            "active_panel_matches": shell.active_editor_panel is panel,
        },
    )
    assert negative.textCursor().position() == len(negative.toPlainText())
    real_shell_scenario.input.undo(positive_field)
    real_shell_scenario.wait_until(
        lambda: negative.toPlainText() == "N\n[SEP|Subject]\nnegative",
        description="peer prompt undo projection",
    )
    real_shell_scenario.input.redo(positive_field)
    real_shell_scenario.wait_until(
        lambda: negative.toPlainText() == "N\n[SEP|Character]\nnegative",
        description="peer prompt redo projection",
    )
    _rename_first_separator(real_shell_scenario, positive_field, "")
    real_shell_scenario.wait_until(
        lambda: negative.toPlainText() == "N\n[SEP]\nnegative",
        description="peer prompt cleared-name projection",
    )
    real_shell_scenario.input.undo(positive_field)
    real_shell_scenario.wait_until(
        lambda: negative.toPlainText() == "N\n[SEP|Character]\nnegative",
        description="cleared-name undo projection",
    )
    real_shell_scenario.input.redo(positive_field)
    real_shell_scenario.wait_until(
        lambda: negative.toPlainText() == "N\n[SEP]\nnegative",
        description="cleared-name redo projection",
    )

    assert _prompt_inputs(workflow, "positive")["value"] == positive.toPlainText()
    assert _prompt_inputs(workflow, "negative")["value"] == negative.toPlainText()
    assert "positive" in positive.toPlainText()
    assert "negative" in negative.toPlainText()


def _wait_for_prompt(
    scenario: PromptEditorRealShellScenario,
    panel: object,
    node_name: str,
) -> PromptEditor:
    """Return one settled production prompt editor from the live panel registry."""

    widgets = cast(
        dict[tuple[str, str, str], object],
        getattr(panel, "input_widgets_by_field_key"),
    )
    key = ("Region", node_name, "value")
    scenario.wait_until(
        lambda: isinstance(widgets.get(key), PromptEditor),
        description=f"{node_name} prompt editor projection",
    )
    editor = widgets.get(key)
    assert isinstance(editor, PromptEditor)
    scenario.wait_until(editor.isVisible, description=f"visible {node_name} prompt")
    scenario.wait_for_queued_delivery()
    return editor


def _rename_first_separator(
    scenario: PromptEditorRealShellScenario,
    field: PromptFieldHandle,
    name: str,
) -> None:
    """Rename the first separator using the production keyboard interaction."""

    editor = field.editor
    separator_end = editor.toPlainText().index("[SEP|")
    separator_end = editor.toPlainText().index("]", separator_end) + 1
    scenario.input.set_source_cursor_position(field, separator_end)
    scenario.input.press_key(field, Qt.Key.Key_F2)
    scenario.wait_until(
        lambda: (
            (
                inline := editor.viewport().findChild(
                    QLineEdit,
                    REGION_NAME_INLINE_EDITOR_OBJECT_NAME,
                )
            )
            is not None
            and inline.isVisible()
        ),
        description="regional name editor",
    )
    inline = editor.viewport().findChild(
        QLineEdit,
        REGION_NAME_INLINE_EDITOR_OBJECT_NAME,
    )
    assert inline is not None
    inline.setFocus()
    inline.selectAll()
    if name:
        QTest.keyClicks(inline, name)
    else:
        QTest.keyClick(inline, Qt.Key.Key_Backspace)
    QTest.keyClick(inline, Qt.Key.Key_Return)
    scenario.wait_for_queued_delivery()


def _prompt_inputs(workflow: object, node_name: str) -> dict[str, object]:
    """Return a typed prompt input mapping from the synthetic regional graph."""

    cubes = cast(Any, workflow).cubes
    nodes = cubes["Region"].buffer["nodes"]
    node = nodes[node_name]
    inputs = node["inputs"]
    assert isinstance(inputs, dict)
    return inputs
