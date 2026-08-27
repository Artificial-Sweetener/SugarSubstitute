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

"""Build representative metadata for Output canvas projection tests."""

from substitute.domain.workflow import ImageMeta


def build_meta(
    label: str,
    *,
    source_key: str,
    image_number: int = 1,
    scene_key: str = "",
    scene_title: str = "",
    scene_order: int | None = None,
    scene_count: int | None = None,
    list_index: int | None = None,
    generation_run_id: str = "",
    prompt_id: str = "",
    client_id: str = "",
    node_id: str = "",
) -> ImageMeta:
    """Build Output metadata for projection tests."""

    return ImageMeta(
        workflow_name="Recipe",
        cube_name=label,
        image_number=image_number,
        suffix="",
        path=f"E:/outputs/{source_key}_{image_number}.png",
        source_key=source_key,
        source_label=label,
        scene_key=scene_key,
        scene_title=scene_title,
        scene_order=scene_order,
        scene_count=scene_count,
        list_index=list_index,
        generation_run_id=generation_run_id,
        prompt_id=prompt_id,
        client_id=client_id,
        node_id=node_id,
    )
