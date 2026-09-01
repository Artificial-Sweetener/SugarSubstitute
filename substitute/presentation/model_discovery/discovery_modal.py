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

"""Present reusable provider-ranked cards for an empty model picker."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    CaptionLabel,
    CheckBox,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    SubtitleLabel,
)

from substitute.presentation.widgets.civitai_page_action import (
    UrlOpener,
    open_external_url,
)
from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.model_discovery import (
    ModelDiscoveryCard,
    ModelDiscoveryPlan,
    model_card_identity,
)
from sugarsubstitute_shared.presentation.localization import render_application_text


class ModelDiscoveryModal(QDialog):
    """Review safe model cards with no automatic selection or download."""

    def __init__(
        self,
        *,
        plan: ModelDiscoveryPlan,
        open_url: UrlOpener | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build a model-picker recovery dialog from a shared plan."""

        super().__init__(parent)
        self._plan = plan
        self._open_url = open_url or open_external_url
        self._checks: dict[str, CheckBox] = {}
        self.setObjectName("EmptyModelPickerDiscoveryModal")
        self.setWindowTitle(_text(app_text("Find models")))
        self.setModal(True)
        self.resize(900, 650)
        self._build()

    @property
    def selected_identities(self) -> tuple[str, ...]:
        """Return checked provider-version identities in card order."""

        return tuple(
            identity
            for identity, checkbox in self._checks.items()
            if checkbox.isChecked()
        )

    def choose_models(self) -> tuple[str, ...]:
        """Run the modal and return only explicit selections."""

        if self.exec() != QDialog.DialogCode.Accepted:
            return ()
        return self.selected_identities

    def _build(self) -> None:
        """Compose empty-picker explanation, cards, and optional actions."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)
        title = SubtitleLabel(
            _text(app_text("No models are available for this picker")), self
        )
        layout.addWidget(title)
        description = CaptionLabel(
            _text(
                app_text(
                    "Choose from popular compatible files from the last month, or explore CivitAI. Nothing is selected automatically."
                )
            ),
            self,
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget(scroll)
        cards = QGridLayout(content)
        cards.setContentsMargins(0, 4, 0, 4)
        cards.setSpacing(12)
        for index, card in enumerate(self._plan.cards):
            cards.addWidget(self._build_card(card, content), index // 3, index % 3)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        footer = QHBoxLayout()
        explore = PushButton(_text(app_text("Explore more on CivitAI")), self)
        explore.clicked.connect(lambda: self._open_url(self._plan.explore_url))
        footer.addWidget(explore)
        footer.addStretch(1)
        cancel = PushButton(_text(app_text("Not now")), self)
        cancel.clicked.connect(self.reject)
        self.download_button = PrimaryPushButton(
            _text(app_text("Download selected")), self
        )
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.accept)
        footer.addWidget(cancel)
        footer.addWidget(self.download_button)
        layout.addLayout(footer)

    def _build_card(self, card: ModelDiscoveryCard, parent: QWidget) -> QFrame:
        """Build one unchecked provider card with file and destination details."""

        model = card.model
        identity = model_card_identity(card)
        frame = QFrame(parent)
        frame.setObjectName("ModelDiscoveryCard")
        card_layout = QVBoxLayout(frame)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(7)
        title = StrongBodyLabel(model.model_name, frame)
        title.setWordWrap(True)
        card_layout.addWidget(title)
        version = CaptionLabel(model.version_name, frame)
        version.setWordWrap(True)
        card_layout.addWidget(version)
        details = CaptionLabel(
            _text(
                app_text(
                    "%1 · %2",
                    model.base_model or _text(app_text("Base model not listed")),
                    _format_size(model.size_bytes),
                )
            ),
            frame,
        )
        details.setWordWrap(True)
        card_layout.addWidget(details)
        destination = QLabel(
            _text(app_text("Saves to %1", str(card.destination))), frame
        )
        destination.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        destination.setWordWrap(True)
        card_layout.addWidget(destination)
        card_layout.addStretch(1)
        checkbox = CheckBox(_text(app_text("Download this model")), frame)
        checkbox.setChecked(False)
        checkbox.stateChanged.connect(self._sync_download_action)
        self._checks[identity] = checkbox
        card_layout.addWidget(checkbox)
        return frame

    def _sync_download_action(self) -> None:
        """Enable transfer confirmation only after explicit selection."""

        self.download_button.setEnabled(bool(self.selected_identities))


def _text(message: ApplicationText) -> str:
    """Render one application-owned localized message."""

    return render_application_text(message)


def _format_size(size_bytes: int) -> str:
    """Return a compact binary file size."""

    if size_bytes >= 1024**3:
        return f"{size_bytes / 1024**3:.1f} GiB"
    if size_bytes >= 1024**2:
        return f"{size_bytes / 1024**2:.1f} MiB"
    return f"{size_bytes / 1024:.1f} KiB"


__all__ = ["ModelDiscoveryModal"]
