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

"""Verify Output canvas preview-retirement host adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from uuid import UUID

import pytest

from substitute.application.workflows.output_preview_lifecycle_service import (
    OutputCanvasRevisionCache,
    PreviewSlotKey,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewLane,
    OutputPreviewLaneKey,
    OutputPreviewRegistry,
)
from substitute.domain.workflow import CanvasSessionRevision
from substitute.presentation.canvas.output import output_canvas_preview_retirement


def test_retire_output_preview_id_removes_registry_lane_and_logs_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Single-preview retirement should execute host effects and diagnostics."""

    preview_id = UUID(int=1)
    registry = OutputPreviewRegistry()
    cache = OutputCanvasRevisionCache(registry=registry, session=None)
    cache.active_preview_generation_run_id = "run"
    registry.store_accepted_lane(
        _source_lane(
            preview_id=preview_id,
            source_key="wf:upscale",
            source_label="Upscale",
        )
    )
    asset_lookup = _PreviewAssetLookup({preview_id: object()})
    presenter = _PreviewPanePresenter()
    host = SimpleNamespace(
        _asset_lookup=asset_lookup,
        _qpane_presenter=presenter,
        _preview_registry=registry,
        _revision_cache=cache,
        _projection_workflow_id="wf",
    )
    logs: list[dict[str, object]] = []
    monkeypatch.setattr(
        output_canvas_preview_retirement,
        "log_debug",
        lambda _logger, _message, **context: logs.append(context),
    )

    output_canvas_preview_retirement.retire_output_preview_id(
        host,
        preview_id,
        retire_reason="final_output_registered",
        scene_run_id="scene-run",
        scene_key="portrait",
        source_key="wf:upscale",
        set_index=1,
    )

    assert registry.lane_for_id(preview_id) is None
    assert presenter.removed_image_ids == [preview_id]
    assert preview_id not in asset_lookup.preview_images_by_id
    assert logs == [
        {
            "preview_id": preview_id,
            "retire_reason": "final_output_registered",
            "workflow_id": "wf",
            "generation_run_id": "run",
            "scene_run_id": "scene-run",
            "scene_key": "portrait",
            "source_key": "wf:upscale",
            "set_index": 1,
            "removed_source_key_count": 1,
            "removed_source_slot_count": 1,
            "removed_scene_slot_count": 0,
            "removed_accepted_scene_count": 0,
            "removed_preview_scene_group_count": 0,
            "updated_preview_scene_group_count": 0,
        }
    ]


def test_retire_output_previews_for_completed_slot_removes_scene_and_source_lanes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Completed-slot retirement should execute every planned preview removal."""

    scene_preview_id = UUID(int=1)
    source_preview_id = UUID(int=2)
    registry = OutputPreviewRegistry()
    cache = OutputCanvasRevisionCache(registry=registry, session=None)
    registry.store_accepted_lane(
        _scene_lane(
            preview_id=scene_preview_id,
            source_key="wf:upscale",
            source_label="Upscale",
        )
    )
    registry.store_accepted_lane(
        _source_lane(
            preview_id=source_preview_id,
            source_key="wf:upscale",
            source_label="Upscale",
        )
    )
    asset_lookup = _PreviewAssetLookup(
        {scene_preview_id: object(), source_preview_id: object()}
    )
    presenter = _PreviewPanePresenter()
    host = SimpleNamespace(
        _asset_lookup=asset_lookup,
        _qpane_presenter=presenter,
        _preview_registry=registry,
        _revision_cache=cache,
        _projection_workflow_id="wf",
    )
    monkeypatch.setattr(
        output_canvas_preview_retirement,
        "log_debug",
        lambda _logger, _message, **_context: None,
    )

    output_canvas_preview_retirement.retire_output_previews_for_completed_slot(
        host,
        PreviewSlotKey(
            scene_run_id="scene-run",
            generation_run_id="run",
            scene_key="portrait",
            source_key="wf:upscale",
            set_index=1,
        ),
        source_label="Upscale",
        retire_reason="final_output_registered",
    )

    assert registry.lane_for_id(scene_preview_id) is None
    assert registry.lane_for_id(source_preview_id) is None
    assert set(presenter.removed_image_ids) == {scene_preview_id, source_preview_id}
    assert asset_lookup.preview_images_by_id == {}


@dataclass(slots=True)
class _PreviewAssetLookup:
    """Hold mutable preview assets for adapter tests."""

    preview_images_by_id: dict[UUID, object]

    def preview_images(self) -> dict[UUID, object]:
        """Return the mutable preview image map."""

        return self.preview_images_by_id


@dataclass(slots=True)
class _PreviewPanePresenter:
    """Record QPane image removals for adapter tests."""

    removed_image_ids: list[UUID] = field(default_factory=list)

    def remove_image(self, image_id: UUID) -> None:
        """Record one removed image id."""

        self.removed_image_ids.append(image_id)


def _source_lane(
    *,
    preview_id: UUID,
    source_key: str,
    source_label: str,
) -> OutputPreviewLane:
    """Return one source preview lane for the standard scene slot."""

    return OutputPreviewLane(
        key=OutputPreviewLaneKey.source(
            workflow_id="wf",
            generation_run_id="run",
            prompt_id="prompt",
            source_key=source_key,
            scene_run_id="scene-run",
            scene_key="portrait",
        ),
        preview_id=preview_id,
        image=object(),
        source_label=source_label,
        client_id="client",
        session_revision=CanvasSessionRevision(1),
    )


def _scene_lane(
    *,
    preview_id: UUID,
    source_key: str,
    source_label: str,
) -> OutputPreviewLane:
    """Return one scene preview lane for the standard scene slot."""

    return OutputPreviewLane(
        key=OutputPreviewLaneKey.scene(
            workflow_id="wf",
            generation_run_id="run",
            prompt_id="prompt",
            source_key=source_key,
            scene_run_id="scene-run",
            scene_key="portrait",
        ),
        preview_id=preview_id,
        image=object(),
        source_label=source_label,
        client_id="client",
        session_revision=CanvasSessionRevision(1),
        scene_title="Portrait",
        scene_order=1,
        accepted_for_overview=True,
    )
