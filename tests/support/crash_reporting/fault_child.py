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

"""Trigger destructive crash modes inside a dedicated supervised process."""

from __future__ import annotations

import gc
import os
from pathlib import Path
import sys
import threading

from sugarsubstitute_shared.crash_reporting.native import CrashpadNativeClient
from sugarsubstitute_shared.crash_reporting.protocol import (
    CleanExitOutcome,
    CrashRunContext,
)
from sugarsubstitute_shared.crash_reporting.runtime import (
    ProcessCrashRuntime,
    install_process_crash_runtime,
    report_active_execution_exception,
)


class _NoopNativeClient(CrashpadNativeClient):
    """Keep Python fault qualification independent of native Crashpad coverage."""

    def start(
        self,
        *,
        context: CrashRunContext,
        application_version: str,
        attachment_path: Path,
    ) -> None:
        """Accept registration while the separate native probe covers Crashpad."""

        del context, application_version, attachment_path


def _runtime() -> ProcessCrashRuntime:
    """Install the real Python crash runtime with only native loading replaced."""

    context = CrashRunContext.from_environment()
    if context is None:
        raise RuntimeError("Fault child requires a supervisor crash contract.")
    return install_process_crash_runtime(
        context=context,
        application_version="qualification",
        launch_arguments=sys.argv,
        install_root=Path.cwd(),
        native_client=_NoopNativeClient(),
    )


def _raise_main() -> None:
    """Raise through the interpreter main boundary."""

    raise RuntimeError("qualified main-thread failure")


def _raise_thread() -> None:
    """Raise through Python's threading exception hook."""

    thread = threading.Thread(
        target=lambda: _raise_main(),
        name="qualification-thread",
    )
    thread.start()
    thread.join(timeout=10)
    if thread.is_alive():
        raise RuntimeError("Qualification thread did not terminate within ten seconds.")


def _raise_unraisable() -> None:
    """Raise from finalization where Python cannot propagate normally."""

    class BrokenFinalizer:
        """Provide one deliberately broken finalizer."""

        def __del__(self) -> None:
            """Raise the qualification error."""

            raise RuntimeError("qualified unraisable failure")

    value = BrokenFinalizer()
    del value
    gc.collect()


def _raise_qt_event() -> None:
    """Raise while the crash-aware QApplication dispatches a posted event."""

    from PySide6.QtCore import QCoreApplication, QEvent, QObject
    from substitute.app.bootstrap.crash_aware_application import CrashAwareApplication

    class BrokenReceiver(QObject):
        """Raise from the real QObject event dispatch path."""

        def event(self, event: QEvent) -> bool:
            """Reject the posted event destructively."""

            del event
            raise RuntimeError("qualified Qt event failure")

    application = CrashAwareApplication(["crash-qualification"])
    receiver = BrokenReceiver()
    QCoreApplication.postEvent(receiver, QEvent(QEvent.Type.User))
    application.exec()


def _raise_qt_fatal() -> None:
    """Emit a real Qt fatal message after installing its authoritative hook."""

    from PySide6.QtCore import qFatal
    from substitute.app.bootstrap.qt_message_trace import (
        install_qt_message_trace_handler,
    )

    install_qt_message_trace_handler()
    qFatal("qualified Qt fatal failure")


def main() -> int:
    """Run exactly one requested destructive boundary."""

    mode = sys.argv[1]
    if mode == "startup":
        raise RuntimeError("qualified pre-runtime startup failure")
    runtime = _runtime()
    if mode == "python_main":
        _raise_main()
    if mode == "python_thread":
        _raise_thread()
    if mode == "unraisable":
        _raise_unraisable()
    if mode == "qt_event":
        _raise_qt_event()
    if mode == "qt_fatal":
        _raise_qt_fatal()
    if mode == "execution":
        report_active_execution_exception(RuntimeError("qualified execution failure"))
    if mode == "privacy":
        raise RuntimeError(
            f"api_key=qualification-secret path={Path.cwd()} password=private-value"
        )
    if mode == "abort":
        os.abort()
    if mode == "hard_exit":
        os._exit(0)
    if mode == "clean":
        runtime.request_clean_exit(CleanExitOutcome.CLOSED)
        return 0
    raise ValueError(f"Unknown fault mode: {mode}")


if __name__ == "__main__":
    raise SystemExit(main())
