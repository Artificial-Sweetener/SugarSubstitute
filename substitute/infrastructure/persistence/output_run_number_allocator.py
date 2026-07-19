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

"""Allocate generation output run numbers from rendered output files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

from substitute.domain.generation import (
    DEFAULT_OUTPUT_PATH_PATTERN,
    OutputPreferences,
    OutputRunBucket,
)

_TOKEN_RE = re.compile(r"\{([^{}]+)\}")
_PATH_SEPARATOR_RE = re.compile(r"[\\/]+")
_RUN_PATTERN = re.compile(r"^\d+$")
_SUPPORTED_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp"})


class OutputPatternPreferenceProvider(Protocol):
    """Provide the active output organization pattern."""

    def load_preferences(self) -> OutputPreferences:
        """Return normalized output preferences."""


class FileOutputRunNumberAllocator:
    """Allocate output run numbers from files already present in the bucket."""

    def __init__(
        self,
        output_preferences: OutputPatternPreferenceProvider | None = None,
        *,
        path_pattern: str | None = None,
    ) -> None:
        """Store active-pattern access for filesystem run scans."""

        self._output_preferences = output_preferences
        self._path_pattern = path_pattern

    def allocate_output_run_number(
        self,
        *,
        bucket: OutputRunBucket,
    ) -> int:
        """Return the next output number for a resolved output bucket."""

        return (
            self._max_existing_run_number(bucket.directory, self._active_pattern()) + 1
        )

    def _active_pattern(self) -> str:
        """Return the currently configured output path pattern."""

        if self._output_preferences is not None:
            return self._output_preferences.load_preferences().organization.path_pattern
        return self._path_pattern or DEFAULT_OUTPUT_PATH_PATTERN

    def _max_existing_run_number(
        self, bucket_directory: Path, path_pattern: str
    ) -> int:
        """Return the largest rendered run number found below one bucket."""

        bucket = Path(bucket_directory)
        if not bucket.is_dir():
            return 0
        pattern = _RunPattern.from_output_path_pattern(path_pattern)
        return max(pattern.iter_run_numbers(bucket), default=0)


class _RunPattern:
    """Match run numbers in paths relative to a resolved run bucket."""

    def __init__(
        self,
        *,
        component_expressions: tuple[re.Pattern[str], ...],
    ) -> None:
        """Store relative component expressions from the bucket boundary."""

        self._component_expressions = component_expressions

    @classmethod
    def from_output_path_pattern(cls, path_pattern: str) -> _RunPattern:
        """Build a run matcher aligned with output bucket resolution."""

        parts = _split_path_pattern(path_pattern)
        if not parts:
            return cls(
                component_expressions=(re.compile(r"(?P<run>\d+)"),),
            )
        filename_pattern = parts[-1]
        if "{run}" in filename_pattern:
            return cls(
                component_expressions=(_compile_component(filename_pattern),),
            )
        for index, component in enumerate(parts[:-1]):
            if "{run}" in component:
                return cls(
                    component_expressions=tuple(
                        _compile_component(part) for part in parts[index:]
                    ),
                )
        return cls(
            component_expressions=(re.compile(r"(?P<run>\d+)"),),
        )

    def iter_run_numbers(self, bucket: Path) -> tuple[int, ...]:
        """Return run numbers from supported image files under one bucket."""

        numbers: list[int] = []
        for path in bucket.rglob("*"):
            if (
                not path.is_file()
                or path.suffix.casefold() not in _SUPPORTED_IMAGE_SUFFIXES
            ):
                continue
            relative_parts = self._relative_match_parts(bucket, path)
            if relative_parts is None:
                continue
            number = self._number_from_parts(relative_parts)
            if number is not None:
                numbers.append(number)
        return tuple(numbers)

    def _relative_match_parts(
        self,
        bucket: Path,
        path: Path,
    ) -> tuple[str, ...] | None:
        """Return relative path parts shaped for the compiled expressions."""

        try:
            relative = path.relative_to(bucket)
        except ValueError:
            return None
        parts = relative.parts
        if len(parts) != len(self._component_expressions):
            return None
        return (*parts[:-1], path.stem)

    def _number_from_parts(self, parts: tuple[str, ...]) -> int | None:
        """Extract the run number when every relative component matches."""

        if len(parts) != len(self._component_expressions):
            return None
        run_text = ""
        for part, expression in zip(parts, self._component_expressions, strict=True):
            match = expression.fullmatch(part)
            if match is None:
                return None
            if "run" in match.groupdict():
                run_text = match.group("run")
        if not run_text or _RUN_PATTERN.fullmatch(run_text) is None:
            return None
        return int(run_text)


def _split_path_pattern(path_pattern: str) -> tuple[str, ...]:
    """Split a relative output path pattern into non-empty components."""

    normalized = path_pattern.strip().rstrip("\\/")
    return tuple(part for part in _PATH_SEPARATOR_RE.split(normalized) if part)


def _compile_component(component_pattern: str) -> re.Pattern[str]:
    """Compile one rendered path component pattern with a named run capture."""

    expression_parts: list[str] = []
    cursor = 0
    for match in _TOKEN_RE.finditer(component_pattern):
        expression_parts.append(re.escape(component_pattern[cursor : match.start()]))
        token_name = match.group(1)
        if token_name == "run":
            expression_parts.append(r"(?P<run>\d+)")
        else:
            expression_parts.append(r".+?")
        cursor = match.end()
    expression_parts.append(re.escape(component_pattern[cursor:]))
    return re.compile(f"^{''.join(expression_parts)}$", re.IGNORECASE)


__all__ = ["FileOutputRunNumberAllocator", "OutputPatternPreferenceProvider"]
