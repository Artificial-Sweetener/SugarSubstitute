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

"""Present contained CivitAI model-link validation inside onboarding."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QIcon, QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    IconWidget,
    PlainTextEdit,
    ScrollArea,
)

from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import (
    apply_application_text,
    render_application_text,
)

from substitute.application.model_recommendations import (
    ModelFamilyPresentation,
    RecommendationCardAsset,
    RecommendationLinkResult,
    RecommendationLinkStatus,
)
from substitute.domain.model_recommendations import ModelFamilyId
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
    LocalizedPrimaryPushButton,
    LocalizedPushButton,
    LocalizedSubtitleLabel,
)
from substitute.presentation.onboarding.external_link_opener import (
    civitai_model_search_url,
)
from substitute.presentation.onboarding.onboarding_model_link_rows import (
    ModelLinkReadyRow,
)
from substitute.presentation.resources.brand_icons import civitai_badge_icon_path


class ModelLinkImportOverlay(QFrame):
    """Own a non-window modal overlay constrained to the installer surface."""

    validation_requested = Signal(object, tuple)
    models_accepted = Signal(tuple)
    browse_requested = Signal(str)

    def __init__(self, *, host: QWidget) -> None:
        """Build the scrim, centered panel, result list, and stable footer."""

        super().__init__(host)
        self._host = host
        self._family_id: ModelFamilyId | None = None
        self._ready_cards: tuple[RecommendationCardAsset, ...] = ()
        self._editing_existing = False
        self._browse_url = "https://civitai.com/search/models"
        self.setObjectName("OnboardingModelLinkImportOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 28)
        self.panel = QFrame(self)
        self.panel.setObjectName("OnboardingModelLinkImportPanel")
        self.panel.setFixedSize(720, 540)
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(26, 22, 26, 22)
        panel_layout.setSpacing(12)

        heading = QHBoxLayout()
        icon = IconWidget(QIcon(str(civitai_badge_icon_path())), self.panel)
        icon.setFixedSize(30, 30)
        heading.addWidget(icon, alignment=Qt.AlignmentFlag.AlignTop)
        heading_text = QVBoxLayout()
        heading_text.setSpacing(4)
        self.title_label = LocalizedSubtitleLabel(
            app_text("Add models from CivitAI"), self.panel
        )
        heading_text.addWidget(self.title_label)
        self.description_label = LocalizedCaptionLabel("", self.panel)
        self.description_label.setWordWrap(True)
        heading_text.addWidget(self.description_label)
        heading.addLayout(heading_text, 1)
        panel_layout.addLayout(heading)

        self.link_edit = PlainTextEdit(self.panel)
        self.link_edit.setObjectName("OnboardingModelLinkInput")
        self.link_edit.setFixedHeight(92)
        self.link_edit.setPlaceholderText(
            render_application_text(
                app_text("Paste one CivitAI model or version link per line")
            )
        )
        panel_layout.addWidget(self.link_edit)

        input_actions = QHBoxLayout()
        self.browse_button = LocalizedPushButton(app_text("Browse CivitAI"), self.panel)
        self.browse_button.setObjectName("OnboardingModelLinkBrowseButton")
        self.browse_button.clicked.connect(
            lambda: self.browse_requested.emit(self._browse_url)
        )
        input_actions.addWidget(self.browse_button)
        input_actions.addStretch(1)
        self.check_button = LocalizedPushButton(app_text("Check links"), self.panel)
        self.check_button.setObjectName("OnboardingModelLinkCheckButton")
        self.check_button.clicked.connect(self._request_validation)
        input_actions.addWidget(self.check_button)
        panel_layout.addLayout(input_actions)

        self.result_scroll = ScrollArea(self.panel)
        self.result_scroll.setObjectName("OnboardingModelLinkResultScroll")
        self.result_scroll.viewport().setObjectName("OnboardingModelLinkResultViewport")
        self.result_scroll.setWidgetResizable(True)
        self.result_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.result_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.result_scroll.enableTransparentBackground()
        self.result_scroll.setStyleSheet(
            "ScrollArea, QWidget#OnboardingModelLinkResultViewport {"
            "background: transparent; border: none;}"
        )
        self.result_host = QFrame(self.result_scroll)
        self.result_host.setObjectName("OnboardingModelLinkResults")
        self.result_layout = QVBoxLayout(self.result_host)
        self.result_layout.setContentsMargins(14, 10, 14, 10)
        self.result_layout.setSpacing(5)
        self.status_label = LocalizedBodyLabel(
            app_text("Paste links above to preview compatible models."),
            self.result_host,
        )
        self.status_label.setWordWrap(True)
        self.result_layout.addWidget(self.status_label)
        self.result_layout.addStretch(1)
        self.result_scroll.setWidget(self.result_host)
        self.result_scroll.viewport().setStyleSheet("background: transparent;")
        panel_layout.addWidget(self.result_scroll, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.cancel_button = LocalizedPushButton(app_text("Cancel"), self.panel)
        self.cancel_button.setObjectName("OnboardingModelLinkCancelButton")
        self.cancel_button.clicked.connect(self.close_overlay)
        footer.addWidget(self.cancel_button)
        self.add_button = LocalizedPrimaryPushButton(app_text("Add models"), self.panel)
        self.add_button.setObjectName("OnboardingModelLinkAddButton")
        self.add_button.setEnabled(False)
        self.add_button.clicked.connect(self._accept_ready_models)
        footer.addWidget(self.add_button)
        panel_layout.addLayout(footer)
        outer.addWidget(self.panel, alignment=Qt.AlignmentFlag.AlignCenter)
        host.installEventFilter(self)
        self.hide()

    def open_for(
        self,
        family_id: ModelFamilyId,
        presentation: ModelFamilyPresentation,
        imported_cards: tuple[RecommendationCardAsset, ...],
    ) -> None:
        """Open over the installer and restore this family's accepted links."""

        self._family_id = family_id
        self._browse_url = civitai_model_search_url(family_id)
        self._editing_existing = bool(imported_cards)
        apply_application_text(
            self.description_label,
            app_text(
                "CivitAI is a library of community-made image models. Browse it, then paste the links you want below—we'll check that they work with %1.",
                presentation.name,
            ),
        )
        self.link_edit.setPlainText(
            "\n".join(card.recommendation.model_page_url for card in imported_cards)
        )
        self._ready_cards = imported_cards
        if imported_cards:
            self._render_accepted_cards(imported_cards)
        else:
            self._clear_results()
            apply_application_text(
                self.status_label,
                app_text("Paste links above to preview compatible models."),
            )
        self._update_add_button()
        self.setGeometry(self._host.rect())
        self.show()
        self.raise_()
        self.link_edit.setFocus()

    def show_checking(self) -> None:
        """Disable repeated submission while the background resolver runs."""

        self.check_button.setEnabled(False)
        self.add_button.setEnabled(False)
        apply_application_text(self.status_label, app_text("Checking model links…"))

    def set_results(self, results: tuple[RecommendationLinkResult, ...]) -> None:
        """Render concise per-link validation and retain every ready preview."""

        self.check_button.setEnabled(True)
        self._clear_results()
        ready_cards = tuple(
            result.card
            for result in results
            if result.status is RecommendationLinkStatus.READY
            and result.card is not None
        )
        self._ready_cards = ready_cards
        if not results:
            apply_application_text(
                self.status_label,
                app_text("Paste at least one CivitAI model link."),
            )
        else:
            self.status_label.hide()
            for result in results:
                self.result_layout.insertWidget(
                    self.result_layout.count() - 1,
                    self._result_row(result),
                )
        self._update_add_button()

    def close_overlay(self) -> None:
        """Hide the contained surface without destroying retained session state."""

        self.hide()

    def ready_cards(self) -> tuple[RecommendationCardAsset, ...]:
        """Return the currently validated link previews for qualification."""

        return self._ready_cards

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Keep the scrim exactly within the installer when its host resizes."""

        if watched is self._host and event.type() is QEvent.Type.Resize:
            self.setGeometry(self._host.rect())
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Close the contained workflow with Escape."""

        if event.key() is Qt.Key.Key_Escape:
            self.close_overlay()
            event.accept()
            return
        super().keyPressEvent(event)

    def _request_validation(self) -> None:
        """Publish normalized non-empty input lines for background validation."""

        if self._family_id is None:
            return
        urls = tuple(
            line.strip()
            for line in self.link_edit.toPlainText().splitlines()
            if line.strip()
        )
        self.show_checking()
        self.validation_requested.emit(self._family_id, urls)

    def _accept_ready_models(self) -> None:
        """Commit only successfully resolved previews to the current family."""

        if self._ready_cards or self._editing_existing:
            self.models_accepted.emit(self._ready_cards)
            self.close_overlay()

    def _clear_results(self) -> None:
        """Delete old result rows while preserving the owned status label."""

        while self.result_layout.count() > 2:
            item = self.result_layout.takeAt(1)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self.status_label.show()

    def _render_accepted_cards(
        self, cards: tuple[RecommendationCardAsset, ...]
    ) -> None:
        """Restore concise accepted-model rows when reopening the overlay."""

        self._clear_results()
        self.status_label.hide()
        for card in cards:
            self.result_layout.insertWidget(
                self.result_layout.count() - 1,
                self._ready_row(card),
            )

    def _result_row(self, result: RecommendationLinkResult) -> QWidget:
        """Return one localized status row for a submitted link."""

        if result.card is not None:
            return self._ready_row(result.card)
        if result.status is RecommendationLinkStatus.INVALID:
            text = app_text("Invalid CivitAI model link")
        elif result.status is RecommendationLinkStatus.INCOMPATIBLE:
            text = app_text("This model is not compatible with the current family")
        elif result.status is RecommendationLinkStatus.DUPLICATE:
            text = app_text("This model is already in your list")
        else:
            text = app_text("CivitAI could not check this link right now")
        label = LocalizedCaptionLabel(text, self.result_host)
        label.setWordWrap(True)
        return label

    def _ready_row(self, card: RecommendationCardAsset) -> ModelLinkReadyRow:
        """Return a preview row connected to this overlay's draft state."""

        row = ModelLinkReadyRow(card, self.result_host)
        row.removal_requested.connect(
            lambda version_id: self._remove_ready_card(version_id, row)
        )
        return row

    def _remove_ready_card(self, version_id: int, row: QWidget) -> None:
        """Remove one accepted preview and its source link from the draft list."""

        removed_urls = {
            card.recommendation.model_page_url
            for card in self._ready_cards
            if card.recommendation.version_id == version_id
        }
        self._ready_cards = tuple(
            card
            for card in self._ready_cards
            if card.recommendation.version_id != version_id
        )
        retained_lines = (
            line
            for line in self.link_edit.toPlainText().splitlines()
            if line.strip() not in removed_urls
        )
        self.link_edit.setPlainText("\n".join(retained_lines))
        self.result_layout.removeWidget(row)
        row.hide()
        row.setParent(None)
        row.deleteLater()
        if not self._ready_cards and self.result_layout.count() == 2:
            self.status_label.show()
            apply_application_text(
                self.status_label,
                app_text("Paste links above to preview compatible models."),
            )
        self._update_add_button()

    def _update_add_button(self) -> None:
        """Keep the final action count and enabled state synchronized."""

        count = len(self._ready_cards)
        apply_application_text(
            self.add_button,
            app_text("Save changes")
            if self._editing_existing
            else (
                (
                    app_text("Add 1 model")
                    if count == 1
                    else app_text("Add %1 models", count)
                )
                if count
                else app_text("Add models")
            ),
        )
        self.add_button.setEnabled(count > 0 or self._editing_existing)


__all__ = ["ModelLinkImportOverlay"]
