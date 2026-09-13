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

"""Verify opt-in update checks and reviewed side-by-side execution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
import hashlib
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QCheckBox, QWidget

from substitute.infrastructure.model_updates import FileModelUsageRepository
from substitute.presentation.model_updates import ModelUpdateModal
from substitute.presentation.shell.model_update_notification_controller import (
    ModelUpdateNotificationController,
)
from sugarsubstitute_shared.model_acquisition import ModelAcquisitionService
from sugarsubstitute_shared.model_discovery import (
    CivitaiDiscoveryClient,
    DiscoveredModel,
    ModelArtifactKind,
)
from sugarsubstitute_shared.model_updates import (
    CivitaiCompatibleUpdateGateway,
    ModelUpdateAcquisitionService,
    ModelUpdateProposal,
    ModelUpdateService,
    ModelUsageRecord,
    model_update_identity,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


class _Preferences:
    """Expose an authoritative opt-in flag."""

    def __init__(self, enabled: bool) -> None:
        """Store consent."""

        self._enabled = enabled

    def load_preferences(self) -> object:
        """Return the CivitAI aggregate shape used by the controller."""

        return SimpleNamespace(model_update_notifications_enabled=self._enabled)


class _Usage:
    """Return one recently used provider-known model."""

    def __init__(self, record: ModelUsageRecord) -> None:
        """Store the record."""

        self._record = record

    def load(self) -> tuple[ModelUsageRecord, ...]:
        """Return current usage."""

        return (self._record,)

    def save(self, records: tuple[ModelUsageRecord, ...]) -> None:
        """Reject unrelated persistence during checks."""

        raise AssertionError(records)


class _Updates:
    """Return one exact compatible candidate and count provider access."""

    def __init__(self, candidate: DiscoveredModel) -> None:
        """Store the candidate."""

        self._candidate = candidate
        self.calls = 0

    def latest_compatible(
        self,
        *,
        model_id: int,
        current_version_id: int,
        artifact_kind: ModelArtifactKind,
        base_model: str | None,
    ) -> DiscoveredModel | None:
        """Return the prepared candidate."""

        _ = (model_id, current_version_id, artifact_kind, base_model)
        self.calls += 1
        return self._candidate


class _Stream:
    """Expose an in-memory update body."""

    def __init__(self, payload: bytes) -> None:
        """Store unread bytes."""

        self._payload = payload
        self.content_length = len(payload)

    def read(self, size: int) -> bytes:
        """Read a bounded chunk."""

        chunk, self._payload = self._payload[:size], self._payload[size:]
        return chunk

    def close(self) -> None:
        """Release the stream."""


def _records(tmp_path: Path) -> tuple[ModelUsageRecord, DiscoveredModel, bytes]:
    """Build one current/candidate pair."""

    payload = b"verified-update"
    current = ModelUsageRecord(
        sha256="a" * 64,
        path=tmp_path / "models" / "checkpoints" / "old.safetensors",
        artifact_kind=ModelArtifactKind.CHECKPOINTS,
        model_id=3,
        version_id=4,
        base_model="SDXL",
        usage_count=1,
        last_used_at=datetime(2026, 8, 31, tzinfo=UTC),
    )
    candidate = DiscoveredModel(
        artifact_kind=ModelArtifactKind.CHECKPOINTS,
        model_id=3,
        version_id=5,
        model_name="Updated",
        version_name="v5",
        creator="Creator",
        base_model="SDXL",
        file_name="updated.safetensors",
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        download_url="https://civitai.com/api/download/models/5",
        model_page_url="https://civitai.com/models/3",
        thumbnail_url=None,
        provider_rank=1,
    )
    return current, candidate, payload


def test_opt_out_prevents_provider_check(tmp_path: Path) -> None:
    """Focus must remain entirely local while notifications are disabled."""

    current, candidate, _payload = _records(tmp_path)
    updates = _Updates(candidate)
    parent = QWidget()
    controller = ModelUpdateNotificationController(
        parent_widget=parent,
        preferences=_Preferences(False),
        updates=ModelUpdateService(usage=_Usage(current), updates=updates),
        model_root=None,
        acquisition=None,
        feedback=lambda _severity, _message: None,
    )

    assert controller.check_on_focus() is False
    assert updates.calls == 0
    controller.close()
    parent.deleteLater()


def test_real_persisted_usage_reaches_update_modal_and_atomic_download(
    tmp_path: Path,
) -> None:
    """Prove tracking, compatibility lookup, review UI, and transfer as one session."""

    payload = b"synthetic-compatible-update"
    candidate_hash = hashlib.sha256(payload).hexdigest()
    model_root = tmp_path / "models"
    current_path = model_root / "checkpoints" / "current.safetensors"
    current_path.parent.mkdir(parents=True)
    current_path.write_bytes(b"synthetic-current-model")
    usage_repository = FileModelUsageRepository(tmp_path / "settings")

    def service_clock() -> datetime:
        """Return a stable clock inside the update relevance window."""

        return datetime(2026, 9, 12, tzinfo=UTC)

    update_service = ModelUpdateService(
        usage=usage_repository,
        updates=CivitaiCompatibleUpdateGateway(
            CivitaiDiscoveryClient(
                fetch_json=lambda _url, **_kwargs: _update_provider_payload(
                    candidate_hash,
                    len(payload),
                )
            )
        ),
        clock=service_clock,
    )
    update_service.record_usage(
        sha256="a" * 64,
        path=current_path,
        artifact_kind=ModelArtifactKind.CHECKPOINTS,
        model_id=314,
        version_id=10,
        base_model="SDXL 1.0",
    )
    shown: list[ModelUpdateProposal] = []

    def review_in_production_modal(
        proposals: Sequence[ModelUpdateProposal],
        root: Path,
        parent: QWidget,
    ) -> tuple[str, ...]:
        """Exercise the actual unchecked review surface and explicitly select once."""

        assert len(proposals) == 1
        shown.extend(proposals)
        modal = ModelUpdateModal(proposals=proposals, model_root=root, parent=parent)
        checks = modal.findChildren(QCheckBox)
        assert len(checks) == 1
        assert not checks[0].isChecked()
        checks[0].setChecked(True)
        QTimer.singleShot(0, modal.accept)
        try:
            return modal.choose_updates()
        finally:
            modal.deleteLater()

    parent = QWidget()
    feedback: list[tuple[str, str]] = []
    controller = ModelUpdateNotificationController(
        parent_widget=parent,
        preferences=_Preferences(True),
        updates=update_service,
        model_root=model_root,
        acquisition=ModelUpdateAcquisitionService(
            model_root=model_root,
            acquisition=ModelAcquisitionService(
                allowed_roots=(model_root,),
                stream_opener=lambda _url, _headers, _timeout: _Stream(payload),
            ),
        ),
        chooser=review_in_production_modal,
        feedback=lambda severity, message: feedback.append((severity, message)),
    )

    assert controller.check_on_focus()
    wait_for_qt_condition(
        lambda: not controller.running and bool(feedback),
        timeout_ms=5000,
    )

    assert len(shown) == 1
    assert shown[0].current.path == current_path
    assert shown[0].candidate.version_id == 20
    assert current_path.read_bytes() == b"synthetic-current-model"
    assert (model_root / "checkpoints" / "updated.safetensors").read_bytes() == payload
    assert feedback[-1][0] == "success"
    persisted = usage_repository.load()
    assert len(persisted) == 1 and persisted[0].usage_count == 1
    controller.close()
    parent.deleteLater()


def _update_provider_payload(sha256: str, size_bytes: int) -> dict[str, object]:
    """Return a realistic newest-first CivitAI version response."""

    def version(
        version_id: int,
        *,
        name: str,
        file_name: str,
        file_hash: str,
        byte_count: int,
    ) -> dict[str, object]:
        """Build one safe public SafeTensor version."""

        return {
            "id": version_id,
            "name": name,
            "baseModel": "SDXL 1.0",
            "availability": "Public",
            "images": [],
            "files": [
                {
                    "name": file_name,
                    "downloadUrl": (
                        f"https://civitai.com/api/download/models/{version_id}"
                    ),
                    "sizeKB": byte_count / 1024,
                    "primary": True,
                    "metadata": {"format": "SafeTensor"},
                    "hashes": {"SHA256": file_hash},
                    "pickleScanResult": "Success",
                    "virusScanResult": "Success",
                }
            ],
        }

    return {
        "id": 314,
        "name": "Synthetic Update Model",
        "type": "Checkpoint",
        "nsfw": False,
        "creator": {"username": "Synthetic"},
        "modelVersions": [
            version(
                20,
                name="Updated",
                file_name="updated.safetensors",
                file_hash=sha256,
                byte_count=size_bytes,
            ),
            version(
                10,
                name="Current",
                file_name="current.safetensors",
                file_hash="a" * 64,
                byte_count=23,
            ),
        ],
    }


def test_opt_in_review_downloads_exact_selection_and_does_not_repeat(
    tmp_path: Path,
) -> None:
    """One reviewed candidate should transfer once and stay suppressed this process."""

    current, candidate, payload = _records(tmp_path)
    model_root = tmp_path / "models"
    current.path.parent.mkdir(parents=True)
    current.path.write_bytes(b"old")
    updates = _Updates(candidate)
    proposal = ModelUpdateProposal(current=current, candidate=candidate)

    def open_stream(url: str, headers: Mapping[str, str], timeout: float) -> _Stream:
        """Return the verified candidate bytes."""

        _ = (url, headers, timeout)
        return _Stream(payload)

    feedback: list[tuple[str, str]] = []
    chooser_calls: list[tuple[ModelUpdateProposal, ...]] = []

    def choose_update(
        proposals: Sequence[ModelUpdateProposal],
        _root: Path,
        _parent: QWidget,
    ) -> tuple[str, ...]:
        """Record presented updates and choose the deterministic proposal."""

        chooser_calls.append(tuple(proposals))
        return (model_update_identity(proposal),)

    parent = QWidget()
    controller = ModelUpdateNotificationController(
        parent_widget=parent,
        preferences=_Preferences(True),
        updates=ModelUpdateService(
            usage=_Usage(current),
            updates=updates,
            clock=lambda: datetime(2026, 8, 31, tzinfo=UTC),
        ),
        model_root=model_root,
        acquisition=ModelUpdateAcquisitionService(
            model_root=model_root,
            acquisition=ModelAcquisitionService(
                allowed_roots=(model_root,),
                stream_opener=open_stream,
            ),
        ),
        chooser=choose_update,
        feedback=lambda severity, message: feedback.append((severity, message)),
    )

    assert controller.check_on_focus() is True
    wait_for_qt_condition(
        lambda: not controller.running and bool(feedback),
        timeout_ms=5000,
    )

    assert chooser_calls == [(proposal,)]
    assert current.path.read_bytes() == b"old"
    downloaded = model_root / "checkpoints" / candidate.file_name
    assert downloaded.read_bytes() == payload
    assert feedback[-1][0] == "success"

    assert controller.check_on_focus() is True
    wait_for_qt_condition(lambda: not controller.running, timeout_ms=5000)
    assert chooser_calls == [(proposal,)]
    controller.close()
    parent.deleteLater()
