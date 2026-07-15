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

"""Tests for shell GUI-reload lifecycle detachment."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.app.bootstrap.execution_runtime import ExecutionRuntime
from substitute.presentation.shell.shell_reload_lifecycle_controller import (
    ShellReloadLifecycleController,
)
from substitute.presentation.shell.shell_resource_lifecycle import (
    ShellResourceLifecycle,
)
from tests.execution_testing import RecordingDispatcher


class _Disposable:
    """Record dispose calls."""

    def __init__(self) -> None:
        """Create an undisposed object."""

        self.dispose_calls = 0

    def dispose(self) -> None:
        """Record one disposal request."""

        self.dispose_calls += 1


def test_detach_for_gui_reload_stops_observers_and_disposes_queue_surfaces() -> None:
    """GUI reload detachment should release UI and execution resources."""

    calls: list[object] = []
    dropdown = _Disposable()
    panel = _Disposable()
    observer = object()
    shell = SimpleNamespace(
        _detached_for_gui_reload=False,
        node_definition_refresh_controller=SimpleNamespace(
            dispose=lambda: calls.append("node")
        ),
        shell_resource_lifecycle=SimpleNamespace(
            shutdown_or_raise=lambda: calls.append("resources")
        ),
        generation_job_queue_service=SimpleNamespace(
            remove_observer=lambda callback: calls.append(callback)
        ),
        _generation_job_queue_observer=observer,
        _generation_queue_dropdown=dropdown,
        generationQueuePanel=panel,
    )
    controller = ShellReloadLifecycleController(shell)

    controller.detach_for_gui_reload()

    assert shell._detached_for_gui_reload is True
    assert calls == ["node", observer, "resources"]
    assert dropdown.dispose_calls == 1
    assert panel.dispose_calls == 1


def test_detach_for_gui_reload_allows_optional_queue_observer_removal() -> None:
    """Observer removal should be optional for lightweight shell doubles."""

    calls: list[str] = []
    shell = SimpleNamespace(
        _detached_for_gui_reload=False,
        node_definition_refresh_controller=SimpleNamespace(
            dispose=lambda: calls.append("node")
        ),
        shell_resource_lifecycle=SimpleNamespace(
            shutdown_or_raise=lambda: calls.append("resources")
        ),
        generation_job_queue_service=SimpleNamespace(),
        _generation_job_queue_observer=object(),
    )
    controller = ShellReloadLifecycleController(shell)

    controller.detach_for_gui_reload()

    assert shell._detached_for_gui_reload is True
    assert calls == ["node", "resources"]


def test_detach_for_gui_reload_is_idempotent() -> None:
    """Repeated reload detachment should not dispose shell resources twice."""

    calls: list[str] = []
    shell = SimpleNamespace(
        _detached_for_gui_reload=False,
        node_definition_refresh_controller=SimpleNamespace(
            dispose=lambda: calls.append("node")
        ),
        shell_resource_lifecycle=SimpleNamespace(
            shutdown_or_raise=lambda: calls.append("resources")
        ),
        generation_job_queue_service=SimpleNamespace(),
        _generation_job_queue_observer=object(),
    )
    controller = ShellReloadLifecycleController(shell)

    controller.detach_for_gui_reload()
    controller.detach_for_gui_reload()

    assert calls == ["node", "resources"]


def test_detach_releases_fixed_runtime_owners_before_replacement_build() -> None:
    """A replacement shell should reuse every fixed owner before Qt destruction."""

    runtime = ExecutionRuntime()
    lifecycle = ShellResourceLifecycle()
    owner_routes = (
        ("node_definition", "node_definition_cache"),
        ("generation_dispatch", "generation_queue_dispatch"),
        ("generation_preparation", "workspace_generation_preparation"),
        ("model_metadata", "manual_model_metadata_context_actions"),
        ("cube_library_update", "cube_library_update_controller"),
    )
    replacement_submitters = []
    listener_stops: list[str] = []
    try:
        for lane_name, owner_id in owner_routes:
            submitter = runtime.submitter(
                lane_name,
                owner_id=owner_id,
                dispatcher=RecordingDispatcher(),
            )
            lifecycle.register(f"{lane_name}:{owner_id}", submitter.close)
        lifecycle.register(
            "cube_library_listener",
            lambda: listener_stops.append("stopped"),
        )
        shell = SimpleNamespace(
            _detached_for_gui_reload=False,
            node_definition_refresh_controller=SimpleNamespace(dispose=lambda: None),
            shell_resource_lifecycle=lifecycle,
            generation_job_queue_service=SimpleNamespace(),
            _generation_job_queue_observer=object(),
        )

        ShellReloadLifecycleController(shell).detach_for_gui_reload()

        for lane_name, owner_id in owner_routes:
            replacement_submitters.append(
                runtime.submitter(
                    lane_name,
                    owner_id=owner_id,
                    dispatcher=RecordingDispatcher(),
                )
            )
        assert listener_stops == ["stopped"]
    finally:
        for submitter in replacement_submitters:
            submitter.close()
        lifecycle.shutdown()
        runtime.shutdown()
