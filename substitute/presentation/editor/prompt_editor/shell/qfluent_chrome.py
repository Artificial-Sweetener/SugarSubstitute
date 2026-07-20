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

"""Own prompt-editor QFluent chrome and lightweight lifecycle routing."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast

from PySide6.QtCore import QEvent, QObject, QRect, Qt, QTimer
from PySide6.QtGui import QFont, QPalette, QWheelEvent
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.shell.chrome_style import connect_theme_refresh


class PromptShellChromeHost(Protocol):
    """Describe host widget APIs needed by QFluent chrome ownership."""

    def font(self) -> QFont:
        """Return the live host font."""

    def palette(self) -> QPalette:
        """Return the live host palette."""


class PromptShellChromeSurface(Protocol):
    """Describe projection-surface APIs needed by shell chrome."""

    def refresh_geometry(self) -> None:
        """Refresh projection geometry after host style changes."""

    def setFont(self, font: QFont) -> None:  # noqa: N802
        """Apply the host font to the projection surface."""

    def setPalette(self, palette: QPalette) -> None:  # noqa: N802
        """Apply the host palette to the projection surface."""


class PromptShellQFluentChrome:
    """Coordinate QFluent placeholder, style, focus, and lifecycle chrome."""

    _STYLE_SYNC_EVENT_TYPES = {
        QEvent.Type.FontChange,
        QEvent.Type.PaletteChange,
        QEvent.Type.StyleChange,
    }
    _LAYOUT_EVENT_TYPES = {
        QEvent.Type.Show,
        QEvent.Type.Resize,
        QEvent.Type.LayoutRequest,
    }

    def __init__(
        self,
        *,
        host: PromptShellChromeHost,
        shell_viewport: QWidget,
        content_viewport: Callable[[], QWidget | None],
        apply_host_placeholder: Callable[[str], None],
        source_text: Callable[[], str],
        surface: Callable[[], PromptShellChromeSurface | None],
        shell_padding_fill_plane: Callable[[], QWidget | None],
        fill_plane: Callable[[], QWidget | None],
        sync_surface_scroll_metrics_from_host: Callable[[], None],
        update_backing_fill: Callable[[QRect], None],
        finish_pending_key_edit_block: Callable[[str], None],
        schedule_lora_metadata_catchup: Callable[[], None],
        handle_focus_out: Callable[[], None],
        handle_hide: Callable[[], None],
        handle_move: Callable[[], None],
        schedule_manual_height_layout_reapply: Callable[[], None],
        observes_manual_resize_bounds_viewport: Callable[[QObject], bool],
        schedule_shell_geometry_sync: Callable[[], None],
        handle_viewport_wheel_event: Callable[[QWheelEvent], bool],
    ) -> None:
        """Store shell-only collaborators without importing feature owners."""

        self._host = host
        self._shell_viewport = shell_viewport
        self._content_viewport = content_viewport
        self._apply_host_placeholder = apply_host_placeholder
        self._source_text = source_text
        self._surface = surface
        self._shell_padding_fill_plane = shell_padding_fill_plane
        self._fill_plane = fill_plane
        self._sync_surface_scroll_metrics_from_host = (
            sync_surface_scroll_metrics_from_host
        )
        self._update_backing_fill = update_backing_fill
        self._finish_pending_key_edit_block = finish_pending_key_edit_block
        self._schedule_lora_metadata_catchup = schedule_lora_metadata_catchup
        self._handle_focus_out = handle_focus_out
        self._handle_hide = handle_hide
        self._handle_move = handle_move
        self._schedule_manual_height_layout_reapply = (
            schedule_manual_height_layout_reapply
        )
        self._observes_manual_resize_bounds_viewport = (
            observes_manual_resize_bounds_viewport
        )
        self._schedule_shell_geometry_sync = schedule_shell_geometry_sync
        self._handle_viewport_wheel_event = handle_viewport_wheel_event
        self._configured_placeholder_text = ""
        self._theme_refresh_bound = False

    def bind_theme_refresh(self) -> None:
        """Refresh projection style after QFluent theme or accent changes."""

        if self._theme_refresh_bound:
            return
        self._theme_refresh_bound = True
        connect_theme_refresh(self._host, self.sync_surface_style)

    def set_placeholder_text(self, text: str) -> None:
        """Store configured placeholder text and refresh host visibility."""

        self._configured_placeholder_text = text
        self.apply_placeholder_visibility()

    def placeholder_text(self) -> str:
        """Return the configured placeholder text."""

        return self._configured_placeholder_text

    def apply_placeholder_visibility(self) -> None:
        """Keep placeholder rendering owned by the QFluent host document."""

        self._apply_host_placeholder(
            self._configured_placeholder_text if not self._source_text() else ""
        )

    def sync_surface_style(self) -> None:
        """Push the live host font and palette onto the projection surface."""

        surface = self._surface()
        if surface is None:
            return
        surface.setFont(self._host.font())
        surface.setPalette(self._host.palette())
        self._sync_surface_scroll_metrics_from_host()
        surface.refresh_geometry()
        self.update_fill_planes()

    def handle_surface_backing_fill_invalidated(self, rect: QRect) -> None:
        """Repaint shell-owned fill layers under a dirty projection rect."""

        self._update_backing_fill(rect)

    def configure_owned_fill_plane(self) -> None:
        """Let prompt fill planes show through transparent shell widgets."""

        self._shell_viewport.setAutoFillBackground(False)
        self._shell_viewport.setAttribute(
            Qt.WidgetAttribute.WA_NoSystemBackground,
            True,
        )

    def handle_focus_in(self) -> None:
        """Refresh ready feature chrome after the editor gains focus."""

        self._schedule_lora_metadata_catchup()

    def finish_pending_focus_out_edit_block(self) -> None:
        """Finish pending source edit grouping before host focus-out handling."""

        self._finish_pending_key_edit_block("editor_focus_out")

    def schedule_focus_out_cleanup(self, reason: Qt.FocusReason) -> None:
        """Defer focus-out interaction cleanup until Qt focus routing settles."""

        QTimer.singleShot(0, lambda: self._resolve_focus_out_cleanup(reason))

    def _resolve_focus_out_cleanup(self, reason: Qt.FocusReason) -> None:
        """Clean up only after focus has conclusively left the editor flow."""

        host = cast(QWidget, self._host)
        focus_widget = QApplication.focusWidget()
        if focus_widget is host or (
            focus_widget is not None and host.isAncestorOf(focus_widget)
        ):
            return
        if focus_widget is None and reason == Qt.FocusReason.ActiveWindowFocusReason:
            return
        self._handle_focus_out()

    def handle_hide(self) -> None:
        """Route editor-hide cleanup to the interaction owner."""

        self._handle_hide()

    def handle_show(self) -> None:
        """Refresh ready feature chrome after a hidden editor becomes visible."""

        self._schedule_lora_metadata_catchup()

    def focus_next_prev_child(self, next_child: bool) -> bool:
        """Keep Tab inside the prompt editor for autocomplete handling."""

        _ = next_child
        return False

    def handle_resize(self) -> None:
        """Refresh shell layout after the host is resized."""

        self._schedule_manual_height_layout_reapply()
        self._schedule_shell_geometry_sync()

    def handle_move(self) -> None:
        """Route host move handling to the interaction owner."""

        self._handle_move()

    def handle_change_event(self, event: QEvent) -> None:
        """Refresh projection style after cheap host style changes."""

        if event.type() in self._STYLE_SYNC_EVENT_TYPES:
            self.sync_surface_style()

    def handle_event_filter(self, watched: QObject, event: QEvent) -> bool | None:
        """Handle shell-owned viewport lifecycle events.

        Returns:
            ``True`` or ``False`` when the shell consumed the event decision;
            ``None`` when the public widget should continue with its own routing.
        """

        event_type = event.type()
        if (
            self._observes_manual_resize_bounds_viewport(watched)
            and event_type in self._LAYOUT_EVENT_TYPES
        ):
            self._schedule_manual_height_layout_reapply()
        content_viewport = self._content_viewport()
        if watched is not self._shell_viewport and watched is not content_viewport:
            return None
        if event_type == QEvent.Type.Wheel:
            return self._handle_viewport_wheel_event(cast(QWheelEvent, event))
        if event_type in self._LAYOUT_EVENT_TYPES:
            self._schedule_shell_geometry_sync()
        return None

    def update_fill_planes(self) -> None:
        """Repaint passive fill planes after placeholder or style changes."""

        shell_padding_fill_plane = self._shell_padding_fill_plane()
        if shell_padding_fill_plane is not None:
            shell_padding_fill_plane.update()
        fill_plane = self._fill_plane()
        if fill_plane is not None:
            fill_plane.update()


__all__ = [
    "PromptShellChromeHost",
    "PromptShellChromeSurface",
    "PromptShellQFluentChrome",
]
