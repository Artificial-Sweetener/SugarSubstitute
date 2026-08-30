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

"""Queue ready-shell GUI startup tasks in their canonical startup order."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


class ReadyShellStartupTaskQueueProtocol(Protocol):
    """Expose the queue operations needed to schedule ready-shell startup tasks."""

    def add(self, name: str, callback: Callable[[], None]) -> None:
        """Append one named startup task."""

    def start(self) -> None:
        """Start the queued startup task sequence."""


class RunnableReadyShellTaskProtocol(Protocol):
    """Expose execution of one already-composed ready-shell task."""

    def run(self) -> None:
        """Execute the task."""


class ReadyShellStartupTaskScheduler(Protocol):
    """Schedule composed ready-shell tasks through the canonical queue owner."""

    def __call__(
        self,
        *,
        queue: ReadyShellStartupTaskQueueProtocol,
        prepare_main_window: Callable[[], object],
        target_activation_task: RunnableReadyShellTaskProtocol,
        start_readiness_timer: Callable[[], None],
        shell_build_task: RunnableReadyShellTaskProtocol,
        metadata_bridge_task: RunnableReadyShellTaskProtocol,
        prompt_editor_warmup_task: RunnableReadyShellTaskProtocol,
        initial_workspace_prehydration_task: RunnableReadyShellTaskProtocol,
        minimum_shell_ready_task: RunnableReadyShellTaskProtocol,
    ) -> None:
        """Schedule all managed-ready startup tasks."""


@dataclass(frozen=True, slots=True)
class ReadyShellStartupTasks:
    """Store ready-shell startup task callbacks in execution order fields."""

    prepare_main_window: Callable[[], None]
    activate_target: Callable[[], None]
    start_readiness_timer: Callable[[], None]
    build_main_window: Callable[[], None]
    wire_metadata_bridge: Callable[[], None]
    warm_prompt_editor_gui: Callable[[], None]
    prehydrate_initial_workspace: Callable[[], None]
    mark_minimum_shell_ready: Callable[[], None]


def enqueue_ready_shell_startup_tasks(
    queue: ReadyShellStartupTaskQueueProtocol,
    tasks: ReadyShellStartupTasks,
) -> None:
    """Append ready-shell startup tasks in the canonical startup order."""

    queue.add("prepare_main_window", tasks.prepare_main_window)
    queue.add("activate_target", tasks.activate_target)
    queue.add("start_readiness_timer", tasks.start_readiness_timer)
    queue.add("build_main_window", tasks.build_main_window)
    queue.add("wire_metadata_bridge", tasks.wire_metadata_bridge)
    queue.add("warm_prompt_editor_gui", tasks.warm_prompt_editor_gui)
    queue.add("prehydrate_initial_workspace", tasks.prehydrate_initial_workspace)
    queue.add("mark_minimum_shell_ready", tasks.mark_minimum_shell_ready)
    queue.start()


def schedule_ready_shell_startup_tasks(
    *,
    queue: ReadyShellStartupTaskQueueProtocol,
    prepare_main_window: Callable[[], None],
    activate_target: Callable[[], None],
    start_readiness_timer: Callable[[], None],
    build_main_window: Callable[[], None],
    wire_metadata_bridge: Callable[[], None],
    warm_prompt_editor_gui: Callable[[], None],
    prehydrate_initial_workspace: Callable[[], None],
    mark_minimum_shell_ready: Callable[[], None],
) -> None:
    """Create and enqueue the ready-shell startup task bundle."""

    enqueue_ready_shell_startup_tasks(
        queue,
        ReadyShellStartupTasks(
            prepare_main_window=prepare_main_window,
            activate_target=activate_target,
            start_readiness_timer=start_readiness_timer,
            build_main_window=build_main_window,
            wire_metadata_bridge=wire_metadata_bridge,
            warm_prompt_editor_gui=warm_prompt_editor_gui,
            prehydrate_initial_workspace=prehydrate_initial_workspace,
            mark_minimum_shell_ready=mark_minimum_shell_ready,
        ),
    )


def schedule_ready_shell_task_adapters(
    *,
    queue: ReadyShellStartupTaskQueueProtocol,
    prepare_main_window: Callable[[], object],
    target_activation_task: RunnableReadyShellTaskProtocol,
    start_readiness_timer: Callable[[], None],
    shell_build_task: RunnableReadyShellTaskProtocol,
    metadata_bridge_task: RunnableReadyShellTaskProtocol,
    prompt_editor_warmup_task: RunnableReadyShellTaskProtocol,
    initial_workspace_prehydration_task: RunnableReadyShellTaskProtocol,
    minimum_shell_ready_task: RunnableReadyShellTaskProtocol,
) -> None:
    """Adapt composed startup tasks into the canonical callback sequence."""

    def prepare_main_window_task() -> None:
        """Load shell presentation collaborators before target activation."""

        prepare_main_window()

    schedule_ready_shell_startup_tasks(
        queue=queue,
        prepare_main_window=prepare_main_window_task,
        activate_target=target_activation_task.run,
        start_readiness_timer=start_readiness_timer,
        build_main_window=shell_build_task.run,
        wire_metadata_bridge=metadata_bridge_task.run,
        warm_prompt_editor_gui=prompt_editor_warmup_task.run,
        prehydrate_initial_workspace=initial_workspace_prehydration_task.run,
        mark_minimum_shell_ready=minimum_shell_ready_task.run,
    )


__all__ = [
    "ReadyShellStartupTaskScheduler",
    "ReadyShellStartupTaskQueueProtocol",
    "ReadyShellStartupTasks",
    "RunnableReadyShellTaskProtocol",
    "enqueue_ready_shell_startup_tasks",
    "schedule_ready_shell_startup_tasks",
    "schedule_ready_shell_task_adapters",
]
