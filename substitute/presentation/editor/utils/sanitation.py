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

"""Normalize editor metadata so Qt widgets receive safe primitive values."""

from __future__ import annotations

from typing import Any


def deep_sanitize_for_qt(obj: Any) -> Any:
    """
    Recursively replaces any integer value outside the signed 32-bit range with None,
    for safe property assignment in Qt (whose widgets apparently still think it's 1997).

    Qt's property system (and some widgets) will quietly panic if handed an int that's
    too big for a signed 32-bit value—no matter how modern your CPU. So, this helper
    walks through your dicts and lists, replacing any too-large (or too-small) ints with
    None, sidestepping inexplicable QVariant overflows and mysterious widget failures.

    Parameters:
        obj (Any): The object (likely a dict, list, or primitive) to sanitize.

    Returns:
        The sanitized copy, with all >32-bit ints swapped for None.

    Note:
        It's a little absurd we have to write this in 2025, but here we are.
    """
    MAX_QT_INT = 2_147_483_647
    MIN_QT_INT = -2_147_483_648
    if isinstance(obj, dict):
        return {k: deep_sanitize_for_qt(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [deep_sanitize_for_qt(v) for v in obj]
    elif isinstance(obj, int) and not (MIN_QT_INT <= obj <= MAX_QT_INT):
        return None
    else:
        return obj


def sanitize_constraints_for_qt(constraints: dict[str, Any]) -> dict[str, Any]:
    """
    Produces a constraints dict safe for Qt widgets by replacing any integer value
    outside the 32-bit signed range with None. (Because, in the year of our lord 2025,
    that's still necessary.)

    Qt's widgets can only cope with 32-bit ints—if you hand them a bigger number,
    they'll either clamp, fail, or just sulk. This helper protects you from
    QVariant overflow errors (and existential questions) by making your constraints
    Qt-compliant, one tiny int at a time.

    Parameters:
        constraints (dict): The constraints dictionary (min, max, step, etc.) to sanitize.

    Returns:
        dict: A sanitized copy, safe for use with Qt's sometimes-anxious widgets.

    See Also:
        deep_sanitize_for_qt() — for full-recursion sanitizing through arbitrarily nested data.

    Because apparently "modern C++" and "modern GUI frameworks" aren't always synonyms.
    """
    MAX_QT_INT = 2_147_483_647
    MIN_QT_INT = -2_147_483_648
    safe: dict[str, Any] = {}
    for k, v in constraints.items():
        if isinstance(v, int) and not (MIN_QT_INT <= v <= MAX_QT_INT):
            safe[k] = None  # or str(v) if you need it for display/debug
        else:
            safe[k] = v
    return safe
