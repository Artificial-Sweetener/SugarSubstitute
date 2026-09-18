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

"""Prove kernel ownership ends with execution rather than persisted lock data."""

from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import os
import json
from pathlib import Path
import subprocess
import sys
import pytest
from sugarsubstitute_shared.installation_mutation import (
    InstallationMutationBusyError,
    installation_mutation,
)
from sugarsubstitute_shared.installation_mutation_record import read_mutation_record
from sugarsubstitute_shared.process_identity import ProcessIdentityError


def _probe(root: Path, mode: str = "claim") -> int:
    """Observe a hidden child with bounded completion and captured diagnostics."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.shared.installation_mutation.probe_process",
            str(root),
            mode,
        ],
        capture_output=True,
        text=True,
        timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        check=False,
    )
    assert result.returncode in {0, 17, 73}, result.stderr
    return result.returncode


def test_other_process_waits_for_outermost_execution(tmp_path: Path) -> None:
    """Retain native exclusion until nested recovery and the outer commit finish."""
    with installation_mutation(tmp_path) as operation:
        with installation_mutation(tmp_path / ".", ownership=operation):
            assert _probe(tmp_path) == 17
        assert _probe(tmp_path) == 17
        assert _probe(tmp_path / "independent-install") == 0
    assert _probe(tmp_path) == 0


def test_process_death_releases_without_removing_rendezvous(tmp_path: Path) -> None:
    """Reclaim after abrupt native process exit without editing any lock file."""
    assert _probe(tmp_path, "crash") == 73
    rendezvous = tmp_path / ".repair" / "mutation.lock"
    assert rendezvous.is_file()
    assert read_mutation_record(tmp_path) is not None
    before = rendezvous.stat().st_ino
    assert _probe(tmp_path) == 0
    assert rendezvous.stat().st_ino == before
    assert read_mutation_record(tmp_path) is None


def test_other_thread_cannot_join_owned_execution(tmp_path: Path) -> None:
    """Reject a separate worker even when its process already owns the install."""

    def attempt() -> None:
        """Request an independent mutation from the competing worker."""
        with installation_mutation(tmp_path):
            raise AssertionError("competing thread acquired ownership")

    with ThreadPoolExecutor(max_workers=1) as pool:
        with installation_mutation(tmp_path):
            with pytest.raises(InstallationMutationBusyError):
                pool.submit(attempt).result(timeout=10)
    assert _probe(tmp_path) == 0


def test_independent_same_thread_operation_cannot_join_owner(tmp_path: Path) -> None:
    """Require operation authority rather than treating thread identity as permission."""
    with installation_mutation(tmp_path):
        with pytest.raises(InstallationMutationBusyError) as rejected:
            with installation_mutation(tmp_path):
                pass
        assert rejected.value.owner_record == read_mutation_record(tmp_path)
        assert rejected.value.owner_record is not None
        assert _probe(tmp_path) == 17
    assert _probe(tmp_path) == 0


def test_exception_releases_ownership(tmp_path: Path) -> None:
    """Release the descriptor when mutation raises without leaking thread ownership."""
    with pytest.raises(ValueError, match="injected"):
        with installation_mutation(tmp_path):
            raise ValueError("injected")
    assert _probe(tmp_path) == 0


def test_live_identity_hint_cannot_authorize_another_installation(
    tmp_path: Path,
) -> None:
    """Admit an unowned installation despite a valid hint naming a live operation."""
    active_root = tmp_path / "active"
    available_root = tmp_path / "available"
    available_record = available_root / ".repair" / "mutation.lock"
    available_record.parent.mkdir(parents=True)
    with installation_mutation(active_root):
        active_record = read_mutation_record(active_root)
        assert active_record is not None
        available_record.write_bytes(
            (active_root / ".repair" / "mutation.lock").read_bytes()
        )
        assert read_mutation_record(available_root) == active_record
        assert _probe(available_root) == 0
        assert read_mutation_record(available_root) is None
        assert read_mutation_record(active_root) == active_record
        assert _probe(active_root) == 17
    assert _probe(active_root) == 0


def test_active_operation_publishes_process_incarnation(tmp_path: Path) -> None:
    """Expose a bounded identity hint for recovery without making file presence a lease."""
    from sugarsubstitute_shared.process_identity import capture_process_identity

    rendezvous = tmp_path / ".repair" / "mutation.lock"
    with installation_mutation(tmp_path):
        with rendezvous.open("rb") as reader:
            reader.seek(1)
            record = json.loads(reader.read(4096))
        identity = capture_process_identity(os.getpid())
        assert record["schema_version"] == 1
        assert record["pid"] == identity.pid
        assert record["created_at"] == identity.created_at
        assert len(record["operation_id"]) == 32
    assert rendezvous.read_bytes() == b""


@pytest.mark.parametrize(
    "payload",
    [b"not-json", b"x" * 5000, b"{}", b"null", b"[" * 1500 + b"]" * 1500],
)
def test_invalid_identity_never_prevents_native_acquisition(
    tmp_path: Path, payload: bytes
) -> None:
    """Ignore unusable hints while admitting an installation with no live native owner."""
    rendezvous = tmp_path / ".repair" / "mutation.lock"
    rendezvous.parent.mkdir()
    rendezvous.write_bytes(b"\0" + payload)
    assert read_mutation_record(tmp_path) is None
    with installation_mutation(tmp_path):
        assert read_mutation_record(tmp_path) is not None
    assert read_mutation_record(tmp_path) is None


@pytest.mark.parametrize("failure", [OSError, ProcessIdentityError])
def test_identity_publication_failure_preserves_native_operation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: type[OSError] | type[ProcessIdentityError],
) -> None:
    """Keep advisory identity failure from blocking an otherwise admitted operation."""
    from sugarsubstitute_shared import installation_mutation as mutation_module

    def reject_publication(descriptor: int) -> None:
        """Leave incomplete hint data before failing inside the owned operation."""
        os.lseek(descriptor, 1, os.SEEK_SET)
        os.write(descriptor, b"partial identity")
        raise failure("injected publication failure")

    with monkeypatch.context() as fault:
        fault.setattr(mutation_module, "publish_mutation_record", reject_publication)
        with installation_mutation(tmp_path):
            assert read_mutation_record(tmp_path) is None
            assert _probe(tmp_path) == 17
    assert _probe(tmp_path) == 0


def test_deep_identity_record_cannot_replace_contention_error(tmp_path: Path) -> None:
    """Keep recovery metadata parsing bounded under the normal interpreter limit."""
    rendezvous = tmp_path / ".repair" / "mutation.lock"
    with installation_mutation(tmp_path):
        with rendezvous.open("r+b") as writer:
            writer.seek(1)
            writer.write(b"[" * 1500 + b"]" * 1500)
            writer.truncate()
        previous_limit = sys.getrecursionlimit()
        try:
            sys.setrecursionlimit(1000)
            with pytest.raises(InstallationMutationBusyError) as rejected:
                with installation_mutation(tmp_path):
                    pass
            assert rejected.value.owner_record is None
        finally:
            sys.setrecursionlimit(previous_limit)
    assert _probe(tmp_path) == 0


def test_expired_authority_cannot_join_a_successor(tmp_path: Path) -> None:
    """Reject a late collaborator even when a new operation owns the same root."""
    with installation_mutation(tmp_path) as retired:
        pass
    with installation_mutation(tmp_path):
        with pytest.raises(InstallationMutationBusyError, match="expired"):
            with installation_mutation(tmp_path, ownership=retired):
                pass
        assert _probe(tmp_path) == 17
    assert _probe(tmp_path) == 0


def test_authority_cannot_cross_installations(tmp_path: Path) -> None:
    """Keep an explicit operation scoped to its original installation."""
    with installation_mutation(tmp_path) as operation:
        with pytest.raises(InstallationMutationBusyError, match="elsewhere"):
            with installation_mutation(tmp_path / "another", ownership=operation):
                pass
        assert _probe(tmp_path) == 17


def test_authority_cannot_cross_execution_threads(tmp_path: Path) -> None:
    """Prevent a second worker from concurrently using one operation's authority."""
    with installation_mutation(tmp_path) as operation:

        def attempt() -> None:
            """Attempt to use the original worker's capability from another thread."""
            with installation_mutation(tmp_path, ownership=operation):
                pass

        with ThreadPoolExecutor(max_workers=1) as pool:
            with pytest.raises(InstallationMutationBusyError, match="elsewhere"):
                pool.submit(attempt).result(timeout=10)
        assert _probe(tmp_path) == 17


def test_foreign_thread_cannot_release_active_authority(tmp_path: Path) -> None:
    """Keep invalid cleanup from releasing another execution's native claim."""
    with installation_mutation(tmp_path) as operation:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with pytest.raises(InstallationMutationBusyError, match="elsewhere"):
                pool.submit(operation.release).result(timeout=10)
        assert _probe(tmp_path) == 17


def test_expired_release_cannot_underflow_authority(tmp_path: Path) -> None:
    """Reject reuse of a released operation before it changes ownership state."""
    with installation_mutation(tmp_path) as operation:
        pass
    with pytest.raises(InstallationMutationBusyError, match="expired"):
        operation.release()
    with pytest.raises(InstallationMutationBusyError, match="expired"):
        operation.validate(tmp_path)


@pytest.mark.platforms("windows")
def test_metadata_byte_lock_does_not_authorize_mutation(tmp_path: Path) -> None:
    """Keep delayed byte-lock teardown from impersonating a live operation owner."""
    import msvcrt

    rendezvous = tmp_path / ".repair" / "mutation.lock"
    rendezvous.parent.mkdir()
    with rendezvous.open("w+b", buffering=0) as retained_file:
        msvcrt.locking(retained_file.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            with installation_mutation(tmp_path):
                assert _probe(tmp_path) == 17
        finally:
            retained_file.seek(0)
            msvcrt.locking(retained_file.fileno(), msvcrt.LK_UNLCK, 1)
    assert _probe(tmp_path) == 0


@pytest.mark.platforms("windows")
def test_exclusive_metadata_reader_cannot_block_native_ownership(
    tmp_path: Path,
) -> None:
    """Keep an unavailable advisory file from becoming an installation admission gate."""
    import ctypes
    from ctypes import wintypes

    rendezvous = tmp_path / ".repair" / "mutation.lock"
    rendezvous.parent.mkdir()
    rendezvous.write_bytes(b"\0")
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
    reader = kernel.CreateFileW(str(rendezvous), 0x80000000, 0, None, 3, 0x80, None)
    assert reader != ctypes.c_void_p(-1).value, ctypes.WinError(ctypes.get_last_error())
    try:
        with installation_mutation(tmp_path):
            assert _probe(tmp_path) == 17
        assert _probe(tmp_path) == 0
    finally:
        assert kernel.CloseHandle(reader), ctypes.WinError(ctypes.get_last_error())


@pytest.mark.parametrize("release_order", [(0, 1, 2), (2, 0, 1), (1, 2, 0)])
def test_retained_scopes_keep_native_ownership_until_last_release(
    tmp_path: Path, release_order: tuple[int, int, int]
) -> None:
    """Keep retained transaction ownership when its preparation scope exits first."""
    with ExitStack() as cleanup:
        scopes = [cleanup.enter_context(ExitStack()) for _ in range(3)]
        operation = scopes[0].enter_context(installation_mutation(tmp_path))
        for scope in scopes[1:]:
            scope.enter_context(installation_mutation(tmp_path, ownership=operation))
        for index in release_order[:-1]:
            scopes[index].close()
            assert _probe(tmp_path) == 17
        scopes[release_order[-1]].close()
        assert _probe(tmp_path) == 0
