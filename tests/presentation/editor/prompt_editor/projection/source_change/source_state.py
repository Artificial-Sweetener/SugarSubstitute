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

"""Provide source-state recorders for source-change contracts."""

from __future__ import annotations


from PySide6.QtGui import QFont

from substitute.presentation.editor.prompt_editor.core.editing.source_commands import (
    PromptSourceEditOrigin,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.projection.freshness_controller import (
    ProjectionFreshness,
    PromptProjectionFreshnessBlockers,
)


class _SourceDocumentRecorder:
    """Record source document mirror operations."""

    def __init__(self) -> None:
        """Create an empty source-document recorder."""

        self.font_syncs = 0
        self.range_fallback_calls: list[tuple[str, str | None, int | None]] = []
        self.replacements: list[str] = []

    def sync_default_font(self, font: QFont) -> None:
        """Record a default font sync."""

        _ = font
        self.font_syncs += 1

    def replace_with_range_fallback(
        self,
        *,
        next_text: str,
        previous_text: str | None,
        start: int | None,
        end: int | None,
        replacement_text: str | None,
    ) -> bool:
        """Record one source mirror range/fallback update."""

        _ = end
        _ = replacement_text
        self.range_fallback_calls.append((next_text, previous_text, start))
        return True

    def replace_text(self, text: str) -> None:
        """Record one full source mirror replacement."""

        self.replacements.append(text)


class _SessionRecorder:
    """Record session state touched by source-change application."""

    def __init__(self) -> None:
        """Create empty session state."""

        self.diagnostics: tuple[object, ...] = ()
        self.autocomplete_preview: object | None = None
        self.expanded_source_range: tuple[int, int] | None = None
        self.autocomplete_preview_updates: list[object | None] = []

    def set_diagnostics(self, diagnostics: tuple[object, ...]) -> None:
        """Record diagnostic replacement."""

        self.diagnostics = diagnostics

    def set_autocomplete_preview(self, preview: object | None) -> None:
        """Record autocomplete preview replacement."""

        self.autocomplete_preview = preview
        self.autocomplete_preview_updates.append(preview)


class _MouseRecorder:
    """Record source-change pointer cleanup."""

    def __init__(self) -> None:
        """Create an empty mouse recorder."""

        self.cleared = 0

    def clear_pointer_state_for_source_replacement(self) -> None:
        """Record pointer cleanup."""

        self.cleared += 1


class _FreshnessControllerRecorder:
    """Record freshness-controller calls used by source-change tests."""

    def __init__(self) -> None:
        """Create an empty freshness controller recorder."""

        self.freshness = ProjectionFreshness.UNAVAILABLE
        self.pending_clear_count = 0
        self.can_defer_projection = False
        self.deferral_reason = "safe_typing"

    def clear_pending_after_immediate_apply(self) -> None:
        """Record pending update clearing through the freshness owner."""

        self.pending_clear_count += 1

    def has_stale_projection_geometry(self) -> bool:
        """Return whether deferred overlay geometry may be consumed."""

        return self.freshness is ProjectionFreshness.STALE_SAFE

    def transient_committed_source_identity(
        self,
        *,
        current_source_identity: PromptSourceIdentity,
    ) -> PromptSourceIdentity:
        """Return the committed source identity for transient overlays."""

        return current_source_identity

    def can_defer_source_rebuild_for_edit(
        self,
        *,
        blockers: PromptProjectionFreshnessBlockers,
        start: int,
        end: int,
        replaced_text: str,
        replacement_text: str,
        origin: PromptSourceEditOrigin,
        updated_text: str,
        normalized_text: str,
        edit_inside_projected_token: bool,
        delete_intersects_projected_token: bool,
        typed_character_requires_immediate_projection: bool,
        syntax_sensitive_autocomplete_prefix: bool,
    ) -> tuple[bool, str]:
        """Return configured deferral state through the freshness owner."""

        _ = blockers
        _ = start
        _ = end
        _ = replaced_text
        _ = replacement_text
        _ = origin
        _ = updated_text
        _ = normalized_text
        _ = edit_inside_projected_token
        _ = delete_intersects_projected_token
        _ = typed_character_requires_immediate_projection
        _ = syntax_sensitive_autocomplete_prefix
        return self.can_defer_projection, self.deferral_reason

    def can_extend_deferred_plain_source_edit(
        self,
        *,
        previous_projection_freshness: ProjectionFreshness,
        start: int,
        end: int,
        replacement_text: str,
        typed_character_requires_immediate_projection: bool,
        syntax_sensitive_autocomplete_prefix: bool,
    ) -> bool:
        """Mirror the focused deferred-chain eligibility contract."""

        return (
            previous_projection_freshness is ProjectionFreshness.STALE_SAFE
            and start == end
            and len(replacement_text) == 1
            and replacement_text not in {"\n", "\r", "\t"}
            and (
                not typed_character_requires_immediate_projection
                or syntax_sensitive_autocomplete_prefix
            )
        )
