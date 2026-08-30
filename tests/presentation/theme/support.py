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

"""Own QFluent theme state, observable switching, and native test lifetime."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TypeVar

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    Theme,
    setTheme,
    setThemeColor,
)
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    isDarkTheme,
    styleSheetManager,
    themeColor,
)

from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application
from tests.support.qt.semantic_wait import wait_for_qt_condition


_WidgetT = TypeVar("_WidgetT", bound=QWidget)


class ThemeWidgetOwner:
    """Own theme state and every independent widget root created by one test."""

    def __init__(self, _application: QApplication) -> None:
        """Require the worker application and initialize root ownership."""

        self._roots: list[QWidget] = []

    def own(self, widget: _WidgetT) -> _WidgetT:
        """Retain one independently constructed widget root."""

        self._roots.append(widget)
        return widget

    def wait_until(
        self,
        predicate: Callable[[], bool],
        *,
        timeout_ms: int = 3000,
    ) -> None:
        """Wait only until the requested observable state is reached."""

        wait_for_qt_condition(predicate, timeout_ms=timeout_ms)

    def switch_theme(
        self,
        theme: Theme,
        *,
        settled: Callable[[], bool] | None = None,
    ) -> None:
        """Switch QFluent theme and wait for its observable state."""

        setTheme(theme)
        self.wait_until(
            lambda: _theme_is_active(theme) and (settled is None or settled())
        )

    @contextmanager
    def using_theme(self, theme: Theme) -> Iterator[None]:
        """Apply one theme and restore the prior theme after exact cleanup."""

        previous_theme = Theme.DARK if isDarkTheme() else Theme.LIGHT
        self.switch_theme(theme)
        try:
            yield
        finally:
            self.destroy_all()
            self.switch_theme(previous_theme)

    def destroy_all(self) -> None:
        """Destroy every independent widget root synchronously."""

        for widget in reversed(self._roots):
            destroy_qt_object(widget)
        self._roots.clear()


@contextmanager
def fluent_theme(
    theme: Theme,
    *,
    accent_color: QColor | None = None,
) -> Iterator[None]:
    """Temporarily own QFluent theme and optional accent state for one test."""

    ensure_qt_application()
    previous_theme = Theme.DARK if isDarkTheme() else Theme.LIGHT
    previous_accent = QColor(themeColor())
    setTheme(theme)
    if accent_color is not None:
        setThemeColor(accent_color)
    _wait_for_theme(theme)
    try:
        yield
    finally:
        setTheme(previous_theme)
        setThemeColor(previous_accent)
        _wait_for_theme(previous_theme)


def is_qfluent_managed(widget: QWidget) -> bool:
    """Return whether QFluent's stylesheet manager owns the widget."""

    return widget in styleSheetManager.widgets


def _wait_for_theme(theme: Theme) -> None:
    """Wait until QFluent publishes the requested theme."""

    wait_for_qt_condition(lambda: _theme_is_active(theme))


def _theme_is_active(theme: Theme) -> bool:
    """Return whether QFluent exposes the requested concrete theme."""

    if theme is Theme.DARK:
        return bool(isDarkTheme())
    if theme is Theme.LIGHT:
        return not bool(isDarkTheme())
    return True


__all__ = [
    "ThemeWidgetOwner",
    "fluent_theme",
    "is_qfluent_managed",
]
