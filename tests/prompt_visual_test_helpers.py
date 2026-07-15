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

"""Provide live QFluent reference helpers for prompt-editor visual parity tests."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    TextEdit as QFluentTextEdit,
    Theme,
    setTheme,
)
from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]

from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)
from tests.execution_test_helpers import immediate_prompt_task_executor_factory


class _VisualTextWidget(Protocol):
    """Describe the widget surface needed for prompt visual parity assertions."""

    def contentsMargins(self) -> Any: ...

    def cursorRect(self) -> Any: ...

    def document(self) -> Any: ...

    def font(self) -> Any: ...

    def fontMetrics(self) -> Any: ...

    def grab(self) -> Any: ...

    def height(self) -> int: ...

    def resize(self, width: int, height: int) -> None: ...

    def setDisabled(self, disabled: bool) -> None: ...

    def setFocus(self) -> None: ...

    def setPlainText(self, text: str) -> None: ...

    def setPlaceholderText(self, text: str) -> None: ...

    def setReadOnly(self, read_only: bool) -> None: ...

    def show(self) -> None: ...

    def verticalScrollBar(self) -> Any: ...


def ensure_qapp() -> QApplication:
    """Return a running Qt application for prompt-editor visual tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def process_events(app: QApplication, cycles: int = 5) -> None:
    """Flush several event-loop turns so widget visuals settle deterministically."""

    for _ in range(cycles):
        app.processEvents()


@contextmanager
def fluent_theme(theme: Theme) -> Iterator[None]:
    """Temporarily switch QFluent theme mode for one visual parity assertion."""

    previous_theme = Theme.DARK if isDarkTheme() else Theme.LIGHT
    setTheme(theme)
    try:
        yield
    finally:
        setTheme(previous_theme)


def create_prompt_editor() -> PromptEditor:
    """Instantiate one real prompt editor with deterministic test dependencies."""

    return PromptEditor(
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )


def create_reference_text_edit() -> QFluentTextEdit:
    """Instantiate one live QFluent `TextEdit` reference widget."""

    return QFluentTextEdit()


def show_text_widget(
    widget: _VisualTextWidget,
    *,
    width: int,
    text: str = "",
    placeholder: str = "",
    disabled: bool = False,
    focused: bool = False,
    read_only: bool = False,
    height: int | None = None,
) -> _VisualTextWidget:
    """Configure and show one text widget for visual parity assertions."""

    app = ensure_qapp()
    widget.setPlaceholderText(placeholder)
    widget.setReadOnly(read_only)
    widget.setDisabled(disabled)
    widget.resize(width, 120 if height is None else height)
    widget.setPlainText(text)
    widget.show()
    if focused:
        cast(QWidget, widget).activateWindow()
        cast(QWidget, widget).raise_()
        widget.setFocus()
    process_events(app)
    return widget


def widget_image(widget: _VisualTextWidget) -> QImage:
    """Grab one widget image in a deterministic ARGB32 format."""

    return (
        cast(QWidget, widget)
        .grab()
        .toImage()
        .convertToFormat(QImage.Format.Format_ARGB32)
    )


def pixel_rgba(image: QImage, x: int, y: int) -> tuple[int, int, int, int]:
    """Return one image pixel as an RGBA tuple for focused parity assertions."""

    color = image.pixelColor(x, y)
    return color.red(), color.green(), color.blue(), color.alpha()


def equalize_reference_height(
    reference: QFluentTextEdit,
    prompt_editor: PromptEditor,
    *,
    width: int,
) -> None:
    """Resize the QFluent reference to the live prompt-editor shell height."""

    app = ensure_qapp()
    reference.resize(width, prompt_editor.height())
    process_events(app)
