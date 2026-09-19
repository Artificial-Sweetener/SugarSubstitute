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

"""Verify semantic auditing of launcher lifecycle log records."""

from __future__ import annotations

from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from tools.single_instance_log_evidence import audit_launcher_log


_REQUIRED_MESSAGES = (
    "Elected application supervisor through native IPC",
    "Forwarding secondary invocation",
    "Queued secondary invocation until a surface owner is available",
    "Registered supervised application child",
    "Secondary invocation produced a visible surface",
    "Supervised application child disconnected",
    "Application supervisor shutdown completed",
)


def test_traceback_continuations_inherit_identity_from_their_log_record(
    tmp_path: Path,
) -> None:
    """Accept multiline exception detail beneath one identified error record."""

    layout = InstallLayout.from_root(tmp_path / "install")
    layout.logs_dir.mkdir(parents=True)
    records = [
        f"2026-09-14T00:00:0{index} INFO process=42 test {message}"
        for index, message in enumerate(_REQUIRED_MESSAGES)
    ]
    records.extend(
        (
            "2026-09-14T00:00:06 ERROR process=42 test launch failed",
            "Traceback (most recent call last):",
            '  File "launcher.py", line 1, in main',
            "RuntimeError: failed",
        )
    )
    layout.logs_dir.joinpath("launcher.log").write_text(
        "\n".join(records) + "\n",
        encoding="utf-8",
    )

    evidence = audit_launcher_log(layout)

    assert evidence["record_count"] == len(_REQUIRED_MESSAGES) + 1
    assert evidence["continuation_line_count"] == 3
    assert evidence["process_identity_on_every_record"] is True


def test_timestamped_record_without_process_identity_is_rejected(
    tmp_path: Path,
) -> None:
    """Reject a genuine structured record whose process cannot be identified."""

    layout = InstallLayout.from_root(tmp_path / "install")
    layout.logs_dir.mkdir(parents=True)
    records = [
        f"2026-09-14T00:00:0{index} INFO process=42 test {message}"
        for index, message in enumerate(_REQUIRED_MESSAGES)
    ]
    records.append("2026-09-14T00:00:06 ERROR test unidentified")
    layout.logs_dir.joinpath("launcher.log").write_text(
        "\n".join(records) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AssertionError, match="process identity"):
        audit_launcher_log(layout)


def test_scenario_selects_only_events_its_processes_can_observe(tmp_path: Path) -> None:
    """Require owner-crash evidence without demanding a dead owner's final log."""

    layout = InstallLayout.from_root(tmp_path / "install")
    layout.logs_dir.mkdir(parents=True)
    layout.logs_dir.joinpath("launcher.log").write_text(
        "2026-09-14T00:00:00 WARNING process=42 test "
        "Application lost its authoritative supervisor\n",
        encoding="utf-8",
    )

    evidence = audit_launcher_log(
        layout,
        required_events=("Application lost its authoritative supervisor",),
    )

    assert evidence["event_counts"] == {
        "Application lost its authoritative supervisor": 1
    }
