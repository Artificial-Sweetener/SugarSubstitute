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

"""Probe source-backed caret boundaries through the real prompt-editor shell."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

from PySide6.QtCore import Qt

from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from tests.support.prompt_editor.real_shell.models import (
    PromptEditorStateSnapshot,
    PromptFieldHandle,
)
from tests.support.prompt_editor.real_shell.input_driver import PromptEditorInputDriver
from tests.support.prompt_editor.real_shell.snapshots import PromptEditorSnapshotCapture

type PromptDecorationBoundary = Literal[
    "leading",
    "content_start",
    "content_interior",
    "content_end",
    "trailing",
]


@dataclass(frozen=True, slots=True)
class PromptDecorationBoundaryCase:
    """Describe one source fixture and its applicable visible boundaries."""

    token_kind: PromptProjectionTokenKind
    source_text: str
    boundaries: tuple[PromptDecorationBoundary, ...]


DECORATION_BOUNDARY_CASES = (
    PromptDecorationBoundaryCase(
        PromptProjectionTokenKind.EMPHASIS,
        "before (alpha:1.2) after",
        (
            "leading",
            "content_start",
            "content_interior",
            "content_end",
            "trailing",
        ),
    ),
    PromptDecorationBoundaryCase(
        PromptProjectionTokenKind.SCENE,
        "before\n**Scene title\nafter",
        (
            "leading",
            "content_start",
            "content_interior",
            "content_end",
            "trailing",
        ),
    ),
    PromptDecorationBoundaryCase(
        PromptProjectionTokenKind.WILDCARD,
        "before {colors} after",
        ("leading", "trailing"),
    ),
    PromptDecorationBoundaryCase(
        PromptProjectionTokenKind.LORA,
        "before <lora:style:0.8> after",
        ("leading", "trailing"),
    ),
    PromptDecorationBoundaryCase(
        PromptProjectionTokenKind.REGION_SEPARATOR,
        "before\n[SEP]\nafter",
        ("leading", "trailing"),
    ),
)


class RealShellPromptDecorationBoundaryProbe:
    """Place and observe carets at semantic decoration boundaries."""

    def __init__(
        self,
        *,
        input_driver: PromptEditorInputDriver,
        snapshots: PromptEditorSnapshotCapture,
    ) -> None:
        """Bind only the input and snapshot owners used by this probe."""

        self._input = input_driver
        self._snapshots = snapshots

    def token_for_kind(
        self,
        field: PromptFieldHandle,
        kind: PromptProjectionTokenKind,
    ) -> PromptProjectionToken:
        """Return the sole production token of the requested kind."""

        surface = cast(Any, field.editor)._surface
        tokens = surface.projection_document().tokens
        matching_tokens = tuple(token for token in tokens if token.kind is kind)
        if len(matching_tokens) != 1:
            raise AssertionError(
                f"expected one {kind.value} token, received {len(matching_tokens)}"
            )
        return cast(PromptProjectionToken, matching_tokens[0])

    def place_caret(
        self,
        field: PromptFieldHandle,
        token: PromptProjectionToken,
        boundary: PromptDecorationBoundary,
    ) -> PromptEditorStateSnapshot:
        """Place the caret at one token boundary and return settled owner state."""

        position = decoration_boundary_position(token, boundary)
        self._input.set_source_cursor_position(field, position)
        snapshot = self._snapshots.capture(
            field,
            label=f"{token.kind.value}-{boundary}-placed",
        )
        expected_placement = decoration_boundary_placement(boundary)
        if (
            boundary == "trailing"
            and snapshot.caret_state_placement != expected_placement
        ):
            self._input.press_key(field, Qt.Key.Key_Right)
            snapshot = self._snapshots.capture(
                field,
                label=f"{token.kind.value}-{boundary}-selected",
            )
        return snapshot


def decoration_boundary_position(
    token: PromptProjectionToken,
    boundary: PromptDecorationBoundary,
) -> int:
    """Return the authoritative source position for one token boundary."""

    if boundary == "leading":
        return token.source_start
    if boundary == "trailing":
        return token.source_end
    content_range = token.content_range
    if content_range is None:
        raise AssertionError(f"{token.kind.value} has no {boundary} boundary")
    if boundary == "content_start":
        return content_range[0]
    if boundary == "content_end":
        return content_range[1]
    return content_range[0] + ((content_range[1] - content_range[0]) // 2)


def decoration_boundary_placement(boundary: PromptDecorationBoundary) -> str:
    """Return the projection caret placement that owns one boundary."""

    if boundary == "leading":
        return "token_leading_edge"
    if boundary == "trailing":
        return "token_trailing_edge"
    return "token_content"


__all__ = [
    "DECORATION_BOUNDARY_CASES",
    "PromptDecorationBoundary",
    "PromptDecorationBoundaryCase",
    "RealShellPromptDecorationBoundaryProbe",
    "decoration_boundary_placement",
    "decoration_boundary_position",
]
