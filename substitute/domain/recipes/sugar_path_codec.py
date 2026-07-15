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

"""Encode and decode Sugar DSL identifiers and dotted paths."""

from __future__ import annotations


class SugarPathCodec:
    """Own identifier quoting and dotted-path tokenization for Sugar scripts."""

    def encode_segment(self, segment: str) -> str:
        """Return an identifier or escaped string token for one path segment."""

        if segment.replace("_", "").isalnum():
            return segment
        escaped = (
            segment.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\r", "\\r")
            .replace("\n", "\\n")
            .replace("\t", "\\t")
        )
        return f'"{escaped}"'

    def split(self, source: str) -> list[str]:
        """Split a dotted path while decoding escaped quoted segments."""

        parts: list[str] = []
        current: list[str] = []
        in_quotes = False
        escaped = False
        for character in source.strip():
            if escaped:
                current.append(self._decode_escape(character))
                escaped = False
                continue
            if character == "\\" and in_quotes:
                escaped = True
                continue
            if character == '"':
                in_quotes = not in_quotes
                continue
            if character == "." and not in_quotes:
                parts.append("".join(current).strip())
                current = []
                continue
            current.append(character)
        if escaped:
            current.append("\\")
        parts.append("".join(current).strip())
        return parts

    def _decode_escape(self, character: str) -> str:
        """Decode the escape sequences recognized by the Sugar lexer."""

        return {
            "n": "\n",
            "r": "\r",
            "t": "\t",
            "\\": "\\",
            '"': '"',
            "'": "'",
        }.get(character, character)


__all__ = ["SugarPathCodec"]
