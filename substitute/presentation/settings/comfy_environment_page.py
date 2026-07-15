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

"""Render the Comfy Python environment Settings page."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from html import escape
from collections.abc import Mapping
from typing import Literal

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QBoxLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CaptionLabel,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    SearchLineEdit,
    StrongBodyLabel,
    setFont,
)

from substitute.application.comfy_environment import (
    ComfyEnvironmentJob,
    ComfyEnvironmentJobStatus,
    ComfyEnvironmentPackage,
    ComfyEnvironmentService,
    ComfyEnvironmentSnapshot,
    ComfyMaintenancePlan,
    ComfyPackageClaimant,
)
from substitute.application.errors import SubstituteOperationContext
from substitute.presentation.errors import (
    ErrorPresenter,
    ErrorReportPresenterProtocol,
)
from substitute.presentation.shell.chrome_style import connect_theme_refresh
from substitute.presentation.settings.settings_style import (
    settings_card_border_color,
    settings_card_fill_color,
    settings_navigation_selected_fill_color,
)
from substitute.presentation.settings.comfy_environment_package_list import (
    PackageInventoryList,
    claimant_count,
    package_item_id,
    sorted_packages,
)
from substitute.presentation.settings.planned_changes_panel import PlannedChangesPanel
from substitute.presentation.settings.settings_async import (
    SettingsAsyncTaskRunnerFactory,
)
from sugarsubstitute_shared.presentation.widgets.scrolling import (
    configure_qfluent_scroll_surface,
)
from substitute.shared.logging.logger import get_logger, log_exception

_LOGGER = get_logger("presentation.settings.comfy_environment_page")
_PACKAGE_NAME_COLUMN = 0
_CLAIMANT_COUNT_COLUMN = 2
_SOFT_WRAP_BREAK = chr(0x200B)
_SOFT_WRAP_AFTER = frozenset("\\/._-+=:;,)]}")
_SOFT_WRAP_RUN_LENGTH = 18
_CLAIMANT_CHILD_INDENT = 16
_QT_MAX_WIDGET_SIZE = 16777215
_NO_PENDING_SNAPSHOT = object()
ComfyEnvironmentLayoutMode = Literal["wide", "medium", "narrow", "compact"]
_ENVIRONMENT_WIDE_WIDTH = 900
_ENVIRONMENT_MEDIUM_WIDTH = 680
_ENVIRONMENT_NARROW_WIDTH = 420


@dataclass(frozen=True)
class ComfyEnvironmentOperationFailure:
    """Describe one exception-backed Comfy environment operation failure."""

    operation: str
    title: str
    message: str
    error: BaseException
    package_name: str | None = None
    values: Mapping[str, object] = field(default_factory=dict)


class WrapAnywhereCaptionLabel(CaptionLabel):  # type: ignore[misc]
    """Caption label that can wrap long package tokens without changing text."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        """Create a caption label with soft break opportunities."""

        self._plain_text = ""
        CaptionLabel.__init__(self, parent)
        self.setText(text)

    def setText(self, text: str) -> None:
        """Set display text with invisible soft wrap breaks."""

        self._plain_text = text
        super().setText(_with_soft_wrap_breaks(text))

    def text(self) -> str:
        """Return the original text without inserted wrap hints."""

        return self._plain_text


class WrapAnywhereStrongBodyLabel(StrongBodyLabel):  # type: ignore[misc]
    """Strong label that can wrap long package tokens without changing text."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        """Create a strong label with soft break opportunities."""

        self._plain_text = ""
        StrongBodyLabel.__init__(self, parent)
        self.setText(text)

    def setText(self, text: str) -> None:
        """Set display text with invisible soft wrap breaks."""

        self._plain_text = text
        self.setTextFormat(Qt.TextFormat.PlainText)
        super().setText(_with_soft_wrap_breaks(text))

    def set_package_heading(self, package_name: str, version: str) -> None:
        """Set an inline package heading with smaller version text."""

        self._plain_text = f"{package_name}  {version}"
        self.setTextFormat(Qt.TextFormat.RichText)
        name = escape(_with_soft_wrap_breaks(package_name))
        version_text = escape(_with_soft_wrap_breaks(version))
        super().setText(
            f'{name} <span style="font-size: 12px; font-weight: 400;">'
            f"{version_text}</span>"
        )

    def text(self) -> str:
        """Return the original text without inserted wrap hints."""

        return self._plain_text


class ElidedCaptionLabel(CaptionLabel):  # type: ignore[misc]
    """Caption label that elides long single-line text and exposes a tooltip."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        """Create a single-line label with controlled right-edge elision."""

        self._plain_text = ""
        CaptionLabel.__init__(self, parent)
        self.setText(text)

    def setText(self, text: str) -> None:
        """Set the complete text used for elision and tooltip content."""

        self._plain_text = text
        self.setToolTip(text)
        self.setMinimumWidth(0)
        self._sync_elided_text()

    def text(self) -> str:
        """Return the original text without elision."""

        return self._plain_text

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Recompute elision when layout changes alter available width."""

        self._sync_elided_text()
        super().resizeEvent(event)

    def _sync_elided_text(self) -> None:
        """Render the current text using intentional Qt elision."""

        available_width = self.contentsRect().width()
        if available_width <= 0:
            super().setText(self._plain_text)
            return
        super().setText(
            self.fontMetrics().elidedText(
                self._plain_text,
                Qt.TextElideMode.ElideRight,
                available_width,
            )
        )


class ClaimantGroupRow(QWidget):
    """Keep a dependency group name and expand button adjacent while eliding."""

    def __init__(self, group_name: str, parent: QWidget | None = None) -> None:
        """Create one transitive dependency group row."""

        super().__init__(parent)
        self.label = _claimant_group_label(group_name, self)
        self.toggle_button = _claimant_toggle_button(self)
        self._label_natural_width = self.label.fontMetrics().horizontalAdvance(
            group_name
        )
        self._spacing = 4
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self._spacing)
        layout.addWidget(self.label)
        layout.addWidget(self.toggle_button)
        layout.addStretch(1)
        self.setFixedHeight(max(16, self.fontMetrics().height() + 2))

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Constrain the label so long dependency names elide before the button."""

        available_width = max(
            0,
            self.contentsRect().width() - self.toggle_button.width() - self._spacing,
        )
        self.label.setFixedWidth(
            max(0, min(self._label_natural_width, available_width))
        )
        super().resizeEvent(event)


class ClaimantsDetailWidget(QWidget):
    """Render dependency claimants with collapsible transitive groups."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create an empty claimant detail widget."""

        super().__init__(parent)
        self._plain_text = ""
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def set_package(self, package: ComfyEnvironmentPackage) -> None:
        """Render claimants for one installed package."""

        self._plain_text = _claimant_detail(package)
        _clear_layout(self._layout)
        self._layout.addWidget(_claimant_heading_label("Required by:", self))
        if not package.claimants:
            self._layout.addWidget(
                _claimant_message_label("No known extension claimant.", self)
            )
            self._sync_height()
            return
        for group_name, claimants in _group_claimants_by_required_via(
            package.claimants
        ):
            if group_name is None:
                for claimant in sorted(claimants, key=_claimant_sort_key):
                    self._layout.addWidget(
                        _claimant_entry_label(claimant.display_name, self)
                    )
                continue
            self._add_transitive_group(
                group_name,
                tuple(sorted(claimants, key=_claimant_sort_key)),
            )
        self._sync_height()

    def clear(self) -> None:
        """Clear rendered claimant rows."""

        self._plain_text = ""
        _clear_layout(self._layout)
        self.setFixedHeight(0)

    def text(self) -> str:
        """Return the plain claimant detail text."""

        return self._plain_text

    def _add_transitive_group(
        self,
        group_name: str,
        claimants: tuple[ComfyPackageClaimant, ...],
    ) -> None:
        """Add one collapsed transitive dependency claimant group."""

        row = ClaimantGroupRow(group_name, self)
        toggle_button = row.toggle_button

        children = QWidget(self)
        children.setObjectName("comfyEnvironmentClaimantChildren")
        children.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        child_layout = QVBoxLayout(children)
        child_layout.setContentsMargins(_CLAIMANT_CHILD_INDENT, 0, 0, 0)
        child_layout.setSpacing(0)
        for claimant in claimants:
            child_layout.addWidget(
                _claimant_child_label(claimant.display_name, children)
            )
        children.setFixedHeight(children.sizeHint().height())
        children.hide()

        def toggle_children() -> None:
            """Toggle child claimant visibility."""

            children.setHidden(not children.isHidden())
            toggle_button.setText("-" if not children.isHidden() else "+")
            children.updateGeometry()
            self._sync_height()

        toggle_button.clicked.connect(toggle_children)
        self._layout.addWidget(row)
        self._layout.addWidget(children)

    def _sync_height(self) -> None:
        """Size the claimant block to its current collapsed or expanded content."""

        self.setMinimumHeight(0)
        self.setMaximumHeight(_QT_MAX_WIDGET_SIZE)
        self.setFixedHeight(_visible_layout_height(self._layout))
        self.updateGeometry()


class ComfyEnvironmentPage(QWidget):
    """Display Comfy Python environment status and lifecycle actions."""

    snapshot_loaded = Signal(object)
    restart_requested = Signal(object)
    job_loaded = Signal(object)
    maintenance_plan_loaded = Signal(object)
    apply_job_loaded = Signal(object)
    operation_failed = Signal(object)

    def __init__(
        self,
        service: ComfyEnvironmentService,
        *,
        open_reconfigure_window: Callable[[], object],
        error_presenter: ErrorReportPresenterProtocol | None = None,
        parent: QWidget | None = None,
        task_runner_factory: SettingsAsyncTaskRunnerFactory,
    ) -> None:
        """Build the environment Settings page."""

        super().__init__(parent)
        self._service = service
        self._open_reconfigure_window = open_reconfigure_window
        self._error_presenter = error_presenter
        self._active_job_id: str | None = None
        self._all_packages: tuple[ComfyEnvironmentPackage, ...] = ()
        self._packages: tuple[ComfyEnvironmentPackage, ...] = ()
        self._selected_package_id: str | None = None
        self._maintenance_plan: ComfyMaintenancePlan | None = None
        self._sort_column = _CLAIMANT_COUNT_COLUMN
        self._sort_ascending = False
        self._operation_planning_supported = False
        self._settings_lifecycle_bound = False
        self._settings_page_active = False
        self._layout_mode: ComfyEnvironmentLayoutMode | None = None
        self._refresh_generation = 0
        self._refresh_in_flight = False
        self._pending_snapshot_payload: object = _NO_PENDING_SNAPSHOT
        self._task_runner = task_runner_factory(
            self,
            owner_id="comfy_environment_settings",
        )
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(1000)
        self._poll_timer.timeout.connect(self._poll_active_job)

        self._build_ui()
        connect_theme_refresh(self, self._apply_theme_styles)
        self.snapshot_loaded.connect(self._apply_snapshot)
        self.restart_requested.connect(self._apply_restart_job)
        self.job_loaded.connect(self._apply_job_update)
        self.maintenance_plan_loaded.connect(self._apply_maintenance_plan)
        self.apply_job_loaded.connect(self._apply_plan_job)
        self.operation_failed.connect(self._show_operation_failure)

    def set_settings_page_active(self, active: bool) -> None:
        """Apply Settings route/page visibility and render any pending snapshot."""

        self._settings_lifecycle_bound = True
        self._settings_page_active = active
        if not active or self._pending_snapshot_payload is _NO_PENDING_SNAPSHOT:
            if active and not self._refresh_in_flight:
                self.refresh()
            return
        payload = self._pending_snapshot_payload
        self._pending_snapshot_payload = _NO_PENDING_SNAPSHOT
        self._apply_snapshot(payload)

    def refresh(self) -> None:
        """Refresh environment status without blocking the UI thread."""

        if self._refresh_in_flight:
            return
        self._refresh_generation += 1
        generation = self._refresh_generation
        self._refresh_in_flight = True
        self.status_label.setText("Checking the selected Comfy server.")
        self.refresh_button.setEnabled(False)
        self._run_background(
            task_id="comfy_environment_refresh",
            operation=lambda: self._load_snapshot(generation),
        )

    def select_inventory_item(self, item_id: str) -> None:
        """Select one installed package and render its details."""

        package = self._find_package(item_id)
        if package is None:
            return
        self._selected_package_id = item_id
        self.package_list.select_item(item_id)
        self._render_package_detail(package)

    def inventory_item_names(self) -> tuple[str, ...]:
        """Return installed package names currently rendered by the page."""

        return tuple(package.name for package in self._all_packages)

    def visible_inventory_item_names(self) -> tuple[str, ...]:
        """Return visible installed package names after filtering."""

        return tuple(package.name for package in self._packages)

    def detail_text(self) -> str:
        """Return detail panel text for the selected installed package."""

        return "\n".join(
            (
                self.detail_title_label.text(),
                self.detail_meta_label.text(),
                self.detail_summary_label.text(),
                self.detail_claimants_label.text(),
                self.detail_tags_label.text(),
                self.detail_actions_label.text(),
            )
        )

    def layout_mode(self) -> ComfyEnvironmentLayoutMode | None:
        """Return the active adaptive inventory layout mode."""

        return self._layout_mode

    def resize(self, width: QSize | int, height: int | None = None) -> None:
        """Lower mode-specific minimums before direct resize requests apply."""

        requested_width = width.width() if isinstance(width, QSize) else width
        self._sync_layout_mode(requested_width)
        if isinstance(width, QSize):
            super().resize(width)
            return
        if height is None:
            return
        super().resize(width, height)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Update the adaptive inventory layout after page width changes."""

        super().resizeEvent(event)
        self._sync_layout_mode(event.size().width())

    def showEvent(self, event: QShowEvent) -> None:
        """Apply actual visible width after hidden setup defaults to wide mode."""

        super().showEvent(event)
        self._sync_layout_mode(self.width())
        if not self._settings_lifecycle_bound and not self._refresh_in_flight:
            self.refresh()

    def _build_ui(self) -> None:
        """Build page widgets and wire local UI actions."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        status_panel = QFrame(self)
        status_panel.setObjectName("comfyEnvironmentStatusPanel")
        status_layout = QVBoxLayout(status_panel)
        status_layout.setContentsMargins(18, 16, 18, 16)
        status_layout.setSpacing(8)
        self.status_label = BodyLabel(
            "Checking the selected Comfy server.", status_panel
        )
        self.python_label = CaptionLabel("", status_panel)
        self.comfy_label = CaptionLabel("", status_panel)
        for label in (self.status_label, self.python_label, self.comfy_label):
            label.setWordWrap(True)
            label.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Preferred,
            )
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.python_label)
        status_layout.addWidget(self.comfy_label)
        self.action_row = QHBoxLayout()
        self.action_row.setSpacing(10)
        self.restart_button = PrimaryPushButton("Restart Comfy", status_panel)
        self.restart_button.setEnabled(False)
        self.restart_button.clicked.connect(self._request_restart)
        self.refresh_button = PushButton("Refresh", status_panel)
        self.refresh_button.clicked.connect(self.refresh)
        self.reconfigure_button = PushButton("Open setup wizard", status_panel)
        self.reconfigure_button.clicked.connect(self._open_reconfigure_window)
        self.action_row.addWidget(self.restart_button)
        self.action_row.addWidget(self.refresh_button)
        self.action_row.addWidget(self.reconfigure_button)
        self.action_row.addStretch(1)
        status_layout.addLayout(self.action_row)
        self.job_label = CaptionLabel("", status_panel)
        self.job_label.setWordWrap(True)
        self.job_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        status_layout.addWidget(self.job_label)
        layout.addWidget(status_panel)

        self.inventory_panel = QWidget(self)
        self.inventory_panel.setObjectName("comfyEnvironmentInventoryPanel")
        self.inventory_panel.setStyleSheet(
            """
            QWidget#comfyEnvironmentInventoryPanel {
                background: transparent;
                border: none;
            }
            """
        )
        self.inventory_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        inventory_layout = QVBoxLayout(self.inventory_panel)
        inventory_layout.setContentsMargins(0, 0, 0, 0)
        inventory_layout.setSpacing(0)
        self.inventory_label = BodyLabel("Packages not loaded", self.inventory_panel)
        self.inventory_count_label = CaptionLabel(
            "Not loaded",
            self.inventory_panel,
        )
        self.package_selector = QFrame(self.inventory_panel)
        self.package_selector.setObjectName("comfyEnvironmentPackageSelector")
        self.package_selector.setMinimumWidth(380)
        self.package_selector.setMaximumWidth(440)
        self.package_selector.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )
        package_selector_layout = QVBoxLayout(self.package_selector)
        package_selector_layout.setContentsMargins(14, 14, 14, 14)
        package_selector_layout.setSpacing(8)

        self.inventory_filter = SearchLineEdit(self.package_selector)
        self.inventory_filter.setPlaceholderText("Filter packages, claimants, or tags")
        self.inventory_filter.setClearButtonEnabled(True)
        self.inventory_filter.textChanged.connect(self._apply_inventory_filter)

        self.package_list = PackageInventoryList(self.package_selector)
        self.package_list.package_selected.connect(self._render_package_detail_by_id)
        self.inventory_count_label.hide()
        package_selector_layout.addWidget(self.inventory_label)
        package_selector_layout.addWidget(self.inventory_filter)
        package_selector_layout.addWidget(self.package_list, 1)

        self.detail_container = QFrame(self.inventory_panel)
        self.detail_container.setObjectName("comfyEnvironmentDetailContainer")
        self.detail_container.setMinimumWidth(240)
        self.detail_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        detail_container_layout = QVBoxLayout(self.detail_container)
        detail_container_layout.setContentsMargins(14, 14, 14, 14)
        detail_container_layout.setSpacing(8)

        self.detail_panel = QWidget(self.detail_container)
        self.detail_panel.setObjectName("comfyEnvironmentDetailPanel")
        self.detail_panel.setMinimumWidth(0)
        self.detail_panel.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(12, 12, 12, 12)
        detail_layout.setSpacing(8)
        detail_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.detail_title_label = WrapAnywhereStrongBodyLabel(
            "Select a package",
            self.detail_panel,
        )
        setFont(self.detail_title_label, 16)
        self.detail_meta_label = WrapAnywhereCaptionLabel("", self.detail_panel)
        self.detail_summary_label = WrapAnywhereCaptionLabel("", self.detail_panel)
        self.detail_claimants_label = ClaimantsDetailWidget(self.detail_panel)
        self.detail_tags_label = WrapAnywhereCaptionLabel("", self.detail_panel)
        for label in (
            self.detail_title_label,
            self.detail_meta_label,
            self.detail_summary_label,
            self.detail_tags_label,
        ):
            _configure_detail_text_label(label)
        detail_layout.addWidget(self.detail_title_label)
        detail_layout.addWidget(self.detail_meta_label)
        detail_layout.addWidget(self.detail_summary_label)
        detail_layout.addWidget(self.detail_claimants_label)
        detail_layout.addWidget(self.detail_tags_label)

        self.detail_action_bar = QWidget(self.detail_container)
        self.detail_action_bar.setObjectName("comfyEnvironmentDetailActionBar")
        self.detail_action_bar.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        self.detail_actions_layout = QHBoxLayout(self.detail_action_bar)
        self.detail_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.detail_actions_layout.setSpacing(8)
        self.update_package_button = PushButton("Plan update", self.detail_action_bar)
        self.update_package_button.setEnabled(False)
        self.update_package_button.clicked.connect(self._request_update_plan)
        self.uninstall_package_button = PushButton(
            "Plan uninstall",
            self.detail_action_bar,
        )
        self.uninstall_package_button.setEnabled(False)
        self.uninstall_package_button.clicked.connect(self._request_uninstall_plan)
        self.detail_actions_layout.addWidget(self.update_package_button)
        self.detail_actions_layout.addWidget(self.uninstall_package_button)
        self.detail_actions_label = WrapAnywhereCaptionLabel(
            "",
            self.detail_container,
        )
        _configure_detail_text_label(self.detail_actions_label)
        self.detail_actions_label.hide()

        self.detail_scroll = ScrollArea(self.detail_container)
        configure_qfluent_scroll_surface(self.detail_scroll)
        self.detail_scroll.setObjectName("comfyEnvironmentDetailScroll")
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.detail_scroll.setMinimumHeight(0)
        self.detail_scroll.setMinimumWidth(240)
        self.detail_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.detail_scroll.viewport().setObjectName("comfyEnvironmentDetailViewport")
        self.detail_scroll.setWidget(self.detail_panel)
        detail_container_layout.addWidget(self.detail_scroll, 1)
        detail_container_layout.addWidget(self.detail_action_bar, 0)

        self.inventory_body = QGridLayout()
        self.inventory_body.setContentsMargins(0, 0, 0, 0)
        self.inventory_body.setHorizontalSpacing(12)
        self.inventory_body.setVerticalSpacing(12)
        self.planned_changes_panel = PlannedChangesPanel(self.inventory_panel)
        self.planned_changes_panel.remove_item_requested.connect(
            self._request_remove_plan_item
        )
        self.planned_changes_panel.reorder_requested.connect(
            self._request_reorder_plan_items
        )
        self.planned_changes_panel.clear_requested.connect(self._request_clear_plan)
        self.planned_changes_panel.apply_requested.connect(self._request_apply_plan)
        inventory_layout.addLayout(self.inventory_body, 1)
        layout.addWidget(self.inventory_panel, 1)

        self._apply_theme_styles()
        self._sync_layout_mode()

    def _sync_layout_mode(self, available_width: int | None = None) -> None:
        """Apply the inventory layout mode for the current page width."""

        width = (
            max(1, available_width)
            if available_width is not None
            else max(
                self.width(),
                self.contentsRect().width(),
                _ENVIRONMENT_WIDE_WIDTH if not self.isVisible() else 0,
            )
        )
        mode = _environment_layout_mode(width)
        if mode == self._layout_mode:
            return
        self._layout_mode = mode
        self._apply_inventory_layout_mode(mode)

    def _apply_inventory_layout_mode(
        self,
        mode: ComfyEnvironmentLayoutMode,
    ) -> None:
        """Reposition inventory panes for one adaptive width mode."""

        self.inventory_body.removeWidget(self.package_selector)
        self.inventory_body.removeWidget(self.detail_container)
        self.inventory_body.removeWidget(self.planned_changes_panel)
        self._configure_inventory_mode_widths(mode)
        if mode == "wide":
            self.inventory_body.addWidget(self.package_selector, 0, 0)
            self.inventory_body.addWidget(self.detail_container, 0, 1)
            self.inventory_body.addWidget(self.planned_changes_panel, 1, 0, 1, 2)
            column_stretches = (0, 1, 0)
        elif mode == "medium":
            self.inventory_body.addWidget(self.package_selector, 0, 0)
            self.inventory_body.addWidget(self.detail_container, 0, 1)
            self.inventory_body.addWidget(self.planned_changes_panel, 1, 0, 1, 2)
            column_stretches = (0, 1, 0)
        else:
            self.inventory_body.addWidget(self.package_selector, 0, 0)
            self.inventory_body.addWidget(self.detail_container, 1, 0)
            self.inventory_body.addWidget(self.planned_changes_panel, 2, 0)
            column_stretches = (1, 0, 0)
        for column, stretch in enumerate(column_stretches):
            self.inventory_body.setColumnStretch(column, stretch)
        for row in range(3):
            self.inventory_body.setRowStretch(row, 1 if row == 0 else 0)
        self._apply_action_layout_mode(mode)

    def _configure_inventory_mode_widths(
        self,
        mode: ComfyEnvironmentLayoutMode,
    ) -> None:
        """Apply mode-specific width constraints to inventory panes."""

        if mode == "wide":
            self.package_selector.setSizePolicy(
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Expanding,
            )
            self.package_selector.setMinimumWidth(380)
            self.package_selector.setMaximumWidth(440)
            self.package_list.setMinimumWidth(380)
            self.package_list.setMaximumWidth(440)
            self.detail_container.setMinimumWidth(240)
            self.detail_scroll.setMinimumWidth(240)
            self.planned_changes_panel.setMinimumWidth(280)
            self.planned_changes_panel.setMaximumWidth(_QT_MAX_WIDGET_SIZE)
            return
        if mode == "medium":
            self.package_selector.setSizePolicy(
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Expanding,
            )
            self.package_selector.setMinimumWidth(320)
            self.package_selector.setMaximumWidth(400)
            self.package_list.setMinimumWidth(320)
            self.package_list.setMaximumWidth(400)
            self.detail_container.setMinimumWidth(220)
            self.detail_scroll.setMinimumWidth(220)
            self.planned_changes_panel.setMinimumWidth(0)
            self.planned_changes_panel.setMaximumWidth(_QT_MAX_WIDGET_SIZE)
            return
        self.package_selector.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.package_selector.setMinimumWidth(0)
        self.package_selector.setMaximumWidth(_QT_MAX_WIDGET_SIZE)
        self.package_list.setMinimumWidth(0)
        self.package_list.setMaximumWidth(_QT_MAX_WIDGET_SIZE)
        self.detail_container.setMinimumWidth(0)
        self.detail_scroll.setMinimumWidth(0)
        self.planned_changes_panel.setMinimumWidth(0)
        self.planned_changes_panel.setMaximumWidth(_QT_MAX_WIDGET_SIZE)

    def _apply_action_layout_mode(self, mode: ComfyEnvironmentLayoutMode) -> None:
        """Stack action rows when horizontal button groups would set page width."""

        compact = mode in {"narrow", "compact"}
        direction = (
            QBoxLayout.Direction.TopToBottom
            if compact
            else QBoxLayout.Direction.LeftToRight
        )
        self.detail_actions_layout.setDirection(direction)
        self.action_row.setDirection(direction)
        self.planned_changes_panel.set_compact_width_mode(compact)

    def _apply_theme_styles(self) -> None:
        """Refresh custom environment panel styles from the active QFluent theme."""

        self.setStyleSheet(_environment_panel_stylesheet(self))

    def _load_snapshot(self, generation: int) -> None:
        """Load the backend snapshot through the settings task route."""

        try:
            snapshot = self._service.load_snapshot()
            self.snapshot_loaded.emit((generation, snapshot))
        except Exception as error:
            log_exception(
                _LOGGER, "Failed to load Comfy environment snapshot", error=error
            )
            self.snapshot_loaded.emit((generation, None))

    def _run_background(
        self,
        *,
        task_id: str,
        operation: Callable[[], object],
    ) -> None:
        """Run one Comfy environment operation through the settings execution lane."""

        self._task_runner.run(
            task_id=task_id,
            generation=self._refresh_generation,
            operation=operation,
            context={"page": "comfy_environment"},
        )

    def _apply_snapshot(self, snapshot: object) -> None:
        """Render one environment snapshot."""

        generation = self._refresh_generation
        has_generation = False
        if (
            isinstance(snapshot, tuple)
            and len(snapshot) == 2
            and isinstance(snapshot[0], int)
        ):
            has_generation = True
            generation = snapshot[0]
            snapshot = snapshot[1]
        if has_generation and generation != self._refresh_generation:
            return
        self._refresh_in_flight = False
        if (
            has_generation
            and self._settings_lifecycle_bound
            and not self._settings_page_active
            and not self.isVisible()
        ):
            self.refresh_button.setEnabled(True)
            self._pending_snapshot_payload = (generation, snapshot)
            return
        self.refresh_button.setEnabled(True)
        if not isinstance(snapshot, ComfyEnvironmentSnapshot):
            self._render_unavailable("Comfy environment status is unavailable.")
            return
        if snapshot.capabilities is None:
            self._render_unavailable(
                "The selected Comfy server does not expose environment management."
            )
            return
        status = snapshot.status
        if status is None:
            self._render_unavailable("Comfy environment status is unavailable.")
            return
        self._operation_planning_supported = (
            snapshot.capabilities.operation_planning_supported
        )
        self.status_label.setText("Comfy environment management is available.")
        self.python_label.setText(
            f"Python {status.python.version} at {status.python.prefix}"
        )
        self.comfy_label.setText(
            f"Comfy root: {status.comfy.root} | process {status.comfy.process_id}"
        )
        self._render_inventory(snapshot)
        self._apply_maintenance_plan(snapshot.maintenance_plan)
        restart_supported = (
            snapshot.capabilities.restart_supported and status.comfy.restart_supported
        )
        self.restart_button.setEnabled(restart_supported)
        if restart_supported:
            self.job_label.setText("Restart is available for this Comfy server.")
        else:
            reason = snapshot.capabilities.restart_unavailable_reason
            self.job_label.setText(
                reason or "Restart is not available for this server."
            )

    def _render_unavailable(self, message: str) -> None:
        """Render unavailable backend state."""

        self.status_label.setText(message)
        self._operation_planning_supported = False
        self.python_label.setText("")
        self.comfy_label.setText("")
        self.restart_button.setEnabled(False)
        self.job_label.setText(
            "Use Comfy Connection settings to change the selected server."
        )
        self._render_packages(())
        self._apply_maintenance_plan(None)
        self.inventory_label.setText("Inventory unavailable")
        self.inventory_count_label.setText("Inventory unavailable")
        self._render_empty_detail("No installed package data is available.")

    def _request_restart(self) -> None:
        """Request a restart job without blocking the UI thread."""

        self.restart_button.setEnabled(False)
        self.job_label.setText("Restart requested.")
        self._run_background(
            task_id="comfy_environment_restart",
            operation=self._restart_comfy,
        )

    def _restart_comfy(self) -> None:
        """Request restart work through the settings task route."""

        try:
            self.restart_requested.emit(self._service.restart_comfy())
        except Exception as error:
            log_exception(_LOGGER, "Failed to request Comfy restart", error=error)
            self.operation_failed.emit(
                ComfyEnvironmentOperationFailure(
                    operation="comfy_environment.restart",
                    title="Comfy restart failed",
                    message="Comfy restart could not be started.",
                    error=error,
                )
            )
            self.restart_requested.emit(None)

    def _apply_restart_job(self, job: object) -> None:
        """Render restart request result and start polling."""

        if not isinstance(job, ComfyEnvironmentJob):
            self.job_label.setText("Comfy restart could not be started.")
            self.restart_button.setEnabled(True)
            return
        self._active_job_id = job.job_id
        self._render_job(job)
        self._poll_timer.start()

    def _poll_active_job(self) -> None:
        """Poll the active restart job without blocking the UI thread."""

        if self._active_job_id is None:
            self._poll_timer.stop()
            return
        job_id = self._active_job_id
        self._run_background(
            task_id="comfy_environment_job_poll",
            operation=lambda: self._load_job(job_id),
        )

    def _load_job(self, job_id: str) -> None:
        """Load one job state through the settings task route."""

        try:
            self.job_loaded.emit(self._service.get_job(job_id))
        except Exception as error:
            log_exception(_LOGGER, "Failed to load Comfy environment job", error=error)
            self.job_loaded.emit(None)

    def _apply_job_update(self, job: object) -> None:
        """Render one polled job update."""

        if job is None:
            self.job_label.setText("Waiting for Comfy to come back.")
            return
        if not isinstance(job, ComfyEnvironmentJob):
            self.job_label.setText("Comfy restart status is unavailable.")
            return
        self._render_job(job)
        if job.status in {
            ComfyEnvironmentJobStatus.SUCCEEDED,
            ComfyEnvironmentJobStatus.FAILED,
            ComfyEnvironmentJobStatus.CANCELLED,
        }:
            self._poll_timer.stop()
            self._active_job_id = None
            self.refresh()

    def _render_job(self, job: ComfyEnvironmentJob) -> None:
        """Render one environment job status."""

        self.job_label.setText(f"{job.message} ({job.status.value})")

    def _render_inventory(self, snapshot: ComfyEnvironmentSnapshot) -> None:
        """Render installed Python package inventory."""

        self._render_packages(snapshot.packages)
        self.inventory_label.setText(_installed_packages_title(len(snapshot.packages)))
        self.inventory_count_label.setText(
            _installed_packages_title(len(snapshot.packages))
        )

    def _render_packages(self, packages: tuple[ComfyEnvironmentPackage, ...]) -> None:
        """Render package rows in the inventory table."""

        self._all_packages = packages
        self._selected_package_id = None
        self._render_filtered_packages(select_first=True)

    def _render_filtered_packages(self, *, select_first: bool = False) -> None:
        """Render package rows after applying search ranking and sort."""

        current_selection = self._selected_package_id
        self._packages = sorted_packages(
            packages=self._all_packages,
            filter_text=self.inventory_filter.text(),
            sort_column=self._sort_column,
            ascending=self._sort_ascending,
        )
        self.package_list.render_packages(self._packages)
        if self._packages:
            if (
                current_selection is not None
                and self._find_rendered_package(current_selection) is not None
                and not select_first
            ):
                self.select_inventory_item(current_selection)
            else:
                self.select_inventory_item(package_item_id(self._packages[0]))
        else:
            self._render_empty_detail("No installed packages were returned.")

    def _apply_inventory_filter(self, text: str) -> None:
        """Filter installed package rows by user-entered text."""

        _ = text
        if not self._all_packages:
            return
        self._render_filtered_packages(select_first=True)
        if not self._packages:
            self._render_empty_detail("No installed packages match the filter.")

    def _change_inventory_sort(self, column: int) -> None:
        """Sort package rows by package name or dependency claimant count."""

        if column not in {_PACKAGE_NAME_COLUMN, _CLAIMANT_COUNT_COLUMN}:
            return
        if column == self._sort_column:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = column
            self._sort_ascending = column == _PACKAGE_NAME_COLUMN
        self._render_filtered_packages()

    def _render_package_detail_by_id(self, item_id: str) -> None:
        """Render details for the package selected in the inventory list."""

        package = self._find_package(item_id)
        if package is not None:
            self._selected_package_id = item_id
            self._render_package_detail(package)

    def _find_package(self, item_id: str) -> ComfyEnvironmentPackage | None:
        """Return one package by rendered item id."""

        for package in self._all_packages:
            if package_item_id(package) == item_id:
                return package
        return None

    def _find_rendered_package(
        self,
        item_id: str,
    ) -> ComfyEnvironmentPackage | None:
        """Return one rendered package by item id."""

        for package in self._packages:
            if package_item_id(package) == item_id:
                return package
        return None

    def _render_package_detail(self, package: ComfyEnvironmentPackage) -> None:
        """Render details for one selected installed package."""

        self.detail_title_label.set_package_heading(package.name, package.version)
        self.detail_meta_label.setText(_package_metadata_line(package))
        self.detail_summary_label.setText(f'"{_summary_text(package)}"')
        self.detail_claimants_label.set_package(package)
        self.detail_tags_label.setText(_management_tag_detail(package))
        self.update_package_button.setEnabled(self._operation_planning_supported)
        self.uninstall_package_button.setEnabled(self._operation_planning_supported)
        self.update_package_button.setProperty("packageId", package_item_id(package))
        self.uninstall_package_button.setProperty("packageId", package_item_id(package))
        has_actions = any(tag.supported_actions for tag in package.management_tags)
        if not self._operation_planning_supported:
            self.detail_actions_label.setText(
                "Operation planning is not available for this Comfy server."
            )
        elif has_actions:
            self.detail_actions_label.setText("")
        else:
            self.detail_actions_label.setText("")

    def _render_empty_detail(self, message: str) -> None:
        """Render an empty package detail state."""

        self.detail_title_label.setText("Installed packages")
        self.detail_meta_label.setText(message)
        self.detail_summary_label.setText("")
        self.detail_claimants_label.clear()
        self.detail_tags_label.setText("")
        self.update_package_button.setEnabled(False)
        self.uninstall_package_button.setEnabled(False)
        self.detail_actions_label.setText("")

    def _request_update_plan(self) -> None:
        """Add an update action for the selected package to the plan."""

        package = self._selected_package()
        if package is None:
            return
        self._set_plan_buttons_enabled(False)
        self.detail_actions_label.setText("Adding update to planned changes.")
        self._run_background(
            task_id="comfy_environment_plan_update",
            operation=lambda: self._add_to_maintenance_plan("update", package),
        )

    def _request_uninstall_plan(self) -> None:
        """Add an uninstall action for the selected package to the plan."""

        package = self._selected_package()
        if package is None:
            return
        self._set_plan_buttons_enabled(False)
        self.detail_actions_label.setText("Adding uninstall to planned changes.")
        self._run_background(
            task_id="comfy_environment_plan_uninstall",
            operation=lambda: self._add_to_maintenance_plan("uninstall", package),
        )

    def _add_to_maintenance_plan(
        self,
        action: str,
        package: ComfyEnvironmentPackage,
    ) -> None:
        """Add one operation to the maintenance plan through the task route."""

        try:
            if action == "update":
                self.maintenance_plan_loaded.emit(
                    self._service.add_package_update_to_plan(package)
                )
            else:
                self.maintenance_plan_loaded.emit(
                    self._service.add_package_uninstall_to_plan(package)
                )
        except Exception as error:
            log_exception(_LOGGER, "Failed to update maintenance plan", error=error)
            self.operation_failed.emit(
                ComfyEnvironmentOperationFailure(
                    operation=f"comfy_environment.plan.{action}",
                    title="Planned change failed",
                    message="Planned changes are unavailable.",
                    error=error,
                    package_name=package.name,
                    values={
                        "action": action,
                        "package_version": package.version,
                    },
                )
            )
            self.maintenance_plan_loaded.emit(None)

    def _apply_maintenance_plan(self, plan: object) -> None:
        """Render one maintenance plan response."""

        self._set_plan_buttons_enabled(self._selected_package() is not None)
        if not isinstance(plan, ComfyMaintenancePlan):
            self._maintenance_plan = None
            self.planned_changes_panel.render_plan(None)
            self.detail_actions_label.setText("Planned changes are unavailable.")
            return
        self._maintenance_plan = plan
        self.planned_changes_panel.render_plan(plan)
        if plan.last_validation_message:
            self.detail_actions_label.setText(plan.last_validation_message)
        elif plan.items:
            self.detail_actions_label.setText("Planned changes updated.")

    def _request_remove_plan_item(self, item_id: str) -> None:
        """Remove one item from the maintenance plan."""

        self.detail_actions_label.setText("Removing planned change.")
        self._run_background(
            task_id="comfy_environment_plan_remove_item",
            operation=lambda: self._remove_plan_item(item_id),
        )

    def _remove_plan_item(self, item_id: str) -> None:
        """Remove one plan item through the settings task route."""

        try:
            self.maintenance_plan_loaded.emit(self._service.remove_plan_item(item_id))
        except Exception as error:
            log_exception(_LOGGER, "Failed to remove plan item", error=error)
            self.operation_failed.emit(
                ComfyEnvironmentOperationFailure(
                    operation="comfy_environment.plan.remove_item",
                    title="Remove planned change failed",
                    message="Planned changes are unavailable.",
                    error=error,
                    values={"item_id": item_id},
                )
            )
            self.maintenance_plan_loaded.emit(None)

    def _request_reorder_plan_items(self, item_ids: object) -> None:
        """Send a proposed plan item order."""

        if self._maintenance_plan is None or not isinstance(item_ids, tuple):
            return
        if not all(isinstance(item_id, str) for item_id in item_ids):
            return
        self.detail_actions_label.setText("Updating planned change order.")
        revision = self._maintenance_plan.revision
        self._run_background(
            task_id="comfy_environment_plan_reorder",
            operation=lambda: self._reorder_plan_items(revision, item_ids),
        )

    def _reorder_plan_items(
        self,
        revision: int,
        item_ids: tuple[str, ...],
    ) -> None:
        """Reorder plan items through the settings task route."""

        try:
            self.maintenance_plan_loaded.emit(
                self._service.reorder_plan_items(
                    revision=revision,
                    item_ids=item_ids,
                )
            )
        except Exception as error:
            log_exception(_LOGGER, "Failed to reorder plan items", error=error)
            self.operation_failed.emit(
                ComfyEnvironmentOperationFailure(
                    operation="comfy_environment.plan.reorder",
                    title="Reorder planned changes failed",
                    message="Planned changes are unavailable.",
                    error=error,
                    values={"revision": revision, "item_ids": item_ids},
                )
            )
            self.maintenance_plan_loaded.emit(None)

    def _request_clear_plan(self) -> None:
        """Clear all planned changes."""

        self.detail_actions_label.setText("Clearing planned changes.")
        self._run_background(
            task_id="comfy_environment_plan_clear",
            operation=self._clear_plan,
        )

    def _clear_plan(self) -> None:
        """Clear the maintenance plan through the settings task route."""

        try:
            self.maintenance_plan_loaded.emit(self._service.clear_plan())
        except Exception as error:
            log_exception(_LOGGER, "Failed to clear plan", error=error)
            self.operation_failed.emit(
                ComfyEnvironmentOperationFailure(
                    operation="comfy_environment.plan.clear",
                    title="Clear planned changes failed",
                    message="Planned changes are unavailable.",
                    error=error,
                )
            )
            self.maintenance_plan_loaded.emit(None)

    def _request_apply_plan(self, revision: int) -> None:
        """Apply the current maintenance plan."""

        self.planned_changes_panel.apply_button.setEnabled(False)
        self.job_label.setText("Applying planned changes.")
        self._run_background(
            task_id="comfy_environment_plan_apply",
            operation=lambda: self._apply_plan(revision),
        )

    def _apply_plan(self, revision: int) -> None:
        """Apply the plan through the settings task route."""

        try:
            self.apply_job_loaded.emit(self._service.apply_plan(revision=revision))
        except Exception as error:
            log_exception(_LOGGER, "Failed to apply plan", error=error)
            self.operation_failed.emit(
                ComfyEnvironmentOperationFailure(
                    operation="comfy_environment.plan.apply",
                    title="Apply planned changes failed",
                    message="Planned changes could not be applied.",
                    error=error,
                    values={"revision": revision},
                )
            )
            self.apply_job_loaded.emit(None)

    def _apply_plan_job(self, job: object) -> None:
        """Render apply request result and start polling."""

        if not isinstance(job, ComfyEnvironmentJob):
            self.job_label.setText("Planned changes could not be applied.")
            if self._maintenance_plan is not None:
                self.planned_changes_panel.render_plan(self._maintenance_plan)
            return
        self._active_job_id = job.job_id
        self._render_job(job)
        self._poll_timer.start()

    def _selected_package(self) -> ComfyEnvironmentPackage | None:
        """Return the currently selected package."""

        if self._selected_package_id is None:
            return None
        return self._find_package(self._selected_package_id)

    def _set_plan_buttons_enabled(self, enabled: bool) -> None:
        """Set plan button enabled state."""

        allowed = enabled and self._operation_planning_supported
        self.update_package_button.setEnabled(allowed)
        self.uninstall_package_button.setEnabled(allowed)

    def _show_operation_failure(self, failure: object) -> None:
        """Show exception-backed settings failures through the unified modal."""

        if not isinstance(failure, ComfyEnvironmentOperationFailure):
            return
        self._resolved_error_presenter().show_exception_report(
            title=failure.title,
            message=failure.message,
            stage="settings",
            error=failure.error,
            context=SubstituteOperationContext(
                operation=failure.operation,
                package_name=failure.package_name,
                values=failure.values,
            ),
        )

    def _resolved_error_presenter(self) -> ErrorReportPresenterProtocol:
        """Return the injected presenter or lazily create one parented to the page."""

        if self._error_presenter is None:
            self._error_presenter = ErrorPresenter(parent=self)
        return self._error_presenter


def _configure_detail_text_label(label: QLabel) -> None:
    """Allow detail text to wrap inside the available inspector width."""

    label.setWordWrap(True)
    label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Maximum)


def _environment_layout_mode(width: int) -> ComfyEnvironmentLayoutMode:
    """Return the Comfy Environment layout mode for an available width."""

    if width >= _ENVIRONMENT_WIDE_WIDTH:
        return "wide"
    if width >= _ENVIRONMENT_MEDIUM_WIDTH:
        return "medium"
    if width >= _ENVIRONMENT_NARROW_WIDTH:
        return "narrow"
    return "compact"


def _installed_packages_title(package_count: int) -> str:
    """Return the package browser title with the installed package count."""

    if package_count == 1:
        return "1 installed package"
    return f"{package_count} installed packages"


def _environment_panel_stylesheet(widget: QWidget) -> str:
    """Return theme-aware styling for bespoke environment management panels."""

    panel_fill = _css_color(settings_card_fill_color(widget))
    border = _css_color(settings_card_border_color())
    return f"""
        QFrame#comfyEnvironmentStatusPanel,
        QFrame#comfyEnvironmentPackageSelector,
        QFrame#comfyEnvironmentDetailContainer,
        QFrame#comfyEnvironmentPlannedChangesPanel {{
            background: {panel_fill};
            border: 1px solid {border};
            border-radius: 6px;
        }}
        QScrollArea#comfyEnvironmentDetailScroll {{
            border: none;
            background: transparent;
        }}
        QWidget#comfyEnvironmentDetailViewport,
        QWidget#comfyEnvironmentDetailPanel {{
            background: transparent;
        }}
        TableWidget#comfyEnvironmentPackageList,
        ListWidget#comfyEnvironmentPlanList {{
            background: transparent;
            border: none;
            alternate-background-color: {_css_color(settings_navigation_selected_fill_color())};
        }}
        QWidget#comfyEnvironmentPackageRow {{
            background: transparent;
        }}
    """


def _css_color(color: QColor) -> str:
    """Return a Qt stylesheet rgba color from a QColor-like object."""

    red = color.red()
    green = color.green()
    blue = color.blue()
    alpha = color.alpha()
    return f"rgba({red}, {green}, {blue}, {alpha})"


def _claimant_toggle_button(parent: QWidget) -> QToolButton:
    """Create one inline font-sized claimant expansion button."""

    button = QToolButton(parent)
    button.setText("+")
    button.setAutoRaise(True)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setToolTip("Show dependent extensions")
    size = _font_square_size(button)
    button.setFixedSize(size, size)
    button.setStyleSheet(
        """
        QToolButton {
            border: none;
            padding: 0;
            margin: 0;
            background: transparent;
        }
        """
    )
    return button


def _claimant_heading_label(text: str, parent: QWidget) -> WrapAnywhereCaptionLabel:
    """Create one wrapping claimant section heading label."""

    label = WrapAnywhereCaptionLabel(text, parent)
    _configure_detail_text_label(label)
    return label


def _claimant_message_label(text: str, parent: QWidget) -> WrapAnywhereCaptionLabel:
    """Create one wrapping claimant status message label."""

    label = WrapAnywhereCaptionLabel(text, parent)
    _configure_detail_text_label(label)
    return label


def _claimant_entry_label(text: str, parent: QWidget) -> ElidedCaptionLabel:
    """Create one compact direct claimant label with tooltip elision."""

    label = ElidedCaptionLabel(text, parent)
    label.setWordWrap(False)
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    label.setFixedHeight(max(16, label.fontMetrics().height() + 2))
    return label


def _claimant_group_label(text: str, parent: QWidget) -> ElidedCaptionLabel:
    """Create a claimant group label that elides beside its inline toggle."""

    label = ElidedCaptionLabel(text, parent)
    label.setWordWrap(False)
    label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    label.setFixedHeight(max(16, label.fontMetrics().height() + 2))
    return label


def _claimant_child_label(text: str, parent: QWidget) -> ElidedCaptionLabel:
    """Create one compact expanded claimant child label with tooltip elision."""

    label = ElidedCaptionLabel(text, parent)
    label.setWordWrap(False)
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    label.setFixedHeight(max(16, label.fontMetrics().height() + 2))
    return label


def _font_square_size(widget: QWidget) -> int:
    """Return a square control size matching the current font line height."""

    return max(14, widget.fontMetrics().height())


def _clear_layout(layout: QVBoxLayout) -> None:
    """Remove and delete all items owned by a vertical layout."""

    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()


def _visible_layout_height(layout: QVBoxLayout) -> int:
    """Return a compact height for visible widgets in one vertical layout."""

    margins = layout.contentsMargins()
    height = margins.top() + margins.bottom()
    visible_items = 0
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item is None:
            continue
        widget = item.widget()
        if widget is None:
            continue
        if (
            widget.objectName() == "comfyEnvironmentClaimantChildren"
            and widget.isHidden()
        ):
            continue
        if visible_items:
            height += max(0, layout.spacing())
        height += _widget_compact_height(widget)
        visible_items += 1
    return height


def _widget_compact_height(widget: QWidget) -> int:
    """Return a usable row height even before Qt resolves a fresh size hint."""

    hinted_height = widget.sizeHint().height()
    if hinted_height > 0:
        return hinted_height
    return max(16, widget.fontMetrics().height() + 2)


def _with_soft_wrap_breaks(text: str) -> str:
    """Return text with invisible break hints inside long tokens."""

    pieces: list[str] = []
    run_length = 0
    for character in text:
        pieces.append(character)
        if character.isspace():
            run_length = 0
            continue
        run_length += 1
        if character in _SOFT_WRAP_AFTER or run_length >= _SOFT_WRAP_RUN_LENGTH:
            pieces.append(_SOFT_WRAP_BREAK)
            run_length = 0
    return "".join(pieces)


def _summary_text(package: ComfyEnvironmentPackage) -> str:
    """Return package summary text without inventing package-specific facts."""

    return package.summary or "Summary unavailable"


def _package_metadata_line(package: ComfyEnvironmentPackage) -> str:
    """Return compact metadata facts for one selected package."""

    claimant_total = claimant_count(package)
    claimant_text = (
        "1 extension claimant"
        if claimant_total == 1
        else f"{claimant_total} extension claimants"
    )
    attribution = package.attribution.replace("-", " ").title()
    summary_source = package.summary_source.replace("-", " ")
    return f"{claimant_text} | {attribution} | summary: {summary_source}"


def _claimant_detail(package: ComfyEnvironmentPackage) -> str:
    """Return all claimant details for one package."""

    if not package.claimants:
        return "Required by:\nNo known extension claimant."
    lines: list[str] = []
    for group_name, claimants in _group_claimants_by_required_via(package.claimants):
        if group_name is None:
            lines.extend(
                claimant.display_name
                for claimant in sorted(claimants, key=_claimant_sort_key)
            )
            continue
        lines.append(group_name)
        lines.extend(
            f"    {claimant.display_name}"
            for claimant in sorted(claimants, key=_claimant_sort_key)
        )
    return "Required by:\n" + "\n".join(lines)


def _group_claimants_by_required_via(
    claimants: tuple[ComfyPackageClaimant, ...],
) -> tuple[tuple[str | None, tuple[ComfyPackageClaimant, ...]], ...]:
    """Group claimants by the immediate package that pulled in the selected package."""

    groups: dict[str | None, dict[tuple[str, str], ComfyPackageClaimant]] = {}
    for claimant in claimants:
        group_name = claimant.required_via
        groups.setdefault(group_name, {}).setdefault(
            (claimant.kind, claimant.claimant_id),
            claimant,
        )
    return tuple(
        (
            group_name,
            tuple(group_claimants.values()),
        )
        for group_name, group_claimants in sorted(
            groups.items(),
            key=lambda item: _required_via_sort_key(item[0]),
        )
    )


def _required_via_sort_key(group_name: str | None) -> tuple[int, str]:
    """Sort direct dependency claimants before transitive package groups."""

    if group_name is None:
        return (0, "")
    return (1, group_name.casefold())


def _claimant_sort_key(claimant: ComfyPackageClaimant) -> tuple[int, str]:
    """Sort Comfy and internal claimants before third-party extensions."""

    normalized = claimant.display_name.strip().lower()
    if normalized == "comfyui":
        return (0, normalized)
    if normalized.startswith(("comfyui", "comfy-ui", "comfy ")):
        return (1, normalized)
    if normalized.startswith(("substitute", "internal")):
        return (2, normalized)
    return (3, normalized)


def _management_tag_detail(package: ComfyEnvironmentPackage) -> str:
    """Return management tag details for one package."""

    lines = [
        f"{tag.display_name}: {', '.join(tag.supported_actions)}"
        for tag in package.management_tags
        if tag.supported_actions
    ]
    if not lines:
        return ""
    return "Supported actions:\n" + "\n".join(lines)
