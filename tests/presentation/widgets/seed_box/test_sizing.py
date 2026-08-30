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

"""Verify seed control and numeric-factory sizing contracts."""

from __future__ import annotations

from PySide6.QtWidgets import QSizePolicy, QWidget

from substitute.domain.node_behavior import FieldPresentation
from substitute.presentation.editor.panel.factories.numeric_factory import (
    widget_factory_seedbox,
)
from substitute.presentation.widgets.combo_box import ComboBox
from substitute.presentation.widgets.seed_box import SeedBox
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_height_matches_searchable_combo_box() -> None:
    """Seed surfaces should align vertically with searchable combo fields."""

    ensure_qt_application()
    combo = ComboBox()
    seed = SeedBox()

    assert seed.height() == combo.height()
    assert seed.line_edit.height() == combo.height()
    assert seed.split_button.height() == combo.height()
    destroy_qt_object(combo)
    destroy_qt_object(seed)


def test_width_policy_matches_shrinkable_combo_contract() -> None:
    """Seed preference should remain stable without imposing a minimum width."""

    ensure_qt_application()
    combo = ComboBox()
    seed = SeedBox()

    assert (
        seed.sizePolicy().horizontalPolicy()
        == (combo.sizePolicy().horizontalPolicy())
        == QSizePolicy.Policy.Maximum
    )
    assert (
        seed.sizePolicy().verticalPolicy()
        == (combo.sizePolicy().verticalPolicy())
        == QSizePolicy.Policy.Fixed
    )
    assert seed.minimumWidth() == 0
    assert seed.maximumWidth() >= seed.sizeHint().width()
    assert seed.sizeHint().width() > seed.minimumSizeHint().width()
    assert seed.minimumSizeHint().width() == combo.minimumSizeHint().width()
    destroy_qt_object(combo)
    destroy_qt_object(seed)


def test_children_follow_constrained_control_width() -> None:
    """The overlaid line edit and split button should follow narrow allocation."""

    ensure_qt_application()
    seed = SeedBox()
    constrained_width = seed.minimumSizeHint().width()

    seed.resize(constrained_width, seed.height())
    seed.show()
    wait_for_qt_condition(lambda: seed.line_edit.width() == constrained_width)

    assert seed.width() == constrained_width
    assert seed.line_edit.width() == constrained_width
    assert seed.split_button.x() == constrained_width - seed.split_button.width()
    destroy_qt_object(seed)


def test_numeric_factory_does_not_force_node_card_minimum_width() -> None:
    """Factory-created seed fields should remain shrinkable in node rows."""

    ensure_qt_application()
    parent = QWidget()
    field = widget_factory_seedbox(
        parent,
        "ksampler",
        "seed",
        123,
        {},
        field_type="INT",
        field_presentation=FieldPresentation.SEED_BOX,
        constraints={"min": 0, "max": 999, "step": 1},
    )

    assert isinstance(field, SeedBox)
    assert field.minimumWidth() == 0
    assert field.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Maximum
    destroy_qt_object(parent)
