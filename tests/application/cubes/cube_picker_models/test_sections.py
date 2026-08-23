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
    _record,
    _section_cube_ids_by_title,
    _source,
    build_cube_picker_sections,
    classify_cube_document,
)


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


def test_classify_cube_document_reads_supported_model_metadata() -> None:
    """Picker classifications should include cube-supported model claims."""

    classification = classify_cube_document(
        {
            "metadata": {"supported_models": [" SDXL 1.0 ", "", "sdxl 1.0"]},
            "implementation": {"inputs": {"image": {}}, "outputs": {"image": {}}},
        }
    )

    assert classification.supported_models == ("SDXL 1.0",)
