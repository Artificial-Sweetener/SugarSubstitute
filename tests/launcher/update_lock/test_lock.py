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

"""Tests for launcher update lock ownership."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.update_lock import (
    LauncherUpdateLock,
    LauncherUpdateLockError,
    UPDATE_LOCK_NAME,
)


def test_launcher_update_lock_creates_and_releases_lock_file(tmp_path: Path) -> None:
    """Update lock acquisition should create and remove the lock file."""

    locks_dir = tmp_path / "locks"

    lock = LauncherUpdateLock.acquire(
        locks_dir,
        now=lambda: datetime(2026, 7, 7, 12, tzinfo=UTC),
    )

    lock_path = locks_dir / UPDATE_LOCK_NAME
    assert lock_path.is_file()
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    assert payload == {
        "acquired_at_utc": "2026-07-07T12:00:00Z",
        "pid": os.getpid(),
    }

    lock.release()

    assert not lock_path.exists()


def test_launcher_update_lock_blocks_concurrent_acquisition(tmp_path: Path) -> None:
    """A live lock owner should prevent a second update owner."""

    locks_dir = tmp_path / "locks"
    lock = LauncherUpdateLock.acquire(locks_dir)
    try:
        with pytest.raises(LauncherUpdateLockError, match="already held"):
            LauncherUpdateLock.acquire(
                locks_dir,
                process_is_alive=lambda _pid: True,
            )
    finally:
        lock.release()


def test_launcher_update_lock_removes_stale_dead_owner(tmp_path: Path) -> None:
    """A lock left behind by a dead owner should be replaced."""

    locks_dir = tmp_path / "locks"
    locks_dir.mkdir()
    lock_path = locks_dir / UPDATE_LOCK_NAME
    lock_path.write_text(
        json.dumps(
            {
                "pid": 999999,
                "acquired_at_utc": "2026-07-07T12:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    lock = LauncherUpdateLock.acquire(
        locks_dir,
        process_is_alive=lambda _pid: False,
    )
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        assert payload["pid"] == os.getpid()
    finally:
        lock.release()


def test_launcher_update_lock_context_manager_releases_on_failure(
    tmp_path: Path,
) -> None:
    """Context-manager usage should release the lock after exceptions."""

    locks_dir = tmp_path / "locks"

    with pytest.raises(RuntimeError, match="boom"):
        with LauncherUpdateLock.acquire(locks_dir):
            raise RuntimeError("boom")

    assert not (locks_dir / UPDATE_LOCK_NAME).exists()
