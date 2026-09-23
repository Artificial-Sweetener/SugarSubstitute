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

"""Verify opt-in update badges and explicitly requested side-by-side transfers."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QWidget

from substitute.infrastructure.model_updates import FileModelUsageRepository
from substitute.presentation.model_updates.version_family_modal import (
    ModelVersionFamilyModal,
)
from substitute.presentation.shell.model_update_notification_controller import (
    ModelUpdateNotificationController,
)
from sugarsubstitute_shared.model_acquisition import ModelAcquisitionService
from sugarsubstitute_shared.model_discovery import (
    CivitaiDiscoveryClient,
    ModelArtifactKind,
)
from sugarsubstitute_shared.model_updates import (
    CivitaiCompatibleUpdateGateway,
    ModelUpdateAcquisitionService,
    ModelUpdateService,
)
from tests.presentation.widgets.model_picker.support import ensure_qapp
from tests.support.qt.semantic_wait import wait_for_qt_condition


class _Preferences:
    """Expose the authoritative update opt-in flag."""

    def __init__(self, enabled: bool) -> None:
        """Store consent for the controller."""

        self.enabled = enabled

    def load_preferences(self) -> object:
        """Return the CivitAI preference projection."""

        return SimpleNamespace(model_update_notifications_enabled=self.enabled)


class _Stream:
    """Expose one deterministic candidate body."""

    def __init__(self, payload: bytes) -> None:
        """Retain the unread bytes."""

        self._payload = payload
        self.content_length = len(payload)

    def read(self, size: int) -> bytes:
        """Read one bounded chunk."""

        chunk, self._payload = self._payload[:size], self._payload[size:]
        return chunk

    def close(self) -> None:
        """Complete the stream without extra effects."""


def _provider_payload(new_hash: str, new_size: int) -> dict[str, object]:
    """Return a real-shape CivitAI page with two compatible versions."""

    def version(identity: int, name: str, digest: str, size: int) -> dict[str, object]:
        """Build one safe public SafeTensor version."""

        return {
            "id": identity,
            "name": name,
            "baseModel": "SDXL 1.0",
            "availability": "Public",
            "images": [],
            "files": [
                {
                    "name": f"{name}.safetensors",
                    "downloadUrl": f"https://civitai.com/api/download/models/{identity}",
                    "sizeKB": size / 1024,
                    "primary": True,
                    "metadata": {"format": "SafeTensor"},
                    "hashes": {"SHA256": digest},
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
            version(20, "Updated", new_hash, new_size),
            version(10, "Current", "a" * 64, 23),
        ],
    }


def _controller(
    tmp_path: Path,
    *,
    enabled: bool,
) -> tuple[ModelUpdateNotificationController, QWidget, Path, Path, bytes]:
    """Compose real usage, provider parsing, controller, and verified acquisition."""

    ensure_qapp()
    payload = b"synthetic-compatible-update"
    model_root = tmp_path / "models"
    current_path = model_root / "checkpoints" / "curated" / "Current.safetensors"
    current_path.parent.mkdir(parents=True)
    current_path.write_bytes(b"synthetic-current-model")
    update_service = ModelUpdateService(
        usage=FileModelUsageRepository(tmp_path / "settings"),
        updates=CivitaiCompatibleUpdateGateway(
            CivitaiDiscoveryClient(
                fetch_json=lambda _url, **_kwargs: _provider_payload(
                    hashlib.sha256(payload).hexdigest(), len(payload)
                )
            )
        ),
        clock=lambda: datetime(2026, 9, 12, tzinfo=UTC),
    )
    update_service.record_usage(
        sha256="a" * 64,
        path=current_path,
        artifact_kind=ModelArtifactKind.CHECKPOINTS,
        model_id=314,
        version_id=10,
        base_model="SDXL 1.0",
    )
    parent = QWidget()
    parent.resize(1280, 820)
    parent.show()
    controller = ModelUpdateNotificationController(
        parent_widget=parent,
        preferences=_Preferences(enabled),
        updates=update_service,
        model_root=model_root,
        acquisition=ModelUpdateAcquisitionService(
            model_root=model_root,
            acquisition=ModelAcquisitionService(
                allowed_roots=(model_root,),
                stream_opener=lambda _url, _headers, _timeout: _Stream(payload),
            ),
        ),
    )
    return controller, parent, model_root, current_path, payload


def test_opt_out_keeps_provider_and_picker_quiet(tmp_path: Path) -> None:
    """No consent means no provider check or update marker."""

    controller, parent, _root, _current, _payload = _controller(tmp_path, enabled=False)
    assert controller.check_on_focus() is False
    assert controller.picker_bridge.proposal_for_sha("a" * 64) is None
    controller.close()
    parent.close()
    parent.deleteLater()


def test_badge_opens_contained_family_only_on_request_and_downloads_beside_current(
    tmp_path: Path,
) -> None:
    """Focus is quiet; user intent opens chronology and downloads one chosen version."""

    controller, parent, _root, current_path, payload = _controller(
        tmp_path, enabled=True
    )
    assert controller.check_on_focus()
    wait_for_qt_condition(
        lambda: (
            not controller.running
            and controller.picker_bridge.proposal_for_sha("a" * 64) is not None
        ),
        timeout_ms=5000,
    )
    assert parent.findChildren(ModelVersionFamilyModal) == []
    assert current_path.read_bytes() == b"synthetic-current-model"

    controller.picker_bridge.request_family("a" * 64)
    wait_for_qt_condition(
        lambda: (
            bool(parent.findChildren(ModelVersionFamilyModal))
            and bool(parent.findChildren(ModelVersionFamilyModal)[0]._cards)
        ),
        timeout_ms=5000,
    )
    modal = parent.findChildren(ModelVersionFamilyModal)[0]
    assert modal.parentWidget() is not parent
    assert tuple(modal._cards) == (10, 20)
    assert modal._cards[10].installed
    assert modal._cards[10].state_label.text() == "In use"
    assert not modal._cards[20].installed
    assert not modal.download_button.isEnabled()
    modal._cards[20].portrait.checkbox.setChecked(True)
    assert modal.download_button.isEnabled()
    modal.download_button.click()
    wait_for_qt_condition(
        lambda: (
            not controller.running and modal._cards[20].state_label.text() == "On disk"
        ),
        timeout_ms=5000,
    )
    assert current_path.read_bytes() == b"synthetic-current-model"
    assert (current_path.parent / "Updated.safetensors").read_bytes() == payload
    assert controller.picker_bridge.proposal_for_sha("a" * 64) is None
    modal.reject()
    assert controller.check_on_focus()
    wait_for_qt_condition(lambda: not controller.running, timeout_ms=5000)
    assert controller.picker_bridge.proposal_for_sha("a" * 64) is None
    controller.close()
    parent.close()
    parent.deleteLater()


def test_context_dismissal_clears_badge_and_survives_a_new_check(
    tmp_path: Path,
) -> None:
    """Right-click dismissal should persist without downloading any file."""

    controller, parent, _root, _current, _payload = _controller(tmp_path, enabled=True)
    assert controller.check_on_focus()
    wait_for_qt_condition(
        lambda: (
            not controller.running
            and controller.picker_bridge.proposal_for_sha("a" * 64) is not None
        ),
        timeout_ms=5000,
    )
    assert controller.picker_bridge.request_dismissal("a" * 64)
    assert controller.picker_bridge.proposal_for_sha("a" * 64) is None
    assert (
        FileModelUsageRepository(tmp_path / "settings").load()[0].dismissed_version_id
        == 20
    )
    assert controller.check_on_focus()
    wait_for_qt_condition(lambda: not controller.running, timeout_ms=5000)
    assert controller.picker_bridge.proposal_for_sha("a" * 64) is None
    controller.close()
    parent.close()
    parent.deleteLater()


def test_icon_page_opt_out_clears_badge_and_survives_a_new_check(
    tmp_path: Path,
) -> None:
    """The icon's page action disables future checks for that model."""

    controller, parent, _root, _current, _payload = _controller(tmp_path, enabled=True)
    assert controller.check_on_focus()
    wait_for_qt_condition(
        lambda: (
            not controller.running
            and controller.picker_bridge.proposal_for_sha("a" * 64) is not None
        ),
        timeout_ms=5000,
    )
    assert controller.picker_bridge.request_page_opt_out("a" * 64)
    assert controller.picker_bridge.proposal_for_sha("a" * 64) is None
    records = FileModelUsageRepository(tmp_path / "settings").load()
    assert records[0].updates_disabled_for_model
    assert controller.check_on_focus()
    wait_for_qt_condition(lambda: not controller.running, timeout_ms=5000)
    assert controller.picker_bridge.proposal_for_sha("a" * 64) is None
    controller.close()
    parent.close()
    parent.deleteLater()
