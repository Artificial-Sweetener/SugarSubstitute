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

"""Verify bounded launcher history is retained with crash incidents."""

from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.crash_launcher_log import (
    capture_launcher_log_tail,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.crash_reporting.protocol import CrashRunContext


def test_capture_launcher_log_retains_only_the_configured_tail(tmp_path: Path) -> None:
    """Large launcher logs must preserve recent evidence without bloating reports."""

    layout = InstallLayout.from_root(tmp_path / "install")
    layout.logs_dir.mkdir(parents=True)
    (layout.logs_dir / "launcher.log").write_bytes(b"old-evidence\nLATEST-EVIDENCE")
    context = CrashRunContext.create(tmp_path / "diagnostics")

    captured = capture_launcher_log_tail(
        layout=layout,
        context=context,
        maximum_bytes=len(b"LATEST-EVIDENCE"),
    )

    assert captured is not None
    assert captured.read_text(encoding="utf-8") == "LATEST-EVIDENCE"


def test_capture_launcher_log_tolerates_missing_source(tmp_path: Path) -> None:
    """A missing launcher log must not obscure the primary crash incident."""

    layout = InstallLayout.from_root(tmp_path / "install")
    context = CrashRunContext.create(tmp_path / "diagnostics")

    assert capture_launcher_log_tail(layout=layout, context=context) is None


def test_capture_launcher_log_rejects_unbounded_configuration(tmp_path: Path) -> None:
    """Invalid evidence bounds must fail before reading launcher history."""

    layout = InstallLayout.from_root(tmp_path / "install")
    context = CrashRunContext.create(tmp_path / "diagnostics")

    with pytest.raises(ValueError, match="must be positive"):
        capture_launcher_log_tail(layout=layout, context=context, maximum_bytes=0)
