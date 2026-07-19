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

"""Render cube/direct workflow presentation through the production Qt shell scaffold."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping, cast

from PySide6.QtCore import QElapsedTimer, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.direct_workflows import DirectWorkflowLoadService
from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.workflow import WorkflowDocumentKind, WorkflowState
from substitute.infrastructure.comfy.workflow_document_repository import (
    ComfyWorkflowDocumentRepository,
)
from substitute.presentation.editor.panel.overrides_controller import (
    GlobalOverridesManager,
)
from substitute.presentation.editor.panel.override_control_identity import (
    OVERRIDE_CONTROL_ROLE,
    OVERRIDE_KEY_PROPERTY,
    OVERRIDE_LABEL_ROLE,
    OVERRIDE_ROLE_PROPERTY,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_STACK_EXPANDED_WIDTH,
)
from substitute.presentation.widgets import SeedBox
from tests.real_shell_prompt_editor_harness import RealShellPromptEditorHarness


@dataclass(frozen=True, slots=True)
class DirectWorkflowLayoutProbe:
    """Capture geometry and chrome from authoritative production widgets."""

    label: str
    mode: str
    generation: int
    animating: bool
    container_width: int
    container_visible: bool
    editor_width: int
    editor_global_left: int
    editor_left_gutter: int
    editor_right_gutter: int
    canvas_width: int
    splitter_sizes: tuple[int, ...]
    button_enabled: bool
    button_checked: bool
    button_accessible_name: str


@dataclass(frozen=True, slots=True)
class RenderedSeedControlProbe:
    """Capture the complete external and internal contract of one SeedBox surface."""

    surface: str
    label_text: str
    label_visible: bool
    label_explicitly_hidden: bool
    widget_type: str
    size: tuple[int, int]
    size_hint: tuple[int, int]
    minimum_size_hint: tuple[int, int]
    size_policy: tuple[int, int]
    line_edit_geometry: tuple[int, int, int, int]
    split_button_geometry: tuple[int, int, int, int]


class RealShellDirectWorkflowHarness:
    """Exercise real EditorPanel/CubeStack routes and the production animator."""

    def __init__(self) -> None:
        """Build one cube and one direct workflow in the production workspace scaffold."""

        self._base = RealShellPromptEditorHarness()
        self._previous_reduced_motion = self._base.app.property(
            "substitute.reduce_motion"
        )
        self._base.app.setProperty("substitute.reduce_motion", False)
        self.shell = self._base.shell
        cube_field = self._base.add_prompt_workflow("cube", activate=True)
        self.cube_workflow_id = cube_field.workflow.workflow_id
        self.direct_workflow_id = "workflow-direct"
        direct_workflow = WorkflowState(
            direct_workflow=DirectWorkflowState(
                source_path=Path("direct-workflow.json"),
                source_workflow={"nodes": []},
                buffer={"nodes": {}},
            )
        )
        self.shell.workflow_session_service.add_existing_workflow(
            self.direct_workflow_id,
            direct_workflow,
            activate=False,
        )
        self.shell.workflow_tabbar.addTab(self.direct_workflow_id, "Direct")
        self.shell.install_workflow_surface(self.direct_workflow_id)
        self.shell.splitter.setSizes([760, 520])
        self.process_events()
        self.activate_cube(animated=False)

    @property
    def app(self) -> QApplication:
        """Return the application owned by the underlying real-shell harness."""

        return self._base.app

    def close(self) -> None:
        """Close all real Qt widgets owned by the shared harness."""

        self._base.app.setProperty(
            "substitute.reduce_motion",
            self._previous_reduced_motion,
        )
        self._base.close()

    def activate_cube(self, *, animated: bool = True) -> None:
        """Activate the cube workflow through route projection."""

        if animated:
            self.shell.workflow_workspace.activate_workflow(
                self.cube_workflow_id,
                force_refresh=True,
                source="direct-harness-cube",
            )
        else:
            self.shell.workflow_session_service.activate_workflow(self.cube_workflow_id)
            self.shell.editor_panel_container.setCurrentWidget(
                self.shell.editor_panels[self.cube_workflow_id]
            )
            self.shell.cube_stack_container.setCurrentWidget(
                cast(QWidget, self.shell.cube_stacks[self.cube_workflow_id])
            )
            self.shell.cube_stack_presentation_controller.activate_document_kind(
                WorkflowDocumentKind.CUBE_STACK,
                animated=False,
            )
        self.process_events()

    def activate_direct(self, *, animated: bool = True) -> None:
        """Activate the direct workflow through the production route projector."""

        if animated:
            self.shell.workflow_workspace.activate_workflow(
                self.direct_workflow_id,
                force_refresh=True,
                source="direct-harness-direct",
            )
        else:
            self.shell.workflow_session_service.activate_workflow(
                self.direct_workflow_id
            )
            self.shell.editor_panel_container.setCurrentWidget(
                self.shell.editor_panels[self.direct_workflow_id]
            )
            self.shell.workflow_ui_factory.reconcile_cube_stack_surface(
                self.direct_workflow_id,
                set_as_current=True,
            )
            self.shell.cube_stack_presentation_controller.activate_document_kind(
                WorkflowDocumentKind.DIRECT_COMFY,
                animated=False,
            )
        self.process_events()

    def load_direct_workflow(
        self,
        path: Path,
        *,
        node_definitions: Mapping[str, Mapping[str, object]],
        expected_node_names: frozenset[str],
    ) -> None:
        """Load a workflow and wait for its expected atomic card projection."""

        self.shell.node_definition_gateway.install_recorded_definitions(
            node_definitions
        )
        service = DirectWorkflowLoadService(
            ComfyWorkflowDocumentRepository(),
            node_definition_gateway=self.shell.node_definition_gateway,
        )
        workflow = self.shell.workflow_session_service.get_workflow(
            self.direct_workflow_id
        )
        if workflow is None:
            raise AssertionError("direct workflow session disappeared")
        workflow.direct_workflow = service.load(path)
        self.activate_direct(animated=True)
        self.wait_for_transition()
        panel = self.shell.editor_panels[self.direct_workflow_id]

        def expected_projection_visible() -> bool:
            """Return whether the atomic projection exposes required card owners."""

            if panel.has_pending_visible_projection_commit():
                panel.finalize_pending_visible_projection()
            self.process_events()
            rendered_node_names = set(self.rendered_node_names())
            return (
                expected_node_names.issubset(rendered_node_names)
                and not panel.is_projection_active()
            )

        self.wait_until(
            expected_projection_visible,
            description=f"direct workflow cards {sorted(expected_node_names)!r}",
        )

    def install_cube_seed_control(
        self,
        *,
        node_definitions: Mapping[str, Mapping[str, object]],
        value: int = 7,
    ) -> None:
        """Add a genuine resolved cube seed field to the production cube surface."""

        workflow = self.shell.workflow_session_service.get_workflow(
            self.cube_workflow_id
        )
        if workflow is None:
            raise AssertionError("cube workflow session disappeared")
        cube_alias = workflow.stack_order[0]
        cube_state = workflow.cubes[cube_alias]
        nodes = cube_state.buffer.get("nodes")
        if not isinstance(nodes, dict):
            raise AssertionError("cube fixture has no mutable node graph")
        nodes["ksampler"] = {
            "class_type": "KSampler",
            "_meta": {"title": "Sampler"},
            "inputs": {"seed": value},
        }
        workflow.global_overrides = {
            "seed": {"value": value, "mode": "global"},
        }
        self.shell.node_definition_gateway.install_recorded_definitions(
            node_definitions
        )
        panel = self.shell.editor_panels[self.cube_workflow_id]
        panel.clear_layout()
        panel.load_all_cubes(
            [(cube_alias, cube_state)],
            cube_states={cube_alias: cube_state},
            stack_order=[cube_alias],
        )
        self.activate_cube(animated=False)
        self._base.wait_until(
            lambda: any(
                field_key == "seed"
                for _section, _node_name, field_key in cast(
                    dict[tuple[str, str, str], QWidget],
                    getattr(panel, "input_widgets_by_field_key"),
                )
            )
        )
        manager = cast(
            GlobalOverridesManager,
            self.shell.override_managers[self.cube_workflow_id],
        )
        manager.sync_state_from_workflow()
        manager.rebuild_active_override_controls()
        self.process_events()

    def seed_toolbar_probe(self, workflow_id: str) -> RenderedSeedControlProbe:
        """Return production toolbar label and SeedBox geometry for one workflow."""

        manager = self._override_manager(workflow_id)
        manager.rebuild_active_override_controls()
        self.process_events()
        label, widget = self._override_surface(workflow_id, "seed")
        if not isinstance(widget, SeedBox):
            raise AssertionError(f"seed override rendered {type(widget).__name__}")
        return _seed_control_probe("toolbar", label, widget)

    def seed_field_probe(
        self,
        workflow_id: str,
        field_key: str,
    ) -> RenderedSeedControlProbe:
        """Return a production node-card seed field and its row-label geometry."""

        panel = self.shell.editor_panels[workflow_id]
        widgets = cast(
            dict[tuple[str, str, str], QWidget],
            getattr(panel, "input_widgets_by_field_key"),
        )
        matches = [
            widget
            for (_section, _node_name, key), widget in widgets.items()
            if key == field_key and isinstance(widget, SeedBox)
        ]
        if not matches:
            rendered = tuple(
                (identity, type(widget).__name__)
                for identity, widget in widgets.items()
            )
            raise AssertionError(
                f"missing rendered SeedBox field: {field_key}; rendered={rendered!r}"
            )
        widget = matches[0]
        row = widget.parentWidget()
        layout = row.layout() if row is not None else None
        label = None
        if layout is not None:
            for index in range(layout.count()):
                item = layout.itemAt(index)
                candidate = item.widget() if item is not None else None
                if candidate is widget or candidate is None:
                    continue
                if callable(getattr(candidate, "text", None)):
                    label = candidate
                    break
        if label is None:
            raise AssertionError(f"missing field-row label for {field_key}")
        return _seed_control_probe("node_card", label, widget)

    def rendered_node_cards(
        self,
        workflow_id: str | None = None,
    ) -> tuple[tuple[str, str], ...]:
        """Return unique node ids and classes rendered by one editor panel."""

        panel = self.shell.editor_panels[workflow_id or self.direct_workflow_id]
        cards = {
            (str(node_name), str(class_type))
            for widget in panel.findChildren(QWidget)
            if (node_name := widget.property("node_name"))
            and (class_type := widget.property("node_class_type"))
        }
        return tuple(sorted(cards))

    def rendered_node_names(self, workflow_id: str | None = None) -> tuple[str, ...]:
        """Return unique rendered node names for one editor panel."""

        return tuple(
            node_name
            for node_name, _class_type in self.rendered_node_cards(workflow_id)
        )

    def wait_for_rendered_node_names(
        self,
        expected_node_names: frozenset[str],
        *,
        workflow_id: str | None = None,
    ) -> None:
        """Wait until one panel exposes all expected production node cards."""

        resolved_workflow_id = workflow_id or self.direct_workflow_id
        panel = self.shell.editor_panels[resolved_workflow_id]

        def expected_projection_visible() -> bool:
            """Finalize eligible reveals and inspect their semantic node identities."""

            if panel.has_pending_visible_projection_commit():
                panel.finalize_pending_visible_projection()
            return (
                expected_node_names.issubset(
                    self.rendered_node_names(resolved_workflow_id)
                )
                and not panel.is_projection_active()
            )

        self.wait_until(
            expected_projection_visible,
            description=(
                f"workflow {resolved_workflow_id!r} cards "
                f"{sorted(expected_node_names)!r}"
            ),
        )

    def rendered_prompt_fields(self) -> tuple[tuple[str, str], ...]:
        """Return direct-workflow fields mounted as production PromptEditors."""

        panel = self.shell.editor_panels[self.direct_workflow_id]
        widgets = cast(
            dict[tuple[str, str, str], QWidget],
            getattr(panel, "input_widgets_by_field_key"),
        )
        return tuple(
            sorted(
                (node_name, field_key)
                for (_section, node_name, field_key), widget in widgets.items()
                if isinstance(widget, PromptEditor)
            )
        )

    def rendered_node_card_order(self) -> tuple[str, ...]:
        """Return production masonry insertion order for the direct section."""

        panel = self.shell.editor_panels[self.direct_workflow_id]
        prompt_editor = next(iter(panel.findChildren(PromptEditor)), None)
        ancestor = prompt_editor.parentWidget() if prompt_editor is not None else None
        while ancestor is not None:
            node_card_order = getattr(ancestor, "node_card_order", None)
            if callable(node_card_order):
                return tuple(node_card_order())
            ancestor = ancestor.parentWidget()
        raise AssertionError("direct workflow masonry owner is unavailable")

    def active_override_keys(self) -> tuple[str, ...]:
        """Return toolbar override keys mounted by the production manager."""

        self._override_manager(
            self.direct_workflow_id
        ).rebuild_active_override_controls()
        self.process_events()
        return tuple(
            sorted(
                {
                    str(widget.property(OVERRIDE_KEY_PROPERTY))
                    for widget in self.shell.menu_bar.findChildren(QWidget)
                    if widget.property(OVERRIDE_ROLE_PROPERTY) == OVERRIDE_CONTROL_ROLE
                    and widget.property(OVERRIDE_KEY_PROPERTY)
                    and not widget.isHidden()
                }
            )
        )

    def set_global_override_value(self, override_key: str, value: object) -> None:
        """Commit a value through the mounted production toolbar widget."""

        _label, widget = self._override_surface(
            self.direct_workflow_id,
            override_key,
        )
        set_value = getattr(widget, "setValue", None)
        if callable(set_value):
            set_value(value)
        else:
            set_current_text = getattr(widget, "setCurrentText", None)
            if not callable(set_current_text):
                raise AssertionError(
                    f"unsupported override widget: {type(widget).__name__}"
                )
            set_current_text(str(value))
        self.process_events()

    def wait_for_transition(self, timeout_ms: int = 2000) -> None:
        """Pump the production animation event loop through exact completion."""

        timer = QElapsedTimer()
        timer.start()
        while self.shell.cube_stack_presentation_controller.is_animating:
            if timer.elapsed() >= timeout_ms:
                raise AssertionError(
                    f"presentation transition exceeded {timeout_ms} ms"
                )
            QTest.qWait(5)
        self.process_events()

    def wait_for_intermediate_transition(self, timeout_ms: int = 2000) -> None:
        """Wait until stack availability reaches an observable intermediate frame."""

        self.wait_until(
            lambda: (
                self.shell.cube_stack_presentation_controller.is_animating
                and 0
                < self.shell.cube_stack_presentation_controller.current_frame().container_width
                < CUBE_STACK_EXPANDED_WIDTH
            ),
            description="cube-stack intermediate presentation frame",
            timeout_ms=timeout_ms,
        )

    def wait_until(
        self,
        predicate: Callable[[], bool],
        *,
        description: str,
        timeout_ms: int = 2000,
    ) -> None:
        """Pump Qt until an observable predicate succeeds or its deadline expires."""

        timer = QElapsedTimer()
        timer.start()
        while not predicate():
            if timer.elapsed() >= timeout_ms:
                raise AssertionError(
                    f"timed out waiting for {description} after {timeout_ms} ms"
                )
            QTest.qWait(5)
        self.process_events()

    def _override_manager(self, workflow_id: str) -> GlobalOverridesManager:
        """Return the production manager for one harness workflow."""

        return cast(
            GlobalOverridesManager,
            self.shell.override_managers[workflow_id],
        )

    def _override_surface(
        self,
        workflow_id: str,
        override_key: str,
    ) -> tuple[QWidget, QWidget]:
        """Resolve one toolbar label/control pair through published Qt identity."""

        self._override_manager(workflow_id).rebuild_active_override_controls()
        self.process_events()
        matching = [
            widget
            for widget in self.shell.menu_bar.findChildren(QWidget)
            if widget.property(OVERRIDE_KEY_PROPERTY) == override_key
            and not widget.isHidden()
        ]
        label = next(
            (
                widget
                for widget in matching
                if widget.property(OVERRIDE_ROLE_PROPERTY) == OVERRIDE_LABEL_ROLE
            ),
            None,
        )
        control = next(
            (
                widget
                for widget in matching
                if widget.property(OVERRIDE_ROLE_PROPERTY) == OVERRIDE_CONTROL_ROLE
            ),
            None,
        )
        if label is None or control is None:
            raise AssertionError(
                f"missing global override surface: {workflow_id}:{override_key}"
            )
        return label, control

    def probe(self, label: str) -> DirectWorkflowLayoutProbe:
        """Read geometry from the real production workspace widgets."""

        controller = self.shell.cube_stack_presentation_controller
        editor = self.shell.editor_panel_container
        editor_left = editor.mapToGlobal(QPoint(0, 0)).x()
        active_editor = self.shell.active_editor_panel
        if active_editor is None:
            raise AssertionError("active editor panel is unavailable")
        left_gutter, right_gutter = active_editor.content_horizontal_gutters()
        return DirectWorkflowLayoutProbe(
            label=label,
            mode=controller.mode.value,
            generation=controller.active_generation,
            animating=controller.is_animating,
            container_width=self.shell.cube_stack_container.width(),
            container_visible=self.shell.cube_stack_container.isVisible(),
            editor_width=editor.width(),
            editor_global_left=editor_left,
            editor_left_gutter=left_gutter,
            editor_right_gutter=right_gutter,
            canvas_width=self.shell.canvas_tabs_container.width(),
            splitter_sizes=tuple(self.shell.splitter.sizes()),
            button_enabled=self.shell.cubeStackModeButton.isEnabled(),
            button_checked=self.shell.cubeStackModeButton.isChecked(),
            button_accessible_name=self.shell.cubeStackModeButton.accessibleName(),
        )

    def capture(self, path: Path, label: str) -> DirectWorkflowLayoutProbe:
        """Save a rendered shell image and return the matching geometry probe."""

        self.process_events()
        if not self.shell.grab().save(str(path)):
            raise AssertionError(f"failed to save harness image to {path}")
        return self.probe(label)

    @staticmethod
    def write_report(path: Path, probes: list[DirectWorkflowLayoutProbe]) -> None:
        """Write machine-inspectable geometry captured beside rendered images."""

        path.write_text(
            json.dumps([asdict(probe) for probe in probes], indent=2),
            encoding="utf-8",
        )

    def process_events(self) -> None:
        """Flush route, layout, visibility, and paint work."""

        self._base.process_events(cycles=6)


def _seed_control_probe(
    surface: str,
    label: object,
    widget: SeedBox,
) -> RenderedSeedControlProbe:
    """Return stable primitive geometry from one rendered seed label/control pair."""

    label_text = getattr(label, "text", None)
    label_visible = getattr(label, "isVisible", None)
    label_hidden = getattr(label, "isHidden", None)
    if (
        not callable(label_text)
        or not callable(label_visible)
        or not callable(label_hidden)
    ):
        raise AssertionError("seed label does not expose QWidget label state")
    hint = widget.sizeHint()
    minimum_hint = widget.minimumSizeHint()
    policy = widget.sizePolicy()
    line_edit = widget.line_edit.geometry()
    split_button = widget.split_button.geometry()
    return RenderedSeedControlProbe(
        surface=surface,
        label_text=str(label_text()),
        label_visible=bool(label_visible()),
        label_explicitly_hidden=bool(label_hidden()),
        widget_type=type(widget).__name__,
        size=(widget.width(), widget.height()),
        size_hint=(hint.width(), hint.height()),
        minimum_size_hint=(minimum_hint.width(), minimum_hint.height()),
        size_policy=(
            int(policy.horizontalPolicy().value),
            int(policy.verticalPolicy().value),
        ),
        line_edit_geometry=(
            line_edit.x(),
            line_edit.y(),
            line_edit.width(),
            line_edit.height(),
        ),
        split_button_geometry=(
            split_button.x(),
            split_button.y(),
            split_button.width(),
            split_button.height(),
        ),
    )


__all__ = [
    "DirectWorkflowLayoutProbe",
    "RealShellDirectWorkflowHarness",
    "RenderedSeedControlProbe",
]
