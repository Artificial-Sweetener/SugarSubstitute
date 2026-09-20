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

"""Verify durable launcher update activation and rollback."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import os
import subprocess
import sys
from launcher.sugarsubstitute_launcher.payload_models import StagedAppPayload

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.update_activation import (
    PendingUpdateActivation,
)
from launcher.sugarsubstitute_launcher.update_activation_journal import (
    UpdateRecoveryError,
)
from launcher.sugarsubstitute_launcher.update_activation_recovery import (
    recover_interrupted_update,
)
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from launcher.sugarsubstitute_launcher.update_quarantine import UpdateQuarantine
from sugarsubstitute_shared.update_rollback_report import (
    UpdateRollbackReport,
    UpdateRollbackReportStore,
    UpdateRollbackStage,
)


def test_pending_update_rolls_back_app_runtime_and_state(tmp_path: Path) -> None:
    """A failed first launch should restore every prior installed component."""

    layout = InstallLayout.from_root(tmp_path / "install")
    _write(layout.app_dir / "version.txt", "old-app")
    _write(layout.runtime_dir / "version.txt", "old-runtime")
    old_state = LauncherUpdateState(installed_app_version="0.3.0")
    old_state.save(layout.state_path)
    activation = PendingUpdateActivation.begin(
        layout=layout,
        successful_state=_updated_state(),
    )
    _write(activation.staging_directory / "version.txt", "candidate-app")
    activation.promote_app(
        StagedAppPayload(version="0.4.0", staging_dir=activation.staging_directory)
    )
    activation.prepare_runtime()
    _write(layout.runtime_dir / "version.txt", "candidate-runtime")

    activation.rollback()

    assert (layout.app_dir / "version.txt").read_text() == "old-app"
    assert (layout.runtime_dir / "version.txt").read_text() == "old-runtime"
    assert LauncherUpdateState.load(layout.state_path).installed_app_version == "0.3.0"
    assert not (layout.launcher_dir / "pending-app-update.json").exists()


def test_pending_update_commit_advances_state_and_removes_backups(
    tmp_path: Path,
) -> None:
    """A proven first launch should atomically become the installed version."""

    layout = InstallLayout.from_root(tmp_path / "install")
    _write(layout.app_dir / "version.txt", "old-app")
    _write(layout.runtime_dir / "version.txt", "old-runtime")
    activation = PendingUpdateActivation.begin(
        layout=layout,
        successful_state=_updated_state(),
    )
    _write(activation.staging_directory / "version.txt", "candidate-app")
    activation.promote_app(
        StagedAppPayload(version="0.4.0", staging_dir=activation.staging_directory)
    )
    activation.prepare_runtime()
    _write(layout.runtime_dir / "version.txt", "candidate-runtime")
    rollback_store = UpdateRollbackReportStore(layout.root)
    rollback_store.save(
        UpdateRollbackReport.capture(
            attempted_version="0.3.5",
            stage=UpdateRollbackStage.PREPARATION,
            error=RuntimeError("earlier failed update"),
        )
    )

    activation.commit()

    assert LauncherUpdateState.load(layout.state_path).installed_app_version == "0.4.0"
    assert (layout.app_dir / "version.txt").read_text() == "candidate-app"
    assert (layout.runtime_dir / "version.txt").read_text() == "candidate-runtime"
    assert not (layout.root / "app_previous").exists()
    assert not (layout.root / "runtime_previous").exists()
    assert not (layout.launcher_dir / "pending-app-update.json").exists()
    assert rollback_store.load() is None


def test_interrupted_update_is_recovered_from_durable_journal(
    tmp_path: Path,
) -> None:
    """The next launcher process should recover a crash before checking updates."""

    layout = InstallLayout.from_root(tmp_path / "install")
    _write(layout.app_dir / "version.txt", "old-app")
    _write(layout.runtime_dir / "version.txt", "old-runtime")
    _crash_activation(layout, "preparing")

    assert recover_interrupted_update(layout) is True

    assert (layout.app_dir / "version.txt").read_text() == "old-app"
    assert (layout.runtime_dir / "version.txt").read_text() == "old-runtime"
    assert recover_interrupted_update(layout) is False


def test_generation_rollback_keeps_interrupted_candidate_retryable(
    tmp_path: Path,
) -> None:
    """A cancelled first launch should restore state without condemning valid bytes."""

    layout = InstallLayout.from_root(tmp_path / "install")
    digest = "1" * 64
    activation = PendingUpdateActivation.begin(
        layout=layout,
        successful_state=_updated_state(),
        generation_backed=True,
        candidate_sha256=digest,
    )
    _write(activation.staging_directory / "version.txt", "candidate-app")
    activation.promote_app(
        StagedAppPayload(version="0.4.0", staging_dir=activation.staging_directory)
    )
    activation.prepare_runtime()
    activation.activate()

    activation.rollback()

    assert not UpdateQuarantine(layout.root).contains(version="0.4.0", sha256=digest)
    assert not (layout.launcher_dir / "pending-app-update.json").exists()


def test_interrupted_commit_finishes_proven_update(
    tmp_path: Path,
) -> None:
    """A crash after the commit marker should finish rather than roll back."""

    layout = InstallLayout.from_root(tmp_path / "install")
    _write(layout.app_dir / "version.txt", "old-app")
    _write(layout.runtime_dir / "version.txt", "old-runtime")
    _crash_activation(layout, "committed")

    assert recover_interrupted_update(layout) is True
    assert LauncherUpdateState.load(layout.state_path).installed_app_version == "0.4.0"
    assert (layout.app_dir / "version.txt").read_text() == "candidate-app"
    assert (layout.runtime_dir / "version.txt").read_text() == "candidate-runtime"


def test_corrupt_recovery_journal_fails_closed(tmp_path: Path) -> None:
    """Unknown recovery state must never launch an ambiguous active payload."""

    layout = InstallLayout.from_root(tmp_path / "install")
    _write(layout.launcher_dir / "pending-app-update.json", "not-json")

    with pytest.raises(UpdateRecoveryError, match="unreadable"):
        recover_interrupted_update(layout)


@pytest.mark.parametrize("interrupted", [False, True])
@pytest.mark.parametrize("backup", ["app", "runtime", "staging"])
def test_proven_update_remains_available_when_backup_cleanup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interrupted: bool,
    backup: str,
) -> None:
    """Keep disposal of old files from rejecting a durably accepted application."""
    import shutil

    from launcher.sugarsubstitute_launcher.update_activation_journal import (
        load_update_journal,
        previous_app_dir,
        previous_runtime_dir,
        staged_app_dir,
        update_journal_path,
    )

    layout = InstallLayout.from_root(tmp_path / "install")
    _write(layout.app_dir / "version.txt", "old-app")
    _write(layout.runtime_dir / "version.txt", "old-runtime")
    activation = None
    if interrupted:
        _crash_activation(layout, "committed")
    else:
        activation = PendingUpdateActivation.begin(
            layout=layout, successful_state=_updated_state()
        )
        _write(activation.staging_directory / "version.txt", "candidate-app")
        activation.promote_app(
            StagedAppPayload(version="0.4.0", staging_dir=activation.staging_directory)
        )
        activation.prepare_runtime()
        _write(layout.runtime_dir / "version.txt", "candidate-runtime")
    journal = load_update_journal(layout)
    assert journal is not None
    _write(staged_app_dir(layout, journal) / "obsolete.txt", "staging remainder")
    blocked = {
        "app": previous_app_dir,
        "runtime": previous_runtime_dir,
        "staging": staged_app_dir,
    }[backup](layout, journal)
    remove = shutil.rmtree

    def reject_backup(path: Path) -> None:
        """Model a native sharing failure only for an obsolete owned directory."""
        if path == blocked:
            raise PermissionError("obsolete backup is still open")
        remove(path)

    try:
        with monkeypatch.context() as fault:
            fault.setattr(shutil, "rmtree", reject_backup)
            if activation is None:
                assert recover_interrupted_update(layout)
            else:
                activation.commit()
        assert blocked.exists()
        assert (layout.app_dir / "version.txt").read_text() == "candidate-app"
        assert (layout.runtime_dir / "version.txt").read_text() == "candidate-runtime"
        assert (
            LauncherUpdateState.load(layout.state_path).installed_app_version == "0.4.0"
        )
        assert not update_journal_path(layout).exists()
        assert not recover_interrupted_update(layout)
    finally:
        if activation is not None:
            activation.rollback()


def _updated_state() -> LauncherUpdateState:
    """Return the deterministic state committed after readiness."""

    return LauncherUpdateState(
        installed_app_version="0.4.0",
        last_update_check_utc=datetime(2026, 8, 12, tzinfo=UTC),
        last_successful_update_utc=datetime(2026, 8, 12, tzinfo=UTC),
    )


@pytest.mark.platforms("windows")
@pytest.mark.parametrize("backup", ["app", "runtime"])
def test_startup_recovers_committed_update_with_native_backup_reader(
    tmp_path: Path, backup: str
) -> None:
    """Finish startup recovery while Windows denies deletion of an old backup."""
    import ctypes
    from ctypes import wintypes

    from launcher.sugarsubstitute_launcher.startup_plan import LauncherStartupCandidate
    from launcher.sugarsubstitute_launcher.startup_recovery import (
        recover_startup_candidate,
    )
    from launcher.sugarsubstitute_launcher.update_activation_journal import (
        load_update_journal,
        previous_app_dir,
        previous_runtime_dir,
        update_journal_path,
    )

    layout = InstallLayout.from_root(tmp_path / "install")
    _write(layout.app_dir / "version.txt", "old-app")
    _write(layout.runtime_dir / "version.txt", "old-runtime")
    _crash_activation(layout, "committed")
    journal = load_update_journal(layout)
    assert journal is not None
    blocked = (previous_app_dir if backup == "app" else previous_runtime_dir)(
        layout, journal
    ) / "version.txt"
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    reader = kernel.CreateFileW(str(blocked), 0x80000000, 3, None, 3, 0x80, None)
    assert reader != ctypes.c_void_p(-1).value, ctypes.WinError(ctypes.get_last_error())
    try:
        with pytest.raises(PermissionError):
            blocked.unlink()
        candidate = recover_startup_candidate(LauncherStartupCandidate(layout, False))
        assert candidate.layout == layout
        assert blocked.read_text() == f"old-{backup}"
        assert (layout.app_dir / "version.txt").read_text() == "candidate-app"
        assert (layout.runtime_dir / "version.txt").read_text() == "candidate-runtime"
        assert (
            LauncherUpdateState.load(layout.state_path).installed_app_version == "0.4.0"
        )
        assert not update_journal_path(layout).exists()
        assert recover_startup_candidate(candidate) is candidate
    finally:
        assert kernel.CloseHandle(reader), ctypes.WinError(ctypes.get_last_error())


def _write(path: Path, content: str) -> None:
    """Write one fixture file and its parent directories."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _crash_activation(layout: InstallLayout, phase: str) -> None:
    """Terminate a hidden fixture owner at a durable activation boundary."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.launcher.update_activation.payload_crash_process",
            str(layout.root),
            phase,
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert result.returncode == 73, result.stderr
