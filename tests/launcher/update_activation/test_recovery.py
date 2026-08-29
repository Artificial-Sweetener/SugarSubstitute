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

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.update_activation import (
    PendingUpdateActivation,
    UpdateRecoveryError,
    recover_interrupted_update,
)
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
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
    layout.app_dir.replace(layout.root / "app_previous")
    _write(layout.app_dir / "version.txt", "candidate-app")
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
    layout.app_dir.replace(layout.root / "app_previous")
    _write(layout.app_dir / "version.txt", "candidate-app")
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
    activation = PendingUpdateActivation.begin(
        layout=layout,
        successful_state=_updated_state(),
    )
    layout.app_dir.replace(layout.root / "app_previous")
    _write(layout.app_dir / "version.txt", "candidate-app")
    activation.prepare_runtime()
    _write(layout.runtime_dir / "version.txt", "candidate-runtime")

    assert recover_interrupted_update(layout) is True

    assert (layout.app_dir / "version.txt").read_text() == "old-app"
    assert (layout.runtime_dir / "version.txt").read_text() == "old-runtime"
    assert recover_interrupted_update(layout) is False


def test_interrupted_commit_finishes_proven_update(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A crash after the commit marker should finish rather than roll back."""

    layout = InstallLayout.from_root(tmp_path / "install")
    _write(layout.app_dir / "version.txt", "old-app")
    _write(layout.runtime_dir / "version.txt", "old-runtime")
    activation = PendingUpdateActivation.begin(
        layout=layout,
        successful_state=_updated_state(),
    )
    layout.app_dir.replace(layout.root / "app_previous")
    _write(layout.app_dir / "version.txt", "candidate-app")
    activation.prepare_runtime()
    _write(layout.runtime_dir / "version.txt", "candidate-runtime")
    original_save = LauncherUpdateState.save

    def fail_state_save(_state: LauncherUpdateState, _path: Path) -> None:
        """Simulate termination after the durable commit marker is written."""

        raise OSError("process terminated")

    monkeypatch.setattr(LauncherUpdateState, "save", fail_state_save)

    with pytest.raises(OSError, match="process terminated"):
        activation.commit()
    monkeypatch.setattr(LauncherUpdateState, "save", original_save)

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


def _updated_state() -> LauncherUpdateState:
    """Return the deterministic state committed after readiness."""

    return LauncherUpdateState(
        installed_app_version="0.4.0",
        last_update_check_utc=datetime(2026, 8, 12, tzinfo=UTC),
        last_successful_update_utc=datetime(2026, 8, 12, tzinfo=UTC),
    )


def _write(path: Path, content: str) -> None:
    """Write one fixture file and its parent directories."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
