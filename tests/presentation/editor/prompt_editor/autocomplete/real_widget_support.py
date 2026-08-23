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

"""Own deterministic real-Qt lifecycle support for autocomplete surface tests."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

import pytest
from PySide6.QtWidgets import QApplication, QWidget
from tests.support.qt.lifecycle import destroy_widget_roots


def ensure_qapp() -> QApplication:
    """Return a running Qt application for autocomplete widget tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def process_events(app: QApplication) -> None:
    """Dispatch event-loop work explicitly requested by a mounted interaction."""

    app.processEvents()


@pytest.fixture(name="widgets")
def widgets() -> Iterator[list[QWidget]]:
    """Track and dispose widgets created during one autocomplete widget test."""

    created: list[QWidget] = []
    yield created
    destroy_widget_roots(created)
