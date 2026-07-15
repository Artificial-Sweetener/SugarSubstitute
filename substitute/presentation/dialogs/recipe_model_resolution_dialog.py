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

"""Render the pre-materialization recipe model resolver dialog."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QLayout,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    FluentIcon,
    LineEdit,
    MessageBoxBase,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
)
from shiboken6 import isValid

from substitute.application.recipes import (
    RecipeModelCivitaiState,
    RecipeModelResolutionRequired,
)

_FALLBACK_PARENT: QWidget | None = None
_DIALOG_WIDTH = 720
_LIST_MINIMUM_HEIGHT = 220
_ACTION_BUTTON_HEIGHT = 32
_CANCEL_BUTTON_MINIMUM_WIDTH = 88
_SETTINGS_BUTTON_MINIMUM_WIDTH = 156
_DOWNLOAD_BUTTON_MINIMUM_WIDTH = 184
_THUMBNAIL_WIDTH = 78
_THUMBNAIL_HEIGHT = 104
_REFERENCE_ROW_HEIGHT = 120


class RecipeModelResolutionAction(str):
    """Describe the action selected from the recipe model resolver dialog."""

    DOWNLOAD = "download"
    SETTINGS = "settings"
    CANCEL = "cancel"


class RecipeModelResolutionDialog(MessageBoxBase):  # type: ignore[misc]
    """Show missing recipe models before workflow materialization."""

    def __init__(
        self,
        required: RecipeModelResolutionRequired,
        *,
        has_api_key: bool,
        downloads_enabled: bool,
        parent: object | None = None,
    ) -> None:
        """Build the resolver dialog for one blocked recipe load."""

        super().__init__(_resolve_parent(parent))
        self._required = required
        self._selected_action = RecipeModelResolutionAction.CANCEL
        self.setClosableOnMaskClicked(False)
        self.setModal(True)
        self.hideYesButton()
        self.hideCancelButton()
        self.widget.setMinimumWidth(_DIALOG_WIDTH)
        self.widget.setMaximumWidth(_DIALOG_WIDTH)
        self._thumbnail_network = QNetworkAccessManager(self.widget)
        self._api_key_edit = LineEdit(self.widget)
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("CivitAI API key")
        self._build_header(downloads_enabled=downloads_enabled)
        self._build_list()
        if not has_api_key:
            self._build_api_key_shortcut()
        self._build_actions(downloads_enabled=downloads_enabled)

    @property
    def selected_action(self) -> str:
        """Return the selected resolver action."""

        return self._selected_action

    def entered_api_key(self) -> str:
        """Return the API key entered through the shortcut field."""

        return cast(str, self._api_key_edit.text()).strip()

    def _build_header(self, *, downloads_enabled: bool) -> None:
        """Create title and explanatory copy."""

        header = QWidget(self.widget)
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        can_download = _all_references_have_downloads(self._required)
        title = SubtitleLabel("Missing model", header)
        message = BodyLabel(_header_message(downloads_enabled, can_download), header)
        message.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(message)
        self.viewLayout.addWidget(header)

    def _build_list(self) -> None:
        """Create the unresolved model state list."""

        model_list = QListWidget(self.widget)
        model_list.setMinimumHeight(_LIST_MINIMUM_HEIGHT)
        model_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        model_list.setSpacing(8)
        for reference in self._required.references:
            item = QListWidgetItem(model_list)
            row = _RecipeModelReferenceRow(
                reference,
                network=self._thumbnail_network,
                parent=model_list,
            )
            item.setSizeHint(QSize(row.sizeHint().width(), _REFERENCE_ROW_HEIGHT))
            model_list.addItem(item)
            model_list.setItemWidget(item, row)
        self.viewLayout.addWidget(model_list)

    def _build_api_key_shortcut(self) -> None:
        """Create a one-time API key shortcut for CivitAI downloads."""

        label = BodyLabel(
            "Some CivitAI downloads require an API key. Paste it here to use it for "
            "this download and save it for next time.",
            self.widget,
        )
        label.setWordWrap(True)
        self.viewLayout.addWidget(label)
        self.viewLayout.addWidget(self._api_key_edit)

    def _build_actions(self, *, downloads_enabled: bool) -> None:
        """Create resolver action buttons."""

        self.buttonGroup.show()
        self.buttonGroup.setFixedHeight(68)
        _clear_layout(self.buttonLayout)
        self.yesButton.hide()
        self.cancelButton.hide()
        self.buttonLayout.setContentsMargins(24, 16, 24, 16)
        self.buttonLayout.setSpacing(12)
        self.buttonLayout.addStretch(1)
        can_download = downloads_enabled and all(
            reference.candidate is not None for reference in self._required.references
        )
        close_button = PushButton("Cancel", self.buttonGroup)
        close_button.setFixedHeight(_ACTION_BUTTON_HEIGHT)
        close_button.setMinimumWidth(_CANCEL_BUTTON_MINIMUM_WIDTH)
        close_button.clicked.connect(self.reject)
        self.buttonLayout.addWidget(close_button, 0, Qt.AlignmentFlag.AlignVCenter)

        settings_button = PushButton("Open CivitAI Settings", self.buttonGroup)
        settings_button.setIcon(FluentIcon.SETTING)
        settings_button.setFixedHeight(_ACTION_BUTTON_HEIGHT)
        settings_button.setMinimumWidth(_SETTINGS_BUTTON_MINIMUM_WIDTH)
        settings_button.clicked.connect(self._accept_settings)
        self.buttonLayout.addWidget(
            settings_button,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        download_button = PrimaryPushButton(
            "Download and open recipe", self.buttonGroup
        )
        download_button.setIcon(FluentIcon.DOWNLOAD)
        download_button.setFixedHeight(_ACTION_BUTTON_HEIGHT)
        download_button.setMinimumWidth(_DOWNLOAD_BUTTON_MINIMUM_WIDTH)
        download_button.setEnabled(can_download)
        download_button.clicked.connect(self._accept_download)
        self.buttonLayout.addWidget(
            download_button,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

    def _accept_download(self) -> None:
        """Accept the dialog with a download action."""

        self._selected_action = RecipeModelResolutionAction.DOWNLOAD
        self.accept()

    def _accept_settings(self) -> None:
        """Accept the dialog with a settings-navigation action."""

        self._selected_action = RecipeModelResolutionAction.SETTINGS
        self.accept()


class _RecipeModelReferenceRow(QWidget):
    """Render one missing model row with an optional CivitAI thumbnail."""

    def __init__(
        self,
        reference: object,
        *,
        network: QNetworkAccessManager,
        parent: QWidget,
    ) -> None:
        """Build the row and start non-blocking thumbnail loading when available."""

        super().__init__(parent)
        self._reply: QNetworkReply | None = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        self._thumbnail = QLabel("No thumbnail", self)
        self._thumbnail.setObjectName("RecipeModelResolutionThumbnail")
        self._thumbnail.setFixedSize(_THUMBNAIL_WIDTH, _THUMBNAIL_HEIGHT)
        self._thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumbnail.setWordWrap(True)
        self._thumbnail.setStyleSheet(
            "QLabel#RecipeModelResolutionThumbnail {"
            "border: 1px solid rgba(255, 255, 255, 44);"
            "border-radius: 6px;"
            "background: rgba(255, 255, 255, 18);"
            "color: rgba(255, 255, 255, 140);"
            "padding: 6px;"
            "}"
        )
        layout.addWidget(self._thumbnail, 0, Qt.AlignmentFlag.AlignTop)

        text = BodyLabel(_reference_label(reference), self)
        text.setWordWrap(True)
        text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(text, 1, Qt.AlignmentFlag.AlignVCenter)

        thumbnail_url = _thumbnail_url(reference)
        if thumbnail_url:
            self._thumbnail.setText("Loading...")
            request = QNetworkRequest(QUrl(thumbnail_url))
            self._reply = network.get(request)
            self._reply.finished.connect(self._finish_thumbnail_load)

    def _finish_thumbnail_load(self) -> None:
        """Apply a downloaded thumbnail if the asynchronous request succeeds."""

        reply = self._reply
        if reply is None:
            return
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self._thumbnail.setText("No thumbnail")
                return
            pixmap = QPixmap()
            payload = cast(bytes, reply.readAll().data())
            if not pixmap.loadFromData(payload):
                self._thumbnail.setText("No thumbnail")
                return
            self._thumbnail.setPixmap(
                pixmap.scaled(
                    self._thumbnail.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        finally:
            reply.deleteLater()
            self._reply = None


def _reference_label(reference: object) -> str:
    """Return a compact user-facing label for one unresolved reference."""

    cube_name = _cube_name(reference)
    state = getattr(reference, "civitai_state", RecipeModelCivitaiState.UNAVAILABLE)
    candidate = getattr(reference, "candidate", None)
    if candidate is not None:
        model_name = getattr(candidate, "model_name", "")
        file_name = getattr(candidate, "name", "")
        model_label = _model_file_label(model_name=model_name, file_name=file_name)
        return f"{cube_name} uses {model_label}, which is missing."
    value = str(getattr(reference, "value", "")).replace("\\", "/")
    model_label = _missing_value_label(value)
    if state is RecipeModelCivitaiState.NOT_FOUND:
        return (
            f"{cube_name} uses {model_label}, but CivitAI did not find a matching "
            "download."
        )
    if state is RecipeModelCivitaiState.NO_SAFE_FILE:
        return (
            f"{cube_name} uses {model_label}, but CivitAI did not offer a safe "
            "download."
        )
    if state is RecipeModelCivitaiState.DISABLED:
        return (
            f"{cube_name} uses {model_label}. Turn on CivitAI model lookup in "
            "Settings to search for it."
        )
    return f"{cube_name} uses {model_label}. Download information is unavailable."


def _header_message(downloads_enabled: bool, can_download: bool) -> str:
    """Return friendly explanatory copy for the current resolver state."""

    if not downloads_enabled:
        return (
            "This recipe uses a model that is not available in your current ComfyUI "
            "model folders. Turn on CivitAI model lookup in Settings to search for it."
        )
    if can_download:
        return (
            "This recipe uses a model that is not in your current ComfyUI model "
            "folders. We found a matching file on CivitAI and can download it for "
            "you, then open the recipe."
        )
    return (
        "This recipe uses a model that is not available in your current ComfyUI "
        "model folders. We could not find an automatic download that is safe to offer."
    )


def _all_references_have_downloads(required: RecipeModelResolutionRequired) -> bool:
    """Return whether every missing model can be downloaded automatically."""

    return all(reference.candidate is not None for reference in required.references)


def _model_file_label(*, model_name: object, file_name: object) -> str:
    """Return a friendly model/file label without implementation details."""

    model_text = str(model_name).strip()
    file_text = str(file_name).strip()
    if model_text and file_text:
        return f"{model_text} ({file_text})"
    if model_text:
        return model_text
    return file_text or "Model file"


def _thumbnail_url(reference: object) -> str | None:
    """Return the already-selected thumbnail URL for one reference."""

    candidate = getattr(reference, "candidate", None)
    if candidate is None:
        return None
    value = getattr(candidate, "thumbnail_url", None)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _cube_name(reference: object) -> str:
    """Return a user-facing cube name for one missing model reference."""

    alias = str(getattr(reference, "alias", "")).strip()
    return alias or "This cube"


def _missing_value_label(value: str) -> str:
    """Return the most readable name for a missing local model value."""

    normalized_value = value.strip().replace("\\", "/")
    if not normalized_value:
        return "a model"
    return normalized_value.rsplit("/", maxsplit=1)[-1] or normalized_value


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


def _resolve_parent(parent: object | None) -> QWidget:
    """Return a QWidget parent because qfluent mask dialogs require one."""

    if isinstance(parent, QWidget) and isValid(parent):
        return parent
    active_window = QApplication.activeWindow()
    if isinstance(active_window, QWidget) and isValid(active_window):
        return active_window
    global _FALLBACK_PARENT
    if _FALLBACK_PARENT is None or not isValid(_FALLBACK_PARENT):
        _FALLBACK_PARENT = QWidget()
        _FALLBACK_PARENT.resize(1024, 768)
    return _FALLBACK_PARENT


__all__ = [
    "RecipeModelResolutionAction",
    "RecipeModelResolutionDialog",
]
