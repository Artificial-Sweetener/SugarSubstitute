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

"""Wire prompt-editor startup and construction lifecycle concerns."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Literal, Protocol, cast

from substitute.shared.logging.logger import log_timing

from ..qt_lifecycle import qt_object_is_alive
from ..shell import (
    PromptShellQFluentChrome,
    PromptShellScrollDelegate,
    PromptShellSizingController,
)

_PROMPT_EDITOR_CONSTRUCTION_LOG_FIELDS = frozenset(
    {
        "autocomplete_minimum_prefix_length",
        "diagnostics_activation_pending",
        "diagnostics_controller_enabled",
        "has_lora_catalog",
        "has_segment_presets",
        "has_spellcheck_service",
        "has_thumbnail_repository",
        "lora_autocomplete_enabled",
        "maximum_visible_lines",
        "spellcheck_feature_enabled",
        "trigger_word_suggestions_enabled",
    }
)
_PROMPT_EDITOR_FORBIDDEN_LOG_FIELD_FRAGMENTS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "exception",
    "file",
    "password",
    "path",
    "prompt",
    "secret",
    "selected",
    "source",
    "text",
    "token",
    "trigger",
    "value",
)


class PromptEditorConstructionLifecycleHost(Protocol):
    """Describe diagnostics lifecycle hooks owned by the feature controller."""

    def can_activate(self) -> bool:
        """Return whether diagnostics activation should be scheduled."""

    def schedule_activation(self) -> None:
        """Schedule the existing diagnostics activation path."""

    @property
    def is_active(self) -> bool:
        """Return whether diagnostics providers have already been activated."""

    @property
    def activation_pending(self) -> bool:
        """Return whether diagnostics activation has already been scheduled."""


class PromptEditorInitialLayoutHost(Protocol):
    """Describe construction-time layout hooks owned by later shell phases."""

    _qfluent_chrome: PromptShellQFluentChrome
    _scroll_delegate: PromptShellScrollDelegate
    _sizing: PromptShellSizingController

    def minimumEditorHeight(self) -> int:  # noqa: N802
        """Return the preferred minimum editor height."""


@dataclass(frozen=True, slots=True)
class PromptEditorLifecycleWiringResult:
    """Report construction lifecycle state after wiring existing hooks."""

    diagnostics_controller_enabled: bool
    diagnostics_activation_pending: bool


class PromptEditorConstructionObserver:
    """Record prompt-safe prompt-editor construction timing logs."""

    def __init__(
        self,
        logger: logging.Logger,
    ) -> None:
        """Store the logger used by constructor phase timing records."""

        self._logger = logger

    def started_at(self) -> float:
        """Return a monotonic timestamp for one constructor phase."""

        return perf_counter()

    def log_timing(
        self,
        message: str,
        *,
        started_at: float,
        level: Literal["debug", "info", "warning", "error"] = "debug",
        **context: object,
    ) -> float:
        """Log one constructor timing measurement with structured context."""

        validated_context = cast(
            dict[str, Any], _validated_construction_context(context)
        )
        return log_timing(
            self._logger,
            message,
            started_at=started_at,
            level=level,
            **validated_context,
        )


def _validated_construction_context(
    context: dict[str, object],
) -> dict[str, object]:
    """Return prompt-editor construction fields after enforcing the safe allowlist."""

    unknown_fields = set(context) - _PROMPT_EDITOR_CONSTRUCTION_LOG_FIELDS
    if unknown_fields:
        joined_fields = ", ".join(sorted(unknown_fields))
        unsafe_fields = [
            field_name
            for field_name in sorted(unknown_fields)
            if _construction_field_name_has_forbidden_fragment(field_name)
        ]
        if unsafe_fields:
            joined_unsafe_fields = ", ".join(unsafe_fields)
            raise ValueError(
                "Prompt-editor construction timing context received "
                f"prompt-safe forbidden fields: {joined_unsafe_fields}"
            )
        raise ValueError(
            "Prompt-editor construction timing context received unsupported fields: "
            f"{joined_fields}"
        )
    return context


def _construction_field_name_has_forbidden_fragment(field_name: str) -> bool:
    """Return whether a construction field name can carry prompt-sensitive data."""

    normalized = field_name.strip().lower().replace("-", "_")
    return any(
        fragment in normalized
        for fragment in _PROMPT_EDITOR_FORBIDDEN_LOG_FIELD_FRAGMENTS
    )


def wire_prompt_editor_construction_lifecycle(
    editor: PromptEditorConstructionLifecycleHost,
) -> PromptEditorLifecycleWiringResult:
    """Wire construction-owned lifecycle hooks without owning their policy."""

    if editor.can_activate():
        editor.schedule_activation()
    return PromptEditorLifecycleWiringResult(
        diagnostics_controller_enabled=editor.is_active,
        diagnostics_activation_pending=editor.activation_pending,
    )


def apply_prompt_editor_initial_layout(editor: PromptEditorInitialLayoutHost) -> None:
    """Apply construction-time style, geometry, placeholder, and height hooks."""

    editor._qfluent_chrome.sync_surface_style()
    editor._scroll_delegate.layout_surface()
    editor._qfluent_chrome.apply_placeholder_visibility()
    editor._sizing.apply_preferred_height(editor.minimumEditorHeight())


def is_deleted_qt_object_error(error: RuntimeError) -> bool:
    """Return whether a RuntimeError came from a deleted PySide C++ object."""

    return "Internal C++ object" in str(error) and "already deleted" in str(error)


__all__ = [
    "PromptEditorConstructionObserver",
    "PromptEditorConstructionLifecycleHost",
    "PromptEditorInitialLayoutHost",
    "PromptEditorLifecycleWiringResult",
    "apply_prompt_editor_initial_layout",
    "is_deleted_qt_object_error",
    "qt_object_is_alive",
    "wire_prompt_editor_construction_lifecycle",
]
