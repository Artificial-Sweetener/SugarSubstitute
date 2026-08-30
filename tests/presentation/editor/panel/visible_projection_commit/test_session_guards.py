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

"""Test visible projection commit session guards."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from _pytest.monkeypatch import MonkeyPatch
from substitute.presentation.editor.panel.projection_models import ProjectedCubeBuild
from substitute.presentation.editor.panel.projection_session import (
    ActiveProjectionSession,
)

import substitute.presentation.editor.panel.visible_projection_commit as mod


def _projection_session() -> ActiveProjectionSession:
    """Create one active projection session for commit tests."""

    return ActiveProjectionSession(
        workflow_id="workflow",
        aliases={"CubeA"},
        token=object(),
        claimed_completions=[],
        projection_completions=[],
    )


def _projected_build() -> ProjectedCubeBuild:
    """Create one completed cube build for commit tests."""

    return ProjectedCubeBuild(
        cube_alias="CubeA",
        final_widget=object(),
        build_session=object(),
        started_at=0.0,
        token=object(),
    )


def test_visible_projection_commit_rejects_stale_session_without_revealing() -> None:
    """Visible commits must prove session freshness before mutating widgets."""

    reveal_calls: list[object] = []
    complete_marks: list[object] = []
    finish_calls: list[str] = []
    cancel_calls: list[str] = []
    session = _projection_session()
    projected_build = _projected_build()
    ports = mod.EditorVisibleProjectionCommitPorts(
        active_workflow_id=lambda: "workflow",
        panel_is_visible=lambda: True,
        is_projection_session_current=lambda _session: False,
        reveal_projected_cube_builds=lambda builds, workflow_id: reveal_calls.append(
            (workflow_id, tuple(builds))
        ),
        mark_build_complete=lambda alias, token: complete_marks.append((alias, token)),
        mark_build_failed=lambda _alias, _token, _error: None,
    )
    pending = mod.PendingVisibleProjectionCommit(
        workflow_id="workflow",
        projection_session=session,
        projected_builds=(projected_build,),
        finish_refresh=lambda: finish_calls.append("finish"),
        cancel_refresh=cancel_calls.append,
        created_at=0.0,
    )

    committed = mod.EditorVisibleProjectionCommitPipeline(
        ports
    ).commit_visible_projection(pending)

    assert committed is False
    assert reveal_calls == []
    assert complete_marks == []
    assert finish_calls == []
    assert cancel_calls == ["visible_projection_session_stale"]


def test_visible_projection_commit_defers_until_panel_is_active(
    monkeypatch: MonkeyPatch,
) -> None:
    """Completed projection builds should publish only after the panel is visible."""

    scheduled_retries: list[tuple[str, int]] = []
    monkeypatch.setattr(
        QTimer,
        "singleShot",
        staticmethod(
            lambda delay, _callback: scheduled_retries.append(
                ("visible_commit_retry", delay)
            )
        ),
    )
    visible = False
    reveal_calls: list[tuple[str, tuple[object, ...]]] = []
    complete_marks: list[tuple[str, object]] = []
    finish_calls: list[str] = []
    cancel_calls: list[str] = []
    session = _projection_session()
    projected_build = _projected_build()
    ports = mod.EditorVisibleProjectionCommitPorts(
        active_workflow_id=lambda: "workflow",
        panel_is_visible=lambda: visible,
        is_projection_session_current=lambda _session: True,
        reveal_projected_cube_builds=lambda builds, workflow_id: reveal_calls.append(
            (workflow_id, tuple(builds))
        ),
        mark_build_complete=lambda alias, token: complete_marks.append((alias, token)),
        mark_build_failed=lambda _alias, _token, _error: None,
    )
    pipeline = mod.EditorVisibleProjectionCommitPipeline(ports)

    committed_immediately = pipeline.commit_or_defer(
        workflow_id="workflow",
        projection_session=session,
        projected_builds=(projected_build,),
        finish_refresh=lambda: finish_calls.append("finish"),
        cancel_refresh=cancel_calls.append,
    )
    visible = True
    committed_after_activation = pipeline.finalize_pending_visible_projection()

    assert committed_immediately is False
    assert pipeline.has_pending_visible_projection_commit() is False
    assert committed_after_activation is True
    assert scheduled_retries == [("visible_commit_retry", 0)]
    assert reveal_calls == [("workflow", (projected_build,))]
    assert complete_marks == [("CubeA", projected_build.token)]
    assert finish_calls == ["finish"]
    assert cancel_calls == []
