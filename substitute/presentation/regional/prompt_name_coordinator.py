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

"""Coordinate canonical regional prompt names with their mounted projections."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QWidget

from substitute.application.workflows.regional_prompt_label_service import (
    RegionalPromptLabelService,
)
from substitute.application.workflows.regional_prompt_name_models import (
    RegionalPromptNameSynchronization,
)
from substitute.application.workflows.regional_prompt_name_synchronization_service import (
    RegionalPromptNameSynchronizationService,
)
from substitute.application.workflows.regional_prompt_topology_service import (
    RegionalPromptTopology,
    RegionalPromptTopologyService,
)
from substitute.domain.workflow import WorkflowState
from substitute.presentation.editor.panel.panel_workflow_projection import (
    workflow_for_panel,
)
from substitute.presentation.editor.panel.widgets.fields.regional_mask_batch import (
    RegionalMaskBatchEditor,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)


class RegionalPromptNameCoordinator:
    """Apply one Substitute-owned name invariant to graph and mounted editors."""

    def __init__(
        self,
        *,
        workflow: Callable[[], WorkflowState | None],
        active_panel: Callable[[], QWidget | None],
        topology: RegionalPromptTopologyService,
        labels: RegionalPromptLabelService | None = None,
        names: RegionalPromptNameSynchronizationService | None = None,
    ) -> None:
        """Store canonical workflow owners and presentation boundaries."""

        self._workflow = workflow
        self._active_panel = active_panel
        self._topology = topology
        self._labels = labels or RegionalPromptLabelService(topology=topology)
        self._names = names or RegionalPromptNameSynchronizationService(
            topology=topology
        )

    def handle_prompt_text_changed(
        self,
        panel: QWidget,
        cube_alias: str,
        node_name: str,
        previous_source_text: str,
        current_source_text: str,
    ) -> None:
        """Synchronize one authored transition and refresh every related live view."""

        if panel is not self._active_panel():
            return
        workflow = self._workflow()
        if workflow is None:
            return
        synchronization = self._names.synchronize_prompt_edit(
            workflow,
            section_key=cube_alias,
            prompt_node_name=node_name,
            previous_source_text=previous_source_text,
            current_source_text=current_source_text,
        )
        self._project_prompt_sources(panel, synchronization)
        topology = self._topology.topology_for_prompt(
            workflow,
            cube_alias,
            node_name,
        )
        if topology is not None:
            self._refresh_mask_names(panel, workflow, topology)

    def normalize_for_prompt(
        self,
        panel: QWidget,
        cube_alias: str,
        node_name: str,
    ) -> None:
        """Normalize canonical names when one prompt editor is mounted."""

        workflow = workflow_for_panel(panel)
        if workflow is None:
            return
        synchronization = self._names.normalize_for_prompt(
            workflow,
            section_key=cube_alias,
            prompt_node_name=node_name,
        )
        self._project_prompt_sources(panel, synchronization)
        topology = self._topology.topology_for_prompt(
            workflow,
            cube_alias,
            node_name,
        )
        if topology is not None:
            self._refresh_mask_names(panel, workflow, topology)

    def normalize_for_mask(
        self,
        panel: QWidget,
        cube_alias: str,
        node_name: str,
    ) -> None:
        """Normalize canonical names when one ordered mask editor is mounted."""

        workflow = workflow_for_panel(panel)
        if workflow is None:
            return
        association_key = (cube_alias, node_name)
        synchronization = self._names.normalize_for_mask(
            workflow,
            association_key,
        )
        self._project_prompt_sources(panel, synchronization)
        topology = self._topology.topology_for_mask(workflow, association_key)
        if topology is not None:
            self._refresh_mask_names(panel, workflow, topology)

    def _refresh_mask_names(
        self,
        panel: QWidget,
        workflow: WorkflowState,
        topology: RegionalPromptTopology,
    ) -> None:
        """Project canonical names onto one related ordered-mask editor."""

        collection = workflow.canvas.regional_mask_collection(topology.association_key)
        if collection is None:
            return
        labels = self._labels.labels_for_mask(
            workflow,
            topology.association_key,
            region_count=len(collection.entries),
        )
        for editor in panel.findChildren(RegionalMaskBatchEditor):
            if (editor.cube_alias, editor.node_name) == topology.association_key:
                editor.set_region_names(list(labels))

    @staticmethod
    def _project_prompt_sources(
        panel: QWidget,
        synchronization: RegionalPromptNameSynchronization,
    ) -> None:
        """Project changed canonical prompt values into mounted peer editors."""

        updates = {update.node_name: update for update in synchronization.updates}
        if not updates:
            return
        for surface in panel.findChildren(PromptProjectionSurface):
            editor = _metadata_owner(surface, panel)
            if editor is None:
                continue
            metadata = editor.property("input_metadata")
            if not isinstance(metadata, dict):
                continue
            if metadata.get("cube_alias") != synchronization.section_key:
                continue
            update = updates.get(str(metadata.get("node_name")))
            if update is None or surface.toPlainText() == update.source_text:
                continue
            surface.source_commands.synchronize_source_text(
                update.source_text,
                replacements=tuple(
                    (
                        replacement.source_start,
                        replacement.source_end,
                        replacement.replacement_text,
                    )
                    for replacement in update.replacements
                ),
            )


def _metadata_owner(surface: QWidget, panel: QWidget) -> QWidget | None:
    """Return the nearest prompt host carrying editor field identity."""

    parent = surface.parentWidget()
    while parent is not None and parent is not panel:
        if isinstance(parent.property("input_metadata"), dict):
            return parent
        parent = parent.parentWidget()
    return None


__all__ = ["RegionalPromptNameCoordinator"]
