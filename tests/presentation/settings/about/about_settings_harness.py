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

"""Provide focused construction and assertion support for About settings tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from threading import Event
from typing import Any, cast

import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication, QLabel

from substitute.application.about import (
    AboutInfoService,
    AboutInfoSnapshot,
    AboutVersionRow,
    AboutVersionStatus,
)
from substitute.app.bootstrap.settings_execution import (
    create_settings_task_runner_factory,
)
from substitute.presentation.settings.about_page import AboutSettingsPage
from substitute.presentation.settings.settings_async import (
    SettingsAsyncTaskRunner,
    SettingsAsyncTaskRunnerFactory,
)
from substitute.presentation.shell.shell_resource_lifecycle import (
    ShellResourceLifecycle,
)
from tests.support.execution.runtime_support import ExecutionRuntimeStub
from tests.support.execution import ImmediateTaskSubmitter
from tests.support.qt.lifecycle import destroy_qt_object


class AboutInfoServiceDouble:
    """Return deterministic About snapshots for focused widget tests."""

    def __init__(self, *, qpane_version: str = "2.0.1") -> None:
        """Store the version value returned by refreshed snapshots."""

        self._qpane_version = qpane_version

    def placeholder_snapshot(self) -> AboutInfoSnapshot:
        """Return the initial placeholder snapshot."""

        return about_snapshot("placeholder")

    def snapshot(self) -> AboutInfoSnapshot:
        """Return the refreshed snapshot."""

        return about_snapshot(self._qpane_version)


class BlockingAboutInfoService(AboutInfoServiceDouble):
    """Hold snapshot completion behind an explicit test-controlled barrier."""

    def __init__(self, *, qpane_version: str) -> None:
        """Initialize the worker-start and release barriers."""

        super().__init__(qpane_version=qpane_version)
        self.started = Event()
        self.release = Event()
        self.release_timed_out = False

    def snapshot(self) -> AboutInfoSnapshot:
        """Publish worker entry and wait for the test to authorize completion."""

        self.started.set()
        self.release_timed_out = not self.release.wait(timeout=5.0)
        return super().snapshot()


AboutPageFactory = Callable[
    [AboutInfoService | AboutInfoServiceDouble, SettingsAsyncTaskRunnerFactory | None],
    AboutSettingsPage,
]


@pytest.fixture
def about_page_factory() -> Iterator[AboutPageFactory]:
    """Create About pages and release every owned Qt and execution resource."""

    application()
    pages: list[AboutSettingsPage] = []

    def create_page(
        service: AboutInfoService | AboutInfoServiceDouble,
        task_runner_factory: SettingsAsyncTaskRunnerFactory | None = None,
    ) -> AboutSettingsPage:
        """Create and track one About page for deterministic teardown."""

        page = AboutSettingsPage(
            cast(AboutInfoService, service),
            task_runner_factory=task_runner_factory or immediate_task_runner_factory,
        )
        pages.append(page)
        return page

    yield create_page

    for page in reversed(pages):
        runner = cast(SettingsAsyncTaskRunner, cast(Any, page)._async_runner)
        runner.shutdown()
        page.close()
        destroy_qt_object(page)


def immediate_task_runner_factory(
    parent: QObject,
    *,
    owner_id: str,
) -> SettingsAsyncTaskRunner:
    """Create an immediate Settings task runner for About page tests."""

    return SettingsAsyncTaskRunner(
        parent,
        submitter=ImmediateTaskSubmitter(),
        owner_id=owner_id,
    )


def threaded_task_runner_factory() -> SettingsAsyncTaskRunnerFactory:
    """Create a runtime-backed Settings factory for concurrency assertions."""

    return create_settings_task_runner_factory(
        ExecutionRuntimeStub(),
        resource_lifecycle=ShellResourceLifecycle(),
    )


def about_snapshot(qpane_version: str) -> AboutInfoSnapshot:
    """Return one deterministic About snapshot."""

    return AboutInfoSnapshot(
        versions=(
            AboutVersionRow(
                component_key="SugarSubstitute",
                label="SugarSubstitute",
                value="0.5.0",
                status=AboutVersionStatus.AVAILABLE,
                subtitle="The desktop native Qt frontend for ComfyUI",
                authors="Artificial Sweetener",
                external_url=(
                    "https://github.com/Artificial-Sweetener/SugarSubstitute"
                ),
            ),
            AboutVersionRow(
                component_key="ComfyUI",
                label="ComfyUI",
                value="0.3.2",
                status=AboutVersionStatus.AVAILABLE,
                subtitle=(
                    "The most powerful and modular diffusion model GUI, api and backend"
                ),
                authors="Comfy Org",
                external_url="https://github.com/Comfy-Org/ComfyUI",
            ),
            AboutVersionRow(
                component_key="SugarCubes",
                label="SugarCubes",
                value="0.9.0",
                status=AboutVersionStatus.AVAILABLE,
                subtitle="Composable workflow units for ComfyUI",
                authors="Artificial Sweetener",
                external_url="https://github.com/Artificial-Sweetener/SugarCubes",
            ),
            AboutVersionRow(
                component_key="SubstituteBackend",
                label="Substitute Backend",
                value="1.4.0",
                status=AboutVersionStatus.AVAILABLE,
                subtitle="Allow communication between ComfyUI deployments & Substitute",
                authors="Artificial Sweetener",
                external_url=(
                    "https://github.com/Artificial-Sweetener/Substitute-Backend"
                ),
            ),
            AboutVersionRow(
                component_key="SugarDSL",
                label="Sugar-DSL",
                value="0.2.0",
                status=AboutVersionStatus.AVAILABLE,
                subtitle=(
                    "The scripting language for composing ComfyUI workflows "
                    "with SugarCubes"
                ),
                authors="Artificial Sweetener",
                external_url="https://github.com/Artificial-Sweetener/Sugar-DSL",
            ),
            AboutVersionRow(
                component_key="QPane",
                label="QPane",
                value=qpane_version,
                status=AboutVersionStatus.AVAILABLE,
                subtitle="High-performance PySide6 image viewer",
                authors="Artificial Sweetener",
                external_url="https://github.com/Artificial-Sweetener/QPane",
            ),
            AboutVersionRow(
                component_key="PySide6FluentWidgets",
                label="PySide6-Fluent-Widgets",
                value="1.11.2",
                status=AboutVersionStatus.AVAILABLE,
                subtitle="A fluent design widgets library for PySide6",
                authors="zhiyiYo",
                external_url="https://github.com/zhiyiYo/PyQt-Fluent-Widgets",
            ),
            AboutVersionRow(
                component_key="PySide6",
                label="PySide6",
                value="6.9.0",
                status=AboutVersionStatus.AVAILABLE,
                subtitle="Qt for Python",
                authors="the Qt Company",
                external_url="https://pyside.org/",
            ),
        ),
        project_summary="Widget project summary",
        supporters=("Patron One",),
        special_thanks=("Contributor One",),
    )


def bind_refreshed_snapshot(
    page: AboutSettingsPage,
    service: AboutInfoServiceDouble,
) -> None:
    """Bind the deterministic refreshed snapshot without worker scheduling."""

    page.bind_snapshot(service.snapshot())


def label_texts(widget: AboutSettingsPage) -> tuple[str, ...]:
    """Return nonempty QLabel texts below one About page."""

    return tuple(
        text for label in widget.findChildren(QLabel) if (text := label.text().strip())
    )


def application() -> QApplication:
    """Return the process-owned QApplication, creating it when necessary."""

    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication([])


__all__ = [
    "AboutInfoServiceDouble",
    "AboutPageFactory",
    "BlockingAboutInfoService",
    "about_page_factory",
    "application",
    "bind_refreshed_snapshot",
    "immediate_task_runner_factory",
    "label_texts",
    "threaded_task_runner_factory",
]
