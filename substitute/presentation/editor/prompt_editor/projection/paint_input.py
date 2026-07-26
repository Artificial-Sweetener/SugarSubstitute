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

"""Capture the complete prepared input for prompt projection painting."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType

from PySide6.QtGui import QFont, QPalette

from substitute.application.appearance import SemanticPalette

from ..core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)
from ..core.projection.runs import PromptProjectionRun
from ..core.projection.tokens import PromptProjectionToken
from ..geometry.aggregate import PromptProjectionGeometry
from ..layout.models import (
    PromptProjectionInlineObjectFragment,
    PromptProjectionLayoutSnapshot,
)
from .content_inline_bindings import (
    PromptProjectionBaseInlineBindings,
    PromptProjectionInlinePaintBinding,
)
from .content_text_styles import (
    PromptProjectionBaseTextStyles,
    PromptProjectionTextPaintStyle,
    text_style_for_run,
)
from .paint_state import PromptProjectionPaintState
from .tokens import PromptProjectionInlineObjectRendererRegistry


@dataclass(frozen=True, slots=True)
class PromptProjectionPaintStyleKey:
    """Identify immutable font and palette values prepared for painting."""

    display_mode: PromptProjectionDisplayMode
    font_key: str
    palette_cache_key: int
    text_color: int
    placeholder_color: int
    semantic_accent: tuple[int, int, int]
    semantic_error_foreground: tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class PromptProjectionPaintInput:
    """Provide only prepared references consumed by projection painting."""

    projection_document: PromptProjectionDocument
    layout_snapshot: PromptProjectionLayoutSnapshot
    paint_state: PromptProjectionPaintState
    geometry: PromptProjectionGeometry
    inline_object_renderers: PromptProjectionInlineObjectRendererRegistry
    base_font: QFont
    palette: QPalette
    semantic_palette: SemanticPalette | None
    base_inline_bindings: PromptProjectionBaseInlineBindings
    base_text_styles: PromptProjectionBaseTextStyles
    style_key: PromptProjectionPaintStyleKey | None = field(
        init=False,
        repr=False,
        compare=False,
    )
    _effective_runs_by_id: Mapping[str, PromptProjectionRun] = field(
        init=False,
        repr=False,
        compare=False,
    )
    _effective_tokens_by_id: Mapping[str, PromptProjectionToken] = field(
        init=False,
        repr=False,
        compare=False,
    )
    _effective_text_styles_by_run_id: Mapping[
        str,
        PromptProjectionTextPaintStyle,
    ] = field(init=False, repr=False, compare=False)
    _effective_inline_bindings: Mapping[
        int,
        PromptProjectionInlinePaintBinding,
    ] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Detach retained Qt values from caller-owned mutable instances."""

        object.__setattr__(self, "base_font", QFont(self.base_font))
        object.__setattr__(self, "palette", QPalette(self.palette))
        semantic_palette = self.semantic_palette
        palette = self.palette
        style_key = (
            None
            if semantic_palette is None
            else PromptProjectionPaintStyleKey(
                display_mode=self.projection_document.display_mode,
                font_key=self.base_font.toString(),
                palette_cache_key=int(palette.cacheKey()),
                text_color=palette.color(QPalette.ColorRole.Text).rgba(),
                placeholder_color=palette.color(
                    QPalette.ColorRole.PlaceholderText
                ).rgba(),
                semantic_accent=(
                    semantic_palette.accent.red,
                    semantic_palette.accent.green,
                    semantic_palette.accent.blue,
                ),
                semantic_error_foreground=(
                    semantic_palette.error_foreground.red,
                    semantic_palette.error_foreground.green,
                    semantic_palette.error_foreground.blue,
                ),
            )
        )
        object.__setattr__(self, "style_key", style_key)
        paint_state = self.paint_state
        effective_runs = {
            run_id: run
            for run_id in (
                paint_state.active_run_ids
                | paint_state.ghosted_run_ids
                | paint_state.scene_error_run_ids
            )
            if (
                run := effective_run_for_paint(
                    self.projection_document,
                    paint_state,
                    run_id,
                )
            )
            is not None
        }
        effective_tokens = {
            token_id: token
            for token_id in (
                paint_state.active_token_ids | paint_state.decoration_accented_token_ids
            )
            if (
                token := effective_token_for_paint(
                    self.projection_document,
                    paint_state,
                    token_id,
                )
            )
            is not None
        }
        object.__setattr__(
            self,
            "_effective_runs_by_id",
            MappingProxyType(effective_runs),
        )
        object.__setattr__(
            self,
            "_effective_text_styles_by_run_id",
            MappingProxyType(
                {
                    run_id: text_style_for_run(
                        run,
                        base_font=self.base_font,
                        palette=self.palette,
                        semantic_palette=self.semantic_palette,
                    )
                    for run_id, run in effective_runs.items()
                }
            ),
        )
        object.__setattr__(
            self,
            "_effective_tokens_by_id",
            MappingProxyType(effective_tokens),
        )
        object.__setattr__(
            self,
            "_effective_inline_bindings",
            self.base_inline_bindings.effective_overrides(
                runs_by_id=effective_runs,
                tokens_by_id=effective_tokens,
            ),
        )

    def effective_run(self, run_id: str | None) -> PromptProjectionRun | None:
        """Return one run with this input's paint flags applied."""

        if run_id is None:
            return None
        prepared_run = self._effective_runs_by_id.get(run_id)
        if prepared_run is not None:
            return prepared_run
        return self.projection_document.run_by_id(run_id)

    def effective_token(self, token_id: str | None) -> PromptProjectionToken | None:
        """Return one token with this input's paint flags applied."""

        if token_id is None:
            return None
        prepared_token = self._effective_tokens_by_id.get(token_id)
        if prepared_token is not None:
            return prepared_token
        return self.projection_document.token_by_id(token_id)

    def text_style(
        self,
        run_id: str | None,
    ) -> PromptProjectionTextPaintStyle | None:
        """Return one prepared effective text-run style."""

        if run_id is None:
            return None
        effective = self._effective_text_styles_by_run_id.get(run_id)
        if effective is not None:
            return effective
        return self.base_text_styles.style_for_run(run_id)

    def inline_binding(
        self,
        fragment: PromptProjectionInlineObjectFragment,
    ) -> PromptProjectionInlinePaintBinding | None:
        """Return one prepared effective inline-fragment binding."""

        fragment_id = id(fragment)
        effective = self._effective_inline_bindings.get(fragment_id)
        if effective is not None:
            return effective
        return self.base_inline_bindings.binding(fragment)


def effective_run_for_paint(
    projection_document: PromptProjectionDocument,
    paint_state: PromptProjectionPaintState,
    run_id: str | None,
) -> PromptProjectionRun | None:
    """Return one run with geometry-neutral paint flags applied."""

    run = projection_document.run_by_id(run_id)
    if run is None:
        return None
    active = run.active or paint_state.is_run_active(run.run_id)
    ghosted = run.ghosted or paint_state.is_run_ghosted(run.run_id)
    text_style_variant = (
        "scene_error"
        if paint_state.is_run_scene_error(run.run_id)
        else run.text_style_variant
    )
    if (
        active == run.active
        and ghosted == run.ghosted
        and text_style_variant == run.text_style_variant
    ):
        return run
    return replace(
        run,
        active=active,
        ghosted=ghosted,
        text_style_variant=text_style_variant,
    )


def effective_token_for_paint(
    projection_document: PromptProjectionDocument,
    paint_state: PromptProjectionPaintState,
    token_id: str | None,
) -> PromptProjectionToken | None:
    """Return one token with geometry-neutral paint flags applied."""

    token = projection_document.token_by_id(token_id)
    if token is None:
        return None
    active = token.active or paint_state.is_token_active(token.token_id)
    decoration_accented = (
        token.decoration_accented
        or paint_state.is_token_decoration_accented(token.token_id)
    )
    if active == token.active and decoration_accented == token.decoration_accented:
        return token
    return replace(
        token,
        active=active,
        decoration_accented=decoration_accented,
    )


__all__ = [
    "PromptProjectionPaintInput",
    "PromptProjectionPaintStyleKey",
    "effective_run_for_paint",
    "effective_token_for_paint",
]
