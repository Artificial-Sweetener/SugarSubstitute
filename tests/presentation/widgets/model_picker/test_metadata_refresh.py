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

"""Verify model picker metadata refresh contracts."""

from __future__ import annotations

from typing import Any, cast


from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.domain.model_metadata import BANNER_THUMBNAIL_ROLE
from substitute.presentation.widgets.model_picker import (
    ModelPickerField,
)
from substitute.presentation.widgets.model_picker.model_picker_field import (
    _ModelPickerComboSurface,
)
from tests.support.qt.lifecycle import destroy_qt_object


from tests.presentation.widgets.model_picker.catalog_fixtures import (
    _ClearRecorder,
    _FakeModelCatalog,
    _ThumbnailAssetRepository,
    _item,
    _metadata_event,
    _thumbnail_variant,
)
from tests.presentation.widgets.model_picker.support import (
    _thumbnail_preload_route_factory,
    ensure_qapp,
)


def test_model_picker_field_refresh_metadata_updates_open_popup_items() -> None:
    """Live metadata refresh should replace open popup rows without closing it."""

    app = ensure_qapp()
    catalog = _FakeModelCatalog((_item("models/base.safetensors", "Base", "v1"),))
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=catalog,
        current_value="models/base.safetensors",
    )
    field.resize(320, 34)
    field.show()
    field.open_picker()
    app.processEvents()
    popup = field._popup
    assert popup is not None
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    assert surface is not None
    QTest.keyClicks(surface, "refined")
    app.processEvents()
    catalog.items = (_item("models/refined.safetensors", "Refined", "v2"),)

    field.refresh_metadata()
    app.processEvents()

    current_item = popup.current_item()
    assert popup.isVisible() is True
    assert popup.search_text() == "refined"
    assert surface.text() == "refined"
    assert field.currentText() == "models/base.safetensors"
    assert current_item is not None
    assert current_item.title == "Refined"
    assert catalog.refresh_calls == ["checkpoints", "checkpoints"]
    destroy_qt_object(host)


def test_model_picker_field_reconciles_new_choice_source_without_ui_reset() -> None:
    """Live option replacement should preserve popup, search, focus, and signals."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(()),
        current_value="",
    )
    field.resize(320, 34)
    field.show()
    changed: list[str] = []
    field.currentTextChanged.connect(changed.append)
    field.open_picker()
    app.processEvents()
    popup = field._popup
    assert popup is not None
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    assert surface is not None
    QTest.keyClicks(surface, "only")
    app.processEvents()
    assert surface.search_focus_active() is True

    field.reconcile_choice_source(
        _FakeModelCatalog((_item("models/only.safetensors", "Only Model", "v1"),)),
        "models/only.safetensors",
    )
    app.processEvents()

    assert field._popup is popup
    assert popup.isVisible() is True
    assert popup.search_text() == "only"
    assert surface.text() == "only"
    assert surface.search_focus_active() is True
    assert field.currentText() == "models/only.safetensors"
    assert [item.title for item in popup._view.items()] == ["Only Model"]
    assert changed == []
    destroy_qt_object(host)


def test_model_picker_field_event_refresh_updates_matching_closed_value() -> None:
    """Closed fields should refresh when metadata updates the shown backend value."""

    ensure_qapp()
    value = "Illustrious\\model.safetensors"
    catalog = _FakeModelCatalog((_item(value, "Old Label", "v1"),))
    field = ModelPickerField(choice_source=catalog, current_value=value)
    catalog.items = (_item(value, "New Label", "v2"),)

    refreshed = field.refresh_metadata_for_event(_metadata_event("checkpoints", value))

    assert refreshed is True
    assert field.displayText() == "New Label - v2"
    assert catalog.refresh_calls == ["checkpoints"]
    destroy_qt_object(field)


def test_model_picker_field_thumbnail_event_clears_matching_cache() -> None:
    """Thumbnail events should clear picker pixmaps for matching loaded metadata."""

    ensure_qapp()
    value = "Illustrious\\model.safetensors"
    catalog = _FakeModelCatalog((_item(value, "Base", "v1"),))
    field = ModelPickerField(choice_source=catalog, current_value=value)
    cache = _ClearRecorder()
    cast(Any, field)._thumbnail_cache = cache

    cleared = field.clear_thumbnail_cache_for_event(
        _metadata_event("checkpoints", value)
    )

    assert cleared is True
    assert cache.calls == 1
    destroy_qt_object(field)


def test_model_picker_field_metadata_event_preserves_thumbnail_cache() -> None:
    """Metadata-only events should not clear picker thumbnail pixmaps."""

    ensure_qapp()
    value = "Illustrious\\model.safetensors"
    catalog = _FakeModelCatalog((_item(value, "Base", "v1"),))
    field = ModelPickerField(choice_source=catalog, current_value=value)
    cache = _ClearRecorder()
    cast(Any, field)._thumbnail_cache = cache

    cleared = field.clear_thumbnail_cache_for_event(
        _metadata_event("checkpoints", value, thumbnail_updated=False)
    )

    assert cleared is False
    assert cache.calls == 0
    destroy_qt_object(field)


def test_model_picker_field_event_refresh_defers_unrelated_closed_value() -> None:
    """Closed fields should avoid catalog reloads for unrelated metadata events."""

    ensure_qapp()
    value = "models/base.safetensors"
    catalog = _FakeModelCatalog((_item(value, "Base", "v1"),))
    field = ModelPickerField(choice_source=catalog, current_value=value)
    catalog.items = (_item(value, "Base Updated", "v2"),)

    refreshed = field.refresh_metadata_for_event(
        _metadata_event("checkpoints", "models/other.safetensors")
    )

    assert refreshed is False
    assert field.displayText() == "Base - v1"
    assert catalog.refresh_calls == []
    destroy_qt_object(field)


def test_model_picker_field_event_refresh_catches_up_visible_closed_value() -> None:
    """Visible closed fields should refresh on same-kind metadata catch-up events."""

    app = ensure_qapp()
    value = "models/base.safetensors"
    host = QWidget()
    host.resize(640, 480)
    host.show()
    catalog = _FakeModelCatalog((_item(value, "Base", "v1"),))
    field = ModelPickerField(
        host,
        choice_source=catalog,
        current_value=value,
        thumbnail_asset_repository=_ThumbnailAssetRepository({}),
        thumbnail_preload_route_factory=_thumbnail_preload_route_factory(),
    )
    field.resize(320, 34)
    field.show()
    app.processEvents()
    catalog.items = (
        _item(
            value,
            "Base Updated",
            "v2",
            thumbnail_variants=(
                _thumbnail_variant("base-banner", role=BANNER_THUMBNAIL_ROLE),
            ),
        ),
    )

    refreshed = field.refresh_metadata_for_event(
        _metadata_event("checkpoints", "models/other.safetensors")
    )

    assert refreshed is True
    assert field.displayText() == "Base Updated - v2"
    assert field._surface._closed_banner_display is not None
    assert catalog.refresh_calls == ["checkpoints"]
    destroy_qt_object(host)


def test_model_picker_field_event_refresh_updates_open_popup_items() -> None:
    """Open popups should refresh list rows for same-kind metadata events."""

    app = ensure_qapp()
    catalog = _FakeModelCatalog((_item("models/base.safetensors", "Base", "v1"),))
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=catalog,
        current_value="models/base.safetensors",
    )
    field.resize(320, 34)
    field.show()
    field.open_picker()
    app.processEvents()
    popup = field._popup
    assert popup is not None
    popup.set_search_text("refined")
    catalog.items = (_item("models/refined.safetensors", "Refined", "v2"),)

    refreshed = field.refresh_metadata_for_event(
        _metadata_event("checkpoints", "models/other.safetensors")
    )
    app.processEvents()

    current_item = popup.current_item()
    assert refreshed is True
    assert popup.isVisible() is True
    assert popup.search_text() == "refined"
    assert current_item is not None
    assert current_item.title == "Refined"
    assert catalog.refresh_calls == ["checkpoints", "checkpoints"]
    destroy_qt_object(host)


def test_model_picker_field_event_refresh_skips_loaded_unrelated_kind() -> None:
    """Loaded picker kind metadata should prevent unrelated event refreshes."""

    ensure_qapp()
    value = "models/base.safetensors"
    catalog = _FakeModelCatalog((_item(value, "Base", "v1"),))
    field = ModelPickerField(choice_source=catalog, current_value=value)
    catalog.items = (_item(value, "Base Updated", "v2"),)

    refreshed = field.refresh_metadata_for_event(_metadata_event("loras", value))

    assert refreshed is False
    assert field.displayText() == "Base - v1"
    assert catalog.refresh_calls == []
    destroy_qt_object(field)
