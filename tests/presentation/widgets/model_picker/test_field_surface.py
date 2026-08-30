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

"""Verify model picker field surface contracts."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import cast


import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget
from qfluentwidgets import EditableComboBox, LineEdit  # type: ignore[import-untyped]

from substitute.application.model_metadata import (
    RichChoiceItem,
)
from substitute.domain.model_metadata import BANNER_THUMBNAIL_ROLE
import substitute.presentation.widgets.model_picker.model_picker_field as model_picker_field_module
from substitute.presentation.widgets.model_picker import (
    ModelPickerField,
)
from substitute.presentation.widgets.model_picker.model_picker_field import (
    _ModelPickerComboSurface,
)
from substitute.presentation.widgets.model_picker.model_picker_models import (
    ModelPickerItem,
)
from tests.support.qt.lifecycle import destroy_qt_object


from tests.presentation.widgets.model_picker.catalog_fixtures import (
    _FakeModelCatalog,
    _FakeStaleChoiceSource,
    _ThumbnailAssetRepository,
    _item,
    _thumbnail_asset,
    _thumbnail_variant,
)
from tests.presentation.widgets.model_picker.support import (
    _default_combo_cap_width,
    _thumbnail_preload_route_factory,
    ensure_qapp,
)


def test_model_picker_combo_surface_paint_event_ends_qpainter() -> None:
    """Closed model picker painting should not leave an active QPainter behind."""

    source = inspect.getsource(_ModelPickerComboSurface.paintEvent)

    assert "finally:" in source
    assert "painter.end()" in source


def test_model_picker_field_returns_backend_value_and_displays_known_label() -> None:
    """The closed field should expose backend values while showing metadata labels."""

    ensure_qapp()
    field = ModelPickerField(
        choice_source=_FakeModelCatalog(
            (_item("models/base.safetensors", "Civit Base", "v2.0"),)
        ),
        current_value="models/base.safetensors",
    )

    assert field.currentText() == "models/base.safetensors"
    assert field.displayText() == "Civit Base - v2.0"
    destroy_qt_object(field)


def test_model_picker_field_defers_popup_item_adaptation_until_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closed field construction should not build popup/media-wall item DTOs."""

    app = ensure_qapp()
    original_builder = cast(
        Callable[[tuple[RichChoiceItem, ...]], tuple[ModelPickerItem, ...]],
        getattr(
            model_picker_field_module,
            "model_picker_items_from_rich_choice_items",
        ),
    )
    build_counts: list[int] = []

    def count_picker_item_builds(
        items: tuple[RichChoiceItem, ...],
    ) -> tuple[ModelPickerItem, ...]:
        """Record lazy popup item materialization before delegating."""

        build_counts.append(len(items))
        return original_builder(items)

    monkeypatch.setattr(
        model_picker_field_module,
        "model_picker_items_from_rich_choice_items",
        count_picker_item_builds,
    )
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (
                _item("models/base.safetensors", "Civit Base", "v2.0"),
                _item("models/refined.safetensors", "Refined", "v2.1"),
            )
        ),
        current_value="models/base.safetensors",
    )
    field.resize(320, 34)
    field.show()
    app.processEvents()

    assert build_counts == []

    field.open_picker()
    app.processEvents()

    assert build_counts == [2]
    destroy_qt_object(host)


def test_model_picker_field_enriches_downloaded_value_absent_from_comfy_choices() -> (
    None
):
    """Downloaded recipe models should display metadata before Comfy refreshes choices."""

    ensure_qapp()
    downloaded = _item(
        "Downloaded/model.safetensors",
        "CivitAI Model",
        "v1",
        thumbnail_variants=(
            _thumbnail_variant("downloaded:banner", role=BANNER_THUMBNAIL_ROLE),
        ),
    )
    field = ModelPickerField(
        choice_source=_FakeStaleChoiceSource(
            choices=(_item("existing.safetensors", "Existing", None),),
            extra=downloaded,
        ),
        thumbnail_asset_repository=_ThumbnailAssetRepository(
            {
                "downloaded:banner": _thumbnail_asset(
                    "downloaded:banner",
                    QColor("#2277cc"),
                )
            }
        ),
        current_value=downloaded.backend_value,
        thumbnail_preload_route_factory=_thumbnail_preload_route_factory(),
    )

    assert field.displayText() == "CivitAI Model - v1"
    assert field._surface._closed_banner_display is not None
    destroy_qt_object(field)


def test_model_picker_field_uses_editable_combo_surface_when_closed() -> None:
    """The closed checkpoint picker should expose combo chrome, not line-edit chrome."""

    app = ensure_qapp()
    field = ModelPickerField(
        choice_source=_FakeModelCatalog(
            (_item("models/base.safetensors", "Civit Base", "v2.0"),)
        ),
        current_value="models/base.safetensors",
    )
    field.show()
    app.processEvents()

    surface = field.findChild(EditableComboBox, "modelPickerComboSurface")

    assert surface is not None
    assert surface.isReadOnly() is True
    assert hasattr(surface, "dropButton")
    assert surface.dropButton.isVisible() is True
    assert surface.text() == "Civit Base - v2.0"
    destroy_qt_object(field)


def test_model_picker_field_reports_wide_row_size_hints() -> None:
    """The model picker should request practical width from row layouts."""

    ensure_qapp()
    field = ModelPickerField(
        choice_source=_FakeModelCatalog(
            (
                _item(
                    "models/long_checkpoint_name.safetensors",
                    "Long Checkpoint Name",
                    "v12",
                ),
            )
        ),
        current_value="models/long_checkpoint_name.safetensors",
    )
    line_edit = LineEdit()
    line_edit.setText(field.displayText())

    assert field.minimumSizeHint().width() >= 208
    assert field.sizeHint().width() >= field.minimumSizeHint().width()
    assert field.sizeHint().width() > line_edit.minimumSizeHint().width()
    destroy_qt_object(line_edit)
    destroy_qt_object(field)


def test_model_picker_field_default_size_hint_respects_combo_cap_for_long_labels() -> (
    None
):
    """Long labels should request useful space without exceeding the row cap."""

    ensure_qapp()
    field = ModelPickerField(
        choice_source=_FakeModelCatalog(
            (
                _item(
                    "models/very_long_checkpoint_name.safetensors",
                    "Very Long Checkpoint Title That Should Occupy Available Row Space",
                    "v123456",
                ),
            )
        ),
        current_value="models/very_long_checkpoint_name.safetensors",
    )

    assert field.minimumSizeHint().width() <= field.sizeHint().width()
    assert field.sizeHint().width() <= _default_combo_cap_width()
    destroy_qt_object(field)


def test_model_picker_field_max_hint_width_only_caps_when_explicit() -> None:
    """Explicit max-hint width should remain available for constrained contexts."""

    ensure_qapp()
    field = ModelPickerField(
        choice_source=_FakeModelCatalog(
            (
                _item(
                    "models/very_long_checkpoint_name.safetensors",
                    "Very Long Checkpoint Title That Should Occupy Available Row Space",
                    "v123456",
                ),
            )
        ),
        current_value="models/very_long_checkpoint_name.safetensors",
    )

    field.setMaxHintWidth(320)

    assert field.sizeHint().width() == 320
    destroy_qt_object(field)


def test_model_picker_field_competes_for_label_row_space_as_wide_field() -> None:
    """A long model field should take row width from the label as a wide field."""

    app = ensure_qapp()
    host = QWidget()
    row_layout = QHBoxLayout(host)
    row_layout.setContentsMargins(10, 0, 10, 0)
    row_layout.setSpacing(6)
    label = QWidget(host)
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (
                _item(
                    "models/very_long_checkpoint_name.safetensors",
                    "Very Long Checkpoint Title That Should Occupy Available Row Space",
                    "v123456",
                ),
            )
        ),
        current_value="models/very_long_checkpoint_name.safetensors",
    )
    field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    row_layout.addWidget(label, 1)
    row_layout.addWidget(field, 0)
    host.resize(900, 40)
    host.show()
    app.processEvents()

    assert field.width() > label.width()
    assert field.width() >= field.sizeHint().width()
    destroy_qt_object(host)


def test_model_picker_field_elides_closed_label_on_right_when_narrow() -> None:
    """Closed labels should keep the title start visible and elide the right edge."""

    app = ensure_qapp()
    full_label = "Very Long Checkpoint Title - v123456"
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (
                _item(
                    "models/very_long_checkpoint_title.safetensors",
                    "Very Long Checkpoint Title",
                    "v123456",
                ),
            )
        ),
        current_value="models/very_long_checkpoint_title.safetensors",
    )
    field.resize(128, 34)
    field.show()
    app.processEvents()

    visible_label = field.displayText()

    assert field.currentText() == "models/very_long_checkpoint_title.safetensors"
    assert visible_label != full_label
    assert visible_label.startswith("Very")
    assert visible_label.endswith("\u2026")
    destroy_qt_object(host)


def test_model_picker_field_restores_full_closed_label_when_wide() -> None:
    """Closed label elision should be recomputed when the combo grows wider."""

    app = ensure_qapp()
    full_label = "Very Long Checkpoint Title - v123456"
    host = QWidget()
    host.resize(900, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (
                _item(
                    "models/very_long_checkpoint_title.safetensors",
                    "Very Long Checkpoint Title",
                    "v123456",
                ),
            )
        ),
        current_value="models/very_long_checkpoint_title.safetensors",
    )
    field.resize(128, 34)
    field.show()
    app.processEvents()
    assert field.displayText().endswith("\u2026")

    field.resize(700, 34)
    app.processEvents()

    assert field.displayText() == full_label
    destroy_qt_object(host)


def test_model_picker_field_set_current_text_preserves_unknown_backend_value() -> None:
    """Unknown values should remain selectable and display a conservative fallback."""

    ensure_qapp()
    field = ModelPickerField(
        choice_source=_FakeModelCatalog(()),
    )
    changed: list[str] = []
    field.currentTextChanged.connect(changed.append)

    field.setCurrentText(r"old\missing.ckpt")

    assert field.currentText() == r"old\missing.ckpt"
    assert field.displayText() == "missing"
    assert changed == [r"old\missing.ckpt"]
    destroy_qt_object(field)
