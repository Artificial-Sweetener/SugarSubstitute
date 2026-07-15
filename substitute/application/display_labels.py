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

"""Format machine-oriented identifiers into stable user-facing labels."""

from __future__ import annotations

from typing import Final

_LABEL_OVERRIDES: Final[dict[str, str]] = {
    "sampler_name": "Sampler",
    "scheduler": "Scheduler",
    "cfg": "CFG",
    "ksampler": "KSampler",
    "vectorscopecc": "VectorscopeCC",
}

_ACRONYM_OVERRIDES: Final[dict[str, str]] = {
    "cfg": "CFG",
    "vae": "VAE",
    "lora": "LoRA",
}

_MINOR_WORDS: Final[frozenset[str]] = frozenset(
    {
        "a",
        "above",
        "about",
        "across",
        "after",
        "against",
        "along",
        "amid",
        "among",
        "an",
        "and",
        "around",
        "as",
        "at",
        "before",
        "behind",
        "below",
        "beneath",
        "beside",
        "between",
        "beyond",
        "but",
        "by",
        "because",
        "despite",
        "down",
        "during",
        "except",
        "for",
        "from",
        "in",
        "inside",
        "into",
        "near",
        "nor",
        "of",
        "off",
        "on",
        "onto",
        "or",
        "out",
        "over",
        "past",
        "per",
        "since",
        "so",
        "than",
        "the",
        "through",
        "till",
        "to",
        "under",
        "until",
        "up",
        "upon",
        "versus",
        "via",
        "with",
        "within",
        "without",
        "yet",
    }
)


def beautify_label(key: str) -> str:
    """Return the user-facing label for a machine-oriented key or cube alias."""

    override_key = key.lower().replace(" ", "_")
    if override_key in _LABEL_OVERRIDES:
        return _LABEL_OVERRIDES[override_key]

    prefix, body = _split_preserved_slash_prefix(key)
    if prefix:
        return f"{prefix}{_beautify_label_body(body)}"
    return _beautify_label_body(body)


def _split_preserved_slash_prefix(text: str) -> tuple[str, str]:
    """Split a non-empty leading slash prefix from a cube alias."""

    slash_index = text.find("/")
    if slash_index <= 0 or slash_index >= len(text) - 1:
        return "", text
    return text[: slash_index + 1], text[slash_index + 1 :]


def _beautify_label_body(text: str) -> str:
    """Title-case one label body without considering slash prefixes."""

    words = text.replace("_", " ").split()
    if not words:
        return ""

    formatted_words: list[str] = []
    last_index = len(words) - 1
    for index, word in enumerate(words):
        lower_word = word.lower()
        if index == 0 or index == last_index or lower_word not in _MINOR_WORDS:
            formatted_words.append(_format_title_word(word))
            continue
        formatted_words.append(lower_word)
    return " ".join(formatted_words)


def _format_title_word(word: str) -> str:
    """Return one significant word using project label capitalization rules."""

    lower_word = word.lower()
    if lower_word in _ACRONYM_OVERRIDES:
        return _ACRONYM_OVERRIDES[lower_word]
    if word.isupper() and len(word) > 1:
        return word
    if word.startswith("/") and len(word) > 1:
        return f"/{word[1:].capitalize()}"
    return word.capitalize()
