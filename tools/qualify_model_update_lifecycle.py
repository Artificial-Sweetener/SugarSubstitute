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

"""Qualify installed model-update discovery and persistence without pytest."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
from typing import cast

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QCheckBox, QWidget

from substitute.infrastructure.model_updates import FileModelUsageRepository
from substitute.presentation.model_updates import ModelUpdateModal
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
    ModelUpdatePreferences,
    ModelUpdateProposal,
    ModelUpdateService,
)
from tools.model_lifecycle_qualification import runtime_evidence, wait_until

_CURRENT_PAYLOAD = b"synthetic current model"
_UPDATE_PAYLOAD = b"synthetic compatible model update"
_CURRENT_HASH = hashlib.sha256(_CURRENT_PAYLOAD).hexdigest()
_UPDATE_HASH = hashlib.sha256(_UPDATE_PAYLOAD).hexdigest()
_CLOCK = datetime(2026, 9, 13, tzinfo=UTC)


class _Preferences:
    """Expose explicit model-update consent to the production controller."""

    def load_preferences(self) -> object:
        """Return the enabled application preference aggregate."""

        return SimpleNamespace(model_update_notifications_enabled=True)


class _Stream:
    """Expose a bounded in-memory response through the acquisition port."""

    def __init__(self, payload: bytes) -> None:
        """Store unread synthetic response bytes."""

        self._payload = payload
        self.content_length = len(payload)

    def read(self, size: int) -> bytes:
        """Read at most one requested response chunk."""

        chunk, self._payload = self._payload[:size], self._payload[size:]
        return chunk

    def close(self) -> None:
        """Release the synthetic stream."""


def main(argv: Sequence[str] | None = None) -> int:
    """Run model usage, restart, review, acquisition, and rehydration proof."""

    _ = argv
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    application = cast(QApplication, QApplication.instance() or QApplication([]))
    artifact_dir = Path("build/qualification/model-update-lifecycle").resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="SugarSubstitute-model-update-") as root:
        evidence = _qualify_lifecycle(
            application,
            root=Path(root),
            screenshot_path=artifact_dir / "model-update-modal.png",
        )
    report_path = artifact_dir / "model-update-lifecycle-qualification.json"
    report_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(report_path)
    return 0


def _qualify_lifecycle(
    application: QApplication,
    *,
    root: Path,
    screenshot_path: Path,
) -> dict[str, object]:
    """Exercise production owners across two explicit application restarts."""

    model_root = root / "models"
    settings_root = root / "settings"
    current_path = model_root / "checkpoints" / "current.safetensors"
    current_path.parent.mkdir(parents=True)
    current_path.write_bytes(_CURRENT_PAYLOAD)

    initial_repository = FileModelUsageRepository(settings_root)
    _new_update_service(initial_repository).record_usage(
        sha256=_CURRENT_HASH,
        path=current_path,
        artifact_kind=ModelArtifactKind.CHECKPOINTS,
        model_id=314,
        version_id=10,
        base_model="SDXL 1.0",
    )
    initial_records = initial_repository.load()
    if len(initial_records) != 1 or initial_records[0].usage_count != 1:
        raise AssertionError("Generate-derived model usage was not persisted.")

    restarted_repository = FileModelUsageRepository(settings_root)
    restarted_service = _new_update_service(restarted_repository)
    restarted_proposals = restarted_service.check_updates(
        ModelUpdatePreferences(enabled=True)
    )
    if len(restarted_proposals) != 1:
        raise AssertionError(
            "A fresh update service did not rediscover the compatible update."
        )
    proposal = restarted_proposals[0]
    if proposal.current.path != current_path or proposal.candidate.version_id != 20:
        raise AssertionError(
            "Restarted update identity disagreed with persisted usage."
        )

    modal_evidence: dict[str, object] = {}

    def choose_update(
        proposals: Sequence[ModelUpdateProposal],
        destination: Path,
        parent: QWidget,
    ) -> tuple[str, ...]:
        """Drive the production modal from unchecked review to explicit consent."""

        modal = ModelUpdateModal(
            proposals=proposals,
            model_root=destination,
            parent=parent,
        )
        checks = modal.findChildren(QCheckBox)
        if len(checks) != 1 or checks[0].isChecked():
            raise AssertionError(
                "Update review did not begin with one unchecked model."
            )
        modal_evidence["initially_unchecked"] = True

        def accept_selected() -> None:
            """Capture the visible modal and explicitly select its update."""

            if not modal.grab().save(str(screenshot_path), "PNG"):
                raise OSError(
                    f"Could not save update modal evidence: {screenshot_path}"
                )
            checks[0].setChecked(True)
            if not modal.download_button.isEnabled():
                raise AssertionError("Explicit selection did not enable download.")
            modal.download_button.click()

        QTimer.singleShot(0, accept_selected)
        try:
            selected = modal.choose_updates()
        finally:
            modal.deleteLater()
        if len(selected) != 1:
            raise AssertionError(
                "Production update review did not return one selection."
            )
        modal_evidence["explicit_selection_count"] = len(selected)
        return selected

    feedback: list[tuple[str, str]] = []
    parent = QWidget()
    controller = ModelUpdateNotificationController(
        parent_widget=parent,
        preferences=_Preferences(),
        updates=restarted_service,
        model_root=model_root,
        acquisition=ModelUpdateAcquisitionService(
            model_root=model_root,
            acquisition=ModelAcquisitionService(
                allowed_roots=(model_root,),
                stream_opener=lambda _url, _headers, _timeout: _Stream(_UPDATE_PAYLOAD),
            ),
        ),
        chooser=choose_update,
        feedback=lambda severity, message: feedback.append((severity, message)),
    )
    if not controller.check_on_focus():
        raise AssertionError("Enabled update notification check did not start.")
    wait_until(
        application,
        lambda: not controller.running and bool(feedback),
        "model update acquisition",
    )
    controller.close()
    parent.deleteLater()
    application.processEvents()
    if feedback[-1][0] != "success":
        raise AssertionError(f"Update acquisition did not report success: {feedback}.")

    updated_path = model_root / "checkpoints" / "updated.safetensors"
    if current_path.read_bytes() != _CURRENT_PAYLOAD:
        raise AssertionError("Side-by-side update modified the current model.")
    if updated_path.read_bytes() != _UPDATE_PAYLOAD:
        raise AssertionError("Downloaded update bytes failed verification.")

    second_restart_repository = FileModelUsageRepository(settings_root)
    second_restart_records = second_restart_repository.load()
    if second_restart_records != initial_records:
        raise AssertionError("Update acquisition changed authoritative usage state.")
    second_restart_proposals = _new_update_service(
        second_restart_repository
    ).check_updates(ModelUpdatePreferences(enabled=True))
    if len(second_restart_proposals) != 1:
        raise AssertionError("Update availability disappeared after a second restart.")

    return {
        "result": "passed",
        "external_network_used": False,
        "usage_persisted_before_restart": True,
        "update_available_after_first_restart": True,
        "update_available_after_second_restart": True,
        "current_model_preserved": True,
        "updated_model_installed_beside_current": True,
        "current_sha256": hashlib.sha256(current_path.read_bytes()).hexdigest(),
        "updated_sha256": hashlib.sha256(updated_path.read_bytes()).hexdigest(),
        "candidate_version_id": proposal.candidate.version_id,
        "modal": modal_evidence,
        "feedback_severity": feedback[-1][0],
        "runtime": runtime_evidence(),
    }


def _new_update_service(repository: FileModelUsageRepository) -> ModelUpdateService:
    """Construct fresh production update ownership over persisted usage."""

    return ModelUpdateService(
        usage=repository,
        updates=CivitaiCompatibleUpdateGateway(
            CivitaiDiscoveryClient(fetch_json=_fetch_update_payload)
        ),
        clock=lambda: _CLOCK,
    )


def _fetch_update_payload(
    url: str,
    *,
    headers: object | None = None,
    timeout: float = 0.0,
) -> dict[str, object]:
    """Return a deterministic provider response without external network access."""

    _ = (url, headers, timeout)
    return {
        "id": 314,
        "name": "Synthetic Update Model",
        "type": "Checkpoint",
        "nsfw": False,
        "creator": {"username": "Synthetic"},
        "modelVersions": [
            _provider_version(
                version_id=20,
                name="Updated",
                file_name="updated.safetensors",
                sha256=_UPDATE_HASH,
                size_bytes=len(_UPDATE_PAYLOAD),
            ),
            _provider_version(
                version_id=10,
                name="Current",
                file_name="current.safetensors",
                sha256=_CURRENT_HASH,
                size_bytes=len(_CURRENT_PAYLOAD),
            ),
        ],
    }


def _provider_version(
    *,
    version_id: int,
    name: str,
    file_name: str,
    sha256: str,
    size_bytes: int,
) -> dict[str, object]:
    """Build one public compatible SafeTensor provider version."""

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
                "sizeKB": size_bytes / 1024,
                "primary": True,
                "metadata": {"format": "SafeTensor"},
                "hashes": {"SHA256": sha256},
                "pickleScanResult": "Success",
                "virusScanResult": "Success",
            }
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
