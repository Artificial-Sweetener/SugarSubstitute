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

"""Build deterministic output-image names for workflow-specific save paths."""

from __future__ import annotations

import glob
import os
import re
import threading
from pathlib import Path

from sugarsubstitute_shared.windows_long_paths import operational_path

_TOKEN_RE = re.compile(r"\{([^{}]+)\}")
_PATH_SEPARATOR_RE = re.compile(r"[\\/]+")
_UNSAFE_COMPONENT_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_WHITESPACE_RE = re.compile(r"\s+")
_SUPPORTED_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp"})
_FOLDER_IMAGE_NUMBER_LOCK = threading.Lock()
_RESERVED_FOLDER_IMAGE_NUMBERS: dict[str, set[int]] = {}


def get_next_image_counter(
    workflow_tab_name: str,
    output_dir: Path | str,
) -> int:
    """Return next 3-digit image index for a workflow-specific output filename prefix."""

    tab_name_for_file = workflow_tab_name.replace(" ", "_").lower()
    directory = operational_path(output_dir)
    pattern = os.path.join(
        os.fspath(directory),
        f"[0-9][0-9][0-9]_{tab_name_for_file}_*.png",
    )
    existing_files = glob.glob(pattern)
    max_counter = 0
    for filename in existing_files:
        matched = re.match(
            r"([0-9]{3})_" + re.escape(tab_name_for_file) + r"_",
            os.path.basename(filename),
        )
        if matched:
            value = int(matched.group(1))
            if value > max_counter:
                max_counter = value
    return max_counter + 1


def get_next_bucket_run_number(output_dir: Path | str) -> int:
    """Return next 3-digit image index for a bucket-local output filename prefix."""

    directory = operational_path(output_dir)
    pattern = os.path.join(os.fspath(directory), "*.png")
    existing_files = glob.glob(pattern)
    max_counter = 0
    for filename in existing_files:
        matched = re.match(r"([0-9]{3})(?:_|\.|$)", os.path.basename(filename))
        if matched:
            value = int(matched.group(1))
            if value > max_counter:
                max_counter = value
    return max_counter + 1


def get_next_folder_image_number(
    output_dir: Path | str,
    path_pattern: str,
) -> int:
    """Return the next folder-local number for a filename `{image#}` token."""

    directory = operational_path(output_dir)
    key = str(directory.resolve()).replace("\\", "/").casefold()
    expression = _compile_folder_image_filename_pattern(path_pattern)
    with _FOLDER_IMAGE_NUMBER_LOCK:
        existing_numbers = tuple(_iter_folder_image_numbers(directory, expression))
        reserved_numbers = _RESERVED_FOLDER_IMAGE_NUMBERS.setdefault(key, set())
        next_number = max((*existing_numbers, *reserved_numbers), default=0) + 1
        reserved_numbers.add(next_number)
        return next_number


def _iter_folder_image_numbers(
    directory: Path,
    expression: re.Pattern[str],
) -> tuple[int, ...]:
    """Return matching `{image#}` numbers from supported images in one folder."""

    if not directory.is_dir():
        return ()
    numbers: list[int] = []
    for path in directory.iterdir():
        if (
            not path.is_file()
            or path.suffix.casefold() not in _SUPPORTED_IMAGE_SUFFIXES
        ):
            continue
        match = expression.fullmatch(path.stem)
        if match is None:
            continue
        number_text = match.group("image")
        if number_text.isdigit():
            numbers.append(int(number_text))
    return tuple(numbers)


def _compile_folder_image_filename_pattern(path_pattern: str) -> re.Pattern[str]:
    """Compile the filename component of an output path pattern with `{image#}`."""

    filename_pattern = _filename_component_pattern(path_pattern)
    expression_parts: list[str] = []
    cursor = 0
    for match in _TOKEN_RE.finditer(filename_pattern):
        expression_parts.append(
            re.escape(
                _sanitize_filename_literal(filename_pattern[cursor : match.start()])
            )
        )
        token_name = match.group(1)
        if token_name == "image#":
            expression_parts.append(r"(?P<image>\d+)")
        else:
            expression_parts.append(r".+?")
        cursor = match.end()
    expression_parts.append(
        re.escape(_sanitize_filename_literal(filename_pattern[cursor:]))
    )
    return re.compile(f"^{''.join(expression_parts)}$", re.IGNORECASE)


def _filename_component_pattern(path_pattern: str) -> str:
    """Return the filename stem component from one relative output pattern."""

    normalized = path_pattern.strip().rstrip("\\/")
    parts = tuple(part for part in _PATH_SEPARATOR_RE.split(normalized) if part)
    return parts[-1] if parts else ""


def _sanitize_filename_literal(value: str) -> str:
    """Return the renderer-compatible sanitized form of one filename literal."""

    text = value.lower()
    text = _UNSAFE_COMPONENT_RE.sub("_", text)
    text = _WHITESPACE_RE.sub("_", text)
    return re.sub(r"_+", "_", text)


__all__ = [
    "get_next_image_counter",
    "get_next_bucket_run_number",
    "get_next_folder_image_number",
]
