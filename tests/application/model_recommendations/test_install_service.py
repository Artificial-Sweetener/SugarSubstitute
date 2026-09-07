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

"""Verify complete family recipes and aggregate model-transfer progress."""

from __future__ import annotations

import hashlib
from pathlib import Path

from sugarsubstitute_shared.model_acquisition import ModelAcquisitionService

from substitute.application.model_recommendations import (
    ModelInstallRecipePlanner,
    ModelInstallService,
)
from substitute.domain.model_recommendations import (
    ModelFamilyId,
    ModelInstallFile,
    ModelInstallPlan,
    ModelInstallProgress,
    ModelRecommendation,
)
from sugarsubstitute_shared.model_discovery import ModelArtifactKind


class _Stream:
    """Read deterministic bytes through the acquisition stream contract."""

    def __init__(self, payload: bytes) -> None:
        """Store bytes and a cursor."""

        self._payload = payload
        self._offset = 0

    @property
    def content_length(self) -> int:
        """Return exact response length."""

        return len(self._payload)

    def read(self, size: int) -> bytes:
        """Read one bounded chunk."""

        value = self._payload[self._offset : self._offset + size]
        self._offset += len(value)
        return value

    def close(self) -> None:
        """Release the in-memory stream."""


def _recommendation(family_id: ModelFamilyId, model_id: int) -> ModelRecommendation:
    """Build one selected provider recommendation."""

    return ModelRecommendation(
        family_id=family_id,
        model_id=model_id,
        version_id=model_id * 10,
        model_name=f"Model {model_id}",
        version_name="v1",
        creator="creator",
        file_name=f"model-{model_id}.safetensors",
        size_bytes=1_024,
        sha256="a" * 64,
        download_url=f"https://civitai.com/api/download/models/{model_id * 10}",
        model_page_url=f"https://civitai.com/models/{model_id}",
        thumbnail_image_id=model_id * 100,
        thumbnail_url="https://image.civitai.com/example.jpeg",
        popularity_rank=model_id,
    )


def test_recipe_planner_keeps_anima_to_explicit_primary_selections(
    tmp_path: Path,
) -> None:
    """SimpleSyrup owns Anima dependencies, so setup downloads only chosen models."""

    planner = ModelInstallRecipePlanner(free_space=lambda _path: 10**12)

    plan = planner.plan(
        [
            _recommendation(ModelFamilyId.ANIMA, 1),
            _recommendation(ModelFamilyId.ANIMA, 2),
        ],
        model_root=tmp_path / "models",
    )

    assert len(plan.files) == 2
    assert plan.files[0].destination_dir.name == "diffusion_models"
    assert plan.files[1].destination_dir.name == "diffusion_models"
    assert plan.total_bytes == 2_048
    assert plan.has_sufficient_space


def test_recipe_planner_keeps_sdxl_a_single_checkpoint_file(tmp_path: Path) -> None:
    """An SDXL CivitAI primary is already a complete supported recipe."""

    plan = ModelInstallRecipePlanner(free_space=lambda _path: 10_000).plan(
        [_recommendation(ModelFamilyId.SDXL, 1)],
        model_root=tmp_path,
    )

    assert len(plan.files) == 1
    assert plan.files[0].artifact_kind is ModelArtifactKind.CHECKPOINTS


def test_model_install_service_reports_monotonic_file_and_aggregate_bytes(
    tmp_path: Path,
) -> None:
    """Multiple downloads must expose exact aggregate progress through completion."""

    payloads = {
        "https://civitai.com/api/download/models/10": b"primary",
        "https://civitai.com/api/download/models/20": b"second",
    }

    def open_stream(url: str, _headers: object, _timeout: float) -> _Stream:
        """Return deterministic payload bytes for one reviewed URL."""

        return _Stream(payloads[url])

    files = (
        _install_file(
            tmp_path,
            url="https://civitai.com/api/download/models/10",
            payload=payloads["https://civitai.com/api/download/models/10"],
            model_id=1,
        ),
        _install_file(
            tmp_path,
            url="https://civitai.com/api/download/models/20",
            payload=payloads["https://civitai.com/api/download/models/20"],
            model_id=2,
        ),
    )
    plan = ModelInstallPlan(tmp_path, files, available_bytes=1_000)
    primary = ModelAcquisitionService(
        allowed_roots=(tmp_path,),
        stream_opener=open_stream,
    )
    progress: list[ModelInstallProgress] = []

    results = ModelInstallService(
        primary_acquisition=primary,
    ).acquire(plan, on_progress=progress.append)

    assert len(results) == 2
    received = [event.aggregate_received_bytes for event in progress]
    assert received == sorted(received)
    assert received[-1] == plan.total_bytes
    assert progress[-1].completed_files == 2


def test_model_install_service_rejects_insufficient_space_before_reservation(
    tmp_path: Path,
) -> None:
    """Review-time disk failure must leave the target untouched."""

    file = _install_file(
        tmp_path,
        url="https://civitai.com/api/download/models/10",
        payload=b"large",
        model_id=1,
    )
    plan = ModelInstallPlan(tmp_path, (file,), available_bytes=1)
    service = ModelInstallService(
        primary_acquisition=ModelAcquisitionService(allowed_roots=(tmp_path,)),
    )

    try:
        service.acquire(plan)
    except OSError as error:
        assert "enough free space" in str(error)
    else:
        raise AssertionError("Insufficient disk space was accepted.")
    assert not file.destination_dir.exists()


def _install_file(
    root: Path,
    *,
    url: str,
    payload: bytes,
    model_id: int,
) -> ModelInstallFile:
    """Build one exact test install file."""

    return ModelInstallFile(
        family_id=ModelFamilyId.SDXL,
        artifact_kind=ModelArtifactKind.CHECKPOINTS,
        model_id=model_id,
        version_id=model_id * 10,
        display_name=f"file-{model_id}",
        file_name=f"file-{model_id}.safetensors",
        source_url=url,
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        destination_dir=root / "checkpoints",
    )
