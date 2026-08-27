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

"""Mount and observe model picker widgets through deterministic boundaries."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast


from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.model_metadata import (
    ModelCatalogItem,
)
from substitute.presentation.widgets.model_picker import (
    ModelPickerField,
    ModelPickerThumbnailPreloadRoute,
)
from substitute.presentation.widgets.model_picker.model_picker_field import (
    _ModelPickerComboSurface,
)
from tests.support.execution import ImmediateTaskSubmitter
from tests.support.qt.semantic_wait import wait_for_qt_condition


from tests.presentation.widgets.model_picker.catalog_fixtures import (
    _FakeModelCatalog,
)


def ensure_qapp() -> QApplication:
    """Return a running Qt application for picker field tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _wait_for_thumbnail_preloader_idle(
    preloader: object,
    timeout_ms: int,
) -> bool:
    """Wait for one thumbnail preloader's authoritative pending state to clear."""

    if not hasattr(preloader, "has_pending_work"):
        raise TypeError("preloader must expose has_pending_work().")
    wait_for_qt_condition(
        lambda: not bool(preloader.has_pending_work()),
        timeout_ms=timeout_ms,
    )
    return True


def _thumbnail_preload_route_factory() -> Callable[
    [QWidget], ModelPickerThumbnailPreloadRoute
]:
    """Return an immediate thumbnail preload route factory for widget tests."""

    def _factory(_receiver: QWidget) -> ModelPickerThumbnailPreloadRoute:
        """Create one immediate route for a constructed model picker."""

        return ModelPickerThumbnailPreloadRoute(
            submitter=ImmediateTaskSubmitter(),
            close=lambda: None,
        )

    return _factory


def _default_combo_cap_width() -> int:
    """Return the default preferred-width cap for model picker rows."""

    return 520


def _right_click_closed_picker_surface(surface: _ModelPickerComboSurface) -> None:
    """Deliver a deterministic right-button press to a closed picker surface."""

    position = QPoint(12, 12)
    surface.mousePressEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(position),
            QPointF(surface.mapToGlobal(position)),
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )


def _open_picker_surface(
    items: tuple[ModelCatalogItem, ...],
    *,
    current_value: str,
    extra_items: tuple[ModelCatalogItem, ...] = (),
) -> tuple[QWidget, ModelPickerField, _ModelPickerComboSurface]:
    """Return a shown host, open picker field, and focused combo surface."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(extra_items + items),
        current_value=current_value,
    )
    field.resize(320, 34)
    field.show()
    field.open_picker()
    app.processEvents()
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    assert surface is not None
    assert field._popup is not None
    assert field._popup.isVisible() is True
    return host, field, surface


def _open_picker_surface_by_click(
    items: tuple[ModelCatalogItem, ...],
    *,
    current_value: str,
) -> tuple[QWidget, ModelPickerField, _ModelPickerComboSurface]:
    """Return a picker opened through the same mouse path users exercise."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(items),
        current_value=current_value,
    )
    field.resize(320, 34)
    field.show()
    app.processEvents()
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    assert surface is not None

    QTest.mouseClick(surface, Qt.MouseButton.LeftButton, pos=QPoint(8, 8))
    app.processEvents()
    wait_for_qt_condition(
        lambda: QApplication.focusWidget() is surface,
        description="model picker search-surface focus",
        state=lambda: QApplication.focusWidget(),
    )

    assert field._popup is not None
    assert field._popup.isVisible() is True
    return host, field, surface


def _exclusive_bottom(rect: QRect) -> int:
    """Return the exclusive bottom edge for popup overlap assertions."""

    return rect.top() + rect.height()


def _screen_available_geometry() -> QRect:
    """Return the primary screen's available geometry for global-anchor tests."""

    app = ensure_qapp()
    screen = app.primaryScreen()
    if screen is None:
        return QRect(0, 0, 1920, 1080)
    return screen.availableGeometry()


def _render_surface(
    surface: _ModelPickerComboSurface,
    *,
    fill: QColor | None = None,
) -> QImage:
    """Render one model picker combo surface into an offscreen image."""

    image = QImage(surface.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#00000000") if fill is None else fill)
    surface.render(image)
    return image


def _visible_model_picker_titles(field: ModelPickerField) -> list[str]:
    """Return visible popup item titles for field search assertions."""

    popup = field._popup
    assert popup is not None
    return [item.title for item in popup._view.items()]
