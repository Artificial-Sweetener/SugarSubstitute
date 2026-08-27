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

"""Provide lightweight field-state collaborators for controller contracts."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, cast

import substitute.presentation.editor.panel.field_state_controller as field_state_controller
from substitute.presentation.editor.panel.factories import widget_wiring

__all__ = (
    "ComboBoxBase",
    "ImagePickerBase",
    "MaskPickerBase",
    "ModelPickerFieldBase",
    "PromptEditorBase",
    "SeedBoxBase",
    "_ComboWidget",
    "_Signal",
    "_SignalMap",
    "_as_combo_box",
    "_as_image_picker",
    "_as_model_picker",
    "_as_prompt_editor",
    "_prepare_field_state_module",
    "field_state_controller",
    "widget_wiring",
)


class _Signal:
    """Record callbacks and invoke them in emission order."""

    def __init__(self) -> None:
        self._callbacks: list[Callable[..., object]] = []

    def connect(self, callback: Callable[..., object]) -> None:
        self._callbacks.append(callback)

    def __getitem__(self, _signature: object) -> _Signal:
        """Return the overloaded signal view used by Qt-style tests."""

        return self

    def emit(self, *args: object) -> None:
        for callback in self._callbacks:
            callback(*args)


class _SignalMap(dict[str, _Signal]):
    """Create named signals on first use."""

    def __init__(self, signal: _Signal | None = None) -> None:
        super().__init__()
        self._signal = signal or _Signal()

    def __getitem__(self, _signature: object) -> _Signal:
        return self._signal

    def __missing__(self, key: str) -> _Signal:
        signal = _Signal()
        self[key] = signal
        return signal


class PromptEditorBase:
    """Serve as the patched direct prompt-editor type."""


class ImagePickerBase:
    """Serve as the patched direct image-picker type."""


class MaskPickerBase:
    """Serve as the patched direct mask-picker type."""


class ModelPickerFieldBase:
    """Serve as the patched direct model-picker type."""


class SeedBoxBase:
    """Serve as the patched direct seed-box type."""


class ComboBoxBase:
    """Serve as the patched direct combo-box type."""


def _prepare_field_state_module(monkeypatch: Any) -> None:
    """Patch controller type dispatch to deterministic local base types."""

    for name, value in {
        "PromptEditor": PromptEditorBase,
        "ImagePicker": ImagePickerBase,
        "MaskPicker": MaskPickerBase,
        "ModelPickerField": ModelPickerFieldBase,
        "SeedBox": SeedBoxBase,
        "ComboBox": ComboBoxBase,
    }.items():
        monkeypatch.setattr(field_state_controller, name, value)
    monkeypatch.setattr(widget_wiring, "ImagePicker", ImagePickerBase)
    monkeypatch.setattr(widget_wiring, "MaskPicker", MaskPickerBase)


def _as_prompt_editor(value: object) -> Any:
    """Return a test prompt editor through the production type boundary."""

    return cast(Any, value)


def _as_image_picker(value: object) -> Any:
    """Return a test image picker through the production type boundary."""

    return cast(Any, value)


def _as_model_picker(value: object) -> Any:
    """Return a test model picker through the production type boundary."""

    return cast(Any, value)


def _as_combo_box(value: object) -> Any:
    """Return a test combo box through the production type boundary."""

    return cast(Any, value)


class _ComboWidget(ComboBoxBase):
    """Provide a minimal combo box with metadata and change signals."""

    def __init__(
        self,
        *,
        initial_text: str,
        metadata: Mapping[str, object],
        options: list[str] | None = None,
        strict_unknown_text: bool = False,
    ) -> None:
        self._text = initial_text
        self._metadata = dict(metadata)
        self._options = options or []
        self._strict_unknown_text = strict_unknown_text
        self.currentTextChanged = _SignalMap()

    def property(self, name: str) -> object | None:
        return self._metadata if name == "input_metadata" else None

    def currentText(self) -> str:  # noqa: N802
        return self._text

    def setCurrentText(self, value: str) -> None:  # noqa: N802
        if self._strict_unknown_text and value not in self._options:
            return
        self._text = value
        self.currentTextChanged[str].emit(value)
