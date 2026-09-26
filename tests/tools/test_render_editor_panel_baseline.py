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

"""Test deterministic editor-panel baseline rendering contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.editor_panel_baseline.environment import runtime_environment
from tools.editor_panel_baseline.rendering import scroll_capture_values
from tools.editor_panel_baseline.sources import validate_base_cube_sources
from tools.editor_projection_rig.scenarios import WORKFLOW_SDXL_BASELINE


def test_runtime_environment_records_reproduction_versions() -> None:
    """Render manifests must identify the environment needed for comparison."""

    environment = runtime_environment()

    assert set(environment) == {
        "mypy",
        "platform",
        "pyside6",
        "pytest",
        "python",
        "python_executable",
        "qt",
        "ruff",
    }
    assert all(environment.values())


def test_scroll_capture_values_resolve_named_viewport_positions() -> None:
    """Named captures must remain stable across baseline and comparison runs."""

    assert scroll_capture_values(
        maximum=901,
        position_names=("top", "middle", "bottom"),
    ) == (("top", 0), ("middle", 450), ("bottom", 901))


def test_scroll_capture_values_reject_unknown_positions() -> None:
    """A misspelled position must fail rather than capture misleading evidence."""

    with pytest.raises(ValueError, match="Unknown editor baseline position"):
        scroll_capture_values(maximum=10, position_names=("center",))


def test_base_cube_validation_rejects_fixture_source_version_drift(
    tmp_path: Path,
) -> None:
    """A stale fixture must not be presented as a current Base-Cubes baseline."""

    fixtures = tmp_path / "fixtures"
    base_cubes = tmp_path / "Base-Cubes"
    fixtures.mkdir()
    source = base_cubes / "SDXL" / "Text to Image.cube"
    source.parent.mkdir(parents=True)
    source.write_text(
        json.dumps(
            {
                "cube_id": ("Artificial-Sweetener/Base-Cubes/SDXL/Text to Image.cube"),
                "version": "2.0.0",
            }
        ),
        encoding="utf-8",
    )
    (fixtures / "workflow_sdxl_baseline.json").write_text(
        json.dumps(
            {
                "cubes": [
                    {
                        "cube_id": (
                            "Artificial-Sweetener/Base-Cubes/SDXL/Text to Image.cube"
                        ),
                        "version": "1.0.0",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Fixture/source mismatch"):
        validate_base_cube_sources(
            scenarios=(WORKFLOW_SDXL_BASELINE,),
            fixtures_dir=fixtures,
            base_cubes_dir=base_cubes,
        )
