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

"""Characterization tests for lightweight widget and utility behavior."""

from __future__ import annotations

import importlib
import os
from typing import cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QSizePolicy, QWidget


class _SignalRecorder:
    """Simple Qt-like signal recorder."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def emit(self, *args) -> None:
        """Record emitted arguments."""
        self.calls.append(args)


def _ensure_qapp() -> QApplication:
    """Return the QApplication required by real widget size-hint tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_combo_box_base_remove_item_left_of_current_decrements_index() -> None:
    """Removing an item before current should decrement current index."""
    mod = importlib.import_module("substitute.presentation.widgets.combo_box")

    class _FakeCombo:
        def __init__(self) -> None:
            self.items = [mod.ComboItem("A"), mod.ComboItem("B"), mod.ComboItem("C")]
            self._currentIndex = 2
            self.currentTextChanged = _SignalRecorder()
            self.currentIndexChanged = _SignalRecorder()

        def currentIndex(self) -> int:
            return self._currentIndex

        def currentText(self) -> str:
            return mod.ComboBoxBase.currentText(self)

        def setText(self, _text: str) -> None:
            return None

        def setCurrentIndex(self, index: int) -> None:
            mod.ComboBoxBase.setCurrentIndex(self, index)

        def count(self) -> int:
            return len(self.items)

        def clear(self) -> None:
            mod.ComboBoxBase.clear(self)

        def itemText(self, index: int) -> str:
            return mod.ComboBoxBase.itemText(self, index)

    fake = _FakeCombo()

    mod.ComboBoxBase.removeItem(fake, 1)

    assert fake._currentIndex == 1
    assert [item.text for item in fake.items] == ["A", "C"]
    assert fake.currentIndexChanged.calls == [(1,)]


def test_combo_box_base_insert_items_before_current_shifts_index() -> None:
    """Bulk insert before current should shift selection index by insert count."""
    mod = importlib.import_module("substitute.presentation.widgets.combo_box")

    class _FakeCombo:
        def __init__(self) -> None:
            self.items = [mod.ComboItem("A"), mod.ComboItem("B")]
            self._currentIndex = 1
            self.currentTextChanged = _SignalRecorder()
            self.currentIndexChanged = _SignalRecorder()

        def currentIndex(self) -> int:
            return self._currentIndex

        def currentText(self) -> str:
            return mod.ComboBoxBase.currentText(self)

        def setText(self, _text: str) -> None:
            return None

        def setCurrentIndex(self, index: int) -> None:
            mod.ComboBoxBase.setCurrentIndex(self, index)

    fake = _FakeCombo()

    mod.ComboBoxBase.insertItems(fake, 0, ["X", "Y"])

    assert [item.text for item in fake.items] == ["X", "Y", "A", "B"]
    assert fake._currentIndex == 3


def test_double_spin_box_text_from_value_trims_trailing_zeroes() -> None:
    """Double spin formatting should trim insignificant trailing zeroes and dot."""
    mod = importlib.import_module("substitute.presentation.widgets.spin_box")

    assert mod.DoubleSpinBox.textFromValue(object(), 1.2300000000) == "1.23"
    assert mod.DoubleSpinBox.textFromValue(object(), 1.0000000000) == "1"


def test_combo_box_max_hint_width_returns_none_when_unset() -> None:
    """ComboBox maxHintWidth should return None when backing attribute is absent."""
    mod = importlib.import_module("substitute.presentation.widgets.combo_box")
    combo = object()
    assert mod.ComboBox.maxHintWidth(combo) is None


def test_combo_box_size_hint_uses_widest_item() -> None:
    """ComboBox preferred width should stay stable for the widest item."""

    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.widgets.combo_box")
    combo = mod.ComboBox()
    combo.addItems(
        [
            "Short",
            "A much longer option that determines the preferred width",
        ]
    )

    short_width = combo.sizeHint().width()
    combo.setCurrentText("A much longer option that determines the preferred width")
    long_width = combo.sizeHint().width()

    assert short_width == long_width
    assert short_width >= combo.fontMetrics().horizontalAdvance(
        "A much longer option that determines the preferred width"
    )


def test_combo_box_size_hint_grows_when_wider_item_is_added() -> None:
    """Adding a wider item should update the combo preferred width."""

    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.widgets.combo_box")
    combo = mod.ComboBox()
    combo.addItem("Short")
    short_width = combo.sizeHint().width()

    combo.addItem("A much longer option that should widen the combo")

    assert combo.currentText() == "Short"
    assert combo.sizeHint().width() > short_width


def test_combo_box_size_hint_resets_after_items_are_cleared() -> None:
    """Clearing items should remove any stale widest-item preferred width."""

    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.widgets.combo_box")
    combo = mod.ComboBox()
    combo.addItem("A much longer option that should widen the combo")
    long_width = combo.sizeHint().width()

    combo.clear()
    combo.addItem("Short")

    assert combo.sizeHint().width() < long_width


def test_combo_box_max_hint_width_caps_preferred_width_only() -> None:
    """Explicit max-hint width should cap sizeHint without fixing widget width."""

    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.widgets.combo_box")
    combo = mod.ComboBox()
    combo.addItem("A much longer option that should exceed the explicit cap" * 2)
    uncapped_width = combo.sizeHint().width()

    combo.setMaxHintWidth(320)
    capped_width = combo.sizeHint().width()

    assert capped_width <= 320
    assert capped_width >= combo.minimumSizeHint().width()
    assert combo.maximumWidth() > 320

    combo.setMaxHintWidth(None)

    assert combo.sizeHint().width() == uncapped_width


def test_combo_box_selection_changes_do_not_resize_preferred_width() -> None:
    """Selecting existing items should not change widest-item preferred width."""

    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.widgets.combo_box")
    combo = mod.ComboBox()
    combo.addItems(
        [
            "Short",
            "Medium length",
            "A much longer option that determines the preferred width",
        ]
    )

    combo.setCurrentText("Short")
    short_width = combo.sizeHint().width()
    combo.setCurrentText("A much longer option that determines the preferred width")
    long_width = combo.sizeHint().width()
    combo.setCurrentText("Medium length")
    medium_width = combo.sizeHint().width()

    assert short_width == long_width == medium_width


def test_combo_box_minimum_size_hint_allows_elision_when_constrained() -> None:
    """ComboBox should remain shrinkable below widest-item preferred width."""

    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.widgets.combo_box")
    combo = mod.ComboBox()
    combo.addItem("A much longer option that determines the preferred width")

    assert combo.minimumSizeHint().width() < combo.sizeHint().width()


def test_combo_box_minimum_size_hint_does_not_reenter_size_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ComboBox minimum width should not recurse through sizeHint()."""

    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.widgets.combo_box")
    combo = mod.ComboBox()
    combo.addItem("A much longer option that determines the preferred width")

    def fail_size_hint(self: object) -> None:
        raise AssertionError("minimumSizeHint re-entered sizeHint")

    monkeypatch.setattr(mod.ComboBox, "sizeHint", fail_size_hint)

    hint = combo.minimumSizeHint()

    assert hint.width() == mod._COMBO_SHRINKABLE_MINIMUM_WIDTH


def test_combo_box_closed_display_text_elides_when_constrained() -> None:
    """Closed combo text should elide when allocated width is constrained."""

    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.widgets.combo_box")
    combo = mod.ComboBox()
    combo.addItem("A much longer option that determines the preferred width")
    constrained_width = combo.minimumSizeHint().width()

    display_text = combo._closed_display_text_for_width(constrained_width)
    available_width = max(
        0, constrained_width - combo._closed_display_text_chrome_width()
    )

    assert display_text != combo.currentText()
    assert combo.fontMetrics().horizontalAdvance(display_text) <= available_width


def test_combo_box_closed_display_text_responds_to_width() -> None:
    """Closed combo elision should remain responsive to allocated width."""

    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.widgets.combo_box")
    combo = mod.ComboBox()
    long_text = "A much longer option that determines the preferred width"
    combo.addItem(long_text)

    narrow_text = combo._closed_display_text_for_width(combo.minimumSizeHint().width())
    wide_text = combo._closed_display_text_for_width(combo.sizeHint().width())

    assert narrow_text != long_text
    assert wide_text == long_text
    assert len(wide_text) > len(narrow_text)


def test_link_selector_combo_box_surrenders_route_prefix_before_eliding() -> None:
    """Link selectors should drop repeated route prefixes before tail elision."""

    _ensure_qapp()
    mod = importlib.import_module(
        "substitute.presentation.widgets.link_selector_combo_box"
    )
    combo = mod.LinkSelectorComboBox()
    link_text = "🔗 SDXL/Text to Image"
    compact_text = "🔗 Text to Image"
    combo.addItem(link_text)

    full_width = combo._closed_display_control_width_for_text_width(
        combo.fontMetrics().horizontalAdvance(link_text)
    )
    compact_width = combo._closed_display_control_width_for_text_width(
        combo.fontMetrics().horizontalAdvance(compact_text)
    )
    narrow_width = max(combo.minimumSizeHint().width(), compact_width - 12)

    assert combo._closed_display_text_for_width(full_width) == link_text
    assert combo._closed_display_text_for_width(compact_width) == compact_text

    narrow_text = combo._closed_display_text_for_width(narrow_width)
    assert narrow_text != link_text
    assert narrow_text != compact_text
    assert "SDXL/" not in narrow_text
    assert narrow_text.startswith("🔗 Text")


def test_link_selector_combo_box_keeps_independent_and_non_routed_labels() -> None:
    """Special compaction should ignore independent and non-routed labels."""

    _ensure_qapp()
    mod = importlib.import_module(
        "substitute.presentation.widgets.link_selector_combo_box"
    )
    combo = mod.LinkSelectorComboBox()
    combo.addItems(["Independent", "🔗 Alpha"])

    independent_width = combo._closed_display_control_width_for_text_width(
        combo.fontMetrics().horizontalAdvance("Independent")
    )
    assert combo._closed_display_text_for_width(independent_width) == "Independent"

    combo.setCurrentText("🔗 Alpha")
    plain_width = combo._closed_display_control_width_for_text_width(
        combo.fontMetrics().horizontalAdvance("🔗 Alpha")
    )
    assert combo._closed_display_text_for_width(plain_width) == "🔗 Alpha"


def test_link_selector_combo_box_shared_preferred_width_affects_size_hint() -> None:
    """Shared preferred width should expand sizeHint without fixing the control."""

    _ensure_qapp()
    mod = importlib.import_module(
        "substitute.presentation.widgets.link_selector_combo_box"
    )
    combo = mod.LinkSelectorComboBox()
    combo.addItem("🔗 SDXL/Text to Image")
    base_hint = combo.sizeHint()
    minimum_hint = combo.minimumSizeHint()
    shared_width = base_hint.width() + 80

    combo.setSharedPreferredWidth(shared_width)

    assert combo.sharedPreferredWidth() == shared_width
    assert combo.sizeHint().width() == shared_width
    assert combo.minimumSizeHint().width() == minimum_hint.width()


def test_link_selector_combo_box_shared_width_fits_actual_closed_text_rect() -> None:
    """Shared width should use the same closed text rect budget as paint."""

    _ensure_qapp()
    mod = importlib.import_module(
        "substitute.presentation.widgets.link_selector_combo_box"
    )
    combo = mod.LinkSelectorComboBox()
    link_text = "🔗 SDXL/Text to Image"
    combo.addItems(["Independent", link_text])
    combo.setCurrentText(link_text)
    shared_width = combo._closed_display_control_width_for_text_width(
        combo.fontMetrics().horizontalAdvance(link_text)
    )

    combo.setSharedPreferredWidth(shared_width)
    combo.resize(combo.sizeHint())

    assert combo._closed_display_text_rect().width() >= (
        combo.fontMetrics().horizontalAdvance(link_text)
    )
    assert combo._closed_display_text_for_width(combo.width()) == link_text


def test_link_selector_combo_box_clears_shared_preferred_width() -> None:
    """Clearing shared preferred width should restore ordinary item-based sizing."""

    _ensure_qapp()
    mod = importlib.import_module(
        "substitute.presentation.widgets.link_selector_combo_box"
    )
    combo = mod.LinkSelectorComboBox()
    combo.addItem("🔗 SDXL/Text to Image")
    base_hint = combo.sizeHint()
    combo.setSharedPreferredWidth(base_hint.width() + 80)

    combo.setSharedPreferredWidth(None)

    assert combo.sharedPreferredWidth() is None
    assert combo.sizeHint() == base_hint


def test_link_selector_combo_box_shared_width_still_allows_pressure_elision() -> None:
    """Paint-time display should still compact from actual narrow width."""

    _ensure_qapp()
    mod = importlib.import_module(
        "substitute.presentation.widgets.link_selector_combo_box"
    )
    combo = mod.LinkSelectorComboBox()
    link_text = "🔗 SDXL/Text to Image"
    compact_text = "🔗 Text to Image"
    combo.addItem(link_text)
    combo.setSharedPreferredWidth(combo.sizeHint().width() + 80)

    compact_width = combo._closed_display_control_width_for_text_width(
        combo.fontMetrics().horizontalAdvance(compact_text)
    )
    narrow_text = combo._closed_display_text_for_width(compact_width - 12)

    assert narrow_text != link_text
    assert "SDXL/" not in narrow_text


def test_combo_box_closed_native_text_is_empty_after_setup() -> None:
    """Closed combo state should keep selection out of native search text."""

    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.widgets.combo_box")
    combo = mod.ComboBox()
    long_text = "A much longer option that determines the preferred width"
    combo.addItem(long_text)

    assert combo.currentText() == long_text
    assert combo.text() == ""


def test_combo_box_narrow_render_does_not_emit_text_changed() -> None:
    """Closed elision paint should not mutate line-edit text state."""

    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.widgets.combo_box")
    combo = mod.ComboBox()
    combo.addItem("A much longer option that determines the preferred width")
    combo.resize(combo.minimumSizeHint().width(), combo.minimumSizeHint().height())

    text_changes: list[str] = []
    combo.textChanged.connect(text_changes.append)

    combo.render(QPixmap(combo.size()))

    assert text_changes == []


def test_combo_box_narrow_render_preserves_committed_text() -> None:
    """Closed elision paint should leave committed and visible text unchanged."""

    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.widgets.combo_box")
    combo = mod.ComboBox()
    long_text = "A much longer option that determines the preferred width"
    combo.addItem(long_text)
    combo.resize(combo.minimumSizeHint().width(), combo.minimumSizeHint().height())

    combo.render(QPixmap(combo.size()))

    assert combo.currentText() == long_text
    assert combo.text() == ""


def test_combo_box_narrow_render_does_not_emit_committed_selection_signals() -> None:
    """Closed elision paint should not emit committed selection signals."""

    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.widgets.combo_box")
    combo = mod.ComboBox()
    combo.addItem("A much longer option that determines the preferred width")
    combo.resize(combo.minimumSizeHint().width(), combo.minimumSizeHint().height())
    current_text_changes: list[str] = []
    current_index_changes: list[int] = []
    activated_indexes: list[int] = []
    text_activations: list[str] = []
    combo.currentTextChanged.connect(current_text_changes.append)
    combo.currentIndexChanged.connect(current_index_changes.append)
    combo.activated.connect(activated_indexes.append)
    combo.textActivated.connect(text_activations.append)

    combo.render(QPixmap(combo.size()))

    assert current_text_changes == []
    assert current_index_changes == []
    assert activated_indexes == []
    assert text_activations == []


def test_combo_box_narrow_render_does_not_set_text_or_geometry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closed elision paint should not use text mutation or layout invalidation."""

    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.widgets.combo_box")
    combo = mod.ComboBox()
    combo.addItem("A much longer option that determines the preferred width")
    combo.resize(combo.minimumSizeHint().width(), combo.minimumSizeHint().height())

    def fail_set_native_search_text(_text: str) -> None:
        raise AssertionError("paint mutated native search text")

    def fail_update_geometry() -> None:
        raise AssertionError("paint invalidated geometry")

    monkeypatch.setattr(combo, "_set_native_search_text", fail_set_native_search_text)
    monkeypatch.setattr(combo, "updateGeometry", fail_update_geometry)

    combo.render(QPixmap(combo.size()))


def test_combo_box_size_hint_uses_cached_widest_width(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ComboBox layout hints should not rescan items after cache refresh."""

    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.widgets.combo_box")
    combo = mod.ComboBox()
    combo.addItems(
        [
            "Short",
            "A much longer option that determines the preferred width",
        ]
    )

    def fail_width_scan(self: object) -> None:
        raise AssertionError("sizeHint rescanned item text widths")

    monkeypatch.setattr(mod.ComboBox, "_widest_item_text_width", fail_width_scan)

    assert combo.sizeHint().width() >= combo.minimumSizeHint().width()


def test_combo_box_cached_width_refreshes_after_item_changes() -> None:
    """ComboBox cached preferred width should track item text mutations."""

    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.widgets.combo_box")
    combo = mod.ComboBox()
    combo.addItems(["Short", "A much longer option"])
    long_width = combo.sizeHint().width()

    combo.setItemText(1, "Tiny")
    shortened_width = combo.sizeHint().width()
    combo.addItem("An even longer option than the original one")
    extended_width = combo.sizeHint().width()
    combo.removeItem(2)
    removed_width = combo.sizeHint().width()

    assert shortened_width < long_width
    assert extended_width > shortened_width
    assert removed_width == shortened_width


def test_combo_box_selection_change_does_not_update_geometry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selecting existing items should repaint without invalidating layout."""

    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.widgets.combo_box")
    combo = mod.ComboBox()
    combo.addItems(["Short", "A much longer option"])

    def fail_update_geometry() -> None:
        raise AssertionError("selection invalidated geometry")

    monkeypatch.setattr(combo, "updateGeometry", fail_update_geometry)

    combo.setCurrentText("A much longer option")
    assert combo.currentText() == "A much longer option"


def test_seed_box_height_matches_searchable_combo_box() -> None:
    """SeedBox should align vertically with searchable combo fields."""

    _ensure_qapp()
    combo_mod = importlib.import_module("substitute.presentation.widgets.combo_box")
    seed_mod = importlib.import_module("substitute.presentation.widgets.seed_box")
    combo = combo_mod.ComboBox()
    seed = seed_mod.SeedBox()

    assert seed.height() == combo.height()
    assert seed.line_edit.height() == combo.height()
    assert seed.split_button.height() == combo.height()


def test_seed_box_uses_combo_like_shrinkable_width_policy() -> None:
    """SeedBox should prefer a stable width without requiring one."""

    _ensure_qapp()
    combo_mod = importlib.import_module("substitute.presentation.widgets.combo_box")
    seed_mod = importlib.import_module("substitute.presentation.widgets.seed_box")
    combo = combo_mod.ComboBox()
    seed = seed_mod.SeedBox()

    assert (
        seed.sizePolicy().horizontalPolicy()
        == combo.sizePolicy().horizontalPolicy()
        == QSizePolicy.Policy.Maximum
    )
    assert (
        seed.sizePolicy().verticalPolicy()
        == combo.sizePolicy().verticalPolicy()
        == QSizePolicy.Policy.Fixed
    )
    assert seed.minimumWidth() == 0
    assert seed.maximumWidth() >= seed.sizeHint().width()
    assert seed.sizeHint().width() > seed.minimumSizeHint().width()
    assert seed.minimumSizeHint().width() == combo.minimumSizeHint().width()


def test_seed_box_resizes_children_when_width_constrained() -> None:
    """SeedBox should keep its overlay usable at its shrinkable minimum."""

    _ensure_qapp()
    seed_mod = importlib.import_module("substitute.presentation.widgets.seed_box")
    seed = seed_mod.SeedBox()
    constrained_width = seed.minimumSizeHint().width()

    seed.resize(constrained_width, seed.height())
    seed.show()
    _ensure_qapp().processEvents()

    assert seed.width() == constrained_width
    assert seed.line_edit.width() == constrained_width
    assert seed.split_button.x() == constrained_width - seed.split_button.width()


def test_seed_factory_does_not_force_node_card_minimum_width() -> None:
    """Factory-created seed fields should collapse like combo fields in node rows."""

    _ensure_qapp()
    numeric_factory = importlib.import_module(
        "substitute.presentation.editor.panel.factories.numeric_factory"
    )
    parent = QWidget()
    try:
        field = numeric_factory.widget_factory_seedbox(
            parent,
            "ksampler",
            "seed",
            123,
            {},
            field_type="INT",
            constraints={"min": 0, "max": 999, "step": 1},
        )

        assert field is not None
        assert field.minimumWidth() == 0
        assert field.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Maximum
    finally:
        parent.deleteLater()
        _ensure_qapp().processEvents()


def test_create_vbox_applies_parent_margins_and_spacing(monkeypatch) -> None:
    """create_vbox should forward parent and layout geometry settings."""
    mod = importlib.import_module("substitute.presentation.editor.utils.create_vbox")

    class _VBox:
        def __init__(self, parent=None) -> None:
            self.parent = parent
            self.margins = None
            self.spacing = None

        def setContentsMargins(self, *margins) -> None:
            self.margins = margins

        def setSpacing(self, spacing: int) -> None:
            self.spacing = spacing

    monkeypatch.setattr(mod, "QVBoxLayout", _VBox)

    parent = object()
    layout = mod.create_vbox(parent=parent, margins=(1, 2, 3, 4), spacing=9)

    assert isinstance(layout, _VBox)
    assert layout.parent is parent
    assert layout.margins == (1, 2, 3, 4)
    assert layout.spacing == 9
