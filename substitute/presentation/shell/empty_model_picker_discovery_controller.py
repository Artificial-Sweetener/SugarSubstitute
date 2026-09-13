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

"""Coordinate the reusable model-suggestion surface for empty pickers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Protocol

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QWidget
from qfluentwidgets import InfoBar  # type: ignore[import-untyped]

from substitute.application.model_suggestions import ModelSuggestionService
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_suggestions import (
    ModelSuggestion,
    ModelSuggestionContext,
    ModelSuggestionPlan,
)
from substitute.presentation.model_discovery import (
    InstalledModelReceiver,
    ModelDiscoveryModal,
    ModelSuggestionCredentialCoordinator,
)
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.model_acquisition import AcquisitionResult
from sugarsubstitute_shared.presentation.localization import render_application_text

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _ThumbnailLoadResult:
    """Carry one independently settled provider thumbnail request."""

    identity: str
    thumbnail: ThumbnailAsset | None


class ModelCatalogRefresher(Protocol):
    """Refresh one authoritative model kind after a verified download."""

    def invalidate(self, kind: str | None = None) -> None:
        """Invalidate cached catalog rows."""

    def refresh_models(self, kind: str) -> object:
        """Reload authoritative catalog rows from the active ComfyUI target."""


class _ThreadCancellation:
    """Expose QThread interruption through the acquisition cancellation port."""

    def __init__(self, thread: QThread) -> None:
        """Store the operation's owning thread."""

        self._thread = thread

    def is_cancelled(self) -> bool:
        """Return whether shutdown or modal cancellation interrupted the task."""

        return self._thread.isInterruptionRequested()


class _SuggestionTask(QObject):
    """Run one bounded provider operation away from the Qt owner thread."""

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
        """Execute the use case and always release its owning thread."""

        try:
            value = self._work()
        except Exception as error:
            _LOGGER.exception("Model suggestion operation failed: %s", self._operation)
            self.failed.emit(str(error) or type(error).__name__)
        else:
            self.succeeded.emit(value)
        finally:
            self.finished.emit()


class EmptyModelPickerDiscoveryController(QObject):
    """Own discovery, explicit credentials, verified transfer, and picker refresh."""

    def __init__(
        self,
        *,
        parent_widget: QWidget,
        service: ModelSuggestionService | None,
        catalog: ModelCatalogRefresher,
        credentials: ModelSuggestionCredentialCoordinator,
    ) -> None:
        """Store the application, catalog, credential, and presentation owners."""

        super().__init__(parent_widget)
        self._parent_widget = parent_widget
        self._service = service
        self._catalog = catalog
        self._credentials = credentials
        self._thread: QThread | None = None
        self._task: _SuggestionTask | None = None
        self._modal: ModelDiscoveryModal | None = None
        self._plan: ModelSuggestionPlan | None = None
        self._installed_value_receiver: InstalledModelReceiver | None = None
        self._pending_operation: (
            tuple[Callable[[], object], Callable[[object], None], str] | None
        ) = None

    @property
    def running(self) -> bool:
        """Return whether provider discovery, preview, or acquisition is active."""

        return self._thread is not None

    def request_for_empty_picker(
        self,
        context: ModelSuggestionContext,
        installed_value_receiver: InstalledModelReceiver,
    ) -> bool:
        """Open discovery immediately for one compatibility-qualified empty picker."""

        if self.running or self._modal is not None:
            return False
        service = self._service
        if service is None:
            InfoBar.warning(
                title=render_application_text(app_text("Find models")),
                content=render_application_text(
                    app_text(
                        "Model downloads are unavailable for this ComfyUI target. You can still add files to its model folders manually."
                    )
                ),
                duration=5000,
                parent=self._parent_widget,
            )
            return False
        modal = ModelDiscoveryModal(parent=self._parent_widget)
        modal.download_requested.connect(self._download_selected)
        modal.finished.connect(self._modal_closed)
        self._modal = modal
        self._installed_value_receiver = installed_value_receiver
        modal.show_loading()
        return self._start(
            lambda: service.plan_empty_picker(context),
            self._handle_plan,
            "discover",
        )

    def close(self) -> None:
        """Cancel owned work and close the suggestion surface during shutdown."""

        modal = self._modal
        if modal is not None:
            modal.close()
        thread = self._thread
        if thread is not None:
            thread.requestInterruption()
            thread.quit()
            if not thread.wait(5000):
                _LOGGER.warning("Model suggestion task did not stop before shutdown.")

    @Slot(object)
    def _handle_plan(self, value: object) -> None:
        """Render a valid plan and queue its independently loaded thumbnails."""

        modal = self._modal
        service = self._service
        if modal is None or service is None:
            return
        if not isinstance(value, ModelSuggestionPlan):
            modal.show_failure(
                render_application_text(
                    app_text("Model discovery returned invalid results.")
                )
            )
            return
        self._plan = value
        modal.show_plan(value)
        suggestions = tuple(
            suggestion
            for suggestion in value.suggestions
            if suggestion.thumbnail_url is not None
        )
        if suggestions:
            self._pending_operation = (
                lambda: self._load_thumbnails(service, suggestions),
                self._handle_thumbnails,
                "thumbnails",
            )

    @Slot(object)
    def _handle_thumbnails(self, value: object) -> None:
        """Install valid independently loaded thumbnails into visible cards."""

        modal = self._modal
        if modal is None or not isinstance(value, tuple):
            return
        for item in value:
            if not isinstance(item, _ThumbnailLoadResult):
                continue
            if item.thumbnail is None:
                modal.set_thumbnail_unavailable(item.identity)
            else:
                modal.set_thumbnail(item.identity, item.thumbnail)

    @staticmethod
    def _load_thumbnails(
        service: ModelSuggestionService,
        suggestions: tuple[ModelSuggestion, ...],
    ) -> tuple[_ThumbnailLoadResult, ...]:
        """Settle each preview independently so one provider asset cannot fail all."""

        results: list[_ThumbnailLoadResult] = []
        thread = QThread.currentThread()
        for suggestion in suggestions:
            if thread.isInterruptionRequested():
                break
            try:
                thumbnail = service.fetch_thumbnail(suggestion)
            except Exception:
                _LOGGER.warning(
                    "Model suggestion thumbnail failed",
                    extra={"suggestion_identity": suggestion.identity},
                    exc_info=True,
                )
                thumbnail = None
            results.append(_ThumbnailLoadResult(suggestion.identity, thumbnail))
        return tuple(results)

    @Slot(str)
    def _download_selected(self, identity: str) -> None:
        """Prompt only when necessary, then queue the exact reviewed transfer."""

        plan = self._plan
        service = self._service
        modal = self._modal
        if plan is None or service is None or modal is None:
            return
        suggestion = next(
            (item for item in plan.suggestions if item.identity == identity), None
        )
        if suggestion is None:
            modal.show_failure(
                render_application_text(
                    app_text("The selected model is no longer available.")
                )
            )
            return
        try:
            authorized = self._credentials.authorize(suggestion, modal)
        except RuntimeError as error:
            _LOGGER.warning(
                "Model suggestion credential flow is unavailable",
                extra={"provider_id": suggestion.reference.provider_id},
                exc_info=error,
            )
            modal.show_failure(
                render_application_text(
                    app_text(
                        "Credentials are unavailable for %1.",
                        suggestion.reference.provider_name,
                    )
                )
            )
            return
        if not authorized:
            return
        modal.set_downloading(suggestion)

        def acquire() -> object:
            """Acquire and refresh the catalog before publishing the field value."""

            thread = self._thread
            cancellation = _ThreadCancellation(thread) if thread is not None else None
            result = service.acquire(plan, identity, cancellation=cancellation)
            model_kind = plan.context.artifact_kind.value
            self._catalog.invalidate(model_kind)
            self._catalog.refresh_models(model_kind)
            return result

        if self.running:
            self._pending_operation = (acquire, self._handle_download, "download")
        else:
            self._start(acquire, self._handle_download, "download")

    @Slot(object)
    def _handle_download(self, value: object) -> None:
        """Publish the exact installed backend value before closing the modal."""

        modal = self._modal
        plan = self._plan
        receiver = self._installed_value_receiver
        if (
            modal is None
            or plan is None
            or receiver is None
            or not isinstance(value, tuple)
            or len(value) != 2
            or not isinstance(value[0], ModelSuggestion)
            or not isinstance(value[1], AcquisitionResult)
        ):
            if modal is not None:
                modal.show_failure(
                    render_application_text(
                        app_text("Model download returned invalid results.")
                    )
                )
            return
        result = value[1]
        try:
            backend_value = result.path.relative_to(plan.destination).as_posix()
        except ValueError:
            modal.show_failure(
                render_application_text(
                    app_text("The downloaded model has an invalid destination.")
                )
            )
            return
        receiver(backend_value)
        modal.finish_download()

    def _start(
        self,
        work: Callable[[], object],
        on_succeeded: Callable[[object], None],
        operation: str,
    ) -> bool:
        """Start one operation and preserve any next operation until release."""

        if self._thread is not None:
            return False
        thread = QThread(self)
        task = _SuggestionTask(work, operation=operation)
        task.moveToThread(thread)
        thread.started.connect(task.run)
        task.succeeded.connect(on_succeeded)
        task.failed.connect(self._show_failure)
        task.finished.connect(thread.quit)
        task.finished.connect(task.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._release_task)
        self._thread = thread
        self._task = task
        thread.start()
        return True

    @Slot(str)
    def _show_failure(self, detail: str) -> None:
        """Keep provider and acquisition failures visible in their modal."""

        if self._modal is not None:
            self._modal.show_failure(
                render_application_text(app_text("Model discovery failed: %1", detail))
            )

    @Slot()
    def _release_task(self) -> None:
        """Release one task and start a queued dependent operation."""

        self._thread = None
        self._task = None
        pending, self._pending_operation = self._pending_operation, None
        if pending is not None and self._modal is not None:
            self._start(*pending)

    @Slot(int)
    def _modal_closed(self, _result: int) -> None:
        """Cancel background work and release all per-request presentation state."""

        thread = self._thread
        if thread is not None:
            thread.requestInterruption()
        modal, self._modal = self._modal, None
        if modal is not None:
            modal.deleteLater()
        self._plan = None
        self._installed_value_receiver = None
        self._pending_operation = None


__all__ = ["EmptyModelPickerDiscoveryController", "ModelCatalogRefresher"]
