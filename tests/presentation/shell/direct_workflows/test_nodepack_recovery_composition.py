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
from typing import cast

from pytest import MonkeyPatch

from substitute.presentation.shell import direct_workflow_composition as composition
from substitute.presentation.shell.comfy_connection_composition import (
    ComfyConnectionRuntimeComposition,
)
from substitute.presentation.shell.main_window_dependencies import (
    MainWindowDependencies,
)
from substitute.presentation.errors import ErrorReportPresenterProtocol
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
    target = object()
    file_actions = object()
    connection_recovery = object()
    error_presenter = object()
    shell = SimpleNamespace(
        direct_workflow_file_actions=file_actions,
        shell_resource_lifecycle=SimpleNamespace(
            register=lambda name, callback: registrations.append((name, callback))
        ),
    )
    dependencies = SimpleNamespace(comfy_target=target)
    comfy_connection = SimpleNamespace(recovery_service=connection_recovery)

    composition.bind_nodepack_recovery(
        shell,
        cast(MainWindowDependencies, dependencies),
        cast(ComfyConnectionRuntimeComposition, comfy_connection),
        cast(ErrorReportPresenterProtocol, error_presenter),
    )

    assert calls == [
        (
            shell,
            {
                "target": target,
                "file_actions": file_actions,
                "connection_recovery": connection_recovery,
                "error_presenter": error_presenter,
            },
        )
    ]
    assert registrations == [
        ("direct_workflow_nodepack_recovery", controller.close),
        ("direct_workflow_nodepack_recovery_review", presenter.close),
    ]
    assert shell.direct_workflow_nodepack_recovery_controller is controller
