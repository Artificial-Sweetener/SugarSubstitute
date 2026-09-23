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

"""Check and present opt-in model updates away from the Qt owner thread."""

from __future__ import annotations

from collections.abc import Callable
import logging
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget
from qfluentwidgets import InfoBar, InfoBarPosition  # type: ignore[import-untyped]

from substitute.presentation.model_discovery.discovery_overlay import (
    ModelDiscoveryOverlay,
)
from substitute.presentation.model_updates.picker_bridge import ModelUpdatePickerBridge
from substitute.presentation.model_updates.version_family_modal import (
    ModelVersionFamilyModal,
)
from substitute.presentation.model_updates.version_thumbnail_loader import (
    VersionThumbnailLoad,
)
from substitute.presentation.qt.execution.thread_pool_dispatcher import (
    start_qt_runnable,
)
from substitute.presentation.widgets.civitai_page_action import open_external_url
from sugarsubstitute_shared.model_discovery import DiscoveredModel
from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.model_updates import (
    ModelUpdateAcquisitionService,
    ModelUpdatePreferences,
    ModelUpdateProposal,
    ModelUpdateService,
    model_update_identity,
)
from sugarsubstitute_shared.presentation.localization import render_application_text


_LOGGER = logging.getLogger(__name__)


class ModelUpdatePreferenceSource(Protocol):
    """Load the application-owned CivitAI preference aggregate."""

    def load_preferences(self) -> object:
        """Return preferences carrying model-update consent."""


Feedback = Callable[[str, str], None]


class _UpdateTask(QObject):
    """Run one provider-backed model update operation."""

    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, work: Callable[[], object], *, operation: str) -> None:
        """Store one blocking use case and its diagnostic identity."""

        super().__init__()
        self._work = work
        self._operation = operation

    @Slot()
    def run(self) -> None:
        """Execute work and always release the owning thread."""

        try:
            result = self._work()
        except Exception as error:
            _LOGGER.exception("Model update operation failed: %s", self._operation)
            self.failed.emit(str(error) or type(error).__name__)
        else:
            self.succeeded.emit(result)
        finally:
            self.finished.emit()


class ModelUpdateNotificationController(QObject):
    """Publish quiet update badges and open explicit version-family exploration."""

    def __init__(
        self,
        *,
        parent_widget: QWidget,
        preferences: ModelUpdatePreferenceSource,
        updates: ModelUpdateService,
        model_root: Path | None,
        acquisition: ModelUpdateAcquisitionService | None,
        fetch_thumbnail: Callable[[str], bytes] | None = None,
        feedback: Feedback | None = None,
    ) -> None:
        """Store update boundaries without starting network work."""

        super().__init__(parent_widget)
        self._parent_widget = parent_widget
        self._preferences = preferences
        self._updates = updates
        self._model_root = model_root
        self._acquisition = acquisition
        self._fetch_thumbnail = fetch_thumbnail
        self._feedback = feedback or self._show_feedback
        self.picker_bridge = ModelUpdatePickerBridge(self)
        self.picker_bridge.familyRequested.connect(self._present_family)
        self.picker_bridge.dismissRequested.connect(self._dismiss_update)
        self.picker_bridge.pageOptOutRequested.connect(self._disable_page_updates)
        self._thread: QThread | None = None
        self._task: _UpdateTask | None = None
        self._overlay: ModelDiscoveryOverlay | None = None
        self._family_modal: ModelVersionFamilyModal | None = None
        self._active_proposal: ModelUpdateProposal | None = None
        self._after_release: Callable[[], None] | None = None
        self._thumbnail_jobs: set[VersionThumbnailLoad] = set()
        self._active_thumbnail_load: VersionThumbnailLoad | None = None

    @property
    def running(self) -> bool:
        """Return whether one provider check or transfer is active."""

        return self._thread is not None

    def check_on_focus(self) -> bool:
        """Start a relevant update check only after explicit opt-in."""

        if not self._notifications_enabled():
            self.picker_bridge.replace(())
            return False
        if self.running or self._family_modal is not None:
            return False
        return self._start(
            lambda: self._updates.check_updates(ModelUpdatePreferences(enabled=True)),
            on_succeeded=self._handle_proposals,
            operation="check",
        )

    def close(self) -> None:
        """Request background-task interruption during shell shutdown."""

        if self._overlay is not None:
            self._overlay.close()
        for job in self._thumbnail_jobs:
            job.cancel()
        thread = self._thread
        if thread is not None:
            thread.requestInterruption()
            thread.quit()
            if not thread.wait(5000):
                _LOGGER.warning("Model update task did not stop before shutdown.")

    def _notifications_enabled(self) -> bool:
        """Read consent from the authoritative CivitAI preference aggregate."""

        try:
            preferences = self._preferences.load_preferences()
        except (OSError, RuntimeError, TypeError, ValueError):
            _LOGGER.exception("Could not load model update preferences.")
            return False
        return bool(getattr(preferences, "model_update_notifications_enabled", False))

    @Slot(object)
    def _handle_proposals(self, value: object) -> None:
        """Publish badges without interrupting the current workflow."""

        if not isinstance(value, tuple) or not all(
            isinstance(item, ModelUpdateProposal) for item in value
        ):
            self._feedback(
                "error", _text(app_text("Model update results were invalid."))
            )
            return
        self.picker_bridge.replace(
            value
            if self._model_root is not None and self._acquisition is not None
            else ()
        )

    @Slot(str)
    def _dismiss_update(self, sha256: str) -> None:
        """Persist one dismissed candidate and remove its visible badge."""

        proposal = self.picker_bridge.proposal_for_sha(sha256)
        if proposal is None:
            return
        try:
            dismissed = self._updates.dismiss_update(
                sha256=sha256, version_id=proposal.candidate.version_id
            )
        except (OSError, RuntimeError, ValueError):
            _LOGGER.exception("Could not dismiss model update for SHA %s.", sha256)
            return
        if dismissed:
            self.picker_bridge.remove(sha256)

    @Slot(str)
    def _disable_page_updates(self, sha256: str) -> None:
        """Persist a page-level opt-out and clear all of its visible badges."""

        proposal = self.picker_bridge.proposal_for_sha(sha256)
        model_id = proposal.current.model_id if proposal is not None else None
        if model_id is None:
            return
        try:
            disabled = self._updates.disable_model_updates(model_id)
        except (OSError, RuntimeError, ValueError):
            _LOGGER.exception("Could not disable model updates for page %s.", model_id)
            return
        if disabled:
            self.picker_bridge.remove_page(model_id)

    @Slot(str)
    def _present_family(self, sha256: str) -> None:
        """Open a contained chronology only after a picker action requests it."""

        if self._family_modal is not None or self.running:
            return
        proposal = self.picker_bridge.proposal_for_sha(sha256)
        if proposal is None:
            return
        overlay = ModelDiscoveryOverlay(owner=self._parent_widget)
        modal = ModelVersionFamilyModal(
            proposal=proposal,
            open_url=open_external_url,
            parent=overlay,
        )
        overlay.attach(modal)
        modal.finished.connect(self._dismiss_family)
        modal.downloadRequested.connect(self._download_version)
        self._overlay = overlay
        self._family_modal = modal
        self._active_proposal = proposal
        overlay.present()
        modal.show_loading()
        self._start(
            lambda: (
                self._updates.version_family(proposal),
                self._updates.installed_hashes_for_kind(proposal.current.artifact_kind),
            ),
            on_succeeded=self._handle_family,
            on_failed=self._show_modal_failure,
            operation="family",
        )

    @Slot(object)
    def _handle_family(self, value: object) -> None:
        """Show only the queried installed model's verified family."""

        modal = self._family_modal
        proposal = self._active_proposal
        if modal is None or proposal is None:
            return
        if not isinstance(value, tuple) or len(value) != 2:
            modal.show_failure(_text(app_text("Model update results were invalid.")))
            return
        versions, installed_hashes = value
        if (
            not isinstance(versions, tuple)
            or not isinstance(installed_hashes, frozenset)
            or not all(isinstance(item, str) for item in installed_hashes)
            or not all(
                isinstance(item, DiscoveredModel)
                and item.artifact_kind is proposal.current.artifact_kind
                and item.base_model is not None
                and proposal.current.base_model is not None
                and item.base_model.casefold() == proposal.current.base_model.casefold()
                for item in versions
            )
        ):
            modal.show_failure(_text(app_text("Model update results were invalid.")))
            return
        modal.show_family(versions, installed_hashes=installed_hashes)
        if self._fetch_thumbnail is not None:
            self._start_thumbnails(versions)
        else:
            for version in versions:
                modal.set_thumbnail_unavailable(version.version_id)

    @Slot(object)
    def _download_version(self, value: object) -> None:
        """Queue one selected exact version beside the installed file."""

        modal = self._family_modal
        proposal = self._active_proposal
        acquisition = self._acquisition
        if (
            modal is None
            or proposal is None
            or acquisition is None
            or not isinstance(value, DiscoveredModel)
            or modal.selected_version != value
        ):
            return
        selected = ModelUpdateProposal(proposal.current, value)
        modal.set_downloading()

        def start_download() -> None:
            """Transfer only after the version lookup task has released."""

            self._start(
                lambda: acquisition.download_selected(
                    (selected,),
                    selected_identities=(model_update_identity(selected),),
                ),
                on_succeeded=self._handle_downloads,
                on_failed=self._show_modal_failure,
                operation="download",
            )

        if self.running:
            self._after_release = start_download
        else:
            start_download()

    @Slot(object)
    def _handle_downloads(self, value: object) -> None:
        """Keep the family visible after verified side-by-side completion."""

        modal = self._family_modal
        if modal is None:
            return
        if not isinstance(value, tuple) or len(value) != 1:
            modal.show_failure(
                _text(app_text("Model downloads returned invalid results."))
            )
            return
        proposal = self._active_proposal
        selected = modal.selected_version
        if (
            proposal is not None
            and selected is not None
            and selected.version_id == proposal.candidate.version_id
        ):
            self._dismiss_update(proposal.current.sha256)
        modal.finish_download()

    def _start(
        self,
        work: Callable[[], object],
        *,
        on_succeeded: Callable[[object], None],
        operation: str,
        on_failed: Callable[[str], None] | None = None,
    ) -> bool:
        """Start one background task and bind deterministic owner-thread cleanup."""

        if self._thread is not None:
            return False
        thread = QThread(self)
        task = _UpdateTask(work, operation=operation)
        task.moveToThread(thread)
        thread.started.connect(task.run)
        task.succeeded.connect(on_succeeded)
        if on_failed is not None:
            task.failed.connect(on_failed)
        task.finished.connect(thread.quit)
        task.finished.connect(task.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._release_task)
        self._thread = thread
        self._task = task
        thread.start()
        return True

    @Slot()
    def _release_task(self) -> None:
        """Release completed execution ownership."""

        self._thread = None
        self._task = None
        after_release, self._after_release = self._after_release, None
        if after_release is not None:
            after_release()

    @Slot(int)
    def _dismiss_family(self, _result: int) -> None:
        """Remove the full-window wash when version browsing ends."""

        overlay = self._overlay
        self._overlay = None
        self._family_modal = None
        self._active_proposal = None
        if self._active_thumbnail_load is not None:
            self._active_thumbnail_load.cancel()
            self._active_thumbnail_load = None
        if overlay is not None:
            overlay.hide()
            overlay.deleteLater()

    def _start_thumbnails(self, versions: tuple[DiscoveredModel, ...]) -> None:
        """Fetch independent card previews without blocking version selection."""

        fetch = self._fetch_thumbnail
        if fetch is None:
            return
        job = VersionThumbnailLoad(versions, fetch=fetch)
        job.signals.loaded.connect(self._thumbnail_loaded)
        job.signals.failed.connect(self._thumbnail_failed)
        job.signals.finished.connect(self._thumbnail_finished)
        self._thumbnail_jobs.add(job)
        self._active_thumbnail_load = job
        start_qt_runnable(job)

    @Slot(int, object)
    def _thumbnail_loaded(self, version_id: int, payload: object) -> None:
        """Decode only current-family, bounded image bytes on the GUI thread."""

        job = self._active_thumbnail_load
        modal = self._family_modal
        if job is None or modal is None or self.sender() is not job.signals:
            return
        image = QImage.fromData(payload) if isinstance(payload, bytes) else QImage()
        if image.isNull():
            modal.set_thumbnail_unavailable(version_id)
        else:
            modal.set_thumbnail(version_id, image)

    @Slot(int)
    def _thumbnail_failed(self, version_id: int) -> None:
        """Settle one current-family card without affecting other previews."""

        job = self._active_thumbnail_load
        modal = self._family_modal
        if job is not None and modal is not None and self.sender() is job.signals:
            modal.set_thumbnail_unavailable(version_id)

    @Slot()
    def _thumbnail_finished(self) -> None:
        """Release a finished task while preserving another active family."""

        sender = self.sender()
        for job in tuple(self._thumbnail_jobs):
            if job.signals is sender:
                self._thumbnail_jobs.remove(job)
                if self._active_thumbnail_load is job:
                    self._active_thumbnail_load = None
                break

    @Slot(str)
    def _show_modal_failure(self, detail: str) -> None:
        """Keep an explicit user-requested failure inside the family panel."""

        modal = self._family_modal
        if modal is not None:
            modal.show_failure(
                _text(app_text("Model update operation failed: %1", detail))
            )

    def _show_feedback(self, severity: str, message: str) -> None:
        """Show a localized, non-blocking shell notification."""

        common = {
            "title": _text(app_text("Model updates")),
            "content": message,
            "isClosable": True,
            "position": InfoBarPosition.TOP_RIGHT,
            "duration": 5000,
            "parent": self._parent_widget,
        }
        if severity == "success":
            InfoBar.success(**common)
        elif severity == "warning":
            InfoBar.warning(**common)
        else:
            InfoBar.error(**common)


def _text(message: ApplicationText) -> str:
    """Render one application-owned localized message."""

    return render_application_text(message)


__all__ = ["ModelUpdateNotificationController", "ModelUpdatePreferenceSource"]
