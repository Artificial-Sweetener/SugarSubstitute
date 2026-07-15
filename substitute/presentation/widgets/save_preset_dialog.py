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

"""Dialog for naming and scoping saved user presets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QDialog, QSizePolicy, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CaptionLabel,
    ComboBox,
    LineEdit,
    MessageBoxBase,
)

from substitute.application.user_presets import UserPresetAssociation

_SCOPE_TEXT_WIDTH = 300
_DIALOG_WIDTH = 360


@dataclass(frozen=True, slots=True)
class PresetSaveScope:
    """Expose one scope choice for preset save dialogs."""

    title: str
    full_label: str
    association: UserPresetAssociation


class SavePresetDialog(MessageBoxBase):  # type: ignore[misc]
    """Collect a saved preset name and target scope."""

    def __init__(
        self,
        *,
        parent: QWidget,
        title: str,
        scopes: tuple[PresetSaveScope, ...],
        name_label: str = "Name",
        scope_label: str = "Save under",
    ) -> None:
        """Create a preset save dialog with caller-supplied copy."""

        super().__init__(parent)
        self._scopes = scopes
        self.widget.setMinimumWidth(_DIALOG_WIDTH)
        self.yesButton.setText("Save")
        self.cancelButton.setText("Cancel")

        self._title = BodyLabel(title, self.widget)
        self._name_label = CaptionLabel(name_label, self.widget)
        self._name_edit = LineEdit(self.widget)
        self._scope_label = CaptionLabel(scope_label, self.widget)
        self._scope_combo = ComboBox(self.widget)
        self._scope_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._scope_combo.currentIndexChanged.connect(self._update_scope_tooltip)
        self._name_edit.textChanged.connect(self._update_save_enabled)

        self.viewLayout.addWidget(self._title)
        self.viewLayout.addWidget(self._name_label)
        self.viewLayout.addWidget(self._name_edit)
        self.viewLayout.addWidget(self._scope_label)
        self.viewLayout.addWidget(self._scope_combo)

        for scope in self._scopes:
            self._scope_combo.addItem(
                _elided_scope_label(
                    scope.full_label,
                    QFontMetrics(self._scope_combo.font()),
                    _SCOPE_TEXT_WIDTH,
                ),
                userData=scope,
            )
        self._update_scope_tooltip()
        self._update_save_enabled()

    @property
    def name_edit(self) -> LineEdit:
        """Return the name editor for focused tests."""

        return self._name_edit

    @property
    def scope_combo(self) -> ComboBox:
        """Return the scope combo for focused tests."""

        return self._scope_combo

    @property
    def scope_label(self) -> CaptionLabel:
        """Return the scope label for focused tests."""

        return self._scope_label

    def preset_name(self) -> str:
        """Return the validated preset name."""

        return cast(str, self._name_edit.text()).strip()

    def selected_scope(self) -> PresetSaveScope:
        """Return the selected save scope."""

        data = self._scope_combo.currentData()
        if not isinstance(data, PresetSaveScope):
            raise RuntimeError("Save preset dialog has no selected scope")
        return data

    def validate(self) -> bool:
        """Return whether the current form data can be saved."""

        return bool(self.preset_name()) and self._scope_combo.currentData() is not None

    def _update_save_enabled(self) -> None:
        """Keep the save button disabled until the dialog has a name and scope."""

        self.yesButton.setEnabled(self.validate())

    def _update_scope_tooltip(self) -> None:
        """Expose the full current scope label without widening the combo."""

        data = self._scope_combo.currentData()
        if isinstance(data, PresetSaveScope):
            self._scope_combo.setToolTip(data.full_label)
        else:
            self._scope_combo.setToolTip("")


def preset_dialog_result(
    dialog: SavePresetDialog,
) -> tuple[str, PresetSaveScope] | None:
    """Return dialog form data when accepted, otherwise ``None``."""

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.preset_name(), dialog.selected_scope()


def _elided_scope_label(
    label: str,
    metrics: QFontMetrics,
    width: int,
) -> str:
    """Return a bounded combo label for potentially unreliable model names."""

    return metrics.elidedText(label, Qt.TextElideMode.ElideRight, width)


__all__ = [
    "PresetSaveScope",
    "SavePresetDialog",
    "_elided_scope_label",
    "preset_dialog_result",
]
