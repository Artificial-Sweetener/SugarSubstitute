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

from PySide6.QtWidgets import QWidget

from substitute.presentation.shell.model_update_notification_controller import (
    ModelUpdateNotificationController,
)
from sugarsubstitute_shared.model_acquisition import ModelAcquisitionService
from sugarsubstitute_shared.model_discovery import DiscoveredModel, ModelCategory
from sugarsubstitute_shared.model_updates import (
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
        category: ModelCategory,
        base_model: str | None,
    ) -> DiscoveredModel | None:
        """Return the prepared candidate."""

        _ = (model_id, current_version_id, category, base_model)
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
        category=ModelCategory.CHECKPOINTS,
        model_id=3,
        version_id=4,
        base_model="SDXL",
        usage_count=1,
        last_used_at=datetime(2026, 8, 31, tzinfo=UTC),
    )
    candidate = DiscoveredModel(
        category=ModelCategory.CHECKPOINTS,
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
