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

"""Render the About landing page in the integrated Settings workspace."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationText
from sugarsubstitute_shared.presentation.localization import (
    LocalizationBindings,
    apply_application_text,
    app_text,
    render_application_text,
)
from substitute.presentation.localization import (
    LocalizedCaptionLabel,
    LocalizedPushButton,
    LocalizedStrongBodyLabel,
)

from collections.abc import Callable
from typing import Literal

from PySide6.QtCore import QEvent, QObject, QRect, QRectF, QSize, Qt, QUrl
from PySide6.QtGui import (
    QDesktopServices,
    QEnterEvent,
    QFont,
    QIcon,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QGridLayout,
    QHBoxLayout,
    QLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CaptionLabel,
    FluentIcon as FIF,
    IconWidget,
    PushButton,
)

from substitute.application.about import (
    ABOUT_LICENSE_PREAMBLE,
    GPL_V3_LICENSE_HTML,
    AboutInfoService,
    AboutInfoSnapshot,
    AboutVersionRow,
)
from sugarsubstitute_shared.presentation.localization import (
    set_localized_accessible_name,
    set_localized_tooltip,
)
from substitute.presentation.dialogs import LicenseDialog
from substitute.presentation.resources import app_icons_rc
from substitute.presentation.resources.app_icon import AppIcon, app_icon_resource_path
from substitute.presentation.resources.brand_icons import qt_logo_icon_path
from substitute.presentation.settings.settings_card import SettingsCard
from substitute.presentation.settings.settings_card_group import SettingsCardGroup
from substitute.presentation.settings.settings_async import (
    SettingsAsyncTaskResult,
    SettingsAsyncTaskRunnerFactory,
)
from substitute.presentation.settings.settings_style import (
    SETTINGS_CARD_GROUP_SPACING,
    SETTINGS_CARD_GROUP_TOP_MARGIN,
    SETTINGS_CARD_GROUP_TITLE_BOTTOM_MARGIN,
    SETTINGS_CARD_ICON_MAX_SIZE,
    SETTINGS_CARD_MIN_WIDTH,
    SETTINGS_CARD_RADIUS,
    settings_card_border_color,
    settings_card_fill_color,
    settings_card_overlay_color,
)

_PRODUCT_DESCRIPTION = app_text(
    "A desktop frontend for building and running ComfyUI workflows with SugarCubes."
)
_EMPTY_SUPPORTERS_TEXT = app_text("Supporter acknowledgements will appear here.")
_EMPTY_SPECIAL_THANKS_TEXT = app_text(
    "Special thanks acknowledgements will appear here."
)
_VERSION_GRID_TWO_COLUMN_WIDTH = 920
_VERSION_COMPACT_CARD_WIDTH = 420
_VERSION_MINIMUM_CARD_WIDTH = 360
_VERSION_METADATA_COLUMN_WIDTH = 180
_VERSION_LINK_BUTTON_SIZE = 38
_VERSION_LINK_ICON_SIZE = 24
_VERSION_METADATA_GAP = 10
_VERSION_WIDE_CARD_HEIGHT = 80
_VERSION_COMPACT_CARD_HEIGHT = 108
_VERSION_MINIMUM_CARD_HEIGHT = 116
_VERSION_CARD_HORIZONTAL_PADDING = 16
_VERSION_CARD_VERTICAL_PADDING = 14
_VERSION_SUBTITLE_FONT_SIZE = 11
_VERSION_WIDE_SUBTITLE_MAX_LINES = 2
_VERSION_UNBOUNDED_MAX_WIDTH = 16777215

_AboutVersionCardLayoutMode = Literal["wide", "compact", "minimum"]
_VersionRepositoryIconKind = Literal["github", "qt"]
_ABOUT_SNAPSHOT_TASK_ID = "about.snapshot"


class AboutSettingsPage(QWidget):
    """Render project identity, versions, and acknowledgements for Settings."""

    def __init__(
        self,
        service: AboutInfoService,
        parent: QWidget | None = None,
        *,
        task_runner_factory: SettingsAsyncTaskRunnerFactory,
    ) -> None:
        """Create the About Settings page bound to one info service."""

        super().__init__(parent)
        self._service = service
        self._snapshot: AboutInfoSnapshot = service.placeholder_snapshot()
        self._refresh_generation = 0
        self._refresh_in_flight = False
        self._refreshed_once = False
        self._async_runner = task_runner_factory(
            self,
            owner_id="about_settings",
        )
        self._async_runner.taskCompleted.connect(self._apply_loaded_snapshot)
        self._supporters_group: SettingsCardGroup
        self._special_thanks_group: SettingsCardGroup
        self._build_layout()

    def refresh(self) -> None:
        """Request a non-blocking reload of About information."""

        self.refresh_async()

    def set_settings_page_active(self, active: bool) -> None:
        """Start non-blocking About metadata loading when the page becomes active."""

        if active and not self._refreshed_once and not self._refresh_in_flight:
            self.refresh_async()

    def refresh_async(self) -> None:
        """Load About information through the shared Settings async boundary."""

        if self._refresh_in_flight:
            return
        self._refresh_generation += 1
        self._refresh_in_flight = True
        self._async_runner.run(
            task_id=_ABOUT_SNAPSHOT_TASK_ID,
            generation=self._refresh_generation,
            operation=self._service.snapshot,
            context={"page": "about"},
        )

    def bind_snapshot(self, snapshot: AboutInfoSnapshot) -> None:
        """Bind one About information snapshot into stable child widgets."""

        previous_supporters = self._snapshot.supporters
        previous_special_thanks = self._snapshot.special_thanks
        self._snapshot = snapshot
        self._version_group.set_rows(snapshot.versions)
        apply_application_text(
            self._project_card.description_label,
            snapshot.project_summary,
        )
        if snapshot.supporters != previous_supporters:
            self._supporters_group = self._replace_group(
                self._supporters_group,
                self._acknowledgement_group(
                    app_text("Supporters"),
                    snapshot.supporters,
                    empty_text=_EMPTY_SUPPORTERS_TEXT,
                    icon=AppIcon.HEART_20_REGULAR,
                ),
            )
        if snapshot.special_thanks != previous_special_thanks:
            self._special_thanks_group = self._replace_group(
                self._special_thanks_group,
                self._acknowledgement_group(
                    app_text("Special thanks"),
                    snapshot.special_thanks,
                    empty_text=_EMPTY_SPECIAL_THANKS_TEXT,
                    icon=AppIcon.STAR_20_REGULAR,
                ),
            )

    def _build_layout(self) -> None:
        """Create the page layout and initial content."""

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(SETTINGS_CARD_GROUP_TOP_MARGIN)
        self._identity_header = _IdentityHeader(self)
        self._version_group = _VersionCardGroup(self._snapshot.versions, parent=self)
        self._project_card = SettingsCard(
            title=app_text("SugarSubstitute"),
            description=self._snapshot.project_summary,
            visual_widget=_settings_icon_widget(self, AppIcon.CUBE_20_FILLED),
            content_alignment="vertical",
            parent=self,
        )
        self._project_group = SettingsCardGroup(
            app_text("Project"),
            cards=(self._project_card,),
            parent=self,
        )
        self._license_group = SettingsCardGroup(
            app_text("License"),
            cards=(
                SettingsCard(
                    title=app_text("GNU General Public License v3"),
                    description=ABOUT_LICENSE_PREAMBLE,
                    visual_widget=_settings_icon_widget(
                        self,
                        AppIcon.CERTIFICATE_20_REGULAR,
                    ),
                    trailing_widget=self._license_action_row(self),
                    content_alignment="vertical",
                    parent=self,
                ),
            ),
            parent=self,
        )
        self._supporters_group = self._acknowledgement_group(
            app_text("Supporters"),
            self._snapshot.supporters,
            empty_text=_EMPTY_SUPPORTERS_TEXT,
            icon=AppIcon.HEART_20_REGULAR,
        )
        self._special_thanks_group = self._acknowledgement_group(
            app_text("Special thanks"),
            self._snapshot.special_thanks,
            empty_text=_EMPTY_SPECIAL_THANKS_TEXT,
            icon=AppIcon.STAR_20_REGULAR,
        )
        self._layout.addWidget(self._identity_header)
        self._layout.addWidget(self._version_group)
        self._layout.addWidget(self._project_group)
        self._layout.addWidget(self._license_group)
        self._layout.addWidget(self._supporters_group)
        self._layout.addWidget(self._special_thanks_group)
        self._layout.addStretch(1)

    def _license_action_row(self, parent: QWidget) -> QWidget:
        """Create the bottom-right License card action row."""

        row = QWidget(parent)
        row.setObjectName("AboutLicenseActionRow")
        row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        row.setStyleSheet("background-color: transparent; border: none;")
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch(1)
        layout.addWidget(self._license_button(row), 0, Qt.AlignmentFlag.AlignRight)
        return row

    def _license_button(self, parent: QWidget) -> PushButton:
        """Create the GPLv3 modal action button."""

        button = LocalizedPushButton(app_text("Read GPLv3"), parent)
        button.setObjectName("AboutReadLicenseButton")
        button.setIcon(FIF.DOCUMENT)
        button.clicked.connect(self._show_license_dialog)
        return button

    def _show_license_dialog(self) -> None:
        """Open the GPLv3 license reader modal."""

        window = self.window()
        dialog_parent = window if isinstance(window, QWidget) else self
        dialog = LicenseDialog(
            license_html=GPL_V3_LICENSE_HTML,
            parent=dialog_parent,
        )
        dialog.exec()

    def _acknowledgement_group(
        self,
        title: ApplicationText,
        entries: tuple[str, ...],
        *,
        empty_text: ApplicationText,
        icon: AppIcon,
    ) -> SettingsCardGroup:
        """Create one acknowledgement Settings card group."""

        return SettingsCardGroup(
            title,
            cards=_acknowledgement_cards(
                entries,
                empty_text=empty_text,
                icon=icon,
                parent=self,
            ),
            parent=self,
        )

    def _replace_group(
        self,
        old_group: SettingsCardGroup,
        new_group: SettingsCardGroup,
    ) -> SettingsCardGroup:
        """Replace one dynamic acknowledgement group in the page layout."""

        index = self._layout.indexOf(old_group)
        if index < 0:
            self._layout.addWidget(new_group)
        else:
            item = self._layout.takeAt(index)
            _ = item
            old_group.setParent(None)
            old_group.deleteLater()
            self._layout.insertWidget(index, new_group)
        return new_group

    def _apply_loaded_snapshot(self, payload: object) -> None:
        """Apply one task-loaded About snapshot on the UI thread."""

        if (
            not isinstance(payload, SettingsAsyncTaskResult)
            or payload.task_id != _ABOUT_SNAPSHOT_TASK_ID
        ):
            return
        if payload.generation != self._refresh_generation:
            return
        self._refresh_in_flight = False
        if isinstance(payload.value, AboutInfoSnapshot):
            self.bind_snapshot(payload.value)
            self._refreshed_once = True
        elif payload.error is not None:
            self._refreshed_once = True


class _IdentityHeader(QWidget):
    """Render the compact product identity block for the About page."""

    def __init__(self, parent: QWidget) -> None:
        """Create the identity header."""

        super().__init__(parent)
        self.setObjectName("AboutSettingsIdentityHeader")
        self._build_layout()

    def _build_layout(self) -> None:
        """Create the logo and product labels."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        logo = QLabel(self)
        logo.setObjectName("AboutSettingsLogo")
        _ = app_icons_rc
        pixmap = QPixmap(app_icon_resource_path(128))
        logo.setPixmap(pixmap)
        logo.setFixedSize(128, 128)
        logo.setScaledContents(True)
        logo.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        title = LocalizedStrongBodyLabel(app_text("SugarSubstitute"), self)
        title.setObjectName("AboutSettingsProductName")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        description = LocalizedCaptionLabel(_PRODUCT_DESCRIPTION, self)
        description.setObjectName("AboutSettingsProductDescription")
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)
        layout.addWidget(description)


class _VersionCardGroup(QWidget):
    """Render About version cards in a responsive one- or two-column grid."""

    def __init__(
        self,
        rows: tuple[AboutVersionRow, ...],
        *,
        parent: QWidget | None = None,
    ) -> None:
        """Create the version group for one snapshot."""

        super().__init__(parent)
        self.setObjectName("AboutVersionCardGroup")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent; border: none;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self._cards_by_key: dict[str, _AboutVersionCard] = {}
        self._card_order: tuple[str, ...] = ()
        self._column_count = 0
        self._build_layout()
        self.set_rows(rows)
        self._sync_grid_columns()

    def set_rows(self, rows: tuple[AboutVersionRow, ...]) -> None:
        """Reconcile version cards from one About snapshot."""

        next_order: list[str] = []
        live_keys: set[str] = set()
        for row in rows:
            key = _version_object_key(row.component_key)
            next_order.append(key)
            live_keys.add(key)
            card = self._cards_by_key.get(key)
            if card is None:
                self._cards_by_key[key] = _version_card(row, self._card_container)
                continue
            card.set_row(row)
        for key in tuple(self._cards_by_key):
            if key in live_keys:
                continue
            card = self._cards_by_key.pop(key)
            self._grid_layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        next_card_order = tuple(next_order)
        if next_card_order != self._card_order:
            self._card_order = next_card_order
            self._column_count = 0
        self._sync_grid_columns()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Reflow version cards when the Settings page changes width."""

        super().resizeEvent(event)
        self._sync_grid_columns()

    def _build_layout(self) -> None:
        """Create the section header and responsive card grid."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SETTINGS_CARD_GROUP_TITLE_BOTTOM_MARGIN)

        self.title_label = LocalizedStrongBodyLabel(
            app_text("Version information"), self
        )
        layout.addWidget(self.title_label)

        self._card_container = QWidget(self)
        self._card_container.setObjectName("AboutVersionCardGrid")
        self._card_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._card_container.setStyleSheet(
            "background-color: transparent; border: none;"
        )
        self._card_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        self._grid_layout = QGridLayout(self._card_container)
        self._grid_layout.setSizeConstraint(
            QLayout.SizeConstraint.SetDefaultConstraint,
        )
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self._grid_layout.setHorizontalSpacing(SETTINGS_CARD_GROUP_SPACING)
        self._grid_layout.setVerticalSpacing(SETTINGS_CARD_GROUP_SPACING)
        layout.addWidget(self._card_container)

    def _sync_grid_columns(self) -> None:
        """Place cards into the current responsive column count."""

        column_count = 2 if self.width() >= _VERSION_GRID_TWO_COLUMN_WIDTH else 1
        self.setProperty("aboutVersionColumnCount", column_count)
        if column_count == self._column_count:
            self._sync_card_width_limits(column_count)
            return
        self._column_count = column_count
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setParent(self._card_container)
        self._reset_grid_columns()
        for index, card in enumerate(self._ordered_cards()):
            if column_count == 2:
                row = index // column_count
                column = index % column_count
            else:
                row = index
                column = 0
            self._grid_layout.addWidget(card, row, column)
        self._sync_card_width_limits(column_count)

    def _reset_grid_columns(self) -> None:
        """Reset grid column stretch before applying the active column mode."""

        for column in range(3):
            self._grid_layout.setColumnMinimumWidth(column, 0)
            self._grid_layout.setColumnStretch(column, 0)
        if self._column_count == 2:
            self._grid_layout.setColumnStretch(0, 1)
            self._grid_layout.setColumnStretch(1, 1)
            return
        self._grid_layout.setColumnStretch(0, 1)

    def _sync_card_width_limits(self, column_count: int) -> None:
        """Apply the card width limits required by the active grid mode."""

        _ = column_count
        for card in self._ordered_cards():
            card.setMaximumWidth(_VERSION_UNBOUNDED_MAX_WIDTH)

    def _ordered_cards(self) -> tuple["_AboutVersionCard", ...]:
        """Return version cards in current snapshot order."""

        return tuple(self._cards_by_key[key] for key in self._card_order)


class _AboutVersionCard(QFrame):
    """Render one responsive About version metadata card."""

    def __init__(
        self,
        row: AboutVersionRow,
        *,
        parent: QWidget | None = None,
    ) -> None:
        """Create a responsive card for one About version row."""

        super().__init__(parent)
        self._row = row
        self._object_key = _version_object_key(row.component_key)
        self._title_text = row.label
        self._subtitle_text = row.subtitle
        self._value_text = row.value
        self._author_text: ApplicationText = (
            app_text("by %1", row.authors) if row.authors else ""
        )
        self._activation_handler = (
            _open_url_handler(row.external_url) if row.external_url else None
        )
        self._layout_mode: _AboutVersionCardLayoutMode = "wide"
        self._hovered = False
        self._pressed = False

        self.setObjectName(f"AboutVersionCard-{self._object_key}")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent; border: none;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(SETTINGS_CARD_MIN_WIDTH)
        self.setFixedHeight(_VERSION_WIDE_CARD_HEIGHT)
        self.setProperty("externalUrl", row.external_url)
        self.setProperty("aboutVersionLayoutMode", self._layout_mode)
        self.setProperty("aboutVersionHovered", False)
        self.setProperty("aboutVersionPressed", False)
        self.setMouseTracking(True)
        self.title_label = self._create_title_label()
        self.subtitle_label = self._create_subtitle_label()
        self.value_label = self._create_value_label()
        self.author_label = self._create_author_label()
        self._localization_bindings = LocalizationBindings(self)
        self._localization_bindings.bind_tooltip(
            self,
            lambda: (
                render_application_text(
                    app_text("Open %1 project website", self._row.label)
                )
                if self._row.external_url
                else ""
            ),
        )
        self._localization_bindings.bind_tooltip(
            self.title_label,
            lambda: render_application_text(self._title_text),
        )
        self._localization_bindings.bind_tooltip(
            self.subtitle_label,
            lambda: render_application_text(self._subtitle_text),
        )
        self._localization_bindings.bind_tooltip(
            self.value_label,
            self._value_tooltip,
        )
        self._localization_bindings.bind_tooltip(
            self.author_label,
            lambda: render_application_text(self._author_text),
        )
        self.trailing_widget = self._create_transparent_slot(
            f"AboutVersionTrailing-{self._object_key}"
        )
        self.metadata_slot = self._create_transparent_slot(
            f"AboutVersionMetadata-{self._object_key}"
        )
        self.metadata_text = self._create_transparent_slot(
            f"AboutVersionMetadataText-{self._object_key}"
        )
        self.icon_slot = _version_repository_icon(
            row,
            self,
            self._activate,
            self._set_pressed,
        )
        self._sync_interaction_cursors()
        for child in (
            self.title_label,
            self.subtitle_label,
            self.value_label,
            self.author_label,
        ):
            child.installEventFilter(self)
        self._layout_content()

    def set_row(self, row: AboutVersionRow) -> None:
        """Bind updated version metadata while preserving card identity."""

        object_key = _version_object_key(row.component_key)
        if object_key != self._object_key:
            raise ValueError("Cannot bind About version row with a different identity.")
        previous_icon_kind = _version_repository_icon_kind(self._row)
        next_icon_kind = _version_repository_icon_kind(row)
        self._row = row
        self._title_text = row.label
        self._subtitle_text = row.subtitle
        self._value_text = row.value
        self._author_text = app_text("by %1", row.authors) if row.authors else ""
        self._activation_handler = (
            _open_url_handler(row.external_url) if row.external_url else None
        )
        self.setProperty("externalUrl", row.external_url)
        self.value_label.setProperty("aboutVersionStatus", row.status.value)
        self.author_label.setVisible(bool(self._author_text))
        self._localization_bindings.retranslate()
        self._sync_repository_icon(
            row,
            previous_kind=previous_icon_kind,
            next_kind=next_icon_kind,
        )
        self._sync_interaction_cursors()
        self._sync_layout_mode()
        self._layout_content()
        self.update()

    def sizeHint(self) -> QSize:
        """Return the preferred size for a normal full-width Settings card."""

        return QSize(SETTINGS_CARD_MIN_WIDTH, self._mode_height())

    def changeEvent(self, event: QEvent) -> None:
        """Re-elide translated metadata when the application language changes."""

        super().changeEvent(event)
        if event.type() == QEvent.Type.LanguageChange:
            self._sync_elided_text()

    def minimumSizeHint(self) -> QSize:
        """Return the minimum viable size for the responsive metadata tile."""

        return QSize(SETTINGS_CARD_MIN_WIDTH, self._mode_height())

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Activate linked cards when label children receive body clicks."""

        _ = watched
        if self._activation_handler is None:
            return super().eventFilter(watched, event)
        if not isinstance(event, QMouseEvent):
            return super().eventFilter(watched, event)
        if event.button() != Qt.MouseButton.LeftButton:
            return super().eventFilter(watched, event)
        if event.type() == QEvent.Type.MouseButtonPress:
            self._set_pressed(True)
            event.accept()
            return True
        if event.type() == QEvent.Type.MouseButtonRelease:
            self._set_pressed(False)
            self._activate()
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def enterEvent(self, event: QEnterEvent) -> None:
        """Apply hover feedback when the pointer enters an interactive card."""

        self._set_hovered(True)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Clear hover and press feedback when the pointer leaves the card."""

        self._set_hovered(False)
        self._set_pressed(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Consume body presses for linked cards so release activates once."""

        if (
            self._activation_handler is not None
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self._set_pressed(True)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Keep hover feedback current for synthesized and native pointer moves."""

        self._set_hovered(True)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Open the project link when a linked card body is clicked."""

        if (
            self._activation_handler is not None
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self._set_pressed(False)
            self._activate()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Recompute card mode and child geometry when width changes."""

        super().resizeEvent(event)
        self._sync_layout_mode()
        self._layout_content()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the About card using the shared Settings card material."""

        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(settings_card_border_color())
        painter.setBrush(settings_card_fill_color(self))
        painter.drawRoundedRect(rect, SETTINGS_CARD_RADIUS, SETTINGS_CARD_RADIUS)
        if self._activation_handler is None:
            return
        overlay = settings_card_overlay_color(
            pressed=self._pressed,
            hovered=self._hovered,
        )
        if overlay.alpha() <= 0:
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(overlay)
        painter.drawRoundedRect(rect, SETTINGS_CARD_RADIUS, SETTINGS_CARD_RADIUS)

    def _create_title_label(self) -> BodyLabel:
        """Create the component title label."""

        label = BodyLabel(render_application_text(self._title_text), self)
        label.setObjectName(f"AboutVersionTitle-{self._object_key}")
        font = label.font()
        font.setWeight(QFont.Weight.DemiBold)
        label.setFont(font)
        label.setWordWrap(False)
        return label

    def _create_subtitle_label(self) -> CaptionLabel:
        """Create the compact component description label."""

        label = CaptionLabel(render_application_text(self._subtitle_text), self)
        label.setObjectName(f"AboutVersionSubtitle-{self._object_key}")
        font = label.font()
        font.setPixelSize(_VERSION_SUBTITLE_FONT_SIZE)
        label.setFont(font)
        label.setWordWrap(False)
        return label

    def _create_value_label(self) -> BodyLabel:
        """Create the version value label."""

        label = BodyLabel(self)
        label.setObjectName(f"AboutVersionValue-{self._object_key}")
        label.setProperty("aboutVersionStatus", self._row.status.value)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    def _create_author_label(self) -> CaptionLabel:
        """Create the author attribution label."""

        label = CaptionLabel(self._author_text, self)
        label.setObjectName(f"AboutVersionAuthor-{self._object_key}")
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setVisible(bool(self._author_text))
        return label

    def _value_tooltip(self) -> str:
        """Return localized status copy plus opaque runtime detail."""

        return "\n\n".join(
            render_application_text(part)
            for part in (self._row.value, self._row.detail)
            if part
        )

    def _create_transparent_slot(self, object_name: str) -> QWidget:
        """Create one transparent geometry slot for compatibility and testing."""

        slot = QWidget(self)
        slot.setObjectName(object_name)
        slot.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        slot.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        slot.setStyleSheet("background-color: transparent; border: none;")
        return slot

    def _sync_repository_icon(
        self,
        row: AboutVersionRow,
        *,
        previous_kind: _VersionRepositoryIconKind | None,
        next_kind: _VersionRepositoryIconKind | None,
    ) -> None:
        """Recreate or update the project link icon for the current row."""

        if previous_kind != next_kind:
            if self.icon_slot is not None:
                self.icon_slot.setParent(None)
                self.icon_slot.deleteLater()
            self.icon_slot = _version_repository_icon(
                row,
                self,
                self._activate,
                self._set_pressed,
            )
            return
        if self.icon_slot is None:
            return
        _bind_version_repository_text(self.icon_slot, row)
        for child in self.icon_slot.findChildren(QWidget):
            _bind_version_repository_text(child, row)

    def _sync_layout_mode(self) -> None:
        """Select the internal layout that fits the current card width."""

        width = self.width()
        if width < _VERSION_MINIMUM_CARD_WIDTH:
            mode: _AboutVersionCardLayoutMode = "minimum"
        elif width <= _VERSION_COMPACT_CARD_WIDTH:
            mode = "compact"
        else:
            mode = "wide"
        if mode == self._layout_mode:
            return
        self._layout_mode = mode
        self.setProperty("aboutVersionLayoutMode", mode)
        self.setFixedHeight(self._mode_height())
        self.updateGeometry()

    def _layout_content(self) -> None:
        """Lay out labels and link affordances for the active width mode."""

        if self._layout_mode == "wide":
            self._layout_wide_content()
        else:
            self._layout_stacked_content()
        for widget in (
            self.trailing_widget,
            self.metadata_slot,
            self.metadata_text,
            self.title_label,
            self.subtitle_label,
            self.value_label,
            self.author_label,
        ):
            widget.raise_()
        if self.icon_slot is not None:
            self.icon_slot.raise_()

    def _layout_wide_content(self) -> None:
        """Lay out the normal two-column metadata tile internals."""

        card_width = self.width()
        card_height = _VERSION_WIDE_CARD_HEIGHT
        content_x = _VERSION_CARD_HORIZONTAL_PADDING
        content_gap = _VERSION_METADATA_GAP
        trailing_width = self._trailing_width()
        trailing_x = max(
            content_x,
            card_width - _VERSION_CARD_HORIZONTAL_PADDING - trailing_width,
        )
        text_width = max(0, trailing_x - content_gap - content_x)

        title_height = self._label_height(self.title_label)
        subtitle_height = self._wide_subtitle_height(text_width)
        text_height = title_height + 1 + subtitle_height
        text_y = max(0, (card_height - text_height) // 2)

        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.subtitle_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.subtitle_label.setWordWrap(False)
        self.value_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.author_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.title_label.setGeometry(content_x, text_y, text_width, title_height)
        self.subtitle_label.setGeometry(
            content_x,
            text_y + title_height + 1,
            text_width,
            subtitle_height,
        )

        metadata_y = (card_height - _VERSION_LINK_BUTTON_SIZE) // 2
        metadata_text_height = self._metadata_text_height()
        metadata_text_y = (
            metadata_y + (_VERSION_LINK_BUTTON_SIZE - metadata_text_height) // 2
        )
        self.trailing_widget.setGeometry(
            trailing_x,
            metadata_y,
            trailing_width,
            _VERSION_LINK_BUTTON_SIZE,
        )
        self.metadata_slot.setGeometry(
            trailing_x,
            metadata_y,
            _VERSION_METADATA_COLUMN_WIDTH,
            _VERSION_LINK_BUTTON_SIZE,
        )
        self.metadata_text.setGeometry(
            trailing_x,
            metadata_text_y,
            _VERSION_METADATA_COLUMN_WIDTH,
            metadata_text_height,
        )
        self._set_value_geometry(
            QRect(
                trailing_x,
                metadata_text_y,
                _VERSION_METADATA_COLUMN_WIDTH,
                self._label_height(self.value_label),
            ),
        )
        if self._author_text:
            self._set_author_geometry(
                QRect(
                    trailing_x,
                    metadata_text_y + self._label_height(self.value_label) + 1,
                    _VERSION_METADATA_COLUMN_WIDTH,
                    self._label_height(self.author_label),
                ),
            )
        if self.icon_slot is not None:
            self.icon_slot.setGeometry(
                trailing_x + _VERSION_METADATA_COLUMN_WIDTH + _VERSION_METADATA_GAP,
                metadata_y,
                _VERSION_LINK_BUTTON_SIZE,
                _VERSION_LINK_BUTTON_SIZE,
            )
        self._sync_elided_text()

    def _layout_stacked_content(self) -> None:
        """Lay out compact and minimum cards as explicit stacked metadata."""

        card_width = self.width()
        card_height = self._mode_height()
        content_x = _VERSION_CARD_HORIZONTAL_PADDING
        content_width = max(0, card_width - _VERSION_CARD_HORIZONTAL_PADDING * 2)
        icon_width = _VERSION_LINK_BUTTON_SIZE if self.icon_slot is not None else 0
        title_height = self._label_height(self.title_label)
        value_height = self._label_height(self.value_label)
        subtitle_height = self._single_line_label_height(self.subtitle_label)
        author_height = self._label_height(self.author_label)

        value_width = self._stacked_value_width(content_width)
        title_width = max(0, content_width - value_width - _VERSION_METADATA_GAP)
        top_y = _VERSION_CARD_VERTICAL_PADDING
        top_height = max(title_height, value_height)
        subtitle_y = top_y + top_height + 4
        bottom_y = (
            card_height - _VERSION_CARD_VERTICAL_PADDING - _VERSION_LINK_BUTTON_SIZE
        )
        author_width = max(0, content_width - icon_width - _VERSION_METADATA_GAP)

        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.subtitle_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.subtitle_label.setWordWrap(False)
        self.value_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.author_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.title_label.setGeometry(content_x, top_y, title_width, title_height)
        self._set_value_geometry(
            QRect(
                content_x + content_width - value_width,
                top_y,
                value_width,
                value_height,
            ),
        )
        self.subtitle_label.setGeometry(
            content_x,
            subtitle_y,
            content_width,
            subtitle_height,
        )
        self.trailing_widget.setGeometry(
            content_x,
            bottom_y,
            content_width,
            _VERSION_LINK_BUTTON_SIZE,
        )
        self.metadata_slot.setGeometry(
            content_x,
            bottom_y,
            author_width,
            _VERSION_LINK_BUTTON_SIZE,
        )
        self.metadata_text.setGeometry(
            content_x,
            bottom_y + (_VERSION_LINK_BUTTON_SIZE - author_height) // 2,
            author_width,
            author_height,
        )
        if self._author_text:
            self._set_author_geometry(
                QRect(
                    content_x,
                    bottom_y + (_VERSION_LINK_BUTTON_SIZE - author_height) // 2,
                    author_width,
                    author_height,
                )
            )
        if self.icon_slot is not None:
            self.icon_slot.setGeometry(
                content_x + content_width - icon_width,
                bottom_y,
                icon_width,
                _VERSION_LINK_BUTTON_SIZE,
            )
        self._sync_elided_text()

    def _set_value_geometry(self, rect: QRect) -> None:
        """Apply version value geometry and keep the label visible."""

        self.value_label.setGeometry(rect)
        self.value_label.setVisible(rect.width() > 0 and rect.height() > 0)

    def _set_author_geometry(self, rect: QRect) -> None:
        """Apply author geometry while preserving empty-author rows."""

        self.author_label.setGeometry(rect)
        self.author_label.setVisible(bool(self._author_text) and rect.width() > 0)

    def _sync_elided_text(self) -> None:
        """Elide text labels to their current geometry while preserving tooltips."""

        self.title_label.setText(
            _elided_label_text(
                self.title_label,
                render_application_text(self._title_text),
                self.title_label.width(),
                Qt.TextElideMode.ElideRight,
            )
        )
        if self._layout_mode == "wide":
            self.subtitle_label.setText(
                _elided_wrapped_label_text(
                    self.subtitle_label,
                    render_application_text(self._subtitle_text),
                    self.subtitle_label.width(),
                    _VERSION_WIDE_SUBTITLE_MAX_LINES,
                )
            )
        else:
            self.subtitle_label.setText(
                _elided_label_text(
                    self.subtitle_label,
                    render_application_text(self._subtitle_text),
                    self.subtitle_label.width(),
                    Qt.TextElideMode.ElideRight,
                )
            )
        self.value_label.setText(
            _elided_label_text(
                self.value_label,
                render_application_text(self._value_text),
                self.value_label.width(),
                Qt.TextElideMode.ElideMiddle,
            )
        )
        self.author_label.setText(
            _elided_label_text(
                self.author_label,
                render_application_text(self._author_text),
                self.author_label.width(),
                Qt.TextElideMode.ElideRight,
            )
        )

    def _activate(self) -> None:
        """Open the external project URL when this card has one."""

        if self._activation_handler is not None:
            self._activation_handler()

    def _set_hovered(self, hovered: bool) -> None:
        """Store hover state and repaint when interaction feedback changes."""

        if self._activation_handler is None or self._hovered == hovered:
            return
        self._hovered = hovered
        self.setProperty("aboutVersionHovered", hovered)
        self.update()

    def _set_pressed(self, pressed: bool) -> None:
        """Store press state and repaint when interaction feedback changes."""

        if self._activation_handler is None or self._pressed == pressed:
            return
        self._pressed = pressed
        self.setProperty("aboutVersionPressed", pressed)
        self.update()

    def _sync_interaction_cursors(self) -> None:
        """Apply linked-card pointer cursors to the card and passive targets."""

        cursor = (
            Qt.CursorShape.PointingHandCursor
            if self._activation_handler is not None
            else Qt.CursorShape.ArrowCursor
        )
        for target in self._cursor_targets():
            target.setCursor(cursor)

    def _cursor_targets(self) -> tuple[QWidget, ...]:
        """Return card regions that should expose the linked-card cursor."""

        targets: list[QWidget] = [
            self,
            self.title_label,
            self.subtitle_label,
            self.value_label,
            self.author_label,
            self.trailing_widget,
            self.metadata_slot,
            self.metadata_text,
        ]
        if self.icon_slot is not None:
            targets.append(self.icon_slot)
            targets.extend(self.icon_slot.findChildren(QWidget))
        return tuple(targets)

    def _mode_height(self) -> int:
        """Return the fixed card height for the current layout mode."""

        if self._layout_mode == "minimum":
            return _VERSION_MINIMUM_CARD_HEIGHT
        if self._layout_mode == "compact":
            return _VERSION_COMPACT_CARD_HEIGHT
        return _VERSION_WIDE_CARD_HEIGHT

    def _label_height(self, label: QLabel) -> int:
        """Return a stable label height that preserves text descenders."""

        return max(label.sizeHint().height(), label.fontMetrics().height() + 2)

    def _single_line_label_height(self, label: QLabel) -> int:
        """Return a single-line label height independent of wrapped size hints."""

        return label.fontMetrics().height() + 2

    def _wide_subtitle_height(self, width: int) -> int:
        """Return a bounded two-line subtitle height for wide cards."""

        line_height = int(self.subtitle_label.fontMetrics().lineSpacing())
        if width <= 0:
            return line_height + 2
        subtitle = _elided_wrapped_label_text(
            self.subtitle_label,
            render_application_text(self._subtitle_text),
            width,
            _VERSION_WIDE_SUBTITLE_MAX_LINES,
        )
        line_count = max(
            1, min(_VERSION_WIDE_SUBTITLE_MAX_LINES, len(subtitle.splitlines()))
        )
        return line_count * line_height + 2

    def _metadata_text_height(self) -> int:
        """Return the stacked version/author metadata text height."""

        if not self._author_text:
            return self._label_height(self.value_label)
        return (
            self._label_height(self.value_label)
            + self._label_height(self.author_label)
            + 1
        )

    def _trailing_width(self) -> int:
        """Return the wide-mode metadata and project-icon cluster width."""

        if self.icon_slot is None:
            return _VERSION_METADATA_COLUMN_WIDTH
        return (
            _VERSION_METADATA_COLUMN_WIDTH
            + _VERSION_METADATA_GAP
            + _VERSION_LINK_BUTTON_SIZE
        )

    def _stacked_value_width(self, content_width: int) -> int:
        """Return the width reserved for the top-row version value."""

        limit = (
            120 if self._layout_mode == "minimum" else _VERSION_METADATA_COLUMN_WIDTH
        )
        return min(limit, max(72, content_width // 3))


class _VersionRepositoryIconSlot(QWidget):
    """Render a passive project icon slot that activates the owning card."""

    def __init__(
        self,
        activate: Callable[[], None],
        pressed_changed: Callable[[bool], None],
        *,
        parent: QWidget,
    ) -> None:
        """Create an activatable fixed-size project icon slot."""

        super().__init__(parent)
        self._activate = activate
        self._pressed_changed = pressed_changed
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent; border: none;")
        self.setFixedSize(_VERSION_LINK_BUTTON_SIZE, _VERSION_LINK_BUTTON_SIZE)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Consume linked icon presses so release activates once."""

        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed_changed(True)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Activate the owning version card from the passive icon area."""

        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed_changed(False)
            self._activate()
            event.accept()
            return
        super().mouseReleaseEvent(event)


def _version_card(row: AboutVersionRow, parent: QWidget) -> _AboutVersionCard:
    """Create one responsive About version card."""

    return _AboutVersionCard(row, parent=parent)


def _version_repository_icon(
    row: AboutVersionRow,
    parent: QWidget,
    activate: Callable[[], None],
    pressed_changed: Callable[[bool], None],
) -> QWidget | None:
    """Create one passive external project icon when the row has a known target."""

    if not row.external_url:
        return None
    slot = _VersionRepositoryIconSlot(
        activate,
        pressed_changed,
        parent=parent,
    )
    slot.setObjectName(
        f"AboutVersionLinkIconSlot-{_version_object_key(row.component_key)}"
    )
    _bind_version_repository_text(slot, row)

    layout = QHBoxLayout(slot)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    if _is_pyside_project_url(row.external_url):
        icon = IconWidget(QIcon(str(qt_logo_icon_path())), slot)
        icon.setObjectName(
            f"AboutVersionQtIcon-{_version_object_key(row.component_key)}"
        )
    else:
        icon = IconWidget(FIF.GITHUB, slot)
        icon.setObjectName(
            f"AboutVersionGitHubIcon-{_version_object_key(row.component_key)}"
        )
    icon.setFixedSize(_VERSION_LINK_ICON_SIZE, _VERSION_LINK_ICON_SIZE)
    icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    _bind_version_repository_text(icon, row)
    layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignCenter)
    return slot


def _version_repository_icon_kind(
    row: AboutVersionRow,
) -> _VersionRepositoryIconKind | None:
    """Return the repository icon kind represented by one version row."""

    if not row.external_url:
        return None
    return "qt" if _is_pyside_project_url(row.external_url) else "github"


def _bind_version_repository_text(target: QWidget, row: AboutVersionRow) -> None:
    """Bind project-link affordances while preserving their dynamic row label."""

    if _is_pyside_project_url(row.external_url):
        set_localized_tooltip(target, "Open the PySide6 project website")
        set_localized_accessible_name(target, "PySide6 project website")
        return
    set_localized_tooltip(target, "Open %1 repository on GitHub", row.label)
    set_localized_accessible_name(target, "%1 GitHub repository", row.label)


def _elided_label_text(
    label: QLabel,
    text: str,
    width: int,
    mode: Qt.TextElideMode,
) -> str:
    """Return text elided to one label's current layout width."""

    return label.fontMetrics().elidedText(text, mode, max(0, width))


def _elided_wrapped_label_text(
    label: QLabel,
    text: str,
    width: int,
    max_lines: int,
) -> str:
    """Return text split across bounded lines with the final line elided."""

    if max_lines <= 1:
        return _elided_label_text(
            label,
            " ".join(text.split()),
            width,
            Qt.TextElideMode.ElideRight,
        )
    available_width = max(0, width)
    if available_width <= 0:
        return ""
    metrics = label.fontMetrics()
    normalized = " ".join(text.split())
    if metrics.horizontalAdvance(normalized) <= available_width:
        return normalized

    remaining_words = normalized.split()
    lines: list[str] = []
    while remaining_words and len(lines) < max_lines:
        if len(lines) == max_lines - 1:
            lines.append(
                metrics.elidedText(
                    " ".join(remaining_words),
                    Qt.TextElideMode.ElideRight,
                    available_width,
                )
            )
            break

        line_words: list[str] = []
        while remaining_words:
            candidate = " ".join((*line_words, remaining_words[0]))
            if line_words and metrics.horizontalAdvance(candidate) > available_width:
                break
            word = remaining_words.pop(0)
            if not line_words and metrics.horizontalAdvance(word) > available_width:
                lines.append(
                    metrics.elidedText(
                        word,
                        Qt.TextElideMode.ElideRight,
                        available_width,
                    )
                )
                break
            line_words.append(word)
        if line_words:
            lines.append(" ".join(line_words))
    return "\n".join(lines)


def _is_pyside_project_url(url: str) -> bool:
    """Return whether one About link should use the Qt logo mark."""

    return url.rstrip("/") == "https://pyside.org"


def _open_url_handler(url: str) -> Callable[[], None]:
    """Return a Qt slot that opens one trusted repository URL."""

    def handler() -> None:
        _open_external_url(url)

    return handler


def _open_external_url(url: str) -> bool:
    """Open one trusted external repository URL through the desktop shell."""

    return bool(QDesktopServices.openUrl(QUrl(url)))


def _version_object_key(label: str) -> str:
    """Return a stable object-name suffix for one version row label."""

    return "".join(character for character in label if character.isalnum())


def _acknowledgement_cards(
    entries: tuple[str, ...],
    *,
    empty_text: ApplicationText,
    icon: AppIcon,
    parent: QWidget,
) -> tuple[SettingsCard, ...]:
    """Return acknowledgement cards or one graceful empty-state card."""

    if not entries:
        return (
            SettingsCard(
                title=empty_text,
                visual_widget=_settings_icon_widget(parent, icon),
                content_alignment="vertical",
                parent=parent,
            ),
        )
    return tuple(
        SettingsCard(
            title=entry,
            visual_widget=_settings_icon_widget(parent, icon),
            parent=parent,
        )
        for entry in entries
    )


def _settings_icon_widget(parent: QWidget, icon: AppIcon) -> IconWidget:
    """Create one fixed-size About Settings card icon."""

    widget = IconWidget(icon, parent)
    widget.setFixedSize(SETTINGS_CARD_ICON_MAX_SIZE, SETTINGS_CARD_ICON_MAX_SIZE)
    return widget


__all__ = ["AboutSettingsPage"]
