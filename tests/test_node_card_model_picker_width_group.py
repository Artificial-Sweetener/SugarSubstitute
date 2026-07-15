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

"""Regression tests for card-scoped model picker width grouping."""

from __future__ import annotations

import os
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import ComboBox  # type: ignore[import-untyped]

import substitute.presentation.editor.panel.widgets.node_card as node_card_view
from substitute.application.model_metadata import (
    ModelCatalogItem,
    RichChoiceItem,
    RichChoiceResolution,
)
from substitute.presentation.widgets.model_picker import ModelPickerField

_QT_WIDGET_MAXIMUM_SIZE = 16_777_215


class _FakeModelChoiceSource:
    """Return deterministic rich-choice rows for model picker layout tests."""

    def current_resolution(self) -> RichChoiceResolution:
        """Return one enriched model row."""

        item = _model_catalog_item()
        rich_item = RichChoiceItem(
            value=item.backend_value,
            title=item.display_name,
            subtitle=item.display_subtitle,
            search_text=item.search_text,
            model_kind=item.kind,
            catalog_item=item,
            thumbnail_variants=item.thumbnail_variants,
            is_enriched=True,
            is_ambiguous=False,
        )
        return RichChoiceResolution(
            items=(rich_item,),
            should_use_rich_picker=True,
            matched_kinds=(item.kind,),
            option_count=1,
            enriched_count=1,
            ambiguous_count=0,
            unmatched_count=0,
            reason="test fixture",
        )

    def refresh(self) -> RichChoiceResolution:
        """Return the current deterministic resolution for refresh requests."""

        return self.current_resolution()


def _ensure_qapp() -> QApplication:
    """Return the shared QApplication used by node-card model picker tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _process_events(app: QApplication, *, cycles: int = 8) -> None:
    """Process deferred card width sync and resulting layout requests."""

    for _ in range(cycles):
        app.processEvents()


def _model_catalog_item() -> ModelCatalogItem:
    """Return one fake model catalog item for rich picker fields."""

    return ModelCatalogItem(
        kind="checkpoints",
        backend_value="models/base.safetensors",
        display_name="Base Model",
        display_subtitle="v1",
        relative_path="models/base.safetensors",
        folder="models",
        basename="base.safetensors",
        extension=".safetensors",
        thumbnail_variants=(),
        base_model=None,
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key="base",
        collision_count=1,
        has_collision=False,
        search_text="base model v1",
    )


def _model_picker(parent: QWidget) -> ModelPickerField:
    """Return one expanding model picker field for card layout tests."""

    field = ModelPickerField(
        parent,
        choice_source=_FakeModelChoiceSource(),
        current_value="models/base.safetensors",
    )
    field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return field


def _node_card_surface() -> QWidget:
    """Return the private node-card surface used as the width-sync owner."""

    surface_type = cast(type[QWidget], getattr(node_card_view, "_NodeCardSurface"))
    return surface_type()


def _row_with_field(
    card: QWidget,
    *,
    label_width: int,
    field: QWidget,
) -> QWidget:
    """Return one row whose label width changes the field's natural width."""

    row = QWidget(card)
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(0)
    label = QWidget(row)
    label.setFixedWidth(label_width)
    row_layout.addWidget(label, 0)
    row_layout.addWidget(field, 1)
    return row


def _card_with_model_pickers(
    *,
    width: int,
    label_widths: tuple[int, ...],
) -> tuple[QWidget, tuple[ModelPickerField, ...]]:
    """Return one shown node card with model picker rows."""

    card = _node_card_surface()
    layout = QVBoxLayout(card)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    fields: list[ModelPickerField] = []
    for label_width in label_widths:
        field = _model_picker(card)
        fields.append(field)
        layout.addWidget(_row_with_field(card, label_width=label_width, field=field))
    card.resize(width, 120)
    card.show()
    return card, tuple(fields)


def test_model_pickers_on_same_node_card_share_thinnest_width() -> None:
    """Visible model pickers on one node card should share the narrowest width."""

    app = _ensure_qapp()
    card, fields = _card_with_model_pickers(width=620, label_widths=(60, 220, 120))
    _process_events(app)

    widths = {field.width() for field in fields}

    assert len(widths) == 1
    assert next(iter(widths)) == min(field.maximumWidth() for field in fields)
    card.deleteLater()


def test_capped_model_pickers_stay_right_aligned_after_layout_requests() -> None:
    """Repeated layout requests should not shift right-aligned capped pickers."""

    app = _ensure_qapp()
    card, fields = _card_with_model_pickers(width=620, label_widths=(60, 220, 120))
    _process_events(app)
    initial_positions = [field.mapTo(card, QPoint(0, 0)).x() for field in fields]
    assert initial_positions == [220, 220, 220]

    for _ in range(3):
        app.postEvent(card, QEvent(QEvent.Type.LayoutRequest))
        _process_events(app, cycles=3)

    assert [field.mapTo(card, QPoint(0, 0)).x() for field in fields] == [220] * 3
    assert {field.width() for field in fields} == {400}
    card.deleteLater()


def test_model_picker_width_group_grows_when_node_card_widens() -> None:
    """Released max-width caps should let grouped model pickers grow together."""

    app = _ensure_qapp()
    card, fields = _card_with_model_pickers(width=500, label_widths=(80, 220))
    _process_events(app)
    narrow_width = fields[0].width()

    card.resize(700, 120)
    _process_events(app)

    assert {field.width() for field in fields} == {fields[0].width()}
    assert fields[0].width() > narrow_width
    card.deleteLater()


def test_model_picker_width_groups_do_not_cross_node_cards() -> None:
    """Model picker width caps should be isolated to one node card."""

    app = _ensure_qapp()
    first_card, first_fields = _card_with_model_pickers(
        width=520,
        label_widths=(180, 260),
    )
    second_card, second_fields = _card_with_model_pickers(
        width=680,
        label_widths=(60, 100),
    )
    _process_events(app)

    first_widths = {field.width() for field in first_fields}
    second_widths = {field.width() for field in second_fields}

    assert len(first_widths) == 1
    assert len(second_widths) == 1
    assert next(iter(second_widths)) > next(iter(first_widths))
    first_card.deleteLater()
    second_card.deleteLater()


def test_single_model_picker_node_card_is_not_capped() -> None:
    """A lone model picker should not receive an artificial shared max width."""

    app = _ensure_qapp()
    card, (field,) = _card_with_model_pickers(width=620, label_widths=(80,))
    _process_events(app)

    assert field.maximumWidth() == _QT_WIDGET_MAXIMUM_SIZE
    card.deleteLater()


def test_model_picker_width_group_ignores_ordinary_combos() -> None:
    """Ordinary combo boxes should not participate in model picker width caps."""

    app = _ensure_qapp()
    card = _node_card_surface()
    layout = QVBoxLayout(card)
    layout.setContentsMargins(0, 0, 0, 0)
    first_picker = _model_picker(card)
    second_picker = _model_picker(card)
    combo = ComboBox(card)
    combo.addItem("ordinary")
    combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    layout.addWidget(_row_with_field(card, label_width=60, field=first_picker))
    layout.addWidget(_row_with_field(card, label_width=220, field=second_picker))
    layout.addWidget(_row_with_field(card, label_width=40, field=combo))
    card.resize(620, 120)
    card.show()
    _process_events(app)

    assert first_picker.width() == second_picker.width()
    assert combo.maximumWidth() == _QT_WIDGET_MAXIMUM_SIZE
    card.deleteLater()
