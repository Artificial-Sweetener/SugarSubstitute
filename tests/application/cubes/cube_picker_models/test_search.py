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

#    SugarSubsti

from .support import (
    CubeSourceMetadata,
    _classification,
    _flatten_cube_ids,
    _record,
    _target_pairs,
    build_cube_picker_sections,
    build_cube_search_targets,
)


def test_cube_picker_search_matches_display_identity_source_and_description() -> None:
    """Search should match the fields users can reasonably remember."""

    records = [
        _record(
            cube_id="ExampleOwner/Sharp-Pack/prompt-mask.cube",
            display_name="Promptmask Detailer",
            description="Finds masked regions",
            source=CubeSourceMetadata(
                kind="github",
                repo_ref="ExampleOwner/Sharp-Pack",
                owner="ExampleOwner",
                repo="Sharp-Pack",
                path="prompt-mask.cube",
            ),
        ),
        _record(
            cube_id="ExampleOwner/Base-Cubes/text-to-image.cube",
            display_name="Text to Image",
        ),
    ]
    classifications = {
        "ExampleOwner/Sharp-Pack/prompt-mask.cube": _classification("middle", 1, 1),
        "ExampleOwner/Base-Cubes/text-to-image.cube": _classification("start", 0, 1),
    }

    by_description = build_cube_picker_sections(
        records,
        classifications=classifications,
        search_text="masked",
    )
    by_source = build_cube_picker_sections(
        records,
        classifications=classifications,
        search_text="sharp-pack",
    )
    by_version = build_cube_picker_sections(
        records,
        classifications=classifications,
        search_text="v1.0.0",
    )

    assert _flatten_cube_ids(by_description) == (
        "ExampleOwner/Sharp-Pack/prompt-mask.cube",
    )
    assert _flatten_cube_ids(by_source) == ("ExampleOwner/Sharp-Pack/prompt-mask.cube",)
    assert _flatten_cube_ids(by_version) == (
        "ExampleOwner/Base-Cubes/text-to-image.cube",
        "ExampleOwner/Sharp-Pack/prompt-mask.cube",
    )


def test_cube_picker_search_matches_loaded_node_metadata() -> None:
    """Search should match node classes, authored titles, and surface controls."""

    records = [
        _record(
            cube_id="ExampleOwner/Base-Cubes/detailer.cube",
            display_name="Detailer",
        ),
        _record(
            cube_id="ExampleOwner/Base-Cubes/plain.cube",
            display_name="Plain",
        ),
    ]
    classifications = {
        "ExampleOwner/Base-Cubes/detailer.cube": _classification(
            "middle",
            1,
            1,
            search_terms=(
                "UltralyticsDetectorProvider",
                "bbox_detector",
                "Detailer sampler",
                "ksampler.denoise",
            ),
        ),
    }

    by_class = build_cube_picker_sections(
        records,
        classifications=classifications,
        search_text="ultralytics",
    )
    by_title = build_cube_picker_sections(
        records,
        classifications=classifications,
        search_text="detailer sampler",
    )
    by_control = build_cube_picker_sections(
        records,
        classifications=classifications,
        search_text="ksampler.denoise",
    )

    assert _flatten_cube_ids(by_class) == ("ExampleOwner/Base-Cubes/detailer.cube",)
    assert _flatten_cube_ids(by_title) == ("ExampleOwner/Base-Cubes/detailer.cube",)
    assert _flatten_cube_ids(by_control) == ("ExampleOwner/Base-Cubes/detailer.cube",)


def test_cube_search_targets_include_display_model_pack_and_source_metadata() -> None:
    """Structured search targets should expose searchable metadata sources."""

    records = [
        _record(
            cube_id="ExampleOwner/Sharp-Pack/prompt-mask.cube",
            display_name="Promptmask Detailer",
            source=CubeSourceMetadata(
                kind="github",
                repo_ref="ExampleOwner/Sharp-Pack",
                owner="ExampleOwner",
                repo="Sharp-Pack",
                branch="main",
                namespace="Sharp-Pack",
                path="prompt-mask.cube",
            ),
            supported_models=("SDXL 1.0",),
        ),
    ]

    targets = build_cube_search_targets(records)

    assert ("Promptmask Detailer", "cube") in _target_pairs(targets)
    assert ("SDXL 1.0", "model") in _target_pairs(targets)
    assert ("ExampleOwner/Sharp-Pack", "pack") in _target_pairs(targets)
    assert ("main", "source") in _target_pairs(targets)
