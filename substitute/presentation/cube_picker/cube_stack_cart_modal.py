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

"""QFluent shopping-cart modal for editing a cube stack draft."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from time import perf_counter
from typing import Literal, Protocol, cast
from uuid import uuid4

from PySide6.QtCore import (
    QEvent,
    QEventLoop,
    QObject,
    QPoint,
    QPropertyAnimation,
    Qt,
)
from PySide6.QtGui import QCursor, QIcon, QKeyEvent, QMouseEvent, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    MessageBoxBase,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    SearchLineEdit,
    StrongBodyLabel,
    TitleLabel,
    ToolButton,
)

from substitute.application.cubes import (
    CubePickerClassification,
    CubePickerEntry,
    CubePickerModelRoleSection,
    CubeStackDraft,
    CubeStackDraftEntry,
    CubeStackDraftResult,
    build_cube_picker_model_role_sections,
    cube_stack_draft_entry_from_record,
    cube_stack_draft_result,
)
from substitute.application.ports import CubeCatalogRecord, CubeCatalogSnapshot
from substitute.presentation.cube_picker.cube_drag_controller import CubeDragController
from substitute.presentation.cube_picker.cube_drag_ghost import CubeDragGhost
from substitute.presentation.cube_picker.cube_picker_card import (
    CUBE_PICKER_CARD_HEIGHT,
    CUBE_PICKER_CARD_WIDTH,
    CubePickerCard,
)
from substitute.presentation.cube_picker.cube_staging_stack import (
    CubeDraftStack,
)
from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_STACK_EXPANDED_WIDTH,
)
from sugarsubstitute_shared.presentation.widgets.scrolling import (
    configure_qfluent_scroll_surface,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_info,
    log_timing,
)

_LOGGER = get_logger("presentation.cube_picker.stack_cart_modal")
_FALLBACK_PARENT: QWidget | None = None
_MODAL_MINIMUM_HEIGHT = 360
_MODAL_OWNER_HEIGHT_FRACTION = 0.88
_PANE_MARGIN = 0
_PANE_SPACING = 5
_BODY_SPACING = 8
_SCROLLBAR_ALLOWANCE = 18
_LIBRARY_SEARCH_MIN_WIDTH = CUBE_PICKER_CARD_WIDTH
_LIBRARY_MODEL_HEADER_HEIGHT = 28
_LIBRARY_ROLE_HEADER_HEIGHT = 18
_LIBRARY_RESULT_SPACING = 6
_LIBRARY_SECTION_GAP = 0
_CART_HEADER_HEIGHT = 20
_CART_DROP_ZONE_HEIGHT = 450
_CART_EMPTY_STATE_HEIGHT = 112
_FOOTER_GAP = 0
_CursorOverrideMode = Literal["active_drag"]
_CURSOR_FEEDBACK_EVENT_TYPES = {
    QEvent.Type.Enter,
    QEvent.Type.Leave,
    QEvent.Type.HoverEnter,
    QEvent.Type.HoverMove,
    QEvent.Type.HoverLeave,
    QEvent.Type.MouseButtonPress,
    QEvent.Type.MouseButtonRelease,
    QEvent.Type.MouseMove,
}


class CubePickerIconFactoryProtocol(Protocol):
    """Describe icon resolution used by cube picker cards."""

    def icon_for_cube(
        self,
        *,
        cube_id: str,
        display_name: str,
        icon: object | None,
        catalog_revision: str = "",
        cube_content_hash: str = "",
        render_size: int | None = None,
    ) -> object:
        """Return a Qt icon for one picker card."""


CubeCatalogRefreshCallback = Callable[[], CubeCatalogSnapshot]
CubePickerClassifyCallback = Callable[
    [list[CubeCatalogRecord]],
    Mapping[str, CubePickerClassification],
]


class CubeStackCartModal(MessageBoxBase):  # type: ignore[misc]
    """Edit the current cube stack as a QFluent cart-style modal."""

    def __init__(
        self,
        *,
        records: list[CubeCatalogRecord],
        icon_factory: CubePickerIconFactoryProtocol,
        refresh_catalog: CubeCatalogRefreshCallback | None = None,
        classifications: Mapping[str, CubePickerClassification] | None = None,
        classify_records: CubePickerClassifyCallback | None = None,
        initial_draft: CubeStackDraft | None = None,
        stack_anchor: QWidget | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build the cart modal around a catalog and initial stack draft."""

        modal_started_at = perf_counter()
        _ = stack_anchor
        self._cart_trace_id = uuid4().hex
        self._size_owner_window: QWidget | None = None
        log_info(
            _LOGGER,
            "Started cube cart modal construction",
            cart_trace_id=self._cart_trace_id,
            record_count=len(records),
            initial_entry_count=(
                len(initial_draft.entries) if initial_draft is not None else 0
            ),
            classification_count=len(classifications or {}),
            has_refresh_catalog=refresh_catalog is not None,
            has_classify_records=classify_records is not None,
        )
        phase_started_at = perf_counter()
        super().__init__(parent or _fallback_parent())
        log_timing(
            _LOGGER,
            "Cube cart modal super init completed",
            started_at=phase_started_at,
            cart_trace_id=self._cart_trace_id,
        )
        self._records = records
        self._records_by_id = {record.cube_id: record for record in records}
        self._icon_factory = icon_factory
        self._refresh_catalog = refresh_catalog
        self._classifications = dict(classifications or {})
        self._classify_records = classify_records
        self._initial_draft = initial_draft or CubeStackDraft(entries=())
        self._cards: dict[str, CubePickerCard] = {}
        self._ordered_card_keys: list[str] = []
        self._ordered_cube_ids: list[str] = self._ordered_card_keys
        self._selected_card_key: str | None = None
        self._drag_controller = CubeDragController()
        self._drag_ghost: CubeDragGhost | None = None
        self._drag_restore_entry: CubeStackDraftEntry | None = None
        self._drag_restore_index: int | None = None
        self._drag_restore_icon: QIcon | None = None
        self._staged_icons: dict[str, QIcon] = {}
        self._ghost_fade_animation: QPropertyAnimation | None = None
        self._drag_event_filter_installed = False
        self._drag_cursor_override_active = False
        self._cursor_override_mode: _CursorOverrideMode | None = None
        self._lifecycle_event_filter_installed = False
        self._app_event_filter_installed = False
        self._event_loop: QEventLoop | None = None
        self._result: CubeStackDraftResult | None = None
        self._visible_library_card_count = 0
        self._visible_library_section_count = 0
        self._visible_library_model_section_count = 0
        self._visible_library_role_section_count = 0
        self._library_show_empty_state = False

        phase_started_at = perf_counter()
        self._configure_modal()
        log_timing(
            _LOGGER,
            "Cube cart modal configure completed",
            started_at=phase_started_at,
            cart_trace_id=self._cart_trace_id,
        )
        phase_started_at = perf_counter()
        self._build_header()
        log_timing(
            _LOGGER,
            "Cube cart modal header build completed",
            started_at=phase_started_at,
            cart_trace_id=self._cart_trace_id,
        )
        phase_started_at = perf_counter()
        self._build_body()
        log_timing(
            _LOGGER,
            "Cube cart modal body build completed",
            started_at=phase_started_at,
            cart_trace_id=self._cart_trace_id,
        )
        phase_started_at = perf_counter()
        self._build_footer()
        log_timing(
            _LOGGER,
            "Cube cart modal footer build completed",
            started_at=phase_started_at,
            cart_trace_id=self._cart_trace_id,
        )
        phase_started_at = perf_counter()
        self._reset_draft_stack()
        log_timing(
            _LOGGER,
            "Cube cart modal draft stack reset completed",
            started_at=phase_started_at,
            cart_trace_id=self._cart_trace_id,
            initial_entry_count=len(self._initial_draft.entries),
            staged_icon_count=len(self._staged_icons),
        )
        phase_started_at = perf_counter()
        self._bind_size_owner_window()
        log_timing(
            _LOGGER,
            "Cube cart modal size owner bind completed",
            started_at=phase_started_at,
            cart_trace_id=self._cart_trace_id,
            has_size_owner=self._size_owner_window is not None,
        )
        phase_started_at = perf_counter()
        self._rebuild_results()
        log_timing(
            _LOGGER,
            "Cube cart modal initial results rebuild completed",
            started_at=phase_started_at,
            cart_trace_id=self._cart_trace_id,
            visible_card_count=self._visible_library_card_count,
            visible_section_count=self._visible_library_section_count,
        )
        phase_started_at = perf_counter()
        self._sync_actions()
        log_timing(
            _LOGGER,
            "Cube cart modal action sync completed",
            started_at=phase_started_at,
            cart_trace_id=self._cart_trace_id,
        )
        phase_started_at = perf_counter()
        self._apply_modal_size()
        log_timing(
            _LOGGER,
            "Cube cart modal size apply completed",
            started_at=phase_started_at,
            cart_trace_id=self._cart_trace_id,
            modal_width=self.width(),
            modal_height=self.height(),
        )
        log_info(
            _LOGGER,
            "Opened cube stack cart modal",
            cart_trace_id=self._cart_trace_id,
            initial_entry_count=len(self._initial_draft.entries),
            existing_entry_count=sum(
                1 for entry in self._initial_draft.entries if entry.source == "existing"
            ),
        )
        log_timing(
            _LOGGER,
            "Cube cart modal construction completed",
            started_at=modal_started_at,
            cart_trace_id=self._cart_trace_id,
            record_count=len(self._records),
            visible_card_count=self._visible_library_card_count,
            visible_section_count=self._visible_library_section_count,
            initial_entry_count=len(self._initial_draft.entries),
        )

    def edit_stack(self) -> CubeStackDraftResult | None:
        """Execute the modal and return the accepted stack draft."""

        edit_started_at = perf_counter()
        log_info(
            _LOGGER,
            "Started cube cart modal edit loop",
            cart_trace_id=self._cart_trace_id,
            record_count=len(self._records),
            visible_card_count=self._visible_library_card_count,
            visible_section_count=self._visible_library_section_count,
        )
        self._result = None
        phase_started_at = perf_counter()
        self.show()
        log_timing(
            _LOGGER,
            "Cube cart modal show returned",
            started_at=phase_started_at,
            cart_trace_id=self._cart_trace_id,
        )
        self._install_lifecycle_event_filter()
        self._search.setFocus()
        self._event_loop = QEventLoop()
        phase_started_at = perf_counter()
        self._event_loop.exec()
        log_timing(
            _LOGGER,
            "Cube cart modal event loop exited",
            started_at=phase_started_at,
            cart_trace_id=self._cart_trace_id,
            accepted=self._result is not None,
        )
        self._event_loop = None
        log_timing(
            _LOGGER,
            "Cube cart modal edit loop completed",
            started_at=edit_started_at,
            cart_trace_id=self._cart_trace_id,
            accepted=self._result is not None,
            result_entry_count=len(self._result.entries) if self._result else 0,
        )
        return self._result

    def stage_cubes(self) -> CubeStackDraftResult | None:
        """Compatibility wrapper returning the accepted draft result."""

        return self.edit_stack()

    def select_cube(self) -> CubeCatalogRecord | None:
        """Compatibility wrapper returning the first applied new cube record."""

        result = self.edit_stack()
        if result is None or result.is_empty:
            return None
        first_new_entry = next(
            (entry for entry in result.entries if entry.source == "new"),
            None,
        )
        if first_new_entry is None:
            return None
        return self._records_by_id.get(first_new_entry.cube_id)

    def set_records(
        self,
        records: list[CubeCatalogRecord],
        *,
        classifications: Mapping[str, CubePickerClassification] | None = None,
    ) -> None:
        """Replace visible catalog records while preserving selection if possible."""

        started_at = perf_counter()
        previous_selection = self._selected_card_key
        self._records = records
        self._records_by_id = {record.cube_id: record for record in records}
        self._classifications = dict(classifications or {})
        self._selected_card_key = previous_selection
        self._rebuild_results()
        log_timing(
            _LOGGER,
            "Cube cart modal records replaced",
            started_at=started_at,
            cart_trace_id=self._cart_trace_id,
            record_count=len(self._records),
            classification_count=len(self._classifications),
            visible_card_count=self._visible_library_card_count,
            visible_section_count=self._visible_library_section_count,
        )

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """Focus search and refresh owner-based sizing before showing."""

        self._bind_size_owner_window()
        self._apply_modal_size()
        super().showEvent(event)
        self._install_lifecycle_event_filter()
        self._search.setFocus()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Handle modal resize, keyboard navigation, and active drag events."""

        if event.type() in _CURSOR_FEEDBACK_EVENT_TYPES:
            self._sync_idle_cursor_feedback()
        size_owner_window = getattr(self, "_size_owner_window", None)
        if watched is size_owner_window and event.type() == QEvent.Type.Resize:
            self._apply_modal_size()
        search = getattr(self, "_search", None)
        if watched is search and event.type() == QEvent.Type.KeyPress:
            key_event = cast(QKeyEvent, event)
            if key_event.key() == Qt.Key.Key_Down:
                self._move_selection(1)
                return True
            if key_event.key() == Qt.Key.Key_Up:
                self._move_selection(-1)
                return True
        if event.type() == QEvent.Type.KeyPress:
            key_event = cast(QKeyEvent, event)
            if key_event.key() == Qt.Key.Key_Escape:
                if self._drag_controller.state is not None:
                    self._cancel_drag(restore=True)
                else:
                    self.reject()
                return True
        drag_controller = getattr(self, "_drag_controller", None)
        if (
            drag_controller is not None
            and drag_controller.state is not None
            and isinstance(event, QMouseEvent)
        ):
            if event.type() == QEvent.Type.MouseMove:
                self._move_drag(_event_global_pos(event))
                return True
            if (
                event.type() == QEvent.Type.MouseButtonRelease
                and event.button() == Qt.MouseButton.LeftButton
            ):
                self._finish_drag(_event_global_pos(event))
                return True
        return bool(super().eventFilter(watched, event))

    def accept(self) -> None:
        """Accept the current draft and close the modal."""

        self._result = cube_stack_draft_result(list(self._staging_stack.entries()))
        self._close_modal(int(QDialog.DialogCode.Accepted))

    def reject(self) -> None:
        """Reject the draft and close the modal."""

        if self._drag_controller.state is not None:
            self._cancel_drag(restore=True)
        self._result = None
        self._close_modal(int(QDialog.DialogCode.Rejected))

    def done(self, code: int) -> None:
        """Close synchronously to avoid dangling fade animations in modal tests."""

        self._clear_cursor_feedback()
        self._remove_lifecycle_event_filter()
        QDialog.done(self, code)

    def _close_modal(self, code: int) -> None:
        """Hide the modal and complete the active local event loop."""

        self._clear_cursor_feedback()
        self._remove_lifecycle_event_filter()
        self.hide()
        if self._event_loop is not None and self._event_loop.isRunning():
            self._event_loop.quit()
            return
        QDialog.done(self, code)

    def _configure_modal(self) -> None:
        """Apply standard QFluent modal setup for the cart picker."""

        self.setClosableOnMaskClicked(False)
        self.setModal(True)
        self.hideYesButton()
        self.hideCancelButton()
        self.buttonGroup.hide()
        self.buttonGroup.setFixedHeight(0)
        self.widget.setMinimumHeight(_MODAL_MINIMUM_HEIGHT)

    def _build_header(self) -> None:
        """Create modal title and top-level refresh/close controls."""

        header = QWidget(self.widget)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._title = TitleLabel("Add cubes", header)
        layout.addWidget(self._title, 1)

        self._refresh_button = ToolButton(FluentIcon.SYNC, header)
        self._refresh_button.setToolTip("Refresh catalog")
        self._refresh_button.setAccessibleName("Refresh catalog")
        self._refresh_button.clicked.connect(self._refresh_records)
        self._refresh_button.setEnabled(self._refresh_catalog is not None)
        layout.addWidget(self._refresh_button, 0)

        self._close_button = ToolButton(FluentIcon.CLOSE, header)
        self._close_button.setToolTip("Close")
        self._close_button.setAccessibleName("Close")
        self._close_button.clicked.connect(self.reject)
        layout.addWidget(self._close_button, 0)

        self.viewLayout.addWidget(header)

    def _build_body(self) -> None:
        """Create the full-width controls and two-column picker body."""

        self._body = QWidget(self.widget)
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(_PANE_SPACING)
        self._build_library_controls(self._body)
        self._columns = QWidget(self._body)
        self._columns_layout = QHBoxLayout(self._columns)
        self._columns_layout.setContentsMargins(0, 0, 0, 0)
        self._columns_layout.setSpacing(_BODY_SPACING)
        self._build_library_pane(self._columns)
        self._build_cart_pane(self._columns)
        self._columns_layout.addWidget(
            self._library_pane,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        self._columns_layout.addWidget(
            self._cart_pane,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        self._body_layout.addWidget(self._library_controls)
        self._body_layout.addWidget(self._columns)
        self.viewLayout.addWidget(self._body)

    def _build_library_controls(self, parent: QWidget) -> None:
        """Create the full-width library search and view controls."""

        self._library_controls = QWidget(parent)
        self._library_controls.setObjectName("cubePickerLibraryControls")
        layout = QVBoxLayout(self._library_controls)
        layout.setContentsMargins(
            _PANE_MARGIN, _PANE_MARGIN, _PANE_MARGIN, _PANE_MARGIN
        )
        layout.setSpacing(_PANE_SPACING)
        self._library_controls_layout = layout

        self._library_title: QWidget = StrongBodyLabel(
            "Cube library", self._library_controls
        )
        layout.addWidget(self._library_title)

        self._search = SearchLineEdit(self._library_controls)
        self._search.setPlaceholderText("Search cubes")
        self._search.setAccessibleName("Search cubes")
        self._search.setMinimumWidth(_LIBRARY_SEARCH_MIN_WIDTH)
        self._search.textChanged.connect(self._rebuild_results)
        self._search.installEventFilter(self)
        layout.addWidget(self._search)

        self._library_message_label = CaptionLabel("", self._library_controls)
        self._library_message_label.hide()
        layout.addWidget(self._library_message_label)

    def _build_library_pane(self, parent: QWidget) -> None:
        """Create the scrollable cube picker list pane."""

        self._library_pane = QWidget(parent)
        self._library_pane.setObjectName("cubePickerLibraryRegion")
        self._library_pane.setFixedWidth(self._library_pane_width())
        layout = QVBoxLayout(self._library_pane)
        layout.setContentsMargins(
            _PANE_MARGIN, _PANE_MARGIN, _PANE_MARGIN, _PANE_MARGIN
        )
        layout.setSpacing(0)
        self._library_layout = layout

        self._library_scroll = ScrollArea(self._library_pane)
        configure_qfluent_scroll_surface(self._library_scroll)
        self._library_scroll.setWidgetResizable(True)
        self._library_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._library_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._library_scroll.enableTransparentBackground()
        self._results = QWidget(self._library_scroll)
        self._results.setObjectName("cubePickerResults")
        self._results.setAutoFillBackground(False)
        self._results_layout = QVBoxLayout(self._results)
        self._results_layout.setContentsMargins(0, 0, 0, 0)
        self._results_layout.setSpacing(_LIBRARY_RESULT_SPACING)
        self._library_scroll.setWidget(self._results)
        self._library_scroll.setStyleSheet(
            """
            ScrollArea,
            QWidget#cubePickerResults {
                background: transparent;
                border: none;
            }
            """
        )
        layout.addWidget(self._library_scroll)

    def _build_cart_pane(self, parent: QWidget) -> None:
        """Create the current stack cart draft pane."""

        self._cart_pane = QWidget(parent)
        self._cart_pane.setObjectName("cubePickerStackRegion")
        self._cart_pane.setFixedWidth(self._cart_pane_width())
        layout = QVBoxLayout(self._cart_pane)
        layout.setContentsMargins(
            _PANE_MARGIN, _PANE_MARGIN, _PANE_MARGIN, _PANE_MARGIN
        )
        layout.setSpacing(_LIBRARY_RESULT_SPACING)
        self._cart_layout = layout

        header = QWidget(self._cart_pane)
        self._cart_header = header
        header.setFixedHeight(_CART_HEADER_HEIGHT)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        title = StrongBodyLabel("Cube stack", header)
        header_layout.addWidget(title, 0)
        header_layout.addStretch(1)
        layout.addWidget(header)

        self._cart_scroll = ScrollArea(self._cart_pane)
        configure_qfluent_scroll_surface(self._cart_scroll)
        self._cart_scroll.setWidgetResizable(True)
        self._cart_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._cart_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._cart_scroll.enableTransparentBackground()
        self._cart_scroll_content = QWidget(self._cart_scroll)
        self._cart_scroll_content.setObjectName("cubePickerCartScrollContent")
        self._cart_scroll_content.setAutoFillBackground(False)
        cart_content_layout = QVBoxLayout(self._cart_scroll_content)
        cart_content_layout.setContentsMargins(0, 0, 0, 0)
        cart_content_layout.setSpacing(0)
        self._staging_stack = CubeDraftStack(self._cart_scroll_content)
        self._staging_stack.staged_drag_started.connect(self._begin_staged_drag)
        self._staging_stack.staged_drag_moved.connect(self._move_drag)
        self._staging_stack.staged_drag_finished.connect(self._finish_drag)
        self._staging_stack.remove_requested.connect(self._remove_staged_cube)
        cart_content_layout.addWidget(self._staging_stack)
        self._cart_scroll.setWidget(self._cart_scroll_content)
        self._cart_scroll.setStyleSheet(
            """
            ScrollArea,
            QWidget#cubePickerCartScrollContent {
                background: transparent;
                border: none;
            }
            """
        )
        layout.addWidget(self._cart_scroll)

    def _build_footer(self) -> None:
        """Create Reset, Cancel, and Apply modal actions."""

        footer = QWidget(self.widget)
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addStretch(1)

        self._clear_button = PushButton("Reset", footer)
        self._clear_button.clicked.connect(self._reset_draft_stack)
        layout.addWidget(self._clear_button)

        self._cancel_button = PushButton("Cancel", footer)
        self._cancel_button.clicked.connect(self.reject)
        layout.addWidget(self._cancel_button)

        self._apply_button = PrimaryPushButton("Apply", footer)
        self._apply_button.clicked.connect(self.accept)
        layout.addWidget(self._apply_button)
        self._footer = footer
        self.viewLayout.addWidget(footer)

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
        """Return the widget that should define modal sizing."""

        parent = cast(QWidget | None, self.parentWidget())
        if parent is None:
            return None
        window = parent.window()
        return window if isinstance(window, QWidget) else parent

    def _apply_modal_size(self) -> None:
        """Apply content-sized modal and pane geometry."""

        library_scroll_height = self._library_scroll_height()
        cart_scroll_height = self._cart_scroll_height()
        cart_scroll_content_height = max(
            cart_scroll_height,
            self._cart_content_height(),
        )
        self._library_controls.setFixedSize(
            self._body_width(),
            self._library_controls_height(),
        )
        self._search.setFixedWidth(self._body_width())
        self._library_message_label.setFixedWidth(self._body_width())
        self._library_scroll.setFixedSize(
            self._library_scroll_width(),
            library_scroll_height,
        )
        self._results.setFixedSize(
            self._library_content_width(),
            self._library_content_height(),
        )
        self._cart_scroll.setFixedSize(
            self._cart_scroll_width(),
            cart_scroll_height,
        )
        self._staging_stack.setFixedWidth(self._cart_content_width())
        self._staging_stack.setFixedHeight(
            max(cart_scroll_height, self._cart_content_height())
        )
        self._cart_scroll_content.setFixedSize(
            self._cart_content_width(),
            cart_scroll_content_height,
        )
        self._library_pane.setFixedSize(
            self._library_pane_width(),
            self._library_pane_height(library_scroll_height),
        )
        self._cart_pane.setFixedSize(
            self._cart_pane_width(),
            self._cart_pane_height(cart_scroll_height),
        )
        self._columns.setFixedSize(
            self._body_width(),
            self._columns_height(),
        )
        self._body.setFixedSize(
            self._body_width(),
            self._body_height(),
        )
        self.widget.setFixedSize(
            self._modal_content_width(),
            self._modal_content_height(),
        )

    def _library_content_width(self) -> int:
        """Return list content width for one-column library cards."""

        return max(CUBE_PICKER_CARD_WIDTH, _LIBRARY_SEARCH_MIN_WIDTH)

    def _cart_content_width(self) -> int:
        """Return cart content width from stack card metrics."""

        return CUBE_STACK_EXPANDED_WIDTH

    def _library_pane_width(self) -> int:
        """Return library pane width including margins and scrollbar allowance."""

        return self._library_content_width() + (_PANE_MARGIN * 2) + _SCROLLBAR_ALLOWANCE

    def _cart_pane_width(self) -> int:
        """Return cart pane width including margins and scrollbar allowance."""

        return self._cart_content_width() + (_PANE_MARGIN * 2) + _SCROLLBAR_ALLOWANCE

    def _library_scroll_width(self) -> int:
        """Return library scroll surface width including its scrollbar gutter."""

        return self._library_content_width() + _SCROLLBAR_ALLOWANCE

    def _cart_scroll_width(self) -> int:
        """Return cart scroll surface width including its scrollbar gutter."""

        return self._cart_content_width() + _SCROLLBAR_ALLOWANCE

    def _modal_content_width(self) -> int:
        """Return modal width from pane widths and modal margins."""

        margins = self.viewLayout.contentsMargins()
        return int(margins.left()) + self._body_width() + int(margins.right())

    def _body_width(self) -> int:
        """Return total two-pane body width."""

        return self._library_pane_width() + _BODY_SPACING + self._cart_pane_width()

    def _body_height(self) -> int:
        """Return full body height including controls and columns."""

        return (
            self._library_controls_height()
            + int(self._body_layout.spacing())
            + self._columns_height()
        )

    def _columns_height(self) -> int:
        """Return shared height for the picker and stack columns."""

        return max(self._library_pane.height(), self._cart_pane.height())

    def _library_content_height(self) -> int:
        """Return deterministic height for visible library result content."""

        if self._library_show_empty_state:
            return 120
        item_count = (
            self._visible_library_card_count + self._visible_library_section_count
        )
        if item_count == 0:
            return 0
        return (
            (self._visible_library_card_count * CUBE_PICKER_CARD_HEIGHT)
            + (self._visible_library_model_section_count * _LIBRARY_MODEL_HEADER_HEIGHT)
            + (self._visible_library_role_section_count * _LIBRARY_ROLE_HEADER_HEIGHT)
            + (max(0, item_count - 1) * _LIBRARY_RESULT_SPACING)
            + max(0, self._visible_library_section_count - 1) * _LIBRARY_SECTION_GAP
        )

    def _cart_content_height(self) -> int:
        """Return deterministic height for current cart draft content."""

        return self._staging_stack.preferred_height()

    def _library_scroll_height(self) -> int:
        """Return visible picker viewport height for library results."""

        return self._base_scroll_height()

    def _cart_scroll_height(self) -> int:
        """Return cart viewport height below the stack header."""

        return max(
            _CART_EMPTY_STATE_HEIGHT,
            self._base_scroll_height() - self._cart_header_area_height(),
        )

    def _base_scroll_height(self) -> int:
        """Return the stable modal pane viewport height."""

        return min(_CART_DROP_ZONE_HEIGHT, self._max_scroll_height())

    def _max_scroll_height(self) -> int:
        """Return the owner-height cap available to individual scroll panes."""

        available = self._available_modal_height()
        modal_chrome = self._modal_content_height_without_body()
        return max(160, available - modal_chrome)

    def _available_modal_height(self) -> int:
        """Return owner-based modal height maximum."""

        return max(
            _MODAL_MINIMUM_HEIGHT,
            int(round(self._owner_window_height() * _MODAL_OWNER_HEIGHT_FRACTION)),
        )

    def _modal_content_height(self) -> int:
        """Return content-sized modal height."""

        return min(
            self._available_modal_height(),
            max(
                _MODAL_MINIMUM_HEIGHT,
                self._modal_content_height_without_body() + self._body.height(),
            ),
        )

    def _modal_content_height_without_body(self) -> int:
        """Return modal height contribution outside the body panes."""

        margins = self.viewLayout.contentsMargins()
        return (
            int(margins.top())
            + _widget_hint_height(self._title)
            + int(self.viewLayout.spacing())
            + int(self.viewLayout.spacing())
            + _widget_hint_height(self._footer)
            + int(margins.bottom())
            + _FOOTER_GAP
        )

    def _library_controls_height(self) -> int:
        """Return height for controls above both picker columns."""

        margins = self._library_controls_layout.contentsMargins()
        return (
            int(margins.top())
            + _widget_hint_height(self._library_title)
            + int(self._library_controls_layout.spacing())
            + _widget_hint_height(self._search)
            + self._library_message_height()
            + int(margins.bottom())
        )

    def _library_pane_height(self, scroll_height: int) -> int:
        """Return library pane height for one result scroll height."""

        margins = self._library_layout.contentsMargins()
        return int(margins.top()) + scroll_height + int(margins.bottom())

    def _library_message_height(self) -> int:
        """Return message-label height only when an actionable message is visible."""

        if self._library_message_label.isHidden():
            return 0
        return int(self._library_controls_layout.spacing()) + _widget_hint_height(
            self._library_message_label
        )

    def _cart_header_area_height(self) -> int:
        """Return stack header height plus the card-row gap below it."""

        return _widget_hint_height(self._cart_header) + int(self._cart_layout.spacing())

    def _cart_pane_height(self, scroll_height: int) -> int:
        """Return cart pane height for one cart scroll height."""

        margins = self._cart_layout.contentsMargins()
        return (
            int(margins.top())
            + self._cart_header_area_height()
            + scroll_height
            + int(margins.bottom())
        )

    def _section_header_height(self) -> int:
        """Return legacy role-section header height used for content metrics."""

        return _LIBRARY_ROLE_HEADER_HEIGHT

    def _model_header_height(self) -> int:
        """Return model section header height used for content metrics."""

        return _LIBRARY_MODEL_HEADER_HEIGHT

    def _role_header_height(self) -> int:
        """Return role subsection header height used for content metrics."""

        return _LIBRARY_ROLE_HEADER_HEIGHT

    def _library_result_spacing(self) -> int:
        """Return spacing between library result rows."""

        return _LIBRARY_RESULT_SPACING

    def _section_gap(self) -> int:
        """Return extra spacing between library sections."""

        return _LIBRARY_SECTION_GAP

    def _owner_window_height(self) -> int:
        """Return owner height or a screen fallback."""

        owner_window = self._owner_window()
        if owner_window is not None and owner_window.height() > 0:
            return owner_window.height()
        screen = QApplication.primaryScreen()
        if screen is not None:
            return screen.availableGeometry().height()
        return max(_MODAL_MINIMUM_HEIGHT, self.widget.height())

    def _rebuild_results(self) -> None:
        """Rebuild library section headers and cards for search and view state."""

        started_at = perf_counter()
        search_text = self._search.text()
        phase_started_at = perf_counter()
        removed_count = self._clear_results()
        clear_elapsed_ms = _elapsed_ms(phase_started_at)
        self._cards.clear()
        self._ordered_card_keys.clear()
        phase_started_at = perf_counter()
        sections = build_cube_picker_model_role_sections(
            self._records,
            classifications=self._classifications,
            search_text=search_text,
        )
        section_elapsed_ms = _elapsed_ms(phase_started_at)
        visible_count = sum(
            len(role_section.entries)
            for section in sections
            for role_section in section.role_sections
        )
        if visible_count == 0:
            self._visible_library_card_count = 0
            self._visible_library_section_count = 0
            self._visible_library_model_section_count = 0
            self._visible_library_role_section_count = 0
            self._library_show_empty_state = True
            phase_started_at = perf_counter()
            self._add_empty_state()
            add_sections_elapsed_ms = _elapsed_ms(phase_started_at)
        else:
            self._visible_library_card_count = visible_count
            self._visible_library_model_section_count = len(sections)
            self._visible_library_role_section_count = sum(
                len(section.role_sections) for section in sections
            )
            self._visible_library_section_count = (
                self._visible_library_model_section_count
                + self._visible_library_role_section_count
            )
            self._library_show_empty_state = False
            phase_started_at = perf_counter()
            for section in sections:
                self._add_model_role_section(section)
            add_sections_elapsed_ms = _elapsed_ms(phase_started_at)
        if self._selected_card_key not in self._cards:
            self._selected_card_key = (
                self._ordered_card_keys[0] if self._ordered_card_keys else None
            )
        phase_started_at = perf_counter()
        self._sync_card_selection()
        sync_selection_elapsed_ms = _elapsed_ms(phase_started_at)
        self._sync_library_message_from_results(visible_count)
        message_elapsed_ms = _elapsed_ms(phase_started_at)
        phase_started_at = perf_counter()
        self._apply_modal_size()
        size_elapsed_ms = _elapsed_ms(phase_started_at)
        log_timing(
            _LOGGER,
            "Cube cart modal results rebuild completed",
            started_at=started_at,
            cart_trace_id=self._cart_trace_id,
            record_count=len(self._records),
            grouping_mode="model_role",
            search_text_length=len(search_text),
            classification_count=len(self._classifications),
            section_count=len(sections),
            visible_count=visible_count,
            visible_card_count=self._visible_library_card_count,
            visible_section_count=self._visible_library_section_count,
            visible_model_section_count=self._visible_library_model_section_count,
            visible_role_section_count=self._visible_library_role_section_count,
            removed_widget_count=removed_count,
            clear_elapsed_ms=f"{clear_elapsed_ms:.3f}",
            section_elapsed_ms=f"{section_elapsed_ms:.3f}",
            add_sections_elapsed_ms=f"{add_sections_elapsed_ms:.3f}",
            sync_selection_elapsed_ms=f"{sync_selection_elapsed_ms:.3f}",
            message_elapsed_ms=f"{message_elapsed_ms:.3f}",
            size_elapsed_ms=f"{size_elapsed_ms:.3f}",
        )

    def _clear_results(self) -> int:
        """Remove all library result widgets."""

        removed_count = 0
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                removed_count += 1
                widget.deleteLater()
        return removed_count

    def _add_empty_state(self) -> None:
        """Show a compact library empty state."""

        text = "No cubes available" if not self._records else "No matching cubes"
        label = BodyLabel(text, self._results)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setMinimumHeight(120)
        self._results_layout.addWidget(label)

    def _add_model_role_section(self, section: CubePickerModelRoleSection) -> None:
        """Add one model section with role subsections and cube cards."""

        if not section.role_sections:
            return
        self._results_layout.addWidget(self._create_model_section_header(section.title))
        for role_section in section.role_sections:
            role_header = CaptionLabel(role_section.title, self._results)
            role_header.setFixedHeight(_LIBRARY_ROLE_HEADER_HEIGHT)
            role_header.setStyleSheet("font-weight: 700;")
            self._results_layout.addWidget(role_header)
            for entry in role_section.entries:
                self._add_card(entry, card_key=self._card_key(section, entry))

    def _card_key(
        self, section: CubePickerModelRoleSection, entry: CubePickerEntry
    ) -> str:
        """Return a stable card key while preserving cube-id keys when unique."""

        if entry.cube_id not in self._cards:
            return entry.cube_id
        return f"{section.key}\x1f{entry.cube_id}"

    def _create_model_section_header(self, title: str) -> QWidget:
        """Return a centered model title with WinUI-style divider rules."""

        header = QWidget(self._results)
        header.setObjectName("cubePickerModelHeader")
        header.setFixedHeight(_LIBRARY_MODEL_HEADER_HEIGHT)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._create_model_section_rule(header), 1)
        label = StrongBodyLabel(title, header)
        label.setObjectName("cubePickerModelHeaderTitle")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label, 0)
        layout.addWidget(self._create_model_section_rule(header), 1)
        return header

    def _create_model_section_rule(self, parent: QWidget) -> QFrame:
        """Return one subtle divider rule for a model section header."""

        rule = QFrame(parent)
        rule.setObjectName("cubePickerModelHeaderRule")
        rule.setFrameShape(QFrame.Shape.HLine)
        rule.setFrameShadow(QFrame.Shadow.Plain)
        rule.setFixedHeight(1)
        rule.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        rule.setStyleSheet(
            """
            QFrame#cubePickerModelHeaderRule {
                border: none;
                background: rgba(96, 96, 96, 82);
            }
            """
        )
        return rule

    def _add_card(self, entry: CubePickerEntry, *, card_key: str) -> None:
        """Add one cube library card."""

        started_at = perf_counter()
        icon_started_at = perf_counter()
        icon = self._icon_for_entry(entry)
        icon_elapsed_ms = _elapsed_ms(icon_started_at)
        card_started_at = perf_counter()
        card = CubePickerCard(entry, icon=icon, parent=self._results)
        card_elapsed_ms = _elapsed_ms(card_started_at)
        bind_started_at = perf_counter()
        card.activated.connect(self._stage_cube_from_library)
        card.drag_started.connect(self._begin_library_drag)
        card.drag_moved.connect(self._move_drag)
        card.drag_finished.connect(self._finish_drag)
        bind_elapsed_ms = _elapsed_ms(bind_started_at)
        self._cards[card_key] = card
        self._ordered_card_keys.append(card_key)
        layout_started_at = perf_counter()
        self._results_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignLeft)
        log_timing(
            _LOGGER,
            "Cube cart modal library card added",
            started_at=started_at,
            cart_trace_id=self._cart_trace_id,
            cube_id=entry.cube_id,
            display_name=entry.display_name,
            card_key=card_key,
            card_index=len(self._ordered_card_keys) - 1,
            icon_elapsed_ms=f"{icon_elapsed_ms:.3f}",
            card_elapsed_ms=f"{card_elapsed_ms:.3f}",
            bind_elapsed_ms=f"{bind_elapsed_ms:.3f}",
            layout_elapsed_ms=f"{_elapsed_ms(layout_started_at):.3f}",
        )

    def _move_selection(self, delta: int) -> None:
        """Move keyboard selection through visible library cards."""

        if not self._ordered_card_keys:
            return
        if self._selected_card_key not in self._ordered_card_keys:
            next_index = 0
        else:
            current_index = self._ordered_card_keys.index(self._selected_card_key)
            next_index = max(
                0,
                min(len(self._ordered_card_keys) - 1, current_index + delta),
            )
        self._selected_card_key = self._ordered_card_keys[next_index]
        self._sync_card_selection()
        self._cards[self._selected_card_key].setFocus()

    def _sync_card_selection(self) -> None:
        """Synchronize selected state into library cards."""

        for card_key, card in self._cards.items():
            card.set_selected(card_key == self._selected_card_key)

    def _stage_cube_from_library(self, cube_id: str) -> None:
        """Stage one new cube copy at the end of the cart stack."""

        record = self._records_by_id.get(cube_id)
        if record is None:
            return
        entry = cube_stack_draft_entry_from_record(record)
        icon = self._icon_for_staging_entry(entry)
        self._staged_icons[entry.draft_id] = icon
        self._staging_stack.insert_entry(
            len(self._staging_stack.entries()),
            entry,
            icon,
        )
        self._sync_actions()

    def _remove_staged_cube(self, staged_id: str) -> None:
        """Remove one draft entry from the cart by temporary id."""

        removed = self._staging_stack.remove_staged_id(staged_id)
        if removed is not None:
            self._staged_icons.pop(removed.draft_id, None)
        self._sync_actions()

    def _reset_draft_stack(self) -> None:
        """Reset the cart draft to the stack state captured on open."""

        entries = list(self._initial_draft.entries)
        icons = {
            entry.draft_id: self._icon_for_staging_entry(entry) for entry in entries
        }
        self._staging_stack.set_entries(entries, icons=icons)
        self._staged_icons = icons
        self._sync_actions()

    def _begin_library_drag(self, cube_id: str, global_pos: object) -> None:
        """Begin dragging a copy from the library into the cart."""

        record = self._records_by_id.get(cube_id)
        if record is None or not isinstance(global_pos, QPoint):
            return
        entry = cube_stack_draft_entry_from_record(record)
        icon = self._icon_for_staging_entry(entry)
        self._drag_controller.begin(source="library", entry=entry)
        self._begin_drag_cursor_feedback()
        self._show_drag_ghost(entry=entry, icon=icon, global_pos=global_pos)
        self._move_drag(global_pos)

    def _begin_staged_drag(self, staged_id: str, global_pos: object) -> None:
        """Begin moving or removing an existing cart draft cube."""

        if not isinstance(global_pos, QPoint):
            return
        current_entries = list(self._staging_stack.entries())
        entry = self._staging_stack.staged_entry(staged_id)
        if entry is None:
            return
        self._drag_restore_index = current_entries.index(entry)
        self._drag_restore_entry = entry
        self._drag_restore_icon = self._staged_icons.get(staged_id, QIcon())
        self._staging_stack.remove_staged_id(staged_id)
        self._drag_controller.begin(
            source="draft_stack",
            entry=entry,
            source_draft_id=staged_id,
        )
        self._begin_drag_cursor_feedback()
        self._show_drag_ghost(
            entry=entry,
            icon=self._drag_restore_icon or QIcon(),
            global_pos=global_pos,
        )
        self._move_drag(global_pos)

    def _move_drag(self, global_pos: object) -> None:
        """Move the drag ghost and update the cart insertion placeholder."""

        if not isinstance(global_pos, QPoint):
            return
        state = self._drag_controller.state
        if state is None:
            self._end_drag_cursor_feedback()
            return
        if self._drag_ghost is not None:
            self._drag_ghost.move_to_global(global_pos)
        insertion_index = self._staging_stack.insertion_index_at_global_pos(global_pos)
        self._drag_controller.update_insertion_index(insertion_index)
        self._staging_stack.set_placeholder_index(insertion_index)

    def _finish_drag(self, global_pos: object) -> None:
        """Commit a drop into the cart stack or remove/cancel it."""

        if isinstance(global_pos, QPoint):
            self._move_drag(global_pos)
        state = self._drag_controller.state
        if state is None:
            return
        insertion_index = state.insertion_index
        if insertion_index is not None:
            icon = (
                self._drag_restore_icon
                if state.source == "draft_stack"
                else self._icon_for_staging_entry(state.entry)
            )
            self._staged_icons[state.entry.draft_id] = icon or QIcon()
            self._staging_stack.insert_entry(
                insertion_index,
                state.entry,
                icon or QIcon(),
            )
        elif state.source == "draft_stack":
            self._staged_icons.pop(state.entry.draft_id, None)
        self._cancel_drag(
            restore=False,
            fade_ghost=state.source == "draft_stack" and insertion_index is None,
        )
        self._sync_actions()

    def _cancel_drag(self, *, restore: bool, fade_ghost: bool = False) -> None:
        """Clear drag presentation and optionally restore a draft item."""

        state = self._drag_controller.state
        if (
            restore
            and state is not None
            and state.source == "draft_stack"
            and self._drag_restore_entry is not None
            and self._drag_restore_index is not None
        ):
            icon = self._drag_restore_icon or QIcon()
            self._staged_icons[self._drag_restore_entry.draft_id] = icon
            self._staging_stack.insert_entry(
                self._drag_restore_index,
                self._drag_restore_entry,
                icon,
            )
        self._drag_controller.cancel()
        self._end_drag_cursor_feedback()
        self._staging_stack.set_placeholder_index(None)
        if self._drag_ghost is not None:
            if fade_ghost:
                self._fade_drag_ghost_out(self._drag_ghost)
            else:
                self._drag_ghost.deleteLater()
            self._drag_ghost = None
        self._remove_drag_event_filter()
        self._drag_restore_entry = None
        self._drag_restore_index = None
        self._drag_restore_icon = None
        self._sync_actions()

    def _begin_drag_cursor_feedback(self) -> None:
        """Show modal-owned cursor feedback during an active cube drag."""

        self._drag_cursor_override_active = True
        self._set_cursor_override_mode("active_drag")

    def _end_drag_cursor_feedback(self) -> None:
        """Restore cursor feedback owned by this modal drag session."""

        if not self._drag_cursor_override_active:
            return
        self._drag_cursor_override_active = False
        self._sync_idle_cursor_feedback()

    def _sync_idle_cursor_feedback(self) -> None:
        """Clear modal-owned cursor feedback when no drag is active."""

        if self._drag_cursor_override_active or self._drag_controller.state is not None:
            return
        mode = self._idle_cursor_override_mode_for_widget(
            QApplication.widgetAt(QCursor.pos())
        )
        self._set_cursor_override_mode(mode)

    def _idle_cursor_override_mode_for_widget(
        self,
        widget: QWidget | None,
    ) -> _CursorOverrideMode | None:
        """Return idle cursor mode for the actual modal hit-test widget."""

        _ = widget
        return None

    def _set_cursor_override_mode(
        self,
        mode: _CursorOverrideMode | None,
    ) -> None:
        """Set the single application cursor override owned by this modal."""

        if self._cursor_override_mode == mode:
            return
        if mode is None:
            if self._cursor_override_mode is not None:
                QApplication.restoreOverrideCursor()
            self._cursor_override_mode = None
            return
        cursor = QCursor(_cursor_shape_for_mode(mode))
        if self._cursor_override_mode is None:
            QApplication.setOverrideCursor(cursor)
        else:
            QApplication.changeOverrideCursor(cursor)
        self._cursor_override_mode = mode

    def _clear_cursor_feedback(self) -> None:
        """Clear any cursor override owned by this modal."""

        self._drag_cursor_override_active = False
        self._set_cursor_override_mode(None)

    def _fade_drag_ghost_out(self, ghost: CubeDragGhost) -> None:
        """Fade a removed draft cube away after it is dragged out."""

        effect = QGraphicsOpacityEffect(ghost)
        ghost.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", ghost)
        animation.setDuration(110)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.finished.connect(ghost.deleteLater)
        self._ghost_fade_animation = animation
        animation.start()

    def _show_drag_ghost(
        self,
        *,
        entry: CubeStackDraftEntry,
        icon: QIcon,
        global_pos: QPoint,
    ) -> None:
        """Create and show the held stack-sized cube card."""

        if self._drag_ghost is not None:
            self._drag_ghost.deleteLater()
        self._drag_ghost = CubeDragGhost(
            entry=entry,
            icon=icon,
            parent=self.widget,
        )
        self._install_drag_event_filter()
        self._drag_ghost.move_to_global(global_pos)
        self._drag_ghost.show()
        self._drag_ghost.raise_()

    def _install_lifecycle_event_filter(self) -> None:
        """Capture global keyboard input while the modal is open."""

        if self._lifecycle_event_filter_installed:
            return
        self._lifecycle_event_filter_installed = True
        self._ensure_app_event_filter()

    def _remove_lifecycle_event_filter(self) -> None:
        """Stop capturing global keyboard input for the modal lifecycle."""

        if not self._lifecycle_event_filter_installed:
            return
        self._lifecycle_event_filter_installed = False
        self._release_app_event_filter_if_unused()

    def _install_drag_event_filter(self) -> None:
        """Capture drag move/release even when the source card is rebuilt."""

        if self._drag_event_filter_installed:
            return
        self._drag_event_filter_installed = True
        self._ensure_app_event_filter()

    def _remove_drag_event_filter(self) -> None:
        """Stop capturing global mouse events for a completed drag."""

        if not self._drag_event_filter_installed:
            return
        self._drag_event_filter_installed = False
        self._release_app_event_filter_if_unused()

    def _ensure_app_event_filter(self) -> None:
        """Install the modal as an application-level event filter once."""

        if self._app_event_filter_installed:
            return
        app = QApplication.instance()
        if app is None:
            return
        app.installEventFilter(self)
        self._app_event_filter_installed = True

    def _release_app_event_filter_if_unused(self) -> None:
        """Remove the application event filter when no modal path needs it."""

        if (
            not self._app_event_filter_installed
            or self._drag_event_filter_installed
            or self._lifecycle_event_filter_installed
        ):
            return
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._app_event_filter_installed = False

    def _refresh_records(self) -> None:
        """Refresh catalog data in place when a refresh callback is available."""

        if self._refresh_catalog is None:
            return
        self._refresh_button.setEnabled(False)
        self._set_library_message("Refreshing...")
        try:
            snapshot = self._refresh_catalog()
        except Exception as error:
            log_exception(
                _LOGGER,
                "Cube stack cart modal refresh failed",
                error=error,
            )
            self._set_library_message("Unable to refresh catalog")
            return
        finally:
            self._refresh_button.setEnabled(True)
        classifications = (
            dict(self._classify_records(snapshot.entries))
            if self._classify_records is not None
            else {}
        )
        self.set_records(snapshot.entries, classifications=classifications)
        if snapshot.error:
            self._set_library_message(snapshot.error)
        elif snapshot.state == "stale":
            self._set_library_message("Showing stale catalog")
        else:
            self._set_library_message(None)

    def _set_library_message(self, text: str | None) -> None:
        """Show actionable library status without normal count metadata."""

        message = text or ""
        self._library_message_label.setText(message)
        self._library_message_label.setVisible(bool(message))
        self._apply_modal_size()

    def _sync_library_message_from_results(self, visible_count: int) -> None:
        """Show only actionable result messages for the current catalog."""

        _ = visible_count
        self._set_library_message(None)

    def _sync_actions(self) -> None:
        """Enable actions from draft stack state."""

        result = cube_stack_draft_result(list(self._staging_stack.entries()))
        has_changes = result.has_changes_from(self._initial_draft)
        self._apply_button.setEnabled(has_changes)
        self._clear_button.setEnabled(has_changes)
        self._apply_modal_size()

    def _icon_for_entry(self, entry: CubePickerEntry) -> QIcon:
        """Resolve one library card icon."""

        started_at = perf_counter()
        icon = cast(
            QIcon,
            self._icon_factory.icon_for_cube(
                cube_id=entry.cube_id,
                display_name=entry.display_name,
                icon=entry.icon,
                catalog_revision=entry.catalog_revision,
                cube_content_hash=entry.content_hash,
            ),
        )
        log_timing(
            _LOGGER,
            "Cube cart modal library icon resolved",
            started_at=started_at,
            cart_trace_id=self._cart_trace_id,
            cube_id=entry.cube_id,
            display_name=entry.display_name,
            has_descriptor=entry.icon is not None,
            icon_null=icon.isNull(),
        )
        return icon

    def _icon_for_staging_entry(self, entry: CubeStackDraftEntry) -> QIcon:
        """Resolve one cart draft card icon."""

        started_at = perf_counter()
        icon = cast(
            QIcon,
            self._icon_factory.icon_for_cube(
                cube_id=entry.cube_id,
                display_name=entry.display_name,
                icon=entry.icon,
                catalog_revision=entry.catalog_revision,
                cube_content_hash=entry.content_hash,
            ),
        )
        log_timing(
            _LOGGER,
            "Cube cart modal staging icon resolved",
            started_at=started_at,
            cart_trace_id=self._cart_trace_id,
            cube_id=entry.cube_id,
            display_name=entry.display_name,
            has_descriptor=entry.icon is not None,
            icon_null=icon.isNull(),
        )
        return icon


def _elapsed_ms(started_at: float) -> float:
    """Return elapsed milliseconds for cube cart performance logs."""

    return max(0.0, (perf_counter() - started_at) * 1000.0)


def _fallback_parent() -> QWidget:
    """Return a safe parent for QFluent dialogs opened without a caller."""

    global _FALLBACK_PARENT
    active_window = QApplication.activeWindow()
    if active_window is not None:
        return active_window
    if _FALLBACK_PARENT is None:
        _FALLBACK_PARENT = QWidget()
        _FALLBACK_PARENT.resize(1200, 800)
    return _FALLBACK_PARENT


def _event_global_pos(event: QMouseEvent) -> QPoint:
    """Return mouse global position across PySide event variants."""

    global_position = getattr(event, "globalPosition", None)
    if callable(global_position):
        return cast(QPoint, global_position().toPoint())
    global_pos = getattr(event, "globalPos", None)
    if callable(global_pos):
        return cast(QPoint, global_pos())
    return QPoint()


def _cursor_shape_for_mode(mode: _CursorOverrideMode) -> Qt.CursorShape:
    """Return the Qt cursor shape for one modal-owned cursor mode."""

    _ = mode
    return Qt.CursorShape.ClosedHandCursor


def _widget_hint_height(widget: QWidget) -> int:
    """Return a typed size-hint height for Qt and QFluent widgets."""

    return max(int(widget.sizeHint().height()), int(widget.minimumHeight()))


class CubePickerDialog:
    """Open the default QFluent cube stack cart modal."""

    def edit_stack(
        self,
        *,
        parent: object,
        records: list[CubeCatalogRecord],
        initial_draft: CubeStackDraft,
        icon_factory: CubePickerIconFactoryProtocol,
        stack_anchor: object | None = None,
        refresh_catalog: CubeCatalogRefreshCallback | None = None,
        classifications: Mapping[str, CubePickerClassification] | None = None,
        classify_records: CubePickerClassifyCallback | None = None,
    ) -> CubeStackDraftResult | None:
        """Show the cart modal and return the accepted stack draft."""

        modal = CubeStackCartModal(
            records=records,
            initial_draft=initial_draft,
            stack_anchor=stack_anchor if isinstance(stack_anchor, QWidget) else None,
            icon_factory=icon_factory,
            refresh_catalog=refresh_catalog,
            classifications=classifications,
            classify_records=classify_records,
            parent=parent if isinstance(parent, QWidget) else None,
        )
        return modal.edit_stack()

    def stage_cubes(
        self,
        *,
        parent: object,
        records: list[CubeCatalogRecord],
        icon_factory: CubePickerIconFactoryProtocol,
        refresh_catalog: CubeCatalogRefreshCallback | None = None,
        classifications: Mapping[str, CubePickerClassification] | None = None,
        classify_records: CubePickerClassifyCallback | None = None,
    ) -> CubeStackDraftResult | None:
        """Compatibility wrapper opening an empty cart draft."""

        return self.edit_stack(
            parent=parent,
            records=records,
            initial_draft=CubeStackDraft(entries=()),
            stack_anchor=None,
            icon_factory=icon_factory,
            refresh_catalog=refresh_catalog,
            classifications=classifications,
            classify_records=classify_records,
        )

    def select_cube(
        self,
        *,
        parent: object,
        records: list[CubeCatalogRecord],
        icon_factory: CubePickerIconFactoryProtocol,
        refresh_catalog: CubeCatalogRefreshCallback | None = None,
        classifications: Mapping[str, CubePickerClassification] | None = None,
        classify_records: CubePickerClassifyCallback | None = None,
    ) -> CubeCatalogRecord | None:
        """Compatibility wrapper returning the first applied staged cube."""

        result = self.edit_stack(
            parent=parent,
            records=records,
            initial_draft=CubeStackDraft(entries=()),
            stack_anchor=None,
            icon_factory=icon_factory,
            refresh_catalog=refresh_catalog,
            classifications=classifications,
            classify_records=classify_records,
        )
        if result is None or result.is_empty:
            return None
        return {record.cube_id: record for record in records}.get(
            result.entries[0].cube_id
        )


CubeStagingDrawer = CubeStackCartModal
CubeStackPickerController = CubeStackCartModal

__all__ = [
    "CubeCatalogRefreshCallback",
    "CubePickerClassifyCallback",
    "CubePickerDialog",
    "CubePickerIconFactoryProtocol",
    "CubeStackCartModal",
    "CubeStackPickerController",
    "CubeStagingDrawer",
]
