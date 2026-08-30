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

"""Persist serialized launch-handoff metadata independently of ownership."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path
import secrets
import threading
import time
from typing import BinaryIO, Iterator, cast


APPLICATION_LAUNCH_LOCK_NAME = "application-launch.lock"
_APPLICATION_LAUNCH_MUTEX_NAME = "application-launch.mutex"
_MUTEX_ACQUIRE_TIMEOUT_SECONDS = 5.0
_MUTEX_RETRY_SECONDS = 0.01
_THREAD_LOCKS: dict[Path, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


@dataclass(frozen=True, slots=True)
class ApplicationLaunchRecord:
    """Describe the process and handoff token recorded during application startup."""

    pid: int
    token_digest: str
    handoff_consumed: bool
    restart_token_digest: str | None = None

    def to_json(self) -> dict[str, object]:
        """Return the stable JSON representation written to disk."""

        return {
            "handoff_consumed": self.handoff_consumed,
            "pid": self.pid,
            "restart_token_digest": self.restart_token_digest,
            "token_digest": self.token_digest,
        }


def application_launch_lock_path(install_root: Path) -> Path:
    """Return the installation-scoped launch metadata path."""

    return (
        install_root.expanduser().resolve()
        / "launcher"
        / "locks"
        / APPLICATION_LAUNCH_LOCK_NAME
    )


def read_application_launch_record(
    lock_path: Path,
) -> ApplicationLaunchRecord | None:
    """Read valid metadata, returning `None` for missing or malformed data."""

    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    pid = payload.get("pid")
    token_digest = payload.get("token_digest")
    handoff_consumed = payload.get("handoff_consumed", False)
    restart_token_digest = payload.get("restart_token_digest")
    if (
        not isinstance(pid, int)
        or pid <= 0
        or not isinstance(token_digest, str)
        or not token_digest
        or not isinstance(handoff_consumed, bool)
        or (
            restart_token_digest is not None
            and not isinstance(restart_token_digest, str)
        )
    ):
        return None
    return ApplicationLaunchRecord(
        pid=pid,
        token_digest=token_digest,
        handoff_consumed=handoff_consumed,
        restart_token_digest=restart_token_digest,
    )


def write_application_launch_record(
    lock_path: Path,
    record: ApplicationLaunchRecord,
) -> None:
    """Atomically replace metadata after its owner authorizes mutation."""

    temporary_path = lock_path.with_name(
        f".{lock_path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    )
    try:
        file_descriptor = os.open(
            temporary_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        )
        try:
            payload = json.dumps(record.to_json(), sort_keys=True).encode("utf-8")
            written = 0
            while written < len(payload):
                write_count = os.write(file_descriptor, payload[written:])
                if write_count <= 0:
                    raise OSError("Application launch record write made no progress.")
                written += write_count
            os.fsync(file_descriptor)
        finally:
            os.close(file_descriptor)
        os.replace(temporary_path, lock_path)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def remove_application_launch_record(
    lock_path: Path,
    *,
    expected_record: ApplicationLaunchRecord | None,
) -> None:
    """Remove metadata only when it still matches the inspected state."""

    if (
        expected_record is not None
        and read_application_launch_record(lock_path) != expected_record
    ):
        return
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return


@contextmanager
def serialized_application_launch_record_access(
    lock_path: Path,
) -> Iterator[None]:
    """Serialize metadata transitions across local threads and processes."""

    thread_lock = _thread_lock_for(lock_path)
    with thread_lock:
        mutex_path = lock_path.with_name(_APPLICATION_LAUNCH_MUTEX_NAME)
        with mutex_path.open("a+b", buffering=0) as mutex_file:
            _ensure_mutex_byte(mutex_file)
            _acquire_mutex(mutex_file)
            try:
                yield
            finally:
                _release_mutex(mutex_file)


def _thread_lock_for(lock_path: Path) -> threading.Lock:
    """Return the process-local lock paired with one installation record."""

    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(lock_path, threading.Lock())


def _ensure_mutex_byte(mutex_file: BinaryIO) -> None:
    """Ensure Windows has one stable byte range available for locking."""

    mutex_file.seek(0, os.SEEK_END)
    if mutex_file.tell() == 0:
        mutex_file.write(b"\0")
        mutex_file.flush()
    mutex_file.seek(0)


def _acquire_mutex(mutex_file: BinaryIO) -> None:
    """Acquire one bounded cross-process metadata mutex."""

    deadline = time.monotonic() + _MUTEX_ACQUIRE_TIMEOUT_SECONDS
    while True:
        try:
            _try_acquire_mutex(mutex_file)
            return
        except OSError as error:
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    "Timed out waiting for application launch ownership."
                ) from error
            time.sleep(_MUTEX_RETRY_SECONDS)


def _try_acquire_mutex(mutex_file: BinaryIO) -> None:
    """Attempt one non-blocking platform-native mutex acquisition."""

    mutex_file.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(mutex_file.fileno(), msvcrt.LK_NBLCK, 1)
        return
    _posix_flock(mutex_file, "LOCK_EX", "LOCK_NB")


def _release_mutex(mutex_file: BinaryIO) -> None:
    """Release one platform-native metadata mutex."""

    mutex_file.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(mutex_file.fileno(), msvcrt.LK_UNLCK, 1)
        return
    _posix_flock(mutex_file, "LOCK_UN")


def _posix_flock(mutex_file: BinaryIO, *flag_names: str) -> None:
    """Call POSIX flock through a typed dynamic platform boundary."""

    import importlib

    fcntl_module = importlib.import_module("fcntl")
    flock = cast(
        Callable[[int, int], None],
        getattr(fcntl_module, "flock"),
    )
    operation = 0
    for flag_name in flag_names:
        operation |= cast(int, getattr(fcntl_module, flag_name))
    flock(mutex_file.fileno(), operation)


__all__ = [
    "APPLICATION_LAUNCH_LOCK_NAME",
    "ApplicationLaunchRecord",
    "application_launch_lock_path",
    "read_application_launch_record",
    "remove_application_launch_record",
    "serialized_application_launch_record_access",
    "write_application_launch_record",
]
