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

"""Behavior tests for output preferences and memory-only final images."""

from __future__ import annotations

import io
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from PIL import Image
from PySide6.QtGui import QImage

from substitute.application.generation import (
    JpegOutputSettings,
    JpegSizingMode,
    OutputPersistenceMode,
    OutputPreferenceService,
)
from substitute.application.ports import OutputImageUpdate, OutputSavePlan
from substitute.application.workflows.output_visual_events import LiveFinalOutputEvent
from substitute.infrastructure.comfy.final_image_event import (
    FinalImageEvent,
    FinalImageSource,
)
from substitute.infrastructure.comfy.final_image_event_handler import (
    FinalImageEventHandler,
)
from substitute.infrastructure.comfy.image_artifact import ComfyImageArtifact
from substitute.infrastructure.comfy.output_image_persistence import (
    OutputImagePersistence,
)
from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceIdentity,
)
from substitute.infrastructure.persistence.file_output_preference_repository import (
    FileOutputPreferenceRepository,
)
from substitute.presentation.shell.output_image_commit_pipeline import (
    OutputImageCommitRequest,
    PreparedOutputImage,
)
from substitute.presentation.shell.output_image_preparation_dispatcher import (
    prepare_output_image,
)


def test_final_only_policy_uses_active_topology_and_explicit_mute_wins(
    tmp_path: Path,
) -> None:
    """Final means the last active cube, while an explicit final mute saves nothing."""

    repository = FileOutputPreferenceRepository(tmp_path / "settings")
    service = OutputPreferenceService(repository, default_output_root=tmp_path)
    service.save_preferences(
        replace(
            service.load_preferences(),
            persistence_mode=OutputPersistenceMode.FINAL_CUBE,
        )
    )

    plan = service.create_save_plan(
        workflow_name="Workflow",
        output_run_number=1,
        job_started_at=datetime(2026, 7, 18),
        active_cube_aliases=("First", "Bypassed", "Final"),
        muted_cube_aliases=frozenset({"Bypassed"}),
    )

    assert plan.persists_cube("First") is False
    assert plan.persists_cube("Bypassed") is False
    assert plan.persists_cube("Final") is True

    muted_final_plan = service.create_save_plan(
        workflow_name="Workflow",
        output_run_number=1,
        job_started_at=datetime(2026, 7, 18),
        active_cube_aliases=("First", "Final"),
        muted_cube_aliases=frozenset({"Final"}),
    )

    assert muted_final_plan.persists_cube("First") is False
    assert muted_final_plan.persists_cube("Final") is False


def test_canonical_png_keeps_recipe_and_optional_jpeg_is_same_stem(
    tmp_path: Path,
) -> None:
    """JPEG is an additional derivative; the PNG remains recipe-bearing."""

    persistence = OutputImagePersistence(
        output_save_plan=OutputSavePlan(
            output_root=tmp_path,
            path_pattern="{workflow}_{source}",
            workflow_name="My Workflow",
            output_run_number=1,
            job_started_at=datetime(2026, 7, 18),
            jpeg=JpegOutputSettings(enabled=True, quality=82),
        ),
        workflow_payload={"workflow": {"nodes": [{"id": 1}]}},
        sugar_script="use cube as Main",
        cube_numbers_by_alias={},
    )

    result = persistence.persist_output_image(
        image_bytes=_png_bytes(),
        source_identity=_source_identity("Main"),
    )

    assert result.file_path is not None
    jpeg_path = result.file_path.with_suffix(".jpg")
    assert result.file_path.is_file()
    assert jpeg_path.is_file()
    with Image.open(result.file_path) as png:
        assert png.info["sugar_script"].endswith("use cube as Main")
        assert "workflow" in png.info
    with Image.open(jpeg_path) as jpeg:
        assert jpeg.format == "JPEG"
        assert jpeg.size == (64, 48)


def test_target_size_jpeg_encoder_produces_bounded_derivative(
    tmp_path: Path,
) -> None:
    """Target-size mode should search quality without changing the canonical PNG."""

    persistence = OutputImagePersistence(
        output_save_plan=OutputSavePlan(
            output_root=tmp_path,
            path_pattern="target",
            workflow_name="Workflow",
            output_run_number=1,
            job_started_at=datetime(2026, 7, 18),
            jpeg=JpegOutputSettings(
                enabled=True,
                sizing_mode=JpegSizingMode.TARGET_SIZE,
                target_size_kib=4,
            ),
        ),
        workflow_payload={},
        sugar_script="recipe",
        cube_numbers_by_alias={},
    )

    result = persistence.persist_output_image(
        image_bytes=_png_bytes(width=256, height=256),
        source_identity=_source_identity("Main"),
    )

    assert result.file_path is not None
    assert result.file_path.with_suffix(".jpg").stat().st_size <= 4 * 1024
    with Image.open(result.file_path) as png:
        assert png.size == (256, 256)


def test_memory_only_final_image_still_reaches_decoded_canvas_commit() -> None:
    """No durable path must never prevent a valid final image from reaching canvas."""

    image_bytes = _png_bytes()
    updates: list[OutputImageUpdate] = []
    handler = FinalImageEventHandler(
        artifact_fetcher=_StaticFetcher(image_bytes),
        output_persistence=_MemoryOnlyPersistence(),
        on_output_image=updates.append,
    )
    handler.handle(
        FinalImageEvent(
            workflow_id="workflow",
            generation_run_id="run",
            prompt_id="prompt",
            client_id="client",
            workflow_payload={},
            source=FinalImageSource(
                node_id="node",
                source_key="workflow:node",
                source_label="Main",
                cube_alias="Main",
            ),
            artifacts=(
                ComfyImageArtifact(
                    filename="image.png",
                    subfolder="",
                    type="output",
                    width=64,
                    height=48,
                ),
            ),
            list_index=0,
        )
    )

    assert len(updates) == 1
    update = updates[0]
    assert update.file_path is None
    assert update.image_bytes == image_bytes
    live_event = LiveFinalOutputEvent.from_update(update)
    assert live_event is not None
    request = _commit_request_from_event(live_event)
    prepared = prepare_output_image(request, loader=_NeverDiskLoader())
    assert isinstance(prepared, PreparedOutputImage)
    assert prepared.image.width() == 64
    assert prepared.image.height() == 48


class _StaticFetcher:
    """Return deterministic in-memory artifact bytes."""

    def __init__(self, image_bytes: bytes) -> None:
        self._image_bytes = image_bytes

    def fetch(self, artifact: ComfyImageArtifact) -> bytes:
        """Return the prepared bytes for any artifact."""

        del artifact
        return self._image_bytes


class _MaterializedMemoryOnlyImage:
    """Expose dimensions without a durable file path."""

    file_path: Path | None = None
    width = 64
    height = 48


class _MemoryOnlyPersistence:
    """Represent a policy decision that skips durable persistence."""

    def persist_output_image(
        self,
        *,
        image_bytes: bytes,
        source_identity: OutputSourceIdentity,
    ) -> _MaterializedMemoryOnlyImage:
        """Return decoded facts without writing a file."""

        del image_bytes, source_identity
        return _MaterializedMemoryOnlyImage()


class _NeverDiskLoader:
    """Fail if memory-only preparation attempts filesystem decoding."""

    def load_output_image(self, path: Path) -> QImage | None:
        """Reject unexpected disk access."""

        raise AssertionError(f"Unexpected disk decode: {path}")


def _commit_request_from_event(
    live_event: LiveFinalOutputEvent,
) -> OutputImageCommitRequest:
    """Build the narrow request needed to prove the canvas decode invariant."""

    return OutputImageCommitRequest(
        workflow_id=live_event.identity.workflow_id,
        file_path=live_event.file_path,
        node_id=live_event.node_id,
        node_meta_title="Main.Output",
        workflow_name="Workflow",
        source_key=live_event.identity.source_key,
        source_label=live_event.identity.source_label,
        image_bytes=live_event.image_bytes,
        generation_run_id=live_event.identity.generation_run_id,
        prompt_id=live_event.identity.prompt_id,
        client_id=live_event.identity.client_id,
        position=live_event.position,
        artifact_width=live_event.artifact_width,
        artifact_height=live_event.artifact_height,
        live_event=live_event,
    )


def _source_identity(alias: str) -> OutputSourceIdentity:
    """Return one deterministic output source identity."""

    return OutputSourceIdentity(
        node_id="node",
        source_key=f"workflow:{alias}",
        source_label=alias,
        cube_alias=alias,
    )


def _png_bytes(width: int = 64, height: int = 48) -> bytes:
    """Return a deterministic RGBA PNG payload."""

    buffer = io.BytesIO()
    Image.new("RGBA", (width, height), (255, 64, 128, 192)).save(buffer, format="PNG")
    return buffer.getvalue()
