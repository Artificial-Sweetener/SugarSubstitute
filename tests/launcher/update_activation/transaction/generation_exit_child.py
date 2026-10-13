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

"""Expose authenticated readiness before a real Windows exit or termination."""

from __future__ import annotations

import os
from pathlib import Path
import sys

from sugarsubstitute_shared.application_readiness import (
    ApplicationReadinessReceipt,
    ApplicationReadinessSurface,
    READINESS_PATH_ENV,
    READINESS_TOKEN_ENV,
    publish_application_readiness_receipt,
)
from sugarsubstitute_shared.application_supervisor_client import (
    ApplicationSupervisorClient,
)
from sugarsubstitute_shared.crash_reporting.protocol import CrashRunContext
from sugarsubstitute_shared.crash_reporting.runtime import install_process_crash_runtime
from .native_terminal_event import TerminalEvent


def main() -> None:
    """Install real Crashpad and wait for the post-readiness terminal action."""
    context = CrashRunContext.from_environment()
    assert context is not None
    install_process_crash_runtime(
        context=context,
        application_version="0.27.1",
        launch_arguments=sys.argv,
        install_root=Path(os.environ["PROOF_INSTALL_ROOT"]),
    )
    event = TerminalEvent(os.environ["PROOF_TERMINAL_EVENT"], create=False)
    publish_application_readiness_receipt(
        receipt_path=Path(os.environ[READINESS_PATH_ENV]),
        receipt=ApplicationReadinessReceipt(
            pid=os.getpid(),
            token=os.environ[READINESS_TOKEN_ENV],
            surface=ApplicationReadinessSurface.MAIN_SHELL,
            parent_pid=os.getppid(),
        ),
    )
    try:
        event.wait(timeout=30)
    finally:
        event.close()
    if os.environ["PROOF_EXIT_MODE"] == "restart":
        client = ApplicationSupervisorClient.connect_from_environment(dict(os.environ))
        assert client is not None
        try:
            assert client.request_restart()
        finally:
            client.close()
    os._exit(73)


if __name__ == "__main__":
    main()
