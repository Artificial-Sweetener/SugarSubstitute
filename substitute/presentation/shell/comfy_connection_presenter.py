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

"""Present non-blocking Comfy connection and restart feedback."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    InfoBar,
    InfoBarIcon,
    InfoBarPosition,
    PushButton,
)
from sugarsubstitute_shared.presentation.localization import (
    app_text,
    render_application_text,
)

from substitute.domain.comfy_connection import (
    ComfyConnectionPhase,
    ComfyConnectionState,
    ComfyConnectionStateChange,
)


class ComfyConnectionPresenter:
    """Own one deduplicated workspace-level connection status InfoBar."""

    def __init__(
        self,
        *,
        notification_surface: QWidget,
        request_restart: Callable[[], object],
        open_connection_settings: Callable[[], object],
    ) -> None:
        """Bind connection feedback and recovery actions to one workspace surface."""

        self._notification_surface = notification_surface
        self._request_restart = request_restart
        self._open_connection_settings = open_connection_settings
        self._active_bar: InfoBar | None = None
        self._last_revision = -1

    def present(self, change: ComfyConnectionStateChange) -> None:
        """Project one authoritative connection transition into window feedback."""

        current = change.current
        if current.revision <= self._last_revision:
            return
        self._last_revision = current.revision
        phase = current.phase
        if phase is ComfyConnectionPhase.RECONNECTING:
            return
        if phase is ComfyConnectionPhase.DISCONNECTED:
            self._show_disconnected(current)
            return
        if phase is ComfyConnectionPhase.RESTARTING:
            self._show_restarting()
            return
        if phase is ComfyConnectionPhase.RESTART_FAILED:
            self._show_restart_failed(current)
            return
        if phase is ComfyConnectionPhase.READY:
            self._show_ready(change.previous.phase)

    def close(self) -> None:
        """Close active connection feedback during shell teardown."""

        self._close_active_bar()

    def _show_disconnected(self, state: ComfyConnectionState) -> None:
        """Show sustained outage feedback with only target-safe actions."""

        bar = self._create_bar(
            icon=InfoBarIcon.ERROR,
            title=render_application_text(app_text("Comfy disconnected")),
            duration=-1,
        )
        if state.can_restart:
            self._add_action(
                bar,
                text=render_application_text(app_text("Restart Comfy")),
                object_name="restartComfyButton",
                callback=self._request_restart,
            )
        else:
            self._add_action(
                bar,
                text=render_application_text(app_text("Settings")),
                object_name="openComfyConnectionSettingsButton",
                callback=self._open_connection_settings,
            )
        self._replace_bar(bar)

    def _show_restarting(self) -> None:
        """Show persistent progress feedback while the owned server restarts."""

        self._replace_bar(
            self._create_bar(
                icon=InfoBarIcon.INFORMATION,
                title=render_application_text(app_text("Restarting Comfy")),
                is_closable=False,
                duration=-1,
            )
        )

    def _show_restart_failed(self, state: ComfyConnectionState) -> None:
        """Show a recoverable failure without exposing technical diagnostics."""

        bar = self._create_bar(
            icon=InfoBarIcon.ERROR,
            title=render_application_text(app_text("Comfy restart failed")),
            duration=-1,
        )
        if state.can_restart:
            self._add_action(
                bar,
                text=render_application_text(app_text("Retry")),
                object_name="retryComfyRestartButton",
                callback=self._request_restart,
            )
        self._add_action(
            bar,
            text=render_application_text(app_text("Settings")),
            object_name="openComfyConnectionSettingsButton",
            callback=self._open_connection_settings,
        )
        self._replace_bar(bar)

    def _show_ready(self, previous_phase: ComfyConnectionPhase) -> None:
        """Confirm recovery only when a prior outage was visible or restarting."""

        self._close_active_bar()
        if previous_phase is ComfyConnectionPhase.RESTARTING:
            self._replace_bar(
                self._create_bar(
                    icon=InfoBarIcon.SUCCESS,
                    title=render_application_text(app_text("Comfy restarted")),
                    duration=3000,
                )
            )
        elif previous_phase in {
            ComfyConnectionPhase.DISCONNECTED,
            ComfyConnectionPhase.RESTART_FAILED,
        }:
            self._replace_bar(
                self._create_bar(
                    icon=InfoBarIcon.SUCCESS,
                    title=render_application_text(app_text("Comfy reconnected")),
                    duration=3000,
                )
            )

    def _create_bar(
        self,
        *,
        icon: InfoBarIcon,
        title: str,
        is_closable: bool = True,
        duration: int,
    ) -> InfoBar:
        """Create an unshown bar so actions contribute to right-edge placement."""

        return InfoBar(
            icon=icon,
            title=title,
            content="",
            isClosable=is_closable,
            duration=duration,
            position=InfoBarPosition.TOP_RIGHT,
            parent=self._notification_surface,
        )

    def _replace_bar(self, bar: InfoBar) -> InfoBar:
        """Replace existing feedback and track user dismissal safely."""

        self._close_active_bar()
        self._active_bar = bar
        bar.setObjectName("comfyConnectionInfoBar")

        def clear_reference() -> None:
            """Forget the bar only when this exact instance was dismissed."""

            if self._active_bar is bar:
                self._active_bar = None

        bar.closedSignal.connect(clear_reference)
        bar.show()
        return bar

    @staticmethod
    def _add_action(
        bar: InfoBar,
        *,
        text: str,
        object_name: str,
        callback: Callable[[], object],
    ) -> None:
        """Add one native Fluent action button to an InfoBar."""

        button = PushButton(text, bar)
        button.setObjectName(object_name)
        button.clicked.connect(callback)
        bar.addWidget(button)
        bar.adjustSize()

    def _close_active_bar(self) -> None:
        """Close the tracked InfoBar without retaining a stale Qt wrapper."""

        bar = self._active_bar
        self._active_bar = None
        if bar is not None:
            bar.close()


__all__ = ["ComfyConnectionPresenter"]
