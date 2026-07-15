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

"""Coordinate exclusive launcher update work."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import time
from typing import Self


UPDATE_LOCK_NAME = "app-update.lock"


class LauncherUpdateLockError(RuntimeError):
    """Raised when the launcher cannot acquire the update lock."""


@dataclass(frozen=True, slots=True)
class LauncherUpdateLockRecord:
    """Describe the process that owns a launcher update lock."""

    pid: int
    acquired_at_utc: datetime

    def to_json(self) -> dict[str, object]:
        """Return a JSON-safe lock record."""

        return {
            "pid": self.pid,
            "acquired_at_utc": self.acquired_at_utc.replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
        }


class LauncherUpdateLock:
    """Represent one acquired launcher update lock."""

    def __init__(self, path: Path) -> None:
        """Store the acquired lock path."""

        self._path = path
        self._released = False

    @classmethod
    def acquire(
        cls,
        locks_dir: Path,
        *,
        timeout_seconds: float = 0.0,
        poll_interval_seconds: float = 0.05,
        process_is_alive: Callable[[int], bool] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> Self:
        """Acquire the launcher app-update lock or raise after timeout."""

        locks_dir.mkdir(parents=True, exist_ok=True)
        lock_path = locks_dir / UPDATE_LOCK_NAME
        deadline = time.monotonic() + timeout_seconds
        process_is_alive = (
            _process_is_alive if process_is_alive is None else process_is_alive
        )
        now = _utc_now if now is None else now
        while True:
            _remove_stale_lock(lock_path, process_is_alive=process_is_alive)
            try:
                _write_new_lock(lock_path, now=now)
                return cls(lock_path)
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise LauncherUpdateLockError(
                        f"Launcher update lock is already held: {lock_path}"
                    ) from None
                time.sleep(poll_interval_seconds)

    def release(self) -> None:
        """Release the launcher update lock."""

        if self._released:
            return
        self._released = True
        try:
            self._path.unlink()
        except FileNotFoundError:
            return

    def __enter__(self) -> LauncherUpdateLock:
        """Return this acquired lock for context-manager usage."""

        return self

    def __exit__(self, *_exc_info: object) -> None:
        """Release the lock at the end of a context-manager block."""

        self.release()


def _write_new_lock(lock_path: Path, *, now: Callable[[], datetime]) -> None:
    """Create a new lock file atomically."""

    record = LauncherUpdateLockRecord(
        pid=os.getpid(),
        acquired_at_utc=now().astimezone(UTC),
    )
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    file_descriptor = os.open(lock_path, flags)
    try:
        payload = json.dumps(record.to_json(), sort_keys=True).encode("utf-8")
        os.write(file_descriptor, payload)
    finally:
        os.close(file_descriptor)


def _remove_stale_lock(
    lock_path: Path,
    *,
    process_is_alive: Callable[[int], bool],
) -> None:
    """Remove an existing lock when its recorded process no longer exists."""

    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict):
        return
    pid = payload.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return
    if process_is_alive(pid):
        return
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return


def _process_is_alive(pid: int) -> bool:
    """Return whether a process ID appears to be alive."""

    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _utc_now() -> datetime:
    """Return the current UTC time."""

    return datetime.now(UTC)
