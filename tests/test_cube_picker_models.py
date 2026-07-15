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

"""Tests for cube picker grouping and filtering models."""

from __future__ import annotations

from substitute.application.cubes import (
    CubePickerClassification,
    CubePickerModelRoleSection,
    CubePickerRole,
    CubePickerSection,
    CubeSearchTerm,
    CubeSearchTarget,
    build_cube_picker_entries,
    build_cube_picker_model_role_sections,
    build_cube_picker_sections,
    build_cube_search_targets,
    classify_cube_document,
)
from substitute.application.ports import CubeCatalogRecord
from substitute.domain.cube_library import CubeSourceMetadata


def test_cube_picker_sections_group_roles_without_role_filters() -> None:
    """Kind view should group cubes by role without a separate role filter."""

    records = [
        _record(
            cube_id="Artificial-Sweetener/Base-Cubes/middle.cube",
            display_name="Middle",
        ),
        _record(
            cube_id="Artificial-Sweetener/Base-Cubes/start.cube",
            display_name="Start",
        ),
        _record(
            cube_id="Artificial-Sweetener/Base-Cubes/legacy.cube",
            display_name="Legacy",
        ),
    ]
    classifications = {
        "Artificial-Sweetener/Base-Cubes/middle.cube": _classification("middle", 1, 1),
        "Artificial-Sweetener/Base-Cubes/start.cube": _classification("start", 0, 1),
    }

    sections = build_cube_picker_sections(records, classifications=classifications)

    assert [section.title for section in sections] == [
        "Start cubes",
        "Middle cubes",
        "Other cubes",
    ]
    assert sections[0].entries[0].cube_id.endswith("start.cube")
    assert sections[2].entries[0].role == "unclassified"


def test_build_cube_picker_sections_defaults_to_kind_view() -> None:
    """The default section view should remain role-based."""

    records = [
        _record(cube_id="pack/middle.cube", display_name="Middle"),
        _record(cube_id="pack/start.cube", display_name="Start"),
    ]
    classifications = {
        "pack/middle.cube": _classification("middle", 1, 1),
        "pack/start.cube": _classification("start", 0, 1),
    }

    sections = build_cube_picker_sections(records, classifications=classifications)

    assert [(section.key, section.title, section.role) for section in sections] == [
        ("start", "Start cubes", "start"),
        ("middle", "Middle cubes", "middle"),
    ]


def test_cube_picker_sections_show_end_section_when_end_cubes_exist() -> None:
    """Kind view should include an End section when the catalog contains ends."""

    records = [
        _record(
            cube_id="Artificial-Sweetener/Base-Cubes/end.cube",
            display_name="End",
        ),
    ]
    classifications = {
        "Artificial-Sweetener/Base-Cubes/end.cube": _classification("end", 1, 0)
    }

    sections = build_cube_picker_sections(records, classifications=classifications)

    assert sections[0].title == "End cubes"
    assert sections[0].entries[0].display_name == "End"


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


def test_build_cube_picker_sections_groups_by_pack_repo_ref() -> None:
    """Pack view should group entries by explicit repository reference."""

    records = [
        _record(
            cube_id="owner/a/start.cube",
            display_name="Start",
            source=_source(repo_ref="owner/a"),
        ),
        _record(
            cube_id="owner/b/middle.cube",
            display_name="Middle",
            source=_source(repo_ref="owner/b"),
        ),
    ]

    sections = build_cube_picker_sections(records, view_mode="pack")

    assert [section.title for section in sections] == ["owner/a", "owner/b"]
    assert _section_cube_ids_by_title(sections) == {
        "owner/a": ("owner/a/start.cube",),
        "owner/b": ("owner/b/middle.cube",),
    }


def test_build_cube_picker_sections_groups_by_owner_repo_when_repo_ref_missing() -> (
    None
):
    """Pack view should fall back to owner/repo when repo_ref is unavailable."""

    records = [
        _record(
            cube_id="owner/repo/cube.cube",
            display_name="Cube",
            source=_source(owner="owner", repo="repo"),
        ),
    ]

    sections = build_cube_picker_sections(records, view_mode="pack")

    assert [(section.key, section.title) for section in sections] == [
        ("owner/repo", "owner/repo")
    ]


def test_build_cube_picker_sections_uses_local_fallback() -> None:
    """Pack view should give local-only source metadata a readable label."""

    records = [
        _record(
            cube_id="local/imkno/demo.cube",
            display_name="Demo",
            source=_source(kind="local"),
        ),
    ]

    sections = build_cube_picker_sections(records, view_mode="pack")

    assert [(section.key, section.title) for section in sections] == [
        ("local", "Local cubes")
    ]


def test_build_cube_picker_sections_uses_unknown_fallback() -> None:
    """Pack view should group missing source metadata under Unknown source."""

    records = [_record(cube_id="loose.cube", display_name="Loose")]

    sections = build_cube_picker_sections(records, view_mode="pack")

    assert [(section.key, section.title) for section in sections] == [
        ("unknown", "Unknown source")
    ]


def test_pack_view_search_filters_entries_without_losing_pack_headers() -> None:
    """Pack search should retain only pack sections that still have matches."""

    records = [
        _record(
            cube_id="owner/a/alpha.cube",
            display_name="Alpha",
            source=_source(repo_ref="owner/a"),
        ),
        _record(
            cube_id="owner/b/beta.cube",
            display_name="Beta",
            source=_source(repo_ref="owner/b"),
        ),
    ]

    sections = build_cube_picker_sections(
        records,
        view_mode="pack",
        search_text="beta",
    )

    assert [section.title for section in sections] == ["owner/b"]
    assert _flatten_cube_ids(sections) == ("owner/b/beta.cube",)


def test_pack_view_sorts_local_first_unknown_last() -> None:
    """Pack sections should prioritize local sources and leave unknown last."""

    records = [
        _record(cube_id="loose.cube", display_name="Loose"),
        _record(
            cube_id="owner/z/cube.cube",
            display_name="Remote Z",
            source=_source(repo_ref="owner/z"),
        ),
        _record(
            cube_id="local/imkno/cube.cube",
            display_name="Local",
            source=_source(kind="local"),
        ),
        _record(
            cube_id="owner/a/cube.cube",
            display_name="Remote A",
            source=_source(repo_ref="owner/a"),
        ),
    ]

    sections = build_cube_picker_sections(records, view_mode="pack")

    assert [section.title for section in sections] == [
        "Local cubes",
        "owner/a",
        "owner/z",
        "Unknown source",
    ]


def test_pack_view_sorts_entries_by_display_name_then_cube_id() -> None:
    """Pack sections should keep existing cube card ordering within each pack."""

    records = [
        _record(
            cube_id="owner/a/beta-2.cube",
            display_name="Beta",
            source=_source(repo_ref="owner/a"),
        ),
        _record(
            cube_id="owner/a/alpha.cube",
            display_name="alpha",
            source=_source(repo_ref="owner/a"),
        ),
        _record(
            cube_id="owner/a/beta-1.cube",
            display_name="Beta",
            source=_source(repo_ref="owner/a"),
        ),
    ]

    sections = build_cube_picker_sections(records, view_mode="pack")

    assert _flatten_cube_ids(sections) == (
        "owner/a/alpha.cube",
        "owner/a/beta-1.cube",
        "owner/a/beta-2.cube",
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


def test_classify_cube_document_reads_supported_model_metadata() -> None:
    """Picker classifications should include cube-supported model claims."""

    classification = classify_cube_document(
        {
            "metadata": {"supported_models": [" SDXL 1.0 ", "", "sdxl 1.0"]},
            "implementation": {"inputs": {"image": {}}, "outputs": {"image": {}}},
        }
    )

    assert classification.supported_models == ("SDXL 1.0",)


def test_classify_cube_document_indexes_node_metadata_for_search() -> None:
    """Picker classifications should expose loaded cube node terms for search."""

    classification = classify_cube_document(
        {
            "implementation": {
                "nodes": {
                    "bbox_detector": {
                        "class_type": "UltralyticsDetectorProvider",
                        "inputs": {},
                    }
                },
                "inputs": {"image": {}},
                "outputs": {"image": {}},
                "definitions": {
                    "UltralyticsDetectorProvider": {
                        "display_name": "Ultralytics Detector Provider",
                        "category": "detection",
                    }
                },
                "layout": {
                    "nodes": {
                        "bbox_detector": {
                            "class_type": "UltralyticsDetectorProvider",
                            "title": "bbox detector",
                        }
                    }
                },
            },
            "surface": {
                "controls": [
                    {
                        "control_id": "bbox_detector.model_name",
                        "symbol": "bbox_detector",
                        "input_name": "model_name",
                        "class_type": "UltralyticsDetectorProvider",
                    }
                ]
            },
        }
    )

    assert "UltralyticsDetectorProvider" in classification.search_terms
    assert "Ultralytics Detector Provider" in classification.search_terms
    assert "bbox detector" in classification.search_terms
    assert "bbox_detector.model_name" in classification.search_terms
    assert CubeSearchTerm("UltralyticsDetectorProvider", "node") in (
        classification.search_targets
    )
    assert CubeSearchTerm("Ultralytics Detector Provider", "definition") in (
        classification.search_targets
    )
    assert CubeSearchTerm("bbox_detector.model_name", "control") in (
        classification.search_targets
    )


def _record(
    *,
    cube_id: str,
    display_name: str,
    description: str = "",
    source: CubeSourceMetadata | None = None,
    supported_models: tuple[str, ...] = (),
) -> CubeCatalogRecord:
    """Return one catalog record for picker model tests."""

    return CubeCatalogRecord(
        cube_id=cube_id,
        version="1.0.0",
        display_name=display_name,
        description=description,
        source=source,
        supported_models=supported_models,
    )


def _source(
    *,
    kind: str = "github",
    repo_ref: str = "",
    owner: str = "",
    repo: str = "",
    namespace: str = "",
    path: str = "",
) -> CubeSourceMetadata:
    """Return source metadata for picker model tests."""

    return CubeSourceMetadata(
        kind=kind,
        repo_ref=repo_ref,
        owner=owner,
        repo=repo,
        namespace=namespace,
        path=path,
    )


def _classification(
    role: CubePickerRole,
    inputs: int,
    outputs: int,
    supported_models: tuple[str, ...] = (),
    search_terms: tuple[str, ...] = (),
    search_targets: tuple[CubeSearchTerm, ...] = (),
) -> CubePickerClassification:
    """Return one picker classification for tests."""

    return CubePickerClassification(
        role=role,
        input_count=inputs,
        output_count=outputs,
        supported_models=supported_models,
        search_terms=search_terms,
        search_targets=search_targets,
    )


def _flatten_cube_ids(sections: tuple[CubePickerSection, ...]) -> tuple[str, ...]:
    """Return cube IDs from all section entries in display order."""

    return tuple(entry.cube_id for section in sections for entry in section.entries)


def _target_pairs(targets: tuple[CubeSearchTarget, ...]) -> set[tuple[str, str]]:
    """Return display text and kind pairs for search-target assertions."""

    return {(target.text, target.kind) for target in targets}


def _section_cube_ids_by_title(
    sections: tuple[CubePickerSection, ...],
) -> dict[str, tuple[str, ...]]:
    """Return section entries keyed by section title."""

    return {
        section.title: tuple(entry.cube_id for entry in section.entries)
        for section in sections
    }


def _flatten_model_role_cube_ids(
    sections: tuple[CubePickerModelRoleSection, ...],
) -> tuple[str, ...]:
    """Return cube IDs from nested model-role sections in display order."""

    return tuple(
        entry.cube_id
        for model_section in sections
        for role_section in model_section.role_sections
        for entry in role_section.entries
    )


def _model_role_cube_ids_by_title(
    sections: tuple[CubePickerModelRoleSection, ...],
) -> dict[str, tuple[str, ...]]:
    """Return nested section entries keyed by model section title."""

    return {
        section.title: tuple(
            entry.cube_id
            for role_section in section.role_sections
            for entry in role_section.entries
        )
        for section in sections
    }
