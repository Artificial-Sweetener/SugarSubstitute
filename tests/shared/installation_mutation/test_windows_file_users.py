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

"""Observe native file users without treating an ordinary reader as a lock owner."""

from pathlib import Path
import os

import pytest

from sugarsubstitute_shared.installation_mutation import installation_mutation
from sugarsubstitute_shared.installation_mutation_record import (
    mutation_rendezvous_path,
    read_mutation_record,
)
from sugarsubstitute_shared.windows_file_users import WindowsFileUsers
from sugarsubstitute_shared.process_identity import capture_process_identity

pytestmark = pytest.mark.platforms("windows")


def test_native_file_users_include_mutation_owner_incarnation(tmp_path: Path) -> None:
    """Match the native holder's process creation time against its advisory record."""
    with installation_mutation(tmp_path):
        candidate = read_mutation_record(tmp_path)
        assert candidate is not None
        users = WindowsFileUsers().snapshot(mutation_rendezvous_path(tmp_path))
        actual = next(user for user in users if user.pid == os.getpid())
        assert abs(actual.created_at - candidate.process.created_at) < 0.000001
    assert WindowsFileUsers().snapshot(mutation_rendezvous_path(tmp_path)) == ()


def test_native_file_users_report_readers_without_granting_mutation_authority(
    tmp_path: Path,
) -> None:
    """Preserve the distinction between using a file and holding its byte lock."""
    path = tmp_path / "fixture.lock"
    path.write_bytes(b"fixture")
    with path.open("rb"):
        users = WindowsFileUsers().snapshot(path)
        identity = capture_process_identity(os.getpid())
        actual = next(user for user in users if user.pid == identity.pid)
        assert abs(actual.created_at - identity.created_at) < 0.000001
    assert WindowsFileUsers().snapshot(path) == ()


def test_native_query_failure_does_not_disable_later_inspection(tmp_path: Path) -> None:
    """Surface the native directory error and retain a usable query adapter."""
    inspector = WindowsFileUsers()
    with pytest.raises(OSError):
        inspector.snapshot(tmp_path)
    path = tmp_path / "fixture.lock"
    path.write_bytes(b"fixture")
    assert inspector.snapshot(path) == ()
