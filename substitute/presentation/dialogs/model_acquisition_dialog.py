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

"""Present a reviewed cart of exact missing workflow models."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtNetwork import QNetworkAccessManager
from PySide6.QtWidgets import QLayout, QLineEdit, QScrollArea, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, LineEdit  # type: ignore[import-untyped]

from sugarsubstitute_shared.localization import ApplicationMessage, app_text
from sugarsubstitute_shared.presentation.localization import (
    set_localized_placeholder,
)

from substitute.application.recipes import (
    RecipeModelResolutionRequired,
    RecipeModelUnresolvedReference,
)
from substitute.domain.model_metadata import CivitaiDownloadAccess
from substitute.presentation.dialogs.full_window_modal import FullWindowModalBase
from substitute.presentation.dialogs.model_acquisition_card import (
    ModelAcquisitionCard,
    UrlOpener,
)
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedPrimaryPushButton,
    LocalizedPushButton,
    LocalizedSubtitleLabel,
)
from substitute.presentation.onboarding.onboarding_model_card_layout import (
    ModelCardLayout,
)
from substitute.presentation.widgets.civitai_page_action import open_external_url

_DIALOG_WIDTH = 940
_DIALOG_MINIMUM_HEIGHT = 440
_DIALOG_API_KEY_MINIMUM_HEIGHT = 530
_ACTION_BUTTON_HEIGHT = 34


class ModelAcquisitionAction(str, Enum):
    """Describe the action selected from the model acquisition dialog."""

    DOWNLOAD = "download"
    SETTINGS = "settings"
    CANCEL = "cancel"


class ModelAcquisitionDialog(FullWindowModalBase):
    """Review every unique missing model before any download begins."""

    def __init__(
        self,
        required: RecipeModelResolutionRequired,
        *,
        has_api_key: bool,
        downloads_enabled: bool,
        open_url: UrlOpener | None = None,
        preview_images_by_sha256: Mapping[str, QImage] | None = None,
        parent: object | None = None,
    ) -> None:
        """Build a deterministic cart from one shared resolution request."""

        super().__init__(parent)
        self._references = _unique_references(required.references)
        self._has_api_key = has_api_key
        self._downloads_enabled = downloads_enabled
        self._selected_action = ModelAcquisitionAction.CANCEL
        self._open_url = open_url or open_external_url
        self._preview_images = preview_images_by_sha256 or {}
        self.cards: list[ModelAcquisitionCard] = []
        self.setClosableOnMaskClicked(False)
        self.setModal(True)
        self.hideYesButton()
        self.hideCancelButton()
        minimum_height = (
            _DIALOG_API_KEY_MINIMUM_HEIGHT
            if self._requires_api_key() and not has_api_key
            else _DIALOG_MINIMUM_HEIGHT
        )
        self.widget.setMinimumSize(_DIALOG_WIDTH, minimum_height)
        self.widget.setMaximumWidth(_DIALOG_WIDTH)
        self._thumbnail_network = QNetworkAccessManager(self.widget)
        self._api_key_edit = LineEdit(self.widget)
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        set_localized_placeholder(self._api_key_edit, "CivitAI API key")
        self._build_header()
        self._build_cart()
        self._build_api_key_requirement()
        self._build_actions()

    @property
    def selected_action(self) -> ModelAcquisitionAction:
        """Return the explicitly selected acquisition action."""

        return self._selected_action

    def entered_api_key(self) -> str:
        """Return the API key entered through the acquisition shortcut."""

        return cast(str, self._api_key_edit.text()).strip()

    def _build_header(self) -> None:
        """Create workflow-neutral title and current availability guidance."""

        header = QWidget(self.widget)
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(
            LocalizedSubtitleLabel(
                app_text("Models required by this workflow"),
                header,
            )
        )
        message = LocalizedBodyLabel(self._header_message(), header)
        message.setWordWrap(True)
        layout.addWidget(message)
        self.viewLayout.addWidget(header)

    def _build_cart(self) -> None:
        """Create a wrapping, scrollable grid using the installer card language."""

        scroll = QScrollArea(self.widget)
        scroll.setObjectName("ModelAcquisitionCartScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea#ModelAcquisitionCartScroll { background: transparent; }"
            "QScrollArea#ModelAcquisitionCartScroll > QWidget > QWidget {"
            " background: transparent; }"
        )
        scroll.viewport().setAutoFillBackground(False)
        host = QWidget(scroll)
        host.setObjectName("ModelAcquisitionCart")
        host.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = ModelCardLayout(host)
        for reference in self._references:
            card = ModelAcquisitionCard(
                reference,
                network=self._thumbnail_network,
                open_url=self._open_url,
                preview_image=self._preview_images.get(reference.sha256),
                parent=host,
            )
            layout.addWidget(card)
            self.cards.append(card)
        host.setMinimumHeight(layout.heightForWidth(_DIALOG_WIDTH - 72))
        scroll.setWidget(host)
        self.viewLayout.addWidget(scroll, 1)

    def _build_api_key_requirement(self) -> None:
        """Show credentials only when one exact candidate is known to require them."""

        self._api_key_edit.hide()
        if not self._requires_api_key() or self._has_api_key:
            return
        label = LocalizedBodyLabel(
            app_text(
                "Some CivitAI downloads require an API key. Paste it here to use it for "
                "this download and save it for next time."
            ),
            self.widget,
        )
        label.setObjectName("ModelAcquisitionApiKeyGuidance")
        label.setWordWrap(True)
        self.viewLayout.addWidget(label)
        self._api_key_edit.setObjectName("ModelAcquisitionApiKey")
        self._api_key_edit.show()
        self._api_key_edit.textChanged.connect(self._update_download_enabled)
        self.viewLayout.addWidget(self._api_key_edit)

    def _build_actions(self) -> None:
        """Create a stable footer with cancellation, settings, and install actions."""

        self.buttonGroup.show()
        self.buttonGroup.setFixedHeight(70)
        _clear_layout(self.buttonLayout)
        self.yesButton.hide()
        self.cancelButton.hide()
        self.buttonLayout.setContentsMargins(24, 17, 24, 17)
        self.buttonLayout.setSpacing(12)
        self.buttonLayout.addStretch(1)
        self.cancel_action = LocalizedPushButton(app_text("Cancel"), self.buttonGroup)
        self.cancel_action.setFixedHeight(_ACTION_BUTTON_HEIGHT)
        self.cancel_action.clicked.connect(self.reject)
        self.buttonLayout.addWidget(self.cancel_action)
        self.settings_action = LocalizedPushButton(
            app_text("Open CivitAI Settings"), self.buttonGroup
        )
        self.settings_action.setIcon(FluentIcon.SETTING)
        self.settings_action.setFixedHeight(_ACTION_BUTTON_HEIGHT)
        self.settings_action.clicked.connect(self._accept_settings)
        self.buttonLayout.addWidget(self.settings_action)
        self.download_action = LocalizedPrimaryPushButton(
            app_text("Download %1 models", len(self._references)),
            self.buttonGroup,
        )
        self.download_action.setObjectName("ModelAcquisitionDownloadAction")
        self.download_action.setIcon(FluentIcon.DOWNLOAD)
        self.download_action.setFixedHeight(_ACTION_BUTTON_HEIGHT)
        self.download_action.clicked.connect(self._accept_download)
        self.buttonLayout.addWidget(self.download_action)
        self._update_download_enabled()

    def _header_message(self) -> ApplicationMessage:
        """Return guidance matching the aggregate cart state."""

        if not self._downloads_enabled:
            return app_text(
                "Automatic model downloads are disabled. Open CivitAI Settings to review model download preferences."
            )
        if not self._all_models_downloadable():
            return app_text(
                "Some required models do not have a verified automatic download. Review each item for details."
            )
        return app_text(
            "Review these exact model matches before downloading them to the connected ComfyUI installation."
        )

    def _all_models_downloadable(self) -> bool:
        """Return whether every unique required model has a verified candidate."""

        return bool(self._references) and all(
            reference.candidate is not None for reference in self._references
        )

    def _requires_api_key(self) -> bool:
        """Return whether any exact candidate is provider-gated."""

        return any(
            reference.candidate is not None
            and reference.candidate.download_access
            is CivitaiDownloadAccess.API_KEY_REQUIRED
            for reference in self._references
        )

    def _update_download_enabled(self) -> None:
        """Prevent acquisition until availability and credential needs are met."""

        key_ready = (
            not self._requires_api_key()
            or self._has_api_key
            or bool(self.entered_api_key())
        )
        self.download_action.setEnabled(
            self._downloads_enabled and self._all_models_downloadable() and key_ready
        )

    def _accept_download(self) -> None:
        """Accept only a currently valid aggregate acquisition request."""

        if not self.download_action.isEnabled():
            return
        self._selected_action = ModelAcquisitionAction.DOWNLOAD
        self.accept()

    def _accept_settings(self) -> None:
        """Accept with a request to open model-provider settings."""

        self._selected_action = ModelAcquisitionAction.SETTINGS
        self.accept()


def _unique_references(
    references: tuple[RecipeModelUnresolvedReference, ...],
) -> tuple[RecipeModelUnresolvedReference, ...]:
    """Return one card per exact kind/hash while retaining source order."""

    unique: dict[tuple[str, str], RecipeModelUnresolvedReference] = {}
    for reference in references:
        unique.setdefault((reference.kind, reference.sha256.upper()), reference)
    return tuple(unique.values())


def _clear_layout(layout: QLayout) -> None:
    """Remove qfluent's default action widgets from the footer layout."""

    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            widget.hide()
        nested_layout = item.layout()
        if nested_layout is not None:
            _clear_layout(nested_layout)


__all__ = ["ModelAcquisitionAction", "ModelAcquisitionDialog"]
