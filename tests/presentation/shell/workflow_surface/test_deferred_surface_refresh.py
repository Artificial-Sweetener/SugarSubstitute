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

"""Deferred workflow override and completion contracts."""

from __future__ import annotations

from collections.abc import Callable
import logging
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QTimer

from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowSurfaceInvalidationService,
)
from substitute.presentation.shell.workflow_surface_reconciler import (
    ActiveWorkflowSurfaceRefresher,
)


def test_deferred_override_presentation_rebuild_skips_stale_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deferred override rebuild callbacks should ignore stale workflow ids."""

    actions: list[str] = []
    scheduled: list[Callable[[], None]] = []
    shell = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-current")
    )
    manager = SimpleNamespace(
        rebuild_override_menu=lambda: actions.append("rebuild"),
        rebuild_active_override_controls=lambda: actions.append("controls"),
    )
    monkeypatch.setattr(
        QTimer,
        "singleShot",
        staticmethod(lambda _msec, callback: scheduled.append(callback)),
    )

    ActiveWorkflowSurfaceRefresher(shell).schedule_active_override_presentation_rebuild(
        manager, workflow_id="wf-old"
    )
    scheduled[0]()

    assert actions == []


def test_active_surface_refresh_success_emits_no_info_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Successful active surface maintenance should not spam INFO logs."""

    calls: list[str] = []

    class _EditorPanel:
        """Editor-panel double that reports a clean projection."""

        def current_projection_signature(self, **kwargs: object) -> object:
            """Return a stable projection signature."""

            del kwargs
            return "signature"

        def is_projection_clean(self, signature: object) -> bool:
            """Report whether the requested signature is clean."""

            return signature == "signature"

        def refresh_clean_projection(self, **kwargs: object) -> None:
            """Record lightweight projection refresh."""

            del kwargs
            calls.append("editor:clean")

    class _OverrideManager:
        """Override-manager double for active surface refresh."""

        def sync_state_from_workflow(self) -> None:
            """Record state synchronization."""

            calls.append("override:sync")

        def apply_global_overrides_without_snapshot_fallback(self) -> bool:
            """Record pre-projection override application."""

            calls.append("override:pre")
            return False

        def materialize_default_overrides(self) -> bool:
            """Record default override materialization."""

            calls.append("override:defaults")
            return False

        def apply_global_overrides(
            self,
            *,
            use_cached_behavior_snapshot: bool,
        ) -> None:
            """Record post-projection override application."""

            calls.append(f"override:post:{use_cached_behavior_snapshot}")

    workflow = SimpleNamespace(cubes={}, stack_order=[])
    invalidation = WorkflowSurfaceInvalidationService()
    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a",
            workflows={"wf-a": workflow},
        ),
        get_active_workflow=lambda: workflow,
        active_editor_panel=_EditorPanel(),
        active_override_manager=_OverrideManager(),
        editor_panels={"wf-a": _EditorPanel()},
        override_managers={"wf-a": _OverrideManager()},
        workflow_canvas_projection_coordinator=SimpleNamespace(
            project_workflow=lambda _workflows, workflow_id: calls.append(
                f"canvas:{workflow_id}"
            )
        ),
        workflow_surface_invalidation_service=invalidation,
        canvas_route_controller=SimpleNamespace(
            refresh_input_canvas_availability=lambda: calls.append("input")
        ),
        generation_action_controller=SimpleNamespace(
            apply_generation_action_availability=lambda: calls.append("generation")
        ),
    )
    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.presentation.shell.workflow_surface_reconciler",
    )

    ActiveWorkflowSurfaceRefresher(view).refresh_active_workflow_surface()

    assert "editor:clean" in calls
    assert invalidation.is_clean("wf-a")
    assert caplog.records == []
