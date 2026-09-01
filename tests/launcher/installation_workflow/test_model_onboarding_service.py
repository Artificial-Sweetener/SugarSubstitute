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

"""Verify installer model gating and exact checked acquisition behavior."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
from pathlib import Path

from launcher.sugarsubstitute_launcher.application.model_onboarding import (
    ManagedComfyModelFolders,
    default_installer_capabilities,
)
from sugarsubstitute_shared.model_acquisition import ModelAcquisitionService
from sugarsubstitute_shared.model_discovery import (
    CubeModelCapability,
    DiscoveredModel,
    ModelCategory,
    ModelDiscoveryPlanner,
    ModelOnboardingService,
    model_card_identity,
)


class _Discovery:
    """Return deterministic popularity-ordered model records."""

    def __init__(self, records: Mapping[ModelCategory, tuple[DiscoveredModel, ...]]):
        """Store category records."""

        self._records = records

    def discover_monthly_popular(
        self,
        category: ModelCategory,
        *,
        limit: int,
    ) -> tuple[DiscoveredModel, ...]:
        """Return bounded records for one category."""

        return self._records.get(category, ())[:limit]


class _Stream:
    """Expose one in-memory model response."""

    def __init__(self, payload: bytes) -> None:
        """Store unread response bytes."""

        self._payload = payload
        self.content_length = len(payload)

    def read(self, size: int) -> bytes:
        """Read a bounded response chunk."""

        chunk, self._payload = self._payload[:size], self._payload[size:]
        return chunk

    def close(self) -> None:
        """Release the in-memory response."""


def _candidate(
    category: ModelCategory, identity: int, payload: bytes
) -> DiscoveredModel:
    """Build one exact downloadable model record."""

    return DiscoveredModel(
        category=category,
        model_id=identity,
        version_id=identity * 10,
        model_name=f"Model {identity}",
        version_name="v1",
        creator="Creator",
        base_model="SDXL 1.0",
        file_name=f"model-{identity}.safetensors",
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        download_url=f"https://civitai.com/api/download/models/{identity * 10}",
        model_page_url=f"https://civitai.com/models/{identity}",
        thumbnail_url=None,
        provider_rank=identity,
    )


def _service(
    model_root: Path,
    *,
    records: Mapping[ModelCategory, tuple[DiscoveredModel, ...]],
    payloads: Mapping[str, bytes],
) -> ModelOnboardingService:
    """Compose the real planner and acquisition service over deterministic ports."""

    folders = ManagedComfyModelFolders(model_root)

    def open_stream(url: str, headers: Mapping[str, str], timeout: float) -> _Stream:
        """Return exact test bytes without network access."""

        _ = (headers, timeout)
        return _Stream(payloads[url])

    return ModelOnboardingService(
        planner=ModelDiscoveryPlanner(
            inventory=folders,
            discovery=_Discovery(records),
            destinations=folders,
        ),
        acquisition=ModelAcquisitionService(
            allowed_roots=(model_root,),
            stream_opener=open_stream,
        ),
    )


def test_eligibility_scan_is_read_only_and_existing_model_suppresses_offer(
    tmp_path: Path,
) -> None:
    """Scanning must create nothing and any compatible model must suppress onboarding."""

    model_root = tmp_path / "comfyui" / "models"
    service = _service(model_root, records={}, payloads={})
    capabilities = default_installer_capabilities()

    assert service.assess(capabilities).should_offer
    assert not model_root.exists()

    checkpoint = model_root / ModelCategory.CHECKPOINTS.value / "owned.safetensors"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"owned")

    assert not service.assess(capabilities).should_offer


def test_only_checked_exact_cards_download_side_by_side(tmp_path: Path) -> None:
    """Unchecked provider cards must not transfer or replace an existing filename."""

    model_root = tmp_path / "models"
    first_payload = b"first-model"
    second_payload = b"second-model"
    first = _candidate(ModelCategory.CHECKPOINTS, 1, first_payload)
    second = _candidate(ModelCategory.CHECKPOINTS, 2, second_payload)
    records = {ModelCategory.CHECKPOINTS: (first, second)}
    payloads = {
        first.download_url: first_payload,
        second.download_url: second_payload,
    }
    service = _service(model_root, records=records, payloads=payloads)
    capability = CubeModelCapability(
        "checkpoint-cube",
        frozenset({ModelCategory.CHECKPOINTS}),
    )
    plan = service.plan(
        (capability,),
        selected_categories=(ModelCategory.CHECKPOINTS,),
    )
    destination = model_root / ModelCategory.CHECKPOINTS.value
    destination.mkdir(parents=True)
    (destination / second.file_name).write_bytes(b"do-not-replace")

    results = service.download_selected(
        plan,
        selected_identities=(model_card_identity(plan.cards[1]),),
    )

    assert len(results) == 1
    assert results[0].path.read_bytes() == second_payload
    assert results[0].path.name != second.file_name
    assert (destination / second.file_name).read_bytes() == b"do-not-replace"
    assert not (destination / first.file_name).exists()


def test_unknown_ui_identity_cannot_trigger_a_download(tmp_path: Path) -> None:
    """An identity absent from the reviewed plan must produce no provider action."""

    payload = b"candidate"
    candidate = _candidate(ModelCategory.LORAS, 3, payload)
    service = _service(
        tmp_path / "models",
        records={ModelCategory.LORAS: (candidate,)},
        payloads={candidate.download_url: payload},
    )
    capability = CubeModelCapability("lora-cube", frozenset({ModelCategory.LORAS}))
    plan = service.plan((capability,), selected_categories=(ModelCategory.LORAS,))

    assert service.download_selected(plan, selected_identities=("forged",)) == ()
    assert not (tmp_path / "models").exists()
