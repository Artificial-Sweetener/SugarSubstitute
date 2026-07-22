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

"""Render configured output path patterns safely."""

from __future__ import annotations

import re
from pathlib import Path

from substitute.domain.generation import (
    OutputPathRenderContext,
    OutputPathRenderResult,
    OutputRunBucket,
    SUPPORTED_OUTPUT_PATH_TOKEN_NAMES,
)
from substitute.shared.util.path_safety import ensure_within_root
from sugarsubstitute_shared.windows_long_paths import operational_path

_TOKEN_RE = re.compile(r"\{([^{}]+)\}")
_PATH_SEPARATOR_RE = re.compile(r"[\\/]+")
_UNSAFE_COMPONENT_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_WHITESPACE_RE = re.compile(r"\s+")
_COLLISION_LIMIT = 10_000
_TIME_TOKEN_NAMES = frozenset({"date", "time", "day"})


class OutputPathTemplateError(ValueError):
    """Represent invalid output path template or render context state."""


class OutputPathTemplateRenderer:
    """Render output organization templates into contained filesystem paths."""

    def validate_pattern(self, path_pattern: str) -> None:
        """Validate one relative output path pattern without rendering it."""

        self._validate_pattern(path_pattern)
        parts = self._split_path_pattern(path_pattern)
        if not parts:
            raise OutputPathTemplateError("Output pattern must include a filename.")

    def render_path(
        self,
        *,
        output_root: Path,
        path_pattern: str,
        context: OutputPathRenderContext,
        extension: str = "png",
        avoid_collisions: bool = True,
    ) -> OutputPathRenderResult:
        """Render one collision-safe output path under output_root."""

        self.validate_pattern(path_pattern)
        resolved_root = self._resolve_output_root(output_root)
        directory_component_patterns, filename_stem_pattern = self._split_path_pattern(
            path_pattern
        )
        folder_parts = self._render_folder_parts(
            directory_component_patterns,
            context,
        )
        filename_stem = self._render_filename_stem(filename_stem_pattern, context)
        candidate = resolved_root.joinpath(
            *folder_parts, f"{filename_stem}.{extension}"
        )
        contained = ensure_within_root(
            candidate,
            root_path=resolved_root,
            subject="Output image",
        )
        if avoid_collisions:
            contained = self._collision_safe_path(contained, resolved_root)
        return OutputPathRenderResult(path=contained, display_path=str(contained))

    def preview_path(
        self,
        *,
        output_root: Path,
        path_pattern: str,
        context: OutputPathRenderContext,
    ) -> OutputPathRenderResult:
        """Render an example output path without filesystem collision suffixing."""

        return self.render_path(
            output_root=output_root,
            path_pattern=path_pattern,
            context=context,
            avoid_collisions=False,
        )

    def resolve_run_bucket(
        self,
        *,
        output_root: Path,
        path_pattern: str,
        context: OutputPathRenderContext,
    ) -> OutputRunBucket:
        """Resolve the output directory namespace used for `{run}` allocation."""

        self.validate_pattern(path_pattern)
        resolved_root = self._resolve_output_root(output_root)
        directory_component_patterns, filename_stem_pattern = self._split_path_pattern(
            path_pattern
        )
        bucket_component_patterns = self._bucket_component_patterns(
            directory_component_patterns,
            filename_stem_pattern,
        )
        folder_parts = self._render_folder_parts(bucket_component_patterns, context)
        directory = ensure_within_root(
            resolved_root.joinpath(*folder_parts),
            root_path=resolved_root,
            subject="Output run bucket",
        )
        display_label = folder_parts[-1] if folder_parts else directory.name
        return OutputRunBucket(
            key=self._bucket_key(directory),
            directory=directory,
            display_label=display_label or str(directory),
        )

    def bucket_affecting_time_tokens(self, path_pattern: str) -> tuple[str, ...]:
        """Return time tokens that can change the resolved run bucket."""

        self.validate_pattern(path_pattern)
        directory_component_patterns, filename_stem_pattern = self._split_path_pattern(
            path_pattern
        )
        bucket_component_patterns = self._bucket_component_patterns(
            directory_component_patterns,
            filename_stem_pattern,
        )
        tokens: set[str] = set()
        for component_pattern in bucket_component_patterns:
            tokens.update(
                token
                for token in _TOKEN_RE.findall(component_pattern)
                if token in _TIME_TOKEN_NAMES
            )
        return tuple(token for token in ("date", "day", "time") if token in tokens)

    def _split_path_pattern(self, path_pattern: str) -> tuple[tuple[str, ...], str]:
        """Split a relative output pattern into folder parts and filename stem."""

        normalized = path_pattern.strip().rstrip("\\/")
        parts = tuple(part for part in _PATH_SEPARATOR_RE.split(normalized) if part)
        if not parts:
            return (), ""
        return parts[:-1], parts[-1]

    def _bucket_component_patterns(
        self,
        directory_component_patterns: tuple[str, ...],
        filename_stem_pattern: str,
    ) -> tuple[str, ...]:
        """Return directory patterns resolvable before a `{run}` component."""

        if "{run}" in filename_stem_pattern:
            return directory_component_patterns
        bucket_parts: list[str] = []
        for component_pattern in directory_component_patterns:
            if "{run}" in component_pattern:
                break
            bucket_parts.append(component_pattern)
        return tuple(bucket_parts)

    def _render_folder_parts(
        self,
        directory_component_patterns: tuple[str, ...],
        context: OutputPathRenderContext,
    ) -> tuple[str, ...]:
        """Render sanitized directory components from path pattern parts."""

        if not directory_component_patterns:
            return ()
        parts: list[str] = []
        for raw_part in directory_component_patterns:
            if not raw_part:
                continue
            rendered = self._render_pattern(
                raw_part,
                context,
                replace_spaces=False,
                lowercase=False,
            )
            sanitized = self._sanitize_component(
                rendered,
                replace_spaces=False,
                lowercase=False,
            )
            if sanitized:
                parts.append(sanitized)
            elif raw_part.strip():
                parts.append("untitled")
        return tuple(parts)

    def _render_filename_stem(
        self,
        filename_stem_pattern: str,
        context: OutputPathRenderContext,
    ) -> str:
        """Render a sanitized filename stem from the last path pattern part."""

        rendered = self._render_pattern(
            filename_stem_pattern,
            context,
            replace_spaces=True,
            lowercase=True,
        )
        sanitized = self._sanitize_component(
            rendered,
            replace_spaces=True,
            lowercase=True,
        )
        return sanitized or "output"

    def _render_pattern(
        self,
        pattern: str,
        context: OutputPathRenderContext,
        *,
        replace_spaces: bool,
        lowercase: bool,
    ) -> str:
        """Render all supported tokens in one pattern string."""

        self._validate_pattern(pattern)
        values = self._token_values(context)

        def replace(match: re.Match[str]) -> str:
            """Return sanitized token text for one matched placeholder."""

            token_name = match.group(1)
            value = values[token_name]
            return self._sanitize_component(
                value,
                replace_spaces=replace_spaces,
                lowercase=lowercase,
            )

        return _TOKEN_RE.sub(replace, pattern)

    def _validate_pattern(self, pattern: str) -> None:
        """Reject malformed placeholders and unsupported tokens."""

        remainder = _TOKEN_RE.sub("", pattern)
        if "{" in remainder or "}" in remainder:
            raise OutputPathTemplateError(
                f"Output path pattern has malformed token syntax: {pattern}"
            )
        unknown_tokens = sorted(
            token
            for token in _TOKEN_RE.findall(pattern)
            if token not in SUPPORTED_OUTPUT_PATH_TOKEN_NAMES
        )
        if unknown_tokens:
            joined = ", ".join(f"{{{token}}}" for token in unknown_tokens)
            raise OutputPathTemplateError(f"Unknown output path token(s): {joined}.")

    def _token_values(self, context: OutputPathRenderContext) -> dict[str, str]:
        """Return raw token values for a render context."""

        started = context.job_started_at
        run_number = (
            f"{context.output_run_number:03d}"
            if context.output_run_number is not None
            else ""
        )
        cube_number = (
            f"{context.cube_number:02d}" if context.cube_number is not None else ""
        )
        folder_image_number = (
            f"{context.folder_image_number:02d}"
            if context.folder_image_number is not None
            else ""
        )
        return {
            "run": run_number,
            "cube#": cube_number,
            "image#": folder_image_number,
            "seed": context.seed,
            "workflow": context.workflow_name,
            "source": context.source,
            "cube": context.cube,
            "date": started.strftime("%Y-%m-%d"),
            "time": started.strftime("%H-%M-%S"),
            "day": started.strftime("%A"),
            "width": str(context.width),
            "height": str(context.height),
            "index": str(context.index),
            "set": str(context.set_index),
        }

    def _sanitize_component(
        self,
        value: object,
        *,
        replace_spaces: bool,
        lowercase: bool,
    ) -> str:
        """Return filesystem-safe text for one rendered component."""

        text = str(value).strip()
        if lowercase:
            text = text.lower()
        text = _UNSAFE_COMPONENT_RE.sub("_", text)
        if replace_spaces:
            text = _WHITESPACE_RE.sub("_", text)
        text = re.sub(r"_+", "_", text).strip(" ._")
        return text

    def _resolve_output_root(self, output_root: Path) -> Path:
        """Return a resolved absolute output root or raise."""

        if not Path(str(output_root)).expanduser().is_absolute():
            raise OutputPathTemplateError("Output root must be an absolute path.")
        root = operational_path(output_root)
        return root.resolve()

    def _collision_safe_path(self, candidate: Path, root: Path) -> Path:
        """Return candidate or a numbered sibling that does not exist."""

        if not candidate.exists():
            return candidate
        stem = candidate.stem
        suffix = candidate.suffix
        for index in range(2, _COLLISION_LIMIT):
            variant = candidate.with_name(f"{stem}_{index:03d}{suffix}")
            contained = ensure_within_root(
                variant,
                root_path=root,
                subject="Output image",
            )
            if not contained.exists():
                return contained
        raise OutputPathTemplateError(
            f"Could not allocate a unique output path for '{candidate}'."
        )

    @staticmethod
    def _bucket_key(directory: Path) -> str:
        """Return a stable path-derived bucket identity."""

        return str(directory).replace("\\", "/").casefold()


__all__ = [
    "OutputPathTemplateError",
    "OutputPathTemplateRenderer",
]
