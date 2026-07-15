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

"""Adapt macOS NSSpellChecker to the prompt spellcheck gateway contract."""

from __future__ import annotations

from typing import Any


class MacOSSpellCheckGateway:
    """Use AppKit NSSpellChecker for native macOS spellcheck."""

    def __init__(self, *, language_tag: str) -> None:
        """Load the shared AppKit spell checker when PyObjC is available."""

        self._language_tag = language_tag.replace("_", "-")
        self._checker: Any | None = None
        self._reason: str | None = None
        try:
            from AppKit import NSSpellChecker  # type: ignore[import-not-found]

            self._checker = NSSpellChecker.sharedSpellChecker()
            if self._checker is None:
                self._reason = "NSSpellChecker is unavailable."
        except ImportError:
            self._reason = "PyObjC AppKit is not installed."
        except Exception as error:
            self._reason = f"NSSpellChecker initialization failed: {error!r}."

    def is_available(self) -> bool:
        """Return whether the AppKit spell checker loaded."""

        return self._checker is not None

    def availability_reason(self) -> str | None:
        """Return the AppKit unavailability reason."""

        return self._reason

    def check_word(self, word: str) -> bool:
        """Return whether NSSpellChecker accepts one word."""

        if self._checker is None:
            return True
        result = self._checker.checkSpellingOfString_startingAt_language_wrap_inSpellDocumentWithTag_wordCount_(
            word,
            0,
            self._language_tag,
            False,
            0,
            None,
        )
        range_value = result[0] if isinstance(result, tuple) else result
        return int(getattr(range_value, "location", -1)) < 0

    def suggest(self, word: str, *, limit: int = 8) -> tuple[str, ...]:
        """Return NSSpellChecker guesses for one rejected word."""

        if self._checker is None:
            return ()
        from Foundation import NSMakeRange  # type: ignore[import-not-found]

        guesses = (
            self._checker.guessesForWordRange_inString_language_inSpellDocumentWithTag_(
                NSMakeRange(0, len(word)),
                word,
                self._language_tag,
                0,
            )
        )
        return tuple(str(guess) for guess in (guesses or ()))[:limit]

    def supports_session_ignore(self) -> bool:
        """Return whether AppKit session ignore is available."""

        return self._checker is not None and hasattr(
            self._checker,
            "ignoreWord_inSpellDocumentWithTag_",
        )

    def ignore_for_session(self, word: str) -> None:
        """Ignore one word for the AppKit spell document session."""

        if self.supports_session_ignore():
            checker = self._checker
            if checker is not None:
                checker.ignoreWord_inSpellDocumentWithTag_(word, 0)

    def supports_persistent_add(self) -> bool:
        """Return whether AppKit learned-word persistence is available."""

        return self._checker is not None and hasattr(self._checker, "learnWord_")

    def add_to_dictionary(self, word: str) -> bool:
        """Persist one word in the user's learned AppKit words."""

        if not self.supports_persistent_add():
            return False
        checker = self._checker
        if checker is None:
            return False
        checker.learnWord_(word)
        return True


__all__ = ["MacOSSpellCheckGateway"]
