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

"""Define spellcheck backend contracts used by prompt editor services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SpellCheckGateway(Protocol):
    """Check words and manage backend-owned spellcheck decisions."""

    def is_available(self) -> bool:
        """Return whether a backend and dictionary are ready."""

    def availability_reason(self) -> str | None:
        """Return a diagnostic reason when the gateway is unavailable."""

    def check_word(self, word: str) -> bool:
        """Return whether one word is accepted by the active dictionary."""

    def suggest(self, word: str, *, limit: int = 8) -> tuple[str, ...]:
        """Return spelling suggestions for one rejected word."""

    def supports_session_ignore(self) -> bool:
        """Return whether ignored words can be delegated to the backend."""

    def ignore_for_session(self, word: str) -> None:
        """Accept one word until the application session ends."""

    def supports_persistent_add(self) -> bool:
        """Return whether accepted words can be stored persistently."""

    def add_to_dictionary(self, word: str) -> bool:
        """Persist one accepted word when the backend supports it."""


__all__ = ["SpellCheckGateway"]
