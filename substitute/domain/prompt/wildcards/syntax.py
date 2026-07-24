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

"""Define configurable prompt wildcard activator syntax."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PromptWildcardActivatorStyle(str, Enum):
    """Identify supported wildcard wrapper styles."""

    CURLY = "curly"
    DOUBLE_UNDERSCORE = "double_underscore"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class PromptWildcardDelimiter:
    """Describe one validated wildcard wrapper pair."""

    prefix: str
    suffix: str


@dataclass(frozen=True, slots=True)
class PromptWildcardSyntaxProfile:
    """Capture wildcard delimiter settings used by parser and resolver."""

    activator_style: PromptWildcardActivatorStyle = PromptWildcardActivatorStyle.CURLY
    custom_prefix: str = ""
    custom_suffix: str = ""
    also_recognize_curly: bool = True

    @classmethod
    def default(cls) -> "PromptWildcardSyntaxProfile":
        """Return the compatibility profile for existing curly-brace prompts."""

        return cls()

    @classmethod
    def double_underscore(cls) -> "PromptWildcardSyntaxProfile":
        """Return the built-in double-underscore wildcard profile."""

        return cls(
            activator_style=PromptWildcardActivatorStyle.DOUBLE_UNDERSCORE,
            also_recognize_curly=True,
        )

    @classmethod
    def custom(
        cls,
        *,
        prefix: str,
        suffix: str,
        also_recognize_curly: bool = True,
    ) -> "PromptWildcardSyntaxProfile":
        """Return a validated custom wildcard profile."""

        validate_custom_wildcard_delimiters(prefix, suffix)
        return cls(
            activator_style=PromptWildcardActivatorStyle.CUSTOM,
            custom_prefix=prefix,
            custom_suffix=suffix,
            also_recognize_curly=also_recognize_curly,
        )

    def delimiters(self) -> tuple[PromptWildcardDelimiter, ...]:
        """Return active wildcard delimiter pairs in matching priority order."""

        delimiters: list[PromptWildcardDelimiter] = []
        if self.activator_style is PromptWildcardActivatorStyle.CURLY:
            delimiters.append(PromptWildcardDelimiter("{", "}"))
        elif self.activator_style is PromptWildcardActivatorStyle.DOUBLE_UNDERSCORE:
            delimiters.append(PromptWildcardDelimiter("__", "__"))
        else:
            validate_custom_wildcard_delimiters(self.custom_prefix, self.custom_suffix)
            delimiters.append(
                PromptWildcardDelimiter(self.custom_prefix, self.custom_suffix)
            )

        if (
            self.also_recognize_curly
            and self.activator_style is not PromptWildcardActivatorStyle.CURLY
        ):
            delimiters.append(PromptWildcardDelimiter("{", "}"))
        return tuple(delimiters)


def validate_custom_wildcard_delimiters(prefix: str, suffix: str) -> None:
    """Reject custom wildcard wrappers that conflict with prompt syntax."""

    _validate_custom_delimiter_part(prefix, "prefix")
    _validate_custom_delimiter_part(suffix, "suffix")
    if prefix == "<" and suffix == ">":
        raise ValueError("Wildcard delimiters must not conflict with LoRA syntax.")
    if prefix == "(" and suffix == ")":
        raise ValueError("Wildcard delimiters must not conflict with emphasis syntax.")
    if "{" in prefix or "}" in prefix or "{" in suffix or "}" in suffix:
        raise ValueError("Custom wildcard delimiters must not contain braces.")


def _validate_custom_delimiter_part(value: str, label: str) -> None:
    """Validate one side of a custom wildcard wrapper."""

    if not value:
        raise ValueError(f"Wildcard {label} must not be empty.")
    if len(value) > 8:
        raise ValueError(f"Wildcard {label} must be 8 characters or fewer.")
    if any(character.isspace() for character in value):
        raise ValueError(f"Wildcard {label} must not contain whitespace.")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"Wildcard {label} must not contain control characters.")
    if any(character in value for character in ("'", '"', "/", "\\")):
        raise ValueError(
            f"Wildcard {label} must not contain quotes or path separators."
        )
    if value.isalnum():
        raise ValueError(f"Wildcard {label} must include punctuation.")


__all__ = [
    "PromptWildcardActivatorStyle",
    "PromptWildcardDelimiter",
    "PromptWildcardSyntaxProfile",
    "validate_custom_wildcard_delimiters",
]
