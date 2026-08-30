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

"""Apply splash-first analysis to the repository executable entrypoints."""

from __future__ import annotations

from pathlib import Path

from tools.splash_first_governance import validate_repository


def test_repository_executable_startup_is_splash_first() -> None:
    """Every protected executable path must keep unreviewed work behind splash."""

    repository_root = Path(__file__).resolve().parents[3]

    assert validate_repository(repository_root) == ()
