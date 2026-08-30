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

"""Provide restore-projection controller doubles."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any


from substitute.application.workspace_state import RestoreProjectionArtifact
from substitute.domain.workflow import WorkflowState
from substitute.presentation.shell import (
    restore_projection_controller as controller_mod,
)
from substitute.presentation.shell.restore_projection_controller import (
    RestoreProjectionController,
)


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
        target_key="target",
        workspace_fingerprint="workspace",
        active_route=active_workflow_id,
        active_workflow_id=active_workflow_id,
        workflows=(),
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
