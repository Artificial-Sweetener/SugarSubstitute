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

"""Contract tests for the app icon import tool."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from tools import import_app_icon


def test_import_app_icon_writes_runtime_assets_and_qrc(tmp_path: Path) -> None:
    """Importing a square source should generate all runtime app icon assets."""

    source_path = tmp_path / "source.png"
    destination_dir = tmp_path / "resources" / "app_icons"
    qrc_path = tmp_path / "resources" / "app_icons.qrc"
    Image.new("RGBA", (64, 64), (255, 0, 0, 255)).save(source_path)

    import_app_icon.import_app_icon(
        source_path=source_path,
        destination_dir=destination_dir,
        qrc_path=qrc_path,
    )

    assert (destination_dir / import_app_icon.SOURCE_IMAGE_NAME).is_file()
    assert (destination_dir / "app_icon.ico").is_file()
    for size in import_app_icon.APP_ICON_PNG_SIZES:
        generated = destination_dir / f"app_icon_{size}.png"
        assert generated.is_file()
        with Image.open(generated) as image:
            assert image.size == (size, size)
            assert image.mode == "RGBA"
    assert qrc_path.read_text(encoding="utf-8") == _expected_qrc()


def test_import_app_icon_rejects_non_square_source(tmp_path: Path) -> None:
    """Non-square sources should fail before writing misleading icon assets."""

    source_path = tmp_path / "wide.png"
    Image.new("RGBA", (64, 32), (255, 0, 0, 255)).save(source_path)

    with pytest.raises(ValueError, match="must be square"):
        import_app_icon.import_app_icon(
            source_path=source_path,
            destination_dir=tmp_path / "app_icons",
            qrc_path=tmp_path / "app_icons.qrc",
        )


def test_import_app_icon_validation_rejects_outputs_outside_repo(
    tmp_path: Path,
) -> None:
    """Path validation should prevent default tool outputs outside the repository."""

    source_path = tmp_path / "source.png"
    source_path.write_bytes(b"not checked before output validation")
    outside_repo = import_app_icon.REPO_ROOT.parent / "_outside_app_icon_test"

    with pytest.raises(ValueError, match="must stay inside repo"):
        import_app_icon._validate_import_paths(
            source_path=source_path,
            destination_dir=outside_repo / "app_icons",
            qrc_path=outside_repo / "app_icons.qrc",
        )


def _expected_qrc() -> str:
    """Return the deterministic app icon Qt resource manifest text."""

    lines = [
        "<RCC>",
        f'  <qresource prefix="{import_app_icon.APP_ICON_RESOURCE_PREFIX}">',
    ]
    for size in import_app_icon.APP_ICON_PNG_SIZES:
        lines.append(
            f'    <file alias="{size}.png">app_icons/app_icon_{size}.png</file>'
        )
    lines.extend(
        [
            "  </qresource>",
            "</RCC>",
            "",
        ]
    )
    return "\n".join(lines)
