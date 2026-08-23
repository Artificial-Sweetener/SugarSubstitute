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

"""Own the Qt application and every top-level widget created by window tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from substitute.presentation.onboarding.onboarding_window import OnboardingWindow
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


@pytest.fixture(scope="package", autouse=True)
def qt_application_owner() -> Iterator[QApplication]:
    """Keep one QApplication alive for this process-local capability package."""

    yield ensure_qt_application()


@pytest.fixture(autouse=True)
def top_level_widget_owner(
    qt_application_owner: QApplication,
) -> Iterator[None]:
    """Destroy exactly the top-level widgets created by each test."""

    existing_widget_ids = {
        id(widget) for widget in qt_application_owner.topLevelWidgets()
    }
    yield
    created_widgets = [
        widget
        for widget in qt_application_owner.topLevelWidgets()
        if id(widget) not in existing_widget_ids
    ]
    for widget in reversed(created_widgets):
        if not isValid(widget):
            continue
        if isinstance(widget, OnboardingWindow):
            widget._emit_close_requested_on_close = False
        widget.close()
        destroy_qt_object(widget)


__all__ = ["qt_application_owner", "top_level_widget_owner"]
