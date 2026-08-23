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

"""Test runtime Python-distribution-name constants."""

from __future__ import annotations

from substitute.domain.runtime_versions import (
    PYSIDE6_DISTRIBUTION_NAMES,
    PYSIDE6_FLUENT_WIDGETS_DISTRIBUTION_NAMES,
)


def test_pyside_runtime_distribution_names_match_installed_packages() -> None:
    """PySide UI package constants should resolve installed distribution names."""

    assert PYSIDE6_DISTRIBUTION_NAMES == ("PySide6",)
    assert PYSIDE6_FLUENT_WIDGETS_DISTRIBUTION_NAMES == ("PySide6-Fluent-Widgets",)
