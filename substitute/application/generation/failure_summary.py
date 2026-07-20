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

"""Summarize raw generation failures into compact user-facing text."""

from __future__ import annotations

import re
from typing import Protocol

from sugarsubstitute_shared.localization import ApplicationText, app_text

_MAX_FALLBACK_LENGTH = 48


class GenerationFailureLine(Protocol):
    """Describe generation failure fields needed for one shell-visible line."""

    @property
    def stage(self) -> str:
        """Return the failure stage key to display."""

    @property
    def message(self) -> ApplicationText:
        """Return the user-visible failure message."""

    @property
    def prompt_id(self) -> str | None:
        """Return the Comfy prompt ID when the failure has one."""


def format_generation_failure_line(
    failure: GenerationFailureLine,
) -> ApplicationText:
    """Build one shell-visible generation failure line."""

    stage_label = failure.stage.replace("_", " ").strip() or "generation"
    base_message = (
        app_text("Generation failed during %1: %2", stage_label, failure.message)
        if failure.message
        else app_text("Generation failed during %1.", stage_label)
    )
    if failure.prompt_id is None:
        return base_message
    return app_text("%1 prompt_id=%2", base_message, failure.prompt_id)


def summarize_generation_failure(
    message: str | None,
    *,
    detail: str | None = None,
) -> ApplicationText:
    """Return a compact user-facing generation failure summary."""

    source = _combine_failure_text(message, detail)
    lowered = source.lower()
    if not source:
        return app_text("Generation failed")

    module_name = _extract_missing_module(source)
    if module_name:
        return app_text("Missing %1", module_name)

    dll_module_name = _extract_failed_import_module(source)
    if dll_module_name:
        return app_text("%1 failed to load", dll_module_name)

    if _looks_like_unattributed_import_failure(lowered):
        return app_text("Dependency failed")

    if _looks_like_out_of_memory(lowered):
        return app_text("Out of memory")

    if _looks_like_comfy_unavailable(lowered):
        return app_text("ComfyUI unavailable")

    if _looks_like_missing_model(lowered):
        return app_text("Missing model")

    if _looks_like_invalid_input(lowered):
        return app_text("Invalid input")

    return _fallback_summary(message or detail or source)


def _combine_failure_text(message: str | None, detail: str | None) -> str:
    """Join message and detail into one classification source."""

    parts = [part.strip() for part in (message, detail) if part and part.strip()]
    return "\n".join(parts)


def _extract_missing_module(source: str) -> str | None:
    """Return module name from Python missing-module messages."""

    patterns = (
        r"No module named ['\"]([^'\"]+)['\"]",
        r"ModuleNotFoundError:\s*No module named ['\"]([^'\"]+)['\"]",
    )
    for pattern in patterns:
        match = re.search(pattern, source, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _extract_failed_import_module(source: str) -> str | None:
    """Return import target from DLL/import-load failure messages."""

    match = re.search(
        r"(?:DLL load failed|ImportError:.*?failed).*?while importing ([A-Za-z0-9_.-]+)",
        source,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1)
    return None


def _looks_like_unattributed_import_failure(lowered: str) -> bool:
    """Return whether text looks dependency-related without a package name."""

    return any(
        phrase in lowered
        for phrase in (
            "modulenotfounderror",
            "importerror",
            "dll load failed",
            "failed to import",
        )
    )


def _looks_like_out_of_memory(lowered: str) -> bool:
    """Return whether text describes an out-of-memory failure."""

    return any(
        phrase in lowered
        for phrase in (
            "cuda out of memory",
            "outofmemoryerror",
            "out of memory",
        )
    )


def _looks_like_comfy_unavailable(lowered: str) -> bool:
    """Return whether text describes ComfyUI connectivity or availability failure."""

    return any(
        phrase in lowered
        for phrase in (
            "connection refused",
            "timed out waiting for events",
            "websocket listener timed out",
            "comfyui is unavailable",
            "comfyui unavailable",
            "http 500",
            "failed to start generation listener",
        )
    )


def _looks_like_missing_model(lowered: str) -> bool:
    """Return whether text describes a missing model/checkpoint file."""

    return any(
        phrase in lowered
        for phrase in (
            "checkpoint not found",
            "model file does not exist",
            "missing model",
            "no such file or directory",
            ".safetensors",
            ".ckpt",
        )
    )


def _looks_like_invalid_input(lowered: str) -> bool:
    """Return whether text describes invalid user input or unsafe paths."""

    return any(
        phrase in lowered
        for phrase in (
            "outside allowed root",
            "invalid mask",
            "invalid image path",
            "invalid input",
        )
    )


def _fallback_summary(source: str | None) -> ApplicationText:
    """Return a clipped first-line/first-sentence fallback summary."""

    if source is None:
        return app_text("Generation failed")
    normalized = " ".join(source.strip().split())
    if not normalized:
        return app_text("Generation failed")
    first_line = normalized.splitlines()[0].strip()
    first_sentence_match = re.match(r"(.+?[.!?])(?:\s|$)", first_line)
    candidate = (
        first_sentence_match.group(1).strip() if first_sentence_match else first_line
    )
    if len(candidate) <= _MAX_FALLBACK_LENGTH:
        return candidate
    return f"{candidate[: _MAX_FALLBACK_LENGTH - 1].rstrip()}..."


__all__ = [
    "GenerationFailureLine",
    "format_generation_failure_line",
    "summarize_generation_failure",
]
