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

"""Cover restored projection coordination outside MainWindow."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

from PySide6.QtCore import QTimer

from substitute.application.workspace_state import RestoreProjectionArtifact
from substitute.application.workspace_state.restore_projection_identity import (
    node_definition_fingerprint,
)
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.domain.workspace_snapshot import (
    EditorViewportSnapshot,
    WorkflowSnapshot,
    WorkspaceSnapshot,
)
from substitute.presentation.shell import (
    restore_projection_controller as controller_mod,
)
from substitute.presentation.shell.restore_projection_controller import (
    RestoreProjectionController,
)


def test_pre_show_restore_projection_projects_cached_workflow(
    monkeypatch: Any,
) -> None:
    """Pre-show restore should project the matching cached workflow before reveal."""

    shell: Any = _projection_shell()
    events: list[str] = []
    shell.workflow_session_service = _WorkflowSession(events)
    shell.generation_action_controller = SimpleNamespace(
        apply_generation_action_availability=lambda: events.append("actions")
    )
    _install_materializer_recorder(monkeypatch, events)
    shell.workflow_tabbar = _WorkflowTabbar(events)
    shell.cube_stacks = {"wf-a": "cube-stack"}
    shell.editor_panels = {"wf-a": "editor-panel"}
    shell.cube_stack_container = _StackContainer(events, "cube")
    shell.editor_panel_container = _StackContainer(events, "editor")

    def refresh_active_workflow_surface(
        *,
        force_refresh: bool,
        on_complete: Callable[[], None],
    ) -> None:
        """Record restore projection refresh and finish it."""

        events.append(f"refresh:{force_refresh}")
        on_complete()

    shell.active_workflow_surface_refresher = SimpleNamespace(
        refresh_active_workflow_surface=refresh_active_workflow_surface
    )

    result = RestoreProjectionController(shell).start_pre_show_restore_projection(
        _artifact(active_workflow_id="wf-a"),
        on_complete=lambda: events.append("complete"),
    )

    assert result is True
    assert shell._active_workspace_route == "wf-a"
    assert events == [
        "activate:wf-a",
        "actions",
        "ensure:wf-a:True",
        "tab:wf-a:False",
        "cube_current:cube-stack",
        "editor_current:editor-panel",
        "refresh:True",
        "complete",
    ]


def test_pre_show_restore_projection_skips_mismatched_cache_artifact() -> None:
    """Pre-show restore should not use a cache artifact for another active workflow."""

    shell: Any = _projection_shell()
    events: list[str] = []

    result = RestoreProjectionController(shell).start_pre_show_restore_projection(
        _artifact(active_workflow_id="wf-other"),
        on_complete=lambda: events.append("complete"),
    )

    assert result is False
    assert events == []


def test_post_backend_validation_clears_stale_direct_node_cache() -> None:
    """Pre-show restore should clear stale derived node-definition state."""

    repository = _CacheRepository()
    live_definition = {"input": {"required": {"seed": ["INT", {}]}}}
    shell: Any = _projection_shell()
    shell.restore_projection_cache_repository = repository
    shell.cube_load_service = SimpleNamespace()
    shell.node_definition_gateway = SimpleNamespace(
        get_node_definition=lambda _node_class: live_definition
    )
    artifact = replace(
        _artifact(active_workflow_id="wf-a"),
        node_definition_fingerprints={"KSampler": "stale"},
    )
    events: list[str] = []

    started = _ObservedRestoreProjectionController(
        shell, events
    ).start_pre_show_restore_projection(
        artifact,
        on_complete=lambda: events.append("complete"),
    )

    assert started is True
    assert repository.clear_calls == 1
    assert events == ["project:wf-a:True", "complete"]


def test_post_backend_validation_accepts_matching_direct_node_cache() -> None:
    """Pre-show restore should preserve matching derived definition state."""

    repository = _CacheRepository()
    live_definition = {"input": {"required": {"seed": ["INT", {}]}}}
    shell: Any = _projection_shell()
    shell.restore_projection_cache_repository = repository
    shell.cube_load_service = SimpleNamespace()
    shell.node_definition_gateway = SimpleNamespace(
        get_node_definition=lambda _node_class: live_definition
    )
    artifact = replace(
        _artifact(active_workflow_id="wf-a"),
        node_definition_fingerprints={
            "KSampler": node_definition_fingerprint(live_definition)
        },
    )
    events: list[str] = []

    started = _ObservedRestoreProjectionController(
        shell, events
    ).start_pre_show_restore_projection(
        artifact,
        on_complete=lambda: events.append("complete"),
    )

    assert started is True
    assert repository.clear_calls == 0
    assert events == ["project:wf-a:True", "complete"]


def test_project_restored_settings_uses_settings_route_controller() -> None:
    """Restored Settings routes should project through the settings owner."""

    events: list[str] = []
    shell: Any = SimpleNamespace(
        _active_workspace_route="wf-a",
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        settings_route_controller=SimpleNamespace(
            project_settings_workspace=lambda: events.append("settings")
        ),
    )

    RestoreProjectionController(shell).project_restored_settings()

    assert events == ["settings"]


def test_project_restored_workflow_forces_surface_projection() -> None:
    """Restored active workflows should project even when already active."""

    calls: list[tuple[str, bool]] = []

    def project_workflow(
        workflow_id: str,
        *,
        force_refresh: bool = False,
        on_surface_complete: Callable[[], None] | None = None,
    ) -> None:
        """Record projection and complete when requested."""

        calls.append((workflow_id, force_refresh))
        if on_surface_complete is not None:
            on_surface_complete()

    shell: Any = SimpleNamespace(
        workspace_controller=SimpleNamespace(
            project_workflow=project_workflow,
        ),
        _restored_workflow_snapshots_by_id={},
        _pending_restored_workflow_snapshots={},
        _prehydrated_workspace_snapshot=None,
    )

    RestoreProjectionController(shell).project_restored_workflow("wf-a")

    assert calls == [("wf-a", True)]


def test_project_restored_workflow_restores_exact_editor_viewport(
    monkeypatch: Any,
) -> None:
    """Restored workflow projection should apply saved scroll after refresh."""

    scrollbar = _ViewportScrollBar(value=0, maximum=500)
    snapshot = WorkflowSnapshot(
        workflow_id="wf-a",
        tab_label="Restored",
        workflow=WorkflowState(
            cubes={
                "CubeA": CubeState(
                    cube_id="cube.a",
                    version="1",
                    alias="CubeA",
                    original_cube={},
                    buffer={},
                )
            },
            stack_order=["CubeA"],
        ),
        active_cube_alias="CubeA",
        editor_viewport=EditorViewportSnapshot(
            scroll_value=120,
            scroll_maximum=500,
            anchor_cube_alias="CubeA",
        ),
    )
    project_calls: list[tuple[str, bool]] = []

    def project_workflow(
        workflow_id: str,
        *,
        force_refresh: bool = False,
        on_surface_complete: Callable[[], None] | None = None,
    ) -> None:
        """Record projection and complete the surface immediately."""

        project_calls.append((workflow_id, force_refresh))
        if on_surface_complete is not None:
            on_surface_complete()

    monkeypatch.setattr(
        QTimer,
        "singleShot",
        lambda _delay, callback: callback(),
    )
    shell: Any = SimpleNamespace(
        workspace_controller=SimpleNamespace(project_workflow=project_workflow),
        _restored_workflow_snapshots_by_id={"wf-a": snapshot},
        _pending_restored_workflow_snapshots={},
        _prehydrated_workspace_snapshot=None,
        _shell_restore_lifecycle="running",
        editor_panels={"wf-a": _ViewportEditorPanel(scrollbar)},
    )

    RestoreProjectionController(shell).project_restored_workflow("wf-a")

    assert project_calls == [("wf-a", True)]
    assert scrollbar.value() == 120
    assert shell._shell_restore_lifecycle == "running"


def test_queue_restore_projection_cache_capture_writes_when_running(
    monkeypatch: Any,
) -> None:
    """Cache capture should persist the live restore projection once restore is running."""

    writes: list[dict[str, object]] = []
    snapshot = WorkspaceSnapshot(
        schema_version="1",
        workflows=(),
        tab_order=(),
        active_route="wf-a",
    )
    shell: Any = SimpleNamespace(
        _shell_restore_lifecycle="running",
        _pending_restore_projection_cache_capture_workflow_id="",
        restore_projection_cache_repository=object(),
        _prehydrated_workspace_snapshot=snapshot,
        restore_projection_target_key="target",
        editor_panels={"wf-a": object()},
        node_definition_gateway=object(),
    )

    class _Extractor:
        """Record capture requests and return a trace-compatible artifact."""

        def capture_and_store(self, **kwargs: object) -> object:
            """Record capture arguments."""

            writes.append(kwargs)
            return SimpleNamespace(
                workflows=(
                    SimpleNamespace(
                        cube_stack=SimpleNamespace(cubes=(object(),)),
                    ),
                ),
                node_definition_fingerprints={"node": "fingerprint"},
            )

    monkeypatch.setattr(
        controller_mod,
        "RestoredEditorProjectionCacheExtractor",
        _Extractor,
    )

    RestoreProjectionController(shell).queue_restore_projection_cache_capture("wf-a")

    assert shell._pending_restore_projection_cache_capture_workflow_id == ""
    assert writes == [
        {
            "repository": shell.restore_projection_cache_repository,
            "snapshot": snapshot,
            "target_key": "target",
            "editor_panels": shell.editor_panels,
            "node_definition_gateway": shell.node_definition_gateway,
        }
    ]


def test_queue_restore_projection_cache_capture_waits_until_restore_running() -> None:
    """Cache capture should remain pending until visible restore finalization completes."""

    shell: Any = SimpleNamespace(
        _shell_restore_lifecycle="restoring",
        _pending_restore_projection_cache_capture_workflow_id="",
    )

    RestoreProjectionController(shell).queue_restore_projection_cache_capture("wf-a")

    assert shell._pending_restore_projection_cache_capture_workflow_id == "wf-a"


class _ViewportScrollBar:
    """Record editor scrollbar state for restore projection tests."""

    def __init__(self, *, value: int, maximum: int) -> None:
        """Store initial scrollbar values."""

        self._value = value
        self._maximum = maximum

    def value(self) -> int:
        """Return the current scrollbar value."""

        return self._value

    def maximum(self) -> int:
        """Return the current scrollbar maximum."""

        return self._maximum

    def setValue(self, value: int) -> None:
        """Record the restored scrollbar value."""

        self._value = value


class _ViewportScroll:
    """Expose the vertical scrollbar expected by editor panels."""

    def __init__(self, scrollbar: _ViewportScrollBar) -> None:
        """Store the scrollbar."""

        self._scrollbar = scrollbar

    def verticalScrollBar(self) -> _ViewportScrollBar:
        """Return the vertical scrollbar."""

        return self._scrollbar


class _ViewportEditorPanel:
    """Expose scroll state for restored projection viewport tests."""

    def __init__(self, scrollbar: _ViewportScrollBar) -> None:
        """Store scroll state."""

        self.scroll = _ViewportScroll(scrollbar)


def _projection_shell() -> Any:
    """Return shell state required for pre-show projection tests."""

    return SimpleNamespace(
        _prehydrated_restore_finalized=False,
        _prehydrated_restore_runtime_prepared=True,
        _prehydrated_active_workflow_projection_pending="wf-a",
        _active_workspace_route="",
        cube_stack_presentation_controller=SimpleNamespace(
            activate_document_kind=lambda _kind, *, animated: None
        ),
    )


def _artifact(*, active_workflow_id: str) -> RestoreProjectionArtifact:
    """Build a minimal restore projection artifact."""

    return RestoreProjectionArtifact(
        schema_version=1,
        created_at="2026-01-01T00:00:00Z",
        app_projection_version=1,
        target_key="target",
        workspace_fingerprint="workspace",
        active_route=active_workflow_id,
        active_workflow_id=active_workflow_id,
        workflows=(),
        prompt_editor_feature_profile_fingerprint="prompt",
        node_definition_fingerprints={},
        cube_definition_fingerprints={},
    )


class _WorkflowSession:
    """Record workflow activation requests."""

    def __init__(self, events: list[str]) -> None:
        """Store the shared event sink."""

        self._events = events
        self.workflows = {"wf-a": WorkflowState()}

    def activate_workflow(self, workflow_id: str) -> None:
        """Record workflow activation."""

        self._events.append(f"activate:{workflow_id}")


class _CacheRepository:
    """Record invalid cache clearing."""

    def __init__(self) -> None:
        """Initialize clear-call tracking."""

        self.clear_calls = 0

    def clear(self) -> None:
        """Record one cache invalidation."""

        self.clear_calls += 1


class _ObservedRestoreProjectionController(RestoreProjectionController):
    """Expose pre-show projection completion without constructing shell widgets."""

    def __init__(self, shell: Any, events: list[str]) -> None:
        """Store the projection event sink."""

        super().__init__(shell)
        self._events = events

    def project_restored_workflow_editor_surface(
        self,
        workflow_id: str,
        *,
        suppress_visible_geometry: bool,
        on_surface_complete: Callable[[], None],
    ) -> None:
        """Record the public projection request and complete it synchronously."""

        self._events.append(f"project:{workflow_id}:{suppress_visible_geometry}")
        on_surface_complete()


class _WorkflowTabbar:
    """Record workflow tab selection."""

    def __init__(self, events: list[str]) -> None:
        """Store the shared event sink."""

        self._events = events

    def select_workflow_tab(self, workflow_id: str, *, emit: bool) -> None:
        """Record tab selection."""

        self._events.append(f"tab:{workflow_id}:{emit}")


class _StackContainer:
    """Record stacked-widget current selection requests."""

    def __init__(self, events: list[str], name: str) -> None:
        """Store the shared event sink."""

        self._events = events
        self._name = name

    def setCurrentWidget(self, widget: object) -> None:
        """Record the selected widget."""

        self._events.append(f"{self._name}_current:{widget}")


def _install_materializer_recorder(monkeypatch: Any, events: list[str]) -> None:
    """Patch restore projection to record materializer UI hydration."""

    class _Materializer:
        """Record workflow UI hydration requests."""

        def ensure_workflow_ui(
            self,
            workflow_id: str,
            *,
            set_as_current: bool,
        ) -> tuple[object, object]:
            """Record the hydration request."""

            events.append(f"ensure:{workflow_id}:{set_as_current}")
            return object(), object()

    monkeypatch.setattr(
        controller_mod,
        "restored_workflow_materializer_for",
        lambda _shell: _Materializer(),
    )
