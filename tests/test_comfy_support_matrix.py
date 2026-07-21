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

"""Verify the committed real-tag Comfy compatibility matrix."""

from __future__ import annotations

import pytest

from tools.ci.comfy_support_matrix import COMFY_SUPPORT_MATRIX, matrix_entry


def test_comfy_support_matrix_starts_at_explicit_floor_and_ends_at_current() -> None:
    """Keep the declared proof range anchored at floor and reviewed current tag."""

    assert COMFY_SUPPORT_MATRIX[0].comfyui_tag == "v0.15.0"
    assert COMFY_SUPPORT_MATRIX[-1].comfyui_tag == "v0.28.2"


def test_comfy_support_matrix_covers_manager_contract_transitions() -> None:
    """Represent every reviewed 4.1 and 4.2 pin/capability transition."""

    assert [
        (entry.manager_version, entry.supports_pygit2) for entry in COMFY_SUPPORT_MATRIX
    ] == [
        ("4.1b1", False),
        ("4.1b2", False),
        ("4.1b6", False),
        ("4.1", False),
        ("4.2.1", True),
        ("4.2.2", True),
    ]


def test_unknown_matrix_tag_is_rejected() -> None:
    """Prevent unreviewed tags from silently using guessed expectations."""

    with pytest.raises(ValueError, match="Unknown ComfyUI matrix tag"):
        matrix_entry("v0.14.0")
