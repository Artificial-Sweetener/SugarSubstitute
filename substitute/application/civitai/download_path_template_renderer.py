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

"""Render CivitAI download path patterns for validation and previews."""

from __future__ import annotations

import re
from pathlib import Path

from substitute.domain.civitai import (
    CivitaiDownloadPathRenderContext,
    CivitaiDownloadPathRenderResult,
    SUPPORTED_CIVITAI_DOWNLOAD_PATH_TOKEN_NAMES,
)
from substitute.shared.util.path_safety import ensure_within_root

_TOKEN_RE = re.compile(r"\{([^{}]+)\}")
_PATH_SEPARATOR_RE = re.compile(r"[\\/]+")
_UNSAFE_COMPONENT_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_WHITESPACE_RE = re.compile(r"\s+")


class CivitaiDownloadPathTemplateError(ValueError):
    """Represent invalid CivitAI download path pattern state."""


class CivitaiDownloadPathTemplateRenderer:
    """Render safe relative download paths inside a Comfy model root."""

    def validate_pattern(self, path_pattern: str) -> None:
        """Validate one CivitAI download path pattern without rendering it."""

        self._validate_pattern(path_pattern)
        if not self._split_path_pattern(path_pattern):
            raise CivitaiDownloadPathTemplateError(
                "CivitAI download pattern must include a file name."
            )

    def preview_path(
        self,
        *,
        path_pattern: str,
        context: CivitaiDownloadPathRenderContext,
    ) -> CivitaiDownloadPathRenderResult:
        """Render an example absolute destination under the context Comfy root."""

        self.validate_pattern(path_pattern)
        root = self._resolve_comfy_root(context.comfy_root)
        relative_path = self._render_relative_path(
            path_pattern=path_pattern,
            context=context,
        )
        candidate = root / relative_path
        contained = ensure_within_root(
            candidate,
            root_path=root,
            subject="CivitAI model download",
        )
        return CivitaiDownloadPathRenderResult(
            path=contained,
            relative_path=relative_path,
            display_path=str(contained),
        )

    def _render_relative_path(
        self,
        *,
        path_pattern: str,
        context: CivitaiDownloadPathRenderContext,
    ) -> Path:
        """Render and sanitize the relative path described by one pattern."""

        parts = self._split_path_pattern(path_pattern)
        if not parts:
            raise CivitaiDownloadPathTemplateError(
                "CivitAI download pattern must include a file name."
            )
        rendered_parts = tuple(
            self._render_component(part, context, filename=index == len(parts) - 1)
            for index, part in enumerate(parts)
        )
        if any(part in {"", ".", ".."} for part in rendered_parts):
            raise CivitaiDownloadPathTemplateError(
                "CivitAI download pattern rendered an empty or unsafe path component."
            )
        relative_path = Path(*rendered_parts)
        if relative_path.is_absolute() or _contains_traversal(relative_path):
            raise CivitaiDownloadPathTemplateError(
                "CivitAI download pattern must stay inside the model folder."
            )
        return relative_path

    def _render_component(
        self,
        pattern: str,
        context: CivitaiDownloadPathRenderContext,
        *,
        filename: bool,
    ) -> str:
        """Render one path component and apply filename extension rules."""

        values = self._token_values(context)

        def replace(match: re.Match[str]) -> str:
            token_name = match.group(1)
            return self._sanitize_component(values[token_name])

        rendered = _TOKEN_RE.sub(replace, pattern)
        sanitized = self._sanitize_component(rendered)
        if filename and not Path(sanitized).suffix:
            suffix = Path(values["file_name"]).suffix
            if suffix:
                sanitized = f"{sanitized}{suffix}"
        return sanitized

    def _validate_pattern(self, pattern: str) -> None:
        """Reject malformed placeholders and unsupported tokens."""

        stripped = pattern.strip()
        if not stripped:
            raise CivitaiDownloadPathTemplateError(
                "CivitAI download pattern cannot be empty."
            )
        remainder = _TOKEN_RE.sub("", stripped)
        if "{" in remainder or "}" in remainder:
            raise CivitaiDownloadPathTemplateError(
                f"CivitAI download pattern has malformed token syntax: {pattern}"
            )
        unknown_tokens = sorted(
            token
            for token in _TOKEN_RE.findall(stripped)
            if token not in SUPPORTED_CIVITAI_DOWNLOAD_PATH_TOKEN_NAMES
        )
        if unknown_tokens:
            joined = ", ".join(f"{{{token}}}" for token in unknown_tokens)
            raise CivitaiDownloadPathTemplateError(
                f"Unknown CivitAI download path token(s): {joined}."
            )
        if Path(stripped).is_absolute() or _starts_with_windows_drive(stripped):
            raise CivitaiDownloadPathTemplateError(
                "CivitAI download pattern must be relative."
            )
        if any(part in {".", ".."} for part in _PATH_SEPARATOR_RE.split(stripped)):
            raise CivitaiDownloadPathTemplateError(
                "CivitAI download pattern cannot contain traversal."
            )

    def _token_values(
        self, context: CivitaiDownloadPathRenderContext
    ) -> dict[str, str]:
        """Return normalized raw token values for a render context."""

        return {
            "base_model": normalize_base_model_bucket(context.base_model)
            or normalize_base_model_bucket(context.model_name)
            or "Unsorted",
            "model_name": context.model_name.strip() or "Unsorted",
            "version_name": context.version_name.strip() or "Version",
            "creator": context.creator.strip() or "Unknown Creator",
            "file_name": _safe_file_name(context.file_name),
            "file_stem": Path(_safe_file_name(context.file_name)).stem,
        }

    @staticmethod
    def _split_path_pattern(path_pattern: str) -> tuple[str, ...]:
        """Split a relative pattern into non-empty path components."""

        normalized = path_pattern.strip().rstrip("\\/")
        return tuple(part for part in _PATH_SEPARATOR_RE.split(normalized) if part)

    @staticmethod
    def _sanitize_component(value: object) -> str:
        """Return filesystem-safe text for one rendered path component."""

        text = str(value).strip()
        text = _UNSAFE_COMPONENT_RE.sub("_", text)
        text = _WHITESPACE_RE.sub(" ", text)
        text = re.sub(r"_+", "_", text).strip(" ._")
        return text

    @staticmethod
    def _resolve_comfy_root(comfy_root: Path) -> Path:
        """Return a resolved absolute Comfy model root."""

        root = Path(comfy_root)
        if not root.is_absolute():
            raise CivitaiDownloadPathTemplateError(
                "CivitAI preview root must be an absolute path."
            )
        return root.resolve()


def normalize_base_model_bucket(value: str | None) -> str:
    """Return a local folder bucket for a CivitAI base model label."""

    if value is None:
        return ""
    text = value.strip()
    folded = text.casefold()
    if not text:
        return ""
    if "anima" in folded:
        return "Anima"
    if "illustrious" in folded:
        return "Illustrious"
    if "pony" in folded:
        return "Pony"
    if "flux" in folded:
        return "Flux"
    if "sdxl" in folded or "stable diffusion xl" in folded:
        return "SDXL"
    if "stable diffusion 1.5" in folded or folded in {"sd 1.5", "sd1.5", "sd15"}:
        return "SD 1.5"
    if "wan" in folded and "2.2" in folded:
        return "WAN 2.2"
    if "wan" in folded and "2.1" in folded:
        return "WAN 2.1"
    return text


def _safe_file_name(file_name: str) -> str:
    """Return source file metadata as a safe single filename component."""

    source = Path(file_name).name.strip()
    cleaned = CivitaiDownloadPathTemplateRenderer._sanitize_component(source)
    return cleaned or "model.safetensors"


def _contains_traversal(path: Path) -> bool:
    """Return whether a relative path contains traversal components."""

    return any(part in {"..", "."} for part in path.parts)


def _starts_with_windows_drive(value: str) -> bool:
    """Return whether text starts with a Windows drive prefix."""

    return bool(re.match(r"^[A-Za-z]:[\\/]", value.strip()))


__all__ = [
    "CivitaiDownloadPathTemplateError",
    "CivitaiDownloadPathTemplateRenderer",
    "normalize_base_model_bucket",
]
