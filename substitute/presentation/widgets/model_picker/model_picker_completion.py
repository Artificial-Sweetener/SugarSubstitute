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

"""Build model-picker inline-completion candidates from picker item metadata."""

from __future__ import annotations

from pathlib import PurePosixPath

from substitute.presentation.widgets.inline_completion import (
    InlineCompletion,
    InlineCompletionChannel,
    inline_completion_matches,
    inline_completion_suffix,
)
from substitute.presentation.widgets.model_picker.model_picker_models import (
    ModelPickerItem,
)

_PATH_SEPARATOR_EQUIVALENCE = (frozenset({"/", "\\"}),)
_SUPPORTED_MODEL_EXTENSIONS = (".safetensors", ".ckpt", ".pt")
_MIN_FILENAME_SUBSTRING_QUERY_LENGTH = 3


def model_picker_inline_completion(
    *,
    query: str,
    item: ModelPickerItem | None,
) -> InlineCompletion | None:
    """Return the best display-only completion for one picker item and query."""

    typed_query = str(query)
    if item is None or not typed_query:
        return None
    if _contains_path_separator(typed_query):
        path_completion = _completion_for_candidate(
            channel="path",
            query=typed_query,
            candidate=_path_candidate_for_item(item, typed_query),
            equivalent_characters=_PATH_SEPARATOR_EQUIVALENCE,
        )
        if path_completion is not None:
            return path_completion

    filename_completion = _completion_for_candidate(
        channel="filename",
        query=typed_query,
        candidate=_filename_candidate_for_item(item),
    )
    if filename_completion is not None:
        return filename_completion
    filename_substring_completion = _substring_completion_for_candidate(
        channel="filename",
        query=typed_query,
        candidate=_filename_candidate_for_item(item),
    )
    if filename_substring_completion is not None:
        return filename_substring_completion

    return _completion_for_candidate(
        channel="friendly_name",
        query=typed_query,
        candidate=_friendly_name_candidate_for_item(item),
    )


def _completion_for_candidate(
    *,
    channel: InlineCompletionChannel,
    query: str,
    candidate: str,
    equivalent_characters: tuple[frozenset[str], ...] = (),
) -> InlineCompletion | None:
    """Return an inline completion when a query matches one candidate prefix."""

    if not inline_completion_matches(
        typed_text=query,
        candidate_text=candidate,
        equivalent_characters=equivalent_characters,
    ):
        return None
    return InlineCompletion(
        channel=channel,
        completed_text=candidate,
        suffix_text=inline_completion_suffix(
            typed_text=query,
            candidate_text=candidate,
            equivalent_characters=equivalent_characters,
        ),
    )


def _substring_completion_for_candidate(
    *,
    channel: InlineCompletionChannel,
    query: str,
    candidate: str,
) -> InlineCompletion | None:
    """Return a filename completion for substring search matches."""

    typed_query = str(query)
    if len(
        typed_query.strip()
    ) < _MIN_FILENAME_SUBSTRING_QUERY_LENGTH or _contains_path_separator(typed_query):
        return None
    match_index = candidate.casefold().find(typed_query.casefold())
    if match_index <= 0:
        return None
    matched_candidate = candidate[match_index:]
    return InlineCompletion(
        channel=channel,
        completed_text=matched_candidate,
        suffix_text=matched_candidate[len(typed_query) :],
    )


def _path_candidate_for_item(item: ModelPickerItem, query: str) -> str:
    """Return the extension-stripped path candidate in the user's separator style."""

    path = _normalized_model_path(item)
    path_without_extension = _strip_supported_model_extension(path)
    separator = "\\" if "\\" in query and "/" not in query else "/"
    if separator == "\\":
        return path_without_extension.replace("/", "\\")
    return path_without_extension


def _filename_candidate_for_item(item: ModelPickerItem) -> str:
    """Return the extension-stripped filename candidate for one picker item."""

    path = _normalized_model_path(item)
    return _strip_supported_model_extension(PurePosixPath(path).name)


def _friendly_name_candidate_for_item(item: ModelPickerItem) -> str:
    """Return the visible title-subtitle candidate for one picker item."""

    title = item.title.strip()
    subtitle = "" if item.subtitle is None else item.subtitle.strip()
    if title and subtitle:
        return f"{title} - {subtitle}"
    return title


def _normalized_model_path(item: ModelPickerItem) -> str:
    """Return the best available item path using POSIX separators."""

    source_path = item.relative_path.strip() or item.backend_value.strip()
    return source_path.replace("\\", "/")


def _strip_supported_model_extension(value: str) -> str:
    """Strip one supported model extension from the final path component."""

    lower_value = value.casefold()
    for extension in _SUPPORTED_MODEL_EXTENSIONS:
        if lower_value.endswith(extension):
            return value[: -len(extension)]
    return value


def _contains_path_separator(value: str) -> bool:
    """Return whether a query is shaped like a folder path."""

    return "/" in value or "\\" in value


__all__ = ["model_picker_inline_completion"]
