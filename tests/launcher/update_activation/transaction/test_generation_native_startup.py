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

"""Prove failed generation startup retires its real native process family."""

from collections.abc import Mapping, Sequence
import json
import os
from pathlib import Path
import socket
import sys

import psutil  # type: ignore[import-untyped]
import pytest

from launcher.sugarsubstitute_launcher.application_readiness_supervisor import (
    ApplicationReadinessSupervisor,
)
from launcher.sugarsubstitute_launcher.generation_supervision import (
    GenerationStartupError,
    LauncherGenerationSupervisor,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process_execution import (
    ChildProcess,
    spawn_supervised_process,
)
from tests.launcher.application_readiness.process_family_fixture import command

pytestmark = pytest.mark.platforms("windows")


@pytest.mark.parametrize("cancel", [False, True])
def test_generation_startup_retires_unresponsive_family(
    tmp_path: Path, cancel: bool
) -> None:
    """Timeout falls back; deliberate Close exits; neither leaves descendants."""
    family: list[psutil.Process] = []
    owned: list[ChildProcess] = []
    cancel_requested = False
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(4)
        listener.settimeout(10)

        def start(
            arguments: Sequence[str], environment: Mapping[str, str]
        ) -> tuple[ChildProcess, Path]:
            """Start the production family and observe both actual fixture members."""
            nonlocal cancel_requested
            process, log = spawn_supervised_process(
                arguments,
                environment=environment,
                startup_log_path=tmp_path / "generation.log",
                allow_handoff=True,
            )
            owned.append(process)
            for _ in range(2):
                connection, _address = listener.accept()
                with connection:
                    connection.settimeout(5)
                    with connection.makefile("rb") as stream:
                        record = json.loads(stream.read())
                family.append(psutil.Process(record["pid"]))
            family.extend(psutil.Process(process.pid).children(recursive=True))
            family.append(psutil.Process(process.pid))
            cancel_requested = cancel
            return process, log

        ticks = iter(float(index) for index in range(20))
        readiness = ApplicationReadinessSupervisor(
            timeout_seconds=2,
            process_starter=start,
            monotonic=lambda: next(ticks),
            wait=lambda _seconds: None,
            cancellation_requested=lambda: cancel_requested,
        )
        supervisor = LauncherGenerationSupervisor(readiness=readiness)
        try:
            arguments = command("family", listener.getsockname()[1], tmp_path)
            if cancel:
                assert (
                    supervisor.supervise(
                        layout=InstallLayout.from_root(tmp_path),
                        command=arguments,
                        environment=os.environ,
                    )
                    == 0
                )
            else:
                with pytest.raises(GenerationStartupError):
                    supervisor.supervise(
                        layout=InstallLayout.from_root(tmp_path),
                        command=arguments,
                        environment=os.environ,
                    )
            _gone, alive = psutil.wait_procs(family, timeout=5)
            assert not alive, "Generation startup required manual process cleanup"
        finally:
            for process in owned:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)


def test_nested_generation_attests_readiness_through_real_process_hops(
    tmp_path: Path,
) -> None:
    """Accept a verified inner surface through the actual launched generation identity."""
    leaf = (
        "import os; from pathlib import Path; from threading import Event; "
        "from sugarsubstitute_shared.application_readiness import *; "
        "publish_application_readiness_receipt(receipt_path=Path(os.environ[READINESS_PATH_ENV]), "
        "receipt=ApplicationReadinessReceipt(pid=os.getpid(),parent_pid=os.getppid(),"
        "token=os.environ[READINESS_TOKEN_ENV],surface=ApplicationReadinessSurface.MAIN_SHELL)); "
        "Event().wait(60)"
    )
    generation = (
        "import os,sys; from pathlib import Path; from threading import Event; "
        "from launcher.sugarsubstitute_launcher.application_readiness_supervisor import ApplicationReadinessSupervisor; "
        "from launcher.sugarsubstitute_launcher.install_layout import InstallLayout; "
        f"child=ApplicationReadinessSupervisor(timeout_seconds=10).launch_until_ready(layout=InstallLayout.from_root(Path(sys.argv[1])),command=[sys.executable,'-c',{leaf!r}],environment=os.environ); "
        "Event().wait(60)"
    )
    readiness = ApplicationReadinessSupervisor(timeout_seconds=15)
    process = readiness.launch_until_ready(
        layout=InstallLayout.from_root(tmp_path),
        command=[sys.executable, "-c", generation, str(tmp_path)],
        environment=os.environ,
    )
    family = [
        psutil.Process(process.pid),
        *psutil.Process(process.pid).children(recursive=True),
    ]
    try:
        assert len(family) >= 2
    finally:
        process.kill()
        process.wait(timeout=5)
    _gone, alive = psutil.wait_procs(family, timeout=5)
    assert not alive
