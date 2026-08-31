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

from collections.abc import Callable, Sequence
import logging
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QWidget
from qfluentwidgets import InfoBar, InfoBarPosition  # type: ignore[import-untyped]

from substitute.presentation.model_updates import ModelUpdateModal
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


UpdateChooser = Callable[
    [Sequence[ModelUpdateProposal], Path, QWidget], tuple[str, ...]
]
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
    """Own consent-gated checks, review, and side-by-side update downloads."""

    def __init__(
        self,
        *,
        parent_widget: QWidget,
        preferences: ModelUpdatePreferenceSource,
        updates: ModelUpdateService,
        model_root: Path | None,
        acquisition: ModelUpdateAcquisitionService | None,
        chooser: UpdateChooser | None = None,
        feedback: Feedback | None = None,
    ) -> None:
        """Store update boundaries without starting network work."""

        super().__init__(parent_widget)
        self._parent_widget = parent_widget
        self._preferences = preferences
        self._updates = updates
        self._model_root = model_root
        self._acquisition = acquisition
        self._chooser = chooser or self._choose_updates
        self._feedback = feedback or self._show_feedback
        self._thread: QThread | None = None
        self._task: _UpdateTask | None = None
        self._presented: set[str] = set()
        self._after_release: Callable[[], None] | None = None

    @property
    def running(self) -> bool:
        """Return whether one provider check or transfer is active."""

        return self._thread is not None

    def check_on_focus(self) -> bool:
        """Start a relevant update check only after explicit opt-in."""

        if self.running or not self._notifications_enabled():
            return False
        return self._start(
            lambda: self._updates.check_updates(ModelUpdatePreferences(enabled=True)),
            on_succeeded=self._handle_proposals,
            operation="check",
        )

    def close(self) -> None:
        """Request background-task interruption during shell shutdown."""

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
        """Present new exact versions and start only checked downloads."""

        if not isinstance(value, tuple) or not all(
            isinstance(item, ModelUpdateProposal) for item in value
        ):
            self._feedback(
                "error", _text(app_text("Model update results were invalid."))
            )
            return
        proposals = tuple(
            proposal
            for proposal in value
            if model_update_identity(proposal) not in self._presented
        )
        if not proposals:
            return
        self._presented.update(model_update_identity(item) for item in proposals)
        model_root = self._model_root
        if model_root is None:
            self._feedback(
                "warning",
                _text(
                    app_text(
                        "Model updates are available, but this ComfyUI target has no local download destination."
                    )
                ),
            )
            return
        selected = self._chooser(proposals, model_root, self._parent_widget)
        if not selected:
            return
        acquisition = self._acquisition
        if acquisition is None:
            self._feedback(
                "error",
                _text(
                    app_text(
                        "The model download service is unavailable for this target."
                    )
                ),
            )
            return

        def start_download() -> None:
            """Queue the reviewed transfer after update discovery releases its thread."""

            self._start(
                lambda: acquisition.download_selected(
                    proposals,
                    selected_identities=selected,
                ),
                on_succeeded=self._handle_downloads,
                operation="download",
            )

        self._after_release = start_download

    @Slot(object)
    def _handle_downloads(self, value: object) -> None:
        """Report verified side-by-side completion without changing workflows."""

        if not isinstance(value, tuple):
            self._feedback(
                "error", _text(app_text("Model downloads returned invalid results."))
            )
            return
        self._feedback(
            "success",
            _text(
                app_text(
                    "%1 model update(s) downloaded beside your current files.",
                    len(value),
                )
            ),
        )

    def _start(
        self,
        work: Callable[[], object],
        *,
        on_succeeded: Callable[[object], None],
        operation: str,
    ) -> bool:
        """Start one background task and bind deterministic owner-thread cleanup."""

        if self._thread is not None:
            return False
        thread = QThread(self)
        task = _UpdateTask(work, operation=operation)
        task.moveToThread(thread)
        thread.started.connect(task.run)
        task.succeeded.connect(on_succeeded)
        task.failed.connect(
            lambda detail: self._feedback(
                "error",
                _text(app_text("Model update operation failed: %1", detail)),
            )
        )
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

    @staticmethod
    def _choose_updates(
        proposals: Sequence[ModelUpdateProposal],
        model_root: Path,
        parent: QWidget,
    ) -> tuple[str, ...]:
        """Run the production unchecked update review modal."""

        modal = ModelUpdateModal(
            proposals=proposals,
            model_root=model_root,
            parent=parent,
        )
        try:
            return modal.choose_updates()
        finally:
            modal.deleteLater()

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
