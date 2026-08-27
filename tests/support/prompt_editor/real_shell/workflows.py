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

"""Mount and resolve production prompt-editor workflows for one real shell."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import cast

from PySide6.QtWidgets import QWidget
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.presentation.editor.panel.view import EditorPanel
from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.support.prompt_editor.real_shell.models import (
    PromptEditorTraceAction,
    PromptFieldHandle,
    PromptWorkflowHandle,
)
from tests.support.prompt_editor.real_shell.observability import (
    PromptEditorObservability,
)
from tests.support.prompt_editor.real_shell.session import PromptEditorRealShell
from tests.support.prompt_editor.real_shell.workflow_probes import PromptWorkflowProbes
from tests.support.qt.semantic_wait import wait_for_queued_qt_turn


class PromptWorkflowMounts:
    """Own prompt workflow creation, activation, and field resolution."""

    def __init__(
        self,
        *,
        shell: PromptEditorRealShell,
        handles: dict[str, PromptWorkflowHandle],
        wait_until: Callable[[Callable[[], bool]], None],
        observability: PromptEditorObservability,
        trace_actions: list[PromptEditorTraceAction],
    ) -> None:
        """Bind workflow operations to one mounted session."""

        self._shell = shell
        self._handles = handles
        self._wait_until = wait_until
        self._observability = observability
        self._trace_actions = trace_actions
        self.probes = PromptWorkflowProbes(shell)

    def add_prompt_workflow(
        self,
        alias: str = "prompt-harness",
        *,
        initial_text: str = "",
        model_node_type: str | None = None,
        model_field_key: str | None = None,
        model_value: str | None = None,
        activate: bool = True,
    ) -> PromptFieldHandle:
        """Add one workflow and render a CLIP prompt field through EditorPanel."""

        workflow_id = f"workflow-{alias}"
        cube_alias = "Prompt Cube"
        cube_state = _prompt_cube_state(
            initial_text,
            alias=cube_alias,
            model_node_type=model_node_type,
            model_field_key=model_field_key,
            model_value=model_value,
        )
        workflow = WorkflowState(
            cubes={cube_alias: cube_state},
            stack_order=[cube_alias],
            metadata={"name": alias},
        )
        if not self._handles:
            self._shell.workflow_session_service.replace_workflows(
                {workflow_id: workflow},
                active_workflow_id=workflow_id,
            )
        else:
            self._shell.workflow_session_service.add_existing_workflow(
                workflow_id,
                workflow,
                activate=activate,
            )
        self._shell.workflow_tabbar.addTab(workflow_id, alias)
        self._shell.install_workflow_surface(workflow_id)

        handle = PromptWorkflowHandle(
            alias=alias,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            cube_state=cube_state,
        )
        self._handles[alias] = handle
        if activate:
            self.activate_workflow(alias)

        panel = self._shell.editor_panels[workflow_id]
        panel.load_all_cubes(
            [(cube_alias, cube_state)],
            cube_states={cube_alias: cube_state},
            stack_order=[cube_alias],
        )
        if activate:
            self._shell.editor_panel_container.setCurrentWidget(panel)
            self._shell.editor_panel = panel
            panel.show()
            panel.reveal_loaded_cube(cube_alias)
        field_key = (cube_alias, "positive_prompt", "text")
        editor = self._wait_for_panel_prompt_editor(
            panel,
            field_key,
            require_projection_idle=activate,
        )
        if activate:
            self._wait_until(lambda: editor.isVisible())
        wait_for_queued_qt_turn()
        field = PromptFieldHandle(
            workflow=handle,
            node_name="positive_prompt",
            field_key="text",
            editor=editor,
        )
        self._observability.install(field)
        return field

    def add_anima_prompt_workflow(
        self,
        *,
        initial_text: str,
        model_value: str,
    ) -> PromptFieldHandle:
        """Mount the production three-cube Anima projection shape."""

        alias = "anima-prompt-harness"
        workflow_id = f"workflow-{alias}"
        stack_order = [
            "Anima/Text to Image",
            "Anima/Diffusion Upscale",
            "Anima/Automask Detailer",
        ]
        cube_states = {
            stack_order[0]: _anima_prompt_cube_state(
                initial_text,
                alias=stack_order[0],
                model_value=model_value,
            ),
            stack_order[1]: _anima_prompt_cube_state(
                "upscale prompt",
                alias=stack_order[1],
                model_value="",
            ),
            stack_order[2]: _anima_prompt_cube_state(
                "detailer prompt",
                alias=stack_order[2],
                model_value="",
            ),
        }
        workflow = WorkflowState(
            cubes=cube_states,
            stack_order=stack_order,
            metadata={"name": alias},
        )
        self._shell.workflow_session_service.replace_workflows(
            {workflow_id: workflow},
            active_workflow_id=workflow_id,
        )
        self._shell.workflow_tabbar.addTab(workflow_id, alias)
        self._shell.install_workflow_surface(workflow_id)
        handle = PromptWorkflowHandle(
            alias=alias,
            workflow_id=workflow_id,
            cube_alias=stack_order[0],
            cube_state=cube_states[stack_order[0]],
        )
        self._handles[alias] = handle
        self.activate_workflow(alias)
        panel = self._shell.editor_panels[workflow_id]
        panel.load_all_cubes(
            [(cube_alias, cube_states[cube_alias]) for cube_alias in stack_order],
            cube_states=cube_states,
            stack_order=stack_order,
        )
        self._shell.editor_panel_container.setCurrentWidget(panel)
        self._shell.editor_panel = panel
        panel.show()
        for cube_alias in stack_order:
            panel.reveal_loaded_cube(cube_alias)
        field_key = (stack_order[0], "positive_prompt", "text")
        editor = self._wait_for_panel_prompt_editor(panel, field_key)
        wait_for_queued_qt_turn()
        field = PromptFieldHandle(
            workflow=handle,
            node_name="positive_prompt",
            field_key="text",
            editor=editor,
        )
        self._observability.install(field)
        return field

    def add_inferred_prompt_workflow(
        self,
        alias: str = "inferred-prompt-harness",
        *,
        initial_text: str = "",
    ) -> PromptFieldHandle:
        """Mount a cube whose prompt behavior comes only from typed graph flow."""

        workflow_id = f"workflow-{alias}"
        cube_alias = "Inferred Prompt Cube"
        cube_state = _inferred_prompt_cube_state(initial_text, alias=cube_alias)
        self._shell.node_definition_gateway.install_recorded_definitions(
            {
                "KSampler": {
                    "input": {
                        "required": {
                            "positive": ["CONDITIONING"],
                        }
                    },
                    "output": ["LATENT"],
                },
                "OrdinaryControl": {
                    "input": {"required": {"value": ["INT", {"default": 1}]}},
                    "output": [],
                },
            }
        )
        workflow = WorkflowState(
            cubes={cube_alias: cube_state},
            stack_order=[cube_alias],
            metadata={"name": alias},
        )
        if not self._handles:
            self._shell.workflow_session_service.replace_workflows(
                {workflow_id: workflow},
                active_workflow_id=workflow_id,
            )
        else:
            self._shell.workflow_session_service.add_existing_workflow(
                workflow_id,
                workflow,
                activate=True,
            )
        self._shell.workflow_tabbar.addTab(workflow_id, alias)
        self._shell.install_workflow_surface(workflow_id)
        handle = PromptWorkflowHandle(
            alias=alias,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            cube_state=cube_state,
        )
        self._handles[alias] = handle
        self.activate_workflow(alias)
        panel = self._shell.editor_panels[workflow_id]
        panel.load_all_cubes(
            [(cube_alias, cube_state)],
            cube_states={cube_alias: cube_state},
            stack_order=[cube_alias],
        )
        self._shell.editor_panel_container.setCurrentWidget(panel)
        self._shell.editor_panel = panel
        panel.show()
        panel.reveal_loaded_cube(cube_alias)
        field_key = (cube_alias, "encoder", "text")
        editor = self._wait_for_panel_prompt_editor(panel, field_key)
        wait_for_queued_qt_turn()
        field = PromptFieldHandle(
            workflow=handle,
            node_name="encoder",
            field_key="text",
            editor=editor,
        )
        self._observability.install(field)
        return field

    def activate_workflow(self, alias: str, *, force_refresh: bool = True) -> None:
        """Activate one workflow through the production workspace coordinator."""

        self._shell.activate_for_input()
        workflow_id = self._handles[alias].workflow_id
        self._shell.workflow_workspace.activate_workflow(
            workflow_id,
            source="workflow_tab",
            force_refresh=force_refresh,
        )
        wait_for_queued_qt_turn()

    def activate_workflow_for_trace(
        self,
        alias: str,
        *,
        force_refresh: bool = True,
    ) -> None:
        """Activate a workflow and record the route as a replayable trace action."""

        self.activate_workflow(alias, force_refresh=force_refresh)
        self._trace_actions.append(PromptEditorTraceAction("activate_workflow", alias))

    def refresh_prompt_field(self, field: PromptFieldHandle) -> PromptFieldHandle:
        """Resolve a field's current editor after its panel replaces the projection."""

        panel = self._shell.editor_panels[field.workflow.workflow_id]
        editor = self._wait_for_panel_prompt_editor(
            panel,
            (field.workflow.cube_alias, field.node_name, field.field_key),
        )
        self._wait_until(editor.isVisible)
        refreshed_field = replace(field, editor=editor)
        self._observability.install(refreshed_field)
        return refreshed_field

    def wait_for_prompt_field_absence(self, field: PromptFieldHandle) -> None:
        """Wait until a panel has completed removal of one projected prompt field."""

        panel = self._shell.editor_panels[field.workflow.workflow_id]
        field_key = (field.workflow.cube_alias, field.node_name, field.field_key)
        self._wait_until(
            lambda: (
                not panel.is_projection_active()
                and field_key not in _panel_input_widgets(panel)
            )
        )

    def workflow_round_trip(self, field: PromptFieldHandle) -> PromptFieldHandle:
        """Switch away from a prompt workflow and back through real shell routing."""

        self.prepare_workflow_round_trip(field)
        secondary_alias = f"{field.workflow.alias}-secondary"
        self.activate_workflow_for_trace(secondary_alias)
        self.activate_workflow_for_trace(field.workflow.alias)
        return self.prompt_field(field.workflow.alias)

    def prepare_workflow_round_trip(self, field: PromptFieldHandle) -> str:
        """Create and return the inactive secondary workflow alias."""

        secondary_alias = f"{field.workflow.alias}-secondary"
        if secondary_alias not in self._handles:
            self.add_prompt_workflow(
                secondary_alias,
                initial_text="secondary prompt",
                activate=False,
            )
        return secondary_alias

    def prompt_field(self, alias: str) -> PromptFieldHandle:
        """Resolve the current real prompt editor field for one workflow alias."""

        workflow = self._handles[alias]
        panel = self._shell.editor_panels[workflow.workflow_id]
        field_key = (workflow.cube_alias, "positive_prompt", "text")
        widget = self._wait_for_panel_prompt_editor(panel, field_key)
        self._wait_until(lambda: widget.isVisible())
        field = PromptFieldHandle(
            workflow=workflow,
            node_name="positive_prompt",
            field_key="text",
            editor=widget,
        )
        return field

    def _wait_for_panel_prompt_editor(
        self,
        panel: EditorPanel,
        field_key: tuple[str, str, str],
        *,
        require_projection_idle: bool = True,
    ) -> PromptEditor:
        """Resolve a prompt editor from the settled live panel registry."""

        self._wait_until(
            lambda: (
                (not require_projection_idle or not panel.is_projection_active())
                and isinstance(
                    _panel_input_widgets(panel).get(field_key),
                    PromptEditor,
                )
            )
        )
        editor = _panel_input_widgets(panel).get(field_key)
        if not isinstance(editor, PromptEditor):
            raise AssertionError(
                f"settled field {field_key!r} is {type(editor)!r}, not PromptEditor"
            )
        return editor


def _prompt_cube_state(
    initial_text: str,
    *,
    alias: str,
    model_node_type: str | None = None,
    model_field_key: str | None = None,
    model_value: str | None = None,
) -> CubeState:
    """Build a minimal loaded cube state with one prompt node."""

    nodes: dict[str, object] = {
        "positive_prompt": {
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "Positive Prompt"},
            "inputs": {"text": initial_text},
        }
    }
    if (
        model_node_type is not None
        and model_field_key is not None
        and model_value is not None
    ):
        nodes["model"] = {
            "class_type": model_node_type,
            "_meta": {"title": "Model"},
            "inputs": {model_field_key: model_value},
        }
    buffer: dict[str, object] = {
        "nodes": nodes,
        "definitions": {},
        "subgraphs": [],
    }
    return CubeState(
        cube_id="PromptHarness.cube",
        version="1.0",
        alias=alias,
        buffer=buffer,
        original_cube={"workflow": buffer},
        display_name="Prompt Harness Cube",
        dirty=False,
        ui={},
        field_control_states={},
    )


def _anima_prompt_cube_state(
    prompt: str,
    *,
    alias: str,
    model_value: str,
) -> CubeState:
    """Build one Anima cube with production model-before-prompt node order."""

    buffer: dict[str, object] = {
        "nodes": {
            "models": {
                "class_type": "SimpleSyrup.SimpleLoadAnima",
                "_meta": {"title": "Models"},
                "inputs": {"diffusion_model": model_value},
            },
            "positive_prompt": {
                "class_type": "CLIPTextEncode",
                "_meta": {"title": "Positive Prompt"},
                "inputs": {"text": prompt},
            },
        },
        "definitions": {},
        "subgraphs": [],
    }
    return CubeState(
        cube_id=f"PromptHarness.{alias}.cube",
        version="1.0",
        alias=alias,
        buffer=buffer,
        original_cube={"workflow": buffer},
        display_name=alias,
        dirty=False,
        ui={},
        field_control_states={},
    )


def _inferred_prompt_cube_state(initial_text: str, *, alias: str) -> CubeState:
    """Build a cube whose arbitrary encoder name feeds a semantic positive sink."""

    buffer: dict[str, object] = {
        "nodes": {
            "ordinary": {
                "class_type": "OrdinaryControl",
                "inputs": {"value": 1},
            },
            "encoder": {
                "class_type": "CLIPTextEncode",
                "_meta": {"title": "Text Encoder"},
                "inputs": {"text": initial_text},
            },
            "sampler": {
                "class_type": "KSampler",
                "inputs": {"positive": ["encoder", 0]},
            },
        },
        "definitions": {},
        "subgraphs": [],
    }
    return CubeState(
        cube_id="PromptHarness.inferred.cube",
        version="1.0",
        alias=alias,
        buffer=buffer,
        original_cube={"workflow": buffer},
        display_name=alias,
        dirty=False,
        ui={},
        field_control_states={},
    )


def _panel_input_widgets(
    panel: EditorPanel,
) -> dict[tuple[str, str, str], QWidget]:
    """Return the dynamic editor-panel field registry with a strict type."""

    return cast(
        dict[tuple[str, str, str], QWidget],
        getattr(panel, "input_widgets_by_field_key"),
    )
