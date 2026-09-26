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

"""Verify supported Comfy video history shapes."""

from __future__ import annotations

from substitute.infrastructure.comfy.comfy_video_artifact_parser import (
    parse_comfy_video_artifacts,
)


def test_parser_accepts_generic_vhs_and_core_animated_shapes() -> None:
    """Normalize each supported history collection into video artifacts."""

    artifact = {
        "filename": "movie.webm",
        "subfolder": "clips",
        "type": "output",
        "format": "video/webm",
    }

    for payload in (
        {"videos": [artifact]},
        {"gifs": [artifact]},
        {"images": [artifact], "animated": True},
        {"video": artifact},
    ):
        parsed = parse_comfy_video_artifacts(payload)
        assert parsed is not None
        assert len(parsed) == 1
        assert parsed[0].media_kind == "video"
        assert parsed[0].mime_type == "video/webm"


def test_parser_rejects_malformed_collections_without_claiming_images() -> None:
    """Keep ordinary images outside video routing and reject partial records."""

    assert parse_comfy_video_artifacts({"images": [{"filename": "image.png"}]}) == ()
    assert parse_comfy_video_artifacts({"videos": "movie.webm"}) is None
    assert parse_comfy_video_artifacts({"videos": [{"filename": "movie.webm"}]}) is None
