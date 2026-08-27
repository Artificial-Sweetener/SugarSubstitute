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

"""Observe rendered direct-workflow widgets and write layout artifacts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.shell import (
    DirectWorkflowShell,
)


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


def rendered_node_cards(
    shell: DirectWorkflowShell,
    workflow_id: str | None = None,
) -> tuple[tuple[str, str], ...]:
    """Return unique node ids and classes rendered by one editor panel."""

    panel = shell.shell.editor_panels[workflow_id or shell.direct_workflow_id]
    cards = {
        (str(node_name), str(class_type))
        for widget in panel.findChildren(QWidget)
        if (node_name := widget.property("node_name"))
        and (class_type := widget.property("node_class_type"))
    }
    return tuple(sorted(cards))


def rendered_node_names(
    shell: DirectWorkflowShell,
    workflow_id: str | None = None,
) -> tuple[str, ...]:
    """Return unique rendered node names for one editor panel."""

    return tuple(
        node_name for node_name, _class_type in rendered_node_cards(shell, workflow_id)
    )


def wait_for_rendered_node_names(
    shell: DirectWorkflowShell,
    expected_node_names: frozenset[str],
    *,
    workflow_id: str | None = None,
) -> None:
    """Wait until one panel exposes all expected production node cards."""

    resolved_workflow_id = workflow_id or shell.direct_workflow_id
    panel = shell.shell.editor_panels[resolved_workflow_id]

    def expected_projection_visible() -> bool:
        """Finalize eligible reveals and inspect semantic node identities."""

        if panel.has_pending_visible_projection_commit():
            panel.finalize_pending_visible_projection()
        return (
            expected_node_names.issubset(
                rendered_node_names(shell, resolved_workflow_id)
            )
            and not panel.is_projection_active()
        )

    shell.wait_until(
        expected_projection_visible,
        description=(
            f"workflow {resolved_workflow_id!r} cards {sorted(expected_node_names)!r}"
        ),
    )


def rendered_prompt_fields(shell: DirectWorkflowShell) -> tuple[tuple[str, str], ...]:
    """Return direct-workflow fields mounted as production PromptEditors."""

    panel = shell.shell.editor_panels[shell.direct_workflow_id]
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


def rendered_node_card_order(shell: DirectWorkflowShell) -> tuple[str, ...]:
    """Return production masonry insertion order for the direct section."""

    panel = shell.shell.editor_panels[shell.direct_workflow_id]
    prompt_editor = next(iter(panel.findChildren(PromptEditor)), None)
    ancestor = prompt_editor.parentWidget() if prompt_editor is not None else None
    while ancestor is not None:
        node_card_order = getattr(ancestor, "node_card_order", None)
        if callable(node_card_order):
            return tuple(node_card_order())
        ancestor = ancestor.parentWidget()
    raise AssertionError("direct workflow masonry owner is unavailable")


def layout_probe(shell: DirectWorkflowShell, label: str) -> DirectWorkflowLayoutProbe:
    """Read geometry from the production workspace widgets."""

    controller = shell.shell.cube_stack_presentation_controller
    editor = shell.shell.editor_panel_container
    editor_left = editor.mapToGlobal(QPoint(0, 0)).x()
    active_editor = shell.shell.active_editor_panel
    if active_editor is None:
        raise AssertionError("active editor panel is unavailable")
    left_gutter, right_gutter = active_editor.content_horizontal_gutters()
    return DirectWorkflowLayoutProbe(
        label=label,
        mode=controller.mode.value,
        generation=controller.active_generation,
        animating=controller.is_animating,
        container_width=shell.shell.cube_stack_container.width(),
        container_visible=shell.shell.cube_stack_container.isVisible(),
        editor_width=editor.width(),
        editor_global_left=editor_left,
        editor_left_gutter=left_gutter,
        editor_right_gutter=right_gutter,
        canvas_width=shell.shell.canvas_host_container.width(),
        splitter_sizes=tuple(shell.shell.splitter.sizes()),
        button_enabled=shell.shell.cubeStackModeButton.isEnabled(),
        button_checked=shell.shell.cubeStackModeButton.isChecked(),
        button_accessible_name=shell.shell.cubeStackModeButton.accessibleName(),
    )


def capture_layout(
    shell: DirectWorkflowShell,
    path: Path,
    label: str,
) -> DirectWorkflowLayoutProbe:
    """Save a rendered shell image and return its matching geometry probe."""

    shell.process_events()
    if not shell.shell.grab().save(str(path)):
        raise AssertionError(f"failed to save harness image to {path}")
    return layout_probe(shell, label)


def write_layout_report(path: Path, probes: list[DirectWorkflowLayoutProbe]) -> None:
    """Write machine-inspectable geometry beside rendered images."""

    path.write_text(
        json.dumps([asdict(probe) for probe in probes], indent=2),
        encoding="utf-8",
    )
