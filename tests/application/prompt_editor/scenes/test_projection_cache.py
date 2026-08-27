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

"""Test prompt-scene projection cache ownership."""

from __future__ import annotations

from substitute.application.prompt_editor.scenes import projection as projection_module
from substitute.application.prompt_editor.scenes.projection import (
    clear_prompt_scene_projection_cache,
    parse_prompt_scene_projection_document,
)


def test_scene_projection_cache_evicts_the_oldest_document_at_its_capacity() -> None:
    """Bound scene parse reuse without retaining the oldest document."""

    clear_prompt_scene_projection_cache()
    first_document = parse_prompt_scene_projection_document("**scene 0\ntext")

    for index in range(projection_module._SCENE_PARSE_CACHE_LIMIT):  # noqa: SLF001
        parse_prompt_scene_projection_document(f"**scene {index + 1}\ntext")

    assert (
        len(projection_module._SCENE_PARSE_CACHE)
        == projection_module._SCENE_PARSE_CACHE_LIMIT
    )  # noqa: SLF001
    assert "**scene 0\ntext" not in projection_module._SCENE_PARSE_CACHE  # noqa: SLF001
    assert all(
        document is not first_document
        for document in projection_module._SCENE_PARSE_CACHE.values()  # noqa: SLF001
    )
