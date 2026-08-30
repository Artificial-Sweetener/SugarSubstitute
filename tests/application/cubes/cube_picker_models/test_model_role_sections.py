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
    _classification,
    _flatten_cube_ids,
    _flatten_model_role_cube_ids,
    _model_role_cube_ids_by_title,
    _record,
    _section_cube_ids_by_title,
    _source,
    build_cube_picker_entries,
    build_cube_picker_model_role_sections,
    build_cube_picker_sections,
    classify_cube_document,
)


def test_model_view_repeats_cubes_across_supported_models() -> None:
    """Model view should repeat a cube in every model section it claims."""

    records = [
        _record(
            cube_id="owner/a/detailer.cube",
            display_name="Detailer",
            supported_models=("SDXL 1.0", "SD 1.5"),
        ),
        _record(
            cube_id="owner/a/refiner.cube",
            display_name="Refiner",
            supported_models=("SDXL 1.0",),
        ),
    ]

    sections = build_cube_picker_sections(records, view_mode="model")

    assert [section.title for section in sections] == ["SD 1.5", "SDXL 1.0"]
    assert _section_cube_ids_by_title(sections) == {
        "SD 1.5": ("owner/a/detailer.cube",),
        "SDXL 1.0": ("owner/a/detailer.cube", "owner/a/refiner.cube"),
    }


def test_model_view_uses_loaded_metadata_claims_when_catalog_omits_them() -> None:
    """Classification metadata should backfill model claims missing from catalogs."""

    records = [
        _record(cube_id="owner/a/detailer.cube", display_name="Detailer"),
    ]
    classifications = {
        "owner/a/detailer.cube": _classification(
            "middle",
            1,
            1,
            supported_models=("SDXL 1.0",),
        )
    }

    sections = build_cube_picker_sections(
        records,
        view_mode="model",
        classifications=classifications,
    )

    assert [section.title for section in sections] == ["SDXL 1.0"]
    assert _flatten_cube_ids(sections) == ("owner/a/detailer.cube",)


def test_model_view_groups_unclaimed_cubes_last() -> None:
    """Model view should keep cubes without claims discoverable at the end."""

    records = [
        _record(
            cube_id="owner/a/claimed.cube",
            display_name="Claimed",
            supported_models=("SDXL 1.0",),
        ),
        _record(cube_id="owner/a/loose.cube", display_name="Loose"),
    ]

    sections = build_cube_picker_sections(records, view_mode="model")

    assert [section.title for section in sections] == [
        "SDXL 1.0",
        "Unspecified model",
    ]
    assert _section_cube_ids_by_title(sections)["Unspecified model"] == (
        "owner/a/loose.cube",
    )


def test_model_view_search_matches_supported_model_labels() -> None:
    """Search should match supported-model claims."""

    records = [
        _record(
            cube_id="owner/a/detailer.cube",
            display_name="Detailer",
            supported_models=("SDXL 1.0",),
        ),
        _record(
            cube_id="owner/a/loader.cube",
            display_name="Loader",
            supported_models=("Flux .1 D",),
        ),
    ]

    sections = build_cube_picker_sections(
        records,
        view_mode="model",
        search_text="flux",
    )

    assert [section.title for section in sections] == ["Flux .1 D"]
    assert _flatten_cube_ids(sections) == ("owner/a/loader.cube",)


def test_model_role_sections_sort_model_groups_like_model_view() -> None:
    """Model-role sections should keep model-mode alphabetical section order."""

    records = [
        _record(
            cube_id="owner/a/SDXL/detailer.cube",
            display_name="Detailer",
            supported_models=("SDXL 1.0", "SD 1.5"),
        ),
        _record(
            cube_id="owner/a/Flux/loader.cube",
            display_name="Loader",
            supported_models=("Flux .1 D",),
        ),
    ]

    sections = build_cube_picker_model_role_sections(records)

    assert [section.title for section in sections] == ["Flux", "SDXL"]


def test_model_role_sections_use_owning_model_folder_not_compatibility_claims() -> None:
    """Model-role sections should ignore compatibility-only model claims."""

    records = [
        _record(
            cube_id="owner/a/SDXL/detailer.cube",
            display_name="Detailer",
            supported_models=("SDXL 1.0", "SD 1.5"),
        ),
    ]

    sections = build_cube_picker_model_role_sections(records)

    assert _model_role_cube_ids_by_title(sections) == {
        "SDXL": ("owner/a/SDXL/detailer.cube",),
    }


def test_model_role_sections_validate_source_path_with_loaded_metadata_claims() -> None:
    """Classification metadata should help identify a source-path model folder."""

    records = [
        _record(
            cube_id="owner/a/detailer.cube",
            display_name="Detailer",
            source=_source(path="SDXL/detailer.cube"),
        ),
    ]
    classifications = {
        "owner/a/detailer.cube": _classification(
            "middle",
            1,
            1,
            supported_models=("SDXL 1.0",),
        )
    }

    sections = build_cube_picker_model_role_sections(
        records,
        classifications=classifications,
    )

    assert [section.title for section in sections] == ["SDXL"]
    assert _flatten_model_role_cube_ids(sections) == ("owner/a/detailer.cube",)


def test_model_role_sections_group_unclaimed_cubes_last() -> None:
    """Model-role sections should keep cubes without claims discoverable last."""

    records = [
        _record(
            cube_id="owner/a/SDXL/claimed.cube",
            display_name="Claimed",
            supported_models=("SDXL 1.0",),
        ),
        _record(cube_id="owner/a/loose.cube", display_name="Loose"),
    ]

    sections = build_cube_picker_model_role_sections(records)

    assert [section.title for section in sections] == [
        "SDXL",
        "Unspecified model",
    ]
    assert _model_role_cube_ids_by_title(sections)["Unspecified model"] == (
        "owner/a/loose.cube",
    )


def test_model_role_sections_order_and_omit_role_subsections() -> None:
    """Model-role sections should order roles predictably and omit empty roles."""

    records = [
        _record(
            cube_id="SDXL/other.cube",
            display_name="Other",
            supported_models=("SDXL 1.0",),
        ),
        _record(
            cube_id="SDXL/end.cube",
            display_name="End",
            supported_models=("SDXL 1.0",),
        ),
        _record(
            cube_id="SDXL/start.cube",
            display_name="Start",
            supported_models=("SDXL 1.0",),
        ),
    ]
    classifications = {
        "SDXL/start.cube": _classification("start", 0, 1),
        "SDXL/end.cube": _classification("end", 1, 0),
    }

    sections = build_cube_picker_model_role_sections(
        records,
        classifications=classifications,
    )

    assert [section.title for section in sections[0].role_sections] == [
        "Start cubes",
        "End cubes",
        "Other cubes",
    ]


def test_model_role_sections_sort_entries_inside_each_role() -> None:
    """Model-role sections should sort role entries by name, then identity."""

    records = [
        _record(
            cube_id="SDXL/loader-b.cube",
            display_name="Loader",
            supported_models=("SDXL 1.0",),
        ),
        _record(
            cube_id="SDXL/loader-a.cube",
            display_name="Loader",
            supported_models=("SDXL 1.0",),
        ),
        _record(
            cube_id="SDXL/alpha.cube",
            display_name="alpha",
            supported_models=("SDXL 1.0",),
        ),
    ]

    sections = build_cube_picker_model_role_sections(records)

    assert _flatten_model_role_cube_ids(sections) == (
        "SDXL/alpha.cube",
        "SDXL/loader-a.cube",
        "SDXL/loader-b.cube",
    )


def test_model_role_sections_search_filters_nested_sections() -> None:
    """Search should keep only non-empty model and role subsections."""

    records = [
        _record(
            cube_id="SDXL/detailer.cube",
            display_name="Detailer",
            supported_models=("SDXL 1.0",),
        ),
        _record(
            cube_id="Flux/loader.cube",
            display_name="Loader",
            supported_models=("Flux .1 D",),
        ),
    ]
    classifications = {
        "SDXL/detailer.cube": _classification("middle", 1, 1),
        "Flux/loader.cube": _classification("start", 0, 1),
    }

    sections = build_cube_picker_model_role_sections(
        records,
        classifications=classifications,
        search_text="flux",
    )

    assert [section.title for section in sections] == ["Flux"]
    assert [section.title for section in sections[0].role_sections] == ["Start cubes"]
    assert _flatten_model_role_cube_ids(sections) == ("Flux/loader.cube",)


def test_cube_picker_sorting_and_duplicate_names_remain_identity_safe() -> None:
    """Duplicate display names should sort predictably while keeping cube IDs."""

    records = [
        _record(
            cube_id="Example/B-Pack/loader.cube",
            display_name="Loader",
        ),
        _record(
            cube_id="Example/A-Pack/loader.cube",
            display_name="Loader",
        ),
        _record(
            cube_id="Example/Base-Cubes/alpha.cube",
            display_name="alpha",
        ),
    ]

    entries = build_cube_picker_entries(records)

    assert [entry.cube_id for entry in entries] == [
        "Example/Base-Cubes/alpha.cube",
        "Example/A-Pack/loader.cube",
        "Example/B-Pack/loader.cube",
    ]
    assert entries[1].display_name == entries[2].display_name == "Loader"


def test_classify_cube_document_derives_roles_from_current_cube_boundaries() -> None:
    """Picker roles should be derived locally from loaded cube documents."""

    assert (
        classify_cube_document(
            {"implementation": {"inputs": {}, "outputs": {"image": {}}}}
        ).role
        == "start"
    )
    assert (
        classify_cube_document(
            {"implementation": {"inputs": {"image": {}}, "outputs": {"image": {}}}}
        ).role
        == "middle"
    )
    assert (
        classify_cube_document(
            {"implementation": {"inputs": {"image": {}}, "outputs": {}}}
        ).role
        == "end"
    )
