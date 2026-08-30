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

"""Verify card-scoped model-picker width synchronization."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QEvent, QPoint
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import ComboBox  # type: ignore[import-untyped]

import substitute.presentation.editor.panel.widgets.node_card as node_card_view
from substitute.application.model_metadata import (
    ModelCatalogItem,
    RichChoiceItem,
    RichChoiceResolution,
)
from substitute.presentation.widgets.model_picker import ModelPickerField
from tests.presentation.editor.node_card.support import ensure_qapp
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition

_QT_WIDGET_MAXIMUM_SIZE = 16_777_215


class _ModelChoiceSource:
    """Return one deterministic enriched model row."""

    def current_resolution(self) -> RichChoiceResolution:
        """Return the current one-row resolution."""

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
        """Return the same deterministic resolution on refresh."""

        return self.current_resolution()


def test_same_card_pickers_share_narrowest_width() -> None:
    """Cap visible pickers on one card to the narrowest available width."""

    card, fields = _card_with_model_pickers(width=620, label_widths=(60, 220, 120))
    try:
        _request_width_sync(card)
        widths = {field.width() for field in fields}
        assert len(widths) == 1
        assert next(iter(widths)) == min(field.maximumWidth() for field in fields)
    finally:
        destroy_qt_object(card)


def test_capped_pickers_remain_right_aligned_after_layout_requests() -> None:
    """Keep capped pickers aligned when repeated layout requests arrive."""

    card, fields = _card_with_model_pickers(width=620, label_widths=(60, 220, 120))
    try:
        _request_width_sync(card)
        assert _field_positions(card, fields) == [220, 220, 220]

        for _ in range(3):
            ensure_qapp().postEvent(card, QEvent(QEvent.Type.LayoutRequest))
        _request_width_sync(card)

        assert _field_positions(card, fields) == [220] * 3
        assert {field.width() for field in fields} == {400}
    finally:
        destroy_qt_object(card)


def test_width_group_grows_when_card_widens() -> None:
    """Release old caps so grouped pickers can grow with their card."""

    card, fields = _card_with_model_pickers(width=500, label_widths=(80, 220))
    try:
        _request_width_sync(card)
        narrow_width = fields[0].width()
        card.resize(700, 120)
        _request_width_sync(card)

        assert {field.width() for field in fields} == {fields[0].width()}
        assert fields[0].width() > narrow_width
    finally:
        destroy_qt_object(card)


def test_width_groups_do_not_cross_cards() -> None:
    """Keep shared picker caps scoped to one node-card surface."""

    first_card, first_fields = _card_with_model_pickers(
        width=520,
        label_widths=(180, 260),
    )
    second_card, second_fields = _card_with_model_pickers(
        width=680,
        label_widths=(60, 100),
    )
    try:
        _request_width_sync(first_card)
        _request_width_sync(second_card)
        first_widths = {field.width() for field in first_fields}
        second_widths = {field.width() for field in second_fields}

        assert len(first_widths) == 1
        assert len(second_widths) == 1
        assert next(iter(second_widths)) > next(iter(first_widths))
    finally:
        destroy_qt_object(first_card)
        destroy_qt_object(second_card)


def test_single_picker_is_not_capped() -> None:
    """Leave a lone model picker free of an artificial group cap."""

    card, (field,) = _card_with_model_pickers(width=620, label_widths=(80,))
    try:
        _request_width_sync(card)
        assert field.maximumWidth() == _QT_WIDGET_MAXIMUM_SIZE
    finally:
        destroy_qt_object(card)


def test_width_group_ignores_ordinary_combos() -> None:
    """Exclude ordinary combo boxes from model-picker width caps."""

    ensure_qapp()
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
    try:
        _request_width_sync(card)
        assert first_picker.width() == second_picker.width()
        assert combo.maximumWidth() == _QT_WIDGET_MAXIMUM_SIZE
    finally:
        destroy_qt_object(card)


def _model_catalog_item() -> ModelCatalogItem:
    """Return one model catalog item for rich picker fields."""

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
    """Return one expanding model picker field."""

    field = ModelPickerField(
        parent,
        choice_source=_ModelChoiceSource(),
        current_value="models/base.safetensors",
    )
    field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return field


def _node_card_surface() -> QWidget:
    """Return the node-card surface that owns width synchronization."""

    surface_type = cast(type[QWidget], getattr(node_card_view, "_NodeCardSurface"))
    return surface_type()


def _row_with_field(card: QWidget, *, label_width: int, field: QWidget) -> QWidget:
    """Return one row whose label width constrains its field."""

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
    """Return one shown node card containing model-picker rows."""

    ensure_qapp()
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


def _request_width_sync(card: QWidget) -> None:
    """Request production synchronization and wait for its queued completion."""

    defer_sync = cast(
        Callable[[], None],
        getattr(card, "defer_model_picker_width_group_sync"),
    )
    defer_sync()
    wait_for_qt_condition(
        lambda: (
            card.isVisible()
            and not bool(getattr(card, "_model_picker_width_sync_pending"))
        )
    )


def _field_positions(
    card: QWidget,
    fields: tuple[ModelPickerField, ...],
) -> list[int]:
    """Return field left edges in card coordinates."""

    return [field.mapTo(card, QPoint(0, 0)).x() for field in fields]
