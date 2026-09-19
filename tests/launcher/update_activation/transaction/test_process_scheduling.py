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
from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys
from typing import cast

import pytest

import sugarsubstitute_shared.launcher_update.process as update_process_module
from sugarsubstitute_shared.process_identity import (
    ProcessIdentityError,
    capture_process_identity,
)
from sugarsubstitute_shared.launcher_update.request import LauncherUpdateRequest
from sugarsubstitute_shared.launcher_update.transaction import LauncherUpdateTransaction

from sugarsubstitute_shared.launcher_update.bundle_selection import (
    LauncherBundleSelection,
)
from sugarsubstitute_shared.launcher_update.targets import WINDOWS_X64_BUNDLE

from .support import (
    _write_scheduled_update_request,
    _write_installed_layout,
    _write_bundle_tree,
)


def _write_delegating_contract(root: Path) -> None:
    """Mark one synthetic Windows baseline as permanent updater ownership."""

    path = root / "launcher-bin" / "launcher_assets" / "launcher-contract.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"schema_version":1,"delegation_protocol":1}', encoding="utf-8")


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

    def fake_native_launch(*args: object, **kwargs: object) -> int:
        """Capture the same environment at the Windows creation boundary."""
        return fake_popen(*args, env=kwargs["environment"]).pid

    monkeypatch.setattr(
        "sugarsubstitute_shared.windows_independent_process.start_independent_windows_process",
        fake_native_launch,
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
        wait_pid=os.getpid(),
    )

    assert LauncherUpdateRequest.load(
        request_path
    ).wait_identity == capture_process_identity(os.getpid())
    assert str(meipass) not in observed_environment["PATH"].split(os.pathsep)
    assert observed_environment["DYLD_LIBRARY_PATH"] == str(system_library)
    assert "DYLD_LIBRARY_PATH_ORIG" not in observed_environment
    assert "_PYI_APPLICATION_HOME_DIR" not in observed_environment
    assert observed_environment["QUALIFICATION_TOKEN"] == "preserved"
    assert dll_search_path_events == ["enter", "exit"]


def test_delegating_baseline_runs_its_own_update_helper(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Never execute current-protocol updater logic from mutable application code."""

    root = _write_installed_layout(tmp_path / "installation")
    _write_delegating_contract(root)
    staged = root / "launcher" / "updates" / "staged"
    _write_bundle_tree(staged, marker="candidate")
    request_path = root / "launcher" / "updates" / "pending.json"
    LauncherUpdateRequest(
        install_root=root,
        version="0.24.0",
        target_key="windows_x64",
        staged_bundle_dir=staged,
        relaunch=False,
    ).save(request_path)
    commands: list[list[str]] = []

    def start(
        command: list[str],
        *,
        cwd: Path,
        environment: dict[str, str],
        output_fd: int,
    ) -> int:
        """Capture the durable helper command without starting a process."""

        del cwd, output_fd
        commands.append(command)
        assert "PYTHONPATH" not in environment
        return 42

    monkeypatch.setattr(update_process_module, "_start_independent", start)

    helper_pid = update_process_module.schedule_launcher_update(
        request_path=request_path,
        runtime_python=root / "runtime" / "python.exe",
        app_dir=root / "app",
        relaunch=True,
        wait_pid=None,
    )

    assert helper_pid == 42
    assert commands == [
        [
            str((root / "SugarSubstitute.exe").resolve()),
            "--apply-launcher-update",
            str(request_path.resolve()),
        ]
    ]


@pytest.mark.platforms("windows")
@pytest.mark.parametrize("incarnation", ["outgoing", "reused"])
def test_windows_update_wait_tracks_the_original_process(
    tmp_path: Path, incarnation: str
) -> None:
    """Wait for an exact caller without waiting for or stopping a reused PID."""
    root = _write_installed_layout(tmp_path / "installation")
    staged = root / "launcher" / "updates" / "staged"
    _write_bundle_tree(staged, marker="candidate")
    path = root / "launcher" / "updates" / "pending.json"
    with subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", "import sys; sys.stdin.buffer.read(1)"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    ) as process:
        try:
            identity = capture_process_identity(process.pid)
            if incarnation == "reused":
                identity = replace(identity, created_at=identity.created_at - 1.0)
            request = LauncherUpdateRequest(
                install_root=root,
                version="new",
                target_key="windows_x64",
                staged_bundle_dir=staged,
                relaunch=False,
            ).with_process_behavior(relaunch=False, wait_identity=identity)
            request.save(path)
            transaction = LauncherUpdateTransaction(wait_timeout_seconds=0)
            if incarnation == "outgoing":
                with pytest.raises(ProcessIdentityError):
                    transaction.apply(request_path=path)
                assert path.exists()
                assert (
                    LauncherBundleSelection(root, WINDOWS_X64_BUNDLE).resolve().root
                    == root
                )
            else:
                transaction.apply(request_path=path)
                assert not path.exists()
                selected = LauncherBundleSelection(root, WINDOWS_X64_BUNDLE).resolve()
                assert selected.version == "new"
            assert process.poll() is None
            assert (root / "SugarSubstitute.exe").read_text(
                encoding="utf-8"
            ) == "old launcher"
        finally:
            process.terminate()
            try:
                process.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5.0)


@pytest.mark.parametrize("boundary", ["schedule", "relaunch"])
def test_update_process_does_not_inherit_retired_crash_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, boundary: str
) -> None:
    """Updater helpers and new launchers must start outside the outgoing crash session."""
    from sugarsubstitute_shared.crash_reporting.protocol import (
        CrashRunContext,
        CRASH_RUN_TOKEN_ENV,
    )

    context = CrashRunContext.create(tmp_path / "diagnostics")
    for key, value in context.environment({}).items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv(CRASH_RUN_TOKEN_ENV)
    monkeypatch.setenv("QUALIFICATION_TOKEN", "preserved")
    environments: list[dict[str, str]] = []

    class Process:
        """Represent only the spawned process identifier at the external boundary."""

        pid = 42

    def launch(*args: object, **kwargs: object) -> Process:
        """Capture the exact child contract without launching an uncontrolled application."""
        environment = cast(dict[str, str] | None, kwargs.get("env"))
        environments.append(dict(os.environ if environment is None else environment))
        return Process()

    monkeypatch.setattr(
        "sugarsubstitute_shared.launcher_update.process.subprocess.Popen", launch
    )

    def native_launch(*args: object, **kwargs: object) -> int:
        """Observe sanitized state at the Windows native process boundary."""
        return launch(*args, env=kwargs["environment"]).pid

    monkeypatch.setattr(
        "sugarsubstitute_shared.windows_independent_process.start_independent_windows_process",
        native_launch,
    )
    if boundary == "schedule":
        request_path, runtime_python, app_dir = _write_scheduled_update_request(
            tmp_path
        )
        update_process_module.schedule_launcher_update(
            request_path=request_path,
            runtime_python=runtime_python,
            app_dir=app_dir,
            relaunch=True,
            wait_pid=None,
        )
    else:
        update_process_module.relaunch_updated_launcher(
            tmp_path / "SugarSubstitute.exe"
        )
    assert len(environments) == 1
    assert CrashRunContext.from_environment(environments[0]) is None
    assert environments[0]["QUALIFICATION_TOKEN"] == "preserved"
