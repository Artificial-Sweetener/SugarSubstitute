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

"""Coordinate one launcher, splash, or application startup per installation."""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping, Sequence
from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
import secrets
import threading
import time
from typing import BinaryIO, Iterator, Self, cast


APPLICATION_LAUNCH_LOCK_NAME = "application-launch.lock"
APPLICATION_LAUNCH_TOKEN_ENV = "SUGAR_SUBSTITUTE_LAUNCH_GUARD_TOKEN"
_APPLICATION_LAUNCH_MUTEX_NAME = "application-launch.mutex"
_MUTEX_ACQUIRE_TIMEOUT_SECONDS = 5.0
_MUTEX_RETRY_SECONDS = 0.01
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _ApplicationLaunchRecord:
    """Describe the process and handoff token owning application startup."""

    pid: int
    token_digest: str
    handoff_consumed: bool
    restart_token_digest: str | None = None

    def to_json(self) -> dict[str, object]:
        """Return the stable JSON representation written to the lock file."""

        return {
            "handoff_consumed": self.handoff_consumed,
            "pid": self.pid,
            "restart_token_digest": self.restart_token_digest,
            "token_digest": self.token_digest,
        }


_ACTIVE_GUARDS: dict[Path, ApplicationLaunchGuard] = {}
_THREAD_LOCKS: dict[Path, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


class ApplicationLaunchGuard:
    """Own one installation-scoped application launch across process handoffs."""

    def __init__(self, path: Path, token: str) -> None:
        """Store the claimed lock path and private process-handoff token."""

        self._path = path
        self._token = token
        self._released = False
        _ACTIVE_GUARDS[path] = self

    @classmethod
    def enter(
        cls,
        install_root: Path,
        *,
        inherited_token: str | None = None,
        allow_initial_handoff: bool = False,
        process_is_alive: Callable[[int], bool] | None = None,
        token_factory: Callable[[], str] | None = None,
    ) -> Self | None:
        """Acquire a new launch or claim an authorized process handoff."""

        process_is_alive = process_is_alive or _process_is_alive
        lock_path = application_launch_lock_path(install_root)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        token = inherited_token or (token_factory or _new_token)()
        expected_digest = _token_digest(token)

        try:
            with _serialized_record_access(lock_path):
                record = _read_record(lock_path)
                if record is not None:
                    if record.restart_token_digest == expected_digest:
                        _write_claimed_record(lock_path, token_digest=expected_digest)
                        return cls(lock_path, token)
                    if record.token_digest == expected_digest:
                        if record.handoff_consumed:
                            return None
                        _write_claimed_record(lock_path, token_digest=expected_digest)
                        return cls(lock_path, token)
                    if process_is_alive(record.pid):
                        return None
                    _remove_stale_record(lock_path, expected_record=record)
                elif lock_path.exists():
                    return None

                try:
                    _write_new_record(
                        lock_path,
                        token_digest=expected_digest,
                        handoff_consumed=not allow_initial_handoff,
                    )
                except FileExistsError:
                    return None
                return cls(lock_path, token)
        except (OSError, TimeoutError) as error:
            _LOGGER.warning(
                "Application launch ownership could not be inspected safely: %r",
                error,
            )
            return None

    @property
    def token(self) -> str:
        """Return the private token used for authorized child handoff."""

        return self._token

    def initial_handoff_environment(
        self,
        environment: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Build the one child environment authorized for initial handoff."""

        source = os.environ if environment is None else environment
        child_environment = dict(source)
        child_environment[APPLICATION_LAUNCH_TOKEN_ENV] = self._token
        return child_environment

    def prepare_restart_environment(self) -> dict[str, str] | None:
        """Authorize exactly one replacement process after controlled shutdown."""

        if self._released:
            return None
        try:
            with _serialized_record_access(self._path):
                record = _read_record(self._path)
                if (
                    record is None
                    or record.pid != os.getpid()
                    or record.token_digest != _token_digest(self._token)
                    or record.restart_token_digest is not None
                ):
                    return None
                restart_token = _new_token()
                _write_record(
                    self._path,
                    _ApplicationLaunchRecord(
                        pid=record.pid,
                        token_digest=record.token_digest,
                        handoff_consumed=True,
                        restart_token_digest=_token_digest(restart_token),
                    ),
                )
        except (OSError, TimeoutError) as error:
            _LOGGER.warning(
                "Application restart handoff could not be authorized safely: %r",
                error,
            )
            return None
        environment = dict(os.environ)
        environment[APPLICATION_LAUNCH_TOKEN_ENV] = restart_token
        return environment

    def cancel_restart_environment(self, environment: Mapping[str, str]) -> None:
        """Revoke an unused restart handoff after child creation fails."""

        restart_token = inherited_application_launch_token(environment)
        if restart_token is None or self._released:
            return
        try:
            with _serialized_record_access(self._path):
                record = _read_record(self._path)
                if (
                    record is None
                    or record.pid != os.getpid()
                    or record.token_digest != _token_digest(self._token)
                    or record.restart_token_digest != _token_digest(restart_token)
                ):
                    return
                _write_record(
                    self._path,
                    _ApplicationLaunchRecord(
                        pid=record.pid,
                        token_digest=record.token_digest,
                        handoff_consumed=True,
                    ),
                )
        except (OSError, TimeoutError) as error:
            _LOGGER.warning(
                "Unused application restart handoff could not be revoked: %r",
                error,
            )

    def release(self) -> None:
        """Release this process's claim without deleting another claimant's lock."""

        if self._released:
            return
        try:
            with _serialized_record_access(self._path):
                record = _read_record(self._path)
                if (
                    record is not None
                    and record.pid == os.getpid()
                    and record.token_digest == _token_digest(self._token)
                ):
                    try:
                        self._path.unlink()
                    except FileNotFoundError:
                        pass
        except (OSError, TimeoutError) as error:
            _LOGGER.warning(
                "Application launch ownership could not be released safely: %r",
                error,
            )
        finally:
            self._released = True
            if _ACTIVE_GUARDS.get(self._path) is self:
                _ACTIVE_GUARDS.pop(self._path, None)


def application_launch_install_root(
    argv: Sequence[str],
    *,
    app_root: Path,
) -> Path:
    """Resolve the installation root before application bootstrap starts."""

    prefix = "--install-root="
    for raw_argument in argv:
        if raw_argument.startswith(prefix):
            raw_path = raw_argument[len(prefix) :].strip()
            if raw_path:
                return Path(raw_path).expanduser().resolve()
    return app_root.resolve()


def application_launch_lock_path(install_root: Path) -> Path:
    """Return the installation-scoped launch lock path."""

    return (
        install_root.expanduser().resolve()
        / "launcher"
        / "locks"
        / APPLICATION_LAUNCH_LOCK_NAME
    )


def _application_launch_mutex_path(lock_path: Path) -> Path:
    """Return the cross-process mutex file protecting one launch record."""

    return lock_path.with_name(_APPLICATION_LAUNCH_MUTEX_NAME)


def inherited_application_launch_token(
    environment: Mapping[str, str] | None = None,
) -> str | None:
    """Return a non-empty inherited launch token when one is available."""

    source = os.environ if environment is None else environment
    token = source.get(APPLICATION_LAUNCH_TOKEN_ENV)
    return token if token else None


def clear_inherited_application_launch_token(
    environment: MutableMapping[str, str] | None = None,
) -> None:
    """Remove the startup-only token before unrelated children can inherit it."""

    target = os.environ if environment is None else environment
    target.pop(APPLICATION_LAUNCH_TOKEN_ENV, None)


def restart_application_launch_environment(
    command: Sequence[str],
) -> dict[str, str] | None:
    """Return a one-use environment for an in-process controlled app restart."""

    install_root = application_launch_install_root(command, app_root=Path.cwd())
    guard = _ACTIVE_GUARDS.get(application_launch_lock_path(install_root))
    if guard is None:
        return None
    return guard.prepare_restart_environment()


def cancel_restart_application_launch_environment(
    command: Sequence[str],
    environment: Mapping[str, str],
) -> None:
    """Revoke a prepared restart token when its process could not be created."""

    install_root = application_launch_install_root(command, app_root=Path.cwd())
    guard = _ACTIVE_GUARDS.get(application_launch_lock_path(install_root))
    if guard is not None:
        guard.cancel_restart_environment(environment)


def _read_record(lock_path: Path) -> _ApplicationLaunchRecord | None:
    """Read one valid lock record, returning `None` for missing or malformed data."""

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
    return _ApplicationLaunchRecord(
        pid=pid,
        token_digest=token_digest,
        handoff_consumed=handoff_consumed,
        restart_token_digest=restart_token_digest,
    )


def _write_new_record(
    lock_path: Path,
    *,
    token_digest: str,
    handoff_consumed: bool,
) -> None:
    """Create the launch record atomically without replacing a live claimant."""

    record = _ApplicationLaunchRecord(
        pid=os.getpid(),
        token_digest=token_digest,
        handoff_consumed=handoff_consumed,
    )
    file_descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(
            file_descriptor,
            json.dumps(record.to_json(), sort_keys=True).encode("utf-8"),
        )
        os.fsync(file_descriptor)
    finally:
        os.close(file_descriptor)


def _write_claimed_record(lock_path: Path, *, token_digest: str) -> None:
    """Claim an authorized handoff by replacing its owner record."""

    record = _ApplicationLaunchRecord(
        pid=os.getpid(),
        token_digest=token_digest,
        handoff_consumed=True,
    )
    _write_record(lock_path, record)


def _write_record(lock_path: Path, record: _ApplicationLaunchRecord) -> None:
    """Atomically replace a launch record after its owner authorizes mutation."""

    temporary_path = lock_path.with_name(
        f".{lock_path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    )
    try:
        file_descriptor = os.open(
            temporary_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        )
        try:
            os.write(
                file_descriptor,
                json.dumps(record.to_json(), sort_keys=True).encode("utf-8"),
            )
            os.fsync(file_descriptor)
        finally:
            os.close(file_descriptor)
        os.replace(temporary_path, lock_path)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def _remove_stale_record(
    lock_path: Path,
    *,
    expected_record: _ApplicationLaunchRecord,
) -> None:
    """Remove a dead owner's lock only when it has not changed since inspection."""

    if _read_record(lock_path) != expected_record:
        return
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return


def _token_digest(token: str) -> str:
    """Return the non-reversible token representation persisted on disk."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_token() -> str:
    """Return one process-handoff token with sufficient local entropy."""

    return secrets.token_urlsafe(32)


@contextmanager
def _serialized_record_access(lock_path: Path) -> Iterator[None]:
    """Serialize launch-record transitions across local threads and processes."""

    thread_lock = _thread_lock_for(lock_path)
    with thread_lock:
        mutex_path = _application_launch_mutex_path(lock_path)
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
    """Acquire one bounded cross-process launch-record mutex."""

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
    """Release one platform-native launch-record mutex."""

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


def _process_is_alive(pid: int) -> bool:
    """Return whether an existing process still owns its recorded PID."""

    if os.name == "nt":
        return _windows_process_is_alive(pid)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _windows_process_is_alive(pid: int) -> bool:
    """Query process state without sending a Windows signal."""

    from ctypes import wintypes

    process_query_limited_information = 0x1000
    synchronize = 0x00100000
    wait_object_0 = 0x00000000
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    open_process.restype = wintypes.HANDLE
    wait_for_single_object = kernel32.WaitForSingleObject
    wait_for_single_object.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    wait_for_single_object.restype = wintypes.DWORD
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    process_handle = open_process(
        process_query_limited_information | synchronize,
        False,
        pid,
    )
    if not process_handle:
        return ctypes.get_last_error() == 5
    try:
        wait_result = cast(int, wait_for_single_object(process_handle, 0))
        return wait_result != wait_object_0
    finally:
        close_handle(process_handle)


__all__ = [
    "APPLICATION_LAUNCH_LOCK_NAME",
    "APPLICATION_LAUNCH_TOKEN_ENV",
    "ApplicationLaunchGuard",
    "application_launch_install_root",
    "application_launch_lock_path",
    "cancel_restart_application_launch_environment",
    "clear_inherited_application_launch_token",
    "inherited_application_launch_token",
    "restart_application_launch_environment",
]
