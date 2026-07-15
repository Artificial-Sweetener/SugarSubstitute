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

"""Tests for panel visible projection commit publication."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from substitute.presentation.editor.panel.projection_session import (
    ActiveProjectionSession,
)
from substitute.presentation.editor.panel.rendering.render_reconciler import (
    ProjectedCubeBuildProtocol,
)
from substitute.presentation.editor.panel.visible_projection_commit import (
    EditorVisibleProjectionCommitPipeline,
    EditorVisibleProjectionCommitPorts,
    PendingVisibleProjectionCommit,
)


def test_visible_projection_commit_marks_failed_builds_on_reveal_error() -> None:
    """Visible commit failures should mark builds failed and cancel refresh."""

    failed: list[tuple[str, object, str]] = []
    completed: list[tuple[str, object]] = []
    cancelled: list[str] = []
    build_token = object()
    build = cast(
        ProjectedCubeBuildProtocol,
        SimpleNamespace(
            cube_alias="CubeA",
            final_widget=object(),
            build_session=object(),
            started_at=0.0,
            token=build_token,
        ),
    )
    session = ActiveProjectionSession(
        workflow_id="workflow",
        aliases={"CubeA"},
        token=object(),
        claimed_completions=[],
        projection_completions=[],
    )
    ports = EditorVisibleProjectionCommitPorts(
        active_workflow_id=lambda: "workflow",
        panel_is_visible=lambda: True,
        is_projection_session_current=lambda _session: True,
        reveal_projected_cube_builds=lambda _builds, _workflow_id: (
            _ for _ in ()
        ).throw(RuntimeError("boom")),
        mark_build_complete=lambda alias, token: completed.append((alias, token)),
        mark_build_failed=lambda alias, token, error: failed.append(
            (alias, token, type(error).__name__)
        ),
    )
    pipeline = EditorVisibleProjectionCommitPipeline(ports)
    pending = PendingVisibleProjectionCommit(
        workflow_id="workflow",
        projection_session=session,
        projected_builds=(build,),
        finish_refresh=lambda: None,
        cancel_refresh=cancelled.append,
        created_at=0.0,
    )

    assert pipeline.commit_visible_projection(pending) is False

    assert completed == []
    assert failed == [("CubeA", build_token, "RuntimeError")]
    assert cancelled == ["visible_projection_commit_failed"]
