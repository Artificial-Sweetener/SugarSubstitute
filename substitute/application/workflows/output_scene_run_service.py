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

"""Track prompt-scene generation manifests independently from canvas widgets."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, cast
from uuid import UUID

_UNSET = object()


SceneRunStatus = Literal[
    "pending",
    "dispatching",
    "comfy_pending",
    "running",
    "completed",
    "failed",
    "skipped",
    "cancelled",
]


@dataclass(frozen=True, slots=True)
class SceneRunEntry:
    """Describe one prompt scene's canvas-visible run state."""

    scene_key: str
    scene_title: str
    scene_order: int
    job_id: str | None = None
    status: SceneRunStatus = "pending"
    final_output_ids: tuple[UUID, ...] = ()
    preview_id: UUID | None = None

    @property
    def has_visual_content(self) -> bool:
        """Return whether this scene has an inspectable preview or final image."""

        return self.preview_id is not None or bool(self.final_output_ids)


@dataclass(frozen=True, slots=True)
class SceneRunState:
    """Describe one multi-scene generation run manifest."""

    scene_run_id: str
    workflow_id: str
    workflow_name: str
    scenes: tuple[SceneRunEntry, ...]

    def scene_for_key(self, scene_key: str) -> SceneRunEntry | None:
        """Return one scene entry by normalized scene key."""

        for scene in self.scenes:
            if scene.scene_key == scene_key:
                return scene
        return None


class OutputSceneRunService:
    """Own prompt-scene run status and visual attachment state."""

    def __init__(self) -> None:
        """Initialize an empty scene-run registry."""

        self._runs: dict[str, SceneRunState] = {}

    def start_scene_run(
        self,
        *,
        scene_run_id: str,
        workflow_id: str,
        workflow_name: str,
        scenes: tuple[tuple[str, str, int], ...],
    ) -> SceneRunState:
        """Create or replace a scene-run manifest from authority scene order."""

        state = SceneRunState(
            scene_run_id=scene_run_id,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            scenes=tuple(
                SceneRunEntry(
                    scene_key=scene_key,
                    scene_title=scene_title,
                    scene_order=scene_order,
                )
                for scene_key, scene_title, scene_order in scenes
            ),
        )
        self._runs[scene_run_id] = state
        return state

    def run_for_id(self, scene_run_id: str) -> SceneRunState | None:
        """Return one tracked scene run by id."""

        return self._runs.get(scene_run_id)

    def mark_scene_running(
        self,
        *,
        scene_run_id: str,
        scene_key: str,
        job_id: str | None = None,
    ) -> SceneRunState | None:
        """Mark one scene as running."""

        return self._update_scene(
            scene_run_id=scene_run_id,
            scene_key=scene_key,
            status="running",
            job_id=job_id,
        )

    def mark_scene_completed(
        self,
        *,
        scene_run_id: str,
        scene_key: str,
    ) -> SceneRunState | None:
        """Mark one scene as completed."""

        return self._update_scene(
            scene_run_id=scene_run_id,
            scene_key=scene_key,
            status="completed",
            preview_id=None,
        )

    def mark_scene_skipped(
        self,
        *,
        scene_run_id: str,
        scene_key: str,
    ) -> SceneRunState | None:
        """Mark one scene as skipped and discard preview-only content."""

        return self._update_terminal_without_preview(
            scene_run_id=scene_run_id,
            scene_key=scene_key,
            status="skipped",
        )

    def mark_scene_cancelled(
        self,
        *,
        scene_run_id: str,
        scene_key: str,
    ) -> SceneRunState | None:
        """Mark one scene as cancelled and discard preview-only content."""

        return self._update_terminal_without_preview(
            scene_run_id=scene_run_id,
            scene_key=scene_key,
            status="cancelled",
        )

    def mark_scene_failed(
        self,
        *,
        scene_run_id: str,
        scene_key: str,
    ) -> SceneRunState | None:
        """Mark one scene as failed and discard preview-only content."""

        return self._update_terminal_without_preview(
            scene_run_id=scene_run_id,
            scene_key=scene_key,
            status="failed",
        )

    def attach_preview(
        self,
        *,
        scene_run_id: str,
        scene_key: str,
        preview_id: UUID,
    ) -> SceneRunState | None:
        """Attach or replace the transient preview image for one scene."""

        return self._update_scene(
            scene_run_id=scene_run_id,
            scene_key=scene_key,
            preview_id=preview_id,
        )

    def attach_output(
        self,
        *,
        scene_run_id: str,
        scene_key: str,
        output_id: UUID,
    ) -> SceneRunState | None:
        """Attach one final output image to a scene and clear its preview."""

        state = self._runs.get(scene_run_id)
        if state is None:
            return None
        scene = state.scene_for_key(scene_key)
        if scene is None:
            return None
        final_output_ids = scene.final_output_ids
        if output_id not in final_output_ids:
            final_output_ids = (*final_output_ids, output_id)
        return self._update_scene(
            scene_run_id=scene_run_id,
            scene_key=scene_key,
            final_output_ids=final_output_ids,
            preview_id=None,
        )

    def clear_preview(
        self,
        *,
        scene_run_id: str,
        scene_key: str,
    ) -> SceneRunState | None:
        """Remove transient preview content for one scene."""

        return self._update_scene(
            scene_run_id=scene_run_id,
            scene_key=scene_key,
            preview_id=None,
        )

    def _update_terminal_without_preview(
        self,
        *,
        scene_run_id: str,
        scene_key: str,
        status: SceneRunStatus,
    ) -> SceneRunState | None:
        """Apply terminal status while preserving final outputs only."""

        state = self._runs.get(scene_run_id)
        if state is None:
            return None
        scene = state.scene_for_key(scene_key)
        if scene is None:
            return None
        return self._update_scene(
            scene_run_id=scene_run_id,
            scene_key=scene_key,
            status=status,
            preview_id=None,
        )

    def _update_scene(
        self,
        *,
        scene_run_id: str,
        scene_key: str,
        status: SceneRunStatus | None = None,
        job_id: str | None = None,
        final_output_ids: tuple[UUID, ...] | None = None,
        preview_id: UUID | None | object = _UNSET,
    ) -> SceneRunState | None:
        """Replace one scene entry in a tracked run."""

        state = self._runs.get(scene_run_id)
        if state is None:
            return None
        updated_scenes: list[SceneRunEntry] = []
        changed = False
        for scene in state.scenes:
            if scene.scene_key != scene_key:
                updated_scenes.append(scene)
                continue
            next_preview_id = (
                scene.preview_id
                if preview_id is _UNSET
                else cast(UUID | None, preview_id)
            )
            updated_scenes.append(
                replace(
                    scene,
                    status=status or scene.status,
                    job_id=job_id if job_id is not None else scene.job_id,
                    final_output_ids=(
                        final_output_ids
                        if final_output_ids is not None
                        else scene.final_output_ids
                    ),
                    preview_id=next_preview_id,
                )
            )
            changed = True
        if not changed:
            return None
        next_state = replace(state, scenes=tuple(updated_scenes))
        self._runs[scene_run_id] = next_state
        return next_state


__all__ = [
    "OutputSceneRunService",
    "SceneRunEntry",
    "SceneRunState",
    "SceneRunStatus",
]
