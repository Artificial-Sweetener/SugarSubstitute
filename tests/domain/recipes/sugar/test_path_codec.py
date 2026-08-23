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

"""Verify Sugar identifier and dotted-path encoding ownership."""

from __future__ import annotations

import pytest

from substitute.domain.recipes.sugar_path_codec import SugarPathCodec


@pytest.mark.parametrize(
    ("segment", "encoded"),
    [
        ("abc", "abc"),
        ("abc_def", "abc_def"),
        ("abc def", '"abc def"'),
        ("weird/name", '"weird/name"'),
        ('quoted"name', '"quoted\\"name"'),
        (r"path\name", '"path\\\\name"'),
    ],
)
def test_encode_segment_escapes_quoted_identifiers(
    segment: str,
    encoded: str,
) -> None:
    """Quoted path segments should remain valid Sugar string tokens."""

    assert SugarPathCodec().encode_segment(segment) == encoded


@pytest.mark.parametrize(
    "segments",
    [
        ["alias", "node", "field"],
        ["alias with space", 'node"quoted', r"field\path"],
    ],
)
def test_encoded_segments_round_trip_through_dotted_paths(
    segments: list[str],
) -> None:
    """Encoded identifiers should split back into their semantic segments."""

    codec = SugarPathCodec()
    source = ".".join(codec.encode_segment(segment) for segment in segments)
    assert codec.split(source) == segments
