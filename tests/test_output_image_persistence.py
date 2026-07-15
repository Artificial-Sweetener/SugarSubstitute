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

"""Tests for Comfy output image persistence."""

from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, cast

import pytest

from substitute.application.ports.comfy_gateway import OutputSavePlan
from substitute.infrastructure.comfy import output_image_persistence
from substitute.infrastructure.comfy.output_image_persistence import (
    OutputImagePersistence,
    workflow_metadata_json,
)
from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceIdentity,
)


class _Image:
    """Record saved image paths while exposing deterministic dimensions."""

    width = 640
    height = 480

    def __init__(self, saved_paths: list[str]) -> None:
        """Initialize with the list that receives saved paths."""

        self._saved_paths = saved_paths

    def __enter__(self) -> "_Image":
        """Return this fake image for context-manager use."""

        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        tb: object,
    ) -> Literal[False]:
        """Do not suppress image persistence failures."""

        return False

    def save(self, path: str, pnginfo: object | None = None) -> None:
        """Record the target path and ignore encoded metadata details."""

        del pnginfo
        self._saved_paths.append(path)


class _PngInfo:
    """Collect PNG text metadata written by persistence."""

    records: list[tuple[str, str]] = []

    def add_text(self, key: str, value: str) -> None:
        """Record one metadata key/value pair."""

        self.records.append((key, value))


def test_output_image_persistence_module_keeps_infrastructure_boundary() -> None:
    """Output persistence must not import Qt, presentation, or listener code."""

    source_path = (
        Path(__file__).parents[1]
        / "substitute"
        / "infrastructure"
        / "comfy"
        / "output_image_persistence.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden_roots = {
        "PySide6",
        "qfluentwidgets",
        "qframelesswindow",
        "substitute.presentation",
        "substitute.infrastructure.comfy.websocket_listener",
    }

    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    assert not {
        module
        for module in imported_modules
        for forbidden in forbidden_roots
        if module == forbidden or module.startswith(f"{forbidden}.")
    }


def test_workflow_metadata_json_returns_wrapped_ui_workflow() -> None:
    """Workflow metadata should be compact JSON only when a UI workflow exists."""

    workflow = {"version": 0.4, "nodes": [{"id": 1}]}

    assert workflow_metadata_json({"workflow": workflow}) == json.dumps(
        workflow,
        separators=(",", ":"),
    )
    assert workflow_metadata_json({"prompt": {}}) is None


def test_persist_output_image_uses_reserved_run_number_and_png_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Reserved output run numbers should bypass bucket scans and write metadata."""

    saved_paths: list[str] = []
    counter_calls: list[str] = []
    _PngInfo.records = []
    persistence_module = cast(Any, output_image_persistence)
    monkeypatch.setattr(
        persistence_module.Image,
        "open",
        lambda _stream: _Image(saved_paths),
    )
    monkeypatch.setattr(persistence_module.PngImagePlugin, "PngInfo", _PngInfo)

    def _record_unexpected_bucket_scan(path: str) -> int:
        counter_calls.append(path)
        return 99

    monkeypatch.setattr(
        output_image_persistence,
        "get_next_bucket_run_number",
        _record_unexpected_bucket_scan,
    )
    ui_workflow = {"version": 0.4, "nodes": [{"id": 1}]}
    persistence = OutputImagePersistence(
        output_save_plan=OutputSavePlan(
            output_root=tmp_path,
            path_pattern="{run}_{cube#}_{workflow}_{source}_{set}",
            workflow_name="My Workflow",
            output_run_number=12,
            job_started_at=datetime(2026, 5, 1, 14, 32, 9),
        ),
        workflow_payload={"workflow": ui_workflow},
        sugar_script="line one",
        cube_numbers_by_alias={"CubeA": 4},
    )

    persisted = persistence.persist_output_image(
        image_bytes=b"fake-png",
        source_identity=OutputSourceIdentity(
            node_id="output-node",
            source_key="wf-1:output-node",
            source_label="CubeA",
            cube_alias="CubeA",
        ),
    )

    expected_path = tmp_path / "012_04_my_workflow_cubea_1.png"
    assert persisted.file_path == expected_path
    assert persisted.width == 640
    assert persisted.height == 480
    assert saved_paths == [str(expected_path)]
    assert counter_calls == []
    assert _PngInfo.records == [
        ("sugar_script", "# Project: My Workflow\n\nline one"),
        ("workflow", json.dumps(ui_workflow, separators=(",", ":"))),
    ]


def test_persist_output_image_allocates_lazy_run_and_source_ordinals(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Lazy run allocation should happen once while source ordinals increment."""

    saved_paths: list[str] = []
    bucket_calls: list[str] = []
    persistence_module = cast(Any, output_image_persistence)
    monkeypatch.setattr(
        persistence_module.Image,
        "open",
        lambda _stream: _Image(saved_paths),
    )
    monkeypatch.setattr(persistence_module.PngImagePlugin, "PngInfo", _PngInfo)

    def _record_bucket_scan(path: str) -> int:
        bucket_calls.append(path)
        return 7

    monkeypatch.setattr(
        output_image_persistence,
        "get_next_bucket_run_number",
        _record_bucket_scan,
    )
    persistence = OutputImagePersistence(
        output_save_plan=OutputSavePlan(
            output_root=tmp_path,
            path_pattern="{date}\\{run}_{source}_{set}",
            workflow_name="My Workflow",
            output_run_number=None,
            job_started_at=datetime(2026, 5, 1, 14, 32, 9),
        ),
        workflow_payload={},
        sugar_script="line one",
        cube_numbers_by_alias={},
    )
    source_identity = OutputSourceIdentity(
        node_id="output-node",
        source_key="wf-1:output-node",
        source_label="CubeA",
        cube_alias="CubeA",
    )

    first = persistence.persist_output_image(
        image_bytes=b"fake-png",
        source_identity=source_identity,
    )
    second = persistence.persist_output_image(
        image_bytes=b"fake-png",
        source_identity=source_identity,
    )

    assert first.file_path == tmp_path / "2026-05-01" / "007_cubea_1.png"
    assert second.file_path == tmp_path / "2026-05-01" / "007_cubea_2.png"
    assert saved_paths == [str(first.file_path), str(second.file_path)]
    assert bucket_calls == [str(tmp_path / "2026-05-01")]


def test_persist_output_image_allocates_folder_image_number(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Folder image numbers should scan the rendered output folder."""

    saved_paths: list[str] = []
    existing = tmp_path / "2026-05-01" / "image_01_cubea.png"
    existing.parent.mkdir(parents=True)
    existing.write_text("", encoding="utf-8")
    persistence_module = cast(Any, output_image_persistence)
    monkeypatch.setattr(
        persistence_module.Image,
        "open",
        lambda _stream: _Image(saved_paths),
    )
    monkeypatch.setattr(persistence_module.PngImagePlugin, "PngInfo", _PngInfo)
    persistence = OutputImagePersistence(
        output_save_plan=OutputSavePlan(
            output_root=tmp_path,
            path_pattern="{date}\\Image {image#}_{source}",
            workflow_name="My Workflow",
            output_run_number=12,
            job_started_at=datetime(2026, 5, 1, 14, 32, 9),
        ),
        workflow_payload={},
        sugar_script="line one",
        cube_numbers_by_alias={},
    )

    persisted = persistence.persist_output_image(
        image_bytes=b"fake-png",
        source_identity=OutputSourceIdentity(
            node_id="output-node",
            source_key="wf-1:output-node",
            source_label="CubeA",
            cube_alias="CubeA",
        ),
    )

    assert persisted.file_path == tmp_path / "2026-05-01" / "image_02_cubea.png"
    assert saved_paths == [str(persisted.file_path)]
