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

"""Present packaged detector thumbnails in the application modal layer."""

from __future__ import annotations

from PySide6.QtWidgets import QSizePolicy

from substitute.application.model_metadata import ThumbnailAssetRepository
from substitute.application.model_metadata.ultralytics_visual_catalog import (
    BundledUltralyticsThumbnailChoice,
    BundledUltralyticsThumbnailMode,
    bundled_ultralytics_thumbnail_choices,
)
from substitute.presentation.dialogs.full_window_modal import FullWindowModalBase
from substitute.presentation.localization import LocalizedSubtitleLabel
from substitute.presentation.widgets.media_wall import (
    MediaWallItem,
    MediaWallView,
    PickerJustifiedWallProfile,
)
from substitute.presentation.widgets.model_picker.model_picker_models import (
    model_picker_item_aspect_ratio,
    thumbnail_refs_from_model_variants,
)
from sugarsubstitute_shared.presentation.localization import (
    app_text,
    render_application_text,
)

_DIALOG_WIDTH = 880
_DIALOG_HEIGHT = 650
_WALL_PROFILE = PickerJustifiedWallProfile(
    target_row_height=184.0,
    min_row_height=144.0,
    max_row_height=224.0,
    minimum_tile_width=130.0,
)


class UltralyticsThumbnailLibraryModal(FullWindowModalBase):
    """Let the user select one packaged detector thumbnail in-place."""

    def __init__(
        self,
        *,
        asset_repository: ThumbnailAssetRepository,
        model_display_name: str,
        current_asset_name: str | None = None,
        parent: object | None = None,
    ) -> None:
        """Build the full-frame modal and its reusable media wall."""

        super().__init__(parent)
        self._selected_asset_name: str | None = None
        self._choices = bundled_ultralytics_thumbnail_choices()
        self.setClosableOnMaskClicked(False)
        self.hideYesButton()
        self.widget.setMinimumSize(_DIALOG_WIDTH, _DIALOG_HEIGHT)
        self.widget.setMaximumSize(_DIALOG_WIDTH, _DIALOG_HEIGHT)
        self.title_label = LocalizedSubtitleLabel(
            app_text("Choose detector thumbnail for %1", model_display_name),
            self.widget,
        )
        self.title_label.setObjectName("ultralyticsThumbnailLibraryTitle")
        self.title_label.setWordWrap(True)
        self.viewLayout.addWidget(self.title_label)
        self.wall = MediaWallView(
            self.widget,
            asset_repository=asset_repository,
            profile=_WALL_PROFILE,
        )
        self.wall.setFont(self.widget.font())
        self.wall.setObjectName("ultralyticsThumbnailLibraryWall")
        self.wall.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.wall.set_items(tuple(_wall_item(choice) for choice in self._choices))
        self.wall.itemActivated.connect(self._select_thumbnail)
        self.viewLayout.addWidget(self.wall, 1)
        if current_asset_name is not None:
            self._select_current_asset(current_asset_name)

    @property
    def selected_asset_name(self) -> str | None:
        """Return the asset selected before the modal accepted."""

        return self._selected_asset_name

    def _select_current_asset(self, asset_name: str) -> None:
        """Focus the current explicit association when it remains available."""

        for index, choice in enumerate(self._choices):
            if choice.asset_name == asset_name:
                self.wall.set_current_index(index)
                return

    def _select_thumbnail(self, payload: object) -> None:
        """Accept immediately after one concrete library choice is activated."""

        if not isinstance(payload, BundledUltralyticsThumbnailChoice):
            return
        self._selected_asset_name = payload.asset_name
        self.accept()


def _wall_item(choice: BundledUltralyticsThumbnailChoice) -> MediaWallItem:
    """Adapt one packaged thumbnail choice to the reusable media wall."""

    variants = thumbnail_refs_from_model_variants(choice.thumbnail_variants)
    return MediaWallItem(
        item_id=choice.asset_name,
        title=choice.title,
        subtitle=_mode_label(choice.mode),
        aspect_ratio=model_picker_item_aspect_ratio(variants),
        thumbnail_variants=variants,
        payload=choice,
        tooltip=choice.title,
    )


def _mode_label(mode: BundledUltralyticsThumbnailMode) -> str:
    """Return localized visible copy for one detector-output mode."""

    if mode is BundledUltralyticsThumbnailMode.SEGMENTATION:
        return render_application_text(app_text("Segmentation"))
    return render_application_text(app_text("Bounding Box"))


__all__ = ["UltralyticsThumbnailLibraryModal"]
