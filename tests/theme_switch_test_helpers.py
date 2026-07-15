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

"""Provide shared QFluent theme-switch helpers for widget contract tests."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TypeVar

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import Theme, setTheme  # type: ignore[import-untyped]
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    isDarkTheme,
    styleSheetManager,
)

_T = TypeVar("_T")


def ensure_qapp() -> QApplication:
    """Return the running Qt application, creating one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def process_events(cycles: int = 5) -> None:
    """Flush several event-loop turns so QFluent style updates settle."""

    app = ensure_qapp()
    for _ in range(cycles):
        app.processEvents()


@contextmanager
def fluent_theme(theme: Theme) -> Iterator[None]:
    """Temporarily set one QFluent theme for a widget test."""

    previous_theme = Theme.DARK if isDarkTheme() else Theme.LIGHT
    setTheme(theme)
    process_events()
    try:
        yield
    finally:
        setTheme(previous_theme)
        process_events()


def after_dark_to_light(factory: Callable[[], _T]) -> tuple[_T, _T]:
    """Create one subject in dark theme, then return it after switching to light."""

    ensure_qapp()
    setTheme(Theme.DARK)
    process_events()
    subject = factory()
    if isinstance(subject, QWidget):
        subject.show()
    process_events()
    dark_subject = subject
    setTheme(Theme.LIGHT)
    process_events()
    return dark_subject, subject


def is_qfluent_managed(widget: QWidget) -> bool:
    """Return whether QFluent's stylesheet manager owns the widget stylesheet."""

    return widget in styleSheetManager.widgets


def dispose_widgets(*widgets: object) -> None:
    """Close and delete Qt widgets created by theme-switch tests."""

    for widget in widgets:
        if not isinstance(widget, QWidget):
            continue
        widget.close()
        widget.deleteLater()
    process_events()
