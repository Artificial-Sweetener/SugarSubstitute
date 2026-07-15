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

"""Own prompt-editor shell height and manual resize policy."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Protocol, cast

from PySide6.QtCore import QMargins, QObject, QSize, Qt, QTimer
from PySide6.QtWidgets import QWidget

from ..qt_lifecycle import qt_object_is_alive


class PromptShellSizingSignal(Protocol):
    """Describe the public manual-height signal consumed by sizing policy."""

    def emit(self, value: object) -> None:
        """Emit one public manual-height change value."""


class PromptShellSizingDocument(Protocol):
    """Describe document metrics needed for shell height calculations."""

    def documentMargin(self) -> float:  # noqa: N802
        """Return the live document margin."""


class PromptShellSizingHost(Protocol):
    """Describe the QWidget APIs needed by the shell sizing controller."""

    def contentsMargins(self) -> QMargins:
        """Return current host contents margins."""

    def document(self) -> PromptShellSizingDocument:
        """Return the live document used for text metrics."""

    def height(self) -> int:
        """Return current host height."""

    def isEnabled(self) -> bool:  # noqa: N802
        """Return whether the host is currently enabled."""

    def setFixedHeight(self, height: int) -> None:  # noqa: N802
        """Set a fixed host height."""

    def setMaximumHeight(self, height: int) -> None:  # noqa: N802
        """Set the maximum host height."""

    def setMinimumHeight(self, height: int) -> None:  # noqa: N802
        """Set the minimum host height."""

    def setVerticalScrollBarPolicy(  # noqa: N802
        self,
        policy: Qt.ScrollBarPolicy,
    ) -> None:
        """Set the host scrollbar policy."""

    def updateGeometry(self) -> None:  # noqa: N802
        """Notify parent layouts that host geometry changed."""

    def verticalScrollBarPolicy(self) -> Qt.ScrollBarPolicy:  # noqa: N802
        """Return the current host scrollbar policy."""

    def width(self) -> int:
        """Return current host width."""


class PromptShellSizingController:
    """Apply prompt-editor shell sizing without owning editor semantics."""

    _MAX_MANUAL_HEIGHT_VIEWPORT_RATIO = 0.65

    def __init__(
        self,
        *,
        host: PromptShellSizingHost,
        maximum_visible_lines: int | None,
        manual_scroll_height_changed: PromptShellSizingSignal,
        surface_content_height: Callable[[], float],
        projection_line_height: Callable[[], float],
        surface_is_alive: Callable[[], bool],
        sync_surface_scroll_metrics_from_host: Callable[[], None],
        sync_host_scrollbar_shell: Callable[[], None],
        schedule_shell_geometry_sync: Callable[[], None],
        update_fill_planes: Callable[[], None],
        resize_handle: Callable[[], QWidget | None],
        visible_scrollbar: Callable[[], QWidget | None],
        ancestor_external_wheel_handler: Callable[[], object | None],
    ) -> None:
        """Create a shell-local height policy owner around existing collaborators."""

        self._host = host
        self._maximum_visible_lines = maximum_visible_lines
        self._manual_scroll_height_changed = manual_scroll_height_changed
        self._surface_content_height = surface_content_height
        self._projection_line_height = projection_line_height
        self._surface_is_alive = surface_is_alive
        self._sync_surface_scroll_metrics_from_host = (
            sync_surface_scroll_metrics_from_host
        )
        self._sync_host_scrollbar_shell = sync_host_scrollbar_shell
        self._schedule_shell_geometry_sync = schedule_shell_geometry_sync
        self._update_fill_planes = update_fill_planes
        self._resize_handle = resize_handle
        self._visible_scrollbar = visible_scrollbar
        self._ancestor_external_wheel_handler = ancestor_external_wheel_handler
        self._manual_scroll_height: int | None = None
        self._last_content_height = 0.0
        self._last_natural_height = 0
        self._last_effective_height = 0
        self._scroll_mode_active = False
        self._manual_resize_available = False
        self._pending_content_height: float | None = None
        self._height_commit_pending = False
        self._manual_height_layout_reapply_pending = False
        self._manual_resize_bounds_viewport_filter: QWidget | None = None

    @property
    def last_natural_height(self) -> int:
        """Return the last content-fitted shell height."""

        return self._last_natural_height

    def line_height(self) -> int:
        """Return the projection-owned single-line text height used by grow policy."""

        return max(1, int(math.ceil(self._projection_line_height())))

    def minimum_editor_height(self) -> int:
        """Return the shell height for one visible line inside the host."""

        return self.line_height() + self._shell_vertical_padding()

    def manual_scroll_height(self) -> int | None:
        """Return the user-requested durable manual prompt height."""

        return self._manual_scroll_height

    def set_manual_scroll_height(self, height: int | None) -> None:
        """Store a user-owned scroll-mode height preference."""

        previous_height = self._manual_scroll_height
        content_height = (
            self._last_content_height
            if self._last_content_height > 0
            else self._surface_content_height()
        )
        if height is None:
            self._manual_scroll_height = None
        else:
            minimum_height, _maximum_height = self._manual_resize_bounds()
            self._manual_scroll_height = max(minimum_height, int(height))
        if self._manual_scroll_height != previous_height:
            self._manual_scroll_height_changed.emit(self._manual_scroll_height)
        self.handle_surface_content_height_changed(content_height)
        self._schedule_shell_geometry_sync()
        self.schedule_manual_height_layout_reapply()

    def size_hint(self) -> QSize:
        """Return a size hint whose height tracks the fixed shell height."""

        return QSize(max(240, self._host.width()), self._host.height())

    def minimum_size_hint(self) -> QSize:
        """Return a minimum size hint whose height tracks the shell height."""

        return QSize(120, self._host.height())

    def handle_surface_content_height_changed(self, content_height: float) -> None:
        """Schedule QFluent-shell height policy after content changes."""

        self._last_content_height = content_height
        self._pending_content_height = content_height
        self._schedule_height_commit()

    def apply_preferred_height(self, preferred_height: int) -> None:
        """Persist the host-managed preferred height onto the public widget."""

        if self._maximum_visible_lines is None:
            self._host.setMinimumHeight(self.minimum_editor_height())
            self._host.setMaximumHeight(16777215)
            self._host.updateGeometry()
            return
        if self._host.height() != preferred_height:
            self._host.setFixedHeight(preferred_height)
        self._host.updateGeometry()

    def schedule_manual_height_layout_reapply(self) -> None:
        """Defer visible-height recompute from the durable manual preference."""

        if not qt_object_is_alive(cast(QObject, self._host)):
            return
        if self._manual_scroll_height is None:
            return
        if self._manual_height_layout_reapply_pending:
            return
        self._manual_height_layout_reapply_pending = True
        QTimer.singleShot(0, self.reapply_manual_height_for_current_layout)

    def reapply_manual_height_for_current_layout(self) -> None:
        """Recompute visible height after parent layout bounds settle."""

        self._manual_height_layout_reapply_pending = False
        if not qt_object_is_alive(cast(QObject, self._host)):
            return
        if not self._surface_is_alive():
            return
        if self._manual_scroll_height is None:
            return
        content_height = (
            self._last_content_height
            if self._last_content_height > 0
            else self._surface_content_height()
        )
        self.handle_surface_content_height_changed(content_height)
        self._schedule_shell_geometry_sync()

    def layout_resize_handle(self) -> None:
        """Place the resize handle on the editor bottom edge."""

        resize_handle = self._resize_handle()
        if resize_handle is None:
            return
        visible_scrollbar = self._visible_scrollbar()
        scrollbar_width = (
            visible_scrollbar.width()
            if visible_scrollbar is not None and visible_scrollbar.isVisible()
            else 0
        )
        handle_height = resize_handle.height()
        resize_handle.setGeometry(
            0,
            max(0, self._host.height() - handle_height),
            max(0, self._host.width() - scrollbar_width),
            handle_height,
        )

    def scroll_mode_is_active(self) -> bool:
        """Return whether the prompt editor currently has overflow content."""

        return self._scroll_mode_active

    def detach_manual_resize_bounds_filter(self) -> None:
        """Remove the parent viewport event filter owned by manual sizing."""

        if self._manual_resize_bounds_viewport_filter is not None:
            self._manual_resize_bounds_viewport_filter.removeEventFilter(
                cast(QObject, self._host)
            )
            self._manual_resize_bounds_viewport_filter = None

    def observes_manual_resize_bounds_viewport(self, watched: QObject) -> bool:
        """Return whether one event-filter target belongs to manual sizing."""

        return watched is self._manual_resize_bounds_viewport_filter

    def _schedule_height_commit(self) -> None:
        """Coalesce prompt height application onto a settled event-loop turn."""

        if not qt_object_is_alive(cast(QObject, self._host)):
            return
        if self._height_commit_pending:
            return
        self._height_commit_pending = True
        QTimer.singleShot(0, self._commit_pending_height)

    def _commit_pending_height(self) -> None:
        """Apply the latest pending content height to the public widget."""

        self._height_commit_pending = False
        if not qt_object_is_alive(cast(QObject, self._host)):
            return
        content_height = self._pending_content_height
        if content_height is None:
            return
        self._pending_content_height = None
        self._apply_height_for_content(content_height)

    def _apply_height_for_content(self, content_height: float) -> None:
        """Apply one content-height snapshot through the height policy."""

        self._last_content_height = content_height
        previous_resize_available = self._manual_resize_available
        previous_scroll_mode = self._scroll_mode_active
        preferred_height, needs_vertical_scroll = self._target_height_for_content(
            content_height
        )
        target_policy = (
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
            if needs_vertical_scroll
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        policy_changed = self._host.verticalScrollBarPolicy() != target_policy
        height_changed = (
            self._maximum_visible_lines is None
            or self._host.height() != preferred_height
        )
        if policy_changed:
            self._host.setVerticalScrollBarPolicy(target_policy)
        self._sync_surface_scroll_metrics_from_host()
        self._sync_host_scrollbar_shell()
        if height_changed:
            self.apply_preferred_height(preferred_height)
        elif (
            previous_resize_available != self._manual_resize_available
            or previous_scroll_mode != self._scroll_mode_active
        ):
            self._host.updateGeometry()
        if height_changed or previous_resize_available != self._manual_resize_available:
            self._sync_resize_handle()
        self._update_fill_planes()

    def _sync_resize_handle(self) -> None:
        """Update manual resize affordance visibility and placement."""

        resize_handle = self._resize_handle()
        if resize_handle is None:
            return
        should_show = (
            self._maximum_visible_lines is not None
            and self._manual_resize_available
            and self._host.isEnabled()
        )
        resize_handle.setVisible(should_show)
        if should_show:
            self.layout_resize_handle()
            resize_handle.raise_()

    def _target_height_for_content(self, content_height: float) -> tuple[int, bool]:
        """Return the preferred editor height and whether scrolling is needed."""

        natural_height = self._natural_height_for_content(content_height)
        self._last_natural_height = natural_height
        maximum_visible_lines = self._maximum_visible_lines
        if maximum_visible_lines is None:
            viewport_height = max(self.minimum_editor_height(), self._host.height())
            self._last_effective_height = viewport_height
            self._scroll_mode_active = natural_height > viewport_height
            self._manual_resize_available = False
            return viewport_height, self._scroll_mode_active
        default_scroll_height = self._default_scroll_height()
        self._manual_resize_available = natural_height > default_scroll_height
        if self._manual_resize_available:
            requested_cap = self._manual_scroll_height or default_scroll_height
            bounded_cap = self._clamped_visible_manual_height(requested_cap)
            effective_height = min(natural_height, bounded_cap)
        else:
            effective_height = natural_height
        needs_vertical_scroll = natural_height > effective_height
        self._last_effective_height = effective_height
        self._scroll_mode_active = needs_vertical_scroll
        return effective_height, needs_vertical_scroll

    def _natural_height_for_content(self, content_height: float) -> int:
        """Return the prompt editor height needed to fit current content."""

        minimum_document_height = self.line_height() + self._document_vertical_padding()
        document_height = max(math.ceil(content_height), minimum_document_height)
        return document_height + self._outer_vertical_padding()

    def _document_vertical_padding(self) -> int:
        """Return the projection document top/bottom padding in pixels."""

        return int(round(self._host.document().documentMargin() * 2.0))

    def _outer_vertical_padding(self) -> int:
        """Return the host shell padding outside the viewport."""

        margins = self._host.contentsMargins()
        return margins.top() + margins.bottom()

    def _shell_vertical_padding(self) -> int:
        """Return the total non-line padding that surrounds visible text."""

        return self._document_vertical_padding() + self._outer_vertical_padding()

    def _default_scroll_height(self) -> int:
        """Return the automatic scroll-mode prompt height cap."""

        maximum_visible_lines = self._maximum_visible_lines
        if maximum_visible_lines is None:
            return self.minimum_editor_height()
        return (
            self.line_height() * maximum_visible_lines + self._shell_vertical_padding()
        )

    def _manual_resize_bounds(self) -> tuple[int, int]:
        """Return the allowed manual prompt viewport height range."""

        minimum_height = self._default_scroll_height()
        viewport = self._manual_resize_bounds_viewport()
        self._sync_manual_resize_bounds_viewport_filter(viewport)
        if isinstance(viewport, QWidget) and viewport.height() > 0:
            maximum_height = round(
                viewport.height() * self._MAX_MANUAL_HEIGHT_VIEWPORT_RATIO
            )
        else:
            maximum_height = minimum_height * 2
        return minimum_height, max(minimum_height, maximum_height)

    def _sync_manual_resize_bounds_viewport_filter(
        self,
        viewport: QWidget | None,
    ) -> None:
        """Observe parent viewport changes that can reveal stored manual height."""

        if viewport is self._manual_resize_bounds_viewport_filter:
            return
        self.detach_manual_resize_bounds_filter()
        self._manual_resize_bounds_viewport_filter = viewport
        if viewport is not None:
            viewport.installEventFilter(cast(QObject, self._host))

    def _clamped_visible_manual_height(self, height: int) -> int:
        """Return one visible manual height clamped to current layout bounds."""

        minimum_height, maximum_height = self._manual_resize_bounds()
        return max(minimum_height, min(int(height), maximum_height))

    def _manual_resize_bounds_viewport(self) -> QWidget | None:
        """Return the editor-panel viewport that bounds visible manual height."""

        panel = self._ancestor_external_wheel_handler()
        scroll = getattr(panel, "scroll", None) if panel is not None else None
        viewport_method = getattr(scroll, "viewport", None)
        viewport = viewport_method() if callable(viewport_method) else None
        return viewport if isinstance(viewport, QWidget) else None


__all__ = [
    "PromptShellSizingController",
    "PromptShellSizingDocument",
    "PromptShellSizingHost",
    "PromptShellSizingSignal",
]
