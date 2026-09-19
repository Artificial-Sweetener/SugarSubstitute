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

"""Publish bounded recovery identity hints alongside native mutation ownership.

This is transient synchronization metadata, not cache or a lease. A record alone
never establishes that a process owns the kernel lock or may be terminated.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import secrets

from sugarsubstitute_shared.process_identity import (
    ProcessIdentity,
    capture_process_identity,
)

_LOGGER = logging.getLogger(__name__)
_MAXIMUM_RECORD_BYTES = 4096


@dataclass(frozen=True, slots=True)
class InstallationMutationRecord:
    """Identify a candidate operation for independent native and invocation checks."""

    operation_id: str
    process: ProcessIdentity


def mutation_rendezvous_path(root: Path) -> Path:
    """Select the stable identity-hint file shared by installation writers."""
    return root / ".repair" / "mutation.lock"


def open_mutation_record(root: Path) -> int:
    """Open stable, non-inheritable hint storage without deciding native admission."""
    rendezvous = mutation_rendezvous_path(root)
    rendezvous.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(rendezvous, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        os.set_inheritable(descriptor, False)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def publish_mutation_record(descriptor: int) -> None:
    """Publish the current process incarnation after native lock acquisition."""
    identity = capture_process_identity(os.getpid())
    payload = json.dumps(
        {
            "schema_version": 1,
            "pid": identity.pid,
            "created_at": identity.created_at,
            "operation_id": secrets.token_hex(16),
        },
        sort_keys=True,
    ).encode("utf-8")
    os.lseek(descriptor, 1, os.SEEK_SET)
    remaining = memoryview(payload)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise OSError("Installation ownership identity could not be published.")
        remaining = remaining[written:]
    os.ftruncate(descriptor, len(payload) + 1)


def retire_mutation_record(descriptor: int) -> None:
    """Clear the hint while retaining the shared rendezvous inode."""
    os.ftruncate(descriptor, 0)


def read_mutation_record(root: Path) -> InstallationMutationRecord | None:
    """Read bounded candidate identity, treating partial or stale data as unproven."""
    try:
        with mutation_rendezvous_path(root).open("rb") as stream:
            stream.seek(1)
            raw = stream.read(_MAXIMUM_RECORD_BYTES + 1)
    except FileNotFoundError:
        return None
    except OSError:
        _LOGGER.warning(
            "Could not inspect installation ownership identity", exc_info=True
        )
        return None
    if not raw:
        return None
    try:
        if len(raw) > _MAXIMUM_RECORD_BYTES:
            raise ValueError("Ownership record exceeds its bound.")
        data = json.loads(raw)
        if (
            not isinstance(data, dict)
            or type(data.get("schema_version")) is not int
            or data["schema_version"] != 1
        ):
            raise ValueError("Unsupported ownership record.")
        pid = data.get("pid")
        created_at = data.get("created_at")
        operation_id = data.get("operation_id")
        if type(pid) is not int or pid <= 0:
            raise ValueError("Invalid process identifier.")
        if not isinstance(created_at, (int, float)) or isinstance(created_at, bool):
            raise ValueError("Invalid process creation time.")
        if (
            not isinstance(operation_id, str)
            or len(operation_id) != 32
            or any(character not in "0123456789abcdef" for character in operation_id)
        ):
            raise ValueError("Invalid operation identifier.")
        return InstallationMutationRecord(
            operation_id, ProcessIdentity(pid, float(created_at))
        )
    except (ValueError, TypeError, OverflowError, UnicodeError, RecursionError):
        _LOGGER.warning(
            "Ignored invalid installation ownership identity", exc_info=True
        )
        return None
