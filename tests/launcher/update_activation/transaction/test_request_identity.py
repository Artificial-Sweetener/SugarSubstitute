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

"""Verify persisted updater handoffs identify one process incarnation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sugarsubstitute_shared.launcher_update.request import LauncherUpdateRequest
from sugarsubstitute_shared.launcher_update.legacy_request_bridge import (
    renew_legacy_launcher_handoff,
)
from sugarsubstitute_shared.process_identity import ProcessIdentity

from .support import _write_scheduled_update_request


def test_update_request_preserves_exact_outgoing_identity(tmp_path: Path) -> None:
    """Keep the kernel timestamp with the PID across detached helper startup."""
    path, _python, _app = _write_scheduled_update_request(tmp_path)
    request = LauncherUpdateRequest.load(path)
    identity = ProcessIdentity(pid=123, created_at=1000.25)
    request = request.with_process_behavior(relaunch=True, wait_identity=identity)
    request.save(path)
    restored = LauncherUpdateRequest.load(path)
    assert restored.wait_identity == identity
    assert restored.relaunch
    assert (
        restored.with_process_behavior(relaunch=False, wait_identity=None).wait_identity
        is None
    )


@pytest.mark.parametrize("timestamp", [None, 0, -1, float("nan"), float("inf"), True])
def test_new_handoff_rejects_incomplete_or_invalid_identity(
    tmp_path: Path, timestamp: float | None
) -> None:
    """Reject ambiguous new handoffs before changing launcher files."""
    path, _python, _app = _write_scheduled_update_request(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(schema_version=2, wait_pid=123, wait_process_created_at=timestamp)
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        LauncherUpdateRequest.load(path)


def test_legacy_pid_only_request_can_be_rescheduled_without_guessing_identity(
    tmp_path: Path,
) -> None:
    """Preserve staged legacy data while requiring a fresh scheduler handoff."""
    path, _python, _app = _write_scheduled_update_request(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(schema_version=1, wait_pid=123)
    payload.pop("wait_process_created_at", None)
    path.write_text(json.dumps(payload), encoding="utf-8")
    request = LauncherUpdateRequest.load(path)
    with pytest.raises(ValueError, match="rescheduled"):
        _ = request.wait_identity
    updated = request.with_process_behavior(
        relaunch=True, wait_identity=ProcessIdentity(pid=456, created_at=2000.5)
    )
    updated.save(path)
    assert LauncherUpdateRequest.load(path).wait_identity == ProcessIdentity(
        pid=456, created_at=2000.5
    )
    assert updated.staged_bundle_dir == request.staged_bundle_dir


def test_legacy_bridge_binds_only_the_validated_launcher_incarnation(
    tmp_path: Path,
) -> None:
    """Upgrade a PID-only handoff with observed kernel and executable identity."""

    path, _python, _app = _write_scheduled_update_request(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(schema_version=1, wait_pid=123)
    payload.pop("wait_process_created_at", None)
    path.write_text(json.dumps(payload), encoding="utf-8")
    observed: list[tuple[int, Path]] = []

    def resolve(pid: int, executable: Path) -> ProcessIdentity:
        """Return the exact identity after recording the expected executable."""

        observed.append((pid, executable))
        return ProcessIdentity(pid=pid, created_at=456.5)

    renewed = renew_legacy_launcher_handoff(path, identity_resolver=resolve)

    assert renewed.schema_version == 2
    assert renewed.wait_identity == ProcessIdentity(pid=123, created_at=456.5)
    assert observed == [
        (123, (tmp_path / "SugarSubstitute" / "SugarSubstitute").resolve())
    ]
    assert LauncherUpdateRequest.load(path) == renewed


def test_legacy_bridge_needs_no_wait_after_launcher_exit(tmp_path: Path) -> None:
    """Treat a proven missing legacy process as an already completed handoff."""

    path, _python, _app = _write_scheduled_update_request(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(schema_version=1, wait_pid=123)
    payload.pop("wait_process_created_at", None)
    path.write_text(json.dumps(payload), encoding="utf-8")

    renewed = renew_legacy_launcher_handoff(
        path,
        identity_resolver=lambda _pid, _executable: None,
    )

    assert renewed.schema_version == 2
    assert renewed.wait_identity is None
