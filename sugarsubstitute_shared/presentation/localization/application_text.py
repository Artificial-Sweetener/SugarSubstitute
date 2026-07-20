#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Bind explicitly identified application text to Qt language changes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtCore import QCoreApplication, QEvent, QObject

_APPLICATION_CONTEXT = "AppText"
_BINDINGS_ATTRIBUTE = "_sugarsubstitute_localized_property_bindings"


class LocalizedPropertyBinding(QObject):
    """Own one explicitly registered translated property on a Qt object."""

    def __init__(
        self,
        owner: QObject,
        *,
        setter: Callable[[str], None],
        source_text: str,
        arguments: tuple[object, ...],
    ) -> None:
        """Bind one source message without inspecting unrelated widget state."""

        super().__init__(owner)
        self._owner = owner
        self._setter = setter
        self._source_text = source_text
        self._arguments = arguments
        owner.installEventFilter(self)
        self.retranslate()

    def set_message(self, source_text: str, arguments: tuple[object, ...]) -> None:
        """Replace the explicitly owned message and render the active locale."""

        self._source_text = source_text
        self._arguments = arguments
        self.retranslate()

    def retranslate(self) -> None:
        """Render the source message through the active application translator."""

        self._setter(translate_application_message(self._source_text, *self._arguments))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Refresh only this registered property on a language change."""

        if watched is self._owner and event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        return False


def translate_application_text(source_text: str) -> str:
    """Translate one explicit SugarSubstitute-owned English source message."""

    return QCoreApplication.translate(_APPLICATION_CONTEXT, source_text)


def translate_application_message(source_text: str, *arguments: object) -> str:
    """Translate and interpolate one explicit numbered application message."""

    translated = translate_application_text(source_text)
    for index in range(len(arguments), 0, -1):
        translated = translated.replace(
            f"%{index}",
            _render_argument(arguments[index - 1]),
        )
    return translated


def _render_argument(argument: object) -> str:
    """Resolve nested explicit messages while preserving opaque argument text."""

    from sugarsubstitute_shared.presentation.localization.application_message import (
        ApplicationMessage,
    )

    if isinstance(argument, ApplicationMessage):
        return translate_application_message(
            argument.source_text,
            *argument.arguments,
        )
    return str(argument)


def set_localized_text(
    target: QObject,
    source_text: str,
    *arguments: object,
    property_setter: Callable[[str], None] | None = None,
) -> None:
    """Bind an object's normal text property to one application message."""

    setter = property_setter or getattr(target, "setText", None)
    if not callable(setter):
        raise TypeError("Localized text targets must expose setText().")
    _set_localized_property(target, "text", setter, source_text, arguments)


def set_localized_tooltip(
    target: QObject,
    source_text: str,
    *arguments: object,
) -> None:
    """Bind an object's tooltip to one application message."""

    from sugarsubstitute_shared.presentation.fluent_tooltips import (
        set_fluent_tooltip_text,
    )

    if not callable(getattr(target, "setToolTip", None)):
        raise TypeError("Localized tooltip targets must expose setToolTip().")
    if not isinstance(target, QObject):
        set_fluent_tooltip_text(
            cast(Any, target),
            translate_application_message(source_text, *arguments),
        )
        return
    _set_localized_property(
        target,
        "tooltip",
        lambda text: set_fluent_tooltip_text(cast(Any, target), text),
        source_text,
        arguments,
    )


def set_localized_accessible_name(
    target: QObject,
    source_text: str,
    *arguments: object,
    property_setter: Callable[[str], None] | None = None,
) -> None:
    """Bind an object's accessible name to one application message."""

    setter = property_setter or getattr(target, "setAccessibleName", None)
    if not callable(setter):
        raise TypeError(
            "Localized accessible-name targets must expose setAccessibleName()."
        )
    _set_localized_property(
        target,
        "accessible_name",
        setter,
        source_text,
        arguments,
    )


def set_localized_accessible_description(
    target: QObject,
    source_text: str,
    *arguments: object,
    property_setter: Callable[[str], None] | None = None,
) -> None:
    """Bind an object's accessible description to one application message."""

    setter = property_setter or getattr(target, "setAccessibleDescription", None)
    if not callable(setter):
        raise TypeError(
            "Localized accessible-description targets must expose "
            "setAccessibleDescription()."
        )
    _set_localized_property(
        target,
        "accessible_description",
        setter,
        source_text,
        arguments,
    )


def set_localized_window_title(
    target: QObject,
    source_text: str,
    *arguments: object,
) -> None:
    """Bind a window title to one application message."""

    setter = getattr(target, "setWindowTitle", None)
    if not callable(setter):
        raise TypeError("Localized window targets must expose setWindowTitle().")
    _set_localized_property(
        target,
        "window_title",
        setter,
        source_text,
        arguments,
    )


def set_localized_placeholder(
    target: QObject,
    source_text: str,
    *arguments: object,
) -> None:
    """Bind an editor placeholder without touching its authored value."""

    setter = getattr(target, "setPlaceholderText", None)
    if not callable(setter):
        raise TypeError(
            "Localized placeholder targets must expose setPlaceholderText()."
        )
    _set_localized_property(
        target,
        "placeholder",
        setter,
        source_text,
        arguments,
    )


def _set_localized_property(
    target: QObject,
    property_name: str,
    setter: Callable[[str], None],
    source_text: str,
    arguments: tuple[object, ...],
) -> None:
    """Create or update one target-owned explicit translation binding."""

    bindings = getattr(target, _BINDINGS_ATTRIBUTE, None)
    if not isinstance(bindings, dict):
        bindings = {}
        setattr(target, _BINDINGS_ATTRIBUTE, bindings)
    binding = bindings.get(property_name)
    if isinstance(binding, LocalizedPropertyBinding):
        binding.set_message(source_text, arguments)
        return
    bindings[property_name] = LocalizedPropertyBinding(
        target,
        setter=setter,
        source_text=source_text,
        arguments=arguments,
    )


def clear_localized_property(target: QObject, property_name: str) -> None:
    """Release one prior localized binding before assigning opaque content."""

    bindings = getattr(target, _BINDINGS_ATTRIBUTE, None)
    if not isinstance(bindings, dict):
        return
    binding = bindings.pop(property_name, None)
    if not isinstance(binding, LocalizedPropertyBinding):
        return
    target.removeEventFilter(binding)
    binding.setParent(None)
    binding.deleteLater()


__all__ = [
    "LocalizedPropertyBinding",
    "clear_localized_property",
    "set_localized_accessible_description",
    "set_localized_accessible_name",
    "set_localized_placeholder",
    "set_localized_text",
    "set_localized_tooltip",
    "set_localized_window_title",
    "translate_application_message",
    "translate_application_text",
]
