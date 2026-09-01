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

"""Offer shared model discovery when a model picker has no local choices."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Protocol

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QWidget
from qfluentwidgets import InfoBar  # type: ignore[import-untyped]

from substitute.presentation.model_discovery import ModelDiscoveryModal
from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.model_discovery import (
    ModelCategory,
    ModelDiscoveryPlan,
    ModelOnboardingService,
)
from sugarsubstitute_shared.presentation.localization import render_application_text


_LOGGER = logging.getLogger(__name__)
PlanChooser = Callable[[ModelDiscoveryPlan, QWidget], tuple[str, ...]]
Feedback = Callable[[str, str], None]


class ModelCatalogInvalidator(Protocol):
    """Invalidate one model kind after a verified download."""

    def invalidate(self, kind: str | None = None) -> None:
        """Invalidate cached catalog rows."""


class _DiscoveryTask(QObject):
    """Run one blocking picker discovery or acquisition use case."""

    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, work: Callable[[], object], *, operation: str) -> None:
        """Store one operation and its diagnostic identity."""

        super().__init__()
        self._work = work
        self._operation = operation

    @Slot()
    def run(self) -> None:
        """Execute work and always terminate the owner thread."""

        try:
            result = self._work()
        except Exception as error:
            _LOGGER.exception(
                "Empty model picker operation failed: %s", self._operation
            )
            self.failed.emit(str(error) or type(error).__name__)
        else:
            self.succeeded.emit(result)
        finally:
            self.finished.emit()


class EmptyModelPickerDiscoveryController(QObject):
    """Own empty-picker discovery, review, verified transfer, and refresh."""

    def __init__(
        self,
        *,
        parent_widget: QWidget,
        service: ModelOnboardingService | None,
        catalog: ModelCatalogInvalidator,
        chooser: PlanChooser | None = None,
        feedback: Feedback | None = None,
    ) -> None:
        """Store reusable service and presentation boundaries."""

        super().__init__(parent_widget)
        self._parent_widget = parent_widget
        self._service = service
        self._catalog = catalog
        self._chooser = chooser or self._choose_models
        self._feedback = feedback or self._show_feedback
        self._thread: QThread | None = None
        self._task: _DiscoveryTask | None = None
        self._category: ModelCategory | None = None
        self._after_release: Callable[[], None] | None = None

    @property
    def running(self) -> bool:
        """Return whether discovery or a download is active."""

        return self._thread is not None

    def request_for_empty_picker(self, model_kind: str) -> bool:
        """Start shared discovery for one known empty model category."""

        if self.running:
            return False
        try:
            category = ModelCategory(model_kind)
        except ValueError:
            _LOGGER.warning("Ignored unknown empty model picker kind: %s", model_kind)
            return False
        service = self._service
        if service is None:
            self._feedback(
                "warning",
                _text(
                    app_text(
                        "Model downloads are unavailable for this ComfyUI target. You can still add files to its model folders manually."
                    )
                ),
            )
            return False
        self._category = category
        return self._start(
            lambda: service.plan_empty_picker(category),
            on_succeeded=self._handle_plan,
            operation="discover",
        )

    def close(self) -> None:
        """Request background-task shutdown with a bounded wait."""

        thread = self._thread
        if thread is not None:
            thread.requestInterruption()
            thread.quit()
            if not thread.wait(5000):
                _LOGGER.warning("Empty model picker task did not stop before shutdown.")

    @Slot(object)
    def _handle_plan(self, value: object) -> None:
        """Present safe cards or explain that no candidate is available."""

        if not isinstance(value, ModelDiscoveryPlan):
            self._feedback(
                "error", _text(app_text("Model discovery returned invalid results."))
            )
            return
        if not value.cards:
            self._feedback(
                "warning",
                _text(
                    app_text(
                        "No safe popular models are available for this picker right now."
                    )
                ),
            )
            return
        selected = self._chooser(value, self._parent_widget)
        if not selected:
            return
        service = self._service
        if service is None:
            return

        def start_download() -> None:
            """Queue the reviewed transfer after discovery releases its thread."""

            self._start(
                lambda: service.download_selected(
                    value,
                    selected_identities=selected,
                ),
                on_succeeded=self._handle_downloads,
                operation="download",
            )

        self._after_release = start_download

    @Slot(object)
    def _handle_downloads(self, value: object) -> None:
        """Invalidate the category and report verified completion."""

        if not isinstance(value, tuple):
            self._feedback(
                "error", _text(app_text("Model downloads returned invalid results."))
            )
            return
        category = self._category
        if category is not None:
            self._catalog.invalidate(category.value)
        self._feedback(
            "success",
            _text(
                app_text(
                    "%1 model file(s) downloaded and verified. Reopen the picker to use them.",
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
        """Start one blocking operation with owner-thread callbacks."""

        if self._thread is not None:
            return False
        thread = QThread(self)
        task = _DiscoveryTask(work, operation=operation)
        task.moveToThread(thread)
        thread.started.connect(task.run)
        task.succeeded.connect(on_succeeded)
        task.failed.connect(
            lambda detail: self._feedback(
                "error",
                _text(app_text("Model discovery failed: %1", detail)),
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
        """Release execution and start a queued checked acquisition."""

        self._thread = None
        self._task = None
        after_release, self._after_release = self._after_release, None
        if after_release is not None:
            after_release()

    @staticmethod
    def _choose_models(
        plan: ModelDiscoveryPlan,
        parent: QWidget,
    ) -> tuple[str, ...]:
        """Run the production unchecked discovery modal."""

        modal = ModelDiscoveryModal(plan=plan, parent=parent)
        try:
            return modal.choose_models()
        finally:
            modal.deleteLater()

    def _show_feedback(self, severity: str, message: str) -> None:
        """Show localized non-blocking feedback."""

        common = {
            "title": _text(app_text("Find models")),
            "content": message,
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


__all__ = ["EmptyModelPickerDiscoveryController", "ModelCatalogInvalidator"]
