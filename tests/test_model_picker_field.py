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

"""Contract tests for the metadata-backed model picker field."""

from __future__ import annotations

import os
import inspect
import time
from collections.abc import Callable
from typing import Any, cast
from uuid import UUID

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QHBoxLayout, QSizePolicy, QWidget
from qfluentwidgets import EditableComboBox, LineEdit, Theme  # type: ignore[import-untyped]

from substitute.application.model_metadata import (
    ModelCatalogItem,
    ModelMetadataRefreshEvent,
    ModelThumbnailVariant,
    RichChoiceItem,
    RichChoiceResolution,
)
from substitute.domain.model_metadata import BANNER_THUMBNAIL_ROLE, ThumbnailAsset
from substitute.presentation.shell.output_canvas_thumbnail_choices import (
    OutputCanvasThumbnailChoice,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextMenuTarget,
    ModelMetadataMenuAction,
)
import substitute.presentation.widgets.model_picker.model_picker_field as model_picker_field_module
from substitute.presentation.widgets.model_picker import (
    ModelPickerField,
    ModelPickerPopupPlacementMode,
    ModelPickerThumbnailPreloadRoute,
)
from substitute.presentation.widgets.model_picker.model_picker_field import (
    _ModelPickerComboSurface,
)
from substitute.presentation.widgets.model_picker.model_picker_models import (
    ModelPickerItem,
)
from substitute.presentation.widgets.text_caret import TEXT_CARET_WIDTH
from substitute.shared.qt_thumbnail_codec import prepare_qt_thumbnail
from tests.execution_testing import ImmediateTaskSubmitter
from tests.theme_switch_test_helpers import fluent_theme

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "model picker field widget tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def test_model_picker_combo_surface_paint_event_ends_qpainter() -> None:
    """Closed model picker painting should not leave an active QPainter behind."""

    source = inspect.getsource(_ModelPickerComboSurface.paintEvent)

    assert "finally:" in source
    assert "painter.end()" in source


class _FakeModelCatalog:
    """Return deterministic model picker catalog rows."""

    def __init__(self, items: tuple[ModelCatalogItem, ...]) -> None:
        """Store fake catalog rows for list and refresh calls."""

        self.items = items
        self.list_calls: list[str] = []
        self.refresh_calls: list[str] = []

    def list_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return fake rows and record the requested kind."""

        self.list_calls.append(kind)
        return self.items

    def refresh_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return fake rows and record the requested kind."""

        self.refresh_calls.append(kind)
        return self.items

    def current_resolution(self) -> RichChoiceResolution:
        """Return fake rows as a rich-choice source resolution."""

        return _rich_choice_resolution_from_catalog_items(self.items)

    def refresh(self) -> RichChoiceResolution:
        """Record a picker refresh and return fake rich-choice rows."""

        self.refresh_calls.append("checkpoints")
        return self.current_resolution()

    def invalidate(self, kind: str | None = None) -> None:
        """Ignore invalidation because tests control fake catalog rows directly."""

        _ = kind


class _ClearRecorder:
    """Record thumbnail cache clear calls for picker event tests."""

    def __init__(self) -> None:
        """Create an empty clear-call recorder."""

        self.calls = 0

    def clear(self) -> None:
        """Record one cache clear."""

        self.calls += 1


class _FakeStaleChoiceSource:
    """Return stale Comfy choices plus one metadata-backed downloaded model."""

    def __init__(
        self,
        *,
        choices: tuple[ModelCatalogItem, ...],
        extra: ModelCatalogItem,
    ) -> None:
        """Store the exact choices and a selected value absent from those choices."""

        self._choices = choices
        self._extra = extra

    def current_resolution(self) -> RichChoiceResolution:
        """Return the stale Comfy choices."""

        return _rich_choice_resolution_from_catalog_items(self._choices)

    def refresh(self) -> RichChoiceResolution:
        """Return the stale Comfy choices."""

        return self.current_resolution()

    def extra_item_for_value(self, value: str) -> RichChoiceItem | None:
        """Return metadata for the downloaded model when selected."""

        if value == self._extra.backend_value:
            return _rich_choice_item(self._extra)
        return None


class _FailingRefreshChoiceSource:
    """Return initial choices but fail when the picker asks Backend for freshness."""

    def __init__(self, items: tuple[ModelCatalogItem, ...]) -> None:
        """Store initial items and refresh attempts."""

        self._items = items
        self.refresh_calls = 0

    def current_resolution(self) -> RichChoiceResolution:
        """Return the initial rich-choice resolution."""

        return _rich_choice_resolution_from_catalog_items(self._items)

    def refresh(self) -> RichChoiceResolution:
        """Raise to simulate unavailable Backend model selection."""

        self.refresh_calls += 1
        raise RuntimeError("backend unavailable")


class _ThumbnailAssetRepository:
    """Return configured thumbnail assets and count reads by storage key."""

    def __init__(self, assets: dict[str, ThumbnailAsset]) -> None:
        """Store thumbnail assets for model picker field tests."""

        self._assets = assets
        self.reads_by_key: dict[str, int] = {}

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Record and return one configured thumbnail asset."""

        self.reads_by_key[storage_key] = self.reads_by_key.get(storage_key, 0) + 1
        return self._assets.get(storage_key)


class _MetadataActionHandler:
    """Record model metadata menu action targets in field tests."""

    def __init__(self) -> None:
        """Prepare refresh observations."""

        self.refresh_targets: list[object] = []

    def refresh_civitai_metadata(self, target: object) -> None:
        """Record one refresh target."""

        self.refresh_targets.append(target)

    def output_canvas_thumbnail_choices(
        self,
    ) -> tuple[OutputCanvasThumbnailChoice, ...]:
        """Return no output choices for existing field tests."""

        return ()

    def active_output_canvas_thumbnail_choice(
        self,
    ) -> OutputCanvasThumbnailChoice | None:
        """Return no active output choice for existing field tests."""

        return None

    def set_thumbnail_from_output_image(
        self,
        target: ModelMetadataContextMenuTarget,
        image_id: UUID,
    ) -> None:
        """Ignore output thumbnail requests in existing field tests."""

        _ = (target, image_id)


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
    """Pump Qt events in tests until one thumbnail preloader settles."""

    if not hasattr(preloader, "has_pending_work"):
        raise TypeError("preloader must expose has_pending_work().")
    app = ensure_qapp()
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    while bool(preloader.has_pending_work()) and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    app.processEvents()
    return not bool(preloader.has_pending_work())


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
    host.deleteLater()


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
    host.deleteLater()


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
    host.deleteLater()


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
    host.deleteLater()


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


def test_model_picker_field_popup_activation_emits_backend_value() -> None:
    """Activating a popup item should select its backend value and close the popup."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    catalog = _FakeModelCatalog(
        (
            _item("models/alpha.safetensors", "Alpha", None),
            _item("models/beta.safetensors", "Beta", None),
        )
    )
    field = ModelPickerField(
        host,
        choice_source=catalog,
        current_value="models/alpha.safetensors",
    )
    field.resize(220, 34)
    field.show()
    changed: list[str] = []
    field.currentTextChanged.connect(changed.append)

    field.open_picker()
    app.processEvents()
    assert field._popup is not None
    field._popup._view.move_current_right()
    assert field._popup._view.activate_current() is True
    app.processEvents()

    assert field.currentText() == "models/beta.safetensors"
    assert changed == ["models/beta.safetensors"]
    assert field._popup.isVisible() is False
    assert catalog.refresh_calls == ["checkpoints"]


def test_model_picker_field_refresh_failure_opens_empty_without_clearing_value() -> (
    None
):
    """Backend refresh failure should not show stale choices or erase field values."""

    ensure_qapp()
    source = _FailingRefreshChoiceSource(
        (_item("models/alpha.safetensors", "Alpha", None),)
    )
    field = ModelPickerField(
        choice_source=source,
        current_value="models/alpha.safetensors",
    )
    field.resize(320, field.sizeHint().height())
    field.show()

    field.open_picker()

    assert source.refresh_calls == 1
    assert field.currentText() == "models/alpha.safetensors"
    assert field._popup is not None
    assert field._popup._view.items() == ()
    field._dismiss_popup()
    assert field.displayText() == "alpha"
    field.deleteLater()


def test_model_picker_field_popup_search_filters_without_changing_value() -> None:
    """Typing in the field search should filter without selecting a backend value."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (
                _item("models/alpha.safetensors", "Alpha", None),
                _item("models/beta.safetensors", "Beta", None),
            )
        ),
        current_value="models/alpha.safetensors",
    )
    field.resize(220, 34)
    field.show()

    field.open_picker()
    app.processEvents()
    assert field._popup is not None
    surface = field.findChild(EditableComboBox, "modelPickerComboSurface")
    assert surface is not None

    QTest.keyClicks(surface, "beta")
    app.processEvents()

    assert [item.title for item in field._popup._view.items()] == ["Beta"]
    assert field.currentText() == "models/alpha.safetensors"
    assert field.displayText() == "beta"

    QTest.keyClick(surface, Qt.Key.Key_Escape)
    app.processEvents()

    assert field._popup.isVisible() is False
    assert field.currentText() == "models/alpha.safetensors"
    assert field.displayText() == "Alpha"
    host.deleteLater()


def test_model_picker_field_opens_above_when_below_would_cover_field() -> None:
    """Low fields should open above instead of clamping the popup over the field."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 220)
    screen = _screen_available_geometry()
    host.move(screen.left() + 40, screen.top() + max(0, screen.height() - 230))
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (_item("models/alpha.safetensors", "Alpha", None),)
        ),
        current_value="models/alpha.safetensors",
    )
    field.resize(220, 34)
    field.move(100, host.height() - 40)
    field.show()

    field.open_picker()
    app.processEvents()

    popup = field._popup
    assert popup is not None
    field_top = field.mapToGlobal(QPoint(0, 0)).y()
    field_bottom = field_top + field.height()
    popup_geometry = popup.geometry()

    assert popup.isVisible() is True
    assert popup._placement_mode is ModelPickerPopupPlacementMode.ABOVE
    assert _exclusive_bottom(popup_geometry) <= field_top
    assert not (
        popup_geometry.top() < field_bottom
        and _exclusive_bottom(popup_geometry) > field_top
    )
    host.deleteLater()


def test_model_picker_field_open_search_shows_text_caret() -> None:
    """Opening the picker should show a caret that follows native cursor geometry."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (_item("models/alpha.safetensors", "Alpha", None),)
        ),
        current_value="models/alpha.safetensors",
    )
    field.resize(220, 34)
    field.show()

    field.open_picker()
    app.processEvents()
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    assert surface is not None

    assert surface.search_focus_active() is True
    assert surface.isReadOnly() is False
    assert surface.cursor().shape() == Qt.CursorShape.IBeamCursor
    assert surface.cursorRect().height() > 0
    assert surface.cursorPosition() == 0
    assert surface._should_paint_search_caret() is True
    assert surface._current_search_caret_rect().width() == TEXT_CARET_WIDTH

    initial_cursor_left = surface._current_search_caret_rect().left()
    QTest.keyClicks(surface, "be")
    app.processEvents()

    assert surface.text() == "be"
    assert surface.cursorPosition() == 2
    assert surface._should_paint_search_caret() is True
    assert surface._current_search_caret_rect().left() > initial_cursor_left
    host.deleteLater()


def test_model_picker_field_screen_popup_survives_search_focus_transfer() -> None:
    """Opening a screen popup should keep combo-surface search focus usable."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (
                _item("models/alpha.safetensors", "Alpha", None),
                _item("models/beta.safetensors", "Beta", None),
            )
        ),
        current_value="models/alpha.safetensors",
    )
    field.resize(220, 34)
    field.show()
    changed: list[str] = []
    field.currentTextChanged.connect(changed.append)

    field.open_picker()
    app.processEvents()
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    popup = field._popup
    assert surface is not None
    assert popup is not None

    assert popup.isVisible() is True
    assert surface.search_focus_active() is True

    QTest.keyClicks(surface, "beta")
    app.processEvents()

    assert popup.isVisible() is True
    assert [item.title for item in popup._view.items()] == ["Beta"]
    assert field.currentText() == "models/alpha.safetensors"
    assert changed == []
    host.deleteLater()


def test_model_picker_field_typing_still_filters_after_wall_focus() -> None:
    """Typing should keep using the field search after the wall receives focus."""

    app = ensure_qapp()
    host, field, surface = _open_picker_surface_by_click(
        (
            _item("models/alpha.safetensors", "Alpha", None),
            _item("models/beta.safetensors", "Beta", None),
        ),
        current_value="models/alpha.safetensors",
    )
    popup = field._popup
    assert popup is not None
    changed: list[str] = []
    field.currentTextChanged.connect(changed.append)
    app.processEvents()

    assert QApplication.focusWidget() is surface

    QTest.mouseClick(popup._view, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
    focus_widget = QApplication.focusWidget()
    assert focus_widget is not None
    QTest.keyClicks(focus_widget, "be")
    app.processEvents()

    assert QApplication.focusWidget() is surface
    assert surface.text() == "be"
    assert _visible_model_picker_titles(field) == ["Beta"]
    assert field.currentText() == "models/alpha.safetensors"
    assert changed == []
    host.deleteLater()


def test_model_picker_field_typing_still_filters_after_route_focus() -> None:
    """Typing should keep using the field search after route controls take focus."""

    app = ensure_qapp()
    host, field, surface = _open_picker_surface_by_click(
        (
            _item("models/alpha.safetensors", "Alpha", None),
            _item("models/beta.safetensors", "Beta", None),
        ),
        current_value="models/alpha.safetensors",
    )
    popup = field._popup
    assert popup is not None
    changed: list[str] = []
    field.currentTextChanged.connect(changed.append)
    app.processEvents()

    assert QApplication.focusWidget() is surface
    route_buttons = popup._route_bar.child_route_buttons()
    assert route_buttons

    QTest.mouseClick(route_buttons[0], Qt.MouseButton.LeftButton)
    focus_widget = QApplication.focusWidget()
    assert focus_widget is not None
    QTest.keyClicks(focus_widget, "be")
    app.processEvents()

    assert surface.text() == "be"
    assert _visible_model_picker_titles(field) == ["Beta"]
    assert field.currentText() == "models/alpha.safetensors"
    assert changed == []
    host.deleteLater()


def test_model_picker_field_route_click_survives_delayed_release() -> None:
    """Route clicks should complete even when the event loop runs before release."""

    app = ensure_qapp()
    host, field, _surface = _open_picker_surface_by_click(
        (
            _item("illustrious/alpha.safetensors", "Alpha", None, folder="illustrious"),
            _item("realistic/beta.safetensors", "Beta", None, folder="realistic"),
        ),
        current_value="illustrious/alpha.safetensors",
    )
    popup = field._popup
    assert popup is not None
    route_buttons = popup._route_bar.child_route_buttons()
    target_button = next(
        button for button in route_buttons if button.text() == "realistic (1)"
    )

    QTest.mousePress(target_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    QTest.mouseRelease(target_button, Qt.MouseButton.LeftButton)
    app.processEvents()

    assert popup._route_bar.current_route() == ("realistic",)
    assert _visible_model_picker_titles(field) == ["Beta"]
    host.deleteLater()


def test_model_picker_field_click_enters_native_text_editing() -> None:
    """Mouse opening should still let the native line edit initialize caret state."""

    with fluent_theme(Theme.DARK):
        app = ensure_qapp()
        host = QWidget()
        host.resize(640, 480)
        host.show()
        field = ModelPickerField(
            host,
            choice_source=_FakeModelCatalog(
                (_item("models/alpha.safetensors", "Alpha", None),)
            ),
            current_value="models/alpha.safetensors",
        )
        field.resize(220, 34)
        field.show()
        surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
        assert surface is not None

        QTest.mouseClick(surface, Qt.MouseButton.LeftButton, pos=QPoint(8, 8))
        app.processEvents()

        assert surface.search_focus_active() is True
        assert surface.isReadOnly() is False
        assert surface.cursor().shape() == Qt.CursorShape.IBeamCursor
        assert surface.palette().text().color().name() == "#ffffff"
        assert surface._should_paint_search_caret() is True

        initial_caret_left = surface._current_search_caret_rect().left()
        QTest.keyClicks(surface, "al")
        app.processEvents()

        assert surface.text() == "al"
        assert surface.cursorPosition() == 2
        assert surface._current_search_caret_rect().left() > initial_caret_left
        host.deleteLater()


def test_model_picker_field_open_clicks_do_not_clear_search_text() -> None:
    """Clicking inside an open search field should not restart and clear the picker."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (_item("models/alpha.safetensors", "Alpha", None),)
        ),
        current_value="models/alpha.safetensors",
    )
    field.resize(220, 34)
    field.show()

    field.open_picker()
    app.processEvents()
    popup = field._popup
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    assert popup is not None
    assert surface is not None

    QTest.keyClicks(surface, "alpha")
    app.processEvents()
    QTest.mouseClick(
        surface,
        Qt.MouseButton.LeftButton,
        pos=QPoint(surface.width() // 2, surface.height() // 2),
    )
    app.processEvents()

    assert field._popup is popup
    assert popup.isVisible() is True
    assert surface.isReadOnly() is False
    assert surface.text() == "alpha"
    host.deleteLater()


def test_model_picker_field_mouse_drag_can_select_search_text() -> None:
    """Mouse drag selection should stay inside the native editable combo text system."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (_item("models/alpha.safetensors", "Alpha", None),)
        ),
        current_value="models/alpha.safetensors",
    )
    field.resize(220, 34)
    field.show()

    field.open_picker()
    app.processEvents()
    popup = field._popup
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    assert popup is not None
    assert surface is not None

    QTest.keyClicks(surface, "alpha")
    app.processEvents()
    y_position = surface.height() // 2
    QTest.mousePress(
        surface,
        Qt.MouseButton.LeftButton,
        pos=QPoint(12, y_position),
    )
    QTest.mouseMove(surface, QPoint(surface.width() - 48, y_position))
    QTest.mouseRelease(
        surface,
        Qt.MouseButton.LeftButton,
        pos=QPoint(surface.width() - 48, y_position),
    )
    app.processEvents()

    assert field._popup is popup
    assert popup.isVisible() is True
    assert surface.text() == "alpha"
    assert surface.hasSelectedText() is True
    assert surface._should_paint_search_caret() is False
    host.deleteLater()


def test_model_picker_field_search_caret_renders_on_surface() -> None:
    """The search caret should paint visibly over the editable combo surface."""

    with fluent_theme(Theme.DARK):
        app = ensure_qapp()
        host = QWidget()
        host.resize(640, 480)
        host.show()
        field = ModelPickerField(
            host,
            choice_source=_FakeModelCatalog(
                (_item("models/alpha.safetensors", "Alpha", None),)
            ),
            current_value="models/alpha.safetensors",
        )
        field.resize(220, 34)
        field.show()

        field.open_picker()
        app.processEvents()
        surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
        assert surface is not None

        surface._show_search_caret()
        image = QImage(surface.size(), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        surface.render(image)

        caret_rect = surface._current_search_caret_rect()
        assert caret_rect.width() == TEXT_CARET_WIDTH
        line_x = int(round(caret_rect.center().x()))
        painted_pixels = [
            image.pixelColor(line_x, y)
            for y in range(int(caret_rect.top()) + 2, int(caret_rect.bottom()) - 2)
        ]

        assert any(
            pixel.red() > 230
            and pixel.green() > 230
            and pixel.blue() > 230
            and pixel.alpha() > 180
            for pixel in painted_pixels
        )
        host.deleteLater()


def test_model_picker_field_typing_does_not_emit_backend_value_signal() -> None:
    """Search text is transient UI state and must not write through widget wiring."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (
                _item("models/alpha.safetensors", "Alpha", None),
                _item("models/beta.safetensors", "Beta", None),
            )
        ),
        current_value="models/alpha.safetensors",
    )
    field.resize(220, 34)
    field.show()
    changed: list[str] = []
    field.currentTextChanged.connect(changed.append)

    field.open_picker()
    app.processEvents()
    surface = field.findChild(EditableComboBox, "modelPickerComboSurface")
    assert surface is not None

    QTest.keyClicks(surface, "beta")
    app.processEvents()

    assert changed == []
    assert field.currentText() == "models/alpha.safetensors"
    host.deleteLater()


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


def test_model_picker_field_right_click_menu_opens_selected_civitai_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Right-clicking a closed picker field should expose selected model CivitAI URL."""

    app = ensure_qapp()
    opened_urls: list[str] = []

    def open_url(url: str) -> bool:
        """Record URL opens without launching a browser."""

        opened_urls.append(url)
        return True

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
                    model_page_url="https://civitai.com/models/1?modelVersionId=2",
                ),
            )
        ),
        current_value="models/alpha.safetensors",
        open_url=open_url,
    )
    field.resize(260, 34)
    field.show()
    app.processEvents()
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    assert surface is not None
    shown_targets: list[ModelMetadataContextMenuTarget] = []

    def show_menu(target: ModelMetadataContextMenuTarget, _pos: QPoint) -> bool:
        """Record and invoke the selected model's page action."""

        shown_targets.append(target)
        actions = tuple(
            item
            for item in field._metadata_context_menu.menu_items_for_target(target)
            if isinstance(item, ModelMetadataMenuAction)
        )
        actions[0].callback()
        return True

    monkeypatch.setattr(field._metadata_context_menu, "show_menu", show_menu)

    _right_click_closed_picker_surface(surface)
    app.processEvents()

    assert len(shown_targets) == 1
    assert shown_targets[0].backend_value == "models/alpha.safetensors"
    assert opened_urls == ["https://civitai.com/models/1?modelVersionId=2"]
    host.deleteLater()


def test_model_picker_field_right_click_menu_omits_missing_civitai_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Right-clicking a local-only selection should not show an empty context menu."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (_item("models/alpha.safetensors", "Alpha Model", "v1"),)
        ),
        current_value="models/alpha.safetensors",
    )
    field.resize(260, 34)
    field.show()
    app.processEvents()
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    assert surface is not None
    shown_targets: list[ModelMetadataContextMenuTarget] = []

    def show_menu(target: ModelMetadataContextMenuTarget, _pos: QPoint) -> bool:
        """Record the request while preserving empty-menu suppression."""

        shown_targets.append(target)
        return bool(field._metadata_context_menu.menu_items_for_target(target))

    monkeypatch.setattr(
        field._metadata_context_menu,
        "show_menu",
        show_menu,
    )

    _right_click_closed_picker_surface(surface)
    app.processEvents()

    assert len(shown_targets) == 1
    assert field._metadata_context_menu.menu_items_for_target(shown_targets[0]) == ()
    host.deleteLater()


def test_model_picker_field_right_click_refresh_targets_selected_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Right-clicking a selected model should expose manual metadata refresh."""

    app = ensure_qapp()
    handler = _MetadataActionHandler()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (_item("models/alpha.safetensors", "Alpha Model", "v1"),)
        ),
        current_value="models/alpha.safetensors",
        metadata_action_handler=handler,
    )
    field.resize(260, 34)
    field.show()
    app.processEvents()
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    assert surface is not None
    shown_targets: list[ModelMetadataContextMenuTarget] = []

    def show_menu(target: ModelMetadataContextMenuTarget, _pos: QPoint) -> bool:
        """Record and invoke the selected model's refresh action."""

        shown_targets.append(target)
        actions = tuple(
            item
            for item in field._metadata_context_menu.menu_items_for_target(target)
            if isinstance(item, ModelMetadataMenuAction)
        )
        refresh_action = next(
            action for action in actions if action.label == "Refresh CivitAI metadata"
        )
        refresh_action.callback()
        return True

    monkeypatch.setattr(field._metadata_context_menu, "show_menu", show_menu)

    _right_click_closed_picker_surface(surface)
    app.processEvents()

    assert len(shown_targets) == 1
    assert len(handler.refresh_targets) == 1
    refresh_target = handler.refresh_targets[0]
    assert getattr(refresh_target, "model_kind") == "checkpoints"
    assert getattr(refresh_target, "backend_value") == "models/alpha.safetensors"
    host.deleteLater()


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
        host.deleteLater()


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
    host.deleteLater()


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
    host.deleteLater()


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
    host.deleteLater()


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
    host.deleteLater()


def test_model_picker_field_shows_filename_inline_completion() -> None:
    """Typing a filename-only match should show a display-only suffix."""

    app = ensure_qapp()
    host, field, surface = _open_picker_surface(
        (
            _item(
                "Illustrious/notFriendlyName_v11.safetensors",
                "Completely Different",
                "v11",
            ),
        ),
        current_value="Illustrious/notFriendlyName_v11.safetensors",
    )

    QTest.keyClicks(surface, "Friendly")
    app.processEvents()

    assert surface.inline_completion_suffix() == "Name_v11"
    assert surface.text() == "Friendly"
    assert field.currentText() == "Illustrious/notFriendlyName_v11.safetensors"
    host.deleteLater()


def test_model_picker_field_shows_path_inline_completion() -> None:
    """Typing a path prefix should show a suffix for the current visible path."""

    app = ensure_qapp()
    host, _field, surface = _open_picker_surface(
        (_item("Illustrious/amanatsuIllustrious_v11.safetensors", "Amanatsu", "v11"),),
        current_value="Illustrious/amanatsuIllustrious_v11.safetensors",
    )

    QTest.keyClicks(surface, r"Illustrious\aman")
    app.processEvents()

    assert surface.inline_completion_suffix() == "atsuIllustrious_v11"
    host.deleteLater()


def test_model_picker_field_shows_friendly_name_inline_completion() -> None:
    """Typing a CivitAI display prefix should complete the friendly label."""

    app = ensure_qapp()
    host, _field, surface = _open_picker_surface(
        (_item("Illustrious/tNoobnai3_v9.safetensors", "T-noobnai3", "v9"),),
        current_value="Illustrious/tNoobnai3_v9.safetensors",
    )

    QTest.keyClicks(surface, "T-noob")
    app.processEvents()

    assert surface.inline_completion_suffix() == "nai3 - v9"
    host.deleteLater()


def test_model_picker_field_tab_accepts_inline_completion_without_selecting() -> None:
    """Tab should accept ghost text into search text but not select a backend value."""

    app = ensure_qapp()
    host, field, surface = _open_picker_surface(
        (_item("Illustrious/amanatsuIllustrious_v11.safetensors", "Amanatsu", "v11"),),
        current_value="models/alpha.safetensors",
        extra_items=(_item("models/alpha.safetensors", "Alpha", None),),
    )
    changed: list[str] = []
    field.currentTextChanged.connect(changed.append)

    QTest.keyClicks(surface, "aman")
    app.processEvents()
    QTest.keyClick(surface, Qt.Key.Key_Tab)
    app.processEvents()

    assert surface.text() == "amanatsuIllustrious_v11"
    assert surface.inline_completion_suffix() == ""
    assert field.currentText() == "models/alpha.safetensors"
    assert changed == []
    host.deleteLater()


def test_model_picker_field_right_navigates_and_tab_accepts_completion() -> None:
    """Plain Right should navigate while Tab remains the completion accept key."""

    app = ensure_qapp()
    host, _field, surface = _open_picker_surface(
        (_item("Illustrious/amanatsuIllustrious_v11.safetensors", "Amanatsu", "v11"),),
        current_value="Illustrious/amanatsuIllustrious_v11.safetensors",
    )

    QTest.keyClicks(surface, "aman")
    app.processEvents()
    surface.setCursorPosition(2)
    app.processEvents()
    QTest.keyClick(surface, Qt.Key.Key_Right)
    app.processEvents()

    assert surface.text() == "aman"
    assert surface.cursorPosition() == 2
    assert surface.inline_completion_suffix() == ""

    surface.setCursorPosition(len(surface.text()))
    surface.set_inline_completion_suffix("atsuIllustrious_v11")
    QTest.keyClick(surface, Qt.Key.Key_Right)
    app.processEvents()

    assert surface.text() == "aman"
    assert surface.inline_completion_suffix() == "atsuIllustrious_v11"

    QTest.keyClick(surface, Qt.Key.Key_Tab)
    app.processEvents()

    assert surface.text() == "amanatsuIllustrious_v11"
    host.deleteLater()


def test_model_picker_field_arrow_keys_navigate_open_picker_wall() -> None:
    """Open combo-search fields should reuse LoRA-style wall arrow navigation."""

    app = ensure_qapp()
    host, field, surface = _open_picker_surface(
        tuple(
            _item(f"models/model_{index}.safetensors", f"Model {index}", None)
            for index in range(12)
        ),
        current_value="models/model_0.safetensors",
    )
    popup = field._popup
    assert popup is not None
    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title == "Model 0"

    QTest.keyClick(surface, Qt.Key.Key_Right)
    app.processEvents()
    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title == "Model 1"

    QTest.keyClick(surface, Qt.Key.Key_Left)
    app.processEvents()
    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title == "Model 0"

    QTest.keyClick(surface, Qt.Key.Key_Down)
    app.processEvents()
    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title != "Model 0"

    host.deleteLater()


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
    popup.set_search_text("refined")
    catalog.items = (_item("models/refined.safetensors", "Refined", "v2"),)

    field.refresh_metadata()
    app.processEvents()

    current_item = popup.current_item()
    assert popup.isVisible() is True
    assert popup.search_text() == "refined"
    assert current_item is not None
    assert current_item.title == "Refined"
    assert catalog.refresh_calls == ["checkpoints", "checkpoints"]
    host.deleteLater()


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
    popup.set_search_text("only")
    app.processEvents()
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    assert surface is not None
    assert surface.search_focus_active() is True

    field.reconcile_choice_source(
        _FakeModelCatalog((_item("models/only.safetensors", "Only Model", "v1"),)),
        "models/only.safetensors",
    )
    app.processEvents()

    assert field._popup is popup
    assert popup.isVisible() is True
    assert popup.search_text() == "only"
    assert surface.search_focus_active() is True
    assert field.currentText() == "models/only.safetensors"
    assert [item.title for item in popup._view.items()] == ["Only Model"]
    assert changed == []
    host.deleteLater()


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
    host.deleteLater()


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
    host.deleteLater()


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


def test_model_picker_field_ctrl_arrows_preserve_native_text_navigation() -> None:
    """Ctrl-arrow should stay available for caret movement in the search text."""

    app = ensure_qapp()
    host, field, surface = _open_picker_surface(
        tuple(
            _item(f"models/model_{index}.safetensors", f"Model {index}", None)
            for index in range(3)
        ),
        current_value="models/model_0.safetensors",
    )
    popup = field._popup
    assert popup is not None
    QTest.keyClicks(surface, "model")
    surface.setCursorPosition(0)
    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title == "Model 0"

    QTest.keyClick(
        surface,
        Qt.Key.Key_Right,
        Qt.KeyboardModifier.ControlModifier,
    )
    app.processEvents()

    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title == "Model 0"
    assert surface.cursorPosition() > 0
    host.deleteLater()


def test_model_picker_field_text_selection_suppresses_inline_completion() -> None:
    """Selecting search text should clear the display-only suffix."""

    app = ensure_qapp()
    host, _field, surface = _open_picker_surface(
        (_item("Illustrious/amanatsuIllustrious_v11.safetensors", "Amanatsu", "v11"),),
        current_value="Illustrious/amanatsuIllustrious_v11.safetensors",
    )

    QTest.keyClicks(surface, "aman")
    app.processEvents()
    assert surface.inline_completion_suffix() == "atsuIllustrious_v11"

    surface.selectAll()
    app.processEvents()

    assert surface.hasSelectedText() is True
    assert surface.inline_completion_suffix() == ""
    assert surface._should_paint_search_caret() is False
    host.deleteLater()


def test_model_picker_field_escape_clears_inline_completion_and_restores_label() -> (
    None
):
    """Dismissing search should clear ghost text and restore closed combo display."""

    app = ensure_qapp()
    host, field, surface = _open_picker_surface(
        (_item("Illustrious/amanatsuIllustrious_v11.safetensors", "Amanatsu", "v11"),),
        current_value="Illustrious/amanatsuIllustrious_v11.safetensors",
    )

    QTest.keyClicks(surface, "aman")
    app.processEvents()
    assert surface.inline_completion_suffix() == "atsuIllustrious_v11"

    QTest.keyClick(surface, Qt.Key.Key_Escape)
    app.processEvents()

    assert surface.inline_completion_suffix() == ""
    assert field.displayText() == "Amanatsu - v11"
    assert field.currentText() == "Illustrious/amanatsuIllustrious_v11.safetensors"
    host.deleteLater()


def test_model_picker_field_enter_still_selects_current_backend_value() -> None:
    """Enter should activate the current item instead of accepting ghost text."""

    app = ensure_qapp()
    host, field, surface = _open_picker_surface(
        (
            _item("models/alpha.safetensors", "Alpha", None),
            _item("models/beta.safetensors", "Beta", None),
        ),
        current_value="models/alpha.safetensors",
    )
    changed: list[str] = []
    field.currentTextChanged.connect(changed.append)

    QTest.keyClicks(surface, "beta")
    app.processEvents()
    QTest.keyClick(surface, Qt.Key.Key_Return)
    app.processEvents()

    assert field.currentText() == "models/beta.safetensors"
    assert changed == ["models/beta.safetensors"]
    assert field.displayText() == "Beta"
    host.deleteLater()


def test_model_picker_field_click_opens_attached_popup() -> None:
    """Clicking the closed field should reveal the attached model picker popup."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (_item("models/base.safetensors", "Base", None),)
        ),
        current_value="models/base.safetensors",
    )
    field.resize(220, 34)
    field.show()

    surface = field.findChild(EditableComboBox, "modelPickerComboSurface")
    assert surface is not None

    QTest.mouseClick(surface, Qt.MouseButton.LeftButton, pos=QPoint(8, 8))
    app.processEvents()

    assert field._popup is not None
    assert field._popup.isVisible() is True
    host.deleteLater()


def test_model_picker_field_chevron_click_closes_open_popup() -> None:
    """Clicking the drop chevron again should close the open picker popup."""

    app = ensure_qapp()
    host, field, surface = _open_picker_surface(
        (_item("models/base.safetensors", "Civit Base", "v2.0"),),
        current_value="models/base.safetensors",
    )
    popup = field._popup
    assert popup is not None
    assert popup.isVisible() is True

    QTest.mouseClick(surface.dropButton, Qt.MouseButton.LeftButton)
    app.processEvents()

    assert popup.isVisible() is False
    assert field._popup is popup
    assert surface.isReadOnly() is True
    assert field.displayText() == "Civit Base - v2.0"
    host.deleteLater()


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
    app.processEvents()

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


def _rich_choice_resolution_from_catalog_items(
    items: tuple[ModelCatalogItem, ...],
) -> RichChoiceResolution:
    """Adapt fake catalog items into a rich-choice resolution for widget tests."""

    rich_items = tuple(_rich_choice_item(item) for item in items)
    matched_kinds = tuple(sorted({item.kind for item in items}))
    return RichChoiceResolution(
        items=rich_items,
        should_use_rich_picker=True,
        matched_kinds=matched_kinds,
        option_count=len(rich_items),
        enriched_count=len(rich_items),
        ambiguous_count=0,
        unmatched_count=0,
        reason="test fixture",
    )


def _metadata_event(
    kind: str,
    value: str,
    *,
    thumbnail_updated: bool = True,
) -> ModelMetadataRefreshEvent:
    """Return one model metadata event for picker refresh tests."""

    return ModelMetadataRefreshEvent(
        kind=kind,
        value=value,
        relative_path=value,
        sha256="ABC123",
        provider_status="found",
        thumbnail_updated=thumbnail_updated,
    )


def _rich_choice_item(item: ModelCatalogItem) -> RichChoiceItem:
    """Adapt one fake catalog item into a rich choice item."""

    return RichChoiceItem(
        value=item.backend_value,
        title=item.display_name or item.basename,
        subtitle=item.display_subtitle,
        search_text=item.search_text,
        model_kind=item.kind,
        catalog_item=item,
        thumbnail_variants=item.thumbnail_variants,
        is_enriched=True,
        is_ambiguous=False,
    )


def _item(
    backend_value: str,
    display_name: str,
    display_subtitle: str | None,
    *,
    folder: str = "models",
    thumbnail_variants: tuple[ModelThumbnailVariant, ...] = (),
    model_page_url: str | None = None,
) -> ModelCatalogItem:
    """Return one generic catalog item for field tests."""

    return ModelCatalogItem(
        kind="checkpoints",
        display_name=display_name,
        display_subtitle=display_subtitle,
        backend_value=backend_value,
        relative_path=backend_value,
        folder=folder,
        basename=backend_value.rsplit("/", 1)[-1].removesuffix(".safetensors"),
        extension=".safetensors",
        thumbnail_variants=thumbnail_variants,
        base_model=None,
        trained_words=(),
        tags=(),
        model_page_url=model_page_url,
        collision_key=backend_value.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=f"{display_name} {backend_value}".casefold(),
    )


def _thumbnail_variant(storage_key: str, *, role: str) -> ModelThumbnailVariant:
    """Return one prepared model thumbnail variant."""

    return ModelThumbnailVariant(
        size=768,
        storage_key=storage_key,
        width=768,
        height=160,
        content_format="sqthumb-qimage-argb32-premultiplied",
        byte_size=768 * 160 * 4,
        role=role,
    )


def _thumbnail_asset(storage_key: str, color: QColor) -> ThumbnailAsset:
    """Return one Qt-ready thumbnail asset for field tests."""

    image = QImage(768, 160, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    prepared = prepare_qt_thumbnail(image)
    return ThumbnailAsset(
        storage_key=storage_key,
        width=prepared.width,
        height=prepared.height,
        qt_format=prepared.qt_format,
        bytes_per_line=prepared.bytes_per_line,
        content_format=prepared.content_format,
        payload=prepared.payload,
    )
