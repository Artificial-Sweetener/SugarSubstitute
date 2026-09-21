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

"""Recover unresolved workflow masks from verified project-owned evidence."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Mapping
from uuid import UUID, uuid5

from substitute.domain.workflow import (
    ProjectAssetRef,
    ProjectMaskAssetRef,
    WorkflowState,
    workflow_asset_ref_from_json,
    workflow_asset_ref_to_json,
)
from substitute.domain.workspace_snapshot import InputMaskReference
from substitute.shared.logging.logger import get_logger, log_info
from substitute.infrastructure.persistence.workflow_mask_recovery_evidence import (
    WorkflowMaskRecoveryEvidence,
)

_LOGGER = get_logger("infrastructure.persistence.workflow_mask_asset_recovery")
_RECOVERY_NAMESPACE = UUID("1f356784-c123-42e9-a52a-53433670d170")


class WorkflowMaskAssetRecovery:
    """Rebind missing project masks to verified, preserved recovery evidence."""

    def __init__(self, *, projects_dir: Path) -> None:
        """Store the authoritative project root searched during restore."""

        self._projects_dir = projects_dir.resolve()
        self._evidence = WorkflowMaskRecoveryEvidence(projects_dir=self._projects_dir)

    def recover_reference(
        self,
        *,
        workflow_id: str,
        workflow: WorkflowState,
        reference: InputMaskReference,
        document_source_path: Path | None,
    ) -> InputMaskReference:
        """Return a verified path while retaining every original candidate."""

        if self._evidence.inspect(reference.path) is not None:
            return reference
        located = self._project_asset_ref(workflow, reference)
        if located is None:
            return reference
        asset_ref = located
        relative_path = self._safe_relative_path(asset_ref.relative_path)
        if relative_path is None:
            return reference

        explicit_owner = asset_ref.storage_owner.strip()
        if explicit_owner:
            explicit = self._evidence.canonical_candidate(explicit_owner, relative_path)
            if explicit is not None:
                return self._rebind(
                    workflow,
                    reference,
                    asset_ref,
                    workflow_id=workflow_id,
                    owner=explicit.owner,
                    path=explicit.path,
                )

        source_owner = self._source_owner(document_source_path)
        if source_owner:
            source_candidate = self._evidence.canonical_candidate(
                source_owner,
                relative_path,
            )
            if source_candidate is not None:
                return self._rebind(
                    workflow,
                    reference,
                    asset_ref,
                    workflow_id=workflow_id,
                    owner=source_candidate.owner,
                    path=source_candidate.path,
                )

        canonical = self._evidence.canonical_candidates(relative_path)
        nonblank_canonical = tuple(
            candidate for candidate in canonical if candidate.has_authored_pixels
        )
        selected = self._evidence.select_equivalent(
            nonblank_canonical,
            workflow_id=workflow_id,
            mask_id=reference.mask_id,
            source_kind="legacy_project",
        )
        if selected is not None:
            return self._rebind(
                workflow,
                reference,
                asset_ref,
                workflow_id=workflow_id,
                owner=selected.owner,
                path=selected.path,
            )
        if nonblank_canonical:
            return reference

        generation = tuple(
            candidate
            for candidate in self._evidence.generation_candidates(reference.mask_id)
            if candidate.has_authored_pixels
        )
        selected = self._evidence.select_equivalent(
            generation,
            workflow_id=workflow_id,
            mask_id=reference.mask_id,
            source_kind="generation_revision",
        )
        if selected is not None:
            recovery_owner = self._recovery_owner(
                workflow_id=workflow_id,
                mask_id=reference.mask_id,
                digest=selected.digest,
            )
            destination = self._projects_dir / recovery_owner / "masks" / relative_path
            copied = self._evidence.copy_verified(selected, destination)
            if copied is not None:
                return self._rebind(
                    workflow,
                    reference,
                    asset_ref,
                    workflow_id=workflow_id,
                    owner=recovery_owner,
                    path=copied,
                )
        if generation:
            return reference

        selected = self._evidence.select_equivalent(
            canonical,
            workflow_id=workflow_id,
            mask_id=reference.mask_id,
            source_kind="blank_project",
        )
        if selected is not None:
            return self._rebind(
                workflow,
                reference,
                asset_ref,
                workflow_id=workflow_id,
                owner=selected.owner,
                path=selected.path,
            )
        return reference

    def _project_asset_ref(
        self,
        workflow: WorkflowState,
        reference: InputMaskReference,
    ) -> ProjectAssetRef | ProjectMaskAssetRef | None:
        """Return the durable project reference matching one snapshot mask."""

        try:
            mask_id = UUID(reference.mask_id)
        except ValueError:
            return None
        for collection in workflow.canvas.regional_mask_collections.values():
            entry = collection.entry_for_mask(mask_id)
            if entry is not None and isinstance(
                entry.asset_ref,
                ProjectAssetRef | ProjectMaskAssetRef,
            ):
                return entry.asset_ref
        association_key = reference.association_key
        if association_key is None:
            return None
        asset_refs = workflow.metadata.get("asset_refs")
        if not isinstance(asset_refs, Mapping):
            return None
        input_masks = asset_refs.get("input_masks")
        if not isinstance(input_masks, Mapping):
            return None
        payload = input_masks.get(":".join(association_key))
        if not isinstance(payload, Mapping):
            return None
        try:
            asset_ref = workflow_asset_ref_from_json(payload)
        except ValueError:
            return None
        return (
            asset_ref
            if isinstance(asset_ref, ProjectAssetRef | ProjectMaskAssetRef)
            else None
        )

    def _rebind(
        self,
        workflow: WorkflowState,
        reference: InputMaskReference,
        asset_ref: ProjectAssetRef | ProjectMaskAssetRef,
        *,
        workflow_id: str,
        owner: str,
        path: Path,
    ) -> InputMaskReference:
        """Bind the verified storage owner while preserving relative graph values."""

        rebound = replace(asset_ref, storage_owner=owner)
        try:
            mask_id = UUID(reference.mask_id)
        except ValueError:
            return reference
        rebound_count = 0
        for collection in workflow.canvas.regional_mask_collections.values():
            entry = collection.entry_for_mask(mask_id)
            if entry is not None:
                collection.bind_asset(entry.region_id, rebound)
                rebound_count += 1
        association_key = reference.association_key
        if association_key is not None:
            asset_refs = workflow.metadata.get("asset_refs")
            if isinstance(asset_refs, dict):
                input_masks = asset_refs.get("input_masks")
                key = ":".join(association_key)
                if isinstance(input_masks, dict) and key in input_masks:
                    input_masks[key] = workflow_asset_ref_to_json(rebound)
                    rebound_count += 1
        if rebound_count == 0:
            return reference
        log_info(
            _LOGGER,
            "Recovered workflow mask from preserved asset evidence",
            workflow_id=workflow_id,
            mask_id=reference.mask_id,
            storage_owner=owner,
            recovery_source_preserved=True,
        )
        return replace(reference, path=path)

    def _source_owner(self, source_path: Path | None) -> str:
        """Return a project owner encoded by an explicit saved workflow path."""

        if source_path is None:
            return ""
        try:
            relative = source_path.resolve().relative_to(self._projects_dir)
        except (OSError, ValueError):
            return ""
        return relative.parts[0] if len(relative.parts) > 1 else ""

    @staticmethod
    def _safe_relative_path(value: str) -> Path | None:
        """Return a portable project-relative path without traversal."""

        path = Path(value)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            return None
        return path

    @staticmethod
    def _recovery_owner(*, workflow_id: str, mask_id: str, digest: str) -> str:
        """Return a stable filesystem-safe owner for one recovered artifact."""

        identity = uuid5(
            _RECOVERY_NAMESPACE,
            f"{workflow_id}\0{mask_id}\0{digest}",
        )
        return f"recovered-{identity}"


__all__ = ["WorkflowMaskAssetRecovery"]
