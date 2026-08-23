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

"""Verify workflow export persistence orchestration."""

from __future__ import annotations

from pathlib import Path

from tests.application.recipes.workflow_export.support import build_service


def test_workflow_export_service_compiles_and_persists_json() -> None:
    """Compile a workflow payload before persisting it through the repository."""
    expected_payload: dict[str, object] = {
        "1": {"class_type": "KSampler", "inputs": {"steps": 20}}
    }
    service, repository, compiler = build_service(expected_payload)
    destination = Path("recipes") / "export.json"
    output_dir = Path("projects")

    payload = service.export_workflow_json(
        destination_path=destination,
        sugar_script_text="use Cube as A",
        output_dir=output_dir,
    )

    assert compiler.calls == [("use Cube as A", output_dir)]
    assert payload == expected_payload
    assert repository.saved == [(destination, expected_payload)]
