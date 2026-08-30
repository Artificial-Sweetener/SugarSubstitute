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

"""Provide deterministic Comfy environment page test fixtures."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtCore import QObject
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from substitute.application.comfy_environment import ComfyEnvironmentService
from substitute.presentation.settings.comfy_environment_page import ComfyEnvironmentPage
from substitute.presentation.settings.settings_async import SettingsAsyncTaskRunner
from tests.support.execution import ImmediateTaskSubmitter


def immediate_task_runner_factory(
    parent: QObject,
    *,
    owner_id: str,
) -> SettingsAsyncTaskRunner:
    """Create an immediate Settings task runner for environment tests."""

    return SettingsAsyncTaskRunner(
        parent,
        submitter=ImmediateTaskSubmitter(),
        owner_id=owner_id,
    )


def environment_page(
    *,
    comfy_environment_service: ComfyEnvironmentService,
    open_reconfigure_window: Callable[[], object],
    error_presenter: Any | None = None,
) -> ComfyEnvironmentPage:
    """Create a Comfy environment settings page for widget contract tests."""

    page = ComfyEnvironmentPage(
        comfy_environment_service,
        open_reconfigure_window=open_reconfigure_window,
        error_presenter=error_presenter,
        task_runner_factory=immediate_task_runner_factory,
    )
    page.refresh()
    return page


def application() -> QApplication:
    """Return the active QApplication instance for widget contract tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast("QApplication", app)


def css_color(color: QColor) -> str:
    """Return the stylesheet rgba representation for a QColor-like test value."""

    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"


def deliver_queued_events(app: QApplication) -> None:
    """Deliver queued Qt work after a synchronous owner-state change."""

    app.sendPostedEvents()
    app.processEvents()
