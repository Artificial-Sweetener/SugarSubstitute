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

"""Write preset values through supported live editor widget APIs."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from qfluentwidgets import CheckBox, LineEdit  # type: ignore[import-untyped]

from substitute.presentation.editor.panel.prompt_field_state_controller import (
    set_prompt_editor_source_text,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.widgets import ComboBox, DoubleSpinBox, SeedBox, SpinBox
from substitute.presentation.widgets.model_picker import ModelPickerField


@runtime_checkable
class _ValueWritable(Protocol):
    """Describe lightweight widgets that accept an object value."""

    def setValue(self, value: object) -> None:  # noqa: N802
        """Set the current widget value."""


def write_live_widget_value(widget: object, value: object) -> bool:
    """Write a value to one supported live field widget."""

    target = getattr(widget, "spinbox", widget)
    if isinstance(target, DoubleSpinBox):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        target.setValue(float(value))
        return True
    if isinstance(target, (SeedBox, SpinBox)):
        if not isinstance(value, int) or isinstance(value, bool):
            return False
        target.setValue(value)
        return True
    if isinstance(target, _ValueWritable):
        target.setValue(value)
        return True
    if isinstance(target, (ComboBox, ModelPickerField)):
        target.setCurrentText(str(value))
        return True
    if isinstance(target, LineEdit):
        target.setText(str(value))
        return True
    if isinstance(target, CheckBox):
        target.setChecked(bool(value))
        return True
    if isinstance(target, PromptEditor):
        set_prompt_editor_source_text(target, str(value))
        return True
    if target.__class__.__name__ == "SwitchButton":
        set_checked = getattr(target, "setChecked", None)
        if callable(set_checked):
            set_checked(bool(value))
            return True
    return False


__all__ = ["write_live_widget_value"]
