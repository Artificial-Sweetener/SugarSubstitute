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

"""Verify Output canvas final and preview asset lookup."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from substitute.presentation.canvas.output.output_canvas_asset_lookup import (
    OutputCanvasAssetLookup,
)
from substitute.presentation.canvas.shared.types import OutputImageMeta


def test_set_final_output_lookup_installs_payload_and_metadata_callbacks() -> None:
    """Lookup installation should update the owner-held callbacks."""

    image_id = uuid4()
    payload = object()
    metadata = _meta("E:/out.png")

    lookup = OutputCanvasAssetLookup()

    lookup.set_final_output_lookup(
        payload_lookup=lambda candidate_id: (
            payload if candidate_id == image_id else None
        ),
        metadata_lookup=lambda candidate_id: (
            metadata if candidate_id == image_id else None
        ),
    )

    assert lookup.final_output_payload(image_id) is payload
    assert lookup.final_output_metadata(image_id) is metadata


def test_scene_request_layer_payload_prefers_preview_cache_for_preview_layers() -> None:
    """Preview layers should resolve payloads from transient preview cache."""

    preview_id = uuid4()
    final_id = uuid4()
    preview_payload = object()
    final_payload = object()
    lookup = OutputCanvasAssetLookup(
        payload_lookup=lambda image_id: final_payload if image_id == final_id else None,
        preview_image_cache=lambda: {preview_id: preview_payload},
    )

    assert (
        lookup.scene_request_layer_payload(
            SimpleNamespace(image_id=preview_id, metadata={"preview": True})
        )
        is preview_payload
    )
    assert (
        lookup.scene_request_layer_payload(
            SimpleNamespace(image_id=final_id, metadata={"preview": False})
        )
        is final_payload
    )


def test_scene_request_layer_path_uses_final_output_metadata_only() -> None:
    """Preview layers should not expose final-output filesystem paths."""

    image_id = uuid4()
    lookup = OutputCanvasAssetLookup(
        metadata_lookup=lambda candidate_id: (
            _meta("E:/out.png") if candidate_id == image_id else None
        ),
    )

    assert (
        lookup.scene_request_layer_path(
            SimpleNamespace(image_id=image_id, metadata={"preview": True})
        )
        is None
    )
    assert str(
        lookup.scene_request_layer_path(SimpleNamespace(image_id=image_id, metadata={}))
    ) == str(Path("E:/out.png"))


def _meta(path: str) -> OutputImageMeta:
    """Return minimal metadata matching the Output image protocol."""

    return SimpleNamespace(
        workflow_name="Workflow",
        cube_name="Output",
        image_number=1,
        suffix="",
        path=path,
        source_key="source-a",
        source_label="Source A",
        generation_run_id="run-a",
        prompt_id="prompt-a",
        client_id="client-a",
        scene_run_id="",
        scene_key="",
        scene_title="",
        scene_order=None,
        scene_count=None,
        width=None,
        height=None,
        cube_execution_duration_ms=None,
    )
