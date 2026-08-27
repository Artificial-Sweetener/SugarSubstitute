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

"""Own worker-local Qt lifetime for app-orb tests."""

from __future__ import annotations

from collections.abc import Iterator

from PySide6.QtWidgets import QApplication
import pytest

from tests.support.qt.lifecycle import ensure_qt_application


@pytest.fixture(scope="module", autouse=True)
def app_orb_qt_application() -> Iterator[QApplication]:
    """Keep the worker's Qt application alive for each app-orb test module."""

    application = ensure_qt_application()
    yield application
