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

"""Verify launcher handoff geometry, configuration recovery, and logging."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.config import (
    LauncherConfig,
    ReleaseSourceConfig,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.logging_setup import configure_launcher_logging
from launcher.sugarsubstitute_launcher.ui.window_geometry import (
    parse_handoff_geometry,
)


@pytest.mark.parametrize(
    "raw_geometry",
    [None, "", "1,2,3", "1,2,3,4,5", "left,2,300,200", "1,2,0,200"],
)
def test_handoff_geometry_rejects_missing_or_invalid_values(
    raw_geometry: str | None,
) -> None:
    """Leave default placement intact for invalid handoff geometry."""

    assert parse_handoff_geometry(raw_geometry) is None


def test_handoff_geometry_preserves_valid_window_frame() -> None:
    """Preserve position and dimensions from valid handoff geometry."""

    geometry = parse_handoff_geometry("-20,35,1260,800")

    assert geometry is not None
    assert (geometry.x(), geometry.y(), geometry.width(), geometry.height()) == (
        -20,
        35,
        1260,
        800,
    )


def test_launcher_config_upgrades_missing_release_source_to_github(
    tmp_path: Path,
) -> None:
    """Recover legacy schema-one configuration with GitHub update source."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    payload = LauncherConfig.from_layout(layout=layout).to_json()
    payload.pop("release_source")
    layout.config_path.parent.mkdir(parents=True, exist_ok=True)
    layout.config_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = LauncherConfig.load(layout.config_path)

    assert loaded.release_source == ReleaseSourceConfig.default()


def test_launcher_logging_writes_under_launcher_logs(tmp_path: Path) -> None:
    """Create launcher logs beneath launcher-owned state."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")

    log_path = configure_launcher_logging(layout=layout)

    assert log_path == layout.logs_dir / "launcher.log"
    assert log_path.parent.is_dir()
