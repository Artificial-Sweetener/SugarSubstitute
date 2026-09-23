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

"""Verify the contained chronology keeps current and next versions in view."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.model_discovery.discovery_overlay import (
    ModelDiscoveryOverlay,
)
from substitute.presentation.model_updates.version_family_modal import (
    ModelVersionFamilyModal,
)
from tests.presentation.model_updates.support import update_proposal
from tests.presentation.widgets.model_picker.support import ensure_qapp


def test_long_family_initially_shows_installed_and_newer_version() -> None:
    """Opening a long history must not strand the available update offscreen."""

    app = ensure_qapp()
    parent = QWidget()
    parent.resize(1280, 820)
    parent.show()
    proposal = update_proposal("a" * 64)
    current_id = proposal.current.version_id
    assert current_id is not None
    versions = tuple(
        replace(
            proposal.candidate,
            version_id=index,
            version_name=f"v{index}",
            sha256=f"{index:064x}",
        )
        for index in range(1, 9)
    )
    proposal = replace(
        proposal,
        current=replace(proposal.current, version_id=7),
        candidate=versions[-1],
    )
    overlay = ModelDiscoveryOverlay(owner=parent)
    modal = ModelVersionFamilyModal(
        proposal=proposal, open_url=lambda _url: True, parent=overlay
    )
    overlay.attach(modal)
    overlay.present()
    modal.show_loading()
    modal.show_family(
        versions,
        installed_hashes=frozenset({versions[5].sha256, versions[6].sha256}),
    )
    app.processEvents()
    app.processEvents()

    scroll = modal.timeline.horizontalScrollBar().value()
    viewport_width = modal.timeline.viewport().width()
    installed = modal._cards[7]
    newer = modal._cards[8]
    assert scroll > 0
    assert 0 <= installed.x() - scroll < viewport_width
    assert 0 < newer.x() - scroll
    assert newer.x() + newer.width() - scroll <= viewport_width
    assert not modal.download_button.isEnabled()
    assert modal._cards[7].state_label.text() == "In use"
    assert modal._cards[6].state_label.text() == "On disk"
    assert not modal._cards[6].portrait.checkbox.isVisible()
    assert modal._cards[8].portrait.checkbox.isVisible()
    assert not modal.isWindow()
    assert overlay.geometry() == parent.rect()

    initial_positions = (
        modal.family_label.y(),
        modal.timeline.y(),
        modal.provider_button.y(),
    )
    modal._cards[8].portrait.checkbox.setChecked(True)
    modal.set_downloading()
    app.processEvents()
    assert (
        modal.family_label.y(),
        modal.timeline.y(),
        modal.provider_button.y(),
    ) == initial_positions
    modal.finish_download()
    app.processEvents()
    assert modal._cards[8].state_label.text() == "On disk"
    assert not modal._cards[8].portrait.checkbox.isVisible()
    QTest.mouseClick(modal._cards[8].portrait, Qt.MouseButton.LeftButton)
    assert not modal.download_button.isEnabled()
    assert modal.selected_version is None
    assert (
        modal.family_label.y(),
        modal.timeline.y(),
        modal.provider_button.y(),
    ) == initial_positions
    assert modal.timeline.geometry().bottom() + 8 <= modal.provider_button.y()

    modal.reject()
    overlay.close()
    parent.close()
    parent.deleteLater()
    QApplication.processEvents()
