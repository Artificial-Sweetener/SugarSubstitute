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

"""Render selected model downloads as an editable checkout."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.presentation.fluent_tooltips import (
    set_fluent_tooltip_text,
)

from substitute.application.model_recommendations import RecommendationCardAsset
from substitute.domain.model_recommendations import ModelInstallFile, ModelInstallPlan
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
    LocalizedPushButton,
)
from substitute.presentation.onboarding.onboarding_page_primitives import (
    OnboardingPageFrame,
)
from substitute.presentation.onboarding.onboarding_recommendation_portrait import (
    RecommendationPortrait,
)
from substitute.shared.qt_thumbnail_codec import image_from_qt_thumbnail_payload


class DownloadCartCard(QFrame):
    """Present one exact selected model as a removable checkout item."""

    remove_requested = Signal(int)

    def __init__(
        self,
        *,
        item: ModelInstallFile,
        card: RecommendationCardAsset,
        parent: QWidget,
    ) -> None:
        """Build a title-washed portrait with concise family and size metadata."""

        super().__init__(parent)
        self.setObjectName("OnboardingDownloadCartCard")
        self.setMinimumWidth(214)
        self.setMaximumWidth(258)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        pixmap = _card_pixmap(card)
        self.portrait = RecommendationPortrait(
            pixmap=pixmap,
            title=item.display_name,
            thumbnail_failed=card.thumbnail_failed,
            selected=False,
            accessible_name=item.display_name,
            portrait_size=QSize(190, 238),
            selectable=False,
            parent=self,
        )
        if card.thumbnail is not None and pixmap is None:
            self.portrait.set_thumbnail_unavailable()
        layout.addWidget(self.portrait, alignment=Qt.AlignmentFlag.AlignHCenter)

        details = QHBoxLayout()
        details.setContentsMargins(2, 0, 2, 0)
        details.setSpacing(8)
        family = LocalizedCaptionLabel(item.family_id.value.upper(), self)
        family.setObjectName("OnboardingDownloadCartFamily")
        details.addWidget(family)
        details.addStretch(1)
        size = LocalizedBodyLabel(format_model_size(item.size_bytes), self)
        size.setObjectName("OnboardingDownloadCartSize")
        details.addWidget(size)
        layout.addLayout(details)
        remove = LocalizedPushButton(app_text("Remove"), self)
        remove.setObjectName(f"OnboardingRemoveModel_{item.version_id}")
        remove.clicked.connect(lambda: self.remove_requested.emit(item.version_id))
        layout.addWidget(remove)


class DownloadSummaryPanel(QFrame):
    """Summarize the editable cart without exposing a long absolute path."""

    def __init__(self, parent: QWidget) -> None:
        """Build model-count, transfer, storage, and destination values."""

        super().__init__(parent)
        self.setObjectName("OnboardingDownloadSummaryPanel")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 11, 18, 11)
        layout.setSpacing(28)
        self.count_label = self._value(layout, app_text("Models"))
        self.total_label = self._value(layout, app_text("Download"))
        self.available_label = self._value(layout, app_text("Free space"))
        self.destination_label = LocalizedCaptionLabel("", self)
        self.destination_label.setObjectName("OnboardingDownloadDestination")
        self.destination_label.setWordWrap(True)
        self.destination_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self.destination_label, 2)

    def set_plan(self, plan: ModelInstallPlan) -> None:
        """Refresh the visible checkout totals for one exact plan."""

        self.count_label.setText(str(len(plan.files)))
        self.total_label.setText(format_model_size(plan.total_bytes))
        self.available_label.setText(format_model_size(plan.available_bytes))
        self.destination_label.setText(_compact_destination(plan.model_root))
        set_fluent_tooltip_text(self.destination_label, str(plan.model_root))

    def _value(
        self,
        layout: QHBoxLayout,
        label: ApplicationText,
    ) -> LocalizedBodyLabel:
        """Add one compact labeled value to the summary."""

        column = QVBoxLayout()
        column.setSpacing(2)
        column.addWidget(LocalizedCaptionLabel(label, self))
        value = LocalizedBodyLabel("", self)
        value.setObjectName("OnboardingDownloadSummaryValue")
        column.addWidget(value)
        layout.addLayout(column, 1)
        return value


class ModelDownloadReviewPage(OnboardingPageFrame):
    """Review exact selected primary models as an editable cart."""

    remove_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build an approachable checkout with model cards and totals."""

        super().__init__(
            title=app_text("Review model downloads"),
            description=app_text("Remove anything you no longer want, then download."),
            icon=FIF.CHECKBOX,
            parent=parent,
        )
        self.setObjectName("OnboardingModelDownloadReviewPage")
        self.cards_layout = QVBoxLayout()
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(14)
        self.body_layout.addLayout(self.cards_layout)
        self._cards: list[DownloadCartCard] = []
        self._card_rows: list[QWidget] = []
        self.empty_label = LocalizedBodyLabel(
            app_text("Your model cart is empty."), self
        )
        self.empty_label.setWordWrap(True)
        self.empty_label.hide()
        self.body_layout.addWidget(self.empty_label)
        self.summary_panel = DownloadSummaryPanel(self)
        self.body_layout.addWidget(self.summary_panel)
        self.space_warning_label = LocalizedCaptionLabel("", self)
        self.space_warning_label.setObjectName("OnboardingDownloadSpaceWarning")
        self.space_warning_label.setWordWrap(True)
        self.space_warning_label.hide()
        self.body_layout.addWidget(self.space_warning_label)

    def set_plan(
        self,
        plan: ModelInstallPlan,
        cards: tuple[RecommendationCardAsset, ...],
    ) -> None:
        """Render exact selected cards and the resulting download totals."""

        self._clear_cards()
        cards_by_version = {card.recommendation.version_id: card for card in cards}
        current_row: QHBoxLayout | None = None
        for index, item in enumerate(plan.files):
            card = cards_by_version.get(item.version_id)
            if card is None:
                continue
            if index % 3 == 0:
                row_host = QWidget(self)
                current_row = QHBoxLayout(row_host)
                current_row.setContentsMargins(0, 0, 0, 0)
                current_row.setSpacing(14)
                current_row.addStretch(1)
                self.cards_layout.addWidget(row_host)
                self._card_rows.append(row_host)
            if current_row is None:
                continue
            widget = DownloadCartCard(item=item, card=card, parent=self)
            widget.remove_requested.connect(self.remove_requested)
            current_row.addWidget(widget)
            self._cards.append(widget)
            if index % 3 == 2 or index == len(plan.files) - 1:
                current_row.addStretch(1)
        self.empty_label.setVisible(not plan.files)
        self.summary_panel.setVisible(bool(plan.files))
        self.summary_panel.set_plan(plan)
        self.space_warning_label.setVisible(not plan.has_sufficient_space)
        if not plan.has_sufficient_space:
            self.space_warning_label.setText(
                app_text("There is not enough free space for these models.")
            )

    def _clear_cards(self) -> None:
        """Remove prior checkout cards before rendering current selection state."""

        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._card_rows.clear()
        self._cards.clear()


def _card_pixmap(card: RecommendationCardAsset) -> QPixmap | None:
    """Decode a retained exact-version thumbnail for checkout rendering."""

    if card.thumbnail is None:
        return None
    image = image_from_qt_thumbnail_payload(
        width=card.thumbnail.width,
        height=card.thumbnail.height,
        qt_format=card.thumbnail.qt_format,
        bytes_per_line=card.thumbnail.bytes_per_line,
        payload=card.thumbnail.payload,
    )
    if image is None or image.isNull():
        return None
    return QPixmap.fromImage(image)


def _compact_destination(path: Path) -> str:
    """Return a short destination label while retaining the full path as a tooltip."""

    parent = path.parent.name
    return f"…\\{parent}\\{path.name}" if parent else path.name


def format_model_size(size_bytes: int) -> str:
    """Return a concise binary transfer size for review copy."""

    value = float(size_bytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size_bytes} B"


__all__ = ["ModelDownloadReviewPage"]
