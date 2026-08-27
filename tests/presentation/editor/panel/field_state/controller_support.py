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

"""Provide deterministic editor-panel field controller doubles."""

from __future__ import annotations

from typing import Any, Callable, cast


class _PromptEditorDouble:
    """Prompt-editor double that records source replacement calls."""

    def __init__(self, metadata: dict[str, str], text: str) -> None:
        """Initialize metadata and visible source text."""

        self._metadata = metadata
        self._text = text
        self.baseline_replacements: list[str] = []
        self.plain_text_replacements: list[str] = []

    def property(self, name: str) -> object:
        """Return one dynamic property."""

        if name == "input_metadata":
            return self._metadata
        return None

    def toPlainText(self) -> str:
        """Return the current visible source text."""

        return self._text

    def replaceBaselineSourceText(self, text: str) -> None:
        """Record a baseline-safe source replacement."""

        self.baseline_replacements.append(text)
        self._text = text

    def setPlainText(self, text: str) -> None:
        """Record fallback plain-text replacement."""

        self.plain_text_replacements.append(text)
        self._text = text


class _CubeWidgetDouble:
    """Cube widget double that returns scripted prompt-editor children."""

    def __init__(self, prompt_editors: list[_PromptEditorDouble]) -> None:
        """Store child prompt editors."""

        self._prompt_editors = prompt_editors

    def findChildren(self, cls: type[object]) -> list[_PromptEditorDouble]:
        """Return prompt editors only for the requested class."""

        if cls is _PromptEditorDouble:
            return self._prompt_editors
        return []


class _Widget:
    """Widget double with mutable visibility."""

    def __init__(
        self,
        *,
        properties: dict[str, object] | None = None,
        parent: object | None = None,
    ) -> None:
        """Initialize visible state."""

        self.visible = True
        self._properties = dict(properties or {})
        self._parent = parent

    def setVisible(self, visible: bool) -> None:
        """Record visibility."""

        self.visible = visible

    def isVisible(self) -> bool:
        """Return current visibility."""

        return self.visible

    def property(self, name: str) -> object:
        """Return one Qt-style property."""

        return self._properties.get(name)

    def parentWidget(self) -> object | None:
        """Return the assigned parent widget."""

        return self._parent


class _SignalDouble:
    """Minimal signal double for field-state binding tests."""

    def __init__(self) -> None:
        """Initialize connected callbacks."""

        self._callbacks: list[Callable[..., object]] = []

    def connect(self, callback: Callable[..., object]) -> None:
        """Store one callback."""

        self._callbacks.append(callback)

    def emit(self, *args: object) -> None:
        """Invoke stored callbacks."""

        for callback in list(self._callbacks):
            callback(*args)


class _SeedBoxDouble:
    """SeedBox test double with value and mode signals."""

    def __init__(self, metadata: dict[str, object]) -> None:
        """Initialize seed value, mode, and metadata."""

        self._metadata = metadata
        self._value = 0
        self._mode = "random"
        self.valueChanged = _SignalDouble()
        self.modeChanged = _SignalDouble()

    def property(self, name: str) -> object:
        """Return one Qt-style property."""

        if name == "input_metadata":
            return self._metadata
        return None

    def value(self) -> int:
        """Return current seed value."""

        return self._value

    def setValue(self, value: object) -> None:  # noqa: N802
        """Set current seed value and emit when changed."""

        next_value = int(cast(Any, value))
        if self._value == next_value:
            return
        self._value = next_value
        self.valueChanged.emit(next_value)

    def mode(self) -> str:
        """Return current seed mode."""

        return self._mode

    def setMode(self, mode: str) -> None:  # noqa: N802
        """Set current seed mode and emit when changed."""

        if self._mode == mode:
            return
        self._mode = mode
        self.modeChanged.emit(mode)


class _LineEditDouble:
    """Line-edit test double with separate text and commit signals."""

    def __init__(self, metadata: dict[str, object], text: str = "") -> None:
        """Initialize text, metadata, and Qt-like signals."""

        self._metadata = metadata
        self._text = text
        self.textChanged = _SignalDouble()
        self.editingFinished = _SignalDouble()

    def property(self, name: str) -> object:
        """Return one Qt-style property."""

        if name == "input_metadata":
            return self._metadata
        return None

    def text(self) -> str:
        """Return the displayed text."""

        return self._text

    def setText(self, text: str) -> None:  # noqa: N802
        """Replace displayed text and emit the text-change signal."""

        self._text = text
        self.textChanged.emit(text)


class _CubeParent:
    """Cube-section parent double that records height refresh requests."""

    def __init__(self) -> None:
        """Initialize refresh counter."""

        self.height_refreshes = 0

    def defer_update_cube_height(self) -> None:
        """Record a deferred cube-height refresh."""

        self.height_refreshes += 1
