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

"""Exercise the private worker entrypoint without opening any desktop surface."""

from __future__ import annotations

import json
from pathlib import Path
import secrets
import socket
import sys

import pytest

from launcher.sugarsubstitute_launcher.process_execution import spawn_supervised_process
from launcher.sugarsubstitute_launcher.repair_execution_child import (
    run_repair_execution_invocation,
)
from launcher.sugarsubstitute_launcher.repair_execution_protocol import (
    REPAIR_EXECUTION_ENDPOINT_ENV,
    RepairFrameDecoder,
)
from sugarsubstitute_shared.crash_reporting.protocol import (
    without_crash_supervision_environment,
)


def test_worker_invocation_requires_parent_capability(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Reject direct worker requests before loading or mutating an installation."""
    monkeypatch.delenv(REPAIR_EXECUTION_ENDPOINT_ENV, raising=False)
    with pytest.raises(ValueError, match="supervisor capability"):
        run_repair_execution_invocation(
            (f"--repair-worker-request={tmp_path / 'missing.json'}",)
        )
    assert list(tmp_path.iterdir()) == []
    assert run_repair_execution_invocation(("--ordinary-launch",)) is None


@pytest.mark.platforms("windows")
def test_native_execution_child_reports_failure_and_exits_without_ui(
    tmp_path: Path,
) -> None:
    """Run the production bootstrap in a contained child against only a missing fixture."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(15)
        token = secrets.token_hex(32)
        environment = without_crash_supervision_environment()
        environment[REPAIR_EXECUTION_ENDPOINT_ENV] = json.dumps(
            {"port": listener.getsockname()[1], "token": token}
        )
        process, _log = spawn_supervised_process(
            (
                sys.executable,
                "-m",
                "launcher.sugarsubstitute_launcher",
                f"--repair-worker-request={tmp_path / 'missing.json'}",
            ),
            environment=environment,
            startup_log_path=tmp_path / "worker.log",
        )
        try:
            connection, _address = listener.accept()
            messages: list[dict[str, object]] = []
            decoder = RepairFrameDecoder()
            with connection:
                connection.settimeout(10)
                while data := connection.recv(4096):
                    messages.extend(decoder.feed(data))
                decoder.finish()
            assert process.wait(timeout=10) == 1
            assert [message["kind"] for message in messages] == ["ready", "failed"]
            assert messages[0]["token"] == token
            assert isinstance(messages[0]["pid"], int)
            assert "missing.json" in str(messages[1]["details"])
            assert not (tmp_path / "missing.json").exists()
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
