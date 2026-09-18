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

"""Present exact download totals and destination accessibility."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.presentation.fluent_tooltips import (
    set_fluent_tooltip_text,
)

from substitute.domain.model_recommendations import ModelInstallPlan
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
)

from substitute.presentation.onboarding.onboarding_download_text import (
    format_model_size,
)


class DownloadSummaryPanel(QFrame):
    """Summarize the editable cart without exposing a long absolute path."""

    def __init__(self, parent: QWidget) -> None:
        """Build model-count, transfer, storage, and destination values."""

        super().__init__(parent)
        self.setObjectName("OnboardingDownloadSummaryPanel")
        self.setFixedWidth(500)
        self.setFixedHeight(50)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 5, 12, 5)
        layout.setSpacing(18)
        self.count_label = self._value(layout, app_text("Models"))
        self.total_label = self._value(layout, app_text("Download"))
        self.available_label = self._value(layout, app_text("Free space"))

    def set_plan(self, plan: ModelInstallPlan) -> None:
        """Refresh the visible checkout totals for one exact plan."""

        self.count_label.setText(str(len(plan.files)))
        self.total_label.setText(format_model_size(plan.total_bytes))
        self.available_label.setText(format_model_size(plan.available_bytes))
        destination = str(plan.model_root)
        set_fluent_tooltip_text(self, destination)
        self.setAccessibleDescription(destination)

    def _value(
        self,
        layout: QHBoxLayout,
        label: ApplicationText,
    ) -> LocalizedBodyLabel:
        """Add one compact labeled value to the summary."""

        column = QVBoxLayout()
        column.setSpacing(2)
        caption = LocalizedCaptionLabel(label, self)
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(caption)
        value = LocalizedBodyLabel("", self)
        value.setObjectName("OnboardingDownloadSummaryValue")
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(value)
        layout.addLayout(column, 1)
        return value
