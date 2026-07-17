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

"""Exercise real Windows Comfy process discovery, binding, and shutdown."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import time
from uuid import uuid4

import pytest

from substitute.application.onboarding.comfy_environment_service import (
    AttachedPythonRecoveryState,
    ComfyEnvironmentService,
)
from substitute.domain.onboarding import LocalComfyProcess
from substitute.infrastructure.comfy.local_process_gateway import (
    PsutilLocalComfyProcessGateway,
)
from substitute.infrastructure.comfy.workspace_python_discovery import (
    WorkspacePythonGateway,
)


@pytest.mark.skipif(sys.platform != "win32", reason="Uses an E:\\ test root.")
def test_real_comfy_process_can_be_discovered_bound_and_closed() -> None:
    """Capture the exact interpreter from a real process and close it safely."""

    test_root = Path("E:/") / f"SugarSubstitute-Comfy-Process-Test-{uuid4().hex}"
    workspace = test_root / "ComfyUI"
    process: subprocess.Popen[bytes] | None = None
    try:
        for module_name in ("comfy", "torch", "aiohttp"):
            module_root = workspace / module_name
            module_root.mkdir(parents=True)
            (module_root / "__init__.py").write_text("", encoding="utf-8")
        main_path = workspace / "main.py"
        main_path.write_text(
            "import time\nwhile True:\n    time.sleep(0.1)\n",
            encoding="utf-8",
        )
        process = subprocess.Popen(
            [sys.executable, str(main_path)],
            cwd=workspace,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        process_gateway = PsutilLocalComfyProcessGateway()
        service = ComfyEnvironmentService(
            process_gateway=process_gateway,
            python_gateway=WorkspacePythonGateway(),
        )

        observed: tuple[LocalComfyProcess, ...] = ()
        deadline = time.monotonic() + 5.0
        while not observed and time.monotonic() < deadline:
            observed = tuple(
                item for item in process_gateway.scan() if item.pid == process.pid
            )
            if not observed:
                time.sleep(0.05)

        assert len(observed) == 1
        snapshot = service.inspect_attached_recovery(
            workspace=workspace,
            binding=None,
        )
        assert snapshot.state is AttachedPythonRecoveryState.WAITING_FOR_SHUTDOWN
        assert snapshot.binding is not None
        assert snapshot.binding.executable.samefile(Path(sys.executable))

        termination = service.close_processes(observed)
        assert termination.succeeded
        assert process.wait(timeout=5.0) is not None
        process = None

        ready = service.inspect_attached_recovery(
            workspace=workspace,
            binding=snapshot.binding,
        )
        remaining_test_processes = tuple(
            item for item in ready.processes if item.workspace == workspace.resolve()
        )
        assert remaining_test_processes == ()
        if not ready.processes:
            assert ready.state is AttachedPythonRecoveryState.READY
            assert ready.can_continue
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=5.0)
        if test_root.exists():
            shutil.rmtree(test_root)

    assert not test_root.exists()
