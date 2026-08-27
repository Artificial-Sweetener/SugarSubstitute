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

"""Verify model picker banner rendering contracts."""

from __future__ import annotations


from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget
from qfluentwidgets import Theme  # type: ignore[import-untyped]

from substitute.domain.model_metadata import BANNER_THUMBNAIL_ROLE
from substitute.presentation.widgets.model_picker import (
    ModelPickerField,
)
from substitute.presentation.widgets.model_picker.model_picker_field import (
    _ModelPickerComboSurface,
)
from tests.support.qt.lifecycle import destroy_qt_object
from tests.presentation.theme.support import fluent_theme


from tests.presentation.widgets.model_picker.catalog_fixtures import (
    _FakeModelCatalog,
    _ThumbnailAssetRepository,
    _item,
    _thumbnail_asset,
    _thumbnail_variant,
)
from tests.presentation.widgets.model_picker.support import (
    _render_surface,
    _thumbnail_preload_route_factory,
    _wait_for_thumbnail_preloader_idle,
    ensure_qapp,
)


def test_model_picker_field_closed_state_paints_selected_banner() -> None:
    """Closed checkpoint fields should opt into banner decoration when available."""

    with fluent_theme(Theme.DARK):
        app = ensure_qapp()
        banner_asset = _thumbnail_asset("alpha:banner", QColor("#2868d8"))
        repository = _ThumbnailAssetRepository({"alpha:banner": banner_asset})
        host = QWidget()
        host.resize(640, 480)
        host.show()
        field = ModelPickerField(
            host,
            choice_source=_FakeModelCatalog(
                (
                    _item(
                        "models/alpha.safetensors",
                        "Alpha Model",
                        "v1",
                        thumbnail_variants=(
                            _thumbnail_variant(
                                "alpha:banner",
                                role=BANNER_THUMBNAIL_ROLE,
                            ),
                        ),
                    ),
                )
            ),
            thumbnail_asset_repository=repository,
            current_value="models/alpha.safetensors",
            thumbnail_preload_route_factory=_thumbnail_preload_route_factory(),
        )
        field.resize(420, 34)
        field.show()
        app.processEvents()
        assert field._thumbnail_preloader is not None
        assert _wait_for_thumbnail_preloader_idle(field._thumbnail_preloader, 1000)
        surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
        assert surface is not None

        reads_before_render = dict(repository.reads_by_key)
        image = _render_surface(surface, fill=QColor("#202020"))
        edge_pixel = image.pixelColor(0, surface.height() // 2)
        inner_pixel = image.pixelColor(2, surface.height() // 2)

        assert repository.reads_by_key == {"alpha:banner": 1}
        assert repository.reads_by_key == reads_before_render
        assert surface._should_paint_closed_banner_decoration() is True
        assert surface._drop_button_icon_suppressed is True
        assert inner_pixel.blue() > edge_pixel.blue() + 50
        assert field.currentText() == "models/alpha.safetensors"
        destroy_qt_object(host)


def test_model_picker_field_closed_state_falls_back_without_banner() -> None:
    """Missing banner data should keep the existing plain closed combo label."""

    app = ensure_qapp()
    repository = _ThumbnailAssetRepository({})
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (_item("models/alpha.safetensors", "Alpha Model", "v1"),)
        ),
        thumbnail_asset_repository=repository,
        current_value="models/alpha.safetensors",
        thumbnail_preload_route_factory=_thumbnail_preload_route_factory(),
    )
    field.resize(420, 34)
    field.show()
    app.processEvents()
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    assert surface is not None

    _render_surface(surface)

    assert repository.reads_by_key == {}
    assert surface._should_paint_closed_banner_decoration() is False
    assert field.displayText() == "Alpha Model - v1"
    destroy_qt_object(host)


def test_model_picker_field_search_mode_suppresses_closed_banner() -> None:
    """Open search mode should keep banner decoration out of the text editor."""

    app = ensure_qapp()
    banner_asset = _thumbnail_asset("alpha:banner", QColor("#2868d8"))
    repository = _ThumbnailAssetRepository({"alpha:banner": banner_asset})
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (
                _item(
                    "models/alpha.safetensors",
                    "Alpha Model",
                    "v1",
                    thumbnail_variants=(
                        _thumbnail_variant("alpha:banner", role=BANNER_THUMBNAIL_ROLE),
                    ),
                ),
            )
        ),
        thumbnail_asset_repository=repository,
        current_value="models/alpha.safetensors",
        thumbnail_preload_route_factory=_thumbnail_preload_route_factory(),
    )
    field.resize(260, 34)
    field.show()
    app.processEvents()
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    assert surface is not None

    field.open_picker()
    app.processEvents()

    assert surface.isReadOnly() is False
    assert surface._should_paint_closed_banner_decoration() is False
    assert surface.search_focus_active() is True
    destroy_qt_object(host)


def test_model_picker_field_selection_updates_closed_banner_display() -> None:
    """Selecting a new checkpoint should update the closed banner decoration."""

    app = ensure_qapp()
    alpha_asset = _thumbnail_asset("alpha:banner", QColor("#2868d8"))
    beta_asset = _thumbnail_asset("beta:banner", QColor("#d82868"))
    repository = _ThumbnailAssetRepository(
        {
            "alpha:banner": alpha_asset,
            "beta:banner": beta_asset,
        }
    )
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (
                _item(
                    "models/alpha.safetensors",
                    "Alpha Model",
                    "v1",
                    thumbnail_variants=(
                        _thumbnail_variant("alpha:banner", role=BANNER_THUMBNAIL_ROLE),
                    ),
                ),
                _item(
                    "models/beta.safetensors",
                    "Beta Model",
                    "v2",
                    thumbnail_variants=(
                        _thumbnail_variant("beta:banner", role=BANNER_THUMBNAIL_ROLE),
                    ),
                ),
            )
        ),
        thumbnail_asset_repository=repository,
        current_value="models/alpha.safetensors",
        thumbnail_preload_route_factory=_thumbnail_preload_route_factory(),
    )
    field.resize(260, 34)
    field.show()
    field.open_picker()
    app.processEvents()
    assert field._thumbnail_preloader is not None
    assert _wait_for_thumbnail_preloader_idle(field._thumbnail_preloader, 1000)
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    assert surface is not None

    QTest.keyClicks(surface, "beta")
    app.processEvents()
    QTest.keyClick(surface, Qt.Key.Key_Return)
    app.processEvents()
    assert _wait_for_thumbnail_preloader_idle(field._thumbnail_preloader, 1000)
    reads_before_render = dict(repository.reads_by_key)
    _render_surface(surface)

    assert field.currentText() == "models/beta.safetensors"
    assert field.displayText() == "Beta Model - v2"
    assert repository.reads_by_key == reads_before_render
    assert repository.reads_by_key["beta:banner"] == 1
    destroy_qt_object(host)


def test_model_picker_field_banner_chevron_uses_shadowed_parent_paint() -> None:
    """The visible banner chevron should use the shared text-shadow treatment."""

    app = ensure_qapp()
    banner_asset = _thumbnail_asset("alpha:banner", QColor("#ffffff"))
    repository = _ThumbnailAssetRepository({"alpha:banner": banner_asset})
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (
                _item(
                    "models/alpha.safetensors",
                    "Alpha Model",
                    "v1",
                    thumbnail_variants=(
                        _thumbnail_variant("alpha:banner", role=BANNER_THUMBNAIL_ROLE),
                    ),
                ),
            )
        ),
        thumbnail_asset_repository=repository,
        current_value="models/alpha.safetensors",
        thumbnail_preload_route_factory=_thumbnail_preload_route_factory(),
    )
    field.resize(240, 34)
    field.show()
    app.processEvents()
    assert field._thumbnail_preloader is not None
    assert _wait_for_thumbnail_preloader_idle(field._thumbnail_preloader, 1000)
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    assert surface is not None

    image = _render_surface(surface, fill=QColor("#202020"))
    icon_rect = surface._drop_button_icon_rect().adjusted(-3.0, -3.0, 3.0, 3.0)
    icon_pixels = [
        image.pixelColor(x, y)
        for x in range(
            max(0, int(icon_rect.left())),
            min(image.width(), int(icon_rect.right()) + 1),
        )
        for y in range(
            max(0, int(icon_rect.top())),
            min(image.height(), int(icon_rect.bottom()) + 1),
        )
    ]

    assert surface._drop_button_icon_suppressed is True
    assert any(pixel.lightness() < 80 and pixel.alpha() > 180 for pixel in icon_pixels)
    assert any(pixel.lightness() > 210 and pixel.alpha() > 180 for pixel in icon_pixels)
    destroy_qt_object(host)
