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

"""Build and inspect global override controls in the mounted production shell."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.panel.overrides_controller import (
    GlobalOverridesManager,
)
from substitute.presentation.editor.panel.override_control_identity import (
    OVERRIDE_CONTROL_ROLE,
    OVERRIDE_KEY_PROPERTY,
    OVERRIDE_LABEL_ROLE,
    OVERRIDE_ROLE_PROPERTY,
)
from substitute.presentation.widgets import SeedBox
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.shell import (
    DirectWorkflowShell,
)


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


def install_cube_seed_control(
    shell: DirectWorkflowShell,
    *,
    node_definitions: Mapping[str, Mapping[str, object]],
    value: int = 7,
) -> None:
    """Add a resolved cube seed field to the production cube surface."""

    workflow = shell.shell.workflow_session_service.get_workflow(shell.cube_workflow_id)
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
    workflow.global_overrides = {"seed": {"value": value, "mode": "global"}}
    shell.shell.node_definition_gateway.install_recorded_definitions(node_definitions)
    panel = shell.shell.editor_panels[shell.cube_workflow_id]
    panel.clear_layout()
    panel.load_all_cubes(
        [(cube_alias, cube_state)],
        cube_states={cube_alias: cube_state},
        stack_order=[cube_alias],
    )
    shell.activate_cube(animated=False)

    def projection_complete() -> bool:
        """Finalize cube projection before exposing rendered geometry."""

        if panel.has_pending_visible_projection_commit():
            panel.finalize_pending_visible_projection()
        shell.process_events()
        seed_is_rendered = any(
            field_key == "seed"
            for _section, _node_name, field_key in cast(
                dict[tuple[str, str, str], QWidget],
                getattr(panel, "input_widgets_by_field_key"),
            )
        )
        return seed_is_rendered and not panel.is_projection_active()

    shell.wait_until(
        projection_complete,
        description="complete cube seed-control projection",
    )
    manager = override_manager(shell, shell.cube_workflow_id)
    manager.sync_state_from_workflow()
    manager.rebuild_active_override_controls()
    shell.process_events()


def seed_toolbar_probe(
    shell: DirectWorkflowShell,
    workflow_id: str,
) -> RenderedSeedControlProbe:
    """Return toolbar label and SeedBox geometry for one workflow."""

    manager = override_manager(shell, workflow_id)
    manager.rebuild_active_override_controls()
    shell.process_events()
    label, widget = override_surface(shell, workflow_id, "seed")
    if not isinstance(widget, SeedBox):
        raise AssertionError(f"seed override rendered {type(widget).__name__}")
    return seed_control_probe("toolbar", label, widget)


def seed_field_probe(
    shell: DirectWorkflowShell,
    workflow_id: str,
    field_key: str,
) -> RenderedSeedControlProbe:
    """Return a node-card seed field and its row-label geometry."""

    panel = shell.shell.editor_panels[workflow_id]
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
            (identity, type(widget).__name__) for identity, widget in widgets.items()
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
    return seed_control_probe("node_card", label, widget)


def active_override_keys(shell: DirectWorkflowShell) -> tuple[str, ...]:
    """Return toolbar override keys mounted by the direct production manager."""

    override_manager(shell, shell.direct_workflow_id).rebuild_active_override_controls()
    shell.process_events()
    return tuple(
        sorted(
            {
                str(widget.property(OVERRIDE_KEY_PROPERTY))
                for widget in shell.shell.menu_bar.findChildren(QWidget)
                if widget.property(OVERRIDE_ROLE_PROPERTY) == OVERRIDE_CONTROL_ROLE
                and widget.property(OVERRIDE_KEY_PROPERTY)
                and not widget.isHidden()
            }
        )
    )


def set_global_override_value(
    shell: DirectWorkflowShell,
    override_key: str,
    value: object,
) -> None:
    """Commit a value through the mounted direct toolbar control."""

    _label, widget = override_surface(shell, shell.direct_workflow_id, override_key)
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
    shell.process_events()


def override_manager(
    shell: DirectWorkflowShell,
    workflow_id: str,
) -> GlobalOverridesManager:
    """Return the mounted override manager for one harness workflow."""

    return cast(GlobalOverridesManager, shell.shell.override_managers[workflow_id])


def override_surface(
    shell: DirectWorkflowShell,
    workflow_id: str,
    override_key: str,
) -> tuple[QWidget, QWidget]:
    """Resolve one toolbar label/control pair through published Qt identity."""

    override_manager(shell, workflow_id).rebuild_active_override_controls()
    shell.process_events()
    matching = [
        widget
        for widget in shell.shell.menu_bar.findChildren(QWidget)
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


def seed_control_probe(
    surface: str,
    label: object,
    widget: SeedBox,
) -> RenderedSeedControlProbe:
    """Return stable geometry from one rendered seed label/control pair."""

    label_text = getattr(label, "text", None)
    label_visible = getattr(label, "isVisible", None)
    label_hidden = getattr(label, "isHidden", None)
    if not (
        callable(label_text) and callable(label_visible) and callable(label_hidden)
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
