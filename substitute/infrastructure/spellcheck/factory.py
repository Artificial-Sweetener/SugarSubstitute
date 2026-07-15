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

"""Select the platform spellcheck gateway for prompt editor spellcheck."""

from __future__ import annotations

import locale
import sys
import ctypes

from substitute.application.ports import SpellCheckGateway
from substitute.shared.logging.logger import get_logger, log_info, log_warning

from .disabled_spellcheck_gateway import DisabledSpellCheckGateway

_LOGGER = get_logger("infrastructure.spellcheck.factory")


def default_spellcheck_language_tag() -> str:
    """Return the best initial spellcheck language tag for this system."""

    if sys.platform == "win32":
        return _windows_default_language_tag()
    language, _encoding = locale.getlocale()
    if _language_tag_looks_portable(language):
        return language.strip()
    deprecated_language, _deprecated_encoding = locale.getdefaultlocale()
    if _language_tag_looks_portable(deprecated_language):
        return deprecated_language.strip()
    return "en_US"


def _windows_default_language_tag() -> str:
    """Return the Windows user locale as a BCP47-style tag."""

    buffer = ctypes.create_unicode_buffer(85)
    try:
        length = ctypes.windll.kernel32.GetUserDefaultLocaleName(buffer, len(buffer))
    except Exception:
        length = 0
    if length > 0 and buffer.value.strip():
        return buffer.value.strip()
    return "en-US"


def _language_tag_looks_portable(language: object) -> bool:
    """Return whether a locale string resembles a language-region tag."""

    if not isinstance(language, str):
        return False
    normalized = language.strip()
    if not normalized:
        return False
    separator = "-" if "-" in normalized else "_"
    parts = normalized.split(separator)
    return len(parts) >= 2 and len(parts[0]) == 2 and parts[0].isalpha()


def build_spellcheck_gateway(
    *,
    enabled: bool,
    language_tag: str | None = None,
) -> SpellCheckGateway:
    """Return the configured platform spellcheck gateway."""

    resolved_language_tag = language_tag or default_spellcheck_language_tag()
    if not enabled:
        return DisabledSpellCheckGateway("Prompt spellcheck is disabled in settings.")
    gateway = _platform_gateway(resolved_language_tag)
    log_info(
        _LOGGER,
        "Selected prompt spellcheck backend",
        platform=sys.platform,
        language_tag=resolved_language_tag,
        backend=type(gateway).__name__,
        available=gateway.is_available(),
        reason=gateway.availability_reason() or "",
    )
    return gateway


def _platform_gateway(language_tag: str) -> SpellCheckGateway:
    """Create the platform-preferred gateway without import-time platform coupling."""

    try:
        if sys.platform == "win32":
            from .windows_spellcheck_gateway import WindowsSpellCheckGateway

            return WindowsSpellCheckGateway(language_tag=language_tag)
        if sys.platform == "darwin":
            from .macos_spellcheck_gateway import MacOSSpellCheckGateway

            gateway = MacOSSpellCheckGateway(language_tag=language_tag)
            if gateway.is_available():
                return gateway
            log_warning(
                _LOGGER,
                "macOS native spellcheck unavailable; trying Enchant fallback",
                language_tag=language_tag,
                reason=gateway.availability_reason() or "",
            )
        from .enchant_gateway import EnchantSpellCheckGateway

        return EnchantSpellCheckGateway(language_tag=language_tag)
    except Exception as error:
        return DisabledSpellCheckGateway(
            f"Spellcheck backend initialization failed: {error!r}."
        )


__all__ = ["build_spellcheck_gateway", "default_spellcheck_language_tag"]
