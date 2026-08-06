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

"""Capture scalar and ordered Input mask archive references."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from substitute.domain.workflow import WorkflowAssetRef, WorkflowState
from substitute.domain.workspace_snapshot import InputMaskReference


class InputMaskAssetReader(Protocol):
    """Resolve legacy scalar mask assets for snapshot capture."""

    def input_mask_asset_ref(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
    ) -> WorkflowAssetRef | None:
        """Return the mask asset associated with one scalar endpoint."""


class InputMaskSnapshotReferenceService:
    """Build restorable mask references from authoritative canvas state."""

    def __init__(
        self,
        *,
        scalar_asset_reader: InputMaskAssetReader,
        path_for_asset_ref: Callable[[object, str], Path | None],
    ) -> None:
        """Store asset and local-path boundaries used by snapshot capture."""

        self._scalar_asset_reader = scalar_asset_reader
        self._path_for_asset_ref = path_for_asset_ref

    def references(
        self,
        workflow: WorkflowState,
        *,
        workflow_name: str,
    ) -> tuple[InputMaskReference, ...]:
        """Return scalar masks followed by ordered masks in collection order."""

        references: list[InputMaskReference] = []
        for scalar_entry in workflow.canvas.mask_entries.values():
            cube_alias, node_name = scalar_entry.association_key
            asset_ref = self._scalar_asset_reader.input_mask_asset_ref(
                workflow,
                section_key=cube_alias,
                node_name=node_name,
            )
            path = self._path_for_asset_ref(asset_ref, workflow_name)
            if path is None:
                continue
            references.append(
                InputMaskReference(
                    mask_id=str(scalar_entry.mask_id),
                    image_id=str(scalar_entry.image_id),
                    path=path,
                    association_key=(cube_alias, node_name),
                )
            )
        for collection in workflow.canvas.regional_mask_collections.values():
            cube_alias, node_name = collection.association_key
            for regional_entry in collection.entries:
                if regional_entry.mask_id is None or regional_entry.asset_ref is None:
                    continue
                path = self._path_for_asset_ref(regional_entry.asset_ref, workflow_name)
                if path is None:
                    continue
                references.append(
                    InputMaskReference(
                        mask_id=str(regional_entry.mask_id),
                        image_id=str(regional_entry.image_id),
                        path=path,
                        association_key=(cube_alias, node_name),
                    )
                )
        return tuple(references)


__all__ = ["InputMaskSnapshotReferenceService"]
