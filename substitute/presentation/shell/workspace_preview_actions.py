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

"""Authorize and project live Output preview placeholders for the workspace."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from substitute.application.ports import GenerationVisualIdentity
from substitute.application.workflows.output_canvas_session import OutputCanvasSession
from substitute.application.workflows.output_visual_events import (
    LivePreviewEvent,
    OutputSceneIdentity,
)


@dataclass(frozen=True, slots=True)
class WorkspacePreviewActions:
    """Own live preview authorization, session binding, and canvas admission."""

    view: object
    log_missing_output_canvas: Callable[[str], None]

    def display_preview_image(self, preview: object) -> None:
        """Display a preview only after strict run, source, and session checks."""

        if not isinstance(preview, LivePreviewEvent):
            return
        workflow_id = preview.identity.workflow_id
        output_canvas = self._output_canvas()
        if output_canvas is None:
            self.log_missing_output_canvas(workflow_id)
            return
        session = self._output_session(output_canvas, workflow_id)
        if session is None:
            return
        authorization = getattr(self.view, "visual_authorization_service", None)
        authorize_preview = getattr(authorization, "authorize_preview", None)
        authorize_source = getattr(authorization, "authorize_preview_source", None)
        registry = getattr(self.view, "output_preview_registry", None)
        accept_preview = getattr(registry, "accept_preview", None)
        session_service = getattr(self.view, "workflow_session_service", None)
        if not callable(authorize_preview) or not callable(accept_preview):
            return
        acceptance = accept_preview(
            preview,
            session=session,
            active_workflow_id=str(
                getattr(session_service, "active_workflow_id", "") or ""
            ),
            authorize_preview=authorize_preview,
            is_valid_source_placeholder=authorize_source,
            is_valid_scene_placeholder=self._valid_scene_placeholder,
        )
        if not acceptance.accepted and not acceptance.retired_preview_ids:
            return
        apply_preview = getattr(output_canvas, "apply_preview_acceptance", None)
        if callable(apply_preview):
            apply_preview(acceptance)
            return
        self.log_missing_output_canvas(workflow_id)

    def clear_output_previews(self, workflow_id: str) -> None:
        """Clear transient previews only for the active workflow."""

        session_service = getattr(self.view, "workflow_session_service", None)
        active_workflow_id = str(
            getattr(session_service, "active_workflow_id", "") or ""
        )
        if workflow_id != active_workflow_id:
            return
        clear_previews = getattr(self._output_canvas(), "clear_previews", None)
        if callable(clear_previews):
            clear_previews()
            return
        self.log_missing_output_canvas(workflow_id)

    def _output_canvas(self) -> object | None:
        """Return the configured Output canvas when its host exposes one."""

        canvas_host = getattr(self.view, "canvas_host", None)
        canvas_for = getattr(canvas_host, "canvas_for", None)
        return canvas_for("Output") if callable(canvas_for) else None

    def _output_session(
        self,
        output_canvas: object,
        workflow_id: str,
    ) -> OutputCanvasSession | None:
        """Return or bind the active visible Output session for a preview."""

        session_service = getattr(self.view, "workflow_session_service", None)
        active_workflow_id = str(
            getattr(session_service, "active_workflow_id", "") or ""
        )
        if workflow_id != active_workflow_id:
            return None
        session = getattr(output_canvas, "_output_session", None)
        if (
            isinstance(session, OutputCanvasSession)
            and session.workflow_id.value == workflow_id
        ):
            return session
        canvas_host = getattr(self.view, "canvas_host", None)
        is_canvas_visible = getattr(canvas_host, "is_canvas_visible", None)
        if callable(is_canvas_visible) and not bool(is_canvas_visible("Output")):
            return None
        workflows = getattr(session_service, "workflows", None)
        if not isinstance(workflows, Mapping):
            return None
        coordinator = getattr(self.view, "output_canvas_projection_coordinator", None)
        project_workflow = getattr(coordinator, "project_workflow", None)
        if not callable(project_workflow):
            return None
        project_workflow(workflows, workflow_id)
        session = getattr(output_canvas, "_output_session", None)
        return session if isinstance(session, OutputCanvasSession) else None

    def _valid_scene_placeholder(
        self,
        scene: OutputSceneIdentity,
        identity: GenerationVisualIdentity,
    ) -> bool:
        """Return whether a scene placeholder belongs to the active scene run."""

        scene_run_service = getattr(self.view, "output_scene_run_service", None)
        run_for_id = getattr(scene_run_service, "run_for_id", None)
        if not callable(run_for_id):
            return False
        run = run_for_id(scene.run_id)
        if run is None or getattr(run, "workflow_id", None) != identity.workflow_id:
            return False
        scene_entry = getattr(run, "scene_for_key", lambda _scene_key: None)(scene.key)
        if scene_entry is None:
            return False
        return getattr(scene_entry, "status", "") in {
            "pending",
            "dispatching",
            "comfy_pending",
            "running",
        }


__all__ = ["WorkspacePreviewActions"]
