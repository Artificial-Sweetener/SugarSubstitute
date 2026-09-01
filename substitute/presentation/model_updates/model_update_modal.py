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

"""Present opt-in compatible model updates without preselecting downloads."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
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
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
)

from substitute.presentation.widgets.civitai_page_action import (
    UrlOpener,
    open_external_url,
)
from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.model_updates import (
    ModelUpdateProposal,
    model_update_identity,
)
from sugarsubstitute_shared.presentation.localization import render_application_text


class ModelUpdateModal(QDialog):
    """Review compatible updates and return only explicitly checked identities."""

    def __init__(
        self,
        *,
        proposals: Sequence[ModelUpdateProposal],
        model_root: Path,
        open_url: UrlOpener | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build a scrollable side-by-side update review."""

        super().__init__(parent)
        self._proposals = tuple(proposals)
        self._model_root = model_root
        self._open_url = open_url or open_external_url
        self._checks: dict[str, CheckBox] = {}
        self.setObjectName("ModelUpdateModal")
        self.setWindowTitle(_text(app_text("Model updates")))
        self.setModal(True)
        self.resize(720, 620)
        self._build()

    @property
    def selected_identities(self) -> tuple[str, ...]:
        """Return checked exact provider-version identities in display order."""

        return tuple(
            identity
            for identity, checkbox in self._checks.items()
            if checkbox.isChecked()
        )

    def choose_updates(self) -> tuple[str, ...]:
        """Run the modal and return selected identities after confirmation."""

        if self.exec() != QDialog.DialogCode.Accepted:
            return ()
        return self.selected_identities

    def _build(self) -> None:
        """Compose explanatory copy, unchecked cards, and explicit actions."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)
        title = SubtitleLabel(
            _text(app_text("Updates are available for models you use")), self
        )
        layout.addWidget(title)
        description = CaptionLabel(
            _text(
                app_text(
                    "Updates are optional. Downloaded versions are added beside your current files, and existing workflows keep using their current model."
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
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 4, 0, 4)
        content_layout.setSpacing(10)
        for proposal in self._proposals:
            content_layout.addWidget(self._build_card(proposal, content))
        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        later = PushButton(_text(app_text("Later")), self)
        later.clicked.connect(self.reject)
        self.download_button = PrimaryPushButton(
            _text(app_text("Download selected")), self
        )
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.accept)
        footer.addWidget(later)
        footer.addWidget(self.download_button)
        layout.addLayout(footer)

    def _build_card(
        self,
        proposal: ModelUpdateProposal,
        parent: QWidget,
    ) -> QFrame:
        """Build one unchecked update row with current and destination details."""

        candidate = proposal.candidate
        identity = model_update_identity(proposal)
        card = QFrame(parent)
        card.setObjectName("ModelUpdateCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(6)
        top = QHBoxLayout()
        checkbox = CheckBox(
            candidate.model_name or candidate.file_name,
            card,
        )
        checkbox.setChecked(False)
        checkbox.stateChanged.connect(self._sync_download_action)
        self._checks[identity] = checkbox
        top.addWidget(checkbox, 1)
        explore = PushButton(_text(app_text("View on CivitAI")), card)
        explore.clicked.connect(
            lambda _checked=False, url=candidate.model_page_url: self._open_url(url)
        )
        top.addWidget(explore)
        card_layout.addLayout(top)
        details = BodyLabel(
            _text(
                app_text(
                    "%1 → %2 · %3 · %4",
                    str(
                        proposal.current.version_id
                        or _text(app_text("Unknown version"))
                    ),
                    candidate.version_name,
                    candidate.base_model or _text(app_text("Unknown base model")),
                    _format_size(candidate.size_bytes),
                )
            ),
            card,
        )
        details.setWordWrap(True)
        card_layout.addWidget(details)
        destination = self._model_root / candidate.category.value
        destination_label = QLabel(
            _text(app_text("New file destination: %1", str(destination))),
            card,
        )
        destination_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        destination_label.setWordWrap(True)
        card_layout.addWidget(destination_label)
        return card

    def _sync_download_action(self) -> None:
        """Enable confirmation only after one explicit checkbox selection."""

        self.download_button.setEnabled(bool(self.selected_identities))


def _text(message: ApplicationText) -> str:
    """Render one application-owned localized message."""

    return render_application_text(message)


def _format_size(size_bytes: int) -> str:
    """Return a compact binary file-size label."""

    if size_bytes >= 1024**3:
        return f"{size_bytes / 1024**3:.1f} GiB"
    if size_bytes >= 1024**2:
        return f"{size_bytes / 1024**2:.1f} MiB"
    return f"{size_bytes / 1024:.1f} KiB"


__all__ = ["ModelUpdateModal"]
