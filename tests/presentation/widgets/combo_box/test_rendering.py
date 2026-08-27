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

"""Verify closed combo rendering is a mutation-free projection."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QPixmap

from substitute.presentation.widgets.combo_box import ComboBox

_LONG_TEXT = "A much longer option that determines the preferred width"


def _render_narrow(combo: ComboBox) -> None:
    """Render one combo at its shrinkable minimum."""

    combo.resize(combo.minimumSizeHint())
    combo.render(QPixmap(combo.size()))


def test_closed_native_search_text_stays_empty(combo_box: ComboBox) -> None:
    """Committed selection should not leak into transient native search text."""

    combo_box.addItem(_LONG_TEXT)

    assert combo_box.currentText() == _LONG_TEXT
    assert combo_box.text() == ""


def test_narrow_render_does_not_emit_text_change(combo_box: ComboBox) -> None:
    """Paint-time elision should not publish transient text mutation."""

    combo_box.addItem(_LONG_TEXT)
    text_changes: list[str] = []
    combo_box.textChanged.connect(text_changes.append)

    _render_narrow(combo_box)

    assert text_changes == []


def test_narrow_render_preserves_committed_text(combo_box: ComboBox) -> None:
    """Paint-time elision should preserve committed and transient text state."""

    combo_box.addItem(_LONG_TEXT)
    _render_narrow(combo_box)

    assert combo_box.currentText() == _LONG_TEXT
    assert combo_box.text() == ""


def test_narrow_render_emits_no_selection_signals(combo_box: ComboBox) -> None:
    """Projection should not masquerade as a user selection."""

    combo_box.addItem(_LONG_TEXT)
    current_text_changes: list[str] = []
    current_index_changes: list[int] = []
    activated_indexes: list[int] = []
    text_activations: list[str] = []
    combo_box.currentTextChanged.connect(current_text_changes.append)
    combo_box.currentIndexChanged.connect(current_index_changes.append)
    combo_box.activated.connect(activated_indexes.append)
    combo_box.textActivated.connect(text_activations.append)

    _render_narrow(combo_box)

    assert current_text_changes == []
    assert current_index_changes == []
    assert activated_indexes == []
    assert text_activations == []


def test_narrow_render_does_not_mutate_text_or_geometry(
    combo_box: ComboBox,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closed painting should not invoke state or layout mutation paths."""

    combo_box.addItem(_LONG_TEXT)
    combo_box.resize(combo_box.minimumSizeHint())

    def fail_set_native_search_text(_text: str) -> None:
        """Reject native text mutation during paint."""

        raise AssertionError("paint mutated native search text")

    def fail_update_geometry() -> None:
        """Reject layout invalidation during paint."""

        raise AssertionError("paint invalidated geometry")

    monkeypatch.setattr(
        combo_box,
        "_set_native_search_text",
        fail_set_native_search_text,
    )
    monkeypatch.setattr(combo_box, "updateGeometry", fail_update_geometry)

    combo_box.render(QPixmap(combo_box.size()))
