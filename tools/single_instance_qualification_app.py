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

"""Host the production instance owners behind packaged-launcher qualification."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

from PySide6.QtCore import QCoreApplication, QTimer

from substitute.app.bootstrap.application_instance_control import (
    bind_application_instance_shutdown_request,
    start_application_instance_control,
    stop_application_instance_control,
)
from sugarsubstitute_shared.application_launch_guard import (
    ApplicationLaunchGuard,
    application_launch_install_root,
    clear_inherited_application_launch_token,
    inherited_application_launch_token,
)
from sugarsubstitute_shared.launch_splash import (
    SocketSplashSessionClient,
    splash_session_from_args,
)


APPLICATION_CLAIM_DELAY_ENV = (
    "SUGAR_SUBSTITUTE_QUALIFICATION_APPLICATION_CLAIM_DELAY_SECONDS"
)


def main(argv: list[str] | None = None) -> int:
    """Claim production ownership and remain available for graceful shutdown."""

    arguments = sys.argv if argv is None else argv
    install_root = application_launch_install_root(arguments, app_root=Path.cwd())
    _delay_application_claim()
    inherited_token = inherited_application_launch_token()
    guard = ApplicationLaunchGuard.enter(
        install_root,
        inherited_token=inherited_token,
    )
    clear_inherited_application_launch_token()
    if guard is None:
        return 17

    application = QCoreApplication(arguments)
    marker_path = install_root / "user" / "qualification-app.json"
    owner_marker_path = (
        install_root / "user" / "qualification-owners" / f"{os.getpid()}.json"
    )
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    owner_marker_path.parent.mkdir(parents=True, exist_ok=True)

    def request_shutdown(_reason: object | None) -> None:
        """Route local control through the application's event loop."""

        application.quit()

    start_application_instance_control(install_root)
    bind_application_instance_shutdown_request(request_shutdown)
    marker_path.write_text(
        json.dumps({"pid": os.getpid()}, sort_keys=True),
        encoding="utf-8",
    )
    owner_marker_path.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "parent_pid": os.getppid(),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    splash_spec = splash_session_from_args(arguments)
    if splash_spec is not None:
        adoption_path = (
            install_root
            / "user"
            / "qualification-splash-adoptions"
            / f"{os.getpid()}.json"
        )
        adoption_path.parent.mkdir(parents=True, exist_ok=True)
        adoption_path.write_text(
            json.dumps(
                {
                    "app_pid": os.getpid(),
                    "splash_host_pid": splash_spec.host_pid,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        splash_client = SocketSplashSessionClient(splash_spec)
        QTimer.singleShot(2_500, splash_client.close)
    QTimer.singleShot(120_000, application.quit)
    try:
        return application.exec()
    finally:
        stop_application_instance_control()
        try:
            marker_payload = json.loads(marker_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            marker_payload = None
        if (
            isinstance(marker_payload, dict)
            and marker_payload.get("pid") == os.getpid()
        ):
            marker_path.unlink(missing_ok=True)
        owner_marker_path.unlink(missing_ok=True)
        guard.release()


def _delay_application_claim() -> None:
    """Apply the explicit qualification-only launch-race delay."""

    delay = float(os.environ.pop(APPLICATION_CLAIM_DELAY_ENV, "0"))
    if delay > 0:
        time.sleep(delay)


if __name__ == "__main__":
    raise SystemExit(main())
