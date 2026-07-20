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

"""Characterization tests for shared thumbnail-picker behavior."""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication


class _Thumbnail:
    """Minimal thumbnail double used by shared picker helper tests."""

    def __init__(self) -> None:
        self.cleared = False

    def clear(self) -> None:
        """Record thumbnail clearing."""

        self.cleared = True


class _Caption:
    """Minimal caption double used by shared picker helper tests."""

    def __init__(self) -> None:
        self.text = "existing"
        self.width: int | None = None
        self.tooltip = "existing"
        self.visible = True

    def setText(self, text: str) -> None:
        """Record caption text."""

        self.text = text

    def setFixedWidth(self, width: int) -> None:
        """Record width updates."""

        self.width = width

    def setToolTip(self, tooltip: str) -> None:
        """Record tooltip updates."""

        self.tooltip = tooltip

    def hide(self) -> None:
        """Record hide calls."""

        self.visible = False


def _qapp() -> QApplication:
    """Return the existing QApplication or create one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def test_thumbnail_picker_caption_uses_fluent_tooltip_filter() -> None:
    """Caption tooltip behavior should use the shared QFluent owner."""

    _qapp()
    sys.modules.pop("sugarsubstitute_shared.presentation.fluent_tooltips", None)
    sys.modules.pop(
        "substitute.presentation.editor.panel.widgets.fields.thumbnail_picker_base",
        None,
    )
    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.fields.thumbnail_picker_base"
    )

    picker = mod.ThumbnailPickerBase()

    assert isinstance(
        picker._caption_tooltip_filter,
        mod.FluentToolTipFilter,
    )
    assert picker._caption_tooltip_filter._tooltipDelay == 600

    picker.close()
    picker.deleteLater()


def test_restore_placeholder_or_clear_prefers_placeholder_when_available() -> None:
    """Shared restore helper should route back through the configured placeholder path."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.fields.thumbnail_picker_base"
    )
    placeholder_calls: list[str] = []
    fake = SimpleNamespace(
        _placeholder_image_path="C:/images/default.png",
        set_placeholder_image=lambda path: placeholder_calls.append(path),
    )

    mod.ThumbnailPickerBase._restore_placeholder_or_clear(fake)

    assert placeholder_calls == ["C:/images/default.png"]


def test_restore_placeholder_or_clear_resets_thumbnail_state_without_placeholder() -> (
    None
):
    """Shared restore helper should clear thumbnail, caption, and current path state."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.fields.thumbnail_picker_base"
    )
    thumbnail = _Thumbnail()
    caption = _Caption()
    fake = SimpleNamespace(
        _placeholder_image_path=None,
        thumbnail=thumbnail,
        caption=caption,
        thumbnail_size=352,
        _current_file_path="C:/images/chosen.png",
    )

    mod.ThumbnailPickerBase._restore_placeholder_or_clear(fake)

    assert thumbnail.cleared is True
    assert caption.text == ""
    assert caption.width == 344
    assert caption.tooltip == ""
    assert caption.visible is False
    assert fake._current_file_path is None
