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

"""Contract tests for shared canvas image payload and metadata storage."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows import CanvasImageRegistry
from substitute.domain.workflow import ImageMeta


def _metadata() -> ImageMeta:
    """Build metadata carrying every projection-critical output field."""

    return ImageMeta(
        workflow_name="Workflow",
        cube_name="Cube",
        image_number=7,
        suffix="final",
        path="E:/outputs/007_final.png",
        source_key="workflow:cube-output",
        source_label="Cube Output",
        generation_run_id="run-1",
        prompt_id="prompt-1",
        client_id="client-1",
        scene_run_id="scene-run-1",
        scene_key="scene-a",
        scene_title="Scene A",
        scene_order=2,
        scene_count=4,
        width=640,
        height=480,
        list_index=3,
        cube_execution_duration_ms=1234.5,
    )


def test_registry_stores_payload_and_projection_metadata_by_uuid() -> None:
    """Stored records should preserve payload identity and output routing facts."""

    registry = CanvasImageRegistry()
    image_id = uuid4()
    payload = object()
    metadata = _metadata()

    registry.store(image_id, payload=payload, metadata=metadata)

    assert registry.payload_for(image_id) is payload
    assert registry.metadata_for(image_id) is metadata
    assert registry.payload_identity_for(image_id) == id(payload)
    stored = registry.metadata_for(image_id)
    assert stored is not None
    assert stored.generation_run_id == "run-1"
    assert stored.prompt_id == "prompt-1"
    assert stored.client_id == "client-1"
    assert stored.source_key == "workflow:cube-output"
    assert stored.scene_key == "scene-a"
    assert stored.width == 640
    assert stored.height == 480
    assert stored.path == "E:/outputs/007_final.png"
    assert stored.list_index == 3
    assert stored.cube_execution_duration_ms == 1234.5


def test_registry_returns_filtered_payload_and_metadata_lookups() -> None:
    """Bulk lookup helpers should omit UUIDs without matching records."""

    registry = CanvasImageRegistry()
    image_id = uuid4()
    missing_id = uuid4()
    payload = object()
    metadata = _metadata()

    registry.store(image_id, payload=payload, metadata=metadata)

    assert registry.payloads_for((missing_id, image_id)) == {image_id: payload}
    assert registry.metadata_for_ids((missing_id, image_id)) == {image_id: metadata}


def test_registry_hydrates_payload_for_existing_metadata_record() -> None:
    """Catalog-derived payload hydration should not replace metadata."""

    registry = CanvasImageRegistry()
    image_id = uuid4()
    payload = object()
    metadata = _metadata()
    missing_id = uuid4()

    registry.store(image_id, payload=None, metadata=metadata)

    assert registry.remember_payload(missing_id, object()) is False
    assert registry.remember_payload(image_id, payload) is True
    assert registry.payload_for(image_id) is payload
    assert registry.metadata_for(image_id) is metadata


def test_registry_remove_drops_payload_and_metadata_without_policy() -> None:
    """Removing a UUID should delete only the registry record."""

    registry = CanvasImageRegistry()
    image_id = uuid4()
    registry.store(image_id, payload=object(), metadata=_metadata())

    assert image_id in registry
    assert registry.remove(image_id) is True
    assert registry.remove(image_id) is False
    assert image_id not in registry
    assert registry.payload_for(image_id) is None
    assert registry.metadata_for(image_id) is None
