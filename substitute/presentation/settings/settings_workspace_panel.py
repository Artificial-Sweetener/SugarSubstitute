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

"""Host one active Settings detail page with Fluent page transitions."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import app_text

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import cast

from PySide6.QtCore import Property, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import (
    QGraphicsEffect,
    QGraphicsOpacityEffect,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets.common.icon import FluentIconBase  # type: ignore[import-untyped]
from sugarsubstitute_shared.presentation.localization import ApplicationText

from substitute.presentation.motion import (
    SETTINGS_PAGE_TRANSITION_DURATION_MS,
    SETTINGS_PAGE_TRANSITION_OFFSET,
    TRANSFORM_EASING_CURVE,
    restart_property_animation,
)
from substitute.presentation.settings.settings_page_shell import SettingsPageShell
from substitute.presentation.settings.settings_style import SETTINGS_CONTENT_MAX_WIDTH
from substitute.shared.logging.logger import get_logger

_LOGGER = get_logger("presentation.settings.settings_workspace_panel")


SettingsPageWidgetFactory = Callable[[QWidget], QWidget]


@dataclass(frozen=True)
class SettingsPageDescriptor:
    """Describe one page registered in the Settings workspace."""

    page_id: str
    title: ApplicationText
    subtitle: ApplicationText
    icon: FluentIconBase | str | None
    widget: QWidget | None = None
    create_widget: SettingsPageWidgetFactory | None = None

    def create_page_widget(self, parent: QWidget) -> QWidget:
        """Create or return the page widget for one Settings descriptor."""

        if self.widget is not None:
            self.widget.setParent(parent)
            return self.widget
        if self.create_widget is None:
            raise ValueError(f"Settings page '{self.page_id}' has no widget factory.")
        return self.create_widget(parent)


class SettingsWorkspacePanel(QWidget):
    """Host one active Settings detail page with Fluent page transitions."""

    currentPageChanged = Signal(str)
    searchQueryChanged = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create an empty active-page Settings host."""

        super().__init__(parent)
        self._page_order: list[str] = []
        self._page_descriptors: dict[str, SettingsPageDescriptor] = {}
        self._page_shells: dict[str, SettingsPageShell] = {}
        self._stale_page_ids: set[str] = set()
        self._route_active = False
        self._active_page_id: str | None = None
        self._search_shell: SettingsPageShell | None = None
        self._search_active = False
        self._search_query = ""
        self._transition_offset = 0
        self._transition_animation = QPropertyAnimation(self, b"transitionOffset", self)
        self._fade_animation: QPropertyAnimation | None = None
        self._stack = QStackedWidget(self)
        self._stack.setObjectName("SettingsWorkspacePageStack")
        self._stack.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._stack.setStyleSheet("background-color: transparent; border: none;")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent; border: none;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._stack)

    def set_pages(self, pages: Sequence[SettingsPageDescriptor]) -> None:
        """Attach page descriptors in render order."""

        self._clear_pages()
        self._page_order = [page.page_id for page in pages]
        self._page_descriptors = {page.page_id: page for page in pages}
        self._stale_page_ids = set(self._page_order)
        if self._page_order:
            self.select_page(self._page_order[0], animated=False, refresh=False)

    def page_ids(self) -> tuple[str, ...]:
        """Return registered page ids in navigation order."""

        return tuple(self._page_order)

    def active_page_id(self) -> str | None:
        """Return the active page id."""

        return self._active_page_id

    def is_search_active(self) -> bool:
        """Return whether the synthetic Settings search page is visible."""

        return self._search_active

    def search_query(self) -> str:
        """Return the current Settings search query."""

        return self._search_query

    def set_search_query(self, query: str) -> None:
        """Set the Settings search query and notify search coordinators."""

        if query == self._search_query:
            return
        self._search_query = query
        self.searchQueryChanged.emit(query)

    def page_shell(self, page_id: str) -> SettingsPageShell | None:
        """Return the constructed shell for one registered page id."""

        return self._page_shells.get(page_id)

    def constructed_page_ids(self) -> tuple[str, ...]:
        """Return page ids whose widgets have been constructed."""

        return tuple(
            page_id for page_id in self._page_order if page_id in self._page_shells
        )

    def show_search_page(self, widget: QWidget, *, animated: bool = False) -> None:
        """Show a synthetic search results page without changing normal page state."""

        previous_shell = self._search_shell
        if previous_shell is not None:
            self._stack.removeWidget(previous_shell)
            previous_shell.setParent(None)
            previous_shell.deleteLater()
        shell = SettingsPageShell(
            title=app_text("Search settings"), widget=widget, parent=self
        )
        self._search_shell = shell
        self._search_active = True
        self._stack.addWidget(shell)
        self._stack.setCurrentWidget(shell)
        self._sync_page_enabled_state()
        self._run_page_transition(shell, direction=1, animated=animated)
        shell.schedule_metrics_refresh()

    def clear_search_page(self, *, animated: bool = False) -> None:
        """Restore the previous normal Settings page after search clears."""

        shell = self._search_shell
        self._search_shell = None
        self._search_active = False
        active_shell = self._page_shells.get(self._active_page_id or "")
        if active_shell is not None:
            self._stack.setCurrentWidget(active_shell)
            self._run_page_transition(active_shell, direction=-1, animated=animated)
            active_shell.schedule_metrics_refresh()
        self._sync_page_enabled_state()
        if shell is not None:
            self._stack.removeWidget(shell)
            shell.setParent(None)
            shell.deleteLater()

    def reveal_setting(
        self,
        page_id: str,
        setting_id: str,
        *,
        animated: bool = False,
    ) -> None:
        """Reveal the page that owns one catalog setting result."""

        self.set_search_query("")
        self.clear_search_page(animated=False)
        self.select_page(page_id, animated=animated)
        shell = self._page_shells.get(page_id)
        if shell is None:
            return
        revealer = getattr(shell.content_widget(), "reveal_setting", None)
        if callable(revealer):
            revealer(setting_id)

    def refresh(self) -> None:
        """Refresh only the active Settings page exposed in the route."""

        self.refresh_active_page()

    def refresh_active_page(self) -> None:
        """Refresh the active Settings page using its native lifecycle hook."""

        page_id = self._active_page_id
        shell = self._page_shells.get(page_id or "")
        if shell is None or page_id is None:
            return
        self._refresh_page_widget(shell.content_widget())
        self._stale_page_ids.discard(page_id)
        shell.schedule_metrics_refresh()

    def mark_page_stale(self, page_id: str) -> None:
        """Mark one page so the next activation refreshes its content."""

        if page_id in self._page_descriptors:
            self._stale_page_ids.add(page_id)

    def set_route_active(self, active: bool) -> None:
        """Tell embedded pages whether the Settings route is currently visible."""

        self._route_active = active
        for page_id, shell in self._page_shells.items():
            setter = getattr(shell.content_widget(), "set_settings_page_active", None)
            if callable(setter):
                setter(active and page_id == self._active_page_id)

    def select_page(
        self,
        page_id: str,
        *,
        animated: bool = True,
        refresh: bool = True,
    ) -> None:
        """Switch to one active Settings page."""

        shell = self._ensure_page_shell(page_id)
        if shell is None:
            return
        if page_id == self._active_page_id:
            if refresh and self._should_refresh_selected_page():
                self.refresh_active_page()
            return
        previous_page_id = self._active_page_id
        previous_index = (
            self._page_order.index(self._active_page_id)
            if self._active_page_id in self._page_order
            else -1
        )
        next_index = self._page_order.index(page_id)
        self._active_page_id = page_id
        self._stack.setCurrentWidget(shell)
        self._sync_page_enabled_state()
        if previous_page_id is not None:
            previous_shell = self._page_shells.get(previous_page_id)
            if previous_shell is not None:
                setter = getattr(
                    previous_shell.content_widget(),
                    "set_settings_page_active",
                    None,
                )
                if callable(setter):
                    setter(False)
        setter = getattr(shell.content_widget(), "set_settings_page_active", None)
        if callable(setter):
            setter(self._route_active)
        self._run_page_transition(
            shell,
            direction=1 if next_index >= previous_index else -1,
            animated=animated,
        )
        self.currentPageChanged.emit(page_id)
        if refresh and self._should_refresh_selected_page():
            self.refresh_active_page()

    def transition_offset(self) -> int:
        """Return the current test-visible transition offset."""

        return self._transition_offset

    def setTransitionOffset(self, offset: int) -> None:
        """Set the current transition offset and move the active shell."""

        self._transition_offset = offset
        shell = (
            self._search_shell
            if self._search_active
            else self._page_shells.get(self._active_page_id or "")
        )
        if shell is not None:
            shell.move(offset, shell.y())

    transitionOffset = Property(int, transition_offset, setTransitionOffset)

    @staticmethod
    def _refresh_page_widget(widget: QWidget) -> None:
        """Refresh one embedded page using its native lifecycle hook."""

        for method_name in ("reload", "refresh"):
            method = getattr(widget, method_name, None)
            if callable(method):
                method()
                return

    def _ensure_page_shell(self, page_id: str) -> SettingsPageShell | None:
        """Construct and attach the shell for one registered page when needed."""

        shell = self._page_shells.get(page_id)
        if shell is not None:
            return shell
        descriptor = self._page_descriptors.get(page_id)
        if descriptor is None:
            return None
        widget = descriptor.create_page_widget(self)
        shell = SettingsPageShell(title=descriptor.title, widget=widget, parent=self)
        self._page_shells[page_id] = shell
        self._stack.addWidget(shell)
        shell.setEnabled(not self._search_active and page_id == self._active_page_id)
        return shell

    def _run_page_transition(
        self,
        shell: SettingsPageShell,
        *,
        direction: int,
        animated: bool,
    ) -> None:
        """Configure the page slide/fade transition for the selected shell."""

        self._transition_animation.stop()
        if self._fade_animation is not None:
            self._fade_animation.stop()
        start_offset = SETTINGS_PAGE_TRANSITION_OFFSET * direction
        if not animated:
            self.setTransitionOffset(0)
            shell.setGraphicsEffect(cast(QGraphicsEffect, None))
            self._transition_animation.setDuration(0)
            return
        effect = QGraphicsOpacityEffect(shell)
        effect.setOpacity(0.0)
        shell.setGraphicsEffect(effect)
        resolved_duration = restart_property_animation(
            self._transition_animation,
            start_value=start_offset,
            end_value=0,
            duration_ms=SETTINGS_PAGE_TRANSITION_DURATION_MS,
            easing_curve=TRANSFORM_EASING_CURVE,
        )
        fade_animation = QPropertyAnimation(effect, b"opacity", self)
        self._fade_animation = fade_animation
        fade_animation.setStartValue(0.0)
        fade_animation.setEndValue(1.0)
        fade_animation.setDuration(resolved_duration)
        fade_animation.setEasingCurve(TRANSFORM_EASING_CURVE)

        def clear_effect() -> None:
            """Remove transition-only graphics effects after fade-in completes."""

            if self._fade_animation is fade_animation:
                self._fade_animation = None
            if shell.graphicsEffect() is effect:
                shell.setGraphicsEffect(cast(QGraphicsEffect, None))

        fade_animation.finished.connect(clear_effect)
        fade_animation.start()

    def _sync_page_enabled_state(self) -> None:
        """Ensure only the active stacked page is interactive."""

        for page_id, shell in self._page_shells.items():
            shell.setEnabled(
                not self._search_active and page_id == self._active_page_id
            )
        if self._search_shell is not None:
            self._search_shell.setEnabled(self._search_active)

    def _should_refresh_selected_page(self) -> bool:
        """Return whether selected Settings content should refresh now."""

        return self._route_active or self.isVisible()

    def _clear_pages(self) -> None:
        """Remove all registered page shells from the stack."""

        if self._search_shell is not None:
            self._stack.removeWidget(self._search_shell)
            self._search_shell.setParent(None)
            self._search_shell.deleteLater()
            self._search_shell = None
            self._search_active = False
        for shell in self._page_shells.values():
            self._stack.removeWidget(shell)
            shell.setParent(None)
            shell.deleteLater()
        self._page_shells.clear()
        self._page_descriptors.clear()
        self._page_order.clear()
        self._stale_page_ids.clear()
        self._active_page_id = None
        self._search_shell = None
        self._search_active = False


__all__ = [
    "SETTINGS_CONTENT_MAX_WIDTH",
    "SettingsPageDescriptor",
    "SettingsPageWidgetFactory",
    "SettingsWorkspacePanel",
]
