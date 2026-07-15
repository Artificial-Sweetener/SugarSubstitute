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

"""Represent geometry-neutral prompt projection paint state."""

from __future__ import annotations

from dataclasses import dataclass

from .model import (
    PromptProjectionDocument,
    PromptProjectionRun,
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from .session import PromptProjectionSession


@dataclass(frozen=True, slots=True)
class PromptProjectionPaintState:
    """Describe projection visual state that cannot alter layout geometry."""

    active_span_range: tuple[int, int] | None = None
    active_token_ids: frozenset[str] = frozenset()
    active_run_ids: frozenset[str] = frozenset()
    focused_token_id: str | None = None
    hovered_token_id: str | None = None
    ghosted_run_ids: frozenset[str] = frozenset()
    decoration_accent_ranges: tuple[tuple[int, int], ...] = ()
    decoration_accented_token_ids: frozenset[str] = frozenset()
    scene_error_keys: frozenset[str] = frozenset()
    scene_error_run_ids: frozenset[str] = frozenset()

    def references_only(
        self,
        *,
        token_ids: frozenset[str],
        run_ids: frozenset[str],
    ) -> bool:
        """Return whether every stored token/run reference exists."""

        optional_token_ids = frozenset(
            token_id
            for token_id in (self.focused_token_id, self.hovered_token_id)
            if token_id is not None
        )
        return (
            self.active_token_ids <= token_ids
            and self.decoration_accented_token_ids <= token_ids
            and optional_token_ids <= token_ids
            and self.active_run_ids <= run_ids
            and self.ghosted_run_ids <= run_ids
            and self.scene_error_run_ids <= run_ids
        )

    def is_token_active(self, token_id: str | None) -> bool:
        """Return whether one token should paint as active."""

        return token_id is not None and token_id in self.active_token_ids

    def is_token_decoration_accented(self, token_id: str | None) -> bool:
        """Return whether one token should paint with decoration accenting."""

        return token_id is not None and token_id in self.decoration_accented_token_ids

    def is_run_active(self, run_id: str | None) -> bool:
        """Return whether one run should paint as active."""

        return run_id is not None and run_id in self.active_run_ids

    def is_run_ghosted(self, run_id: str | None) -> bool:
        """Return whether one run should paint as autocomplete ghost text."""

        return run_id is not None and run_id in self.ghosted_run_ids

    def is_run_scene_error(self, run_id: str | None) -> bool:
        """Return whether one scene-title run should paint as an error."""

        return run_id is not None and run_id in self.scene_error_run_ids


class PromptProjectionPaintStateBuilder:
    """Build geometry-neutral paint state for an existing projection document."""

    def build(
        self,
        document: PromptProjectionDocument,
        *,
        session: PromptProjectionSession,
        active_span_range: tuple[int, int] | None,
        decoration_accent_ranges: tuple[tuple[int, int], ...],
        scene_error_keys: frozenset[str],
        focused_token_id: str | None = None,
        hovered_token_id: str | None = None,
    ) -> PromptProjectionPaintState:
        """Return paint-only state keyed to existing token and run identifiers."""

        _ = session
        active_token_ids = _active_token_ids(document.tokens, active_span_range)
        decoration_accented_token_ids = _decoration_accented_token_ids(
            document.tokens,
            decoration_accent_ranges,
        )
        active_run_ids = _run_ids_for_tokens(document.runs, active_token_ids)
        scene_error_run_ids = _scene_error_run_ids(
            document.tokens,
            document.runs,
            scene_error_keys,
        )
        ghosted_run_ids = frozenset(run.run_id for run in document.runs if run.ghosted)
        return PromptProjectionPaintState(
            active_span_range=active_span_range,
            active_token_ids=active_token_ids,
            active_run_ids=active_run_ids,
            focused_token_id=focused_token_id,
            hovered_token_id=hovered_token_id,
            ghosted_run_ids=ghosted_run_ids,
            decoration_accent_ranges=decoration_accent_ranges,
            decoration_accented_token_ids=decoration_accented_token_ids,
            scene_error_keys=scene_error_keys,
            scene_error_run_ids=scene_error_run_ids,
        )


def empty_projection_paint_state() -> PromptProjectionPaintState:
    """Return the default geometry-neutral paint state."""

    return PromptProjectionPaintState()


def _active_token_ids(
    tokens: tuple[PromptProjectionToken, ...],
    active_span_range: tuple[int, int] | None,
) -> frozenset[str]:
    """Return token ids covered by the active syntax span."""

    if active_span_range is None:
        return frozenset()
    return frozenset(
        token.token_id
        for token in tokens
        if (token.source_start, token.source_end) == active_span_range
    )


def _decoration_accented_token_ids(
    tokens: tuple[PromptProjectionToken, ...],
    decoration_accent_ranges: tuple[tuple[int, int], ...],
) -> frozenset[str]:
    """Return token ids whose decorations should paint with accent color."""

    accent_ranges = frozenset(decoration_accent_ranges)
    return frozenset(
        token.token_id
        for token in tokens
        if (token.source_start, token.source_end) in accent_ranges
    )


def _run_ids_for_tokens(
    runs: tuple[PromptProjectionRun, ...],
    token_ids: frozenset[str],
) -> frozenset[str]:
    """Return run ids belonging to the supplied tokens."""

    return frozenset(
        run.run_id
        for run in runs
        if run.token_id is not None and run.token_id in token_ids
    )


def _scene_error_run_ids(
    tokens: tuple[PromptProjectionToken, ...],
    runs: tuple[PromptProjectionRun, ...],
    scene_error_keys: frozenset[str],
) -> frozenset[str]:
    """Return scene title run ids that should paint with error styling."""

    scene_error_token_ids = frozenset(
        token.token_id
        for token in tokens
        if token.kind is PromptProjectionTokenKind.SCENE
        and token.value_text in scene_error_keys
    )
    return _run_ids_for_tokens(runs, scene_error_token_ids)


__all__ = [
    "PromptProjectionPaintState",
    "PromptProjectionPaintStateBuilder",
    "empty_projection_paint_state",
]
