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

"""Coordinate transient regional hover across independently composed views."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QWidget

from substitute.application.workflows.regional_prompt_topology_service import (
    RegionalPromptTopology,
    RegionalPromptTopologyService,
)
from substitute.domain.common import MaskAssociationKey
from substitute.domain.workflow import WorkflowState
from substitute.presentation.editor.panel.widgets.fields.regional_mask_batch import (
    RegionalMaskBatchEditor,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)
from substitute.presentation.regional.canvas_hover_presenter import (
    RegionalCanvasHoverPresenter,
)

type _HoverSourceKey = tuple[str, int, str, str]


class RegionalInteractionCoordinator:
    """Resolve graph relationships and publish one transient regional hover."""

    def __init__(
        self,
        *,
        workflow: Callable[[], WorkflowState | None],
        active_panel: Callable[[], QWidget | None],
        canvas_hover: RegionalCanvasHoverPresenter,
        topology: RegionalPromptTopologyService | None = None,
    ) -> None:
        """Store authoritative workflow, panel, topology, and canvas owners."""

        self._workflow = workflow
        self._active_panel = active_panel
        self._canvas_hover = canvas_hover
        self._topology = topology or RegionalPromptTopologyService()
        self._source_key: _HoverSourceKey | None = None
        self._association_key: MaskAssociationKey | None = None

    def handle_prompt_hover(
        self,
        panel: QWidget,
        cube_alias: str,
        node_name: str,
        region_index: object,
    ) -> None:
        """Resolve one prompt separator hover to its graph-related mask endpoint."""

        source_key = ("prompt", id(panel), cube_alias, node_name)
        if not self._accept_source_event(panel, source_key, region_index):
            return
        workflow = self._workflow()
        if workflow is None:
            self._clear_views()
            return
        topology = self._topology.topology_for_prompt(
            workflow,
            cube_alias,
            node_name,
        )
        self._publish(topology, region_index)

    def handle_mask_hover(
        self,
        panel: QWidget,
        cube_alias: str,
        node_name: str,
        region_index: object,
    ) -> None:
        """Publish one ordered mask-row hover to related prompt and canvas views."""

        source_key = ("mask", id(panel), cube_alias, node_name)
        if not self._accept_source_event(panel, source_key, region_index):
            return
        workflow = self._workflow()
        if workflow is None:
            self._clear_views()
            return
        topology = self._topology.topology_for_mask(
            workflow,
            (cube_alias, node_name),
        )
        self._publish(topology, region_index)

    def clear(self) -> None:
        """Clear every transient regional hover publication."""

        self._source_key = None
        self._clear_views()

    def _accept_source_event(
        self,
        panel: QWidget,
        source_key: _HoverSourceKey,
        region_index: object,
    ) -> bool:
        """Reject inactive, malformed, and stale hover-source events."""

        if panel is not self._active_panel():
            return False
        if region_index is None:
            if self._source_key != source_key:
                return False
            self.clear()
            return False
        if isinstance(region_index, bool) or not isinstance(region_index, int):
            return False
        self._source_key = source_key
        return True

    def _publish(
        self,
        topology: RegionalPromptTopology | None,
        region_index: object,
    ) -> None:
        """Apply one validated hover index to every related view."""

        if topology is None or not isinstance(region_index, int):
            self._clear_views()
            return
        self._clear_views()
        self._association_key = topology.association_key
        panel = self._active_panel()
        if panel is not None:
            self._set_mask_editor_hover(panel, topology.association_key, region_index)
            self._set_prompt_hover(panel, topology, region_index)
        self._canvas_hover.show(topology.association_key, region_index)

    def _clear_views(self) -> None:
        """Clear the previously associated panel and CuteCanvas hover state."""

        association_key = self._association_key
        self._association_key = None
        panel = self._active_panel()
        if panel is not None and association_key is not None:
            workflow = self._workflow()
            topology = (
                None
                if workflow is None
                else self._topology.topology_for_mask(workflow, association_key)
            )
            self._set_mask_editor_hover(panel, association_key, None)
            if topology is not None:
                self._set_prompt_hover(panel, topology, None)
        self._canvas_hover.clear()

    @staticmethod
    def _set_mask_editor_hover(
        panel: QWidget,
        association_key: MaskAssociationKey,
        region_index: int | None,
    ) -> None:
        """Set linked hover on the exact native ordered-mask editor."""

        for editor in panel.findChildren(RegionalMaskBatchEditor):
            if (editor.cube_alias, editor.node_name) == association_key:
                editor.set_hovered_region(region_index)

    @staticmethod
    def _set_prompt_hover(
        panel: QWidget,
        topology: RegionalPromptTopology,
        region_index: int | None,
    ) -> None:
        """Set linked hover on all topology-related positive and negative prompts."""

        section_key = topology.association_key[0]
        prompt_nodes = frozenset(topology.prompt_node_names)
        for surface in panel.findChildren(PromptProjectionSurface):
            editor = _metadata_owner(surface, panel)
            if editor is None:
                continue
            metadata = editor.property("input_metadata")
            if not isinstance(metadata, dict):
                continue
            if (
                metadata.get("cube_alias") != section_key
                or metadata.get("node_name") not in prompt_nodes
            ):
                continue
            surface.set_region_hovered(region_index)


def _metadata_owner(surface: QWidget, panel: QWidget) -> QWidget | None:
    """Return the nearest prompt host carrying editor field identity."""

    parent = surface.parentWidget()
    while parent is not None and parent is not panel:
        if isinstance(parent.property("input_metadata"), dict):
            return parent
        parent = parent.parentWidget()
    return None


__all__ = ["RegionalInteractionCoordinator"]
