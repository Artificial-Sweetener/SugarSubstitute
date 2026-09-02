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

"""Render reusable production pages for recovery and model onboarding."""

from __future__ import annotations

from collections.abc import Collection
from typing import cast

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CaptionLabel,
    CheckBox,
    FluentIcon as FIF,
    IconWidget,
    PrimaryPushButton,
    PushButton,
    RadioButton,
    StrongBodyLabel,
    SubtitleLabel,
)

from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from launcher.sugarsubstitute_launcher.ui.experience_models import (
    ModelCardPresentation,
    RepairChoice,
)
from sugarsubstitute_shared.model_discovery.models import ModelCategory


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
            eyebrow=launcher_text("Recovery suite"),
            title=launcher_text("Put Substitute back in a fresh state"),
            description=launcher_text(
                "Repair installs the exact version carried by this installer. "
                "Your projects, outputs, models, inputs, and ComfyUI user data stay in place."
            ),
        )
        self._group = QButtonGroup(self)
        application_panel, self.application_choice = _repair_option(
            self,
            title=launcher_text("Repair Substitute"),
            description=launcher_text(
                "Replace the app, launcher, Python runtime, and app state. "
                "When this installation owns managed ComfyUI, its Substitute Backend "
                "and SugarCubes nodes are refreshed too."
            ),
            badge=launcher_text("Recommended"),
        )
        full_comfy_panel, self.full_comfy_choice = _repair_option(
            self,
            title=launcher_text("Repair Substitute and managed ComfyUI"),
            description=launcher_text(
                "Also rebuild installer-owned ComfyUI core and its Python environment. "
                "Models, user data, inputs, outputs, and third-party custom nodes are preserved."
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


class ModelInterestPage(QFrame):
    """Collect model categories before provider discovery begins."""

    continue_requested = Signal()
    skip_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build an unchecked interest checklist for cube-supported categories."""

        super().__init__(parent)
        self.setObjectName("ExperiencePage")
        layout = _page_layout(self)
        _add_hero(
            layout,
            icon=FIF.ALBUM,
            eyebrow=launcher_text("Optional model setup"),
            title=launcher_text("Which models are you interested in using?"),
            description=launcher_text(
                "Substitute found cubes that can use these model types, but no compatible "
                "models are installed. Choose interests to see three popular picks from "
                "the last month. Nothing is selected or downloaded automatically."
            ),
        )
        self._checks: dict[ModelCategory, CheckBox] = {}
        self._options = QFrame(self)
        self._options.setObjectName("ExperienceOptionGrid")
        self._options_layout = QGridLayout(self._options)
        self._options_layout.setContentsMargins(0, 0, 0, 0)
        self._options_layout.setHorizontalSpacing(12)
        self._options_layout.setVerticalSpacing(12)
        layout.addWidget(self._options)
        self.status_label = CaptionLabel("", self)
        self.status_label.setObjectName("ModelOnboardingStatus")
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        layout.addWidget(self.status_label)
        layout.addStretch(1)
        footer = QHBoxLayout()
        footer.addStretch(1)
        self.skip_button = PushButton(launcher_text("Skip model setup"), self)
        self.skip_button.clicked.connect(self.skip_requested)
        self.primary_button = PrimaryPushButton(
            launcher_text("Find popular models"), self
        )
        self.primary_button.clicked.connect(self.continue_requested)
        footer.addWidget(self.skip_button)
        footer.addWidget(self.primary_button)
        layout.addLayout(footer)

    def set_categories(self, categories: Collection[ModelCategory]) -> None:
        """Replace the checklist with supported categories, all unchecked."""

        while self._options_layout.count():
            item = self._options_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._checks.clear()
        for index, category in enumerate(categories):
            check = CheckBox(_category_title(category), self._options)
            check.setObjectName("ModelCategoryChoice")
            check.setChecked(False)
            self._checks[category] = check
            self._options_layout.addWidget(check, index // 2, index % 2)

    @property
    def selected_categories(self) -> tuple[ModelCategory, ...]:
        """Return checked categories in canonical enumeration order."""

        return tuple(
            category
            for category in ModelCategory
            if category in self._checks and self._checks[category].isChecked()
        )

    def set_status(self, message: str, *, working: bool) -> None:
        """Show discovery progress and prevent overlapping requests."""

        self.status_label.setText(message)
        self.status_label.setVisible(bool(message))
        self.primary_button.setText(
            launcher_text("Finding models...")
            if working
            else launcher_text("Find popular models")
        )
        self.primary_button.setEnabled(not working)
        for check in self._checks.values():
            check.setEnabled(not working)


class ModelGalleryPage(QFrame):
    """Render safe provider-ranked model cards with explicit destinations."""

    continue_requested = Signal()
    back_requested = Signal()
    explore_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the scrollable gallery and its non-destructive actions."""

        super().__init__(parent)
        self.setObjectName("ExperiencePage")
        layout = _page_layout(self)
        _add_hero(
            layout,
            icon=FIF.MARKET,
            eyebrow=launcher_text("Popular this month"),
            title=launcher_text("Choose models to download"),
            description=launcher_text(
                "These files passed the provider's safety metadata checks. Review file "
                "size and destination, then select only what you want."
            ),
        )
        scroll = QScrollArea(self)
        scroll.setObjectName("ModelGalleryScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._gallery = QWidget(scroll)
        self._gallery.setObjectName("ModelGallery")
        self._gallery_layout = QGridLayout(self._gallery)
        self._gallery_layout.setContentsMargins(0, 0, 0, 0)
        self._gallery_layout.setSpacing(12)
        scroll.setWidget(self._gallery)
        layout.addWidget(scroll, 1)
        self._cards: dict[str, ModelCardWidget] = {}
        self.status_label = CaptionLabel("", self)
        self.status_label.setObjectName("ModelOnboardingStatus")
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        layout.addWidget(self.status_label)
        footer = QHBoxLayout()
        back = PushButton(launcher_text("Back"), self)
        back.clicked.connect(self.back_requested)
        explore = PushButton(launcher_text("Explore more on CivitAI"), self)
        explore.clicked.connect(self.explore_requested)
        footer.addWidget(back)
        footer.addWidget(explore)
        footer.addStretch(1)
        self.primary_button = PrimaryPushButton(
            launcher_text("Download selected"), self
        )
        self.primary_button.clicked.connect(self.continue_requested)
        footer.addWidget(self.primary_button)
        layout.addLayout(footer)

    def set_cards(self, cards: Collection[ModelCardPresentation]) -> None:
        """Replace the visible model card collection without preselecting files."""

        while self._gallery_layout.count():
            item = self._gallery_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cards.clear()
        for index, card in enumerate(cards):
            widget = ModelCardWidget(card, self._gallery)
            self._cards[card.identity] = widget
            self._gallery_layout.addWidget(widget, index // 3, index % 3)

    @property
    def visible_model_ids(self) -> tuple[str, ...]:
        """Return model identities in provider display order."""

        return tuple(self._cards)

    @property
    def selected_model_ids(self) -> tuple[str, ...]:
        """Return only explicitly selected model identities."""

        return tuple(
            identity for identity, card in self._cards.items() if card.selected
        )

    def set_model_selected(self, identity: str, *, selected: bool) -> None:
        """Drive one visible card through its public smoke and controller boundary."""

        try:
            card = self._cards[identity]
        except KeyError as error:
            raise ValueError(f"Unknown visible model card: {identity}") from error
        card.check.setChecked(selected)

    def set_status(
        self,
        message: str,
        *,
        working: bool,
        completed: bool = False,
    ) -> None:
        """Show acquisition progress or completion without replacing the cards."""

        self.status_label.setText(message)
        self.status_label.setVisible(bool(message))
        if working:
            button_text = launcher_text("Downloading models...")
        elif completed:
            button_text = launcher_text("Continue setup")
        else:
            button_text = launcher_text("Download selected")
        self.primary_button.setText(button_text)
        self.primary_button.setEnabled(not working)
        for card in self._cards.values():
            card.check.setEnabled(not working and not completed)


class ModelCardWidget(QFrame):
    """Present one model file without trusting provider text as rich content."""

    def __init__(self, card: ModelCardPresentation, parent: QWidget) -> None:
        """Build a compact card from already-sanitized discovery metadata."""

        super().__init__(parent)
        self.setObjectName("ModelDiscoveryCard")
        self._card = card
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(7)
        thumbnail = QLabel(_category_short_title(card.category), self)
        thumbnail.setObjectName("ModelCardThumbnail")
        thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumbnail.setFixedHeight(74)
        layout.addWidget(thumbnail)
        title = StrongBodyLabel(card.model_name, self)
        title.setObjectName("ModelCardTitle")
        title.setWordWrap(True)
        layout.addWidget(title)
        version = CaptionLabel(card.version_name, self)
        version.setWordWrap(True)
        layout.addWidget(version)
        details = CaptionLabel(
            launcher_text(
                "%1 • %2",
                card.base_model or launcher_text("Base model not listed"),
                _format_size(card.size_bytes),
            ),
            self,
        )
        details.setWordWrap(True)
        layout.addWidget(details)
        creator = CaptionLabel(
            launcher_text("by %1", card.creator or launcher_text("Unknown creator")),
            self,
        )
        creator.setWordWrap(True)
        layout.addWidget(creator)
        destination = CaptionLabel(
            launcher_text("Saves to %1", _breakable_path(card.destination)),
            self,
        )
        destination.setObjectName("ModelCardDestination")
        destination.setWordWrap(True)
        layout.addWidget(destination)
        layout.addStretch(1)
        self.check = CheckBox(launcher_text("Download this model"), self)
        self.check.setChecked(card.selected)
        layout.addWidget(self.check)

    @property
    def selected(self) -> bool:
        """Return whether the user explicitly checked this file."""

        return cast(bool, self.check.isChecked())


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
    eyebrow: str,
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
    eyebrow_label = CaptionLabel(eyebrow)
    eyebrow_label.setObjectName("OnboardingHeroEyebrow")
    text.addWidget(eyebrow_label)
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
    title_label = StrongBodyLabel(title, panel)
    copy.addWidget(title_label)
    description_label = CaptionLabel(description, panel)
    description_label.setWordWrap(True)
    copy.addWidget(description_label)
    badge_label = CaptionLabel(badge, panel)
    badge_label.setObjectName("RepairScopeBadge")
    copy.addWidget(badge_label)
    row.addLayout(copy, 1)
    return panel, option


def _breakable_path(path: object) -> str:
    """Insert invisible wrap opportunities into long destination paths."""

    return str(path).replace("\\", "\\\u200b").replace("/", "/\u200b")


def _category_title(category: ModelCategory) -> str:
    """Return localized category copy used by the interest checklist."""

    titles = {
        ModelCategory.CHECKPOINTS: launcher_text("Checkpoint models"),
        ModelCategory.DIFFUSION_MODELS: launcher_text("Diffusion models"),
        ModelCategory.LORAS: launcher_text("LoRA styles and characters"),
        ModelCategory.VAE: launcher_text("VAE color and decoding models"),
        ModelCategory.CONTROLNET: launcher_text("ControlNet guidance models"),
        ModelCategory.UPSCALE_MODELS: launcher_text("Upscaling models"),
    }
    return titles[category]


def _category_short_title(category: ModelCategory) -> str:
    """Return a compact localized placeholder for provider imagery."""

    return _category_title(category).split(" ", maxsplit=1)[0]


def _format_size(size_bytes: int) -> str:
    """Format one positive file size for model-card review."""

    gibibytes = size_bytes / (1024**3)
    if gibibytes >= 1:
        return launcher_text("%1 GB", f"{gibibytes:.1f}")
    mebibytes = size_bytes / (1024**2)
    return launcher_text("%1 MB", f"{mebibytes:.0f}")


__all__ = ["ModelGalleryPage", "ModelInterestPage", "RepairScopePage"]
