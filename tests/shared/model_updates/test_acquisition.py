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

"""Verify explicit model updates download beside current files."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
import hashlib
from pathlib import Path

from sugarsubstitute_shared.model_acquisition import ModelAcquisitionService
from sugarsubstitute_shared.model_discovery import DiscoveredModel, ModelArtifactKind
from sugarsubstitute_shared.model_updates import (
    ModelUpdateAcquisitionService,
    ModelUpdateProposal,
    ModelUsageRecord,
    model_update_identity,
)


class _Stream:
    """Expose a deterministic model body."""

    def __init__(self, payload: bytes) -> None:
        """Store unread bytes."""

        self._payload = payload
        self.content_length = len(payload)

    def read(self, size: int) -> bytes:
        """Return a bounded response chunk."""

        chunk, self._payload = self._payload[:size], self._payload[size:]
        return chunk

    def close(self) -> None:
        """Release the response."""


def test_selected_update_is_verified_and_current_file_remains_byte_identical(
    tmp_path: Path,
) -> None:
    """Downloading a new version must never overwrite the referenced old model."""

    model_root = tmp_path / "models"
    current_path = model_root / "checkpoints" / "model.safetensors"
    current_path.parent.mkdir(parents=True)
    current_path.write_bytes(b"current")
    payload = b"new-version"
    candidate = DiscoveredModel(
        artifact_kind=ModelArtifactKind.CHECKPOINTS,
        model_id=7,
        version_id=9,
        model_name="Model",
        version_name="v9",
        creator="Creator",
        base_model="SDXL",
        file_name=current_path.name,
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        download_url="https://civitai.com/api/download/models/9",
        model_page_url="https://civitai.com/models/7",
        thumbnail_url=None,
        provider_rank=1,
    )
    proposal = ModelUpdateProposal(
        current=ModelUsageRecord(
            sha256="a" * 64,
            path=current_path,
            artifact_kind=ModelArtifactKind.CHECKPOINTS,
            model_id=7,
            version_id=8,
            base_model="SDXL",
            usage_count=1,
            last_used_at=datetime(2026, 8, 31, tzinfo=UTC),
        ),
        candidate=candidate,
    )

    def open_stream(url: str, headers: Mapping[str, str], timeout: float) -> _Stream:
        """Return test bytes at the trusted provider boundary."""

        _ = (url, headers, timeout)
        return _Stream(payload)

    service = ModelUpdateAcquisitionService(
        model_root=model_root,
        acquisition=ModelAcquisitionService(
            allowed_roots=(model_root,),
            stream_opener=open_stream,
        ),
    )

    results = service.download_selected(
        (proposal,),
        selected_identities=(model_update_identity(proposal),),
    )

    assert current_path.read_bytes() == b"current"
    assert len(results) == 1
    assert results[0].path != current_path
    assert results[0].path.read_bytes() == payload


def test_unreviewed_identity_cannot_start_update_download(tmp_path: Path) -> None:
    """A forged UI identity must not create a artifact_kind destination."""

    service = ModelUpdateAcquisitionService(
        model_root=tmp_path / "models",
        acquisition=ModelAcquisitionService(allowed_roots=(tmp_path / "models",)),
    )

    assert service.download_selected((), selected_identities=("forged",)) == ()
    assert not (tmp_path / "models").exists()
