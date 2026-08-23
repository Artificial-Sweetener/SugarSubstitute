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

"""Sugar recipe persistence fixtures."""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class _RecipeCubeStub:
    """Provide typed cube state for recipe buffer tests."""

    cube_id: str
    version: str
    buffer: Mapping[str, object]


def _nested_value(mapping: Mapping[str, object], *keys: str) -> object:
    """Return a value from nested JSON mappings with runtime narrowing."""

    current: object = mapping
    for key in keys:
        assert isinstance(current, Mapping)
        current = current[key]
    return current


def _nested_mapping(
    mapping: Mapping[str, object],
    *keys: str,
) -> Mapping[str, object]:
    """Return a nested JSON mapping with runtime narrowing."""

    value = _nested_value(mapping, *keys)
    assert isinstance(value, Mapping)
    return value
