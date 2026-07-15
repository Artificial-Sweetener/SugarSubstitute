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

"""Adapt the Windows Spell Checking API to the spellcheck gateway contract."""

from __future__ import annotations

from ctypes import POINTER, c_int, c_ulong, c_wchar_p
from ctypes.wintypes import BOOL
from dataclasses import dataclass
from threading import local
from typing import Any

from comtypes import (  # type: ignore[import-untyped]
    CLSCTX_INPROC_SERVER,
    COMMETHOD,
    GUID,
    HRESULT,
    IUnknown,
    CoCreateInstance,
    CoInitialize,
)

_SPELL_CHECKER_FACTORY_CLSID = GUID("{7AB36653-1796-484B-BDFA-E74F1DB7C1DC}")


@dataclass(frozen=True, slots=True)
class _WindowsSpellCheckThreadState:
    """Store COM spellcheck objects owned by one initialized thread."""

    factory: Any
    checker: Any


class _ISpellingError(IUnknown):  # type: ignore[misc]
    """Represent the Windows spelling error COM interface."""

    _iid_ = GUID("{B7C82D61-FBE8-4B47-9B27-6C0D2E0DE0A3}")
    _methods_ = [
        COMMETHOD([], HRESULT, "get_StartIndex", (["out"], POINTER(c_ulong), "val")),
        COMMETHOD([], HRESULT, "get_Length", (["out"], POINTER(c_ulong), "val")),
        COMMETHOD(
            [],
            HRESULT,
            "get_CorrectiveAction",
            (["out"], POINTER(c_int), "val"),
        ),
        COMMETHOD([], HRESULT, "get_Replacement", (["out"], POINTER(c_wchar_p), "val")),
    ]


class _IEnumSpellingError(IUnknown):  # type: ignore[misc]
    """Represent the Windows spelling error enumerator COM interface."""

    _iid_ = GUID("{803E3BD4-2828-4410-8290-418D1D73C762}")
    _methods_ = [
        COMMETHOD(
            [], HRESULT, "Next", (["out"], POINTER(POINTER(_ISpellingError)), "val")
        )
    ]


class _IEnumString(IUnknown):  # type: ignore[misc]
    """Represent the COM string enumerator used for Windows suggestions."""

    _iid_ = GUID("{00000101-0000-0000-C000-000000000046}")
    _methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "Next",
            (["in"], c_ulong, "celt"),
            (["out"], POINTER(c_wchar_p), "rgelt"),
            (["out"], POINTER(c_ulong), "pceltFetched"),
        )
    ]


class _ISpellChecker(IUnknown):  # type: ignore[misc]
    """Represent the Windows spell checker COM interface."""

    _iid_ = GUID("{B6FD0B71-E2BC-4653-8D05-F197E412770B}")
    _methods_ = [
        COMMETHOD([], HRESULT, "get_LanguageTag", (["out"], POINTER(c_wchar_p), "val")),
        COMMETHOD(
            [],
            HRESULT,
            "Check",
            (["in"], c_wchar_p, "text"),
            (["out"], POINTER(POINTER(_IEnumSpellingError)), "val"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "Suggest",
            (["in"], c_wchar_p, "word"),
            (["out"], POINTER(POINTER(_IEnumString)), "val"),
        ),
        COMMETHOD([], HRESULT, "Add", (["in"], c_wchar_p, "word")),
        COMMETHOD([], HRESULT, "Ignore", (["in"], c_wchar_p, "word")),
        COMMETHOD(
            [],
            HRESULT,
            "AutoCorrect",
            (["in"], c_wchar_p, "from_word"),
            (["in"], c_wchar_p, "to_word"),
        ),
    ]


class _ISpellCheckerFactory(IUnknown):  # type: ignore[misc]
    """Represent the Windows spell checker factory COM interface."""

    _iid_ = GUID("{8E018A9D-2415-4677-BF08-794EA61F94BB}")
    _methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "get_SupportedLanguages",
            (["out"], POINTER(POINTER(_IEnumString)), "val"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "IsSupported",
            (["in"], c_wchar_p, "languageTag"),
            (["out"], POINTER(BOOL), "val"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "CreateSpellChecker",
            (["in"], c_wchar_p, "languageTag"),
            (["out"], POINTER(POINTER(_ISpellChecker)), "val"),
        ),
    ]


class WindowsSpellCheckGateway:
    """Use the native Windows spell checking COM API."""

    def __init__(self, *, language_tag: str) -> None:
        """Create an ISpellChecker for the configured BCP47 language tag."""

        self._language_tag = language_tag.replace("_", "-")
        self._thread_state = local()
        self._available = False
        self._reason: str | None = None
        try:
            self._checker_for_current_thread()
            self._available = True
        except ImportError:
            self._reason = "comtypes is not installed."
        except Exception as error:
            self._reason = f"Windows spellcheck initialization failed: {error!r}."

    def is_available(self) -> bool:
        """Return whether a Windows spell checker loaded successfully."""

        return self._available

    def availability_reason(self) -> str | None:
        """Return the Windows spellcheck unavailability reason."""

        return self._reason

    def check_word(self, word: str) -> bool:
        """Return whether Windows accepts one word."""

        if not self._available:
            return True
        checker = self._checker_for_current_thread()
        errors = checker.Check(word)
        return _collection_is_empty(errors)

    def suggest(self, word: str, *, limit: int = 8) -> tuple[str, ...]:
        """Return Windows suggestions for one rejected word."""

        if not self._available:
            return ()
        checker = self._checker_for_current_thread()
        return tuple(_collection_items(checker.Suggest(word)))[:limit]

    def supports_session_ignore(self) -> bool:
        """Return whether Windows session ignore is available."""

        if not self._available:
            return False
        return hasattr(self._checker_for_current_thread(), "Ignore")

    def ignore_for_session(self, word: str) -> None:
        """Ignore one word for the current Windows spellcheck session."""

        if self.supports_session_ignore():
            self._checker_for_current_thread().Ignore(word)

    def supports_persistent_add(self) -> bool:
        """Return whether Windows dictionary additions are available."""

        if not self._available:
            return False
        return hasattr(self._checker_for_current_thread(), "Add")

    def add_to_dictionary(self, word: str) -> bool:
        """Persist one word through the Windows spell checker."""

        if not self.supports_persistent_add():
            return False
        self._checker_for_current_thread().Add(word)
        return True

    def _checker_for_current_thread(self) -> Any:
        """Return an ISpellChecker created inside the calling COM apartment."""

        state = getattr(self._thread_state, "state", None)
        if isinstance(state, _WindowsSpellCheckThreadState):
            return state.checker
        CoInitialize()
        factory = CoCreateInstance(
            _SPELL_CHECKER_FACTORY_CLSID,
            interface=_ISpellCheckerFactory,
            clsctx=CLSCTX_INPROC_SERVER,
        )
        if not bool(factory.IsSupported(self._language_tag)):
            raise RuntimeError(
                f"Windows spellcheck has no dictionary for {self._language_tag}."
            )
        checker = factory.CreateSpellChecker(self._language_tag)
        setattr(
            self._thread_state,
            "state",
            _WindowsSpellCheckThreadState(factory=factory, checker=checker),
        )
        return checker


def _collection_is_empty(collection: Any) -> bool:
    """Return whether a COM string/error collection has no entries."""

    next_error = getattr(collection, "Next", None)
    if callable(next_error):
        return not bool(next_error())
    count = getattr(collection, "Count", None)
    if isinstance(count, int):
        return count == 0
    try:
        iterator = iter(collection)
    except TypeError:
        return False
    return next(iterator, None) is None


def _collection_items(collection: Any) -> tuple[str, ...]:
    """Return strings from a COM collection without assuming one wrapper shape."""

    next_item = getattr(collection, "Next", None)
    if callable(next_item):
        items: list[str] = []
        while True:
            value, fetched_count = next_item(1)
            if fetched_count == 0:
                break
            items.append(str(value))
        return tuple(items)
    try:
        return tuple(str(item) for item in collection)
    except TypeError:
        count = getattr(collection, "Count", 0)
        item = getattr(collection, "Item", None)
        if not isinstance(count, int) or item is None:
            return ()
        return tuple(str(item(index)) for index in range(count))


__all__ = ["WindowsSpellCheckGateway"]
