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

"""Host a real supervisor-connected child for packaged instance qualification."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QWidget

from substitute.app.bootstrap.application_readiness import (
    schedule_main_shell_readiness_receipt,
)
from substitute.app.bootstrap.surface_presentation import run_after_surface_paint
from substitute.app.bootstrap.application_instance_control import (
    start_application_instance_control,
    stop_application_instance_control,
)
from sugarsubstitute_shared.application_launch_context import (
    application_launch_install_root,
)
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation
from sugarsubstitute_shared.crash_reporting.protocol import (
    CleanExitOutcome,
    CrashRunContext,
)
from sugarsubstitute_shared.launch_splash import (
    SocketSplashSessionClient,
    splash_session_from_args,
)


APPLICATION_REGISTRATION_DELAY_ENV = (
    "SUGAR_SUBSTITUTE_QUALIFICATION_APPLICATION_REGISTRATION_DELAY_SECONDS"
)
APPLICATION_PREREGISTRATION_MARKER_NAME = "qualification-application-preregister.json"
APPLICATION_RESTART_AFTER_INVOCATIONS_ENV = (
    "SUGAR_SUBSTITUTE_QUALIFICATION_RESTART_AFTER_INVOCATIONS"
)
APPLICATION_INITIAL_WINDOW_STATE_ENV = (
    "SUGAR_SUBSTITUTE_QUALIFICATION_INITIAL_WINDOW_STATE"
)


def main(argv: list[str] | None = None) -> int:
    """Register with the elected supervisor and remain alive for qualification."""

    arguments = sys.argv if argv is None else argv
    install_root = application_launch_install_root(arguments, app_root=Path.cwd())
    _delay_application_registration(install_root)
    application = QApplication(arguments)
    received_invocations: list[ApplicationInvocation] = []
    restart_after_invocations = int(
        os.environ.pop(APPLICATION_RESTART_AFTER_INVOCATIONS_ENV, "0")
    )
    crash_context = CrashRunContext.from_environment()
    requested_restart = False
    control = None

    def record_invocation(invocation: ApplicationInvocation) -> None:
        """Persist deterministic evidence for every delivered secondary launch."""

        nonlocal requested_restart
        received_invocations.append(invocation)
        invocation_evidence_path(install_root).write_text(
            json.dumps(
                {
                    "count": len(received_invocations),
                    "invocations": [
                        {
                            "arguments": list(item.arguments),
                            "working_directory": item.working_directory,
                        }
                        for item in received_invocations
                    ],
                    "surface": _surface_evidence(window),
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        if (
            restart_after_invocations > 0
            and len(received_invocations) == restart_after_invocations
            and control is not None
        ):
            restart_count = len(received_invocations)

            def request_restart_after_presentation() -> None:
                """Restart only after the triggering invocation's surface paints."""

                nonlocal requested_restart
                assert control is not None
                accepted = control.request_restart()
                restart_evidence_path(install_root).write_text(
                    json.dumps(
                        {
                            "accepted": accepted,
                            "invocation_count": restart_count,
                            "pid": os.getpid(),
                        },
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )
                if accepted:
                    if crash_context is not None:
                        crash_context.write_exit_intent(
                            CleanExitOutcome.RESTART,
                            process_id=os.getpid(),
                        )
                    requested_restart = True
                    application.quit()

            run_after_surface_paint(window, request_restart_after_presentation)
            window.update()

    evidence_path = invocation_evidence_path(install_root)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text('{"count": 0, "invocations": []}', encoding="utf-8")
    control = start_application_instance_control(
        invocation_observer=record_invocation,
    )
    if control is None:
        return 17
    window = QWidget()
    window.setWindowTitle("SugarSubstitute instance qualification")
    window.resize(640, 480)
    _show_initial_window_state(window)
    schedule_main_shell_readiness_receipt(window)
    _schedule_splash_close_after_surface_paint(arguments, install_root, window)
    marker_path = install_root / "user" / "qualification-app.json"
    owner_marker_path = (
        install_root / "user" / "qualification-owners" / f"{os.getpid()}.json"
    )
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    owner_marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(
        json.dumps({"pid": os.getpid()}, sort_keys=True),
        encoding="utf-8",
    )
    owner_marker_path.write_text(
        json.dumps({"pid": os.getpid(), "parent_pid": os.getppid()}, sort_keys=True),
        encoding="utf-8",
    )
    QTimer.singleShot(120_000, application.quit)
    try:
        return application.exec()
    finally:
        stop_application_instance_control()
        _remove_owned_marker(marker_path)
        owner_marker_path.unlink(missing_ok=True)
        if requested_restart and crash_context is not None:
            crash_context.write_exit_receipt(
                CleanExitOutcome.RESTART,
                process_id=os.getpid(),
            )


def _schedule_splash_close_after_surface_paint(
    arguments: list[str],
    install_root: Path,
    window: QWidget,
) -> None:
    """Adopt and close the launcher splash after the replacement surface paints."""

    splash_spec = splash_session_from_args(arguments)
    if splash_spec is None:
        return
    adoption_path = (
        install_root / "user" / "qualification-splash-adoptions" / f"{os.getpid()}.json"
    )
    adoption_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "app_pid": os.getpid(),
        "close_acknowledged": None,
        "splash_host_pid": splash_spec.host_pid,
    }
    _write_splash_adoption(adoption_path, payload)
    splash_client = SocketSplashSessionClient(splash_spec)

    def close_adopted_splash() -> None:
        """Record whether the host applied the production close message."""

        payload["close_acknowledged"] = splash_client.close()
        _write_splash_adoption(adoption_path, payload)

    run_after_surface_paint(window, close_adopted_splash)


def _write_splash_adoption(path: Path, payload: dict[str, object]) -> None:
    """Atomically publish splash adoption and close acknowledgement evidence."""

    temporary_path = path.with_suffix(f".{os.getpid()}.tmp")
    temporary_path.write_text(
        json.dumps(payload, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temporary_path, path)


def _show_initial_window_state(window: QWidget) -> None:
    """Expose one deterministic presentation state for process qualification."""

    state = os.environ.pop(APPLICATION_INITIAL_WINDOW_STATE_ENV, "normal")
    if state == "normal":
        window.show()
        return
    if state == "hidden":
        window.show()
        window.hide()
        return
    if state == "minimized":
        window.showMinimized()
        return
    if state == "offscreen":
        window.move(100_000, 100_000)
        window.show()
        return
    raise ValueError(f"Unsupported qualification window state: {state}")


def _surface_evidence(window: QWidget) -> dict[str, object]:
    """Describe whether the activation target is visible and screen-accessible."""

    frame = window.frameGeometry()
    return {
        "accessible": any(
            frame.intersects(screen.availableGeometry())
            for screen in QGuiApplication.screens()
        ),
        "minimized": window.isMinimized(),
        "visible": window.isVisible(),
        "x": frame.x(),
        "y": frame.y(),
    }


def _delay_application_registration(install_root: Path) -> None:
    """Expose an explicit qualification window after supervisor election."""

    delay = float(os.environ.pop(APPLICATION_REGISTRATION_DELAY_ENV, "0"))
    if delay <= 0:
        return
    marker_path = application_preregistration_marker_path(install_root)
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(
        json.dumps({"pid": os.getpid()}, sort_keys=True),
        encoding="utf-8",
    )
    try:
        time.sleep(delay)
    finally:
        marker_path.unlink(missing_ok=True)


def application_preregistration_marker_path(install_root: Path) -> Path:
    """Return the disposable marker for the delayed child registration phase."""

    return install_root / "user" / APPLICATION_PREREGISTRATION_MARKER_NAME


def invocation_evidence_path(install_root: Path) -> Path:
    """Return the disposable forwarded-invocation evidence path."""

    return install_root / "user" / "qualification-invocations.json"


def restart_evidence_path(install_root: Path) -> Path:
    """Return the disposable supervisor-restart evidence path."""

    return install_root / "user" / "qualification-restart.json"


def _remove_owned_marker(marker_path: Path) -> None:
    """Remove the shared PID marker only when this child still owns it."""

    try:
        marker_payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return
    if isinstance(marker_payload, dict) and marker_payload.get("pid") == os.getpid():
        marker_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
