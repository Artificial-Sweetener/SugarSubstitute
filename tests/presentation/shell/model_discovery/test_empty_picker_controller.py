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

"""Verify shared discovery and verified acquisition from empty model pickers."""

from __future__ import annotations

from collections.abc import Collection, Mapping
import hashlib
from pathlib import Path

from PySide6.QtWidgets import QWidget

from substitute.presentation.shell.empty_model_picker_discovery_controller import (
    EmptyModelPickerDiscoveryController,
)
from sugarsubstitute_shared.model_acquisition import ModelAcquisitionService
from sugarsubstitute_shared.model_discovery import (
    CategoryModelDestinationPolicy,
    DiscoveredModel,
    LocalModel,
    ModelCategory,
    ModelDiscoveryPlan,
    ModelDiscoveryPlanner,
    ModelOnboardingService,
    model_card_identity,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


class _Inventory:
    """Expose an empty authoritative inventory."""

    def list_models(
        self,
        categories: Collection[ModelCategory],
    ) -> tuple[LocalModel, ...]:
        """Return no local models."""

        _ = categories
        return ()


class _Discovery:
    """Return one prepared safe candidate."""

    def __init__(self, candidate: DiscoveredModel) -> None:
        """Store the candidate."""

        self._candidate = candidate

    def discover_monthly_popular(
        self,
        category: ModelCategory,
        *,
        limit: int,
    ) -> tuple[DiscoveredModel, ...]:
        """Return the candidate only for its category."""

        _ = limit
        return (self._candidate,) if category is self._candidate.category else ()


class _Stream:
    """Expose a bounded in-memory download body."""

    def __init__(self, payload: bytes) -> None:
        """Store unread bytes."""

        self._payload = payload
        self.content_length = len(payload)

    def read(self, size: int) -> bytes:
        """Consume one bounded chunk."""

        chunk, self._payload = self._payload[:size], self._payload[size:]
        return chunk

    def close(self) -> None:
        """Release the stream."""


class _Catalog:
    """Record targeted catalog invalidation."""

    def __init__(self) -> None:
        """Initialize no invalidations."""

        self.invalidated: list[str | None] = []

    def invalidate(self, kind: str | None = None) -> None:
        """Record one invalidation."""

        self.invalidated.append(kind)


def test_unknown_or_unavailable_picker_does_not_start_provider_work(
    tmp_path: Path,
) -> None:
    """Unknown categories and unsupported targets should fail locally and clearly."""

    _ = tmp_path
    parent = QWidget()
    feedback: list[tuple[str, str]] = []
    controller = EmptyModelPickerDiscoveryController(
        parent_widget=parent,
        service=None,
        catalog=_Catalog(),
        feedback=lambda severity, message: feedback.append((severity, message)),
    )

    assert controller.request_for_empty_picker("not-a-category") is False
    assert controller.request_for_empty_picker("checkpoints") is False
    assert feedback and feedback[-1][0] == "warning"
    controller.close()
    parent.deleteLater()


def test_checked_empty_picker_model_downloads_and_refreshes_catalog(
    tmp_path: Path,
) -> None:
    """Only the reviewed card should download before the picker catalog refreshes."""

    payload = b"verified-picker-model"
    model_root = tmp_path / "models"
    candidate = DiscoveredModel(
        category=ModelCategory.CHECKPOINTS,
        model_id=11,
        version_id=12,
        model_name="Popular model",
        version_name="v12",
        creator="Creator",
        base_model="SDXL",
        file_name="popular.safetensors",
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        download_url="https://civitai.com/api/download/models/12",
        model_page_url="https://civitai.com/models/11",
        thumbnail_url=None,
        provider_rank=1,
    )

    def open_stream(
        url: str,
        headers: Mapping[str, str],
        timeout: float,
    ) -> _Stream:
        """Return exact candidate bytes without network access."""

        _ = (url, headers, timeout)
        return _Stream(payload)

    service = ModelOnboardingService(
        planner=ModelDiscoveryPlanner(
            inventory=_Inventory(),
            discovery=_Discovery(candidate),
            destinations=CategoryModelDestinationPolicy(model_root),
        ),
        acquisition=ModelAcquisitionService(
            allowed_roots=(model_root,),
            stream_opener=open_stream,
        ),
    )
    catalog = _Catalog()
    feedback: list[tuple[str, str]] = []
    chooser_calls: list[int] = []

    def choose_model(plan: ModelDiscoveryPlan, _parent: QWidget) -> tuple[str, ...]:
        """Record the presented cards and choose the deterministic model."""

        chooser_calls.append(len(plan.cards))
        return (model_card_identity(plan.cards[0]),)

    parent = QWidget()
    controller = EmptyModelPickerDiscoveryController(
        parent_widget=parent,
        service=service,
        catalog=catalog,
        chooser=choose_model,
        feedback=lambda severity, message: feedback.append((severity, message)),
    )

    assert controller.request_for_empty_picker("checkpoints") is True
    wait_for_qt_condition(
        lambda: not controller.running and bool(feedback),
        timeout_ms=5000,
    )

    assert chooser_calls == [1]
    assert (model_root / "checkpoints" / "popular.safetensors").read_bytes() == payload
    assert catalog.invalidated == ["checkpoints"]
    assert feedback[-1][0] == "success"
    controller.close()
    parent.deleteLater()
