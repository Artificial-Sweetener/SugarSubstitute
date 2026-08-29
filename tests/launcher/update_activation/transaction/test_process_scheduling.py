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

"""Verify updater helper environment and native process lifecycle behavior."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys
from typing import cast

import pytest

import sugarsubstitute_shared.launcher_update.process as update_process_module
import sugarsubstitute_shared.launcher_update.transaction as transaction_module

from .support import _write_scheduled_update_request


def test_launcher_update_helper_does_not_inherit_frozen_parent_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The runtime-Python updater helper must not inherit PyInstaller libraries."""

    meipass = tmp_path / "_MEI-update"
    bundled_library = meipass / "libpython.dylib"
    system_library = tmp_path / "system-library"
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(
        "sugarsubstitute_shared.subprocess_environment.os.environ",
        {
            "PATH": f"{meipass}{os.pathsep}{tmp_path}",
            "DYLD_LIBRARY_PATH": str(bundled_library),
            "DYLD_LIBRARY_PATH_ORIG": str(system_library),
            "_PYI_APPLICATION_HOME_DIR": str(meipass),
            "QUALIFICATION_TOKEN": "preserved",
        },
    )
    observed_environment: dict[str, str] = {}
    dll_search_path_events: list[str] = []

    class _Process:
        """Represent the scheduled updater helper."""

        pid = 42

    def fake_popen(*_args: object, **kwargs: object) -> _Process:
        """Capture the environment passed across the helper boundary."""

        assert dll_search_path_events == ["enter"]
        observed_environment.update(cast(dict[str, str], kwargs["env"]))
        return _Process()

    @contextmanager
    def clean_dll_search_path() -> Iterator[None]:
        """Record that native DLL sanitization encloses helper creation."""

        dll_search_path_events.append("enter")
        try:
            yield
        finally:
            dll_search_path_events.append("exit")

    monkeypatch.setattr(
        "sugarsubstitute_shared.launcher_update.process.subprocess.Popen",
        fake_popen,
    )
    monkeypatch.setattr(
        update_process_module,
        "standard_child_process_dll_search_path",
        clean_dll_search_path,
        raising=False,
    )
    request_path, runtime_python, app_dir = _write_scheduled_update_request(tmp_path)

    update_process_module.schedule_launcher_update(
        request_path=request_path,
        runtime_python=runtime_python,
        app_dir=app_dir,
        relaunch=True,
        wait_pid=123,
    )

    assert str(meipass) not in observed_environment["PATH"].split(os.pathsep)
    assert observed_environment["DYLD_LIBRARY_PATH"] == str(system_library)
    assert "DYLD_LIBRARY_PATH_ORIG" not in observed_environment
    assert "_PYI_APPLICATION_HOME_DIR" not in observed_environment
    assert observed_environment["QUALIFICATION_TOKEN"] == "preserved"
    assert dll_search_path_events == ["enter", "exit"]


@pytest.mark.platforms("windows")
def test_windows_process_probe_does_not_terminate_waited_process() -> None:
    """Checking a launcher PID on Windows must never signal or terminate it."""

    process = subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", "import time; time.sleep(30)"],
    )
    try:
        assert transaction_module._process_exists(process.pid) is True
        assert process.poll() is None
    finally:
        process.terminate()
        try:
            process.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5.0)
