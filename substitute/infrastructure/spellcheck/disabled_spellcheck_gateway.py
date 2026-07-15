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

"""Provide a non-failing spellcheck gateway for unavailable configurations."""

from __future__ import annotations


class DisabledSpellCheckGateway:
    """Disable spellcheck while preserving the spellcheck gateway contract."""

    def __init__(self, reason: str) -> None:
        """Store the user/actionable reason for disabled spellcheck."""

        self._reason = reason

    def is_available(self) -> bool:
        """Return that spellcheck is not available."""

        return False

    def availability_reason(self) -> str | None:
        """Return the configured disabled reason."""

        return self._reason

    def check_word(self, word: str) -> bool:
        """Accept every word so disabled spellcheck never creates diagnostics."""

        _ = word
        return True

    def suggest(self, word: str, *, limit: int = 8) -> tuple[str, ...]:
        """Return no suggestions while spellcheck is disabled."""

        _ = word
        _ = limit
        return ()

    def supports_session_ignore(self) -> bool:
        """Return that session ignore is unavailable."""

        return False

    def ignore_for_session(self, word: str) -> None:
        """Ignore disabled gateway session mutations."""

        _ = word

    def supports_persistent_add(self) -> bool:
        """Return that persistent dictionary additions are unavailable."""

        return False

    def add_to_dictionary(self, word: str) -> bool:
        """Return that the word was not persisted."""

        _ = word
        return False


__all__ = ["DisabledSpellCheckGateway"]
