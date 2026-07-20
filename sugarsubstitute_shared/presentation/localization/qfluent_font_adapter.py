#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Synchronize QFluent's independent font owner with the active Qt locale."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import cast

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QWidget

FontFamilyState = tuple[str, ...]
_FontFamiliesGetter = Callable[[], list[str]]
_FontFamiliesSetter = Callable[[list[str], bool], None]
_StyleSheetUpdater = Callable[[bool], None]


class QFluentFontFamilyAdapter:
    """Keep QFluent-created fonts aligned with the active application font."""

    def __init__(self, application: QApplication) -> None:
        """Retain the widget owner without importing QFluent during module import."""

        self._application = application
        self._baseline_families: FontFamilyState | None = None

    def snapshot(self) -> FontFamilyState:
        """Return QFluent's exact global family state for transaction rollback."""

        font_families, _, _ = _qfluent_font_api()
        state = tuple(font_families())
        if self._baseline_families is None:
            self._baseline_families = state
        return state

    def apply_application_font(self, font: QFont) -> None:
        """Apply active locale fallbacks to new and already-mounted QFluent fonts."""

        baseline = self._baseline_families
        if baseline is None:
            baseline = self.snapshot()
        self._replace_families(_merged_families(font.families(), baseline))

    def restore(self, state: object) -> None:
        """Restore one exact QFluent family state after rollback or shutdown."""

        if not isinstance(state, tuple) or not all(
            isinstance(family, str) for family in state
        ):
            raise ValueError("QFluent font-family state is invalid.")
        self._replace_families(state)

    def _replace_families(self, families: FontFamilyState) -> None:
        """Refresh QFluent QSS and explicit fonts without disturbing font metrics."""

        font_families, set_font_families, update_style_sheet = _qfluent_font_api()
        previous_families = tuple(font_families())
        if previous_families == families:
            return
        matching_widgets = tuple(
            widget
            for widget in self._application.allWidgets()
            if tuple(widget.font().families()) == previous_families
        )
        set_font_families(list(families), False)
        update_style_sheet(False)
        for widget in matching_widgets:
            _replace_widget_font_families(widget, families)


def _qfluent_font_api() -> tuple[
    _FontFamiliesGetter,
    _FontFamiliesSetter,
    _StyleSheetUpdater,
]:
    """Load QFluent's public font API only when a runtime manager needs it."""

    try:
        from qfluentwidgets.common.font import (  # type: ignore[import-untyped]
            fontFamilies,
            setFontFamilies,
        )
        from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
            updateStyleSheet,
        )

        return (
            cast(_FontFamiliesGetter, fontFamilies),
            cast(_FontFamiliesSetter, setFontFamilies),
            cast(_StyleSheetUpdater, updateStyleSheet),
        )
    except ImportError as error:
        raise RuntimeError("QFluent's font-family API is unavailable.") from error


def _merged_families(
    application_families: Sequence[str],
    baseline_families: Sequence[str],
) -> FontFamilyState:
    """Place active locale fallbacks before the library's durable defaults."""

    return tuple(
        dict.fromkeys(
            family for family in (*application_families, *baseline_families) if family
        )
    )


def _replace_widget_font_families(
    widget: QWidget,
    families: FontFamilyState,
) -> None:
    """Preserve size, weight, and style while replacing only fallback families."""

    font = QFont(widget.font())
    font.setFamilies(list(families))
    widget.setFont(font)


__all__ = ["FontFamilyState", "QFluentFontFamilyAdapter"]
