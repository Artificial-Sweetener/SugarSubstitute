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

"""Verify link-selector route compaction and shared sizing."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from substitute.presentation.widgets.link_selector_combo_box import (
    LinkSelectorComboBox,
)
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application

_LINK_TEXT = "🔗 SDXL/Text to Image"
_COMPACT_TEXT = "🔗 Text to Image"


@pytest.fixture
def link_selector() -> Iterator[LinkSelectorComboBox]:
    """Yield one link selector and synchronously destroy its Qt owner."""

    ensure_qt_application()
    combo = LinkSelectorComboBox()
    try:
        yield combo
    finally:
        destroy_qt_object(combo)


def test_route_prefix_is_surrendered_before_tail_elision(
    link_selector: LinkSelectorComboBox,
) -> None:
    """Pressure should remove the repeated route before eliding the link tail."""

    link_selector.addItem(_LINK_TEXT)
    full_width = _control_width(link_selector, _LINK_TEXT)
    compact_width = _control_width(link_selector, _COMPACT_TEXT)
    narrow_width = max(link_selector.minimumSizeHint().width(), compact_width - 12)

    assert link_selector._closed_display_text_for_width(full_width) == _LINK_TEXT
    assert link_selector._closed_display_text_for_width(compact_width) == (
        _COMPACT_TEXT
    )
    narrow_text = link_selector._closed_display_text_for_width(narrow_width)
    assert narrow_text not in {_LINK_TEXT, _COMPACT_TEXT}
    assert "SDXL/" not in narrow_text
    assert narrow_text.startswith("🔗 Text")


def test_independent_and_nonrouted_labels_remain_unchanged(
    link_selector: LinkSelectorComboBox,
) -> None:
    """Route-specific compaction should not rewrite unrelated label shapes."""

    link_selector.addItems(["Independent", "🔗 Alpha"])
    assert (
        link_selector._closed_display_text_for_width(
            _control_width(link_selector, "Independent")
        )
        == "Independent"
    )

    link_selector.setCurrentText("🔗 Alpha")
    assert (
        link_selector._closed_display_text_for_width(
            _control_width(link_selector, "🔗 Alpha")
        )
        == "🔗 Alpha"
    )


def test_shared_preferred_width_expands_only_size_hint(
    link_selector: LinkSelectorComboBox,
) -> None:
    """Shared width should expand preference while retaining minimum shrinkability."""

    link_selector.addItem(_LINK_TEXT)
    base_hint = link_selector.sizeHint()
    minimum_hint = link_selector.minimumSizeHint()
    shared_width = base_hint.width() + 80

    link_selector.setSharedPreferredWidth(shared_width)

    assert link_selector.sharedPreferredWidth() == shared_width
    assert link_selector.sizeHint().width() == shared_width
    assert link_selector.minimumSizeHint().width() == minimum_hint.width()


def test_shared_width_fits_actual_closed_text_rect(
    link_selector: LinkSelectorComboBox,
) -> None:
    """Shared width should use the same text budget as closed painting."""

    link_selector.addItems(["Independent", _LINK_TEXT])
    link_selector.setCurrentText(_LINK_TEXT)
    shared_width = _control_width(link_selector, _LINK_TEXT)
    link_selector.setSharedPreferredWidth(shared_width)
    link_selector.resize(link_selector.sizeHint())

    assert link_selector._closed_display_text_rect().width() >= (
        link_selector.fontMetrics().horizontalAdvance(_LINK_TEXT)
    )
    assert link_selector._closed_display_text_for_width(link_selector.width()) == (
        _LINK_TEXT
    )


def test_clearing_shared_width_restores_item_based_sizing(
    link_selector: LinkSelectorComboBox,
) -> None:
    """Removing group width should restore the control's own item preference."""

    link_selector.addItem(_LINK_TEXT)
    base_hint = link_selector.sizeHint()
    link_selector.setSharedPreferredWidth(base_hint.width() + 80)
    link_selector.setSharedPreferredWidth(None)

    assert link_selector.sharedPreferredWidth() is None
    assert link_selector.sizeHint() == base_hint


def test_shared_width_still_allows_pressure_compaction(
    link_selector: LinkSelectorComboBox,
) -> None:
    """A group preference should not prevent compaction at actual narrow width."""

    link_selector.addItem(_LINK_TEXT)
    link_selector.setSharedPreferredWidth(link_selector.sizeHint().width() + 80)
    narrow_text = link_selector._closed_display_text_for_width(
        _control_width(link_selector, _COMPACT_TEXT) - 12
    )

    assert narrow_text != _LINK_TEXT
    assert "SDXL/" not in narrow_text


def _control_width(combo: LinkSelectorComboBox, text: str) -> int:
    """Return the real closed-control width needed for one label."""

    return combo._closed_display_control_width_for_text_width(
        combo.fontMetrics().horizontalAdvance(text)
    )
