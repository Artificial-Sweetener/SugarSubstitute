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

"""Verify Qt-safe editor metadata sanitation."""

from __future__ import annotations

from substitute.presentation.editor.utils.sanitation import (
    deep_sanitize_for_qt,
    sanitize_constraints_for_qt,
)


def test_deep_sanitize_for_qt_recurses_and_limits_integers() -> None:
    """Replace out-of-range integers recursively while preserving safe values."""

    too_big = 2_147_483_648
    too_small = -2_147_483_649
    source = {
        "a": too_big,
        "b": [1, too_small, {"c": too_big}],
        "ok": 123,
        "negok": -100,
    }

    sanitized = deep_sanitize_for_qt(source)

    assert sanitized["a"] is None
    assert sanitized["b"][1] is None
    assert sanitized["b"][2]["c"] is None
    assert sanitized["ok"] == 123
    assert sanitized["negok"] == -100


def test_sanitize_constraints_for_qt_only_limits_integers() -> None:
    """Replace only out-of-range constraint integers."""

    too_big = 9_999_999_999
    constraints = {"min": -1, "max": too_big, "step": 0, "other": "val"}

    safe = sanitize_constraints_for_qt(constraints)

    assert safe["min"] == -1
    assert safe["max"] is None
    assert safe["step"] == 0
    assert safe["other"] == "val"
