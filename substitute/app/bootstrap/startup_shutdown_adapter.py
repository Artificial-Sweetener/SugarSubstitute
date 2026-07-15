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

"""Concrete startup shutdown adapters for managed Comfy process cleanup."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from substitute.app.bootstrap.startup_shutdown import (
    create_startup_shutdown_runtime,
    StartupShutdownRuntime,
)
from substitute.infrastructure.comfy import process_manager


def create_process_manager_startup_shutdown_runtime(
    *,
    comfy_state_getter: Callable[[], object | None],
    save_session_before_cleanup: Callable[[], None] | None = None,
) -> StartupShutdownRuntime:
    """Build startup shutdown runtime with the process-manager cleanup adapter."""

    def typed_comfy_state_getter() -> process_manager.ManagedComfyState | None:
        """Return the current managed Comfy state with infrastructure typing."""

        return cast(process_manager.ManagedComfyState | None, comfy_state_getter())

    return create_startup_shutdown_runtime(
        comfy_state_getter=typed_comfy_state_getter,
        kill_process=process_manager.kill_comfyui_state,
        save_session_before_cleanup=save_session_before_cleanup,
    )


__all__ = ["create_process_manager_startup_shutdown_runtime"]
