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

"""Provide shared visual primitives for onboarding pages."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.presentation.localization import (
    apply_application_text,
)
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
    LocalizedRadioButton,
)

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    FluentIcon as FIF,
    IconWidget,
)

from substitute.presentation.onboarding.onboarding_models import OnboardingTargetMode


@dataclass(frozen=True)
class TargetModePresentation:
    """Describe the concise product-facing copy for one target mode."""

    title: ApplicationText
    summary: ApplicationText
    best_if: ApplicationText
    meaning: ApplicationText
    substitute_handles: ApplicationText
    you_handle: ApplicationText
    technical_note: ApplicationText
    icon: object


_TARGET_MODE_PRESENTATION: dict[OnboardingTargetMode, TargetModePresentation] = {
    OnboardingTargetMode.MANAGED_LOCAL: TargetModePresentation(
        title=app_text("Set up ComfyUI here"),
        summary=app_text(
            "Substitute installs and prepares a local ComfyUI setup for you."
        ),
        best_if=app_text("Best if you want the simplest path."),
        meaning=app_text(
            "Substitute creates a local ComfyUI setup in the folder you choose."
        ),
        substitute_handles=app_text(
            "Substitute installs ComfyUI, prepares what it needs, and keeps required "
            "node packs ready."
        ),
        you_handle=app_text(
            "You mainly choose where the files live. Most people can leave the "
            "local address alone."
        ),
        technical_note=app_text(
            "By default, the managed ComfyUI folder is created as `comfyui` inside "
            "your Substitute folder."
        ),
        icon=FIF.HOME,
    ),
    OnboardingTargetMode.ATTACHED_LOCAL: TargetModePresentation(
        title=app_text("Use my current ComfyUI"),
        summary=app_text(
            "Substitute adopts and starts the local ComfyUI setup you already use."
        ),
        best_if=app_text("Best if you already have local ComfyUI set up."),
        meaning=app_text(
            "Substitute uses your current local ComfyUI folder without reinstalling "
            "the repository."
        ),
        substitute_handles=app_text(
            "Substitute saves that folder, prepares the Python environment it needs, "
            "and starts ComfyUI for you."
        ),
        you_handle=app_text(
            "You keep your ComfyUI files and models. Substitute takes over launching "
            "it while the app is running."
        ),
        technical_note=app_text(
            "The ComfyUI folder is required so Substitute can launch it and inspect "
            "local custom-node files."
        ),
        icon=FIF.LINK,
    ),
    OnboardingTargetMode.REMOTE: TargetModePresentation(
        title=app_text("Use remote ComfyUI"),
        summary=app_text(
            "Substitute connects to a ComfyUI server running on another machine."
        ),
        best_if=app_text("Best if ComfyUI lives on another machine."),
        meaning=app_text(
            "Substitute sends work to a remote ComfyUI server instead of starting one "
            "here."
        ),
        substitute_handles=app_text(
            "Substitute saves the remote address and prepares the local pieces it "
            "still needs for the canvas."
        ),
        you_handle=app_text(
            "You keep the remote ComfyUI server running and reachable from this "
            "computer."
        ),
        technical_note=app_text(
            "Some canvas features still need a local Python environment even when "
            "ComfyUI itself is remote."
        ),
        icon=FIF.IOT,
    ),
}


class OnboardingHeroPanel(QFrame):
    """Render the slim page header shared by the onboarding pages."""

    def __init__(
        self,
        *,
        title: ApplicationText,
        description: ApplicationText,
        icon: object,
        eyebrow: ApplicationText,
        parent: QWidget | None = None,
    ) -> None:
        """Build the compact hero with icon badge, title, and supporting line."""

        super().__init__(parent)
        self.setObjectName("OnboardingHeroPanel")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        badge = QFrame(self)
        badge.setObjectName("OnboardingHeroBadge")
        badge_layout = QVBoxLayout(badge)
        badge_layout.setContentsMargins(10, 10, 10, 10)
        badge_layout.setSpacing(0)
        icon_widget = IconWidget(icon, badge)
        icon_widget.setFixedSize(22, 22)
        badge_layout.addWidget(icon_widget, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(5)

        eyebrow_label = LocalizedCaptionLabel(eyebrow, self)
        eyebrow_label.setObjectName("OnboardingHeroEyebrow")
        text_layout.addWidget(eyebrow_label)

        self.title_label = LocalizedBodyLabel(title, self)
        self.title_label.setObjectName("OnboardingPageTitle")
        self.title_label.setWordWrap(True)
        text_layout.addWidget(self.title_label)

        self.description_label = LocalizedCaptionLabel(description, self)
        self.description_label.setObjectName("OnboardingPageDescription")
        self.description_label.setWordWrap(True)
        text_layout.addWidget(self.description_label)

        layout.addLayout(text_layout, 1)


class OnboardingPageFrame(QFrame):
    """Render one onboarding page with a compact header and primary content body."""

    def __init__(
        self,
        *,
        title: ApplicationText,
        description: ApplicationText,
        icon: object,
        eyebrow: ApplicationText,
        parent: QWidget | None = None,
    ) -> None:
        """Build the shared page surface and expose a body layout for content."""

        super().__init__(parent)
        self.setObjectName("OnboardingPageFrame")

        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.addStretch(1)

        self.content_column = QWidget(self)
        self.content_column.setObjectName("OnboardingContentColumn")
        self.content_column.setMinimumWidth(820)
        self.content_column.setMaximumWidth(980)
        layout = QVBoxLayout(self.content_column)
        layout.setContentsMargins(4, 6, 4, 8)
        layout.setSpacing(18)

        self.hero_panel = OnboardingHeroPanel(
            title=title,
            description=description,
            icon=icon,
            eyebrow=eyebrow,
            parent=self,
        )
        layout.addWidget(self.hero_panel)

        self.body_layout = QVBoxLayout()
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(14)
        layout.addLayout(self.body_layout)
        layout.addStretch(1)
        outer_layout.addWidget(self.content_column, 8)
        outer_layout.addStretch(1)


class OnboardingInfoPanel(QFrame):
    """Render a restrained supporting panel for secondary onboarding detail."""

    def __init__(
        self,
        *,
        title: ApplicationText,
        description: ApplicationText,
        detail_lines: tuple[ApplicationText, ...] = (),
        parent: QWidget | None = None,
    ) -> None:
        """Build the supporting panel with one short description and optional bullets."""

        super().__init__(parent)
        self.setObjectName("OnboardingInfoPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        self.title_label = LocalizedBodyLabel(title, self)
        self.title_label.setObjectName("OnboardingInfoTitle")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.description_label = LocalizedCaptionLabel(description, self)
        self.description_label.setObjectName("OnboardingInfoDescription")
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        self.detail_labels: list[LocalizedCaptionLabel] = []
        for detail_line in detail_lines:
            detail_label = LocalizedCaptionLabel(detail_line, self)
            detail_label.setObjectName("OnboardingInfoDetail")
            detail_label.setWordWrap(True)
            layout.addWidget(detail_label)
            self.detail_labels.append(detail_label)


class OnboardingFieldBlock(QFrame):
    """Render one labeled field with a concise user-facing helper line."""

    def __init__(
        self,
        *,
        label: ApplicationText,
        helper_text: ApplicationText,
        field: QWidget,
        trailing_widget: QWidget | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build the field block around the supplied field widget."""

        super().__init__(parent)
        self.setObjectName("OnboardingFieldBlock")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        label_widget = LocalizedCaptionLabel(label, self)
        label_widget.setObjectName("OnboardingFieldLabel")
        layout.addWidget(label_widget)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addWidget(field, 1)
        if trailing_widget is not None:
            row.addWidget(trailing_widget)
        layout.addLayout(row)

        helper_label = LocalizedCaptionLabel(helper_text, self)
        helper_label.setObjectName("OnboardingFieldHelper")
        helper_label.setWordWrap(True)
        layout.addWidget(helper_label)


class OnboardingSectionPanel(QFrame):
    """Render one primary content section inside a page."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the generic section container used by onboarding pages."""

        super().__init__(parent)
        self.setObjectName("OnboardingSectionPanel")
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(18, 16, 18, 16)
        self.content_layout.setSpacing(12)


class TargetModeCard(QFrame):
    """Render one selectable setup card for the target-mode page."""

    clicked = Signal(str)

    def __init__(
        self,
        *,
        mode: OnboardingTargetMode,
        presentation: TargetModePresentation,
        parent: QWidget | None = None,
    ) -> None:
        """Build the card using concise compare-first copy."""

        super().__init__(parent)
        self._mode = mode
        self.setObjectName(f"OnboardingTargetCard_{mode.value}")
        self.setProperty("targetMode", mode.value)
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)

        badge = QFrame(self)
        badge.setObjectName("OnboardingTargetCardBadge")
        badge_layout = QVBoxLayout(badge)
        badge_layout.setContentsMargins(9, 9, 9, 9)
        badge_layout.setSpacing(0)
        icon_widget = IconWidget(presentation.icon, badge)
        icon_widget.setFixedSize(20, 20)
        badge_layout.addWidget(icon_widget, alignment=Qt.AlignmentFlag.AlignCenter)
        header_row.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(4)

        self.title_label = LocalizedBodyLabel(presentation.title, self)
        self.title_label.setObjectName("OnboardingTargetCardTitle")
        self.title_label.setWordWrap(True)
        text_column.addWidget(self.title_label)

        self.summary_label = LocalizedCaptionLabel(presentation.summary, self)
        self.summary_label.setObjectName("OnboardingTargetCardSummary")
        self.summary_label.setWordWrap(True)
        text_column.addWidget(self.summary_label)
        header_row.addLayout(text_column, 1)
        layout.addLayout(header_row)

        self.best_if_label = LocalizedCaptionLabel(presentation.best_if, self)
        self.best_if_label.setObjectName("OnboardingTargetCardBestIf")
        self.best_if_label.setWordWrap(True)
        layout.addWidget(self.best_if_label)

        layout.addStretch(1)

        self.selection_radio = LocalizedRadioButton(app_text("Select"), self)
        self.selection_radio.setObjectName(f"OnboardingTargetCardRadio_{mode.value}")
        self.selection_radio.setProperty("targetMode", mode.value)
        self.selection_radio.setAutoExclusive(False)
        self.selection_radio.clicked.connect(self._emit_clicked)
        layout.addWidget(self.selection_radio, alignment=Qt.AlignmentFlag.AlignLeft)

    def set_selected(self, selected: bool) -> None:
        """Apply the selected visual treatment to the card."""

        self.setProperty("selected", selected)
        self.selection_radio.setChecked(selected)
        self.selection_radio.setText(
            app_text("Selected") if selected else app_text("Select")
        )
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Emit the selected target mode when the card is pressed."""

        self._emit_clicked()
        super().mousePressEvent(event)

    def _emit_clicked(self) -> None:
        """Emit the configured target mode for card and button activation."""

        self.clicked.emit(self._mode.value)


class TargetModeSummaryPanel(QFrame):
    """Render the selected-mode summary beneath the target-mode cards."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the compact summary block for the current target choice."""

        super().__init__(parent)
        self.setObjectName("OnboardingModeSummaryPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        self.meaning_label = LocalizedCaptionLabel("", self)
        self.meaning_label.setObjectName("OnboardingModeSummaryText")
        self.meaning_label.setWordWrap(True)
        layout.addWidget(self.meaning_label)

        self.substitute_label = LocalizedCaptionLabel("", self)
        self.substitute_label.setObjectName("OnboardingModeSummaryText")
        self.substitute_label.setWordWrap(True)
        layout.addWidget(self.substitute_label)

        self.you_label = LocalizedCaptionLabel("", self)
        self.you_label.setObjectName("OnboardingModeSummaryText")
        self.you_label.setWordWrap(True)
        layout.addWidget(self.you_label)

        self.technical_label = LocalizedCaptionLabel("", self)
        self.technical_label.setObjectName("OnboardingModeTechnicalNote")
        self.technical_label.setWordWrap(True)
        layout.addWidget(self.technical_label)

    def set_presentation(self, presentation: TargetModePresentation) -> None:
        """Render the selected target-mode summary lines."""

        apply_application_text(self.meaning_label, presentation.meaning)
        apply_application_text(
            self.substitute_label,
            presentation.substitute_handles,
        )
        apply_application_text(self.you_label, presentation.you_handle)
        apply_application_text(self.technical_label, presentation.technical_note)
