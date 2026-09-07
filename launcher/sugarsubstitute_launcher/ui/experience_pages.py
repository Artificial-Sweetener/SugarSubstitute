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

"""Render the standalone launcher's explicit recovery page."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CaptionLabel,
    FluentIcon as FIF,
    IconWidget,
    PrimaryPushButton,
    PushButton,
    RadioButton,
    StrongBodyLabel,
    SubtitleLabel,
)

from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from launcher.sugarsubstitute_launcher.ui.experience_models import RepairChoice


class RepairScopePage(QFrame):
    """Present explicit repair boundaries and preservation guarantees."""

    continue_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the explicit application and full-managed-Comfy choices."""

        super().__init__(parent)
        self.setObjectName("ExperiencePage")
        layout = _page_layout(self)
        _add_hero(
            layout,
            icon=FIF.SYNC,
            title=launcher_text("Put Substitute back in a fresh state"),
            description=launcher_text(
                "Restore installer-owned files. Your work and models stay in place."
            ),
        )
        self._group = QButtonGroup(self)
        application_panel, self.application_choice = _repair_option(
            self,
            title=launcher_text("Repair Substitute"),
            description=launcher_text(
                "Refresh Substitute, its launcher, and runtime. Managed installs also "
                "refresh Substitute's ComfyUI nodes."
            ),
            badge=launcher_text("Recommended"),
        )
        full_comfy_panel, self.full_comfy_choice = _repair_option(
            self,
            title=launcher_text("Repair Substitute and managed ComfyUI"),
            description=launcher_text(
                "Also rebuild installer-owned ComfyUI and its Python environment."
            ),
            badge=launcher_text("More thorough"),
        )
        self._group.addButton(self.application_choice, 0)
        self._group.addButton(self.full_comfy_choice, 1)
        self.application_choice.setChecked(True)
        layout.addWidget(application_panel)
        layout.addWidget(full_comfy_panel)
        preservation = QFrame(self)
        preservation.setObjectName("PreservationPanel")
        preservation_layout = QVBoxLayout(preservation)
        preservation_layout.setContentsMargins(16, 14, 16, 14)
        preservation_layout.setSpacing(5)
        preservation_layout.addWidget(
            StrongBodyLabel(launcher_text("Always preserved"), preservation)
        )
        preservation_layout.addWidget(
            CaptionLabel(
                launcher_text(
                    "Projects • outputs • autosaves • settings • models • inputs • "
                    "ComfyUI user data • third-party custom nodes"
                ),
                preservation,
            )
        )
        layout.addWidget(preservation)
        self.status_label = CaptionLabel("", self)
        self.status_label.setObjectName("RepairStatus")
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        layout.addWidget(self.status_label)
        layout.addStretch(1)
        footer = QHBoxLayout()
        footer.addStretch(1)
        cancel = PushButton(launcher_text("Cancel"), self)
        cancel.clicked.connect(self.cancel_requested)
        self.primary_button = PrimaryPushButton(launcher_text("Review repair"), self)
        self.primary_button.clicked.connect(self.continue_requested)
        footer.addWidget(cancel)
        footer.addWidget(self.primary_button)
        layout.addLayout(footer)

    @property
    def choice(self) -> RepairChoice:
        """Return the repair boundary explicitly selected by the user."""

        if self.full_comfy_choice.isChecked():
            return RepairChoice.FULL_MANAGED_COMFY
        return RepairChoice.APPLICATION

    def set_status(self, message: str, *, working: bool) -> None:
        """Project preparation progress without hiding preservation policy."""

        self.status_label.setText(message)
        self.status_label.setVisible(bool(message))
        self.application_choice.setEnabled(not working)
        self.full_comfy_choice.setEnabled(not working)
        self.primary_button.setText(
            launcher_text("Preparing repair...")
            if working
            else launcher_text("Review repair")
        )
        self.primary_button.setEnabled(not working)


def _page_layout(page: QFrame) -> QVBoxLayout:
    """Create consistent production-page geometry."""

    layout = QVBoxLayout(page)
    layout.setContentsMargins(30, 24, 30, 24)
    layout.setSpacing(14)
    return layout


def _add_hero(
    layout: QVBoxLayout,
    *,
    icon: FIF,
    title: str,
    description: str,
) -> None:
    """Add a shared icon, heading, and explanatory copy block."""

    row = QHBoxLayout()
    badge = QFrame()
    badge.setObjectName("OnboardingHeroBadge")
    badge_layout = QVBoxLayout(badge)
    badge_layout.setContentsMargins(10, 10, 10, 10)
    icon_widget = IconWidget(icon, badge)
    icon_widget.setFixedSize(22, 22)
    badge_layout.addWidget(icon_widget)
    row.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)
    text = QVBoxLayout()
    title_label = SubtitleLabel(title)
    title_label.setObjectName("ExperiencePageTitle")
    title_label.setWordWrap(True)
    text.addWidget(title_label)
    description_label = BodyLabel(description)
    description_label.setObjectName("ExperiencePageDescription")
    description_label.setWordWrap(True)
    text.addWidget(description_label)
    row.addLayout(text, 1)
    layout.addLayout(row)


def _repair_option(
    parent: QWidget,
    *,
    title: str,
    description: str,
    badge: str,
) -> tuple[QFrame, RadioButton]:
    """Create one accessible multiline repair option."""

    panel = QFrame(parent)
    panel.setObjectName("RepairScopeOption")
    row = QHBoxLayout(panel)
    row.setContentsMargins(14, 12, 14, 12)
    row.setSpacing(10)
    option = RadioButton(panel)
    option.setObjectName("RepairScopeChoice")
    option.setText("")
    row.addWidget(option, alignment=Qt.AlignmentFlag.AlignTop)
    copy = QVBoxLayout()
    copy.setSpacing(3)
    copy.addWidget(StrongBodyLabel(title, panel))
    description_label = CaptionLabel(description, panel)
    description_label.setWordWrap(True)
    copy.addWidget(description_label)
    badge_label = CaptionLabel(badge, panel)
    badge_label.setObjectName("RepairScopeBadge")
    copy.addWidget(badge_label)
    row.addLayout(copy, 1)
    return panel, option


__all__ = ["RepairScopePage"]
