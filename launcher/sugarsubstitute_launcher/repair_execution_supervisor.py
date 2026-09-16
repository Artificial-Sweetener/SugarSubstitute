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

"""Own a cancellable repair process and require verified exit before completion."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import json
import logging
import secrets
import socket
import subprocess
from threading import Event
import time

from launcher.sugarsubstitute_launcher.application.repair.progress import (
    RepairProgress,
)
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.launcher_ui_process import (
    build_launcher_ui_command,
)
from launcher.sugarsubstitute_launcher.platforms import launcher_target_for_key
from launcher.sugarsubstitute_launcher.process_execution import (
    ChildProcess,
    spawn_supervised_process,
)
from launcher.sugarsubstitute_launcher.repair_execution_protocol import (
    REPAIR_EXECUTION_ENDPOINT_ENV,
    RepairFrameDecoder,
    repair_message_details,
    repair_progress_from_message,
)
from sugarsubstitute_shared.application_instance_protocol import (
    BROKER_ENDPOINT_ENV,
    BROKER_TOKEN_ENV,
)
from sugarsubstitute_shared.application_readiness import (
    READINESS_PATH_ENV,
    READINESS_TOKEN_ENV,
    READINESS_DELEGATION_PATH_ENV,
    READINESS_DELEGATION_TOKEN_ENV,
)
from sugarsubstitute_shared.crash_reporting.protocol import (
    without_crash_supervision_environment,
)
from sugarsubstitute_shared.windows_long_paths import subprocess_path

_LOGGER = logging.getLogger(__name__)


class RepairProcessError(RuntimeError):
    """Report a failed, interrupted or invalid worker execution."""


class RepairExecutionCancelled(RepairProcessError):
    """Report cancellation only after the owned process family has exited."""


def build_repair_execution_command(request: PreparedRepairRequest) -> Sequence[str]:
    """Use the retained bundle so mutation cannot replace the executing runtime."""
    if request.helper_bundle_dir is None:
        raise ValueError("Repair execution requires an independent launcher bundle.")
    bundle = InstallLayout.from_root(
        request.helper_bundle_dir, target=launcher_target_for_key(request.target_key)
    )
    return build_launcher_ui_command(
        bundle, (f"--repair-worker-request={subprocess_path(request.request_path)}",)
    )


class RepairExecutionSupervisor:
    """Keep one attempt's native family and cancellation authority outside its worker."""

    def __init__(
        self,
        *,
        command_builder: Callable[
            [PreparedRepairRequest], Sequence[str]
        ] = build_repair_execution_command,
    ) -> None:
        """Create a single-use attempt whose cancel signal is safe across threads."""
        self._command_builder = command_builder
        self._cancel = Event()
        self._process: ChildProcess | None = None
        self._started = False
        self._safe_to_close = True

    @property
    def safe_to_close(self) -> bool:
        """Expose verified quiescence rather than assuming worker-thread completion."""
        return self._safe_to_close

    def request_cancel(self) -> None:
        """Wake the bounded control loop without running native termination on the UI."""
        self._cancel.set()

    def run(
        self,
        request: PreparedRepairRequest,
        *,
        progress_observer: Callable[[RepairProgress], None],
        output_callback: Callable[[str], None],
    ) -> None:
        """Execute once and release the entire family before reporting any outcome."""
        if self._started:
            raise RuntimeError("A repair execution supervisor cannot be reused.")
        self._started = True
        self._check_cancel()
        command = self._command_builder(request)
        token = secrets.token_hex(32)
        environment = without_crash_supervision_environment()
        for key in (
            BROKER_ENDPOINT_ENV,
            BROKER_TOKEN_ENV,
            READINESS_PATH_ENV,
            READINESS_TOKEN_ENV,
            READINESS_DELEGATION_PATH_ENV,
            READINESS_DELEGATION_TOKEN_ENV,
        ):
            environment.pop(key, None)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(0.1)
            environment[REPAIR_EXECUTION_ENDPOINT_ENV] = json.dumps(
                {"port": listener.getsockname()[1], "token": token}
            )
            process, _log = spawn_supervised_process(
                command,
                environment=environment,
                startup_log_path=request.install_root
                / ".repair"
                / "diagnostics"
                / "repair-execution.log",
            )
            self._process = process
            self._safe_to_close = False
            try:
                try:
                    self._receive(listener, token, progress_observer, output_callback)
                    exit_code = process.wait(timeout=10)
                except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                    raise RepairProcessError(
                        "Repair worker did not complete its control channel and exit."
                    ) from error
                if exit_code != 0:
                    raise RepairProcessError("Repair worker exited unsuccessfully.")
            finally:
                self.stop()

    def stop(self) -> None:
        """Require native exit; an unverified family makes this host disposable."""
        process = self._process
        if process is None or self._safe_to_close:
            return
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        self._safe_to_close = True
        _LOGGER.info(
            "Repair execution family exited",
            extra={"worker_process_id": process.pid},
        )

    def _check_cancel(self) -> None:
        """Honor user intent independently of worker progress or responsiveness."""
        if self._cancel.is_set():
            raise RepairExecutionCancelled("Repair execution was cancelled.")

    def _receive(
        self,
        listener: socket.socket,
        token: str,
        progress: Callable[[RepairProgress], None],
        output: Callable[[str], None],
    ) -> None:
        """Drain bounded frames while continuing to observe cancellation and child exit."""
        assert self._process is not None
        startup_deadline = time.monotonic() + 30
        while True:
            self._check_cancel()
            if time.monotonic() >= startup_deadline:
                raise RepairProcessError(
                    "Repair worker did not establish its control channel."
                )
            try:
                connection, _address = listener.accept()
                break
            except TimeoutError:
                if self._process.poll() is not None:
                    raise RepairProcessError("Repair worker exited before connecting.")
        with connection:
            connection.settimeout(0.1)
            decoder = RepairFrameDecoder()
            authenticated = False
            terminal: dict[str, object] | None = None
            while True:
                self._check_cancel()
                if not authenticated and time.monotonic() >= startup_deadline:
                    raise RepairProcessError(
                        "Repair worker did not authenticate its control channel."
                    )
                try:
                    data = connection.recv(8192)
                except TimeoutError:
                    if self._process.poll() is not None:
                        raise RepairProcessError(
                            "Repair worker exited without completing its control channel."
                        )
                    continue
                if not data:
                    decoder.finish()
                    break
                for message in decoder.feed(data):
                    kind = message.get("kind")
                    if not authenticated:
                        received_token = message.get("token")
                        if (
                            kind != "ready"
                            or not isinstance(received_token, str)
                            or not secrets.compare_digest(received_token, token)
                        ):
                            raise RepairProcessError(
                                "Repair worker control authentication failed."
                            )
                        authenticated = True
                    elif terminal is not None:
                        raise RepairProcessError(
                            "Repair worker sent data after its terminal outcome."
                        )
                    elif kind == "progress":
                        progress(repair_progress_from_message(message))
                    elif kind == "output":
                        output(repair_message_details(message))
                    elif kind in {"succeeded", "failed"}:
                        terminal = message
                    else:
                        raise RepairProcessError(
                            "Repair worker sent an unsupported event."
                        )
                if terminal is not None:
                    decoder.finish()
                    break
            if terminal is None:
                raise RepairProcessError(
                    "Repair worker closed without a terminal outcome."
                )
            if terminal["kind"] == "failed":
                raise RepairProcessError(repair_message_details(terminal))
