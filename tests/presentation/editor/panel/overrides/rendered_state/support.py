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

"""Build rendered override controls with deterministic workflow collaborators."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.generation import GenerationRequest
from substitute.application.generation.seed_randomization_service import (
    SeedRandomizationResult,
    SeedRandomizationService,
)
from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    FieldBehavior,
    OverrideBehavior,
    OverridePinPolicy,
    ResolvedFieldSpec,
)
from substitute.application.overrides import PinnedOverrideService
from substitute.domain.node_behavior import FieldPresentation
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.domain.workspace_snapshot.codecs import workflow_state_to_json
from substitute.presentation.editor.panel.factories.numeric_factory import (
    widget_factory_seedbox,
)
from substitute.presentation.editor.panel.field_state_controller import (
    EditorPanelFieldStateController,
)
from substitute.presentation.editor.panel.overrides_controller import (
    GlobalOverridesManager,
)
from substitute.presentation.shell.main_window_menu import build_main_window_menu
from substitute.presentation.shell.seed_value_projector import SeedValueProjector
from substitute.presentation.shell.workspace_generation_action_adapter import (
    randomize_generation_request_seeds,
)
from substitute.presentation.widgets import SeedBox
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
)
from tests.support.qt.lifecycle import destroy_qt_object


@dataclass
class RenderedOverrideHarness:
    """Own real toolbar controls, one node SeedBox, and workflow state."""

    application: QApplication
    root: QWidget
    workflow: WorkflowState
    manager: GlobalOverridesManager
    node_seed: SeedBox
    autosave_payloads: list[dict[str, object]]

    def toolbar_widget(self, key: str) -> Any:
        """Return one production override widget by canonical key."""

        return self.manager._global_override_controls[key][1]  # noqa: SLF001

    def close(self) -> None:
        """Destroy the harness root and all owned controls synchronously."""

        destroy_qt_object(self.root)


class _SnapshotSource:
    """Expose the behavior snapshot consumed by the override manager."""

    def __init__(self, snapshot: EditorBehaviorSnapshot) -> None:
        """Store the current deterministic behavior snapshot."""

        self._snapshot = snapshot

    def current_behavior_snapshot(self) -> EditorBehaviorSnapshot:
        """Return the behavior snapshot for the mounted workflow."""

        return self._snapshot


class _NodeDefinitionGateway:
    """Return the live KSampler choice inventory used by real combo factories."""

    def get_node_definition(self, node_type: str) -> dict[str, object]:
        """Return a minimal live KSampler definition."""

        if node_type != "KSampler":
            return {}
        return {
            "KSampler": {
                "input": {
                    "required": {
                        "sampler_name": (["er_sde", "euler"], {}),
                        "scheduler": (["simple", "normal"], {}),
                    }
                }
            }
        }

    def get_required_node_definition(self, node_type: str) -> dict[str, object]:
        """Return the required node definition for widget construction."""

        return self.get_node_definition(node_type)


class DeterministicSeedRandomizer:
    """Drive the production seed service with a deterministic value sequence."""

    def __init__(self, values: list[int]) -> None:
        """Store the random values consumed by successive generation requests."""

        self._values = iter(values)
        self._service = SeedRandomizationService()

    def randomize_workflow_seeds(
        self,
        *,
        workflow: WorkflowState,
        behavior_snapshot: EditorBehaviorSnapshot | None,
    ) -> SeedRandomizationResult:
        """Randomize through the production service using the next probe value."""

        return self._service.randomize_workflow_seeds(
            workflow=workflow,
            behavior_snapshot=behavior_snapshot,
            randint=lambda _minimum, _maximum: next(self._values),
        )


def build_workflow() -> WorkflowState:
    """Build one workflow containing the three exercised KSampler fields."""

    cube = CubeState(
        cube_id="owner/repo/demo.cube",
        version="1.0.0",
        alias="A",
        original_cube={"nodes": {}},
        buffer={
            "nodes": {
                "ksampler": {
                    "class_type": "KSampler",
                    "inputs": {
                        "sampler_name": "er_sde",
                        "scheduler": "simple",
                        "seed": 7,
                    },
                }
            }
        },
    )
    return WorkflowState(
        cubes={"A": cube},
        stack_order=["A"],
        global_overrides={
            "sampler_name": {"value": "er_sde", "mode": "global"},
            "scheduler": {"value": "simple", "mode": "global"},
            "seed": {"value": 11, "mode": "global"},
        },
        global_override_selections={
            "sampler_name": True,
            "scheduler": True,
            "seed": True,
        },
    )


def _field_spec(
    *,
    field_key: str,
    value: object,
    order: int,
    field_type: str,
    field_info: list[object] | None = None,
) -> ResolvedFieldSpec:
    """Build one KSampler field spec used by node and toolbar projections."""

    constraints: dict[str, object] = (
        {"min": 0, "max": 999} if field_key == "seed" else {}
    )
    return ResolvedFieldSpec(
        cube_alias="A",
        node_name="ksampler",
        class_type="KSampler",
        field_key=field_key,
        field_type=field_type,
        constraints=constraints,
        meta_info={},
        field_info=field_info,
        value=value,
        field_behavior=FieldBehavior(
            field_key=field_key,
            presentation=(
                FieldPresentation.SEED_BOX
                if field_key == "seed"
                else FieldPresentation.STANDARD
            ),
            override_behavior=OverrideBehavior(
                override_key=field_key,
                pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                toolbar_order=order,
            ),
        ),
    )


def build_behavior_snapshot(workflow: WorkflowState) -> EditorBehaviorSnapshot:
    """Build behavior for the workflow's current node values."""

    inputs = cast(
        dict[str, object],
        cast(dict[str, object], workflow.cubes["A"].buffer["nodes"])["ksampler"],
    )["inputs"]
    values = cast(dict[str, object], inputs)
    specs = (
        _field_spec(
            field_key="sampler_name",
            value=values["sampler_name"],
            order=10,
            field_type="LIST",
            field_info=[["er_sde", "euler"], {"default": "er_sde"}],
        ),
        _field_spec(
            field_key="scheduler",
            value=values["scheduler"],
            order=20,
            field_type="LIST",
            field_info=[["simple", "normal"], {"default": "simple"}],
        ),
        _field_spec(
            field_key="seed",
            value=values["seed"],
            order=30,
            field_type="INT",
        ),
    )
    return EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={
            "A": {"ksampler": {spec.field_key: spec for spec in specs}}
        },
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )


def render_harness(
    application: QApplication,
    workflow: WorkflowState | None = None,
) -> RenderedOverrideHarness:
    """Mount production override controls and a production node SeedBox."""

    active_workflow = workflow or build_workflow()
    snapshot = build_behavior_snapshot(active_workflow)
    root = QWidget()
    parts = build_main_window_menu(root, workspace_controller=object())
    parts.menu_bar.setParent(root)
    root.resize(1100, 100)
    parts.menu_bar.resize(1100, 44)
    root.show()
    parts.menu_bar.show()
    autosave_payloads: list[dict[str, object]] = []
    panel = _SnapshotSource(snapshot)
    panel.cube_widgets = {"A": root}  # type: ignore[attr-defined]
    shell = SimpleNamespace(
        menu_bar=parts.menu_bar,
        menu_bar_layout=parts.menu_bar_layout,
        pendingRestartButton=parts.pending_restart_button,
        _active_workspace_route="workflow",
        active_editor_panel=panel,
        get_active_workflow=lambda: active_workflow,
        request_session_autosave=lambda: autosave_payloads.append(
            workflow_state_to_json(active_workflow)
        ),
    )
    manager = GlobalOverridesManager(
        shell,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=_NodeDefinitionGateway(),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.override_dropdown_btn = parts.override_dropdown_btn
    shell.active_override_manager = manager
    manager.sync_state_from_workflow()
    manager.rebuild_active_override_controls()

    node_seed_result = widget_factory_seedbox(
        root,
        "ksampler",
        "seed",
        7,
        {},
        field_presentation=FieldPresentation.SEED_BOX,
        constraints={"min": 0, "max": 999},
    )
    assert isinstance(node_seed_result, SeedBox)
    node_seed = node_seed_result
    field_state_controller = EditorPanelFieldStateController(cast(Any, panel))
    field_state_controller.bind_node_widget_state(
        node_seed,
        active_workflow.cubes["A"],
        {
            "cube_alias": "A",
            "node_name": "ksampler",
            "node_type": "KSampler",
            "key": "seed",
            "type": "INT",
        },
    )
    node_seed.move(0, 55)
    node_seed.show()
    parts.menu_bar_layout.activate()
    return RenderedOverrideHarness(
        application=application,
        root=root,
        workflow=active_workflow,
        manager=manager,
        node_seed=node_seed,
        autosave_payloads=autosave_payloads,
    )


def node_seed_value(workflow: WorkflowState) -> int:
    """Return the authoritative node seed from the cube input buffer."""

    nodes = cast(dict[str, object], workflow.cubes["A"].buffer["nodes"])
    node = cast(dict[str, object], nodes["ksampler"])
    inputs = cast(dict[str, object], node["inputs"])
    return cast(int, inputs["seed"])


def override_seed_value(workflow: WorkflowState) -> int:
    """Return the authoritative seed value from the global override map."""

    return cast(int, workflow.global_overrides["seed"]["value"])


def randomize_for_generation(
    harness: RenderedOverrideHarness,
    randomizer: DeterministicSeedRandomizer,
) -> None:
    """Run the production generation-request seed randomization adapter."""

    result = randomize_generation_request_seeds(
        seed_randomization_service=randomizer,
        request=GenerationRequest(
            workflow_id="workflow-a",
            workflow_name="Abuse probe",
            workflow=cast(Any, harness.workflow),
        ),
        behavior_snapshot=build_behavior_snapshot(harness.workflow),
    )
    SeedValueProjector(harness.manager.mainwindow).project(harness.workflow, result)


__all__ = [
    "DeterministicSeedRandomizer",
    "RenderedOverrideHarness",
    "node_seed_value",
    "override_seed_value",
    "randomize_for_generation",
    "render_harness",
]
