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

"""Test workspace output preview lifecycle actions."""

from __future__ import annotations

from types import SimpleNamespace


from substitute.application.workflows.output_preview_results import (
    OutputPreviewAcceptance,
)
from substitute.domain.workflow import (
    WorkflowState,
)


from tests.presentation.shell.canvas_actions.support import (
    _import_module,
    _live_preview,
    _output_session,
    _record_and_return,
)


def test_display_preview_image_updates_only_active_workflow() -> None:
    """Strict previews should display only after registry/session acceptance."""

    mod = _import_module()
    previews: list[OutputPreviewAcceptance] = []
    registry_calls: list[str] = []
    focused: list[str] = []
    accepted = OutputPreviewAcceptance(accepted=True)
    output_canvas = SimpleNamespace(
        _output_session=_output_session(),
        apply_preview_acceptance=previews.append,
    )
    registry = SimpleNamespace(
        accept_preview=lambda preview, **_kwargs: _record_and_return(
            registry_calls,
            preview.identity.workflow_id,
            accepted
            if preview.identity.workflow_id == "wf-1"
            else OutputPreviewAcceptance(accepted=False),
        )
    )
    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-1"),
        canvas_host=SimpleNamespace(
            canvas_for={"Output": output_canvas}.get,
            focus_attached_canvas=lambda label: focused.append(label),
        ),
        output_preview_registry=registry,
        visual_authorization_service=SimpleNamespace(
            authorize_preview=lambda _identity: True
        ),
        _log_missing_output_canvas=lambda _workflow_id: None,
    )
    actions = mod.WorkspaceCanvasActions(view)

    actions.display_preview_image(_live_preview(workflow_id="wf-2"))
    actions.display_preview_image(_live_preview(workflow_id="wf-1"))

    assert registry_calls == ["wf-1"]
    assert previews == [accepted]
    assert focused == []


def test_display_preview_image_rebinds_stale_active_workflow_session() -> None:
    """An active preview should replace a mounted session from another workflow."""

    mod = _import_module()
    stale_session = _output_session("wf-old")
    active_session = _output_session("wf-1")
    accepted = OutputPreviewAcceptance(accepted=True)
    accepted_sessions: list[object] = []
    applied: list[OutputPreviewAcceptance] = []
    projection_calls: list[tuple[object, str]] = []
    output_canvas = SimpleNamespace(
        _output_session=stale_session,
        apply_preview_acceptance=applied.append,
    )

    def project_workflow(workflows: object, workflow_id: str) -> None:
        """Replace the stale mounted session through the projection owner."""

        projection_calls.append((workflows, workflow_id))
        output_canvas._output_session = active_session

    registry = SimpleNamespace(
        accept_preview=lambda _preview, **kwargs: _record_and_return(
            accepted_sessions,
            kwargs["session"],
            accepted,
        )
    )
    workflows = {"wf-1": WorkflowState()}
    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-1",
            workflows=workflows,
        ),
        canvas_host=SimpleNamespace(
            canvas_for={"Output": output_canvas}.get,
            is_canvas_visible=lambda label: label == "Output",
        ),
        output_canvas_projection_coordinator=SimpleNamespace(
            project_workflow=project_workflow
        ),
        output_preview_registry=registry,
        visual_authorization_service=SimpleNamespace(
            authorize_preview=lambda _identity: True
        ),
        _log_missing_output_canvas=lambda _workflow_id: None,
    )

    mod.WorkspaceCanvasActions(view).display_preview_image(_live_preview())

    assert projection_calls == [(workflows, "wf-1")]
    assert accepted_sessions == [active_session]
    assert applied == [accepted]


def test_clear_output_previews_updates_only_active_workflow() -> None:
    """Preview cleanup should only reach the output canvas for the active workflow."""

    mod = _import_module()
    clear_calls: list[bool] = []
    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-1"),
        canvas_host=SimpleNamespace(
            canvas_for={
                "Output": SimpleNamespace(
                    clear_previews=lambda: clear_calls.append(True)
                )
            }.get
        ),
        _log_missing_output_canvas=lambda _workflow_id: None,
    )
    actions = mod.WorkspaceCanvasActions(view)

    actions.clear_output_previews("wf-2")
    actions.clear_output_previews("wf-1")

    assert clear_calls == [True]
