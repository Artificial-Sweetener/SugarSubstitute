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
from typing import Protocol

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

from substitute.domain.common import MaskAssociationKey
from substitute.presentation.editor.panel.panel_workflow_projection import (
    workflow_for_panel,
)
from substitute.presentation.regional.color_provider import authored_region_color
from substitute.presentation.regional.mask_editor_projection import (
    RegionalMaskEditorProjector,
)

type _MaskColorProvider = Callable[[int, int], QColor]


class _RegionalPreviewCoordinator(Protocol):
    """Bind ordered mask previews after their editor rows are projected."""

    def bind_regional_collection(
        self,
        association_key: MaskAssociationKey,
        *,
        panel: QWidget,
    ) -> bool:
        """Mount every available CuteCanvas preview for one mask collection."""


class RegionalMaskCollectionPresenter:
    """Render one ordered mask collection's colors, values, and selection."""

    def __init__(
        self,
        *,
        input_document: object,
        active_panel: Callable[[], object | None],
        mask_color: _MaskColorProvider,
        preview_coordinator: _RegionalPreviewCoordinator | None = None,
    ) -> None:
        """Capture authoritative workflow and linked view boundaries."""

        self._input_document = input_document
        self._active_panel = active_panel
        self._mask_color = mask_color
        self._preview_coordinator = preview_coordinator
        self._editor_projector = RegionalMaskEditorProjector()

    def refresh(self, association_key: MaskAssociationKey) -> None:
        """Project one current collection without relying on widget-local state."""

        panel = self._active_panel()
        if not isinstance(panel, QWidget):
            return
        workflow = workflow_for_panel(panel)
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
        self._editor_projector.project_panel(panel, workflow, association_key)
        if self._preview_coordinator is not None:
            self._preview_coordinator.bind_regional_collection(
                association_key,
                panel=panel,
            )


__all__ = ["RegionalMaskCollectionPresenter"]
