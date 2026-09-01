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

"""Verify exact application version inspection without staged-code execution."""

from __future__ import annotations

from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.application.repair import (
    RepairPayloadVersionError,
    inspect_app_payload_version,
)


def test_inspector_reads_one_literal_version_without_importing_payload(
    tmp_path: Path,
) -> None:
    """Version inspection should parse metadata and leave adjacent code inert."""

    app = tmp_path / "app"
    version_file = app / "substitute" / "_version.py"
    version_file.parent.mkdir(parents=True)
    marker = tmp_path / "executed"
    version_file.write_text(
        f'Path(r"{marker}").touch()\n__version__ = "1.2.3"\n', encoding="utf-8"
    )

    assert inspect_app_payload_version(app) == "1.2.3"
    assert not marker.exists()


@pytest.mark.parametrize(
    "source",
    ["", "__version__ = compute_version()", '__version__ = "1"\n__version__ = "2"'],
)
def test_inspector_rejects_missing_dynamic_or_ambiguous_versions(
    tmp_path: Path,
    source: str,
) -> None:
    """Detached repair must not guess a payload's version identity."""

    version_file = tmp_path / "app" / "substitute" / "_version.py"
    version_file.parent.mkdir(parents=True)
    version_file.write_text(source, encoding="utf-8")

    with pytest.raises(RepairPayloadVersionError):
        inspect_app_payload_version(tmp_path / "app")
