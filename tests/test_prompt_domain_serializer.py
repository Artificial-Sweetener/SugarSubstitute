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

"""Pure serializer tests for the prompt-domain model."""

from __future__ import annotations

import pytest

from substitute.domain.prompt import (
    parse_prompt_document,
    serialize_prompt_document,
    serialize_segments,
)


@pytest.mark.parametrize(
    "text",
    [
        "alpha, beta, gamma",
        'alpha, "beta,gamma", (delta,epsilon)',
        "(cat:1.20), plain",
        "((cat:1.2) dog:1.1), [a,b]",
        "alpha, beta, ",
    ],
)
def test_serialize_prompt_document_round_trips_exact_source_text(text: str) -> None:
    """Parsing and serializing unchanged prompt text should preserve the original source."""

    document = parse_prompt_document(text)

    assert serialize_prompt_document(document) == text


def test_serialize_segments_uses_canonical_separators_for_reorders() -> None:
    """Mutating segment order should serialize through deterministic top-level separators."""

    assert (
        serialize_segments(
            ['"beta,gamma"', "(delta,epsilon)", "alpha"],
            has_trailing_comma=True,
        )
        == '"beta,gamma", (delta,epsilon), alpha, '
    )
