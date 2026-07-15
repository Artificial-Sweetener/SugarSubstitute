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

"""Assertions for editor-owned Qt widget lifecycle invariants."""

from __future__ import annotations

from typing import cast

from PySide6.QtWidgets import QApplication, QWidget

APPROVED_TOP_LEVEL_CLASS_NAMES = frozenset(
    {
        "CustomWindow",
        "MainWindow",
        "SearchableComboPopup",
        "RoundMenu",
        "CheckableMenu",
        "ToolTip",
        "TeachingTip",
        "_PromptEditorTextEditMenu",
    }
)

BLOCKED_TOP_LEVEL_SIGNALS = (
    "_NodeCardSurface",
    "NodeCard",
    "AccordionContentClip",
    "NodeCardContentClip",
    "_NodeCardContentSurface",
    "NodeCardContentSurface",
    "CubeSectionView",
    "CubePanel-",
    "EditorPanel",
    "EditorScroll",
)


def assert_no_editor_widgets_are_top_level(
    *,
    ignored_widget_ids: frozenset[int] = frozenset(),
) -> None:
    """Assert editor-owned widgets are not registered as QApplication top-levels."""

    app = QApplication.instance()
    if app is None:
        return
    application = cast(QApplication, app)
    escaped_widgets = [
        _describe_top_level_widget(widget)
        for widget in application.topLevelWidgets()
        if id(widget) not in ignored_widget_ids and _is_blocked_top_level(widget)
    ]
    assert not escaped_widgets, (
        "Editor-owned widgets escaped as QApplication top-levels: "
        + "; ".join(escaped_widgets)
    )


def editor_top_level_widget_ids() -> frozenset[int]:
    """Return current editor-owned top-level widget identities for test isolation."""

    app = QApplication.instance()
    if app is None:
        return frozenset()
    application = cast(QApplication, app)
    return frozenset(
        id(widget)
        for widget in application.topLevelWidgets()
        if _is_blocked_top_level(widget)
    )


def _is_blocked_top_level(widget: QWidget) -> bool:
    """Return whether one top-level widget matches an editor block signal."""

    class_name = type(widget).__name__
    if class_name in APPROVED_TOP_LEVEL_CLASS_NAMES:
        return False
    object_name = widget.objectName()
    return any(
        signal in class_name or signal in object_name
        for signal in BLOCKED_TOP_LEVEL_SIGNALS
    )


def _describe_top_level_widget(widget: QWidget) -> str:
    """Return a concise diagnostic string for one leaked top-level widget."""

    geometry = widget.geometry()
    return (
        f"{type(widget).__name__}"
        f"(objectName={widget.objectName()!r}, visible={widget.isVisible()}, "
        f"geometry={geometry.x()},{geometry.y()} {geometry.width()}x{geometry.height()})"
    )
