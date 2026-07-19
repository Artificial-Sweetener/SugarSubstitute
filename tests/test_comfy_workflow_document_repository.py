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

"""Verify direct Comfy workflow loading from JSON files and PNG metadata."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image, PngImagePlugin

from substitute.infrastructure.comfy.workflow_document_repository import (
    ComfyWorkflowDocumentRepository,
)


def _workflow_payload() -> dict[str, object]:
    """Return a minimal Comfy UI workflow document."""

    return {"nodes": [], "links": []}


def _write_png(path: Path, **metadata: str) -> None:
    """Write a small PNG carrying the supplied text metadata."""

    png_info = PngImagePlugin.PngInfo()
    for key, value in metadata.items():
        png_info.add_text(key, value)
    Image.new("RGB", (1, 1)).save(path, pnginfo=png_info)


def test_repository_loads_comfy_workflow_json(tmp_path: Path) -> None:
    """JSON files should remain supported as direct Comfy workflows."""

    source = tmp_path / "workflow.json"
    source.write_text(json.dumps(_workflow_payload()), encoding="utf-8")
    repository = ComfyWorkflowDocumentRepository()

    assert repository.can_load(source) is True
    assert repository.load(source) == _workflow_payload()


def test_repository_loads_workflow_only_png_metadata(tmp_path: Path) -> None:
    """A PNG workflow should load when no SugarScript metadata is attached."""

    source = tmp_path / "workflow.png"
    _write_png(source, workflow=json.dumps(_workflow_payload()))
    repository = ComfyWorkflowDocumentRepository()

    assert repository.can_load(source) is True
    assert repository.load(source) == _workflow_payload()


def test_repository_rejects_png_workflow_when_sugar_script_is_attached(
    tmp_path: Path,
) -> None:
    """SugarScript metadata should make the direct Comfy load path unavailable."""

    source = tmp_path / "first-party.png"
    _write_png(
        source,
        sugar_script="",
        workflow=json.dumps(_workflow_payload()),
    )
    repository = ComfyWorkflowDocumentRepository()

    assert repository.can_load(source) is False
    with pytest.raises(ValueError, match="SugarScript"):
        repository.load(source)


def test_repository_rejects_png_without_supported_workflow_metadata(
    tmp_path: Path,
) -> None:
    """Generic PNG files should not enter the direct Comfy workflow loader."""

    source = tmp_path / "plain.png"
    _write_png(source, prompt=json.dumps({"1": {}}))
    repository = ComfyWorkflowDocumentRepository()

    assert repository.can_load(source) is False
    with pytest.raises(ValueError, match="embedded Comfy workflow"):
        repository.load(source)
