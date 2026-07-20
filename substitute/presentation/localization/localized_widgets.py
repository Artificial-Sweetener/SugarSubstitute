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

"""Provide drop-in Qt widgets that retain explicitly marked app messages."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QCoreApplication, QEvent, QObject
from PySide6.QtWidgets import QLabel, QPushButton, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CaptionLabel,
    CheckBox,
    PrimaryPushButton,
    PushButton,
    RadioButton,
    StrongBodyLabel,
    SubtitleLabel,
    SwitchButton,
    TitleLabel,
)

from sugarsubstitute_shared.presentation.localization import (
    ApplicationMessage,
    clear_localized_property,
    set_localized_accessible_description,
    set_localized_accessible_name,
    set_localized_text,
    set_localized_tooltip,
)
from sugarsubstitute_shared.presentation.fluent_tooltips import (
    set_fluent_tooltip_text,
)


class _LocalizedTextOwner:
    """Bind only explicit message markers passed to an otherwise normal widget."""

    _accept_localized_messages: bool

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Preserve native construction, then retain any explicit text marker."""

        self._accept_localized_messages = False
        super().__init__(*args, **kwargs)
        self._accept_localized_messages = True
        message = _first_message((*args, *kwargs.values()))
        if message is not None:
            self.setText(message)

    def setText(self, text: str) -> None:  # noqa: N802
        """Bind marked app copy and pass opaque strings through unchanged."""

        if self._accept_localized_messages and isinstance(text, ApplicationMessage):
            set_localized_text(
                cast(QObject, self),
                text.source_text,
                *text.arguments,
                property_setter=self._set_translated_text,
            )
            return
        if self._accept_localized_messages:
            clear_localized_property(cast(QObject, self), "text")
        super().setText(str(text))  # type: ignore[misc]

    def _set_translated_text(self, text: str) -> None:
        """Apply a rendered translation without clearing its source binding."""

        super().setText(text)  # type: ignore[misc]

    def setToolTip(self, text: str) -> None:  # noqa: N802
        """Bind a marked tooltip and preserve ordinary tooltip content."""

        if self._accept_localized_messages and isinstance(text, ApplicationMessage):
            set_localized_tooltip(
                cast(QObject, self),
                text.source_text,
                *text.arguments,
            )
            return
        if self._accept_localized_messages:
            clear_localized_property(cast(QObject, self), "tooltip")
        set_fluent_tooltip_text(cast(QWidget, self), str(text))

    def setAccessibleName(self, text: str) -> None:  # noqa: N802
        """Bind a marked accessible name and preserve ordinary content."""

        if self._accept_localized_messages and isinstance(text, ApplicationMessage):
            set_localized_accessible_name(
                cast(QObject, self),
                text.source_text,
                *text.arguments,
                property_setter=self._set_translated_accessible_name,
            )
            return
        if self._accept_localized_messages:
            clear_localized_property(cast(QObject, self), "accessible_name")
        super().setAccessibleName(str(text))  # type: ignore[misc]

    def _set_translated_accessible_name(self, text: str) -> None:
        """Apply a translated accessible name without releasing its binding."""

        super().setAccessibleName(text)  # type: ignore[misc]

    def setAccessibleDescription(self, text: str) -> None:  # noqa: N802
        """Bind a marked accessible description and preserve ordinary content."""

        if self._accept_localized_messages and isinstance(text, ApplicationMessage):
            set_localized_accessible_description(
                cast(QObject, self),
                text.source_text,
                *text.arguments,
                property_setter=self._set_translated_accessible_description,
            )
            return
        if self._accept_localized_messages:
            clear_localized_property(cast(QObject, self), "accessible_description")
        super().setAccessibleDescription(str(text))  # type: ignore[misc]

    def _set_translated_accessible_description(self, text: str) -> None:
        """Apply a translated accessible description without losing its binding."""

        super().setAccessibleDescription(text)  # type: ignore[misc]


def _first_message(values: tuple[object, ...]) -> ApplicationMessage | None:
    """Return the first explicit message in one overloaded constructor call."""

    return next(
        (value for value in values if isinstance(value, ApplicationMessage)), None
    )


class LocalizedLabel(_LocalizedTextOwner, QLabel):
    """Retain marked text while preserving QLabel behavior and rendering."""


class LocalizedBodyLabel(_LocalizedTextOwner, BodyLabel):  # type: ignore[misc]
    """Retain marked text while preserving Fluent BodyLabel behavior."""


class LocalizedCaptionLabel(_LocalizedTextOwner, CaptionLabel):  # type: ignore[misc]
    """Retain marked text while preserving Fluent CaptionLabel behavior."""


class LocalizedStrongBodyLabel(
    _LocalizedTextOwner,
    StrongBodyLabel,  # type: ignore[misc]
):
    """Retain marked text while preserving Fluent StrongBodyLabel behavior."""


class LocalizedSubtitleLabel(_LocalizedTextOwner, SubtitleLabel):  # type: ignore[misc]
    """Retain marked text while preserving Fluent SubtitleLabel behavior."""


class LocalizedTitleLabel(_LocalizedTextOwner, TitleLabel):  # type: ignore[misc]
    """Retain marked text while preserving Fluent TitleLabel behavior."""


class LocalizedPushButton(_LocalizedTextOwner, PushButton):  # type: ignore[misc]
    """Retain marked text while preserving Fluent PushButton behavior."""


class LocalizedNativePushButton(_LocalizedTextOwner, QPushButton):
    """Retain marked text while preserving native QPushButton behavior."""


class LocalizedPrimaryPushButton(
    _LocalizedTextOwner,
    PrimaryPushButton,  # type: ignore[misc]
):
    """Retain marked text while preserving Fluent PrimaryPushButton behavior."""


class LocalizedCheckBox(_LocalizedTextOwner, CheckBox):  # type: ignore[misc]
    """Retain marked text while preserving Fluent CheckBox behavior."""


class LocalizedRadioButton(_LocalizedTextOwner, RadioButton):  # type: ignore[misc]
    """Retain marked text while preserving Fluent RadioButton behavior."""


class LocalizedSwitchButton(SwitchButton):  # type: ignore[misc]
    """Refresh Fluent's cached default on/off labels after a locale change."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Construct the native control and apply the active locale immediately."""

        super().__init__(*args, **kwargs)
        self._retranslate_state_labels()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Retranslate dependency-owned state text without replacing the control."""

        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate_state_labels()
        super().changeEvent(event)

    def _retranslate_state_labels(self) -> None:
        """Refresh Fluent's cached state labels for the installed translator."""

        on_text = QCoreApplication.translate("SwitchButton", "On")
        off_text = QCoreApplication.translate("SwitchButton", "Off")
        self.setOnText(on_text)
        self.setOffText(off_text)
        self.setText(on_text if self.isChecked() else off_text)


__all__ = [
    "LocalizedBodyLabel",
    "LocalizedCaptionLabel",
    "LocalizedCheckBox",
    "LocalizedLabel",
    "LocalizedNativePushButton",
    "LocalizedPrimaryPushButton",
    "LocalizedPushButton",
    "LocalizedRadioButton",
    "LocalizedStrongBodyLabel",
    "LocalizedSubtitleLabel",
    "LocalizedSwitchButton",
    "LocalizedTitleLabel",
]
