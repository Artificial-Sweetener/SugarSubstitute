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

"""Tests for live cube-stack metadata tooltip formatting."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from substitute.application.cubes import (
    build_cube_stack_tooltip_text,
    cube_stack_tooltip_metadata_from_state,
)


def test_cube_stack_tooltip_formats_requested_metadata_lines() -> None:
    """Tooltip text should show the requested human metadata before details."""

    metadata = cube_stack_tooltip_metadata_from_state(
        alias="Workflow Alias",
        cube_state=_cube_state(
            canonical_cube={
                "cube_id": "ArtificialSweetener/Base-Cubes/Upscale.cube",
                "version": "1.2.3",
                "description": "Improves image resolution while preserving detail.",
                "metadata": {
                    "default_alias": "Diffusion Upscale",
                    "supported_models": ["SDXL 1.0", "SD 1.5"],
                    "tags": ["upscale", "detailer"],
                },
            },
            source={"repo_ref": "ArtificialSweetener/Base-Cubes"},
        ),
    )

    tooltip = build_cube_stack_tooltip_text(metadata)

    assert "<b>Diffusion Upscale</b>, v1.2.3" in tooltip
    assert "Base-Cubes by ArtificialSweetener" in tooltip
    assert "<b>Supported models:</b> SDXL 1.0, SD 1.5" in tooltip
    assert "<b>Description:</b> Improves image resolution" in tooltip
    assert "<b>Tags:</b> upscale, detailer" in tooltip


def test_cube_stack_tooltip_prefers_default_alias_over_workflow_alias() -> None:
    """Canonical default alias should be shown before workflow-local alias."""

    metadata = cube_stack_tooltip_metadata_from_state(
        alias="Workflow Alias",
        cube_state=_cube_state(
            display_name="Display Alias",
            canonical_cube={
                "cube_id": "Author/Pack/Cube.cube",
                "version": "v2",
                "metadata": {"default_alias": "Canonical Alias"},
            },
        ),
    )

    assert metadata.default_alias == "Canonical Alias"
    assert metadata.version == "v2"


def test_cube_stack_tooltip_omits_missing_optional_fields() -> None:
    """Missing metadata should produce a compact fallback tooltip."""

    metadata = cube_stack_tooltip_metadata_from_state(
        alias="Alias",
        cube_state=_cube_state(cube_id="Cube.cube", version="", display_name=""),
    )

    tooltip = build_cube_stack_tooltip_text(metadata, rich_text=False)

    assert tooltip == "Alias"


def test_cube_stack_tooltip_normalizes_sequences_and_limits_list_values() -> None:
    """Model and tag lists should be deduped, trimmed, and compacted."""

    metadata = cube_stack_tooltip_metadata_from_state(
        alias="Alias",
        cube_state=_cube_state(
            canonical_cube={
                "cube_id": "Author/Pack/Cube.cube",
                "version": "1",
                "metadata": {
                    "supported_models": [
                        " SDXL ",
                        "",
                        "sdxl",
                        "Flux",
                        "SD 1.5",
                        "Pony",
                    ],
                    "tags": [" detailer ", "Detailer", "upscale", "latent", "img2img"],
                },
            },
        ),
    )

    tooltip = build_cube_stack_tooltip_text(metadata, rich_text=False)

    assert "Supported models: SDXL, Flux, SD 1.5 +1" in tooltip
    assert "Tags: detailer, upscale, latent +1" in tooltip


def test_cube_stack_tooltip_bounds_description_and_escapes_rich_text() -> None:
    """Long and authored values should fit and escape inside rich text."""

    description = "<script>" + ("long description " * 30)
    metadata = cube_stack_tooltip_metadata_from_state(
        alias="<Alias>",
        cube_state=_cube_state(
            canonical_cube={
                "cube_id": "Author/Pack/Cube.cube",
                "version": "1",
                "description": description,
                "metadata": {"default_alias": "<Default>", "tags": ["<tag>"]},
            },
        ),
    )

    tooltip = build_cube_stack_tooltip_text(metadata)

    assert tooltip.startswith(
        '<div style="max-width: 420px; width: 420px; white-space: normal; '
        'word-wrap: break-word; overflow-wrap: anywhere;">'
    )
    assert "&lt;Default&gt;" in tooltip
    assert "&lt;script&gt;" in tooltip
    assert "&lt;tag&gt;" in tooltip
    assert "<script>" not in tooltip
    assert "..." in tooltip
    assert len(metadata.description) <= 223


def test_cube_stack_tooltip_ignores_graph_payload_keys() -> None:
    """Graph structures should not leak into the cube stack tooltip."""

    metadata = cube_stack_tooltip_metadata_from_state(
        alias="Alias",
        cube_state=_cube_state(
            canonical_cube={
                "cube_id": "Author/Pack/Cube.cube",
                "version": "1",
                "metadata": {"default_alias": "Alias"},
                "implementation": {
                    "nodes": {"SecretNode": {"class_type": "ShouldNotLeak"}},
                    "definitions": {"Hidden": {}},
                },
            },
        ),
    )

    tooltip = build_cube_stack_tooltip_text(metadata, rich_text=False)

    assert "implementation" not in tooltip
    assert "nodes" not in tooltip
    assert "definitions" not in tooltip
    assert "SecretNode" not in tooltip


@pytest.mark.parametrize(
    ("cube_id", "expected"),
    [
        (
            "ArtificialSweetener/Base-Cubes/Cube.cube",
            "Base-Cubes by ArtificialSweetener",
        ),
        ("Author\\Pack\\Cube.cube", "Pack by Author"),
    ],
)
def test_cube_stack_tooltip_parses_pack_and_author_from_cube_id(
    cube_id: str,
    expected: str,
) -> None:
    """Cube ids should provide readable pack and author metadata."""

    metadata = cube_stack_tooltip_metadata_from_state(
        alias="Alias",
        cube_state=_cube_state(
            canonical_cube={
                "cube_id": cube_id,
                "version": "1",
                "metadata": {"default_alias": "Alias"},
            },
        ),
    )

    assert metadata.source_line == expected


def _cube_state(
    *,
    cube_id: str = "FallbackAuthor/FallbackPack/Cube.cube",
    version: str = "1.0.0",
    display_name: str = "Display Alias",
    canonical_cube: dict[str, object] | None = None,
    source: dict[str, object] | None = None,
) -> SimpleNamespace:
    """Build a cube-state double with optional UI metadata."""

    ui: dict[str, object] = {}
    if canonical_cube is not None:
        ui["canonical_cube"] = canonical_cube
    if source is not None:
        ui["source"] = source
    return SimpleNamespace(
        cube_id=cube_id,
        version=version,
        display_name=display_name,
        ui=ui or None,
    )
