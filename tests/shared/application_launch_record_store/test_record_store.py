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

"""Verify launch metadata cannot be truncated by partial operating-system writes."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from sugarsubstitute_shared.application_launch_record_store import (
    ApplicationLaunchRecord,
    read_application_launch_record,
    write_application_launch_record,
)


def test_record_writer_completes_short_writes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Repeated partial writes must still publish one complete JSON record."""

    record_path = tmp_path / "locks" / "application-launch.lock"
    record_path.parent.mkdir()
    expected = ApplicationLaunchRecord(
        pid=42,
        token_digest="digest",
        handoff_consumed=True,
    )
    native_write = os.write

    def write_at_most_three_bytes(file_descriptor: int, payload: bytes) -> int:
        """Model an allowed short write from the operating system."""

        return native_write(file_descriptor, payload[:3])

    monkeypatch.setattr(
        os,
        "write",
        write_at_most_three_bytes,
    )

    write_application_launch_record(record_path, expected)

    assert read_application_launch_record(record_path) == expected


def test_failed_replacement_preserves_the_previous_complete_record(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed temporary write must not damage already published metadata."""

    record_path = tmp_path / "locks" / "application-launch.lock"
    record_path.parent.mkdir()
    previous = ApplicationLaunchRecord(
        pid=42,
        token_digest="previous",
        handoff_consumed=True,
    )
    write_application_launch_record(record_path, previous)
    monkeypatch.setattr(os, "write", lambda _fd, _p: 0)

    with pytest.raises(OSError, match="made no progress"):
        write_application_launch_record(
            record_path,
            ApplicationLaunchRecord(
                pid=43,
                token_digest="replacement",
                handoff_consumed=True,
            ),
        )

    assert read_application_launch_record(record_path) == previous
    assert not tuple(record_path.parent.glob("*.tmp"))
