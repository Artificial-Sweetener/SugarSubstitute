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

"""Render a reusable modal for managing editable text assets."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.fluent_tooltips import (
    set_fluent_tooltip_text,
)

from sugarsubstitute_shared.presentation.localization import app_text

from sugarsubstitute_shared.presentation.localization import (
    set_localized_text,
    set_localized_tooltip,
)
from substitute.presentation.localization import (
    LocalizedCaptionLabel,
    LocalizedPrimaryPushButton,
    LocalizedPushButton,
)

from dataclasses import dataclass
from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidgetItem,
    QMessageBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    CaptionLabel,
    FluentIcon,
    ListWidget,
    MessageBoxBase,
    PushButton,
    SimpleCardWidget,
    ToolButton,
)
from shiboken6 import isValid

from substitute.application.managed_text_assets import (
    CreateManagedTextAssetRequest,
    ManagedTextAsset,
    ManagedTextAssetKind,
    ManagedTextAssetService,
    RenameManagedTextAssetRequest,
)
from substitute.presentation.widgets.menu_model import MenuItem, MenuModel
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer
from substitute.application.prompt_editor import (
    PromptEditorFeatureProfile,
    PromptWheelAdjustmentMode,
)
from substitute.application.prompt_editor.prompt_document_semantics import (
    PromptDocumentSemantics,
)
from substitute.application.errors import SubstituteOperationContext
from substitute.presentation.errors import (
    ErrorPresenter,
    ErrorReportPresenterProtocol,
)
from substitute.presentation.editor.prompt_editor.runtime_services import (
    PromptEditorRuntimeServices,
)
from substitute.presentation.managed_text_assets.numbered_prompt_editor_frame import (
    NumberedPromptEditorFrame,
)
from substitute.presentation.managed_text_assets.managed_text_asset_list import (
    ASSET_ID_ROLE,
    HEADER_KIND_ROLE,
    STRIPE_ROLE,
    AssetEntry,
    AssetListItemDelegate,
    AssetRow,
    group_assets,
    muted_text_color,
)
from substitute.presentation.managed_text_assets.modal_shadow import (
    ManagedTextAssetModalShadow,
)
from substitute.shared.logging.logger import get_logger, log_exception
from sugarsubstitute_shared.presentation.localization import (
    translate_application_message,
    translate_application_text,
)

_LOGGER = get_logger("presentation.managed_text_assets.modal")
_FALLBACK_PARENT: QWidget | None = None
_MODAL_WIDTH = 980
_MODAL_MINIMUM_HEIGHT = 360
_MODAL_OWNER_HEIGHT_FRACTION = 0.9
_LIST_PANE_STRETCH = 7
_EDITOR_PANE_STRETCH = 18


@dataclass(frozen=True, slots=True)
class ManagedTextAssetCreateAction:
    """Describe one modal-level asset creation command."""

    label: str
    kind: ManagedTextAssetKind
    default_content: str = ""
    category: str | None = None


class ManagedTextAssetModal(MessageBoxBase):  # type: ignore[misc]
    """Manage backend-neutral editable text assets inside a large two-pane modal."""

    saved = Signal()

    def __init__(
        self,
        *,
        title: str,
        asset_title: str,
        empty_text: str,
        service: ManagedTextAssetService,
        create_actions: tuple[ManagedTextAssetCreateAction, ...],
        prompt_runtime_services: PromptEditorRuntimeServices,
        prompt_feature_profile: PromptEditorFeatureProfile,
        document_semantics_for_asset: (
            Callable[[ManagedTextAsset], PromptDocumentSemantics] | None
        ) = None,
        wheel_adjustment_mode: PromptWheelAdjustmentMode = (
            PromptWheelAdjustmentMode.HOVER_DWELL
        ),
        error_presenter: ErrorReportPresenterProtocol | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build the managed text asset modal."""

        super().__init__(parent or _fallback_parent())
        self._static_shadow = ManagedTextAssetModalShadow(
            modal=self,
            center_widget=self.widget,
        )
        self._service = service
        self._asset_title = asset_title
        self._empty_text = empty_text
        self._create_actions = create_actions
        self._assets: dict[str, ManagedTextAsset] = {}
        self._entries: dict[str, AssetEntry] = {}
        self._original_text: dict[str, str] = {}
        self._edited_text: dict[str, str] = {}
        self._current_asset_id: str | None = None
        self._updating_editor = False
        self._pending_selection_id: str | None = None
        self._size_owner_window: QWidget | None = None
        self._error_presenter = error_presenter
        self._document_semantics_for_asset = document_semantics_for_asset

        self.setClosableOnMaskClicked(False)
        self.setModal(True)
        self.hideYesButton()
        self.hideCancelButton()
        self.buttonGroup.hide()
        self.buttonGroup.setFixedHeight(0)
        self.widget.setMinimumWidth(_MODAL_WIDTH)
        self.widget.setMinimumHeight(_MODAL_MINIMUM_HEIGHT)

        self._build_header(title)
        self._build_body(
            prompt_runtime_services=prompt_runtime_services,
            prompt_feature_profile=prompt_feature_profile,
            wheel_adjustment_mode=wheel_adjustment_mode,
        )
        self._connect_signals()
        self._bind_size_owner_window()
        self._apply_owner_window_size()
        self.reload()

    def reload(self) -> None:
        """Reload assets from the service while preserving pending selection intent."""

        self._persist_current_text()
        try:
            assets = self._service.list_assets()
        except Exception as exc:
            self._report_error(
                title=app_text("Unable to load assets"),
                operation="wildcard_modal.list_assets",
                error=exc,
            )
            return
        self._assets = {asset.id: asset for asset in assets}
        self._rebuild_asset_list(assets)
        selection_id = self._pending_selection_id or self._current_asset_id
        self._pending_selection_id = None
        if selection_id not in self._assets:
            selection_id = assets[0].id if assets else None
        self._select_asset(selection_id)
        self._update_apply_button()

    def _build_header(self, title: str) -> None:
        """Create the modal header and top-level actions."""

        header = QWidget(self.widget)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self._title = QLabel(title, header)
        self._title.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(self._title, 1)
        self._create_buttons: list[PushButton] = []
        for create_action in self._create_actions:
            button = PushButton(create_action.label, header)
            button.setIcon(FluentIcon.ADD)
            button.clicked.connect(
                lambda _checked=False, action=create_action: self._create_asset(action)
            )
            self._create_buttons.append(button)
            layout.addWidget(button, 0, Qt.AlignmentFlag.AlignTop)
        self._apply_button = LocalizedPrimaryPushButton(app_text("Apply"), header)
        self._apply_button.setIcon(FluentIcon.ACCEPT)
        layout.addWidget(self._apply_button, 0, Qt.AlignmentFlag.AlignTop)
        self._discard_button = LocalizedPushButton(app_text("Discard"), header)
        self._discard_button.setIcon(FluentIcon.CLOSE)
        layout.addWidget(self._discard_button, 0, Qt.AlignmentFlag.AlignTop)
        self.viewLayout.addWidget(header)

    def _build_body(
        self,
        *,
        prompt_runtime_services: PromptEditorRuntimeServices,
        prompt_feature_profile: PromptEditorFeatureProfile,
        wheel_adjustment_mode: PromptWheelAdjustmentMode,
    ) -> None:
        """Create the two-pane asset picker and editor body."""

        body = QWidget(self.widget)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(12)

        left_card = SimpleCardWidget(body)
        left_card.setMinimumWidth(0)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)
        left_title = QLabel(self._asset_title, left_card)
        left_title.setStyleSheet("font-size: 14px; font-weight: 700;")
        left_layout.addWidget(left_title)
        self._asset_list = ListWidget(left_card)
        self._asset_list.setSelectionMode(
            self._asset_list.SelectionMode.SingleSelection
        )
        self._asset_list.setMouseTracking(True)
        self._asset_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._asset_list.setAlternatingRowColors(False)
        self._asset_list.setStyleSheet(
            "ListWidget { background: transparent; }"
            "ListWidget:hover { background: transparent; }"
            "ListWidget::item { background: transparent; }"
        )
        self._asset_list.setItemDelegate(AssetListItemDelegate(self._asset_list))
        self._asset_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        left_layout.addWidget(self._asset_list, 1)
        body_layout.addWidget(left_card, _LIST_PANE_STRETCH)

        right_card = SimpleCardWidget(body)
        right_card.setMinimumWidth(0)
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)
        inspector_header = QWidget(right_card)
        inspector_layout = QHBoxLayout(inspector_header)
        inspector_layout.setContentsMargins(0, 0, 0, 0)
        inspector_layout.setSpacing(8)
        self._asset_name = QLabel("", inspector_header)
        self._asset_name.setStyleSheet("font-size: 16px; font-weight: 700;")
        self._asset_name.setMinimumWidth(0)
        self._asset_name.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        inspector_layout.addWidget(self._asset_name, 1)
        self._save_button = ToolButton(FluentIcon.SAVE, inspector_header)
        set_localized_tooltip(self._save_button, "Save changes")
        self._revert_button = ToolButton(FluentIcon.CANCEL, inspector_header)
        set_localized_tooltip(self._revert_button, "Discard changes")
        inspector_layout.addWidget(self._save_button)
        inspector_layout.addWidget(self._revert_button)
        right_layout.addWidget(inspector_header)
        self._editor = NumberedPromptEditorFrame(
            prompt_runtime_services=prompt_runtime_services,
            prompt_feature_profile=prompt_feature_profile,
            wheel_adjustment_mode=wheel_adjustment_mode,
            parent=right_card,
        )
        right_layout.addWidget(self._editor, 1)
        body_layout.addWidget(right_card, _EDITOR_PANE_STRETCH)
        self.viewLayout.addWidget(body, 1)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """Resize the modal content from the owner window before it is shown."""

        self._bind_size_owner_window()
        self._apply_owner_window_size()
        super().showEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Keep modal height in sync when the owner window is resized."""

        size_owner_window = getattr(self, "_size_owner_window", None)
        if watched is size_owner_window and event.type() == QEvent.Type.Resize:
            self._apply_owner_window_size()
        return bool(super().eventFilter(watched, event))

    def _bind_size_owner_window(self) -> None:
        """Install resize tracking on the top-level owner window."""

        owner_window = self._owner_window()
        if owner_window is self._size_owner_window:
            return
        if self._size_owner_window is not None:
            self._size_owner_window.removeEventFilter(self)
        self._size_owner_window = owner_window
        if self._size_owner_window is not None:
            self._size_owner_window.installEventFilter(self)

    def _owner_window(self) -> QWidget | None:
        """Return the top-level widget that should define modal height."""

        parent = cast(QWidget | None, self.parentWidget())
        if parent is None:
            return None
        window = parent.window()
        if isinstance(window, QWidget):
            return window
        return parent

    def _apply_owner_window_size(self) -> None:
        """Apply the modal width and a height equal to 90% of the owner window."""

        height_source = self._owner_window_height()
        target_height = max(
            _MODAL_MINIMUM_HEIGHT,
            int(round(height_source * _MODAL_OWNER_HEIGHT_FRACTION)),
        )
        self.widget.setFixedHeight(target_height)
        self.widget.setMinimumWidth(_MODAL_WIDTH)

    def _owner_window_height(self) -> int:
        """Return the current owner-window height or a screen fallback height."""

        owner_window = self._owner_window()
        if owner_window is not None and owner_window.height() > 0:
            return owner_window.height()
        screen = QApplication.primaryScreen()
        if screen is not None:
            return screen.availableGeometry().height()
        return max(_MODAL_MINIMUM_HEIGHT, self.widget.height())

    def _connect_signals(self) -> None:
        """Connect modal interaction signals."""

        self._apply_button.clicked.connect(self._apply_and_close)
        self._discard_button.clicked.connect(self.reject)
        self._save_button.clicked.connect(self._save_current)
        self._revert_button.clicked.connect(self._revert_current)
        self._editor.textChanged.connect(self._on_editor_text_changed)
        self._asset_list.currentItemChanged.connect(self._on_current_item_changed)
        self._asset_list.customContextMenuRequested.connect(self._show_context_menu)

    def _rebuild_asset_list(self, assets: tuple[ManagedTextAsset, ...]) -> None:
        """Rebuild the grouped left picker."""

        self._asset_list.clear()
        self._entries.clear()
        if not assets:
            item = QListWidgetItem(self._asset_list)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            label = CaptionLabel(self._empty_text, self._asset_list)
            label.setWordWrap(True)
            item.setSizeHint(label.sizeHint())
            self._asset_list.setItemWidget(item, label)
            return
        row_index = 0
        for group, grouped_assets in group_assets(assets):
            header_item = QListWidgetItem(self._asset_list)
            header_item.setData(HEADER_KIND_ROLE, "header")
            header_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            header = LocalizedCaptionLabel(
                app_text("%1 (%2)", group, len(grouped_assets)),
                self._asset_list,
            )
            header.setStyleSheet(
                f"QLabel{{color:{muted_text_color().name()}; font-weight: 700;}}"
            )
            header_item.setSizeHint(header.sizeHint())
            self._asset_list.setItemWidget(header_item, header)
            for asset in grouped_assets:
                item = QListWidgetItem(self._asset_list)
                item.setData(ASSET_ID_ROLE, asset.id)
                item.setData(STRIPE_ROLE, row_index)
                row = AssetRow(
                    asset,
                    parent=self._asset_list,
                )
                row.selected.connect(self._select_asset)
                item.setSizeHint(row.sizeHint())
                self._asset_list.setItemWidget(item, row)
                self._entries[asset.id] = AssetEntry(asset=asset, item=item, row=row)
                row_index += 1

    def _on_current_item_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        """Bind the asset selected in the left list."""

        if current is None:
            return
        asset_id = current.data(ASSET_ID_ROLE)
        if isinstance(asset_id, str):
            self._select_asset(asset_id)

    def _select_asset(self, asset_id: str | None) -> None:
        """Select and load one asset by id."""

        self._persist_current_text()
        self._current_asset_id = asset_id
        if asset_id is None:
            self._bind_empty_state()
            return
        entry = self._entries.get(asset_id)
        asset = self._assets.get(asset_id)
        if entry is None or asset is None:
            self._bind_empty_state()
            return
        self._asset_list.blockSignals(True)
        try:
            self._asset_list.setCurrentItem(entry.item)
        finally:
            self._asset_list.blockSignals(False)
        if asset_id not in self._original_text:
            try:
                text = self._service.read_asset_text(asset_id)
            except Exception as exc:
                self._report_error(
                    title=app_text("Unable to read asset"),
                    operation="wildcard_modal.read_asset",
                    error=exc,
                )
                text = ""
            self._original_text[asset_id] = text
            self._edited_text[asset_id] = text
        self._bind_asset(asset)
        self._set_editor_text(self._edited_text.get(asset_id, ""))
        self._update_save_button()

    def _bind_asset(self, asset: ManagedTextAsset) -> None:
        """Bind selected asset title to the right inspector."""

        self._asset_name.setText(asset.label)
        set_fluent_tooltip_text(self._asset_name, asset.label)
        self._editor.setEnabled(asset.editable)

    def _bind_empty_state(self) -> None:
        """Show the right-pane empty state."""

        set_localized_text(self._asset_name, "No selection")
        self._set_editor_text("")
        self._editor.setEnabled(False)
        self._save_button.setEnabled(False)
        self._revert_button.setEnabled(False)

    def _set_editor_text(self, text: str) -> None:
        """Set editor text without treating the assignment as a user edit."""

        self._updating_editor = True
        try:
            asset = (
                None
                if self._current_asset_id is None
                else self._assets.get(self._current_asset_id)
            )
            if asset is None or self._document_semantics_for_asset is None:
                self._editor.replaceBaselineSourceText(text)
            else:
                self._editor.replaceBaselineSourceDocument(
                    text,
                    self._document_semantics_for_asset(asset),
                )
        finally:
            self._updating_editor = False

    def _persist_current_text(self) -> None:
        """Store current editor text in the modal's in-memory edit buffer."""

        if self._current_asset_id is None or self._updating_editor:
            return
        self._edited_text[self._current_asset_id] = self._editor.toPlainText()

    def _on_editor_text_changed(self) -> None:
        """Track current text edits and refresh dirty controls."""

        if self._updating_editor or self._current_asset_id is None:
            return
        self._edited_text[self._current_asset_id] = self._editor.toPlainText()
        self._update_save_button()
        self._update_apply_button()

    def _save_current(self) -> None:
        """Persist the current asset text when it is dirty."""

        asset_id = self._current_asset_id
        if asset_id is None:
            return
        self._persist_current_text()
        edited_text = self._edited_text.get(asset_id, "")
        if edited_text == self._original_text.get(asset_id, ""):
            self._update_save_button()
            return
        try:
            asset = self._service.save_asset_text(asset_id, edited_text)
        except Exception as exc:
            self._report_error(
                title=app_text("Unable to save asset"),
                operation="wildcard_modal.save_asset",
                error=exc,
            )
            return
        self._assets[asset.id] = asset
        self._original_text[asset.id] = edited_text
        self._edited_text[asset.id] = edited_text
        self._update_save_button()
        self._update_apply_button()

    def _revert_current(self) -> None:
        """Discard unsaved text edits for the selected asset."""

        asset_id = self._current_asset_id
        if asset_id is None:
            return
        original = self._original_text.get(asset_id, "")
        self._edited_text[asset_id] = original
        self._set_editor_text(original)
        self._update_save_button()
        self._update_apply_button()

    def _apply_and_close(self) -> None:
        """Save staged text changes, then close on success."""

        self._persist_current_text()
        try:
            for asset_id, edited_text in self._edited_text.items():
                if edited_text == self._original_text.get(asset_id):
                    continue
                self._service.save_asset_text(asset_id, edited_text)
            self._service.refresh()
        except Exception as exc:
            self._report_error(
                title=app_text("Unable to apply changes"),
                operation="wildcard_modal.save",
                error=exc,
            )
            return
        self.saved.emit()
        self.accept()

    def _create_asset(self, action: ManagedTextAssetCreateAction) -> None:
        """Prompt for a label and create one asset."""

        label, accepted = QInputDialog.getText(
            self,
            action.label,
            "Name:",
        )
        if not accepted or not label.strip():
            return
        try:
            asset = self._service.create_asset(
                CreateManagedTextAssetRequest(
                    label=label.strip(),
                    kind=action.kind,
                    content=action.default_content,
                    category=action.category,
                )
            )
        except Exception as exc:
            self._report_error(
                title=app_text("Unable to create asset"),
                operation="wildcard_modal.create_asset",
                error=exc,
            )
            return
        self._pending_selection_id = asset.id
        self.reload()

    def _show_context_menu(self, position) -> None:  # type: ignore[no-untyped-def]
        """Show asset row context actions supported by the selected asset."""

        item = self._asset_list.itemAt(position)
        if item is None:
            return
        asset_id = item.data(ASSET_ID_ROLE)
        if not isinstance(asset_id, str):
            return
        asset = self._assets.get(asset_id)
        if asset is None:
            return
        entries: list[MenuItem] = []
        if asset.enabled is not None:
            entries.append(
                MenuItem(
                    "managed_text_asset.toggle_enabled",
                    app_text("Disable") if asset.enabled else app_text("Enable"),
                    callback=lambda: self._toggle_asset_enabled(asset),
                    icon=FluentIcon.PAUSE,
                )
            )
        if asset.can_rename:
            entries.append(
                MenuItem(
                    "managed_text_asset.rename",
                    app_text("Rename"),
                    callback=lambda: self._rename_asset(asset),
                    icon=FluentIcon.EDIT,
                )
            )
        if asset.can_delete:
            entries.append(
                MenuItem(
                    "managed_text_asset.delete",
                    app_text("Delete"),
                    callback=lambda: self._delete_asset(asset),
                    icon=FluentIcon.DELETE,
                )
            )
        if entries:
            menu = QFluentMenuRenderer(parent=self._asset_list).render(
                MenuModel(entries=tuple(entries))
            )
            menu.exec(self._asset_list.mapToGlobal(position))

    def _rename_asset(self, asset: ManagedTextAsset) -> None:
        """Prompt for a new label and rename one asset."""

        label, accepted = QInputDialog.getText(
            self,
            "Rename wildcard",
            "Name:",
            text=asset.label,
        )
        if not accepted or not label.strip() or label.strip() == asset.label:
            return
        try:
            renamed = self._service.rename_asset(
                RenameManagedTextAssetRequest(asset_id=asset.id, label=label.strip())
            )
        except Exception as exc:
            self._report_error(
                title=app_text("Unable to rename asset"),
                operation="wildcard_modal.rename_asset",
                error=exc,
            )
            return
        original_text = self._original_text.pop(asset.id, None)
        edited_text = self._edited_text.pop(asset.id, None)
        if original_text is not None:
            self._original_text[renamed.id] = original_text
        if edited_text is not None:
            self._edited_text[renamed.id] = edited_text
        self._pending_selection_id = renamed.id
        self.reload()

    def _toggle_asset_enabled(self, asset: ManagedTextAsset) -> None:
        """Toggle optional asset participation through its owning service."""

        if asset.enabled is None:
            return
        try:
            updated = self._service.set_asset_enabled(asset.id, not asset.enabled)
        except Exception as exc:
            self._report_error(
                title=app_text("Unable to update asset"),
                operation="managed_text_asset.toggle_enabled",
                error=exc,
            )
            return
        self._pending_selection_id = updated.id
        self.reload()

    def _delete_asset(self, asset: ManagedTextAsset) -> None:
        """Delete one asset after user confirmation."""

        answer = QMessageBox.question(
            self,
            translate_application_text("Delete wildcard"),
            translate_application_message("Delete '%1'?", asset.label),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.delete_asset(asset.id)
        except Exception as exc:
            self._report_error(
                title=app_text("Unable to delete asset"),
                operation="wildcard_modal.delete_asset",
                error=exc,
            )
            return
        self._original_text.pop(asset.id, None)
        self._edited_text.pop(asset.id, None)
        if self._current_asset_id == asset.id:
            self._current_asset_id = None
        self.reload()

    def _update_save_button(self) -> None:
        """Enable save and revert only when the selected text is dirty."""

        asset_id = self._current_asset_id
        is_dirty = asset_id is not None and self._edited_text.get(
            asset_id, ""
        ) != self._original_text.get(asset_id, "")
        self._save_button.setEnabled(is_dirty)
        self._revert_button.setEnabled(is_dirty)

    def _update_apply_button(self) -> None:
        """Enable Apply when text edits are staged."""

        has_text_changes = any(
            edited_text != self._original_text.get(asset_id)
            for asset_id, edited_text in self._edited_text.items()
        )
        self._apply_button.setEnabled(has_text_changes)

    def _report_error(self, *, title: str, operation: str, error: Exception) -> None:
        """Log and show one modal operation failure."""

        log_exception(
            _LOGGER,
            "Managed text asset modal operation failed.",
            operation=operation,
            error=repr(error),
        )
        localized_title = translate_application_text(title)
        self._resolved_error_presenter().show_exception_report(
            title=localized_title,
            message=translate_application_message("%1: %2", localized_title, error),
            stage="managed_text_assets",
            error=error,
            context=SubstituteOperationContext(
                operation=operation,
                values={
                    "asset_title": self._asset_title,
                    "current_asset_id": self._current_asset_id,
                    "edited_asset_count": len(self._edited_text),
                },
            ),
        )

    def _resolved_error_presenter(self) -> ErrorReportPresenterProtocol:
        """Return the injected presenter or lazily create one parented to this modal."""

        if self._error_presenter is None:
            self._error_presenter = ErrorPresenter(parent=self)
        return self._error_presenter


def _fallback_parent() -> QWidget:
    """Return a parent widget for qfluent dialogs opened without a caller."""

    global _FALLBACK_PARENT
    active_window = QApplication.activeWindow()
    if active_window is not None and isValid(active_window):
        return active_window
    if _FALLBACK_PARENT is None or not isValid(_FALLBACK_PARENT):
        _FALLBACK_PARENT = QWidget()
        _FALLBACK_PARENT.resize(1200, 800)
    return _FALLBACK_PARENT


__all__ = ["ManagedTextAssetCreateAction", "ManagedTextAssetModal"]
