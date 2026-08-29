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

"""Control external preflight state for application-startup scenarios."""

from __future__ import annotations

import pytest

from substitute.app.bootstrap import default_comfy_preflight


@pytest.fixture(autouse=True)
def allow_default_comfy_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep startup-route tests independent of a host ComfyUI listener."""

    monkeypatch.setattr(
        default_comfy_preflight,
        "negotiate_default_comfy_listener",
        lambda **_kwargs: True,
    )
