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

"""Define canonical workflow override key helpers."""

from __future__ import annotations

CANONICAL_GLOBAL_OVERRIDE_KEY_MAP: dict[str, str] = {"sampler": "sampler_name"}


def canonicalize_global_override_key(override_key: str) -> str:
    """Return the canonical persisted key for one global override identity."""

    return CANONICAL_GLOBAL_OVERRIDE_KEY_MAP.get(override_key, override_key)


__all__ = [
    "CANONICAL_GLOBAL_OVERRIDE_KEY_MAP",
    "canonicalize_global_override_key",
]
