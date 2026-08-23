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

"""Own wildcard management modal lifetime for each test."""

from __future__ import annotations

from collections.abc import Iterator

from PySide6.QtWidgets import QWidget
from pytest import MonkeyPatch, fixture
from shiboken6 import isValid

from substitute.presentation.managed_text_assets import (
    WildcardManagementModal,
    WildcardManagementOpener,
)
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


@fixture(autouse=True)
def owned_wildcard_modal_lifetime(monkeypatch: MonkeyPatch) -> Iterator[None]:
    """Destroy every modal's top-level owner synchronously after its test."""

    application = ensure_qt_application()
    roots: list[QWidget] = []
    create_modal = WildcardManagementOpener.create_modal

    def create_owned_modal(
        opener: WildcardManagementOpener,
        parent: QWidget | None,
    ) -> WildcardManagementModal:
        """Create one modal and retain its top-level native owner."""

        modal = create_modal(opener, parent)
        root = parent.window() if parent is not None else modal.parentWidget()
        roots.append(root if root is not None else modal)
        return modal

    monkeypatch.setattr(WildcardManagementOpener, "create_modal", create_owned_modal)
    yield

    destroyed: set[int] = set()
    for root in reversed(roots):
        identity = id(root)
        if identity in destroyed or not isValid(root):
            continue
        destroyed.add(identity)
        root.close()
        destroy_qt_object(root)
    assert application is ensure_qt_application()
