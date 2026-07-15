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

"""Own prompt-editor QFluent scroll chrome and viewport geometry sync."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, cast

from PySide6.QtCore import QObject, QRect, QTimer
from PySide6.QtWidgets import QScrollBar, QWidget

from sugarsubstitute_shared.presentation.widgets.scrolling import (
    configure_qfluent_scroll_surface,
)

from ..qt_lifecycle import qt_object_is_alive


class PromptShellScrollHost(Protocol):
    """Describe host widget APIs needed by shell scroll geometry."""

    def rect(self) -> QRect:
        """Return the host rectangle."""

    def updateGeometry(self) -> None:  # noqa: N802
        """Notify parent layouts that host geometry changed."""

    def viewport(self) -> QWidget:
        """Return the projection viewport exposed through the public widget."""


class PromptShellScrollSurface(Protocol):
    """Describe projection-surface APIs needed by shell scroll geometry."""

    def content_height(self) -> float:
        """Return the current projection content height."""

    def has_pending_projection_update(self) -> bool:
        """Return whether projection work is pending."""

    def has_stale_projection_geometry(self) -> bool:
        """Return whether current geometry is stale-safe."""

    def raise_(self) -> None:
        """Raise the projection surface above passive shell layers."""

    def refresh_geometry(self) -> None:
        """Refresh projection geometry after shell layout changes."""

    def refresh_scroll(self) -> None:
        """Refresh projection scroll painting."""

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        """Apply shell viewport geometry to the projection surface."""

    def verticalScrollBar(self) -> QScrollBar:  # noqa: N802
        """Return the projection-owned vertical scrollbar."""


class PromptShellSignal(Protocol):
    """Describe simple Qt signals emitted by shell geometry sync."""

    def emit(self) -> None:
        """Emit the signal."""


class PromptShellScrollDelegate:
    """Coordinate shell-owned scroll chrome and viewport geometry."""

    def __init__(
        self,
        *,
        host: PromptShellScrollHost,
        shell_viewport: QWidget,
        host_scrollbar: Callable[[], QScrollBar],
        surface: Callable[[], PromptShellScrollSurface | None],
        shell_padding_fill_plane: Callable[[], QWidget | None],
        fill_plane: Callable[[], QWidget | None],
        token_weight_controls: Callable[[], QWidget | None],
        handle_content_height_changed: Callable[[float], None],
        layout_resize_handle: Callable[[], None],
        handle_viewport_scroll: Callable[[], None],
        handle_resize: Callable[[], None],
        resized: PromptShellSignal,
    ) -> None:
        """Store shell collaborators without taking feature ownership."""

        self._host = host
        self._shell_viewport = shell_viewport
        self._host_scrollbar = host_scrollbar
        self._surface = surface
        self._shell_padding_fill_plane = shell_padding_fill_plane
        self._fill_plane = fill_plane
        self._token_weight_controls = token_weight_controls
        self._handle_content_height_changed = handle_content_height_changed
        self._layout_resize_handle = layout_resize_handle
        self._handle_viewport_scroll = handle_viewport_scroll
        self._handle_resize = handle_resize
        self._resized = resized
        self._shell_geometry_sync_pending = False
        self._shell_geometry_follow_up_pending = False
        self._visible_scrollbar_value_connected = False

    @property
    def geometry_sync_pending(self) -> bool:
        """Return whether a shell geometry pass is queued."""

        return self._shell_geometry_sync_pending

    @geometry_sync_pending.setter
    def geometry_sync_pending(self, pending: bool) -> None:
        """Set the queued shell geometry flag for guardrail tests."""

        self._shell_geometry_sync_pending = pending

    @property
    def geometry_follow_up_pending(self) -> bool:
        """Return whether a trailing geometry pass is queued."""

        return self._shell_geometry_follow_up_pending

    @geometry_follow_up_pending.setter
    def geometry_follow_up_pending(self, pending: bool) -> None:
        """Set the trailing shell geometry flag for guardrail tests."""

        self._shell_geometry_follow_up_pending = pending

    def configure_host_scroll_delegate(self) -> None:
        """Disable QFluent-owned wheel smoothing for prompt content."""

        configure_qfluent_scroll_surface(self._host)
        scroll_delegate = self._scroll_delegate()
        if scroll_delegate is None:
            return
        self._shell_viewport.removeEventFilter(scroll_delegate)

    def bind_host_scroll_delegate_to_surface(
        self,
        surface: PromptShellScrollSurface,
    ) -> None:
        """Retarget QFluent's visible scrollbar shell to the projection surface."""

        scroll_delegate = self._scroll_delegate()
        if scroll_delegate is None:
            return
        surface_scroll_bar = surface.verticalScrollBar()
        visible_scroll_bar = scroll_delegate.vScrollBar
        previous_partner = getattr(visible_scroll_bar, "partnerBar", None)
        if previous_partner is not None and previous_partner is not surface_scroll_bar:
            self._disconnect_scrollbar_signal(
                previous_partner.rangeChanged,
                visible_scroll_bar.setRange,
            )
            self._disconnect_scrollbar_signal(
                previous_partner.valueChanged,
                visible_scroll_bar._onValueChanged,
            )
            self._disconnect_scrollbar_signal(
                visible_scroll_bar.valueChanged,
                previous_partner.setValue,
            )
        if self._visible_scrollbar_value_connected:
            self._disconnect_scrollbar_signal(
                visible_scroll_bar.valueChanged,
                self.handle_visible_scroll_bar_value_changed,
            )
        visible_scroll_bar.partnerBar = surface_scroll_bar
        surface_scroll_bar.rangeChanged.connect(visible_scroll_bar.setRange)
        surface_scroll_bar.valueChanged.connect(visible_scroll_bar._onValueChanged)
        visible_scroll_bar.valueChanged.connect(
            self.handle_visible_scroll_bar_value_changed
        )
        self._visible_scrollbar_value_connected = True
        self.sync_host_scrollbar_shell()

    def handle_viewport_scroll_value_changed(self, _value: int) -> None:
        """Refresh shell scroll chrome after projection scrollbar movement."""

        surface = self._surface()
        if surface is None:
            return
        self.sync_host_scrollbar_shell()
        surface.refresh_scroll()
        self._update_fill_planes()
        self._handle_viewport_scroll()

    def handle_visible_scroll_bar_value_changed(self, value: int) -> None:
        """Apply user-owned visible scrollbar moves without accepting mirror noise."""

        visible_scroll_bar = self.visible_scrollbar()
        surface = self._surface()
        if visible_scroll_bar is None or surface is None:
            return
        surface_scroll_bar = surface.verticalScrollBar()
        if not self._visible_scroll_change_is_user_driven(visible_scroll_bar):
            return
        surface_scroll_bar.setValue(value)

    def schedule_shell_geometry_sync(self) -> None:
        """Coalesce geometry changes and leave one trailing settled-width pass."""

        if self._shell_geometry_sync_pending:
            self._shell_geometry_follow_up_pending = True
            return
        self._shell_geometry_sync_pending = True
        self._shell_geometry_follow_up_pending = True
        QTimer.singleShot(0, self.sync_shell_geometry)

    def sync_shell_geometry(self) -> None:
        """Rebuild prompt layout and finish once live viewport widths settle."""

        if not qt_object_is_alive(cast(QObject, self._host)):
            self._clear_geometry_pending()
            return
        surface = self._surface()
        if surface is None or not qt_object_is_alive(cast(QObject, surface)):
            self._clear_geometry_pending()
            return
        try:
            self.layout_surface()
            surface.refresh_geometry()
            if (
                surface.has_stale_projection_geometry()
                and surface.has_pending_projection_update()
            ):
                self._host.updateGeometry()
                self._clear_geometry_pending()
                return
            content_height = surface.content_height()
            self._handle_content_height_changed(content_height)
            self._host.updateGeometry()
            self._resized.emit()
            self._handle_resize()
        except RuntimeError as error:
            if not _is_deleted_qt_object_error(error):
                raise
            self._clear_geometry_pending()
            return
        if self._shell_geometry_follow_up_pending:
            self._shell_geometry_follow_up_pending = False
            QTimer.singleShot(0, self.sync_shell_geometry)
            return
        self._shell_geometry_sync_pending = False

    def layout_surface(self) -> None:
        """Resize the projection surface to match the live QFluent viewport."""

        surface = self._surface()
        if surface is None:
            return
        shell_rect = self._shell_viewport.rect()
        shell_padding_fill_plane = self._shell_padding_fill_plane()
        if shell_padding_fill_plane is not None:
            shell_padding_fill_plane.setGeometry(self._host.rect())
            shell_padding_fill_plane.lower()
            shell_padding_fill_plane.update()
        fill_plane = self._fill_plane()
        if fill_plane is not None:
            fill_plane.setGeometry(shell_rect)
            fill_plane.lower()
            fill_plane.update()
        surface.setGeometry(shell_rect)
        surface.raise_()
        token_weight_controls = self._token_weight_controls()
        if token_weight_controls is not None:
            token_weight_controls.setGeometry(self._host.viewport().rect())
        self._layout_resize_handle()

    def sync_host_scrollbar_shell(self) -> None:
        """Keep QFluent's visible scrollbar shell aligned to projection scroll."""

        surface = self._surface()
        visible_scroll_bar = self.visible_scrollbar()
        if surface is None or visible_scroll_bar is None:
            return
        native_scroll_bar = surface.verticalScrollBar()
        qfluent_scroll_bar = cast(Any, visible_scroll_bar)
        qfluent_scroll_bar.setSingleStep(native_scroll_bar.singleStep())
        qfluent_scroll_bar.setPageStep(native_scroll_bar.pageStep())
        reset_value = getattr(qfluent_scroll_bar, "resetValue", None)
        if callable(reset_value):
            reset_value(native_scroll_bar.value())

    def sync_surface_scroll_metrics_from_host(self) -> None:
        """Mirror host textbox wheel-step metrics onto projection scrollbar."""

        surface = self._surface()
        if surface is None:
            return
        host_scroll_bar = self._host_scrollbar()
        surface_scroll_bar = surface.verticalScrollBar()
        surface_scroll_bar.setSingleStep(host_scroll_bar.singleStep())

    def visible_scrollbar(self) -> QWidget | None:
        """Return QFluent's visible vertical scrollbar when available."""

        scroll_delegate = self._scroll_delegate()
        visible_scroll_bar = getattr(scroll_delegate, "vScrollBar", None)
        return visible_scroll_bar if isinstance(visible_scroll_bar, QWidget) else None

    def _scroll_delegate(self) -> Any | None:
        """Return the host's QFluent scroll delegate when present."""

        return getattr(self._host, "scrollDelegate", None)

    def _update_fill_planes(self) -> None:
        """Repaint passive shell fill layers after scroll or geometry changes."""

        shell_padding_fill_plane = self._shell_padding_fill_plane()
        if shell_padding_fill_plane is not None:
            shell_padding_fill_plane.update()
        fill_plane = self._fill_plane()
        if fill_plane is not None:
            fill_plane.update()

    def _clear_geometry_pending(self) -> None:
        """Clear all pending geometry-pass flags."""

        self._shell_geometry_follow_up_pending = False
        self._shell_geometry_sync_pending = False

    def _disconnect_scrollbar_signal(self, signal: object, slot: object) -> None:
        """Disconnect one Qt signal/slot pair when currently connected."""

        try:
            cast(Any, signal).disconnect(slot)
        except (RuntimeError, TypeError):
            return

    def _visible_scroll_change_is_user_driven(self, scroll_bar: object) -> bool:
        """Return whether a visible scrollbar signal came from pointer ownership."""

        try:
            is_slider_down = getattr(scroll_bar, "isSliderDown", None)
            if callable(is_slider_down) and bool(is_slider_down()):
                return True
            under_mouse = getattr(scroll_bar, "underMouse", None)
            if callable(under_mouse) and bool(under_mouse()):
                return True
        except RuntimeError:
            return False
        return False


def _is_deleted_qt_object_error(error: RuntimeError) -> bool:
    """Return whether a runtime error came from a deleted Qt wrapper."""

    return "Internal C++ object" in str(error) and "already deleted" in str(error)


__all__ = [
    "PromptShellScrollDelegate",
    "PromptShellScrollHost",
    "PromptShellScrollSurface",
    "PromptShellSignal",
]
