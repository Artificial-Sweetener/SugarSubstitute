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

"""Require update handoffs to survive independently of their parent job."""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import sys

import pytest

from sugarsubstitute_shared.windows_process_family import WindowsProcessFamily
from .support import _write_scheduled_update_request

pytestmark = pytest.mark.platforms("windows")


@pytest.mark.parametrize("allow_handoff", [False, True])
def test_updater_requires_actual_native_detachment(
    tmp_path: Path, allow_handoff: bool
) -> None:
    """Reject an owned child or prove a handoff survives the owner exit.

    An outer runner job may retain the child after it escapes the application's
    immediate family. The host policy is acceptable when the handoff survives
    the application owner's verified native exit.
    """
    _request, _python, app = _write_scheduled_update_request(tmp_path)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(10)
        package = app / "sugarsubstitute_shared"
        updates = package / "launcher_update"
        updates.mkdir(parents=True)
        (package / "__init__.py").touch()
        (updates / "__init__.py").touch()
        marker = tmp_path / "helper-executed"
        lease_attempt = tmp_path / "lease-inheritance-attempt.json"
        (updates / "helper.py").write_text(
            "import ctypes\nfrom ctypes import wintypes\n"
            "import json\nfrom pathlib import Path\nimport socket\n"
            f"root = Path({str(tmp_path)!r})\n"
            "handle = int((root / 'app-lease-handle.txt').read_text(encoding='utf-8'))\n"
            "written = wintypes.DWORD()\n"
            "payload = ctypes.create_string_buffer(b'leaked')\n"
            "kernel = ctypes.WinDLL('kernel32', use_last_error=True)\n"
            "kernel.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]\n"
            "kernel.WriteFile.restype = wintypes.BOOL\n"
            "leaked = bool(kernel.WriteFile(handle, payload, 6, ctypes.byref(written), None))\n"
            "(root / 'lease-inheritance-attempt.json').write_text(json.dumps({'leaked': leaked, 'written': written.value}), encoding='utf-8')\n"
            f"Path({str(marker)!r}).touch()\n"
            f"with socket.create_connection(('127.0.0.1', {listener.getsockname()[1]}), timeout=10) as s:\n"
            "    s.settimeout(10)\n    s.sendall(b'ready')\n    s.recv(1)\n",
            encoding="utf-8",
        )
        with (tmp_path / "owner.log").open("w", encoding="utf-8") as output:
            family = WindowsProcessFamily.start(
                [
                    sys.executable,
                    "-m",
                    "tests.launcher.update_activation.transaction.detachment_fixture",
                    str(tmp_path),
                ],
                environment=os.environ,
                cwd=Path.cwd(),
                output_fd=output.fileno(),
                allow_breakaway=allow_handoff,
            )
            try:
                assert family.wait(timeout=15) == 0
                result = json.loads((tmp_path / "admission.json").read_text())
                assert result["admitted"] is allow_handoff, result
                if allow_handoff:
                    connection, _address = listener.accept()
                    with connection:
                        connection.settimeout(10)
                        assert connection.recv(5) == b"ready"
                        assert json.loads(
                            lease_attempt.read_text(encoding="utf-8")
                        ) == {
                            "leaked": False,
                            "written": 0,
                        }
                        assert (tmp_path / "app-lease.lock").read_bytes() == b""
                        connection.sendall(b"x")
                        assert connection.recv(1) == b""
                else:
                    assert "process family" in result["reason"].lower(), result
                    assert not marker.exists(), (
                        "Rejected helper executed before admission"
                    )
                    assert not lease_attempt.exists()
            finally:
                if family.poll() is None:
                    family.kill()
                family.wait(timeout=10)
