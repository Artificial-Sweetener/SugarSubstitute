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

"""Redact secrets and identifying path prefixes from user-copyable crash data."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import re


_SENSITIVE_NAME = re.compile(
    r"(?:api[-_]?key|access[-_]?token|auth(?:orization)?|password|secret)",
    re.IGNORECASE,
)
_INLINE_SECRET = re.compile(
    r"(?P<name>api[-_]?key|access[-_]?token|auth(?:orization)?|password|secret)"
    r"(?P<separator>\s*[:=]\s*)(?P<value>[^\s,;]+)",
    re.IGNORECASE,
)
_MAX_TEXT_CHARACTERS = 131_072


class CrashReportRedactor:
    """Sanitize diagnostic text while preserving actionable stack context."""

    def __init__(self, *, home: Path | None, install_root: Path | None) -> None:
        """Build deterministic replacements for known identifying roots."""

        replacements: list[tuple[str, str]] = []
        if home is not None:
            replacements.extend(_path_spellings(home, "<user-home>"))
        if install_root is not None:
            replacements.extend(_path_spellings(install_root, "<install-root>"))
        self._path_replacements = tuple(
            sorted(set(replacements), key=lambda item: len(item[0]), reverse=True)
        )

    def text(self, value: str) -> str:
        """Redact one bounded diagnostic text field."""

        redacted = value[:_MAX_TEXT_CHARACTERS]
        for source, replacement in self._path_replacements:
            redacted = re.sub(
                re.escape(source), replacement, redacted, flags=re.IGNORECASE
            )
        return _INLINE_SECRET.sub(
            lambda match: f"{match.group('name')}{match.group('separator')}<redacted>",
            redacted,
        )

    def arguments(self, arguments: Sequence[str]) -> tuple[str, ...]:
        """Redact sensitive option values and identifying paths from launch arguments."""

        sanitized: list[str] = []
        redact_next = False
        for argument in arguments:
            if redact_next:
                sanitized.append("<redacted>")
                redact_next = False
                continue
            option, separator, value = argument.partition("=")
            if option.startswith("-") and _SENSITIVE_NAME.search(option):
                if separator:
                    sanitized.append(f"{option}=<redacted>")
                else:
                    sanitized.append(option)
                    redact_next = True
                continue
            sanitized.append(
                self.text(argument if not separator else f"{option}={value}")
            )
        return tuple(sanitized)


def _path_spellings(path: Path, replacement: str) -> list[tuple[str, str]]:
    """Return native and slash-normalized spellings for one identifying path."""

    expanded = str(path.expanduser().resolve())
    return [
        (expanded, replacement),
        (expanded.replace("\\", "/"), replacement),
        (expanded.replace("/", "\\"), replacement),
    ]


__all__ = ["CrashReportRedactor"]
