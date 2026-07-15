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

"""Shared test doubles for editor projection tests."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace


class _Widget:
    """Generic widget stub used by coordinator tests."""

    def __init__(self, label: str = "widget") -> None:
        """Initialize recorded widget interactions."""

        self.parents: list[object | None] = []
        self.deleted = 0
        self.label = label
        self.update_wash_calls: list[tuple[str, str]] = []
        self.visible_changes: list[bool] = []
        self.updates_enabled_changes: list[bool] = []
        self.update_calls = 0

    def setParent(self, parent: object | None) -> None:
        """Record parent-detach calls."""

        self.parents.append(parent)

    def deleteLater(self) -> None:
        """Record deferred deletion."""

        self.deleted += 1

    def showUpdatingWash(self, message: str = "Updating") -> None:
        """Record local update wash activation."""

        self.update_wash_calls.append(("show", message))

    def hideUpdatingWash(self) -> None:
        """Record local update wash dismissal."""

        self.update_wash_calls.append(("hide", ""))

    def hide(self) -> None:
        """Record hidden staged-build state."""

        self.visible_changes.append(False)

    def show(self) -> None:
        """Record reveal visibility."""

        self.visible_changes.append(True)

    def setUpdatesEnabled(self, enabled: bool) -> None:
        """Record update suppression changes."""

        self.updates_enabled_changes.append(enabled)

    def update(self) -> None:
        """Record repaint requests."""

        self.update_calls += 1


class _FinalizingWidget(_Widget):
    """Widget stub that records reveal finalization callbacks."""

    def __init__(
        self,
        label: str,
        calls: list[str],
        *,
        fail_on_finalize: bool = False,
    ) -> None:
        """Store callback recording state for coordinator ordering assertions."""

        super().__init__(label)
        self._calls = calls
        self._fail_on_finalize = fail_on_finalize

    def finalize_layout_for_reveal(self, *, reason: str) -> None:
        """Record or fail one coordinator-owned reveal finalization."""

        self._calls.append(f"finalize:{reason}")
        if self._fail_on_finalize:
            raise RuntimeError("finalization failed")


class _LayoutItem:
    """Layout item wrapper used by coordinator tests."""

    def __init__(
        self,
        widget: object | None = None,
        spacer: bool = False,
        layout: object | None = None,
    ) -> None:
        """Store contained layout item state."""

        self._widget = widget
        self._spacer = spacer
        self._layout = layout

    def widget(self) -> object | None:
        """Return contained widget."""

        return self._widget

    def spacerItem(self) -> object | None:
        """Return spacer marker when applicable."""

        return object() if self._spacer else None

    def layout(self) -> object | None:
        """Return nested layout when applicable."""

        return self._layout


class _Layout:
    """Minimal layout that records take/add ordering."""

    def __init__(
        self,
        items: list[_LayoutItem],
        *,
        parent_widget: object | None = None,
    ) -> None:
        """Store layout items and parent surface."""

        self._items = list(items)
        self.added: list[tuple[str, object]] = []
        self.activate_calls = 0
        self._parent_widget = parent_widget

    def count(self) -> int:
        """Return current item count."""

        return len(self._items)

    def takeAt(self, index: int) -> _LayoutItem:
        """Remove and return one item."""

        return self._items.pop(index)

    def itemAt(self, index: int) -> _LayoutItem:
        """Return one item without removing it."""

        return self._items[index]

    def addSpacing(self, spacing: int) -> None:
        """Record spacing insertion."""

        self.added.append(("spacing", spacing))

    def addWidget(self, widget: object) -> None:
        """Record widget insertion."""

        self.added.append(("widget", widget))

    def activate(self) -> None:
        """Record one final layout activation pass."""

        self.activate_calls += 1

    def parentWidget(self) -> object | None:
        """Return the configured parent widget."""

        return self._parent_widget


class _NestedLayout:
    """Nested layout double that records stale widget cleanup."""

    def __init__(self, items: list[_LayoutItem]) -> None:
        """Store nested layout items for cleanup assertions."""

        self._items = list(items)

    def count(self) -> int:
        """Return current item count."""

        return len(self._items)

    def takeAt(self, index: int) -> _LayoutItem:
        """Remove and return one item."""

        return self._items.pop(index)


class _FailingAddLayout(_Layout):
    """Layout double that raises when a staged reveal adds a widget."""

    def addWidget(self, widget: object) -> None:
        """Raise a narrow expected Qt-style failure during reveal."""

        raise RuntimeError(f"cannot add {widget!r}")


class _Signal:
    """Simple signal test double supporting connect/disconnect."""

    def __init__(self) -> None:
        """Initialize connected and disconnected slot records."""

        self.connected: list[object] = []
        self.disconnected: list[object] = []

    def connect(self, slot: object) -> None:
        """Record connected slots."""

        self.connected.append(slot)

    def disconnect(self, slot: object) -> None:
        """Record disconnected slots."""

        self.disconnected.append(slot)


class _BuildSession:
    """Incremental cube-build session double used by insert tests."""

    def __init__(
        self,
        widget: object,
        step_results: list[bool] | None = None,
        *,
        first_usable_after: int = 1,
    ) -> None:
        """Store the built wrapper widget and scripted step completion results."""

        self.widget = widget
        self.step_results = list(step_results or [True])
        self.step_calls = 0
        self._first_usable_after = first_usable_after

    def step(self) -> bool:
        """Return the next scripted completion state."""

        self.step_calls += 1
        if not self.step_results:
            return True
        return self.step_results.pop(0)

    @property
    def first_usable_reached(self) -> bool:
        """Return whether scripted first-usable state has been reached."""

        return self.step_calls >= self._first_usable_after


class _TimerQueue:
    """Deterministic QTimer.singleShot queue for progressive-build tests."""

    def __init__(self) -> None:
        """Initialize the queued callback list."""

        self.callbacks: list[Callable[[], None]] = []

    def singleShot(self, _msec: int, callback: Callable[[], None]) -> None:
        """Record one scheduled callback instead of running it immediately."""

        self.callbacks.append(callback)

    def run_next(self) -> None:
        """Run one queued callback."""

        callback = self.callbacks.pop(0)
        callback()

    def run_all(self) -> None:
        """Run callbacks until the queue is empty."""

        while self.callbacks:
            self.run_next()


def _make_projection_handoff_panel(
    *,
    build_sessions: list[_BuildSession],
    registry_calls: list[str],
    workflow_session_service: SimpleNamespace,
) -> SimpleNamespace:
    """Create a panel double for projection/incremental ownership tests."""

    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 0)

    def _begin_build_cube_widget(_alias: str, _state: object) -> _BuildSession:
        """Return the next scripted build session for this handoff test."""

        return build_sessions.pop(0)

    def _remove_cube_widget_from_layout(widget: object) -> None:
        """Record discarded widgets by label for takeover assertions."""

        registry_calls.append(f"discard:{getattr(widget, 'label', 'widget')}")

    return SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={},
        cube_sections={},
        cube_headers={},
        card_wrappers={},
        _cube_states={},
        _stack_order=[],
        _layout=layout,
        scroll=SimpleNamespace(verticalScrollBar=lambda: scrollbar),
        mainwindow=SimpleNamespace(workflow_session_service=workflow_session_service),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: registry_calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: registry_calls.append(
            "reconcile"
        ),
        sync_prompt_editor_values_from_buffers=lambda: registry_calls.append(
            "prompt_values"
        ),
        _refresh_link_widgets=lambda: registry_calls.append("links"),
        sync_prompt_editor_values_for_cube=lambda alias: registry_calls.append(
            f"prompt_values:{alias}"
        ),
        refresh_link_widgets_for_cube=lambda alias: registry_calls.append(
            f"links:{alias}"
        ),
        _refresh_sampler_scheduler_link_state=lambda: registry_calls.append(
            "sampler_scheduler"
        ),
        _remove_cube_widget_from_layout=_remove_cube_widget_from_layout,
        _begin_build_cube_widget=_begin_build_cube_widget,
        _begin_projection_busy=lambda _message="Loading": "busy",
        _end_projection_busy=lambda _token: registry_calls.append("busy_end"),
        _build_behavior_snapshot=lambda **_kwargs: registry_calls.append("snapshot"),
        hydrate_node_definitions_for_projection=lambda **_kwargs: registry_calls.append(
            "hydrate"
        ),
        _on_scroll_updated=lambda _value: registry_calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "visibility"
        ),
    )
