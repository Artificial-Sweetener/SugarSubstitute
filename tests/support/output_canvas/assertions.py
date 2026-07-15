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

"""Provide focused assertions for Output composition identity tests."""

from __future__ import annotations

from typing import Any


def assert_stable_layer_identity(first: Any, second: Any) -> None:
    """Assert recomposition preserves ordered layer identity and metadata."""

    assert [layer.layer_id for layer in second.layers] == [
        layer.layer_id for layer in first.layers
    ]
    assert [layer.metadata for layer in second.layers] == [
        layer.metadata for layer in first.layers
    ]


__all__ = ["assert_stable_layer_identity"]
