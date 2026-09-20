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

"""Verify non-destructive recovery of workflow mask asset evidence."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from PIL import Image

from substitute.domain.workflow import ProjectMaskAssetRef, WorkflowState
from substitute.domain.workspace_snapshot import InputMaskReference
from substitute.infrastructure.persistence.workflow_mask_asset_recovery import (
    WorkflowMaskAssetRecovery,
)


def test_missing_mask_recovers_authored_generation_revision_without_overwrite(
    tmp_path: Path,
) -> None:
    """A nonblank generation revision should outrank a legacy blank placeholder."""

    projects_dir = tmp_path / "projects"
    workflow, reference, relative_path = _workflow_and_reference(projects_dir)
    legacy = projects_dir / "Untitled Workflow" / "masks" / relative_path
    generation = (
        projects_dir
        / "Untitled Workflow"
        / "masks"
        / ".generation"
        / reference.mask_id
        / "1.png"
    )
    _save_mask(legacy, value=0)
    _save_mask(generation, value=255)
    legacy_digest = _digest(legacy)
    generation_digest = _digest(generation)

    recovered = WorkflowMaskAssetRecovery(projects_dir=projects_dir).recover_reference(
        workflow_id="legacy-label-id",
        workflow=workflow,
        reference=reference,
        document_source_path=None,
    )

    entry = next(iter(workflow.canvas.regional_mask_collections.values())).entries[0]
    assert isinstance(entry.asset_ref, ProjectMaskAssetRef)
    assert entry.asset_ref.storage_owner.startswith("recovered-")
    assert entry.asset_ref.relative_path == str(relative_path)
    assert recovered.path.is_file()
    assert _digest(recovered.path) == generation_digest
    assert _digest(legacy) == legacy_digest
    assert _digest(generation) == generation_digest


def test_conflicting_generation_revisions_remain_unresolved_and_preserved(
    tmp_path: Path,
) -> None:
    """Conflicting authored candidates must not be selected or overwritten."""

    projects_dir = tmp_path / "projects"
    workflow, reference, _relative_path = _workflow_and_reference(projects_dir)
    generation_root = (
        projects_dir / "Untitled Workflow" / "masks" / ".generation" / reference.mask_id
    )
    first = generation_root / "1.png"
    second = generation_root / "2.png"
    _save_mask(first, value=64)
    _save_mask(second, value=255)
    before = (_digest(first), _digest(second))

    recovered = WorkflowMaskAssetRecovery(projects_dir=projects_dir).recover_reference(
        workflow_id="legacy-label-id",
        workflow=workflow,
        reference=reference,
        document_source_path=None,
    )

    entry = next(iter(workflow.canvas.regional_mask_collections.values())).entries[0]
    assert recovered == reference
    assert isinstance(entry.asset_ref, ProjectMaskAssetRef)
    assert entry.asset_ref.storage_owner == ""
    assert (_digest(first), _digest(second)) == before
    assert not tuple(projects_dir.glob("recovered-*"))


def test_equivalent_generation_revisions_choose_newest_without_source_mutation(
    tmp_path: Path,
) -> None:
    """Equivalent revisions should recover deterministically from the newest evidence."""

    projects_dir = tmp_path / "projects"
    workflow, reference, _relative_path = _workflow_and_reference(projects_dir)
    generation_root = (
        projects_dir / "Untitled Workflow" / "masks" / ".generation" / reference.mask_id
    )
    first = generation_root / "1.png"
    second = generation_root / "2.png"
    _save_mask(first, value=255)
    _save_mask(second, value=255)
    first.touch()
    second.touch()
    before = (_digest(first), _digest(second))

    recovered = WorkflowMaskAssetRecovery(projects_dir=projects_dir).recover_reference(
        workflow_id="legacy-label-id",
        workflow=workflow,
        reference=reference,
        document_source_path=None,
    )

    assert recovered.path.is_file()
    assert _digest(recovered.path) == before[1]
    assert (_digest(first), _digest(second)) == before


def test_corrupt_zero_byte_and_wrong_format_candidates_are_ignored(
    tmp_path: Path,
) -> None:
    """Only a decodable image may become authoritative recovery evidence."""

    projects_dir = tmp_path / "projects"
    workflow, reference, relative_path = _workflow_and_reference(projects_dir)
    corrupt = projects_dir / "Corrupt" / "masks" / relative_path
    zero_byte = projects_dir / "Empty" / "masks" / relative_path
    wrong_format = projects_dir / "Wrong" / "masks" / relative_path
    valid = (
        projects_dir
        / "Evidence"
        / "masks"
        / ".generation"
        / reference.mask_id
        / "valid.png"
    )
    corrupt.parent.mkdir(parents=True, exist_ok=True)
    corrupt.write_bytes(b"\x89PNG\r\ntruncated")
    zero_byte.parent.mkdir(parents=True, exist_ok=True)
    zero_byte.write_bytes(b"")
    wrong_format.parent.mkdir(parents=True, exist_ok=True)
    wrong_format.write_text("not an image", encoding="utf-8")
    _save_mask(valid, value=192)

    recovered = WorkflowMaskAssetRecovery(projects_dir=projects_dir).recover_reference(
        workflow_id="legacy-label-id",
        workflow=workflow,
        reference=reference,
        document_source_path=None,
    )

    assert recovered.path.is_file()
    assert _digest(recovered.path) == _digest(valid)
    assert corrupt.read_bytes() == b"\x89PNG\r\ntruncated"
    assert zero_byte.read_bytes() == b""
    assert wrong_format.read_text(encoding="utf-8") == "not an image"


def test_existing_verified_recovery_target_is_never_overwritten(
    tmp_path: Path,
) -> None:
    """A later conflicting revision cannot replace the already rebound good asset."""

    projects_dir = tmp_path / "projects"
    workflow, reference, _relative_path = _workflow_and_reference(projects_dir)
    generation_root = (
        projects_dir / "Untitled Workflow" / "masks" / ".generation" / reference.mask_id
    )
    first = generation_root / "1.png"
    _save_mask(first, value=64)
    recovery = WorkflowMaskAssetRecovery(projects_dir=projects_dir)

    recovered = recovery.recover_reference(
        workflow_id="legacy-label-id",
        workflow=workflow,
        reference=reference,
        document_source_path=None,
    )
    recovered_digest = _digest(recovered.path)
    second = generation_root / "2.png"
    _save_mask(second, value=255)

    repeated = recovery.recover_reference(
        workflow_id="legacy-label-id",
        workflow=workflow,
        reference=reference,
        document_source_path=None,
    )

    assert repeated.path == recovered.path
    assert _digest(repeated.path) == recovered_digest
    assert _digest(first) == recovered_digest
    assert _digest(second) != recovered_digest


def _workflow_and_reference(
    projects_dir: Path,
) -> tuple[WorkflowState, InputMaskReference, Path]:
    """Build one ordered mask with a missing regression-era snapshot path."""

    workflow = WorkflowState()
    image_id = uuid4()
    mask_id = uuid4()
    relative_path = Path("regions") / "left.png"
    collection = workflow.canvas.ensure_regional_mask_collection(("Region", "masks"))
    collection.add_region(
        image_id,
        mask_id=mask_id,
        asset_ref=ProjectMaskAssetRef(relative_path=str(relative_path)),
    )
    reference = InputMaskReference(
        mask_id=str(mask_id),
        image_id=str(image_id),
        path=projects_dir / "Renamed Workflow" / "masks" / relative_path,
        association_key=("Region", "masks"),
    )
    return workflow, reference, relative_path


def _save_mask(path: Path, *, value: int) -> None:
    """Write one deterministic grayscale mask fixture."""

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("L", (8, 8), color=value).save(path)


def _digest(path: Path) -> str:
    """Return the exact SHA-256 of one fixture."""

    return sha256(path.read_bytes()).hexdigest()
