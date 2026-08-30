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

"""Resolve operating-system UI languages without importing Qt."""

from __future__ import annotations

import ctypes
import locale
import os


_MUI_LANGUAGE_NAME = 0x8


def system_ui_languages() -> tuple[str, ...]:
    """Return ordered UI-language candidates for splash-time localization."""

    candidates = [
        *_environment_language_candidates(),
        *_windows_ui_language_candidates(),
    ]
    active_locale, _encoding = locale.getlocale()
    if active_locale:
        candidates.append(active_locale)
    return _deduplicate(candidates)


def _environment_language_candidates() -> tuple[str, ...]:
    """Return POSIX locale preferences in their standard precedence order."""

    language = os.environ.get("LANGUAGE", "")
    candidates = [value for value in language.split(":") if value]
    for variable_name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(variable_name)
        if value:
            candidates.append(value)
    return tuple(candidates)


def _windows_ui_language_candidates() -> tuple[str, ...]:
    """Return Windows preferred UI languages through the kernel locale API."""

    if os.name != "nt":
        return ()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_languages = kernel32.GetUserPreferredUILanguages
    language_count = ctypes.c_ulong()
    buffer_size = ctypes.c_ulong()
    if not get_languages(
        _MUI_LANGUAGE_NAME,
        ctypes.byref(language_count),
        None,
        ctypes.byref(buffer_size),
    ):
        return ()
    buffer = ctypes.create_unicode_buffer(buffer_size.value)
    if not get_languages(
        _MUI_LANGUAGE_NAME,
        ctypes.byref(language_count),
        buffer,
        ctypes.byref(buffer_size),
    ):
        return ()
    buffer_value = "".join(buffer[: buffer_size.value])
    return tuple(value for value in buffer_value.split("\0") if value)


def _deduplicate(candidates: list[str]) -> tuple[str, ...]:
    """Preserve candidate order while removing equivalent repeated values."""

    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = candidate.strip()
        identity = normalized.casefold()
        if not normalized or identity in seen:
            continue
        seen.add(identity)
        result.append(normalized)
    return tuple(result)


__all__ = ["system_ui_languages"]
