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

"""Verify the authoritative Sugar value-literal codec."""

from __future__ import annotations

import pytest

from substitute.domain.recipes.sugar_literal_codec import SugarLiteralCodec


@pytest.mark.parametrize(
    ("value", "encoded"),
    [
        (None, "null"),
        ([], "[]"),
        (["a"], '["a"]'),
        ("", '""'),
        ("hello", '"hello"'),
        ("[]", '"[]"'),
        (True, "True"),
        (42, "42"),
        ("line1\nline2", '"""line1\nline2"""'),
        ('line1\nline2"', '"line1\\nline2\\""'),
        ('line1\nembedded """ delimiter', '"line1\\nembedded \\"\\"\\" delimiter"'),
        ("line1\r\nline2", '"line1\\r\\nline2"'),
        ("prompt \\(literal\\)", '"prompt \\\\(literal\\\\)"'),
        ("café 猫", '"café 猫"'),
    ],
)
def test_encode_emits_canonical_sugar_literals(
    value: object,
    encoded: str,
) -> None:
    """Values should use readable syntax without ambiguous delimiters."""

    assert SugarLiteralCodec().encode(value) == encoded


@pytest.mark.parametrize(
    "value",
    [
        "",
        "plain",
        'terminal quote"',
        'quote run"""',
        "line1\nline2",
        'line1\nline2"',
        "line1\r\nline2",
        "prompt \\(literal\\)",
        "column\tvalue",
        "Unicode café 猫",
    ],
)
def test_encoded_scalar_strings_round_trip(value: str) -> None:
    """Every emitted scalar string should decode without data loss."""

    codec = SugarLiteralCodec()
    encoded = codec.encode(value)
    if encoded.startswith('"""'):
        assert encoded[3:-3] == value
    else:
        assert codec.decode_scalar(encoded) == value
