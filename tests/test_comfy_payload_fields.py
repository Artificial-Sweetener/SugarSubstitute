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

"""Tests for scalar Comfy websocket payload normalization."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from substitute.infrastructure.comfy.comfy_payload_fields import (
    list_index_rejection_reason,
    optional_float,
    positive_int_or_none,
    positive_int_or_zero,
    strict_string_or_none,
    string_or_none,
)


def test_payload_fields_module_keeps_infrastructure_boundary() -> None:
    """Payload field normalization must not import Qt, presentation, or listener code."""

    source_path = (
        Path(__file__).parents[1]
        / "substitute"
        / "infrastructure"
        / "comfy"
        / "comfy_payload_fields.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden_roots = {
        "PySide6",
        "qfluentwidgets",
        "qframelesswindow",
        "substitute.presentation",
        "substitute.infrastructure.comfy.websocket_listener",
    }

    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    assert not {
        module
        for module in imported_modules
        for forbidden in forbidden_roots
        if module == forbidden or module.startswith(f"{forbidden}.")
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("node", "node"),
        (7, "7"),
        (True, "True"),
        (None, None),
        (1.5, None),
        ([], None),
    ],
)
def test_string_or_none_preserves_legacy_coercion(
    value: object,
    expected: str | None,
) -> None:
    """Optional string normalization should preserve current listener coercion."""

    assert string_or_none(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("node", "node"),
        ("", None),
        (7, None),
        (None, None),
    ],
)
def test_strict_string_or_none_requires_nonempty_strings(
    value: object,
    expected: str | None,
) -> None:
    """Strict string normalization should reject non-string payload fields."""

    assert strict_string_or_none(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1, 1.0),
        (1.25, 1.25),
        (True, 1.0),
        ("1", None),
        (None, None),
    ],
)
def test_optional_float_preserves_numeric_coercion(
    value: object,
    expected: float | None,
) -> None:
    """Optional float normalization should preserve current bool/int behavior."""

    assert optional_float(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (8, 8),
        (True, True),
        (0, 0),
        (-1, 0),
        ("8", 0),
    ],
)
def test_positive_int_or_zero_preserves_image_dimension_behavior(
    value: object,
    expected: int,
) -> None:
    """Image dimension fallback should match the previous listener helper."""

    assert positive_int_or_zero(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (8, 8),
        (True, None),
        (0, None),
        (-1, None),
        ("8", None),
    ],
)
def test_positive_int_or_none_rejects_bool_and_nonpositive_values(
    value: object,
    expected: int | None,
) -> None:
    """Artifact dimensions should only accept positive non-bool integers."""

    assert positive_int_or_none(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, None),
        (3, None),
        (-1, "negative_list_index"),
        (True, "non_integer_list_index"),
        (None, "missing_list_index"),
        ("0", "non_integer_list_index"),
    ],
)
def test_list_index_rejection_reason_reports_unusable_indexes(
    value: object,
    expected: str | None,
) -> None:
    """List-index validation should preserve cube-output routing diagnostics."""

    assert list_index_rejection_reason(value) == expected
