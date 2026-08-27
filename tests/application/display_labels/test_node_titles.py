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

"""Verify capitalization policy for technical node titles."""

from substitute.application.display_labels import beautify_label


def test_node_title_preserves_internal_capitalization_without_display_name() -> None:
    """Beautify words without flattening their meaningful internal case."""

    assert beautify_label("mahiro CFG") == "Mahiro CFG"
    assert beautify_label("vectorscopeCC") == "VectorscopeCC"
