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

"""Pin legacy project asset references to their durable storage owner."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from substitute.domain.workflow import (
    ProjectAssetRef,
    ProjectMaskAssetRef,
    WorkflowState,
    workflow_asset_ref_from_json,
    workflow_asset_ref_to_json,
)
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("application.workflows.project_asset_owner_service")
_ASSET_REFS_KEY = "asset_refs"


class ProjectAssetOwnerService:
    """Give unowned legacy project references a stable directory identity."""

    def pin_legacy_owners(
        self,
        workflow: WorkflowState,
        *,
        storage_owner: str,
    ) -> int:
        """Bind every unowned project reference to its current directory."""

        if not storage_owner:
            raise ValueError("Project asset storage owner must not be empty.")
        pinned = self._pin_metadata_owners(workflow, storage_owner)
        for collection in workflow.canvas.regional_mask_collections.values():
            for index, entry in enumerate(collection.entries):
                asset_ref = entry.asset_ref
                if not isinstance(asset_ref, ProjectAssetRef | ProjectMaskAssetRef):
                    continue
                if asset_ref.storage_owner:
                    continue
                collection.entries[index] = replace(
                    entry,
                    asset_ref=replace(asset_ref, storage_owner=storage_owner),
                )
                pinned += 1
        log_info(
            _LOGGER,
            "Pinned workflow project assets to stable storage owner",
            storage_owner=storage_owner,
            pinned_asset_count=pinned,
        )
        return pinned

    @staticmethod
    def _pin_metadata_owners(workflow: WorkflowState, storage_owner: str) -> int:
        """Pin known serialized references while preserving unknown entries."""

        asset_refs = workflow.metadata.get(_ASSET_REFS_KEY)
        if not isinstance(asset_refs, dict):
            return 0
        pinned = 0
        for collection in asset_refs.values():
            if not isinstance(collection, dict):
                continue
            for key, payload in tuple(collection.items()):
                if not isinstance(payload, Mapping):
                    continue
                try:
                    asset_ref = workflow_asset_ref_from_json(payload)
                except ValueError:
                    continue
                if not isinstance(asset_ref, ProjectAssetRef | ProjectMaskAssetRef):
                    continue
                if asset_ref.storage_owner:
                    continue
                collection[key] = workflow_asset_ref_to_json(
                    replace(asset_ref, storage_owner=storage_owner)
                )
                pinned += 1
        return pinned


__all__ = ["ProjectAssetOwnerService"]
