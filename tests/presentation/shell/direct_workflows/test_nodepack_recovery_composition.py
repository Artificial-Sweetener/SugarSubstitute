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

"""Verify direct-workflow nodepack recovery shell composition."""

from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path
from typing import cast

import pytest
from qfluentwidgets import InfoBar  # type: ignore[import-untyped]
from pytest import MonkeyPatch

from substitute.application.comfy_connection import ComfyConnectionRecoveryService
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
)
from substitute.infrastructure.comfy.managed_validation import workspace_python_path
from substitute.presentation.shell import direct_workflow_composition as composition
from substitute.presentation.shell.comfy_connection_composition import (
    ComfyConnectionRuntimeComposition,
)
from substitute.presentation.shell.main_window_dependencies import (
    MainWindowDependencies,
)
from substitute.presentation.dialogs.workflow_nodepack_recovery_dialog import (
    WorkflowNodepackRecoveryPresenter,
)
from substitute.presentation.shell.direct_workflow_nodepack_recovery import (
    DirectWorkflowNodepackRecoveryController,
)


def test_bind_nodepack_recovery_owns_shell_registration(
    monkeypatch: MonkeyPatch,
) -> None:
    """Bind the controller, review owner, and cleanup endpoints atomically."""

    calls: list[tuple[object, dict[str, object]]] = []
    controller = cast(
        DirectWorkflowNodepackRecoveryController,
        SimpleNamespace(close=lambda: None),
    )
    presenter = cast(
        WorkflowNodepackRecoveryPresenter,
        SimpleNamespace(close=lambda: None),
    )
    recovery = composition.DirectWorkflowNodepackRecoveryComposition(
        controller=controller,
        presenter=presenter,
    )

    def compose(shell: object, **kwargs: object) -> object:
        """Capture the collaborators passed to the focused composition owner."""

        calls.append((shell, kwargs))
        return recovery

    monkeypatch.setattr(
        composition, "compose_direct_workflow_nodepack_recovery", compose
    )
    registrations: list[tuple[str, object]] = []
    connection_observers: list[object] = []
    restore_observers: list[object] = []
    target = object()
    connection_recovery = SimpleNamespace(
        add_observer=connection_observers.append,
        remove_observer=connection_observers.remove,
    )
    shell = SimpleNamespace(
        shell_resource_lifecycle=SimpleNamespace(
            register=lambda name, callback: registrations.append((name, callback))
        ),
        restore_finalized=SimpleNamespace(
            connect=restore_observers.append,
            disconnect=restore_observers.remove,
        ),
    )
    dependencies = SimpleNamespace(comfy_target=target)
    comfy_connection = SimpleNamespace(recovery_service=connection_recovery)

    composition.bind_nodepack_recovery(
        shell,
        cast(MainWindowDependencies, dependencies),
        cast(ComfyConnectionRuntimeComposition, comfy_connection),
    )

    assert calls == [
        (
            shell,
            {
                "target": target,
                "connection_recovery": connection_recovery,
            },
        )
    ]
    assert registrations[:2] == [
        ("direct_workflow_nodepack_recovery", controller.close),
        ("direct_workflow_nodepack_recovery_review", presenter.close),
    ]
    assert registrations[2][0] == "open_workflow_nodepack_reassessment"
    assert len(connection_observers) == len(restore_observers) == 1
    cleanup = registrations[2][1]
    assert callable(cleanup)
    cleanup()
    assert connection_observers == restore_observers == []
    assert shell.direct_workflow_nodepack_recovery_controller is controller


@pytest.mark.parametrize(
    ("mode", "install_owned", "uses_workspace_python"),
    [
        (ComfyTargetMode.MANAGED_LOCAL, True, True),
        (ComfyTargetMode.ATTACHED_LOCAL, False, False),
        (ComfyTargetMode.REMOTE, False, False),
    ],
)
def test_nodepack_install_runtime_requires_owned_managed_workspace_or_binding(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    mode: ComfyTargetMode,
    install_owned: bool,
    uses_workspace_python: bool,
) -> None:
    """Only an installed, owned managed target may infer its Python runtime."""

    python = workspace_python_path(tmp_path)
    python.parent.mkdir(parents=True)
    python.touch()
    (tmp_path / "main.py").touch()
    captured: dict[str, object] = {}

    class _Controller:
        """Record the installer environment selected by composition."""

        def __init__(self, **kwargs: object) -> None:
            """Capture the complete controller setup."""

            captured.update(kwargs)

        def observe_connection(self, _change: object) -> None:
            """Accept connection observation registration."""

    monkeypatch.setattr(
        composition, "DirectWorkflowNodepackRecoveryController", _Controller
    )
    observers: list[object] = []
    recovery = SimpleNamespace(
        add_observer=observers.append,
        request_restart=lambda: True,
    )
    shell = SimpleNamespace(
        node_definition_gateway=object(),
        editor_busy=object(),
    )
    target = ComfyTargetConfiguration(
        mode=mode,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=tmp_path,
        install_owned=install_owned,
        launch_owned=True,
        python_binding=None,
    )

    composition.compose_direct_workflow_nodepack_recovery(
        shell,
        target=target,
        connection_recovery=cast(ComfyConnectionRecoveryService, recovery),
    )

    assert captured["workspace"] == tmp_path
    assert captured["python_executable"] == (python if uses_workspace_python else None)
    assert len(observers) == 1

    warnings: list[dict[str, object]] = []
    monkeypatch.setattr(
        InfoBar,
        "warning",
        lambda **kwargs: warnings.append(kwargs),
    )
    failure = captured["present_failure"]
    assert callable(failure)
    failure("workflow-a", "install_nodepacks", RuntimeError("install failed"))
    assert len(warnings) == 1
    assert warnings[0]["parent"] is shell
