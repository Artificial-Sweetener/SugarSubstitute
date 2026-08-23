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

"""Verify workflow export destination policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.application.recipes.workflow_export.support import build_service


def test_build_default_export_path_uses_project_folder(tmp_path: Path) -> None:
    """Place the default export beside its workflow recipe."""
    service, _repository, _compiler = build_service()

    destination = service.build_default_export_path("Recipe Export", tmp_path)

    assert destination == (tmp_path / "Recipe Export" / "Recipe Export.json").resolve()


def test_validate_export_destination_accepts_paths_outside_output_root(
    tmp_path: Path,
) -> None:
    """Accept an explicit destination outside the default output root."""
    service, _repository, _compiler = build_service()

    destination = service.validate_export_destination(tmp_path.parent / "external.json")

    assert destination == (tmp_path.parent / "external.json").resolve()


def test_validate_export_destination_rejects_directory_paths(tmp_path: Path) -> None:
    """Reject an existing directory as an export destination."""
    service, _repository, _compiler = build_service()

    with pytest.raises(ValueError, match="Workflow export"):
        service.validate_export_destination(tmp_path)


def test_validate_export_destination_rejects_non_json_paths(tmp_path: Path) -> None:
    """Reject destinations without a JSON suffix."""
    service, _repository, _compiler = build_service()

    with pytest.raises(ValueError, match=r"\.json"):
        service.validate_export_destination(tmp_path / "workflow.txt")
