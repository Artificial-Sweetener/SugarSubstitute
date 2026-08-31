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

"""Compose process-lifetime managed Comfy crash recovery collaborators."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QObject

from substitute.app.bootstrap.managed_comfy_runtime_owner import (
    ManagedComfyRuntimeOwner,
)
from substitute.app.bootstrap.managed_compatibility_recovery import (
    request_managed_recovery_stop,
)
from substitute.app.bootstrap.managed_recovery_adapters import (
    cleanup_managed_recovery_state,
    confirmed_managed_recovery_termination_status,
)
from substitute.app.bootstrap.process_pump_execution import create_process_pump_task
from substitute.application.comfy_startup_diagnostics import (
    ComfyStartupDiagnosticsCollector,
)
from substitute.domain.onboarding import InstallationContext
from substitute.infrastructure.comfy.managed_launcher import (
    ManagedTaskFactory,
    start_managed_comfy_background,
)
from substitute.presentation.qt.execution import QtOwnerThreadDispatcher
from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)


def build_managed_comfy_runtime_owner(
    *,
    context: InstallationContext,
    comfy_output_stream: TerminalOutputStream,
    execution_runtime: Any,
    qt_owner: QObject,
) -> ManagedComfyRuntimeOwner:
    """Build the process owner that can replace managed Comfy in place."""

    diagnostics = ComfyStartupDiagnosticsCollector()
    restart_submitter = execution_runtime.submitter(
        "startup",
        owner_id="managed_comfy_crash_recovery",
        dispatcher=QtOwnerThreadDispatcher(qt_owner),
    )

    def managed_task_factory(
        identity: Any,
        task_context: Any,
        work: Any,
        thread_name: str,
    ) -> Any:
        """Create managed launch and output-pump tasks in the shared runtime."""

        return create_process_pump_task(
            execution_runtime=execution_runtime,
            dispatcher_factory=lambda: QtOwnerThreadDispatcher(qt_owner),
            identity=identity,
            context=task_context,
            work=work,
            thread_name=thread_name,
        )

    typed_task_factory = cast(ManagedTaskFactory, managed_task_factory)

    def launch_state() -> object | None:
        """Launch a replacement managed process while preserving shell output."""

        target = context.comfy_target
        workspace = target.workspace_path
        if workspace is None:
            raise RuntimeError("Managed Comfy restart requires a workspace.")

        def append_output(line: str) -> None:
            """Keep restart diagnostics in the existing Comfy output stream."""

            diagnostics.append_output(line)
            comfy_output_stream.append_line(line)

        return start_managed_comfy_background(
            endpoint=target.endpoint,
            workspace=workspace,
            runtime_state_dir=context.runtime_state_dir,
            on_log=append_output,
            on_status=comfy_output_stream.append_line,
            diagnostics=diagnostics,
            launch_task_factory=typed_task_factory,
            process_pump_task_factory=typed_task_factory,
            python_executable=(
                target.python_binding.executable
                if target.python_binding is not None
                else None
            ),
        )

    return ManagedComfyRuntimeOwner(
        target=context.comfy_target,
        submitter=restart_submitter,
        request_stop=request_managed_recovery_stop,
        cleanup_state=cleanup_managed_recovery_state,
        confirmed_termination_status=confirmed_managed_recovery_termination_status(),
        launch_state=launch_state,
    )


__all__ = ["build_managed_comfy_runtime_owner"]
