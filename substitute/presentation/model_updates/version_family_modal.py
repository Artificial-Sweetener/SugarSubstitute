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

"""Show one installed model's compatible CivitAI chronology in the app shell."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QLocale, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    FluentIcon as FIF,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
)
from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]

from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
    LocalizedSubtitleLabel,
)
from substitute.presentation.onboarding.onboarding_recommendation_portrait import (
    RecommendationPortrait,
)
from substitute.presentation.widgets.busy_ring import BusyRing
from substitute.presentation.widgets.civitai_page_action import UrlOpener
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.model_discovery import DiscoveredModel, ModelArtifactKind
from sugarsubstitute_shared.model_updates import ModelUpdateProposal
from sugarsubstitute_shared.presentation.localization import render_application_text
from sugarsubstitute_shared.presentation.widgets.scrolling import (
    configure_qfluent_scroll_surface,
)

_CARD_WIDTH = 204
_CARD_HEIGHT = 256
_PORTRAIT_SIZE = QSize(184, 200)


class ModelVersionCard(QFrame):
    """Show one chronological version using the existing model portrait control."""

    selected = Signal(int)

    def __init__(
        self,
        version: DiscoveredModel,
        *,
        installed: bool,
        downloaded: bool,
        parent: QWidget,
    ) -> None:
        """Bind an exact provider version and optionally mark the installed one."""

        super().__init__(parent)
        self.version = version
        self.installed = installed
        self.downloaded = downloaded
        self.setObjectName("ModelVersionCard")
        self.setProperty("selected", False)
        self.setProperty("installed", installed)
        self.setFixedSize(_CARD_WIDTH, _CARD_HEIGHT)
        surface = "rgba(255, 255, 255, 7)" if isDarkTheme() else "#f7f7f9"
        border = "rgba(255, 255, 255, 28)" if isDarkTheme() else "#d8d8de"
        self.setStyleSheet(
            f"QFrame#ModelVersionCard {{ background-color: {surface}; "
            f"border: 1px solid {border}; border-radius: 13px; }}"
            "QFrame#ModelVersionCard[installed='true'] {"
            "border: 1px solid #48c8d2; }"
            "QFrame#ModelVersionCard[selected='true'] {"
            "border: 2px solid #ec2d87; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 8)
        layout.setSpacing(6)
        portrait_label = render_application_text(
            app_text("%1, version %2", version.model_name, version.version_name)
        )
        self.portrait = RecommendationPortrait(
            image=None,
            title=version.version_name,
            metadata="",
            thumbnail_failed=version.thumbnail_url is None,
            selected=False,
            selectable=not (installed or downloaded),
            accessible_name=portrait_label,
            portrait_size=_PORTRAIT_SIZE,
            parent=self,
        )
        self.portrait.selection_changed.connect(self._publish_selection)
        layout.addWidget(self.portrait)
        self.state_label = LocalizedCaptionLabel(
            app_text("In use")
            if installed
            else (
                app_text("On disk")
                if downloaded
                else QLocale.system().formattedDataSize(version.size_bytes)
            ),
            self,
        )
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.state_label)

    def set_selected(self, selected: bool) -> None:
        """Project exclusive timeline choice onto the Fluent checkbox."""

        selected = selected and not (self.installed or self.downloaded)
        self.portrait.set_selected(selected)
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_image(self, image: QImage) -> None:
        """Show a safely fetched provider preview for this exact version."""

        self.portrait.set_image(image)

    def set_thumbnail_unavailable(self) -> None:
        """Settle a preview request that had no allowed or decodable image."""

        self.portrait.set_thumbnail_unavailable()

    def mark_downloaded(self) -> None:
        """Show that the selected version was verified beside the current file."""

        self.downloaded = True
        self.state_label.setText(render_application_text(app_text("On disk")))
        self.set_selected(False)
        self.portrait.set_selectable(False)

    def _publish_selection(self, selected: bool) -> None:
        """Notify the timeline only for a newly selected non-current version."""

        if selected and not (self.installed or self.downloaded):
            self.selected.emit(self.version.version_id)


class ModelVersionFamilyModal(QDialog):
    """Let the user inspect and download one same-type, same-base chronology."""

    downloadRequested = Signal(object)

    def __init__(
        self,
        *,
        proposal: ModelUpdateProposal,
        open_url: UrlOpener,
        parent: QWidget,
    ) -> None:
        """Build a familiar gallery before asynchronously loading its versions."""

        super().__init__(parent)
        self._proposal = proposal
        self._open_url = open_url
        self._versions: tuple[DiscoveredModel, ...] = ()
        self._cards: dict[int, ModelVersionCard] = {}
        self._selected_version_id: int | None = None
        self.setObjectName("ModelVersionFamilyModal")
        self.setModal(True)
        self.setProperty("preferredPanelHeight", 435)
        self.resize(1040, 435)
        self._build()

    @property
    def selected_version(self) -> DiscoveredModel | None:
        """Return the explicitly checked non-current version, if any."""

        return next(
            (
                version
                for version in self._versions
                if version.version_id == self._selected_version_id
            ),
            None,
        )

    def show_loading(self) -> None:
        """Open immediately while safe compatible versions are looked up."""

        self.status_label.setText(
            render_application_text(app_text("Loading model versions…"))
        )
        self.status_label.show()
        self.status_host.show()
        self.busy_ring.start()
        self.busy_ring.show()
        self.download_button.setEnabled(False)
        self.open()

    def show_family(
        self,
        versions: Sequence[DiscoveredModel],
        *,
        installed_hashes: frozenset[str] = frozenset(),
    ) -> None:
        """Lay out one verified chronological family in a horizontal strip."""

        self._versions = tuple(versions)
        self._selected_version_id = None
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self._cards.clear()
        for version in self._versions:
            installed = version.version_id == self._proposal.current.version_id
            card = ModelVersionCard(
                version,
                installed=installed,
                downloaded=version.sha256.casefold() in installed_hashes,
                parent=self.card_host,
            )
            card.selected.connect(self._select_version)
            self.card_layout.addWidget(card)
            self._cards[version.version_id] = card
        card_count = len(self._versions)
        self.card_host.setFixedSize(
            max(1, card_count * _CARD_WIDTH + max(0, card_count - 1) * 12),
            _CARD_HEIGHT + 4,
        )
        installed_id = self._proposal.current.version_id
        installed_card = (
            self._cards.get(installed_id) if installed_id is not None else None
        )
        if installed_card is not None:
            QTimer.singleShot(0, self, self._scroll_to_installed)
        self.busy_ring.stop()
        self.busy_ring.hide()
        if self._versions:
            self.status_label.hide()
            self.status_host.hide()
        else:
            self.show_failure(
                render_application_text(
                    app_text("No compatible versions are available.")
                )
            )
        self.download_button.setEnabled(False)

    def set_thumbnail(self, version_id: int, image: QImage) -> bool:
        """Fill one card's provider preview after bounded thumbnail retrieval."""

        card = self._cards.get(version_id)
        if card is None:
            return False
        card.set_image(image)
        return True

    def set_thumbnail_unavailable(self, version_id: int) -> bool:
        """Replace one unresolved preview with the catalog fallback."""

        card = self._cards.get(version_id)
        if card is None:
            return False
        card.set_thumbnail_unavailable()
        return True

    def show_failure(self, message: str) -> None:
        """Keep a lookup or transfer failure visible and recoverable."""

        self.busy_ring.stop()
        self.busy_ring.hide()
        self.status_label.setText(message)
        self.status_label.setStyleSheet(
            "color: #fa8585;" if isDarkTheme() else "color: #bd3030;"
        )
        self.status_label.show()
        self.status_host.show()
        self.download_button.setEnabled(self.selected_version is not None)
        self.close_button.setEnabled(True)

    def set_downloading(self) -> None:
        """Show the selected version's verified transfer without closing the panel."""

        version = self.selected_version
        if version is None:
            return
        self.status_label.setText(
            render_application_text(
                app_text("Downloading and verifying %1…", version.version_name)
            )
        )
        self.status_label.show()
        self.status_host.show()
        self.busy_ring.start()
        self.busy_ring.show()
        self.download_button.setEnabled(False)
        self.close_button.setEnabled(False)

    def finish_download(self) -> None:
        """Confirm the new file while keeping the version family inspectable."""

        version = self.selected_version
        if version is None:
            return
        self.busy_ring.stop()
        self.busy_ring.hide()
        self.status_label.setText(
            render_application_text(
                app_text(
                    "%1 downloaded beside your current file.", version.version_name
                )
            )
        )
        self.status_label.setStyleSheet(
            "color: #7bdfd7;" if isDarkTheme() else "color: #087d79;"
        )
        self.status_label.show()
        self.status_host.show()
        self._cards[version.version_id].mark_downloaded()
        self._selected_version_id = None
        self.download_button.setEnabled(False)
        self.close_button.setEnabled(True)

    def _build(self) -> None:
        """Compose a contained Fluent gallery with one horizontal chronology."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)
        candidate = self._proposal.candidate
        self.title_label = LocalizedSubtitleLabel(
            app_text("Versions of %1", candidate.model_name), self
        )
        layout.addWidget(self.title_label)
        self.family_label = LocalizedBodyLabel(
            app_text(
                "%1 · %2 · oldest to newest",
                _kind_label(candidate.artifact_kind),
                candidate.base_model or "",
            ),
            self,
        )
        self.family_host = QWidget(self)
        self.family_host.setFixedHeight(28)
        family_row = QHBoxLayout(self.family_host)
        family_row.setContentsMargins(0, 0, 0, 0)
        family_row.addWidget(self.family_label)
        family_row.addStretch(1)
        self.status_host = QWidget(self)
        status_row = QHBoxLayout(self.status_host)
        status_row.setContentsMargins(0, 0, 0, 0)
        self.busy_ring = BusyRing(self, start=False)
        self.busy_ring.setFixedSize(22, 22)
        self.status_label = QLabel(self)
        self.status_label.setStyleSheet(
            "color: #d6d6d6;" if isDarkTheme() else "color: #333333;"
        )
        status_row.addWidget(self.busy_ring)
        status_row.addWidget(self.status_label)
        family_row.addWidget(self.status_host)
        layout.addWidget(self.family_host)
        self.status_host.hide()
        self.timeline = ScrollArea(self)
        configure_qfluent_scroll_surface(self.timeline)
        self.timeline.enableTransparentBackground()
        self.timeline.setWidgetResizable(False)
        self.timeline.setFrameShape(QFrame.Shape.NoFrame)
        self.timeline.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.timeline.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.timeline.setFixedHeight(_CARD_HEIGHT + 21)
        self.card_host = QWidget(self.timeline)
        self.card_host.setObjectName("ModelVersionCardHost")
        panel_color = "#202024" if isDarkTheme() else "#ffffff"
        self.timeline.viewport().setStyleSheet(f"background-color: {panel_color};")
        self.card_host.setStyleSheet(f"background-color: {panel_color};")
        self.card_layout = QHBoxLayout(self.card_host)
        self.card_layout.setContentsMargins(0, 0, 0, 4)
        self.card_layout.setSpacing(12)
        self.timeline.setWidget(self.card_host)
        layout.addWidget(self.timeline, 1)
        footer = QHBoxLayout()
        self.provider_button = PushButton(
            render_application_text(app_text("View on CivitAI")), self
        )
        self.provider_button.setIcon(FIF.GLOBE)
        self.provider_button.clicked.connect(
            lambda: self._open_url(candidate.model_page_url)
        )
        footer.addWidget(self.provider_button)
        footer.addStretch(1)
        self.close_button = PushButton(render_application_text(app_text("Close")), self)
        self.close_button.clicked.connect(self.reject)
        footer.addWidget(self.close_button)
        self.download_button = PrimaryPushButton(
            render_application_text(app_text("Download version")), self
        )
        self.download_button.setIcon(FIF.DOWNLOAD)
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self._request_download)
        footer.addWidget(self.download_button)
        layout.addLayout(footer)

    def _select_version(self, version_id: int) -> None:
        """Allow exactly one non-current version to be downloaded at a time."""

        self._selected_version_id = version_id
        for card_id, card in self._cards.items():
            card.set_selected(card_id == version_id)
        self.download_button.setEnabled(self.selected_version is not None)

    def _scroll_to_installed(self) -> None:
        """Show the installed card beside its immediate newer neighbor."""

        installed_id = self._proposal.current.version_id
        card = self._cards.get(installed_id) if installed_id is not None else None
        if card is None:
            return
        viewport_width = self.timeline.viewport().width()
        centered = card.x() - (viewport_width - card.width()) // 2
        self.timeline.horizontalScrollBar().setValue(centered)

    def _request_download(self) -> None:
        """Ask the controller to acquire only the explicitly selected version."""

        version = self.selected_version
        if version is not None:
            self.downloadRequested.emit(version)


def _kind_label(kind: ModelArtifactKind) -> str:
    """Name the artifact type without exposing its storage identifier."""

    labels = {
        ModelArtifactKind.CHECKPOINTS: app_text("Checkpoint"),
        ModelArtifactKind.DIFFUSION_MODELS: app_text("Diffusion model"),
        ModelArtifactKind.LORAS: app_text("LoRA"),
    }
    return render_application_text(labels[kind])


__all__ = ["ModelVersionCard", "ModelVersionFamilyModal"]
