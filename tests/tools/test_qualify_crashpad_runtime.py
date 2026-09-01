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

"""Verify cross-platform Crashpad qualification process discovery."""

from pathlib import Path
from unittest.mock import MagicMock

import psutil  # type: ignore[import-untyped]

from tools.qualify_crashpad_runtime import _is_handler_process, _wait_for_dump


def test_wait_for_dump_finds_pending_posix_report(tmp_path: Path) -> None:
    """Accept a report retained in Crashpad's POSIX pending directory."""

    dump = tmp_path / "database" / "pending" / "incident.dmp"
    dump.parent.mkdir(parents=True)
    dump.write_bytes(b"MDMP")

    assert _wait_for_dump(tmp_path / "database") == dump


def test_handler_process_matches_exact_executable_and_database(tmp_path: Path) -> None:
    """Identify a detached POSIX handler by its unique database argument."""

    handler = (tmp_path / "runtime" / "crashpad_handler").resolve()
    database = (tmp_path / "idle" / "database").resolve()
    process = MagicMock(spec=psutil.Process)
    process.exe.return_value = str(handler)
    process.cmdline.return_value = [
        str(handler),
        f"--database={database}",
        "--monitor-self",
    ]

    assert _is_handler_process(process, handler=handler, database=database)


def test_handler_process_rejects_another_database(tmp_path: Path) -> None:
    """Exclude unrelated handlers that share the qualified executable."""

    handler = (tmp_path / "runtime" / "crashpad_handler").resolve()
    process = MagicMock(spec=psutil.Process)
    process.exe.return_value = str(handler)
    process.cmdline.return_value = [
        str(handler),
        f"--database={tmp_path / 'another-database'}",
    ]

    assert not _is_handler_process(
        process,
        handler=handler,
        database=tmp_path / "idle" / "database",
    )
