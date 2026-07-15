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

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QIcon, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QScrollArea, QWidget
from qfluentwidgets import MessageBoxBase, ScrollArea, SimpleCardWidget  # type: ignore[import-untyped]
from qfluentwidgets.common.smooth_scroll import (  # type: ignore[import-untyped]
    SmoothMode,
)

from substitute.application.cubes import (
    CubePickerClassification,
    CubePickerRole,
    CubeStackDraft,
    CubeStackDraftEntry,
)
from substitute.application.ports import CubeCatalogRecord
from substitute.domain.cube_library import CubeSourceMetadata
from substitute.presentation.cube_picker.cube_stack_cart_modal import (
    _CART_DROP_ZONE_HEIGHT,
    _SCROLLBAR_ALLOWANCE,
    CubeStackCartModal,
)
from substitute.presentation.cube_picker.cube_picker_card import (
    CUBE_PICKER_CARD_HEIGHT,
    CUBE_PICKER_CARD_WIDTH,
)
from substitute.presentation.cube_picker import CubeStagingDrawer
from substitute.presentation.cubes.cube_placeholder_card import CubePlaceholderCard
from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_ITEM_EXPANDED_WIDTH,
    CUBE_STACK_EXPANDED_WIDTH,
)


def _app() -> QApplication:
    """Return a QApplication for lightweight widget construction."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


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
        modal.close()
        parent.close()
        modal.deleteLater()
        parent.deleteLater()
        app.processEvents()


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


def test_cart_modal_library_cards_use_stack_card_visual_without_close_button() -> None:
    """Library cards should share stack-card dimensions without draft close controls."""

    _app()
    modal = CubeStackCartModal(
        records=_six_catalog_records(),
        classifications=_six_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )

    card = next(iter(modal._cards.values()))

    assert card.width() == CUBE_PICKER_CARD_WIDTH
    assert card.height() == CUBE_PICKER_CARD_HEIGHT
    assert not hasattr(card, "closeButton")
    assert card.findChildren(QLabel) == []


def test_cart_modal_library_cards_use_hover_and_press_visual_state() -> None:
    """Library cards should feed hover and press state into the shared visual."""

    _app()
    modal = CubeStackCartModal(
        records=_six_catalog_records(),
        classifications=_six_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )
    card = next(iter(modal._cards.values()))

    card.set_selected(False)
    idle_state = card._visual_state()
    card.set_selected(True)
    selected_state = card._visual_state()

    assert idle_state.selected is True
    assert selected_state.selected is True
    assert idle_state.hovered is False
    assert selected_state.hovered is False
    assert idle_state.pressed is False
    assert selected_state.pressed is False

    card._hovered = True
    hovered_state = card._visual_state()
    card._pressed = True
    pressed_state = card._visual_state()

    assert hovered_state.hovered is True
    assert hovered_state.pressed is False
    assert pressed_state.hovered is True
    assert pressed_state.pressed is True


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


def test_cart_modal_starts_from_initial_workflow_draft_and_reset_restores_it() -> None:
    """The cart stack should represent the real workflow draft on open."""

    _app()
    parent = QWidget()
    parent.resize(1000, 700)
    initial_entry = CubeStackDraftEntry(
        draft_id="existing:Text",
        source="existing",
        cube_id="cube-existing",
        display_name="Text",
        secondary_text="v1.0.0 - base-cubes",
        icon=None,
        existing_alias="Text",
    )
    modal = CubeStackCartModal(
        records=[
            CubeCatalogRecord(cube_id="cube-a", version="1.0.0", display_name="A")
        ],
        initial_draft=CubeStackDraft(entries=(initial_entry,)),
        icon_factory=_IconFactory(),
        parent=parent,
    )

    assert modal._staging_stack.entries() == (initial_entry,)
    assert modal._apply_button.isEnabled() is False

    modal._stage_cube_from_library("cube-a")
    assert [entry.source for entry in modal._staging_stack.entries()] == [
        "existing",
        "new",
    ]
    assert modal._apply_button.isEnabled() is True

    modal._reset_draft_stack()

    assert modal._staging_stack.entries() == (initial_entry,)
    assert modal._apply_button.isEnabled() is False


def test_cart_modal_search_filters_library_results() -> None:
    """Search should rebuild the library pane without changing the cart."""

    app = _app()
    parent = QWidget()
    parent.resize(1000, 700)
    modal = CubeStackCartModal(
        records=_six_catalog_records(),
        classifications=_six_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=parent,
    )

    assert set(modal._cards) == {
        "image-to-image",
        "inpaint",
        "text-to-image",
        "automask-detailer",
        "diffusion-upscale",
        "promptmask-detailer",
    }

    modal._search.setText("Prompt")
    app.processEvents()

    assert set(modal._cards) == {"promptmask-detailer"}
    assert modal._staging_stack.entries() == ()
    assert modal._search.placeholderText() == "Search cubes"


def test_cart_modal_search_narrows_library_without_suggestion_popup() -> None:
    """Typing in search should narrow the library list without autocomplete state."""

    app = _app()
    parent = QWidget()
    parent.resize(1000, 700)
    parent.show()
    modal = CubeStackCartModal(
        records=_pack_catalog_records(),
        classifications=_pack_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=parent,
    )
    modal.show()
    modal._search.setFocus()
    app.processEvents()

    modal._search.setText("sdxl")
    app.processEvents()

    assert not hasattr(modal, "_search_autocomplete")
    assert set(modal._cards) == {"SDXL/base-start.cube", "SDXL/base-middle.cube"}
    modal.close()
    parent.close()


def test_cart_modal_search_tab_does_not_replace_filter_text() -> None:
    """Tab should leave the active filter text untouched."""

    app = _app()
    parent = QWidget()
    parent.resize(1000, 700)
    parent.show()
    modal = CubeStackCartModal(
        records=_pack_catalog_records(),
        classifications=_pack_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=parent,
    )
    modal.show()
    modal._search.setFocus()
    app.processEvents()

    modal._search.setText("sdxl")
    app.processEvents()
    QTest.keyClick(modal._search, Qt.Key.Key_Tab)
    app.processEvents()

    assert modal._search.text() == "sdxl"
    modal.close()
    parent.close()


def test_cart_modal_search_down_keeps_card_navigation_without_autocomplete() -> None:
    """Down should still move library card selection when suggestions are hidden."""

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
    modal._search.setFocus()
    app.processEvents()
    first_key = modal._selected_card_key

    QTest.keyClick(modal._search, Qt.Key.Key_Down)
    app.processEvents()

    assert modal._selected_card_key != first_key
    modal.close()
    parent.close()


def test_cart_modal_search_filter_refreshes_after_record_replacement() -> None:
    """Replacing records should reapply the active search to visible choices."""

    app = _app()
    parent = QWidget()
    parent.resize(1000, 700)
    parent.show()
    modal = CubeStackCartModal(
        records=_pack_catalog_records(),
        classifications=_pack_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=parent,
    )
    modal.show()
    modal._search.setFocus()
    app.processEvents()
    modal._search.setText("sdxl")
    app.processEvents()

    assert set(modal._cards) == {"SDXL/base-start.cube", "SDXL/base-middle.cube"}

    modal.set_records(
        _six_catalog_records(),
        classifications=_six_catalog_classifications(),
    )
    app.processEvents()

    assert modal._cards == {}
    modal.close()
    parent.close()


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


def test_cart_modal_renders_model_headers_with_role_subsections() -> None:
    """The library should always render model-first, role-second sections."""

    _app()
    modal = CubeStackCartModal(
        records=_pack_catalog_records(),
        classifications=_pack_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )

    label_text = _result_layout_label_texts(modal)

    assert "Flux" in label_text
    assert "SDXL" in label_text
    assert "Unspecified model" in label_text
    assert "Start cubes" in label_text
    assert "Middle cubes" in label_text
    model_headers = modal._results.findChildren(QWidget, "cubePickerModelHeader")
    assert model_headers
    assert all(
        len(header.findChildren(QFrame, "cubePickerModelHeaderRule")) == 2
        for header in model_headers
    )
    assert all(
        label.alignment() & Qt.AlignmentFlag.AlignHCenter
        for header in model_headers
        for label in header.findChildren(QLabel, "cubePickerModelHeaderTitle")
    )


def test_cart_modal_compatibility_model_claims_do_not_create_sections() -> None:
    """A multi-model cube should render only under its owning model folder."""

    _app()
    modal = CubeStackCartModal(
        records=_pack_catalog_records(),
        classifications=_pack_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )

    assert len(modal._cards) == 4
    assert _rendered_cube_ids(modal).count("SDXL/base-start.cube") == 1
    assert _rendered_cube_ids(modal).count("unknown-start") == 1


def test_cart_modal_model_role_card_activation_stages_cube() -> None:
    """Activating a model-role card should stage the underlying cube id."""

    _app()
    modal = CubeStackCartModal(
        records=_pack_catalog_records(),
        classifications=_pack_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )

    modal._cards["SDXL/base-start.cube"].activated.emit("SDXL/base-start.cube")

    assert [entry.cube_id for entry in modal._staging_stack.entries()] == [
        "SDXL/base-start.cube"
    ]


def test_cart_modal_search_rebuilds_model_role_sections_without_changing_cart() -> None:
    """Search should filter nested sections without mutating staged entries."""

    app = _app()
    modal = CubeStackCartModal(
        records=_pack_catalog_records(),
        classifications=_pack_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )

    modal._stage_cube_from_library("SDXL/base-start.cube")
    before = modal._staging_stack.entries()
    modal._search.setText("Local")
    app.processEvents()

    label_text = _result_layout_label_texts(modal)
    assert set(modal._cards) == {"Flux/local-refiner.cube"}
    assert "Flux" in label_text
    assert "Middle cubes" in label_text
    assert "SDXL" not in label_text
    assert "Unspecified model" not in label_text
    assert modal._staging_stack.entries() == before


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


def test_library_click_appends_copy_to_cart_stack() -> None:
    """Clicking a library card should add a new draft copy instead of accepting."""

    _app()
    modal = CubeStackCartModal(
        records=_six_catalog_records(),
        classifications=_six_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )

    modal._cards["inpaint"].activated.emit("inpaint")

    entries = modal._staging_stack.entries()
    assert [entry.cube_id for entry in entries] == ["inpaint"]
    assert entries[0].source == "new"
    assert modal._apply_button.isEnabled() is True


def test_modal_idle_cursor_policy_uses_arrow_for_library_cards() -> None:
    """Idle library cards should keep the normal pointer cursor."""

    _app()
    modal = CubeStackCartModal(
        records=_six_catalog_records(),
        classifications=_six_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )

    cards = list(modal._cards.values())

    assert cards
    assert all(
        card.testAttribute(Qt.WidgetAttribute.WA_SetCursor) is False for card in cards
    )
    assert all(card.cursor().shape() == Qt.CursorShape.ArrowCursor for card in cards)
    assert all(
        modal._idle_cursor_override_mode_for_widget(card) is None for card in cards
    )
    assert all(
        label.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        for card in cards
        for label in card.findChildren(QLabel)
    )


def test_modal_idle_cursor_policy_uses_arrow_for_staged_cards_and_close() -> None:
    """Idle staged cards and close buttons should keep the normal pointer cursor."""

    _app()
    modal = CubeStackCartModal(
        records=_six_catalog_records(),
        classifications=_six_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=_draft_entries(1)),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )
    card = modal._staging_stack.findChildren(QWidget, "cubeStagingCard")[0]
    close_button = getattr(card, "closeButton")

    assert modal._idle_cursor_override_mode_for_widget(card) is None
    assert modal._idle_cursor_override_mode_for_widget(close_button) is None
    assert card.cursor().shape() == Qt.CursorShape.ArrowCursor
    assert close_button.cursor().shape() == Qt.CursorShape.ArrowCursor


def test_library_drag_sets_modal_owned_closed_hand_cursor() -> None:
    """Active library drags should show modal-owned drag cursor feedback."""

    _app()
    _clear_override_cursor()
    try:
        modal = CubeStackCartModal(
            records=_six_catalog_records(),
            classifications=_six_catalog_classifications(),
            initial_draft=CubeStackDraft(entries=()),
            icon_factory=_IconFactory(),
            parent=QWidget(),
        )

        modal._begin_library_drag("inpaint", QPoint(-400, -400))
        cursor = QApplication.overrideCursor()

        assert modal._drag_controller.state is not None
        assert modal._drag_cursor_override_active is True
        assert cursor is not None
        assert cursor.shape() == Qt.CursorShape.ClosedHandCursor
    finally:
        _clear_override_cursor()


def test_library_drag_restores_modal_owned_cursor_on_finish() -> None:
    """Completing a library drag should restore the modal-owned cursor override."""

    _app()
    _clear_override_cursor()
    try:
        modal = CubeStackCartModal(
            records=_six_catalog_records(),
            classifications=_six_catalog_classifications(),
            initial_draft=CubeStackDraft(entries=()),
            icon_factory=_IconFactory(),
            parent=QWidget(),
        )
        modal._begin_library_drag("inpaint", QPoint(-400, -400))

        modal._finish_drag(QPoint(-400, -400))

        assert modal._drag_controller.state is None
        assert modal._drag_cursor_override_active is False
        assert QApplication.overrideCursor() is None
    finally:
        _clear_override_cursor()


def test_staged_drag_restores_modal_owned_cursor_on_reject() -> None:
    """Rejecting the modal during a staged drag should restore cursor feedback."""

    _app()
    _clear_override_cursor()
    try:
        modal = CubeStackCartModal(
            records=[
                CubeCatalogRecord(cube_id="cube-a", version="1.0.0", display_name="A")
            ],
            initial_draft=CubeStackDraft(entries=_draft_entries(1)),
            icon_factory=_IconFactory(),
            parent=QWidget(),
        )
        staged_id = modal._staging_stack.entries()[0].draft_id
        modal._begin_staged_drag(staged_id, QPoint(-400, -400))

        modal.reject()

        assert modal._drag_controller.state is None
        assert modal._drag_cursor_override_active is False
        assert QApplication.overrideCursor() is None
    finally:
        _clear_override_cursor()


def test_staged_drag_release_is_captured_after_source_card_rebuild() -> None:
    """The modal should finish drags even after the source staged card is rebuilt."""

    app = _app()
    modal = CubeStackCartModal(
        records=[
            CubeCatalogRecord(cube_id="cube-a", version="1.0.0", display_name="A")
        ],
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )
    modal._stage_cube_from_library("cube-a")
    staged_id = modal._staging_stack.entries()[0].draft_id

    modal._begin_staged_drag(staged_id, QPoint(-400, -400))
    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(-400, -400),
        QPointF(-400, -400),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    handled = modal.eventFilter(app, release)

    assert handled is True
    assert modal._drag_controller.state is None
    assert modal._drag_event_filter_installed is False
    assert modal._staging_stack.entries() == ()


def test_edit_stack_returns_applied_draft_and_hides_modal() -> None:
    """Applying should return the draft result and close the modal."""

    _app()
    modal = CubeStackCartModal(
        records=[
            CubeCatalogRecord(cube_id="cube-a", version="1.0.0", display_name="A")
        ],
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )
    modal._stage_cube_from_library("cube-a")

    QTimer.singleShot(0, modal.accept)
    result = modal.edit_stack()

    assert result is not None
    assert [entry.cube_id for entry in result.entries] == ["cube-a"]
    assert modal.isHidden()


def test_legacy_staging_drawer_name_uses_cart_modal() -> None:
    """The old public staging name should resolve to the modal implementation."""

    _app()
    picker = CubeStagingDrawer(
        records=[],
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )

    assert isinstance(picker, CubeStackCartModal)


class _IconFactory:
    """Return blank Qt icons for modal tests."""

    def icon_for_cube(
        self,
        *,
        cube_id: str,
        display_name: str,
        icon: object | None,
        catalog_revision: str = "",
        cube_content_hash: str = "",
        render_size: int | None = None,
    ) -> QIcon:
        """Return a blank icon."""

        _ = (
            cube_id,
            display_name,
            icon,
            catalog_revision,
            cube_content_hash,
            render_size,
        )
        return QIcon()


def _six_catalog_records() -> list[CubeCatalogRecord]:
    """Return a representative six-cube catalog for cart modal tests."""

    return [
        CubeCatalogRecord(
            cube_id="image-to-image", version="1.0.0", display_name="Image to Image"
        ),
        CubeCatalogRecord(cube_id="inpaint", version="1.0.0", display_name="Inpaint"),
        CubeCatalogRecord(
            cube_id="text-to-image", version="1.0.0", display_name="Text to Image"
        ),
        CubeCatalogRecord(
            cube_id="automask-detailer",
            version="1.0.0",
            display_name="Automask Detailer",
        ),
        CubeCatalogRecord(
            cube_id="diffusion-upscale",
            version="1.0.0",
            display_name="Diffusion Upscale",
        ),
        CubeCatalogRecord(
            cube_id="promptmask-detailer",
            version="1.0.0",
            display_name="Promptmask Detailer",
        ),
    ]


def _six_catalog_classifications() -> dict[str, CubePickerClassification]:
    """Return start/middle roles for the representative catalog."""

    return {
        "image-to-image": _classification("start", 0, 1),
        "inpaint": _classification("start", 0, 1),
        "text-to-image": _classification("start", 0, 1),
        "automask-detailer": _classification("middle", 1, 1),
        "diffusion-upscale": _classification("middle", 1, 1),
        "promptmask-detailer": _classification("middle", 1, 1),
    }


def _pack_catalog_records() -> list[CubeCatalogRecord]:
    """Return catalog records with varied source packs for view-mode tests."""

    return [
        CubeCatalogRecord(
            cube_id="SDXL/base-start.cube",
            version="1.0.0",
            display_name="Base Start",
            source=_source(repo_ref="Example/Base"),
            supported_models=("SDXL 1.0", "SD 1.5"),
        ),
        CubeCatalogRecord(
            cube_id="SDXL/base-middle.cube",
            version="1.0.0",
            display_name="Base Middle",
            source=_source(repo_ref="Example/Base"),
            supported_models=("SDXL 1.0",),
        ),
        CubeCatalogRecord(
            cube_id="Flux/local-refiner.cube",
            version="1.0.0",
            display_name="Local Refiner",
            source=_source(kind="local"),
            supported_models=("Flux .1 D",),
        ),
        CubeCatalogRecord(
            cube_id="unknown-start",
            version="1.0.0",
            display_name="Unknown Start",
        ),
    ]


def _pack_catalog_classifications() -> dict[str, CubePickerClassification]:
    """Return role classifications for the pack-view fixture."""

    return {
        "SDXL/base-start.cube": _classification("start", 0, 1),
        "SDXL/base-middle.cube": _classification("middle", 1, 1),
        "Flux/local-refiner.cube": _classification("middle", 1, 1),
        "unknown-start": _classification("start", 0, 1),
    }


def _source(
    *,
    kind: str = "github",
    repo_ref: str = "",
) -> CubeSourceMetadata:
    """Return source metadata for modal tests."""

    return CubeSourceMetadata(kind=kind, repo_ref=repo_ref, path="")


def _classification(
    role: CubePickerRole,
    inputs: int,
    outputs: int,
) -> CubePickerClassification:
    """Return one picker role classification."""

    return CubePickerClassification(
        role=role,
        input_count=inputs,
        output_count=outputs,
    )


def _draft_entries(count: int) -> tuple[CubeStackDraftEntry, ...]:
    """Return existing draft entries for representative cart tests."""

    return tuple(
        CubeStackDraftEntry(
            draft_id=f"existing:Cube {index}",
            source="existing",
            cube_id=f"cube-existing-{index}",
            display_name=f"Cube {index}",
            secondary_text="v1.0.0 - base-cubes",
            icon=None,
            existing_alias=f"Cube {index}",
        )
        for index in range(count)
    )


def _visible_label_texts(root: QWidget) -> list[str]:
    """Return non-empty visible label text from one widget subtree."""

    return [
        label.text()
        for label in root.findChildren(QLabel)
        if label.isVisible() and label.text()
    ]


def _all_label_texts(root: QWidget) -> list[str]:
    """Return non-empty label text from one widget subtree."""

    return [label.text() for label in root.findChildren(QLabel) if label.text()]


def _result_layout_label_texts(modal: CubeStackCartModal) -> list[str]:
    """Return non-empty section labels from the active result layout."""

    labels: list[str] = []
    for index in range(modal._results_layout.count()):
        item = modal._results_layout.itemAt(index)
        if item is None:
            continue
        widget = item.widget()
        if isinstance(widget, QLabel) and widget.text():
            labels.append(widget.text())
            continue
        if widget is not None:
            labels.extend(
                label.text() for label in widget.findChildren(QLabel) if label.text()
            )
    return labels


def _rendered_cube_ids(modal: CubeStackCartModal) -> list[str]:
    """Return cube IDs for rendered library cards, including repeated cards."""

    return [card.cube_id for card in modal._cards.values()]


def _clear_override_cursor() -> None:
    """Clear override cursors left by focused cursor-feedback tests."""

    while QApplication.overrideCursor() is not None:
        QApplication.restoreOverrideCursor()
