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

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFrame, QLabel, QWidget

from substitute.application.cubes import (
    CubeStackDraft,
)
from substitute.presentation.cube_picker.cube_stack_cart_modal import (
    CubeStackCartModal,
)


from tests.presentation.cube_picker.cart_modal.support import (
    _IconFactory,
    _app,
    _pack_catalog_classifications,
    _pack_catalog_records,
    _rendered_cube_ids,
    _result_layout_label_texts,
    _six_catalog_classifications,
    _six_catalog_records,
)


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
