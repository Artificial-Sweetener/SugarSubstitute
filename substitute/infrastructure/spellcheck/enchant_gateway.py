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

"""Adapt PyEnchant dictionaries to the prompt spellcheck gateway contract."""

from __future__ import annotations

import sys
from typing import Any

from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.spellcheck.enchant")


class EnchantSpellCheckGateway:
    """Use Enchant providers such as Hunspell or Nuspell for spellcheck."""

    def __init__(self, *, language_tag: str) -> None:
        """Load the requested Enchant dictionary when available."""

        self._language_tag = language_tag
        self._dictionary: Any | None = None
        self._reason: str | None = None
        try:
            import enchant  # type: ignore[import-not-found]

            broker = enchant.Broker()
            try:
                broker.set_ordering("*", "nuspell,hunspell,aspell")
            except Exception:
                log_warning(
                    _LOGGER,
                    "Enchant provider ordering could not be set",
                    platform=sys.platform,
                    language_tag=language_tag,
                )
            if not broker.dict_exists(language_tag):
                self._reason = f"No Enchant dictionary is installed for {language_tag}."
                return
            self._dictionary = broker.request_dict(language_tag)
        except ImportError:
            self._reason = "PyEnchant is not installed."
        except Exception as error:
            self._reason = f"Enchant initialization failed: {error!r}."

    def is_available(self) -> bool:
        """Return whether an Enchant dictionary loaded successfully."""

        return self._dictionary is not None

    def availability_reason(self) -> str | None:
        """Return the Enchant unavailability reason."""

        return self._reason

    def check_word(self, word: str) -> bool:
        """Return whether Enchant accepts one word."""

        if self._dictionary is None:
            return True
        return bool(self._dictionary.check(word))

    def suggest(self, word: str, *, limit: int = 8) -> tuple[str, ...]:
        """Return Enchant suggestions for one rejected word."""

        if self._dictionary is None:
            return ()
        return tuple(str(suggestion) for suggestion in self._dictionary.suggest(word))[
            :limit
        ]

    def supports_session_ignore(self) -> bool:
        """Return whether the loaded dictionary supports session words."""

        return self._dictionary is not None

    def ignore_for_session(self, word: str) -> None:
        """Accept one word for the lifetime of the Enchant dictionary object."""

        if self._dictionary is not None:
            self._dictionary.add_to_session(word)

    def supports_persistent_add(self) -> bool:
        """Return whether the loaded dictionary supports personal word lists."""

        return self._dictionary is not None

    def add_to_dictionary(self, word: str) -> bool:
        """Add one word to the Enchant personal dictionary."""

        if self._dictionary is None:
            return False
        self._dictionary.add(word)
        return True


__all__ = ["EnchantSpellCheckGateway"]
