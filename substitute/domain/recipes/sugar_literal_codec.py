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

"""Encode and decode scalar Sugar DSL values without losing recipe data."""

from __future__ import annotations

import json

from substitute.domain.common import JsonValue


class SugarLiteralCodec:
    """Own the textual representation of values embedded in Sugar scripts."""

    def encode(self, value: JsonValue) -> str:
        """Return an unambiguous Sugar literal for one persisted value."""

        if value is None:
            return "null"
        if isinstance(value, list):
            return "[]" if not value else json.dumps(value)
        if isinstance(value, str):
            return self._encode_string(value)
        if isinstance(value, bool):
            return str(value)
        return str(value)

    def decode_scalar(self, source: str) -> JsonValue:
        """Decode one non-multiline Sugar scalar used by recipe persistence."""

        if source in ("True", "False"):
            return source == "True"
        if source == "null":
            return None
        try:
            return int(source)
        except ValueError:
            try:
                return float(source)
            except ValueError:
                return self._decode_string_or_reference(source)

    def _encode_string(self, value: str) -> str:
        """Use readable multiline syntax only when its delimiter is lossless."""

        if self._can_use_triple_quoted_string(value):
            return f'"""{value}"""'
        return self._encode_quoted_string(value)

    def _can_use_triple_quoted_string(self, value: str) -> bool:
        """Return whether raw triple quotes can represent the value exactly."""

        return (
            "\n" in value
            and "\r" not in value
            and '"""' not in value
            and not value.endswith('"')
        )

    def _encode_quoted_string(self, value: str) -> str:
        """Escape syntax-significant characters supported by Sugar-DSL."""

        escaped = (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\r", "\\r")
            .replace("\n", "\\n")
            .replace("\t", "\\t")
        )
        return f'"{escaped}"'

    def _decode_string_or_reference(self, source: str) -> JsonValue:
        """Decode quoted strings while preserving existing permissive references."""

        if not (source.startswith('"') and source.endswith('"')):
            return source
        try:
            parsed = json.loads(source)
        except json.JSONDecodeError:
            return source[1:-1]
        return parsed if isinstance(parsed, str) else source[1:-1]


__all__ = ["SugarLiteralCodec"]
