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

"""Transactionally replace an installed launcher bundle after it exits."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import ctypes
from ctypes import wintypes

from sugarsubstitute_shared.launcher_update.models import (
    LauncherInstallationRecord,
    LauncherUpdateRequest,
)
from sugarsubstitute_shared.launcher_update.persistence import write_json_atomic
from sugarsubstitute_shared.launcher_update.staging import validate_staged_bundle
from sugarsubstitute_shared.launcher_update.targets import (
    LauncherBundleTarget,
    launcher_bundle_target_for_key,
)


_LOGGER = logging.getLogger(__name__)


class LauncherUpdateTransactionError(RuntimeError):
    """Report an update that could not be promoted or rolled back safely."""


class LauncherUpdateTransaction:
    """Own validated launcher replacement, rollback, recovery, and relaunch."""

    def __init__(
        self,
        *,
        wait_timeout_seconds: float = 120.0,
        retry_interval_seconds: float = 0.1,
    ) -> None:
        """Store bounded process and filesystem retry timing."""

        self._wait_timeout_seconds = wait_timeout_seconds
        self._retry_interval_seconds = retry_interval_seconds

    def apply(self, *, request_path: Path) -> None:
        """Apply one persisted request and relaunch exactly when requested."""

        request = LauncherUpdateRequest.load(request_path)
        target = launcher_bundle_target_for_key(request.target_key)
        install_root = request.install_root.expanduser().resolve()
        _require_descendant(request_path.resolve(), install_root / "launcher")
        staged_dir = request.staged_bundle_dir.expanduser().resolve()
        _require_descendant(staged_dir, install_root / "launcher" / "updates")
        validate_staged_bundle(bundle_dir=staged_dir, target=target)
        self._wait_for_process(request.wait_pid)
        update_root = install_root / "launcher" / "updates"
        backup_root = update_root / "backup"
        journal_path = update_root / "transaction.json"
        self._recover_interrupted_transaction(
            install_root=install_root,
            target=target,
            backup_root=backup_root,
            journal_path=journal_path,
        )
        self._promote_with_retries(
            install_root=install_root,
            target=target,
            staged_dir=staged_dir,
            backup_root=backup_root,
            journal_path=journal_path,
        )
        LauncherInstallationRecord(
            version=request.version,
            target_key=request.target_key,
        ).save(install_root / "launcher" / "installation.json")
        request_path.unlink(missing_ok=True)
        shutil.rmtree(backup_root, ignore_errors=True)
        shutil.rmtree(staged_dir, ignore_errors=True)
        journal_path.unlink(missing_ok=True)
        if request.relaunch:
            _relaunch(install_root / target.executable_relative_path)

    def _wait_for_process(self, pid: int | None) -> None:
        """Wait for the launcher that owns locked bundle files to exit."""

        if pid is None or pid == os.getpid():
            return
        deadline = time.monotonic() + self._wait_timeout_seconds
        while _process_exists(pid):
            if time.monotonic() >= deadline:
                raise LauncherUpdateTransactionError(
                    f"Timed out waiting for launcher process {pid}."
                )
            time.sleep(self._retry_interval_seconds)

    def _promote_with_retries(
        self,
        *,
        install_root: Path,
        target: LauncherBundleTarget,
        staged_dir: Path,
        backup_root: Path,
        journal_path: Path,
    ) -> None:
        """Retry transient file locks without weakening transactional rollback."""

        deadline = time.monotonic() + self._wait_timeout_seconds
        while True:
            try:
                self._promote(
                    install_root=install_root,
                    target=target,
                    staged_dir=staged_dir,
                    backup_root=backup_root,
                    journal_path=journal_path,
                )
                return
            except OSError as error:
                self._rollback(
                    install_root=install_root,
                    target=target,
                    backup_root=backup_root,
                )
                if time.monotonic() >= deadline:
                    raise LauncherUpdateTransactionError(
                        "Launcher files remained locked during replacement."
                    ) from error
                time.sleep(self._retry_interval_seconds)
            except Exception:
                self._rollback(
                    install_root=install_root,
                    target=target,
                    backup_root=backup_root,
                )
                raise

    def _promote(
        self,
        *,
        install_root: Path,
        target: LauncherBundleTarget,
        staged_dir: Path,
        backup_root: Path,
        journal_path: Path,
    ) -> None:
        """Move the old bundle aside, then copy the complete staged bundle."""

        shutil.rmtree(backup_root, ignore_errors=True)
        backup_root.mkdir(parents=True, exist_ok=True)
        write_json_atomic(
            journal_path,
            {"phase": "promoting", "target_key": target.key},
        )
        for relative_path in target.replacement_roots:
            destination = install_root / relative_path
            backup = backup_root / relative_path
            source = staged_dir / relative_path
            if destination.exists():
                backup.parent.mkdir(parents=True, exist_ok=True)
                destination.replace(backup)
            else:
                absence_marker = _absence_marker(backup_root, relative_path)
                absence_marker.parent.mkdir(parents=True, exist_ok=True)
                absence_marker.touch()
            _copy_path(source=source, destination=destination)

    def _recover_interrupted_transaction(
        self,
        *,
        install_root: Path,
        target: LauncherBundleTarget,
        backup_root: Path,
        journal_path: Path,
    ) -> None:
        """Restore a bundle left behind by a terminated prior helper."""

        if not journal_path.exists() or not backup_root.exists():
            return
        _LOGGER.warning("Recovering interrupted launcher update transaction.")
        self._rollback(
            install_root=install_root,
            target=target,
            backup_root=backup_root,
        )
        journal_path.unlink(missing_ok=True)

    @staticmethod
    def _rollback(
        *,
        install_root: Path,
        target: LauncherBundleTarget,
        backup_root: Path,
    ) -> None:
        """Restore every backed-up target and remove partial replacements."""

        for relative_path in reversed(target.replacement_roots):
            destination = install_root / relative_path
            backup = backup_root / relative_path
            if backup.exists():
                _remove_path(destination)
                backup.parent.mkdir(parents=True, exist_ok=True)
                backup.replace(destination)
            elif _absence_marker(backup_root, relative_path).exists():
                _remove_path(destination)


def _copy_path(*, source: Path, destination: Path) -> None:
    """Copy one staged target while preserving its bundle shape."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        shutil.copy2(source, destination)


def _remove_path(path: Path) -> None:
    """Remove one file or tree when it exists."""

    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def _require_descendant(path: Path, parent: Path) -> None:
    """Reject persisted paths outside the install-owned update tree."""

    if not path.is_relative_to(parent.resolve()):
        raise LauncherUpdateTransactionError(
            f"Launcher update path escapes its owner: {path}"
        )


def _absence_marker(backup_root: Path, relative_path: Path) -> Path:
    """Return the marker proving a target was absent before modification."""

    return backup_root / ".absent" / relative_path


def _process_exists(pid: int) -> bool:
    """Return whether a process identifier still names a live process."""

    if sys.platform == "win32":
        return _windows_process_exists(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _windows_process_exists(pid: int) -> bool:
    """Query a Windows process without sending the destructive signal zero."""

    process_query_limited_information = 0x1000
    still_active = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(
        process_query_limited_information,
        False,
        pid,
    )
    if not handle:
        return False
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def _relaunch(executable_path: Path) -> None:
    """Start the newly promoted launcher without inheriting helper handles."""

    creationflags = 0
    startupinfo = None
    if sys.platform == "win32":
        creationflags = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    subprocess.Popen(  # noqa: S603
        [str(executable_path)],
        cwd=executable_path.parent,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creationflags,
        startupinfo=startupinfo,
        shell=False,
    )


__all__ = ["LauncherUpdateTransaction", "LauncherUpdateTransactionError"]
