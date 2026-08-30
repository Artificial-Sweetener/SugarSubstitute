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

"""Tests for shared preset save dialog scope handling."""

from __future__ import annotations

from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QWidget

from substitute.domain.user_presets import GLOBAL_PRESET_ASSOCIATION
from substitute.presentation.widgets.save_preset_dialog import (
    PresetSaveScope,
    SavePresetDialog,
    _elided_scope_label,
)
from tests.support.qt.lifecycle import (
    activate_widget_layouts,
    destroy_qt_object,
    ensure_qt_application,
)


def test_save_preset_dialog_elides_scope_text_but_stores_scope() -> None:
    """The compact combo should not be the source of association truth."""

    ensure_qt_application()
    parent = QWidget()
    scope = PresetSaveScope(
        title="Checkpoint",
        full_label=(
            "Checkpoint: Extremely Long Provider Name With Wrong Version "
            "Details That Should Not Make The Combo Huge"
        ),
        association=GLOBAL_PRESET_ASSOCIATION,
    )

    dialog = SavePresetDialog(parent=parent, title="Save segment", scopes=(scope,))

    assert dialog.scope_combo.currentData() == scope
    assert dialog.scope_combo.toolTip() == scope.full_label
    assert dialog.scope_combo.currentText() != scope.full_label
    destroy_qt_object(dialog)
    destroy_qt_object(parent)


def test_save_preset_dialog_uses_full_width_scope_combo() -> None:
    """The scope combo should fill the same available form width as the name input."""

    ensure_qt_application()
    parent = QWidget()
    dialog = SavePresetDialog(
        parent=parent,
        title="Save segment",
        scopes=(
            PresetSaveScope(
                title="Global",
                full_label="Global",
                association=GLOBAL_PRESET_ASSOCIATION,
            ),
        ),
    )
    activate_widget_layouts(parent, dialog)

    assert dialog.scope_combo.width() == dialog.name_edit.width()
    destroy_qt_object(dialog)
    destroy_qt_object(parent)


def test_save_preset_dialog_scope_label_uses_save_under_copy() -> None:
    """The scope label should use the product copy chosen for save organization."""

    ensure_qt_application()
    parent = QWidget()
    dialog = SavePresetDialog(
        parent=parent,
        title="Save segment",
        scopes=(
            PresetSaveScope(
                title="Global",
                full_label="Global",
                association=GLOBAL_PRESET_ASSOCIATION,
            ),
        ),
    )

    assert dialog.scope_label.text() == "Save under"
    destroy_qt_object(dialog)
    destroy_qt_object(parent)


def test_save_preset_dialog_requires_name() -> None:
    """The save button should require a non-blank segment name."""

    ensure_qt_application()
    parent = QWidget()
    dialog = SavePresetDialog(
        parent=parent,
        title="Save segment",
        scopes=(
            PresetSaveScope(
                title="Global",
                full_label="Global",
                association=GLOBAL_PRESET_ASSOCIATION,
            ),
        ),
    )

    assert not dialog.yesButton.isEnabled()
    dialog.name_edit.setText("Blue eyes")

    assert dialog.yesButton.isEnabled()
    assert dialog.preset_name() == "Blue eyes"
    destroy_qt_object(dialog)
    destroy_qt_object(parent)


def test_save_preset_dialog_accepts_node_preset_title() -> None:
    """The shared dialog should allow node preset save copy."""

    ensure_qt_application()
    parent = QWidget()
    dialog = SavePresetDialog(
        parent=parent,
        title="Save node preset",
        scopes=(
            PresetSaveScope(
                title="Global",
                full_label="Global",
                association=GLOBAL_PRESET_ASSOCIATION,
            ),
        ),
    )

    assert dialog.scope_label.text() == "Save under"
    destroy_qt_object(dialog)
    destroy_qt_object(parent)


def test_elided_scope_label_respects_width_budget() -> None:
    """Scope label elision should keep long unreliable model names compact."""

    app = ensure_qt_application()
    metrics = QFontMetrics(app.font())

    label = _elided_scope_label(
        "Checkpoint: Extremely Long Provider Name With Version Details",
        metrics,
        120,
    )

    assert metrics.horizontalAdvance(label) <= 121
