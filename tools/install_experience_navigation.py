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

"""Drive named controls and observable page transitions in installer checks."""

from __future__ import annotations

from collections.abc import Callable
import time
from typing import TypeVar, cast

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QApplication, QWidget

from substitute.presentation.onboarding import OnboardingWindow


_WIDGET_T = TypeVar("_WIDGET_T", bound=QWidget)


def installer_widget(
    window: OnboardingWindow,
    widget_type: type[_WIDGET_T],
    object_name: str,
) -> _WIDGET_T:
    """Return one required production widget by stable object name."""

    widget = window.findChild(widget_type, object_name)
    if widget is None:
        raise RuntimeError(f"Installer control is missing: {object_name}")
    return cast(_WIDGET_T, widget)


def click_installer_control(window: OnboardingWindow, object_name: str) -> None:
    """Activate one production installer control by stable object name."""

    widget = installer_widget(window, QWidget, object_name)
    if not widget.isEnabled():
        raise RuntimeError(f"Onboarding control is disabled: {object_name}")
    if isinstance(widget, QAbstractButton):
        widget.click()
    else:
        QTest.mouseClick(widget, Qt.MouseButton.LeftButton)
    QApplication.processEvents()


def wait_for_installer_page(window: OnboardingWindow, object_name: str) -> None:
    """Wait until one named production page becomes current."""

    def page_matches() -> bool:
        """Return whether the visible page has the expected stable identity."""

        current = window.page_stack.currentWidget()
        return current is not None and current.objectName() == object_name

    wait_for_installer_condition(
        page_matches,
        description=f"installer page {object_name}",
    )


def wait_for_installer_condition(
    condition: Callable[[], bool],
    *,
    description: str,
    timeout_seconds: float = 5.0,
) -> None:
    """Wait for an observable installer condition with a bounded timeout."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if condition():
            return
        QTest.qWait(10)
    raise TimeoutError(f"Timed out waiting for {description}.")


__all__ = [
    "click_installer_control",
    "installer_widget",
    "wait_for_installer_condition",
    "wait_for_installer_page",
]
