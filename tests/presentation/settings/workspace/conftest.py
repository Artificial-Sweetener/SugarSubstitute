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

"""Own native widget roots created by settings-workspace contracts."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests.support.qt.lifecycle import widget_root_scope


@pytest.fixture(autouse=True)
def settings_workspace_widget_owner() -> Iterator[None]:
    """Destroy top-level widgets created by one settings-workspace test."""

    with widget_root_scope():
        yield
