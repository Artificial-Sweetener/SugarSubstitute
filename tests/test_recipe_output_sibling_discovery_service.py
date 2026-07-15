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

"""Tests for same-folder recipe output sibling discovery."""

from __future__ import annotations

from pathlib import Path

from substitute.application.generation import RecipeOutputSiblingDiscoveryService
from substitute.domain.generation import (
    OutputOrganizationPreferences,
)


class _OutputPreferences:
    """Output organization preference double for sibling discovery tests."""

    def __init__(self, path_pattern: str) -> None:
        """Store the active output filename pattern."""

        self._preferences = OutputOrganizationPreferences(path_pattern=path_pattern)

    def load_preferences(self) -> OutputOrganizationPreferences:
        """Return configured output organization preferences."""

        return self._preferences


def test_recipe_output_sibling_discovery_includes_selected_image(
    tmp_path: Path,
) -> None:
    """Filename discovery should restore the selected image with its siblings."""

    selected = tmp_path / "881_untitled_workflow_text_to_image.png"
    sibling = tmp_path / "881_untitled_workflow_diffusion_upscale.png"
    other_folder = tmp_path / "elsewhere"
    other_folder.mkdir()
    other = other_folder / "881_untitled_workflow_mask.png"
    for path in (selected, sibling, other):
        path.write_bytes(b"image")
    service = RecipeOutputSiblingDiscoveryService(
        output_preferences=_OutputPreferences("{workflow}\\{run}_{workflow}_{source}"),
    )

    result = service.discover_for_recipe_png(
        selected,
        workflow_name="Untitled Workflow",
    )

    assert result.strategy == "same_folder_pattern"
    assert [sibling.path for sibling in result.siblings] == [sibling, selected]
    assert [sibling.sequence for sibling in result.siblings] == [1, 2]
    assert [sibling.source_label for sibling in result.siblings] == [
        "Diffusion Upscale",
        "Text To Image",
    ]


def test_recipe_output_sibling_discovery_falls_back_to_same_folder_pattern(
    tmp_path: Path,
) -> None:
    """Pattern fallback should group same-run same-workflow files in one folder."""

    selected = tmp_path / "881_untitled_workflow_text_to_image.png"
    upscale = tmp_path / "881_untitled_workflow_diffusion_upscale.png"
    detailer = tmp_path / "881_untitled_workflow_automask_detailer.png"
    different_run = tmp_path / "882_untitled_workflow_text_to_image.png"
    different_workflow = tmp_path / "881_other_recipe_text_to_image.png"
    non_image = tmp_path / "881_untitled_workflow_notes.txt"
    nested = tmp_path / "nested"
    nested.mkdir()
    nested_sibling = nested / "881_untitled_workflow_nested.png"
    for path in (
        selected,
        upscale,
        detailer,
        different_run,
        different_workflow,
        non_image,
        nested_sibling,
    ):
        path.write_bytes(b"image")
    service = RecipeOutputSiblingDiscoveryService(
        output_preferences=_OutputPreferences("{workflow}\\{run}_{workflow}_{source}"),
    )

    result = service.discover_for_recipe_png(
        selected,
        workflow_name="Untitled Workflow",
    )

    assert result.strategy == "same_folder_pattern"
    assert [sibling.path for sibling in result.siblings] == [
        detailer,
        upscale,
        selected,
    ]
    assert [sibling.source_key for sibling in result.siblings] == [
        "automask_detailer",
        "diffusion_upscale",
        "text_to_image",
    ]


def test_recipe_output_sibling_discovery_supports_default_cube_number_pattern(
    tmp_path: Path,
) -> None:
    """Default cube-number filenames should still group same-run output siblings."""

    selected = tmp_path / "881_01_untitled_workflow_text_to_image.png"
    sibling = tmp_path / "881_02_untitled_workflow_diffusion_upscale.png"
    different_run = tmp_path / "882_01_untitled_workflow_text_to_image.png"
    for path in (selected, sibling, different_run):
        path.write_bytes(b"image")
    service = RecipeOutputSiblingDiscoveryService(
        output_preferences=_OutputPreferences(
            "{date}\\{run}_{cube#}_{workflow}_{source}"
        ),
    )

    result = service.discover_for_recipe_png(
        selected,
        workflow_name="Untitled Workflow",
    )

    assert [sibling.path for sibling in result.siblings] == [selected, sibling]
    assert [sibling.source_key for sibling in result.siblings] == [
        "text_to_image",
        "diffusion_upscale",
    ]


def test_recipe_output_sibling_discovery_skips_unsupported_patterns(
    tmp_path: Path,
) -> None:
    """Unsupported active patterns should fail closed with no fallback siblings."""

    selected = tmp_path / "881_untitled_workflow_text_to_image.png"
    selected.write_bytes(b"image")
    service = RecipeOutputSiblingDiscoveryService(
        output_preferences=_OutputPreferences("{workflow}\\{run}_{workflow}"),
    )

    result = service.discover_for_recipe_png(
        selected,
        workflow_name="Untitled Workflow",
    )

    assert result.strategy == "same_folder_pattern"
    assert result.siblings == ()
    assert result.warnings == ("unsupported_pattern_tokens",)


def test_recipe_output_sibling_discovery_uses_expected_workflow_token(
    tmp_path: Path,
) -> None:
    """Workflow names should disambiguate workflow/source filename boundaries."""

    selected = tmp_path / "881_untitled_workflow_text_to_image.png"
    sibling = tmp_path / "881_untitled_workflow_diffusion_upscale.png"
    ambiguous = tmp_path / "881_untitled_workflow_text_to_image_extra.png"
    selected.write_bytes(b"image")
    sibling.write_bytes(b"image")
    ambiguous.write_bytes(b"image")
    service = RecipeOutputSiblingDiscoveryService(
        output_preferences=_OutputPreferences("{workflow}\\{run}_{workflow}_{source}"),
    )

    result = service.discover_for_recipe_png(
        selected,
        workflow_name="Untitled Workflow",
    )

    assert [sibling.path for sibling in result.siblings] == [
        sibling,
        selected,
        ambiguous,
    ]
    assert [sibling.source_key for sibling in result.siblings] == [
        "diffusion_upscale",
        "text_to_image",
        "text_to_image_extra",
    ]
