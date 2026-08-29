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
import ctypes
import hashlib
import logging
import os
from pathlib import Path
import secrets
from typing import Self, cast

from sugarsubstitute_shared.application_instance_lease import (
    ApplicationInstanceLease,
)
from sugarsubstitute_shared.application_launch_record_store import (
    APPLICATION_LAUNCH_LOCK_NAME,
    ApplicationLaunchRecord,
    application_launch_lock_path,
    read_application_launch_record,
    remove_application_launch_record,
    serialized_application_launch_record_access,
    write_application_launch_record,
)


APPLICATION_LAUNCH_TOKEN_ENV = "SUGAR_SUBSTITUTE_LAUNCH_GUARD_TOKEN"
_AUTHORIZED_LEASE_HANDOFF_TIMEOUT_SECONDS = 30.0
_LOGGER = logging.getLogger(__name__)
_ACTIVE_GUARDS: dict[Path, ApplicationLaunchGuard] = {}


class ApplicationLaunchGuard:
    """Own one installation-scoped application launch across process handoffs."""

    def __init__(
        self,
        path: Path,
        token: str,
        *,
        instance_lease: ApplicationInstanceLease | None,
    ) -> None:
        """Store the claimed lock path and private process-handoff token."""

        self._path = path
        self._token = token
        self._instance_lease = instance_lease
        self._released = False
        _ACTIVE_GUARDS[path] = self

    @classmethod
    def enter(
        cls,
        install_root: Path,
        *,
        inherited_token: str | None = None,
        allow_initial_handoff: bool = False,
        acquire_instance_lease: bool | None = None,
        process_is_alive: Callable[[int], bool] | None = None,
        token_factory: Callable[[], str] | None = None,
    ) -> Self | None:
        """Acquire a new launch or claim an authorized process handoff."""

        process_is_alive = process_is_alive or _process_is_alive
        lock_path = application_launch_lock_path(install_root)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        token = inherited_token or (token_factory or _new_token)()
        expected_digest = _token_digest(token)
        instance_lease: ApplicationInstanceLease | None = None
        should_acquire_instance_lease = (
            not allow_initial_handoff
            if acquire_instance_lease is None
            else acquire_instance_lease
        )
        if should_acquire_instance_lease:
            authorized_handoff = (
                inherited_token is not None
                and _has_authorized_handoff(lock_path, expected_digest)
            )
            instance_lease = ApplicationInstanceLease.acquire(
                install_root,
                timeout_seconds=(
                    _AUTHORIZED_LEASE_HANDOFF_TIMEOUT_SECONDS
                    if authorized_handoff
                    else 0.0
                ),
            )
            if instance_lease is None:
                return None
        elif ApplicationInstanceLease.owner_exists(install_root):
            return None

        try:
            with serialized_application_launch_record_access(lock_path):
                record = read_application_launch_record(lock_path)
                if record is not None:
                    if record.restart_token_digest == expected_digest:
                        _write_claimed_record(lock_path, token_digest=expected_digest)
                        return cls(
                            lock_path,
                            token,
                            instance_lease=instance_lease,
                        )
                    if record.token_digest == expected_digest:
                        if record.handoff_consumed:
                            _release_rejected_instance_lease(instance_lease)
                            return None
                        _write_claimed_record(lock_path, token_digest=expected_digest)
                        return cls(
                            lock_path,
                            token,
                            instance_lease=instance_lease,
                        )
                    if process_is_alive(record.pid):
                        _release_rejected_instance_lease(instance_lease)
                        return None
                    remove_application_launch_record(
                        lock_path,
                        expected_record=record,
                    )
                elif lock_path.exists():
                    remove_application_launch_record(
                        lock_path,
                        expected_record=None,
                    )

                try:
                    _write_new_record(
                        lock_path,
                        token_digest=expected_digest,
                        handoff_consumed=not allow_initial_handoff,
                    )
                except FileExistsError:
                    _release_rejected_instance_lease(instance_lease)
                    return None
                return cls(
                    lock_path,
                    token,
                    instance_lease=instance_lease,
                )
        except (OSError, TimeoutError) as error:
            _LOGGER.warning(
                "Application launch ownership could not be inspected safely: %r",
                error,
            )
            if instance_lease is not None:
                instance_lease.release()
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
            with serialized_application_launch_record_access(self._path):
                record = read_application_launch_record(self._path)
                if (
                    record is None
                    or record.pid != os.getpid()
                    or record.token_digest != _token_digest(self._token)
                    or record.restart_token_digest is not None
                ):
                    return None
                restart_token = _new_token()
                write_application_launch_record(
                    self._path,
                    ApplicationLaunchRecord(
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
            with serialized_application_launch_record_access(self._path):
                record = read_application_launch_record(self._path)
                if (
                    record is None
                    or record.pid != os.getpid()
                    or record.token_digest != _token_digest(self._token)
                    or record.restart_token_digest != _token_digest(restart_token)
                ):
                    return
                write_application_launch_record(
                    self._path,
                    ApplicationLaunchRecord(
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
            with serialized_application_launch_record_access(self._path):
                record = read_application_launch_record(self._path)
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
            if self._instance_lease is not None:
                self._instance_lease.release()
                self._instance_lease = None
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


def _has_authorized_handoff(lock_path: Path, expected_digest: str) -> bool:
    """Return whether persisted state authorizes waiting for lease transfer."""

    try:
        with serialized_application_launch_record_access(lock_path):
            record = read_application_launch_record(lock_path)
            if record is None:
                return False
            if record.restart_token_digest == expected_digest:
                return True
            return (
                record.token_digest == expected_digest and not record.handoff_consumed
            )
    except (OSError, TimeoutError):
        return False


def _write_new_record(
    lock_path: Path,
    *,
    token_digest: str,
    handoff_consumed: bool,
) -> None:
    """Create the launch record atomically without replacing a live claimant."""

    record = ApplicationLaunchRecord(
        pid=os.getpid(),
        token_digest=token_digest,
        handoff_consumed=handoff_consumed,
    )
    write_application_launch_record(lock_path, record)


def _write_claimed_record(lock_path: Path, *, token_digest: str) -> None:
    """Claim an authorized handoff by replacing its owner record."""

    record = ApplicationLaunchRecord(
        pid=os.getpid(),
        token_digest=token_digest,
        handoff_consumed=True,
    )
    write_application_launch_record(lock_path, record)


def _release_rejected_instance_lease(
    instance_lease: ApplicationInstanceLease | None,
) -> None:
    """Release a lease acquired by an application claim that was rejected."""

    if instance_lease is not None:
        instance_lease.release()


def _token_digest(token: str) -> str:
    """Return the non-reversible token representation persisted on disk."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_token() -> str:
    """Return one process-handoff token with sufficient local entropy."""

    return secrets.token_urlsafe(32)


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
