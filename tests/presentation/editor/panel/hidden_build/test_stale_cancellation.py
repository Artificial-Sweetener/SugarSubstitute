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

"""Test stale hidden-build cancellation before work begins."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer
from _pytest.monkeypatch import MonkeyPatch

import substitute.presentation.editor.panel.hidden_build_scheduler as mod
from substitute.presentation.editor.panel.projection_models import ProjectedCubeBuild


class _BuildSession:
    """Record unexpected staged-build work."""

    def __init__(self) -> None:
        """Initialize the step counter."""

        self.steps = 0

    def step(self) -> bool:
        """Record a build step and report completion."""

        self.steps += 1
        return True


def test_hidden_projection_build_cancels_stale_batch_without_stepping(
    monkeypatch: MonkeyPatch,
) -> None:
    """Hidden staged builds should cancel before work when freshness fails."""

    scheduled_callbacks: list[Callable[[], None]] = []
    monkeypatch.setattr(
        QTimer,
        "singleShot",
        staticmethod(lambda _delay, callback: scheduled_callbacks.append(callback)),
    )
    build_session = _BuildSession()
    projected_build = ProjectedCubeBuild(
        cube_alias="CubeA",
        final_widget=object(),
        build_session=build_session,
        started_at=0.0,
        token=object(),
    )
    completion_calls: list[str] = []
    cancel_calls: list[str] = []
    scheduler = mod.HiddenBuildScheduler(
        mod.HiddenBuildSchedulerPorts(
            reveal_projected_cube_builds=lambda _builds, _workflow_id: None,
            mark_build_complete=lambda _alias, _token: None,
            mark_build_failed=lambda _alias, _token, _reason: None,
        )
    )

    scheduler.schedule_projected_cube_builds(
        (projected_build,),
        on_complete=lambda: completion_calls.append("complete"),
        on_cancel=lambda: cancel_calls.append("cancel"),
        workflow_id="workflow",
        is_current=lambda: False,
    )
    scheduled_callbacks[0]()

    assert build_session.steps == 0
    assert completion_calls == []
    assert cancel_calls == ["cancel"]
