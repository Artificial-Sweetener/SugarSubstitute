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

"""Discover same-folder output images related to a loaded recipe PNG."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Protocol

from substitute.domain.generation import (
    OutputOrganizationPreferences,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_warning,
    log_debug,
)

_LOGGER = get_logger("application.generation.recipe_output_sibling_discovery")
_TOKEN_RE = re.compile(r"\{([^{}]+)\}")
_PATH_SEPARATOR_RE = re.compile(r"[\\/]+")
_UNSAFE_COMPONENT_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_WHITESPACE_RE = re.compile(r"\s+")
_SUPPORTED_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp"})
_SUPPORTED_PATTERN_TOKEN_SETS = frozenset(
    {
        frozenset({"run", "workflow", "source"}),
        frozenset({"run", "cube#", "workflow", "source"}),
    }
)


class OutputOrganizationPreferenceProvider(Protocol):
    """Describe output naming preference access used for filename fallback."""

    def load_preferences(self) -> OutputOrganizationPreferences:
        """Load normalized output organization preferences."""


@dataclass(frozen=True)
class RecipeOutputSibling:
    """Describe one output image to restore with a loaded recipe PNG."""

    path: Path
    source_key: str
    source_label: str
    sequence: int
    node_title: str | None = None
    scene_run_id: str | None = None
    scene_key: str | None = None
    scene_title: str | None = None
    scene_order: int | None = None
    scene_count: int | None = None


@dataclass(frozen=True)
class RecipeOutputSiblingDiscoveryResult:
    """Describe sibling restoration candidates and the strategy that found them."""

    siblings: tuple[RecipeOutputSibling, ...]
    strategy: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _CompiledFilenamePattern:
    """Carry a reverse matcher for a supported output filename pattern."""

    expression: re.Pattern[str]
    reason: str = ""


class RecipeOutputSiblingDiscoveryService:
    """Find same-folder output images related to a loaded recipe PNG."""

    def __init__(
        self,
        *,
        output_preferences: OutputOrganizationPreferenceProvider,
    ) -> None:
        """Store output naming collaborators used for sibling discovery."""

        self._output_preferences = output_preferences

    def discover_for_recipe_png(
        self,
        selected_path: Path,
        *,
        workflow_name: str,
    ) -> RecipeOutputSiblingDiscoveryResult:
        """Return same-folder output siblings for one selected recipe PNG."""

        resolved_selected_path = Path(selected_path)
        log_debug(
            _LOGGER,
            "Recipe output sibling discovery started",
            selected_path=str(resolved_selected_path),
            selected_folder=str(resolved_selected_path.parent),
            workflow_name=workflow_name,
        )

        return self._discover_from_same_folder_pattern(
            resolved_selected_path,
            workflow_name=workflow_name,
        )

    def _discover_from_same_folder_pattern(
        self,
        selected_path: Path,
        *,
        workflow_name: str,
    ) -> RecipeOutputSiblingDiscoveryResult:
        """Return same-folder siblings by reverse-matching supported filename patterns."""

        preferences = self._output_preferences.load_preferences()
        workflow_token = _sanitize_filename_component(workflow_name)
        compiled = _compile_filename_pattern(
            preferences.path_pattern,
            workflow_token=workflow_token,
        )
        if compiled.reason:
            log_debug(
                _LOGGER,
                "Recipe output sibling pattern fallback skipped",
                selected_path=str(selected_path),
                output_pattern=preferences.path_pattern,
                reason=compiled.reason,
            )
            return RecipeOutputSiblingDiscoveryResult(
                siblings=(),
                strategy="same_folder_pattern",
                warnings=(compiled.reason,),
            )

        selected_match = compiled.expression.fullmatch(selected_path.stem)
        if selected_match is None:
            reason = "selected_filename_does_not_match_pattern"
            log_debug(
                _LOGGER,
                "Recipe output sibling pattern fallback skipped",
                selected_path=str(selected_path),
                output_pattern=preferences.path_pattern,
                reason=reason,
            )
            return RecipeOutputSiblingDiscoveryResult(
                siblings=(),
                strategy="same_folder_pattern",
                warnings=(reason,),
            )

        selected_run = selected_match.group("run")
        siblings = self._same_folder_pattern_siblings(
            selected_path,
            expression=compiled.expression,
            selected_run=selected_run,
        )
        log_debug(
            _LOGGER,
            "Recipe output sibling pattern fallback completed",
            selected_path=str(selected_path),
            output_pattern=preferences.path_pattern,
            candidate_count=len(siblings),
        )
        return RecipeOutputSiblingDiscoveryResult(
            siblings=siblings,
            strategy="same_folder_pattern",
        )

    def _same_folder_pattern_siblings(
        self,
        selected_path: Path,
        *,
        expression: re.Pattern[str],
        selected_run: str,
    ) -> tuple[RecipeOutputSibling, ...]:
        """Return matching same-folder image files in deterministic filename order."""

        try:
            candidates = tuple(
                sorted(
                    selected_path.parent.iterdir(),
                    key=lambda path: path.name.casefold(),
                )
            )
        except OSError as error:
            log_warning(
                _LOGGER,
                "Recipe output sibling folder scan failed",
                selected_path=str(selected_path),
                selected_folder=str(selected_path.parent),
                error=error,
            )
            return ()

        siblings: list[RecipeOutputSibling] = []
        for candidate in candidates:
            if not _path_is_supported_image(candidate):
                continue
            if candidate.suffix.casefold() != selected_path.suffix.casefold():
                continue
            match = expression.fullmatch(candidate.stem)
            if match is None or match.group("run") != selected_run:
                continue
            source = match.group("source")
            siblings.append(
                RecipeOutputSibling(
                    path=candidate,
                    source_key=source,
                    source_label=_source_label_from_token(source),
                    sequence=len(siblings) + 1,
                    node_title=_source_label_from_token(source),
                )
            )
        return self._deduplicate_siblings(siblings)

    @staticmethod
    def _deduplicate_siblings(
        siblings: Iterable[RecipeOutputSibling],
    ) -> tuple[RecipeOutputSibling, ...]:
        """Return siblings with duplicate paths removed while preserving order."""

        seen_paths: set[str] = set()
        deduplicated: list[RecipeOutputSibling] = []
        for sibling in siblings:
            key = _normalized_path_key(sibling.path)
            if key in seen_paths:
                continue
            seen_paths.add(key)
            deduplicated.append(sibling)
        return tuple(deduplicated)


def _compile_filename_pattern(
    path_pattern: str,
    *,
    workflow_token: str,
) -> _CompiledFilenamePattern:
    """Compile a supported output filename pattern into a reverse matcher."""

    filename_pattern = _filename_component_pattern(path_pattern)
    tokens = tuple(_TOKEN_RE.findall(filename_pattern))
    token_set = frozenset(tokens)
    if token_set not in _SUPPORTED_PATTERN_TOKEN_SETS:
        return _CompiledFilenamePattern(
            expression=re.compile("$^"),
            reason="unsupported_pattern_tokens",
        )
    if len(tokens) != len(token_set):
        return _CompiledFilenamePattern(
            expression=re.compile("$^"),
            reason="repeated_pattern_tokens",
        )
    if re.search(r"\}\{", filename_pattern):
        return _CompiledFilenamePattern(
            expression=re.compile("$^"),
            reason="adjacent_pattern_tokens",
        )

    expression_parts: list[str] = []
    cursor = 0
    for match in _TOKEN_RE.finditer(filename_pattern):
        expression_parts.append(re.escape(filename_pattern[cursor : match.start()]))
        token_name = match.group(1)
        if token_name == "workflow":
            expression_parts.append(re.escape(workflow_token))
        elif token_name == "run":
            expression_parts.append(r"(?P<run>.+?)")
        elif token_name == "cube#":
            expression_parts.append(r".+?")
        elif token_name == "source":
            expression_parts.append(r"(?P<source>.+?)")
        cursor = match.end()
    expression_parts.append(re.escape(filename_pattern[cursor:]))
    return _CompiledFilenamePattern(
        expression=re.compile(f"^{''.join(expression_parts)}$", re.IGNORECASE),
    )


def _filename_component_pattern(path_pattern: str) -> str:
    """Return the final filename stem pattern from an output path pattern."""

    normalized = path_pattern.strip().rstrip("\\/")
    parts = tuple(part for part in _PATH_SEPARATOR_RE.split(normalized) if part)
    return parts[-1] if parts else ""


def _path_is_supported_image(path: Path) -> bool:
    """Return whether a path is an existing supported image file."""

    return path.is_file() and path.suffix.casefold() in _SUPPORTED_IMAGE_SUFFIXES


def _sanitize_filename_component(value: object) -> str:
    """Match output filename token sanitization used by output path rendering."""

    text = str(value).strip().casefold()
    text = _UNSAFE_COMPONENT_RE.sub("_", text)
    text = _WHITESPACE_RE.sub("_", text)
    return re.sub(r"_+", "_", text).strip(" ._")


def _source_label_from_token(source: str) -> str:
    """Return a readable fallback label from a filename source token."""

    label = source.replace("_", " ").strip()
    return label.title() if label else "Output"


def _normalized_path_key(path: Path) -> str:
    """Return a Windows-tolerant lookup key for output path comparisons."""

    return str(path).replace("\\", "/").casefold()


__all__ = [
    "OutputOrganizationPreferenceProvider",
    "RecipeOutputSibling",
    "RecipeOutputSiblingDiscoveryResult",
    "RecipeOutputSiblingDiscoveryService",
]
