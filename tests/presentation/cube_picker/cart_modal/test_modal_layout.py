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

"""Widget tests for the cube stack cart modal."""

from __future__ import annotations

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QLabel, QScrollArea, QWidget
from qfluentwidgets import MessageBoxBase, ScrollArea, SimpleCardWidget  # type: ignore[import-untyped]
from qfluentwidgets.common.smooth_scroll import (  # type: ignore[import-untyped]
    SmoothMode,
)

from substitute.application.cubes import (
    CubeStackDraft,
)
from substitute.presentation.cube_picker.cube_stack_cart_modal import (
    _CART_DROP_ZONE_HEIGHT,
    _SCROLLBAR_ALLOWANCE,
    CubeStackCartModal,
)
from substitute.presentation.cube_picker.cube_picker_card import (
    CUBE_PICKER_CARD_HEIGHT,
    CUBE_PICKER_CARD_WIDTH,
)
from substitute.presentation.cubes.cube_placeholder_card import CubePlaceholderCard
from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_ITEM_EXPANDED_WIDTH,
    CUBE_STACK_EXPANDED_WIDTH,
)


from tests.presentation.cube_picker.cart_modal.support import (
    _IconFactory,
    _all_label_texts,
    _app,
    _draft_entries,
    _pack_catalog_classifications,
    _pack_catalog_records,
    _six_catalog_classifications,
    _six_catalog_records,
    _visible_label_texts,
)
from tests.support.qt.lifecycle import destroy_qt_object


def test_cart_modal_uses_qfluent_modal_shell_and_flat_regions() -> None:
    """The stack picker should render as a QFluent modal with flat regions."""

    app = _app()
    parent = QWidget()
    parent.resize(1000, 700)
    parent.show()
    modal = CubeStackCartModal(
        records=_six_catalog_records(),
        classifications=_six_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=parent,
    )
    modal.show()
    app.processEvents()

    assert isinstance(modal, MessageBoxBase)
    assert isinstance(modal._library_pane, QWidget)
    assert isinstance(modal._cart_pane, QWidget)
    assert not isinstance(modal._library_pane, SimpleCardWidget)
    assert not isinstance(modal._cart_pane, SimpleCardWidget)
    assert modal._body_layout.itemAt(0).widget() is modal._library_controls
    assert modal._body_layout.itemAt(1).widget() is modal._columns
    assert modal._columns_layout.itemAt(0).widget() is modal._library_pane
    assert modal._columns_layout.itemAt(1).widget() is modal._cart_pane
    assert isinstance(modal._library_scroll, ScrollArea)
    assert isinstance(modal._cart_scroll, ScrollArea)
    assert type(modal._library_scroll) is not QScrollArea
    assert type(modal._cart_scroll) is not QScrollArea


def test_cart_modal_disables_qfluent_smooth_scrolling() -> None:
    """The cart modal scroll panes should respond to wheel input immediately."""

    app = _app()
    parent = QWidget()
    parent.resize(1000, 700)
    parent.show()
    modal = CubeStackCartModal(
        records=_six_catalog_records(),
        classifications=_six_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=_draft_entries(6)),
        icon_factory=_IconFactory(),
        parent=parent,
    )
    try:
        modal.show()
        app.processEvents()

        for scroll_area in (modal._library_scroll, modal._cart_scroll):
            scroll_delegate = scroll_area.scrollDelagate
            assert scroll_delegate.useAni is False
            assert (
                scroll_delegate.verticalSmoothScroll.smoothMode is SmoothMode.NO_SMOOTH
            )
            assert (
                scroll_delegate.horizonSmoothScroll.smoothMode is SmoothMode.NO_SMOOTH
            )
            assert scroll_delegate.vScrollBar.duration == 0
            assert scroll_delegate.hScrollBar.duration == 0
            assert scroll_delegate.vScrollBar.geometry().x() == scroll_area.width() - 13
            assert scroll_delegate.vScrollBar.geometry().y() == 1
            assert scroll_delegate.vScrollBar.geometry().width() == 12
            assert (
                scroll_delegate.vScrollBar.geometry().height()
                == scroll_area.height() - 2
            )
        assert modal._library_scroll.width() == (
            CUBE_PICKER_CARD_WIDTH + _SCROLLBAR_ALLOWANCE
        )
        assert modal._cart_scroll.width() == (
            CUBE_STACK_EXPANDED_WIDTH + _SCROLLBAR_ALLOWANCE
        )
        assert (
            modal._library_scroll.scrollDelagate.vScrollBar.mapTo(
                modal._library_pane,
                QPoint(0, 0),
            ).x()
            == modal._library_pane.width() - 13
        )
        assert (
            modal._cart_scroll.scrollDelagate.vScrollBar.mapTo(
                modal._cart_pane,
                QPoint(0, 0),
            ).x()
            == modal._cart_pane.width() - 13
        )
    finally:
        destroy_qt_object(parent)


def test_cart_modal_does_not_show_visible_count_labels() -> None:
    """Normal modal UI should not show library or cart count metadata."""

    app = _app()
    parent = QWidget()
    parent.resize(1000, 700)
    parent.show()
    modal = CubeStackCartModal(
        records=_six_catalog_records(),
        classifications=_six_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=_draft_entries(2)),
        icon_factory=_IconFactory(),
        parent=parent,
    )
    modal.show()
    app.processEvents()

    visible_text = set(_visible_label_texts(modal.widget))

    assert "6 cubes" not in visible_text
    assert "2 cubes" not in visible_text
    assert "1 cube" not in visible_text
    assert "0 cubes" not in visible_text


def test_cart_modal_stack_drop_zone_has_stable_height() -> None:
    """The cart drop zone should not shrink around zero, one, or two cards."""

    _app()
    parent = QWidget()
    parent.resize(1000, 700)
    pane_heights: list[int] = []
    scroll_heights: list[int] = []
    content_heights: list[int] = []
    for entry_count in (0, 1, 2):
        modal = CubeStackCartModal(
            records=_six_catalog_records(),
            classifications=_six_catalog_classifications(),
            initial_draft=CubeStackDraft(entries=_draft_entries(entry_count)),
            icon_factory=_IconFactory(),
            parent=parent,
        )
        pane_heights.append(modal._cart_pane.height())
        scroll_heights.append(modal._cart_scroll.height())
        content_heights.append(modal._staging_stack.preferred_height())

    assert len(set(pane_heights)) == 1
    assert len(set(scroll_heights)) == 1
    assert pane_heights[0] == _CART_DROP_ZONE_HEIGHT
    assert (
        scroll_heights[0] == _CART_DROP_ZONE_HEIGHT - modal._cart_header_area_height()
    )
    assert scroll_heights[0] > content_heights[-1]


def test_cart_modal_blank_stack_space_drops_at_end() -> None:
    """Blank cart space below cards should be an easy end-of-stack drop target."""

    app = _app()
    parent = QWidget()
    parent.resize(1000, 700)
    modal = CubeStackCartModal(
        records=_six_catalog_records(),
        classifications=_six_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=_draft_entries(2)),
        icon_factory=_IconFactory(),
        parent=parent,
    )
    modal.show()
    app.processEvents()

    blank_y = modal._staging_stack.height() - 16
    global_pos = modal._staging_stack.mapToGlobal(QPoint(20, blank_y))

    assert modal._staging_stack.insertion_index_at_global_pos(global_pos) == 2


def test_cart_modal_regions_are_closer_without_pane_cards() -> None:
    """Flat modal regions should sit close enough to read as one layout."""

    _app()
    modal = CubeStackCartModal(
        records=_six_catalog_records(),
        classifications=_six_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )

    assert modal._body_layout.spacing() <= 8


def test_cart_modal_uses_stable_pane_geometry_for_short_empty_cart() -> None:
    """Short catalogs should use the modal pane height without empty footer gaps."""

    app = _app()
    parent = QWidget()
    parent.resize(1000, 700)
    parent.show()
    modal = CubeStackCartModal(
        records=_six_catalog_records(),
        classifications=_six_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=parent,
    )
    modal.show()
    app.processEvents()

    assert modal.widget.height() <= int(parent.height() * 0.9)
    assert modal.widget.width() < 900
    assert modal._library_pane.width() <= CUBE_PICKER_CARD_WIDTH + 72
    assert modal._cart_pane.width() <= CUBE_STACK_EXPANDED_WIDTH + 72
    library_bottom = modal._library_scroll.mapTo(
        modal.widget, QPoint(0, modal._library_scroll.height())
    ).y()
    cart_bottom = modal._cart_scroll.mapTo(
        modal.widget, QPoint(0, modal._cart_scroll.height())
    ).y()
    assert cart_bottom == library_bottom
    footer_y = modal._apply_button.mapTo(modal.widget, QPoint(0, 0)).y()
    pane_bottom = max(
        modal._library_pane.mapTo(
            modal.widget, QPoint(0, modal._library_pane.height())
        ).y(),
        modal._cart_pane.mapTo(modal.widget, QPoint(0, modal._cart_pane.height())).y(),
    )
    assert footer_y - pane_bottom <= 32


def test_cart_modal_library_results_and_cart_align_vertically() -> None:
    """Picker list and stack column should share bounds and header offset."""

    app = _app()
    parent = QWidget()
    parent.resize(1000, 700)
    parent.show()
    modal = CubeStackCartModal(
        records=_six_catalog_records(),
        classifications=_six_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=_draft_entries(2)),
        icon_factory=_IconFactory(),
        parent=parent,
    )
    modal.show()
    app.processEvents()

    library_top = modal._library_scroll.mapTo(modal.widget, QPoint(0, 0)).y()
    cart_top = modal._cart_pane.mapTo(modal.widget, QPoint(0, 0)).y()
    cart_content_top = modal._staging_stack.mapTo(modal.widget, QPoint(0, 0)).y()
    library_bottom = modal._library_scroll.mapTo(
        modal.widget, QPoint(0, modal._library_scroll.height())
    ).y()
    cart_bottom = modal._cart_pane.mapTo(
        modal.widget, QPoint(0, modal._cart_pane.height())
    ).y()

    assert cart_top == library_top
    assert cart_bottom == library_bottom
    assert modal._cart_pane.height() == modal._library_scroll.height()
    assert modal._cart_scroll.height() == (
        modal._library_scroll.height() - modal._cart_header_area_height()
    )
    assert cart_content_top == library_top + modal._cart_header_area_height()


def test_cart_modal_stack_overflow_scrolls_without_growing_modal() -> None:
    """Large drafts should grow scroll content, not the cart viewport or modal."""

    app = _app()
    parent = QWidget()
    parent.resize(1000, 700)
    modal = CubeStackCartModal(
        records=_six_catalog_records(),
        classifications=_six_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=_draft_entries(14)),
        icon_factory=_IconFactory(),
        parent=parent,
    )
    modal.show()
    app.processEvents()

    assert modal._library_scroll.height() == _CART_DROP_ZONE_HEIGHT
    assert modal._cart_pane.height() == _CART_DROP_ZONE_HEIGHT
    assert modal._cart_scroll.height() == (
        _CART_DROP_ZONE_HEIGHT - modal._cart_header_area_height()
    )
    assert modal._cart_scroll_content.height() > modal._cart_scroll.height()
    assert modal._cart_scroll.verticalScrollBar().maximum() > 0
    assert modal.widget.height() <= modal._available_modal_height()


def test_cart_modal_library_results_have_compact_content_height() -> None:
    """Library cards should stack by content height instead of filling the viewport."""

    _app()
    modal = CubeStackCartModal(
        records=_six_catalog_records(),
        classifications=_six_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )

    expected_content_height = (
        (6 * CUBE_PICKER_CARD_HEIGHT)
        + modal._model_header_height()
        + (2 * modal._role_header_height())
        + (8 * modal._library_result_spacing())
        + (2 * modal._section_gap())
    )
    assert modal._library_content_height() == expected_content_height
    assert modal._results.height() <= expected_content_height + 12


def test_cart_modal_empty_cart_uses_dotted_cube_placeholder() -> None:
    """An empty cart should show the shared dotted cube placeholder."""

    _app()
    modal = CubeStackCartModal(
        records=_six_catalog_records(),
        classifications=_six_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )

    placeholders = modal._staging_stack.findChildren(
        CubePlaceholderCard,
        "cubeStagingEmptyPlaceholder",
    )
    visible_text = set(_visible_label_texts(modal._staging_stack))

    assert len(placeholders) == 1
    assert placeholders[0].isHidden() is False
    assert placeholders[0].width() == CUBE_ITEM_EXPANDED_WIDTH
    assert placeholders[0].height() == CUBE_PICKER_CARD_HEIGHT
    assert "Drag cubes here" not in visible_text


def test_cart_modal_omits_segmented_library_view_picker() -> None:
    """The modal should expose search without Kind, Pack, or Model view tabs."""

    _app()
    modal = CubeStackCartModal(
        records=_pack_catalog_records(),
        classifications=_pack_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )

    assert isinstance(modal._library_title, QLabel)

    assert not hasattr(modal, "_view_tabs")
    assert not hasattr(modal, "_view_row")
    assert not hasattr(modal, "_filter_tabs")
    assert not hasattr(modal, "_filter_row")
    assert modal._library_title.text() == "Cube library"
    assert "Kind" not in _all_label_texts(modal._library_controls)
    assert "Pack" not in _all_label_texts(modal._library_controls)
    assert "Model" not in _all_label_texts(modal._library_controls)


def test_cart_modal_control_height_stays_stable_without_view_picker() -> None:
    """Filtering should not reserve or release a removed view-picker row."""

    app = _app()
    modal = CubeStackCartModal(
        records=_pack_catalog_records(),
        classifications=_pack_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )
    control_height = modal._library_controls_height()

    modal._search.setText("SDXL")
    app.processEvents()

    assert not hasattr(modal, "_view_row")
    assert not hasattr(modal, "_filter_row")
    assert modal._library_controls_height() == control_height
    assert modal._library_controls.height() == modal._library_controls_height()
