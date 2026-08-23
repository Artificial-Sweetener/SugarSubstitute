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

"""Tests for Settings execution route composition."""

from __future__ import annotations

from PySide6.QtCore import QObject

from substitute.app.bootstrap.execution_runtime import ExecutionRuntime
from substitute.app.bootstrap.settings_execution import (
    create_settings_task_runner_factory,
)
from substitute.presentation.shell.shell_resource_lifecycle import (
    ShellResourceLifecycle,
)


def test_settings_runner_route_is_reusable_before_widget_destruction() -> None:
    """Shell cleanup should release all Settings owners before Qt deletion."""

    runtime = ExecutionRuntime()
    old_lifecycle = ShellResourceLifecycle()
    new_lifecycle = ShellResourceLifecycle()
    old_parent = QObject()
    new_parent = QObject()
    owner_ids = (
        "about_settings",
        "generation_settings",
        "cube_library_settings",
        "comfy_connection_settings",
        "comfy_environment_settings",
    )
    try:
        old_factory = create_settings_task_runner_factory(
            runtime,
            resource_lifecycle=old_lifecycle,
        )
        for owner_id in owner_ids:
            old_factory(old_parent, owner_id=owner_id)

        old_lifecycle.shutdown_or_raise()

        new_factory = create_settings_task_runner_factory(
            runtime,
            resource_lifecycle=new_lifecycle,
        )
        for owner_id in owner_ids:
            new_factory(new_parent, owner_id=owner_id)
    finally:
        new_lifecycle.shutdown()
        old_lifecycle.shutdown()
        old_parent.deleteLater()
        new_parent.deleteLater()
        runtime.shutdown()
