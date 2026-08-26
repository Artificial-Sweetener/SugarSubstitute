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

"""Qualify launcher and image IO beyond legacy Windows path limits."""

from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest
from PIL import Image

from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.payload import extract_app_payload_archive
from sugarsubstitute_shared.windows_long_paths import (
    operational_path,
)


def test_launcher_config_and_zip_payload_work_beyond_max_path(
    tmp_path: Path,
) -> None:
    """Installer-owned serialization and extraction should remain prefix-transparent."""

    install_root = operational_path(tmp_path / "install")
    while len(str(install_root)) < 285:
        install_root /= "segment-0123456789abcdef"
    layout = InstallLayout.from_root(install_root)
    config = LauncherConfig.from_layout(layout=layout)
    config.save(layout.config_path)
    archive_path = operational_path(tmp_path / "payload.zip")
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("nested/payload.txt", "payload")

    extract_app_payload_archive(
        zip_path=archive_path,
        destination_dir=layout.app_dir,
    )

    config_text = layout.config_path.read_text(encoding="utf-8")
    assert "\\\\?\\" not in config_text
    assert json.loads(config_text)["install_root"] == str(layout.root)
    assert (layout.app_dir / "nested" / "payload.txt").read_text(
        encoding="utf-8"
    ) == "payload"


@pytest.mark.platforms("windows")
def test_pillow_round_trips_output_beyond_max_path(tmp_path: Path) -> None:
    """Pillow should honor the PathLike transport used by output persistence."""

    output_path = operational_path(tmp_path / "outputs")
    while len(str(output_path)) < 285:
        output_path /= "segment-0123456789abcdef"
    output_path /= "result.png"
    output_path.parent.mkdir(parents=True)

    Image.new("RGB", (11, 13), "purple").save(output_path)
    with Image.open(output_path) as image:
        assert image.size == (11, 13)
