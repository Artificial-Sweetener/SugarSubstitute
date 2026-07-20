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

"""Render an attached searchable picker for metadata-backed model items."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable

from PySide6.QtCore import QEvent, QObject, QRect, Qt, Signal
from PySide6.QtGui import QHideEvent, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
from qfluentwidgets import SearchLineEdit  # type: ignore[import-untyped]

from sugarsubstitute_shared.localization import (
    ApplicationMessage,
    ApplicationText,
    app_text,
)
from sugarsubstitute_shared.presentation.localization import (
    clear_localized_property,
    set_localized_placeholder,
)

from substitute.application.model_metadata import ThumbnailAssetRepository
from substitute.presentation.widgets.civitai_page_action import UrlOpener
from substitute.presentation.widgets.fluent_popup_frame import AttachedFluentPopupFrame
from substitute.presentation.widgets.folder_route import (
    FolderRouteBar,
    FolderRouteEntry,
    FolderRouteTree,
    folder_route_from_item_path,
    normalize_folder_route,
)
from substitute.presentation.widgets.model_picker.model_picker_geometry import (
    MODEL_PICKER_POPUP_HEIGHT,
    MODEL_PICKER_POPUP_MIN_HEIGHT,
    MODEL_PICKER_POPUP_MIN_WIDTH,
    MODEL_PICKER_POPUP_WIDTH,
    ModelPickerPopupPlacementMode,
    model_picker_screen_available_geometry,
    resolve_model_picker_popup_placement,
)
from substitute.presentation.widgets.model_picker.model_picker_models import (
    ModelPickerItem,
)
from substitute.presentation.widgets.model_picker.model_picker_wall import (
    ModelPickerWallView,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)
from substitute.presentation.widgets.media_wall import (
    MediaWallThumbnailCache,
    MediaWallThumbnailPreloader,
)
from substitute.presentation.widgets.picker_keyboard_navigation import (
    PickerKeyboardAction,
    picker_keyboard_action_from_event,
)


class ModelPickerPopup(QWidget):
    """Show a floating model picker attached to a host widget."""

    modelActivated = Signal(object)
    itemActivated = Signal(object)
    dismissed = Signal(object)

    def __init__(
        self,
        items: Iterable[ModelPickerItem],
        *,
        asset_repository: ThumbnailAssetRepository | None = None,
        thumbnail_cache: MediaWallThumbnailCache | None = None,
        thumbnail_preloader: MediaWallThumbnailPreloader | None = None,
        search_placeholder: ApplicationText = app_text("Search models"),
        show_search_field: bool = True,
        dismissal_guard_widgets: Iterable[QWidget] = (),
        open_url: UrlOpener | None = None,
        metadata_action_handler: ModelMetadataContextActionHandler | None = None,
        search_focus_requested: Callable[[], None] | None = None,
        external_search_key_pressed: Callable[[QKeyEvent], bool] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build the search box, route bar, and filtered model wall."""

        materialized_items = tuple(items)
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setObjectName("modelPickerPopup")

        self._frame = AttachedFluentPopupFrame(self)
        self._search = SearchLineEdit(self._frame)
        if isinstance(search_placeholder, ApplicationMessage):
            set_localized_placeholder(
                self._search,
                search_placeholder.source_text,
                *search_placeholder.arguments,
            )
        else:
            clear_localized_property(self._search, "placeholder")
            self._search.setPlaceholderText(search_placeholder)
        self._search.setClearButtonEnabled(True)
        self._show_search_field = show_search_field
        self._dismissal_guard_widgets = tuple(dismissal_guard_widgets)
        self._search_text = ""
        self._placement_mode = ModelPickerPopupPlacementMode.BELOW
        self._picker_items = materialized_items
        self._search_focus_requested = search_focus_requested
        self._external_search_key_pressed = external_search_key_pressed
        route_entries, item_by_route_id = _route_entries_for_picker_items(
            self._picker_items
        )
        self._route_tree = FolderRouteTree(route_entries)
        self._item_by_route_id = item_by_route_id
        self._active_route: tuple[str, ...] = ()
        self._route_bar = FolderRouteBar(self._frame)
        self._route_bar.set_route_tree(self._route_tree)
        self._view = ModelPickerWallView(
            self._frame,
            asset_repository=asset_repository,
            thumbnail_cache=thumbnail_cache,
            thumbnail_preloader=thumbnail_preloader,
            open_url=open_url,
            metadata_action_handler=metadata_action_handler,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._frame)

        self._apply_placement_mode(ModelPickerPopupPlacementMode.BELOW)

        self._search.textChanged.connect(self._set_embedded_search_text)
        self._route_bar.routeChanged.connect(self._set_active_route)
        self._view.modelActivated.connect(self._activate_item)
        self._apply_filters()
        self.resize(MODEL_PICKER_POPUP_WIDTH, MODEL_PICKER_POPUP_HEIGHT)

    def set_search_text(self, query: str) -> None:
        """Apply externally owned search text to the popup filters."""

        next_query = str(query)
        self._search_text = next_query
        if self._search.text() != next_query:
            self._search.blockSignals(True)
            self._search.setText(next_query)
            self._search.blockSignals(False)
        self._apply_filters()

    def search_text(self) -> str:
        """Return the active search text used for filtering."""

        return self._search_text

    def set_items(self, items: Iterable[ModelPickerItem]) -> None:
        """Replace picker items while preserving route and search state."""

        self._picker_items = tuple(items)
        route_entries, item_by_route_id = _route_entries_for_picker_items(
            self._picker_items
        )
        self._route_tree = FolderRouteTree(route_entries)
        self._item_by_route_id = item_by_route_id
        self._route_bar.set_route_tree(self._route_tree)
        self._active_route = self._route_bar.current_route()
        self._apply_filters()

    def activate_current(self) -> bool:
        """Activate the currently selected wall item if one is available."""

        return self._view.activate_current()

    def current_item(self) -> ModelPickerItem | None:
        """Return the current visible picker item selected by wall navigation."""

        return self._view.current_model_item()

    def move_current_up(self) -> None:
        """Move the current wall item to the nearest item above."""

        self._view.move_current_up()

    def move_current_down(self) -> None:
        """Move the current wall item to the nearest item below."""

        self._view.move_current_down()

    def move_current_left(self) -> None:
        """Move the current wall item one item left in row-major order."""

        self._view.move_current_left()

    def move_current_right(self) -> None:
        """Move the current wall item one item right in row-major order."""

        self._view.move_current_right()

    def show_attached_to(self, anchor_rect: QRect) -> None:
        """Show the popup using an anchor rect in global screen coordinates."""

        boundary_rect = model_picker_screen_available_geometry(anchor_rect)
        placement = resolve_model_picker_popup_placement(
            boundary_rect=boundary_rect,
            anchor_rect=anchor_rect,
            preferred_width=MODEL_PICKER_POPUP_WIDTH,
            preferred_height=MODEL_PICKER_POPUP_HEIGHT,
            minimum_width=MODEL_PICKER_POPUP_MIN_WIDTH,
            minimum_height=MODEL_PICKER_POPUP_MIN_HEIGHT,
        )
        self._apply_placement_mode(placement.mode)
        self.setGeometry(placement.geometry)
        self.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus
            if self._show_search_field
            else Qt.FocusPolicy.NoFocus
        )
        self.show()
        self.raise_()
        if self._show_search_field:
            self._search.setFocus()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Route popup-owned picker keys and dismiss on outside interaction."""

        if event.type() == QEvent.Type.KeyPress and self.isVisible():
            key_event = event
            if isinstance(key_event, QKeyEvent):
                watched_widget = watched if isinstance(watched, QWidget) else None
                if watched_widget is not None and self._is_descendant_of(
                    watched_widget,
                    self,
                ):
                    if self._handle_picker_key(key_event):
                        return True
                    return self._forward_external_search_key(key_event)
                if key_event.key() == Qt.Key.Key_Escape:
                    self.hide()
                    key_event.accept()
                    return True
        if event.type() == QEvent.Type.MouseButtonPress and self.isVisible():
            mouse_event = event
            if isinstance(mouse_event, QMouseEvent):
                clicked_widget = QApplication.widgetAt(
                    mouse_event.globalPosition().toPoint()
                )
                if clicked_widget is None or not self._contains_widget(clicked_widget):
                    self.hide()
        return super().eventFilter(watched, event)

    def hideEvent(self, event: QHideEvent) -> None:
        """Remove the global outside-click filter when the popup hides."""

        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        super().hideEvent(event)
        self.dismissed.emit(self)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle picker navigation when the popup itself owns keyboard focus."""

        if self._handle_picker_key(event):
            return
        super().keyPressEvent(event)

    def _apply_placement_mode(self, mode: ModelPickerPopupPlacementMode) -> None:
        """Reorder popup rows so controls stay near the anchor edge."""

        self._placement_mode = mode
        content_layout = self._frame.content_layout()
        for widget in (self._search, self._route_bar, self._view):
            content_layout.removeWidget(widget)

        if self._show_search_field:
            self._search.show()
        else:
            self._search.hide()

        for widget in self._widgets_for_placement_mode(mode):
            content_layout.addWidget(widget)

    def _widgets_for_placement_mode(
        self,
        mode: ModelPickerPopupPlacementMode,
    ) -> tuple[QWidget, ...]:
        """Return visible row widgets in the order required by placement mode."""

        if mode is ModelPickerPopupPlacementMode.ABOVE:
            if self._show_search_field:
                return (self._view, self._route_bar, self._search)
            return (self._view, self._route_bar)
        if self._show_search_field:
            return (self._search, self._route_bar, self._view)
        return (self._route_bar, self._view)

    def _set_embedded_search_text(self, query: str) -> None:
        """Apply embedded search field edits to the shared filter state."""

        self._search_text = query
        self._apply_filters()

    def _set_active_route(self, route: tuple[str, ...]) -> None:
        """Apply one folder route and refresh visible model items."""

        self._active_route = route
        self._route_bar.set_current_route(route)
        self._apply_filters()
        self._request_external_search_focus()

    def _apply_filters(self) -> None:
        """Apply active route and search filters to the wall."""

        route_items = tuple(
            self._item_by_route_id[item_id]
            for item_id in self._route_tree.item_ids_under(self._active_route)
            if item_id in self._item_by_route_id
        )
        normalized_query = self._search_text.strip().replace("\\", "/").casefold()
        if not normalized_query:
            self._view.set_picker_items(route_items)
            return
        filtered_items = tuple(
            item for item in route_items if normalized_query in item.search_text
        )
        self._view.set_picker_items(filtered_items)

    def _activate_item(self, item: object) -> None:
        """Emit the activated picker item and its selection payload."""

        if not isinstance(item, ModelPickerItem):
            return
        self.itemActivated.emit(item)
        self.modelActivated.emit(item.payload)
        self.hide()

    def _handle_picker_key(self, event: QKeyEvent) -> bool:
        """Apply shared picker keyboard actions to this popup's wall state."""

        action = picker_keyboard_action_from_event(event, escape_dismisses=True)
        if action is None:
            return False
        if action is PickerKeyboardAction.DISMISS:
            self.hide()
        elif action is PickerKeyboardAction.ACTIVATE:
            self.activate_current()
        elif action is PickerKeyboardAction.LEFT:
            self.move_current_left()
        elif action is PickerKeyboardAction.RIGHT:
            self.move_current_right()
        elif action is PickerKeyboardAction.UP:
            self.move_current_up()
        elif action is PickerKeyboardAction.DOWN:
            self.move_current_down()
        event.accept()
        return True

    def _request_external_search_focus(self) -> None:
        """Ask the external field-owned search editor to reclaim keyboard focus."""

        if self._show_search_field or self._search_focus_requested is None:
            return
        self._search_focus_requested()

    def _forward_external_search_key(self, event: QKeyEvent) -> bool:
        """Forward non-picker keys to the external field-owned search editor."""

        if self._show_search_field or self._external_search_key_pressed is None:
            return False
        return self._external_search_key_pressed(event)

    def _contains_widget(self, widget: QWidget) -> bool:
        """Return whether the supplied widget belongs to this popup or its owner."""

        if self._is_descendant_of(widget, self):
            return True
        return any(
            self._is_descendant_of(widget, guard_widget)
            for guard_widget in self._dismissal_guard_widgets
        )

    @staticmethod
    def _is_descendant_of(widget: QWidget, root: QWidget) -> bool:
        """Return whether one widget is inside another widget's parent chain."""

        current: QWidget | None = widget
        while current is not None:
            if current is root:
                return True
            current = current.parentWidget()
        return False


def _route_entries_for_picker_items(
    items: tuple[ModelPickerItem, ...],
) -> tuple[tuple[FolderRouteEntry, ...], dict[str, ModelPickerItem]]:
    """Return route entries and item lookup keyed by stable route item ids."""

    raw_ids = tuple(_raw_route_item_id(index, item) for index, item in enumerate(items))
    raw_id_counts = Counter(raw_ids)
    entries: list[FolderRouteEntry] = []
    item_by_route_id: dict[str, ModelPickerItem] = {}
    for index, item in enumerate(items):
        raw_id = raw_ids[index]
        item_id = raw_id if raw_id_counts[raw_id] == 1 else f"{index}:{raw_id}"
        item_by_route_id[item_id] = item
        entries.append(
            FolderRouteEntry(
                item_id=item_id,
                folder_path=_folder_route_for_picker_item(item),
            )
        )
    return tuple(entries), item_by_route_id


def _raw_route_item_id(index: int, item: ModelPickerItem) -> str:
    """Return the preferred stable route id before duplicate disambiguation."""

    return item.relative_path or item.backend_value or f"model:{index}"


def _folder_route_for_picker_item(item: ModelPickerItem) -> tuple[str, ...]:
    """Return the folder route for one model picker item."""

    if item.folder.strip():
        return normalize_folder_route(item.folder)
    return folder_route_from_item_path(item.relative_path)


__all__ = ["ModelPickerPopup"]
