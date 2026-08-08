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

"""Project authoritative regional-mask collections into editor widgets."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QWidget

from substitute.application.workflows.regional_prompt_label_service import (
    RegionalPromptLabelService,
)
from substitute.domain.common import MaskAssociationKey
from substitute.domain.workflow import WorkflowState, workflow_asset_ref_authoring_value
from substitute.presentation.editor.panel.widgets.fields.regional_mask_batch import (
    RegionalMaskBatchEditor,
)


@dataclass(frozen=True, slots=True)
class RegionalMaskEditorSnapshot:
    """Describe ordered values and selection rendered by one editor."""

    values: tuple[str, ...]
    labels: tuple[str | None, ...]
    selected_index: int | None


class RegionalMaskEditorProjector:
    """Own durable collection projection into regional mask editor surfaces."""

    def __init__(
        self,
        labels: RegionalPromptLabelService | None = None,
    ) -> None:
        """Store the topology-owned regional label resolver."""

        self._labels = labels or RegionalPromptLabelService()

    def snapshot(
        self,
        workflow: WorkflowState,
        association_key: MaskAssociationKey,
    ) -> RegionalMaskEditorSnapshot | None:
        """Return the current editor snapshot for one durable collection."""

        collection = workflow.canvas.regional_mask_collection(association_key)
        if collection is None:
            return None
        selected_index = next(
            (
                index
                for index, entry in enumerate(collection.entries)
                if entry.region_id == collection.selected_region_id
            ),
            None,
        )
        return RegionalMaskEditorSnapshot(
            values=tuple(
                ""
                if entry.asset_ref is None
                else workflow_asset_ref_authoring_value(entry.asset_ref)
                for entry in collection.entries
            ),
            labels=self._labels.labels_for_mask(
                workflow,
                association_key,
                region_count=len(collection.entries),
            ),
            selected_index=selected_index,
        )

    def project_editor(
        self,
        editor: RegionalMaskBatchEditor,
        workflow: WorkflowState,
        association_key: MaskAssociationKey,
    ) -> bool:
        """Render one editor from its durable collection when present."""

        snapshot = self.snapshot(workflow, association_key)
        if snapshot is None:
            return False
        editor.set_regions(
            list(snapshot.values),
            labels=list(snapshot.labels),
            selected_index=snapshot.selected_index,
        )
        return True

    def project_panel(
        self,
        panel: QWidget,
        workflow: WorkflowState,
        association_key: MaskAssociationKey,
    ) -> int:
        """Render matching editors below one panel and return the updated count."""

        updated_count = 0
        for editor in panel.findChildren(RegionalMaskBatchEditor):
            if (editor.cube_alias, editor.node_name) != association_key:
                continue
            updated_count += int(self.project_editor(editor, workflow, association_key))
        return updated_count


__all__ = ["RegionalMaskEditorProjector", "RegionalMaskEditorSnapshot"]
