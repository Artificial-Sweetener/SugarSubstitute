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

"""Verify the official CivitAI provider badge asset."""

from PySide6.QtGui import QIcon

from substitute.presentation.resources.brand_icons import civitai_badge_icon_path


def test_civitai_badge_is_a_loadable_svg() -> None:
    """Keep the model-card provider action visually identified as CivitAI."""

    path = civitai_badge_icon_path()

    assert path.suffix == ".svg"
    assert not QIcon(str(path)).isNull()
