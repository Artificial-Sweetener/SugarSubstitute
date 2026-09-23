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

"""Mount real-provider update evidence in production full-window controls."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Sequence

from PySide6.QtCore import QPoint
from PySide6.QtGui import QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from substitute.application.model_metadata import (
    ModelCatalogItem,
    ModelCatalogSnapshot,
    ModelThumbnailVariant,
    RichChoiceItem,
    RichChoiceResolution,
)
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.infrastructure.model_recommendations.thumbnail_fetcher import (
    CivitaiThumbnailFetcher,
)
from substitute.presentation.settings.settings_card_group import SettingsCardGroup
from substitute.presentation.settings.settings_catalog_builders import (
    _civitai_model_update_notifications_row,
)
from substitute.presentation.settings.settings_page_shell import SettingsPageShell
from substitute.presentation.shell.window_frame import SubstituteWindowFrame
from substitute.presentation.widgets.menu_model import MenuModel
from substitute.presentation.widgets.model_metadata_context_menu import (
    model_metadata_menu_entries,
)
from substitute.presentation.widgets.model_picker import ModelPickerField
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer
from substitute.presentation.model_updates.picker_bridge import ModelUpdatePickerBridge
from substitute.shared.qt_thumbnail_codec import prepare_qt_thumbnail
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.model_discovery import DiscoveredModel
from sugarsubstitute_shared.model_updates import ModelUpdateProposal
from tests.presentation.widgets.model_picker.support import (
    _thumbnail_preload_route_factory,
)
from tools.install_experience_capture import (
    prepare_opaque_dark_capture_surface,
    save_opaque_dark_widget_capture,
)


@dataclass(frozen=True, slots=True)
class RealUpdateScenario:
    """Bind one real installed version to its verified compatible chronology."""

    proposal: ModelUpdateProposal
    versions: tuple[DiscoveredModel, ...]


class UpdatePreferenceService:
    """Retain local opt-in state for the production settings card."""

    def __init__(self) -> None:
        """Start with the product's disabled default."""

        self.model_update_notifications_enabled = False

    def load_preferences(self) -> UpdatePreferenceService:
        """Return the preference shape read by the production card."""

        return self

    def set_model_update_notifications_enabled(self, enabled: bool) -> None:
        """Accept the card's real toggle interaction."""

        self.model_update_notifications_enabled = enabled


class _ChoiceSource:
    """Expose real provider catalog rows through the production picker contract."""

    def __init__(self, items: tuple[ModelCatalogItem, ...]) -> None:
        """Retain exact real model metadata and hashes."""

        self._items = items

    def current_resolution(self) -> RichChoiceResolution:
        """Project real catalog rows into the picker choice boundary."""

        rows = tuple(
            RichChoiceItem(
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
            for item in self._items
        )
        return RichChoiceResolution(
            items=rows,
            should_use_rich_picker=True,
            matched_kinds=tuple(sorted({item.kind for item in self._items})),
            option_count=len(rows),
            enriched_count=len(rows),
            ambiguous_count=0,
            unmatched_count=0,
            reason="live CivitAI qualification",
        )

    def refresh(self) -> RichChoiceResolution:
        """Keep the captured provider page stable while opening the picker."""

        return self.current_resolution()


class _ThumbnailRepository:
    """Expose fetched real preview images to the production thumbnail cache."""

    def __init__(self, assets: dict[str, ThumbnailAsset]) -> None:
        """Store bounded decoded images under version-specific keys."""

        self._assets = assets

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Return the real prepared image for a provider version."""

        return self._assets.get(storage_key)


class _RenderedModelCatalog:
    """Publish real provider rows as a stable local model catalog snapshot."""

    def __init__(self, items: tuple[ModelCatalogItem, ...]) -> None:
        """Keep the installed versions selected for this visual qualification."""

        self._items = items

    def list_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return only the requested artifact family."""

        return tuple(item for item in self._items if item.kind == kind)

    def refresh_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Keep a deterministic local snapshot while the picker opens."""

        return self.list_models(kind)

    def invalidate(self, kind: str | None = None) -> None:
        """Leave this immutable qualification snapshot unchanged."""

    def cached_snapshot_nowait(self, kind: str) -> ModelCatalogSnapshot:
        """Supply the foreground-safe snapshot used by production node cards."""

        return ModelCatalogSnapshot(
            kind=kind, items=self.list_models(kind), generation=1
        )


def _asset(
    version: DiscoveredModel, fetcher: CivitaiThumbnailFetcher
) -> ThumbnailAsset:
    """Prepare a real safe-version image for the production picker cache."""

    if version.thumbnail_url is None:
        raise AssertionError(f"Real version {version.version_id} lacks a safe preview.")
    image = QImage.fromData(fetcher.fetch(version.thumbnail_url))
    if image.isNull():
        raise AssertionError(f"Real version {version.version_id} has an invalid image.")
    prepared = prepare_qt_thumbnail(image)
    return ThumbnailAsset(
        storage_key=f"civitai-version-{version.version_id}",
        width=prepared.width,
        height=prepared.height,
        qt_format=prepared.qt_format,
        bytes_per_line=prepared.bytes_per_line,
        content_format=prepared.content_format,
        payload=prepared.payload,
    )


def _catalog_item(version: DiscoveredModel, asset: ThumbnailAsset) -> ModelCatalogItem:
    """Represent an installed real model in the same catalog DTO as the app."""

    kind = version.artifact_kind.value
    return ModelCatalogItem(
        kind=kind,
        display_name=version.model_name,
        display_subtitle=version.version_name,
        backend_value=version.file_name,
        relative_path=version.file_name,
        folder=kind,
        basename=Path(version.file_name).stem,
        extension=".safetensors",
        thumbnail_variants=(
            ModelThumbnailVariant(
                size=max(asset.width, asset.height),
                storage_key=asset.storage_key,
                width=asset.width,
                height=asset.height,
                content_format=asset.content_format,
                byte_size=len(asset.payload),
            ),
        ),
        base_model=version.base_model,
        trained_words=(),
        tags=(),
        model_page_url=version.model_page_url,
        collision_key=version.file_name.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=f"{version.model_name} {version.version_name}".casefold(),
        sha256=version.sha256,
    )


def mount_shell(
    *, settings: bool, service: UpdatePreferenceService
) -> tuple[SubstituteWindowFrame, QVBoxLayout | None]:
    """Mount production controls within a complete application-sized frame."""

    frame = SubstituteWindowFrame(backdrop_mode=None)
    frame.resize(1280, 820)
    prepare_opaque_dark_capture_surface(frame)
    body = QWidget(frame)
    body.setObjectName("JourneyBody")
    body.setStyleSheet("QWidget#JourneyBody { background-color: #181818; }")
    row = QHBoxLayout(body)
    row.setContentsMargins(20, 16, 20, 20)
    sidebar = QFrame(body)
    sidebar.setFixedWidth(280)
    sidebar.setStyleSheet("QFrame { background-color: #242222; border-radius: 8px; }")
    sidebar_layout = QVBoxLayout(sidebar)
    sidebar_layout.setContentsMargins(22, 20, 22, 20)
    for value in ("SugarSubstitute", "Settings" if settings else "Models"):
        label = QLabel(value, sidebar)
        label.setStyleSheet("color: #f5f5f5; font-size: 17px;")
        sidebar_layout.addWidget(label)
    sidebar_layout.addStretch(1)
    row.addWidget(sidebar)
    if settings:
        content = QWidget(body)
        group = SettingsCardGroup("Missing model handling", parent=content)
        group.add_card(_civitai_model_update_notifications_row(service, group))  # type: ignore[arg-type]
        content_layout = QVBoxLayout(content)
        content_layout.addWidget(group)
        content_layout.addStretch(1)
        row.addWidget(
            SettingsPageShell(title=app_text("Generation"), widget=content), 1
        )
        picker_layout = None
    else:
        content = QFrame(body)
        content.setStyleSheet(
            "QFrame { background-color: #202022; border-radius: 8px; }"
        )
        picker_layout = QVBoxLayout(content)
        picker_layout.setContentsMargins(28, 24, 28, 24)
        picker_layout.setSpacing(14)
        row.addWidget(content, 1)
    frame.add_body_widget(body)
    frame.show()
    return frame, picker_layout


def settle(app: QApplication) -> None:
    """Flush queued production layout, preload, and paint work."""

    app.processEvents()
    QTest.qWait(180)
    app.processEvents()


def _capture_with_popup(
    frame: SubstituteWindowFrame, popup: QWidget, path: Path
) -> None:
    """Composite an actual top-level popup over the full app frame offscreen."""

    _capture_with_popups(frame, (popup,), path)


def _capture_with_popups(
    frame: SubstituteWindowFrame, popups: Sequence[QWidget], path: Path
) -> None:
    """Capture stacked picker and menu surfaces in their window positions."""

    image = frame.grab().toImage()
    painter = QPainter(image)
    frame_origin = frame.mapToGlobal(QPoint(0, 0))
    for popup in popups:
        popup_origin = popup.mapToGlobal(QPoint(0, 0))
        painter.drawPixmap(popup_origin - frame_origin, popup.grab())
    painter.end()
    if not image.save(str(path)):
        raise OSError(f"Could not save full-window picker capture: {path}")


def render_picker(
    app: QApplication,
    service: UpdatePreferenceService,
    scenarios: tuple[RealUpdateScenario, ...],
    fetcher: CivitaiThumbnailFetcher,
    output: Path,
    prefix: str,
) -> SubstituteWindowFrame:
    """Capture banner, menu, and tile icons over actual real-model previews."""

    frame, layout = mount_shell(settings=False, service=service)
    assert layout is not None
    heading = QLabel("Models used for Generate", frame)
    heading.setStyleSheet("color: #f5f5f5; font-size: 24px;")
    layout.addWidget(heading)
    hint = QLabel("Choose a model", frame)
    hint.setStyleSheet("color: #b8b8b8; font-size: 13px;")
    layout.addWidget(hint)
    assets = {
        asset.storage_key: asset
        for scenario in scenarios
        for asset in (
            _asset(
                next(
                    version
                    for version in scenario.versions
                    if version.version_id == scenario.proposal.current.version_id
                ),
                fetcher,
            ),
        )
    }
    items = tuple(
        _catalog_item(
            next(
                version
                for version in scenario.versions
                if version.version_id == scenario.proposal.current.version_id
            ),
            assets[f"civitai-version-{scenario.proposal.current.version_id}"],
        )
        for scenario in scenarios
    )
    bridge = ModelUpdatePickerBridge(frame)
    field = ModelPickerField(
        frame,
        choice_source=_ChoiceSource(items),
        thumbnail_asset_repository=_ThumbnailRepository(assets),
        thumbnail_preload_route_factory=_thumbnail_preload_route_factory(),
        current_value=items[0].backend_value,
        model_updates=bridge,
    )
    field.setFixedWidth(500)
    layout.addWidget(field)
    layout.addStretch(1)
    bridge.replace(tuple(scenario.proposal for scenario in scenarios))
    settle(app)
    save_opaque_dark_widget_capture(frame, output / f"{prefix}-banner.png")
    target = field._metadata_context_menu_target_for_current_value()
    if target is None:
        raise AssertionError("The selected real model has no context-menu target.")
    menu_items = field._metadata_context_menu.menu_items_for_target(target)
    if len(menu_items) < 2:
        raise AssertionError("The selected model has no update/provider menu actions.")
    menu = QFluentMenuRenderer(parent=field).render(
        MenuModel(entries=model_metadata_menu_entries(menu_items))
    )
    menu.move(field.mapToGlobal(QPoint(120, 28)))
    menu.show()
    settle(app)
    _capture_with_popup(frame, menu, output / f"{prefix}-context-menu.png")
    menu.close()
    field.open_picker()
    settle(app)
    QTest.qWait(420)
    app.processEvents()
    if field._popup is None or not field._popup.isVisible():
        raise AssertionError("Production model picker did not open.")
    _capture_with_popup(frame, field._popup, output / f"{prefix}-tiles.png")
    field._popup.hide()
    return frame


__all__ = [
    "RealUpdateScenario",
    "UpdatePreferenceService",
    "mount_shell",
    "render_picker",
    "settle",
]
