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

"""Run model discovery and verified acquisitions outside the Qt UI thread."""

from __future__ import annotations

from collections.abc import Collection
import logging

from PySide6.QtCore import QObject, QThread, Signal, SignalInstance, Slot

from launcher.sugarsubstitute_launcher.ui.installer_errors import (
    launcher_failure_detail,
)
from sugarsubstitute_shared.model_discovery import (
    CubeModelCapability,
    ModelCategory,
    ModelDiscoveryPlan,
    ModelOnboardingService,
)


_LOGGER = logging.getLogger(__name__)


class _PlanWorker(QObject):
    """Build one provider-backed model discovery plan."""

    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        *,
        service: ModelOnboardingService,
        capabilities: tuple[CubeModelCapability, ...],
        selected_categories: tuple[ModelCategory, ...],
    ) -> None:
        """Store immutable planning inputs."""

        super().__init__()
        self._service = service
        self._capabilities = capabilities
        self._selected_categories = selected_categories

    @Slot()
    def run(self) -> None:
        """Discover safe cards and always terminate the owning thread."""

        try:
            plan = self._service.plan(
                self._capabilities,
                selected_categories=self._selected_categories,
            )
        except Exception as error:
            _LOGGER.exception("Installer model discovery failed.")
            self.failed.emit(launcher_failure_detail(error))
        else:
            self.succeeded.emit(plan)
        finally:
            self.finished.emit()


class _DownloadWorker(QObject):
    """Acquire explicitly selected exact model versions."""

    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        *,
        service: ModelOnboardingService,
        plan: ModelDiscoveryPlan,
        selected_identities: tuple[str, ...],
    ) -> None:
        """Store the reviewed plan and checked identities."""

        super().__init__()
        self._service = service
        self._plan = plan
        self._selected_identities = selected_identities

    @Slot()
    def run(self) -> None:
        """Download checked files and always terminate the owning thread."""

        try:
            results = self._service.download_selected(
                self._plan,
                selected_identities=self._selected_identities,
            )
        except Exception as error:
            _LOGGER.exception("Installer model acquisition failed.")
            self.failed.emit(launcher_failure_detail(error))
        else:
            self.succeeded.emit(results)
        finally:
            self.finished.emit()


class QtModelOnboardingExecutor(QObject):
    """Own one model planning or acquisition thread at a time."""

    plan_succeeded = Signal(object)
    download_succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize an idle model-operation slot."""

        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: QObject | None = None

    @property
    def running(self) -> bool:
        """Return whether planning or acquisition owns the execution slot."""

        return self._thread is not None

    def start_plan(
        self,
        *,
        service: ModelOnboardingService,
        capabilities: Collection[CubeModelCapability],
        selected_categories: Collection[ModelCategory],
    ) -> bool:
        """Start provider discovery unless another model operation is active."""

        worker = _PlanWorker(
            service=service,
            capabilities=tuple(capabilities),
            selected_categories=tuple(selected_categories),
        )
        return self._start(worker, succeeded=self.plan_succeeded)

    def start_download(
        self,
        *,
        service: ModelOnboardingService,
        plan: ModelDiscoveryPlan,
        selected_identities: Collection[str],
    ) -> bool:
        """Start checked acquisitions unless another model operation is active."""

        worker = _DownloadWorker(
            service=service,
            plan=plan,
            selected_identities=tuple(selected_identities),
        )
        return self._start(worker, succeeded=self.download_succeeded)

    def _start(self, worker: QObject, *, succeeded: SignalInstance) -> bool:
        """Bind one worker to a fresh thread and deterministic cleanup."""

        if self._thread is not None:
            worker.deleteLater()
            return False
        thread = QThread(self)
        worker.moveToThread(thread)
        run = getattr(worker, "run")
        worker_succeeded = getattr(worker, "succeeded")
        worker_failed = getattr(worker, "failed")
        worker_finished = getattr(worker, "finished")
        thread.started.connect(run)
        worker_succeeded.connect(succeeded.emit)
        worker_failed.connect(self.failed.emit)
        worker_finished.connect(thread.quit)
        worker_finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._finish)
        self._thread = thread
        self._worker = worker
        thread.start()
        return True

    @Slot()
    def _finish(self) -> None:
        """Release worker ownership and publish operation completion."""

        self._thread = None
        self._worker = None
        self.finished.emit()


def require_discovery_plan(value: object) -> ModelDiscoveryPlan:
    """Narrow one Qt payload to a shared discovery plan."""

    if not isinstance(value, ModelDiscoveryPlan):
        raise TypeError("Model discovery worker returned an invalid plan.")
    return value


__all__ = ["QtModelOnboardingExecutor", "require_discovery_plan"]
