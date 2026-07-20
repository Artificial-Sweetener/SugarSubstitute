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

"""Provide one installed Qt translator with replaceable active delegates."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QObject, QThread, QTranslator


class CompositeTranslator(QTranslator):
    """Resolve translations through one immutable active-only delegate tuple."""

    def __init__(
        self,
        delegates: Iterable[QTranslator] = (),
        parent: QObject | None = None,
    ) -> None:
        """Retain the initial delegate generation under one process translator."""

        super().__init__(parent)
        self._delegates = tuple(delegates)

    @property
    def delegates(self) -> tuple[QTranslator, ...]:
        """Return the current delegate generation for diagnostics and release tests."""

        return self._delegates

    def replace_delegates(
        self,
        delegates: Iterable[QTranslator],
    ) -> tuple[QTranslator, ...]:
        """Atomically swap delegates on the translator's owning Qt thread."""

        if QThread.currentThread() != self.thread():
            raise RuntimeError(
                "Translator delegates must be replaced on the owner thread."
            )
        previous = self._delegates
        self._delegates = tuple(delegates)
        return previous

    def translate(
        self,
        context: str,
        source_text: str,
        disambiguation: str | None = None,
        n: int = -1,
    ) -> str:
        """Return the first nonempty active translation in priority order."""

        delegates = self._delegates
        for delegate in delegates:
            translated = delegate.translate(context, source_text, disambiguation, n)
            if translated:
                return translated
        return source_text


__all__ = ["CompositeTranslator"]
