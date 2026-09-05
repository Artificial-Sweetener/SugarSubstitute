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

"""Render an approachable review of model downloads during onboarding."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from sugarsubstitute_shared.localization import ApplicationText, app_text

from substitute.domain.model_recommendations import (
    ModelInstallFile,
    ModelInstallPlan,
    ModelRecipeRole,
)
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
)
from substitute.presentation.onboarding.onboarding_page_primitives import (
    OnboardingPageFrame,
)


class DownloadReviewItem(QFrame):
    """Present one exact file without exposing a distracting absolute path."""

    def __init__(
        self,
        item: ModelInstallFile,
        *,
        title: ApplicationText | str,
        parent: QWidget,
    ) -> None:
        """Build a compact file row with its identity and transfer size."""

        super().__init__(parent)
        self.setObjectName("OnboardingDownloadReviewItem")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(14)

        identity = QVBoxLayout()
        identity.setContentsMargins(0, 0, 0, 0)
        identity.setSpacing(3)
        self.title_label = LocalizedBodyLabel(title, self)
        self.title_label.setObjectName("OnboardingDownloadReviewItemTitle")
        self.title_label.setWordWrap(True)
        identity.addWidget(self.title_label)
        self.file_label = LocalizedCaptionLabel(item.file_name, self)
        self.file_label.setObjectName("OnboardingDownloadReviewFileName")
        self.file_label.setWordWrap(True)
        self.file_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        identity.addWidget(self.file_label)
        layout.addLayout(identity, 1)

        self.size_label = LocalizedBodyLabel(format_model_size(item.size_bytes), self)
        self.size_label.setObjectName("OnboardingDownloadReviewItemSize")
        self.size_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self.size_label)


class DownloadReviewGroup(QFrame):
    """Group model files that share one meaning for the user."""

    def __init__(
        self,
        *,
        title: ApplicationText,
        items: tuple[tuple[ModelInstallFile, ApplicationText | str], ...],
        parent: QWidget,
    ) -> None:
        """Build one labeled group of compact download rows."""

        super().__init__(parent)
        self.setObjectName("OnboardingDownloadReviewGroup")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(9)
        self.title_label = LocalizedCaptionLabel(title, self)
        self.title_label.setObjectName("OnboardingDownloadReviewGroupTitle")
        layout.addWidget(self.title_label)
        self.items = tuple(
            DownloadReviewItem(item, title=item_title, parent=self)
            for item, item_title in items
        )
        for item_widget in self.items:
            layout.addWidget(item_widget)
        layout.addStretch(1)


class DownloadSummaryPanel(QFrame):
    """Emphasize aggregate transfer size and available storage."""

    def __init__(self, parent: QWidget) -> None:
        """Build the two-value download summary."""

        super().__init__(parent)
        self.setObjectName("OnboardingDownloadSummaryPanel")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(28)

        download_layout, self.total_label = _summary_value(
            label=app_text("Download"), parent=self
        )
        layout.addLayout(download_layout, 1)
        available_layout, self.available_label = _summary_value(
            label=app_text("Free space"), parent=self
        )
        layout.addLayout(available_layout, 1)
        self.destination_label = LocalizedCaptionLabel(
            app_text("Files will be saved in your ComfyUI models folder."), self
        )
        self.destination_label.setObjectName("OnboardingDownloadDestination")
        self.destination_label.setWordWrap(True)
        layout.addWidget(self.destination_label, 2)

    def set_sizes(self, *, total_bytes: int, available_bytes: int) -> None:
        """Refresh aggregate byte values for the current plan."""

        self.total_label.setText(format_model_size(total_bytes))
        self.available_label.setText(format_model_size(available_bytes))


class ModelDownloadReviewPage(OnboardingPageFrame):
    """Review selected models and their required companion files."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build a grouped download review with a compact storage summary."""

        super().__init__(
            title=app_text("Review model downloads"),
            description=app_text(
                "These files will be downloaded only after you confirm setup."
            ),
            icon=FIF.CHECKBOX,
            eyebrow=app_text("Download review"),
            parent=parent,
        )
        self.setObjectName("OnboardingModelDownloadReviewPage")
        self.group_row = QHBoxLayout()
        self.group_row.setContentsMargins(0, 0, 0, 0)
        self.group_row.setSpacing(14)
        self.body_layout.addLayout(self.group_row)
        self.model_group: DownloadReviewGroup | None = None
        self.required_group: DownloadReviewGroup | None = None
        self.empty_label = LocalizedBodyLabel(
            app_text(
                "No model files selected. Setup will continue without a download."
            ),
            self,
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

    def set_plan(self, plan: ModelInstallPlan) -> None:
        """Render the complete plan as models, companion files, and totals."""

        self._clear_groups()
        primary_files = tuple(
            (item, item.display_name)
            for item in plan.files
            if item.role is ModelRecipeRole.PRIMARY_MODEL
        )
        required_files = tuple(
            (item, _required_file_title(item.role))
            for item in plan.files
            if item.role is not ModelRecipeRole.PRIMARY_MODEL
        )
        self.empty_label.setVisible(not plan.files)
        self.summary_panel.setVisible(bool(plan.files))
        if primary_files:
            self.model_group = DownloadReviewGroup(
                title=app_text("Selected models"),
                items=primary_files,
                parent=self,
            )
            self.group_row.addWidget(self.model_group, 1)
        if required_files:
            self.required_group = DownloadReviewGroup(
                title=app_text("Required components"),
                items=required_files,
                parent=self,
            )
            self.group_row.addWidget(self.required_group, 1)
        self.summary_panel.set_sizes(
            total_bytes=plan.total_bytes,
            available_bytes=plan.available_bytes,
        )
        self.space_warning_label.setVisible(not plan.has_sufficient_space)
        if not plan.has_sufficient_space:
            self.space_warning_label.setText(
                app_text(
                    "This models folder does not have enough free space for the selected downloads."
                )
            )

    def _clear_groups(self) -> None:
        """Remove the prior plan before displaying a new review."""

        for group in (self.model_group, self.required_group):
            if group is not None:
                self.group_row.removeWidget(group)
                group.deleteLater()
        self.model_group = None
        self.required_group = None
        self.space_warning_label.hide()


def _summary_value(
    *, label: ApplicationText, parent: QWidget
) -> tuple[QVBoxLayout, LocalizedBodyLabel]:
    """Build one labeled value column for the aggregate summary."""

    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    label_widget = LocalizedCaptionLabel(label, parent)
    label_widget.setObjectName("OnboardingDownloadSummaryLabel")
    layout.addWidget(label_widget)
    value_widget = LocalizedBodyLabel("", parent)
    value_widget.setObjectName("OnboardingDownloadSummaryValue")
    layout.addWidget(value_widget)
    return layout, value_widget


def _required_file_title(role: ModelRecipeRole) -> ApplicationText:
    """Return the concise user-facing purpose of one required file."""

    if role is ModelRecipeRole.TEXT_ENCODER:
        return app_text("Text encoder")
    return app_text("Image decoder")


def format_model_size(size_bytes: int) -> str:
    """Return a concise binary transfer size for review copy."""

    value = float(size_bytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size_bytes} B"


__all__ = ["ModelDownloadReviewPage"]
