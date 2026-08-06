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

"""Project authoritative regional-mask collections into their linked views."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

from substitute.domain.common import MaskAssociationKey
from substitute.domain.workflow import WorkflowState
from substitute.presentation.regional.mask_editor_projection import (
    RegionalMaskEditorProjector,
)
from substitute.presentation.regional.color_provider import authored_region_color

type _MaskColorProvider = Callable[[int, int], QColor]


class RegionalMaskCollectionPresenter:
    """Render one ordered mask collection's colors, values, and selection."""

    def __init__(
        self,
        *,
        input_document: object,
        active_workflow: Callable[[], WorkflowState | None],
        active_panel: Callable[[], object | None],
        mask_color: _MaskColorProvider,
    ) -> None:
        """Capture authoritative workflow and linked view boundaries."""

        self._input_document = input_document
        self._active_workflow = active_workflow
        self._active_panel = active_panel
        self._mask_color = mask_color
        self._editor_projector = RegionalMaskEditorProjector()

    def refresh(self, association_key: MaskAssociationKey) -> None:
        """Project one current collection without relying on widget-local state."""

        workflow = self._active_workflow()
        if workflow is None:
            return
        collection = workflow.canvas.regional_mask_collection(association_key)
        if collection is None:
            return
        materialized_entries = tuple(
            entry for entry in collection.entries if entry.mask_id is not None
        )
        set_mask_properties = getattr(
            self._input_document,
            "set_mask_properties",
            None,
        )
        if callable(set_mask_properties):
            for index, entry in enumerate(materialized_entries):
                assert entry.mask_id is not None
                set_mask_properties(
                    entry.mask_id,
                    color=authored_region_color(
                        entry.authored_color,
                        self._mask_color(index, len(materialized_entries)),
                    ),
                )
        panel = self._active_panel()
        if not isinstance(panel, QWidget):
            return
        self._editor_projector.project_panel(panel, workflow, association_key)


__all__ = ["RegionalMaskCollectionPresenter"]
