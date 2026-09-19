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

"""Capture executable evidence for an OS-authenticated local endpoint owner."""

from __future__ import annotations

import logging
from pathlib import Path
import sys

import psutil  # type: ignore[import-untyped]

from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceEndpoint,
    NativeApplicationInstanceOwner,
)
from sugarsubstitute_shared.process_identity import ProcessIdentity

_LOGGER = logging.getLogger(__name__)


def capture_native_instance_owner(
    endpoint: ApplicationInstanceEndpoint, identity: ProcessIdentity
) -> NativeApplicationInstanceOwner | None:
    """Bind kernel peer identity to an executable without accepting wire claims."""
    if endpoint.transport not in {"windows-named-pipe", "abstract-unix"}:
        return None
    try:
        if sys.platform == "win32":
            from sugarsubstitute_shared.windows_process_handle_api import (
                NativeProcessHandleApi,
            )

            native = NativeProcessHandleApi()
            handle = native.open(identity.pid)
            if handle is None:
                return None
            try:
                if abs(native.creation_time(handle) - identity.created_at) > 0.000_001:
                    return None
                executable = native.image_path(handle)
                if native.wait(handle, 0):
                    return None
            finally:
                native.close(handle)
        else:
            process = psutil.Process(identity.pid)
            if abs(float(process.create_time()) - identity.created_at) > 0.000_001:
                return None
            executable = Path(process.exe())
            if not process.is_running():
                return None
        return NativeApplicationInstanceOwner(endpoint, identity, executable)
    except (OSError, psutil.Error):
        _LOGGER.warning(
            "Could not retain native endpoint owner image | owner_pid=%s",
            identity.pid,
            exc_info=True,
        )
        return None
