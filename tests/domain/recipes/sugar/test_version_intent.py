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

"""Sugar recipe cube-version intent contracts."""

from collections import OrderedDict


from substitute.domain.recipes.recipe_buffers import (
    restore_recipe_cube_state,
    strip_recipe_buffers,
)
from substitute.domain.recipes.sugar_script_parser import (
    parse_sugar_script_document,
)
from substitute.domain.cube_library import CubeUpdatePolicy
from substitute.domain.workflow import CubeState
from tests.domain.recipes.sugar.serialization_support import serialize_sugar_script


def test_serialize_sugar_script_serializes_pinned_cube_version() -> None:
    """Pinned cube instances should carry their selected version in Sugar text."""

    ordered = ["Text To Image"]
    cube = CubeState(
        cube_id="Owner/Repo/Text to Image.cube",
        version="1.8.0",
        alias="Text To Image",
        original_cube={},
        buffer=OrderedDict(cube_id="Owner/Repo/Text to Image.cube", nodes={}),
    )

    script = serialize_sugar_script(
        strip_recipe_buffers(ordered, {"Text To Image": cube}), ordered
    )

    assert 'use "Owner/Repo/Text to Image.cube"@1.8.0 as "Text To Image"' in script


def test_serialize_sugar_script_omits_follow_latest_version_pin() -> None:
    """Follow-latest cube instances should compile as versionless Sugar uses."""

    ordered = ["Text To Image"]
    cube = CubeState(
        cube_id="Owner/Repo/Text to Image.cube",
        version="1.8.0",
        alias="Text To Image",
        original_cube={},
        buffer=OrderedDict(cube_id="Owner/Repo/Text to Image.cube", nodes={}),
        update_policy=CubeUpdatePolicy.FOLLOW_LATEST,
    )

    script = serialize_sugar_script(
        strip_recipe_buffers(ordered, {"Text To Image": cube}), ordered
    )

    assert 'use "Owner/Repo/Text to Image.cube" as "Text To Image"' in script
    assert "@1.8.0" not in script


def test_serialize_sugar_script_serializes_two_versions_of_same_cube() -> None:
    """Distinct aliases of one cube id should keep their own version pins."""

    ordered = ["Old Text To Image", "New Text To Image"]
    cube_id = "Owner/Repo/Text to Image.cube"
    cubes = {
        "Old Text To Image": CubeState(
            cube_id=cube_id,
            version="1.7.0",
            alias="Old Text To Image",
            original_cube={},
            buffer=OrderedDict(cube_id=cube_id, nodes={}),
        ),
        "New Text To Image": CubeState(
            cube_id=cube_id,
            version="1.8.0",
            alias="New Text To Image",
            original_cube={},
            buffer=OrderedDict(cube_id=cube_id, nodes={}),
        ),
    }

    script = serialize_sugar_script(strip_recipe_buffers(ordered, cubes), ordered)

    assert 'use "Owner/Repo/Text to Image.cube"@1.7.0 as "Old Text To Image"' in script
    assert 'use "Owner/Repo/Text to Image.cube"@1.8.0 as "New Text To Image"' in script


def test_serialize_sugar_script_quotes_special_version_pin() -> None:
    """Version pins outside Sugar bare token rules should be quoted after @."""

    ordered = ["Demo"]
    cube = CubeState(
        cube_id="Owner/Repo/demo.cube",
        version="1.8.0-beta 1",
        alias="Demo",
        original_cube={},
        buffer=OrderedDict(cube_id="Owner/Repo/demo.cube", nodes={}),
    )

    script = serialize_sugar_script(
        strip_recipe_buffers(ordered, {"Demo": cube}), ordered
    )
    parsed = parse_sugar_script_document(script)

    assert 'use "Owner/Repo/demo.cube"@"1.8.0-beta 1" as Demo' in script
    assert parsed.buffers["Demo"]["version"] == "1.8.0-beta 1"


def test_versionless_use_round_trips_follow_latest_policy() -> None:
    """Versionless Sugar use statements should preserve follow-latest policy."""

    ordered = ["A"]
    cube = CubeState(
        cube_id="Owner/Repo/demo.cube",
        version="2.0",
        alias="A",
        original_cube={"cube_id": "Owner/Repo/demo.cube", "version": "2.0"},
        buffer=OrderedDict(cube_id="Owner/Repo/demo.cube", nodes={}),
        update_policy=CubeUpdatePolicy.FOLLOW_LATEST,
    )

    stripped = strip_recipe_buffers(ordered, {"A": cube})
    script = serialize_sugar_script(stripped, ordered)
    parsed = parse_sugar_script_document(script)
    restored = restore_recipe_cube_state(
        "A",
        dict(parsed.buffers["A"]),
        lambda _cube_id: {"cube_id": "Owner/Repo/demo.cube", "version": "2.0"},
    )

    assert 'use "Owner/Repo/demo.cube" as A' in script
    assert "@2.0" not in script
    assert parsed.buffers["A"]["update_policy"] == "follow_latest"
    assert "version" not in parsed.buffers["A"]
    assert restored.update_policy == CubeUpdatePolicy.FOLLOW_LATEST
    assert restored.version == "2.0"


def test_old_cube_metadata_comment_does_not_override_use_intent() -> None:
    """Old Substitute metadata comments should be inert recipe comments."""

    parsed = parse_sugar_script_document(
        "\n".join(
            [
                'use "Owner/Repo/demo.cube" as A',
                '# cube_metadata {"alias":"A","update_policy":"pinned","version":"1.0"}',
                "",
            ]
        )
    )
    restored = restore_recipe_cube_state(
        "A",
        dict(parsed.buffers["A"]),
        lambda _cube_id: {"cube_id": "Owner/Repo/demo.cube", "version": "2.0"},
    )

    assert "cube_metadata" not in parsed.buffers["A"]
    assert restored.update_policy == CubeUpdatePolicy.FOLLOW_LATEST
    assert restored.version == "2.0"
