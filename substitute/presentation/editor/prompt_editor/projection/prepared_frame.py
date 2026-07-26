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

"""Publish one immutable prompt layout as prepared geometry and paint inputs."""

from __future__ import annotations

from PySide6.QtGui import QFont, QPalette
from PySide6.QtCore import QRectF

from substitute.application.appearance import SemanticPalette

from ..geometry.aggregate import PromptProjectionGeometry
from ..geometry.state import PromptProjectionGeometryInput
from ..layout.contracts import (
    PromptLayoutDamage,
    PromptLayoutOutcome,
    PromptLayoutOutput,
)
from ..layout.state import PromptLayoutState
from .content_inline_bindings import (
    PromptProjectionBaseInlineBindings,
    prepare_base_inline_bindings,
)
from .content_text_styles import (
    PromptProjectionBaseTextStyles,
    prepare_base_text_styles,
)
from .content_selection_layer import (
    PromptProjectionSelectionLayer,
    prepare_projection_selection_layer,
)
from ..core.projection.caret import PromptProjectionSelection
from .paint_input import PromptProjectionPaintInput
from .paint_state import (
    PromptProjectionPaintState,
    empty_projection_paint_state,
)


class PromptProjectionPreparedFrame:
    """Own atomic layout publication and its exact derived presentation inputs."""

    __slots__ = (
        "_geometry",
        "_base_inline_bindings",
        "_base_text_styles",
        "_layout_state",
        "_paint_input",
        "_paint_state",
        "_palette",
        "_projection_run_ids",
        "_projection_token_ids",
        "_semantic_palette",
    )

    def __init__(
        self,
        output: PromptLayoutOutput,
        *,
        paint_state: PromptProjectionPaintState | None = None,
        palette: QPalette | None = None,
        semantic_palette: SemanticPalette | None = None,
    ) -> None:
        """Prepare all downstream references from one complete layout output."""

        self._layout_state = PromptLayoutState(output)
        self._paint_state = (
            empty_projection_paint_state() if paint_state is None else paint_state
        )
        self._palette = QPalette() if palette is None else QPalette(palette)
        self._semantic_palette = semantic_palette
        self._base_inline_bindings: PromptProjectionBaseInlineBindings
        self._base_text_styles: PromptProjectionBaseTextStyles
        self._publish_geometry()

    @property
    def output(self) -> PromptLayoutOutput:
        """Return the exact atomically published layout output."""

        return self._layout_state.current

    @property
    def geometry(self) -> PromptProjectionGeometry:
        """Return query owners bound to the current immutable layout."""

        return self._geometry

    @property
    def paint_state(self) -> PromptProjectionPaintState:
        """Return the geometry-neutral visual state layered over the layout."""

        return self._paint_state

    @property
    def paint_input(self) -> PromptProjectionPaintInput:
        """Return the complete prepared input for projection painting."""

        return self._paint_input

    def publish(
        self,
        outcome: PromptLayoutOutcome,
        *,
        reset_paint_state: bool = False,
    ) -> PromptLayoutDamage:
        """Atomically publish one applied engine outcome and derived inputs."""

        if reset_paint_state:
            self._paint_state = empty_projection_paint_state()
        damage = self._layout_state.publish(outcome)
        self._publish_geometry()
        return damage

    def restore(
        self,
        output: PromptLayoutOutput,
        *,
        reset_paint_state: bool = True,
    ) -> None:
        """Publish one validated immutable output and rebuild derived inputs."""

        if (
            output.configuration.inline_object_renderers
            is not self.output.configuration.inline_object_renderers
        ):
            raise ValueError(
                "restored layout output uses a different renderer registry"
            )
        if reset_paint_state:
            self._paint_state = empty_projection_paint_state()
        self._layout_state.restore(output)
        self._publish_geometry()

    def fork(self, output: PromptLayoutOutput) -> PromptProjectionPreparedFrame:
        """Return an independent publication owner sharing immutable references."""

        return PromptProjectionPreparedFrame(
            output,
            paint_state=self._paint_state,
            palette=self._palette,
            semantic_palette=self._semantic_palette,
        )

    def set_paint_state(self, paint_state: PromptProjectionPaintState) -> None:
        """Replace geometry-neutral visual state without rebuilding geometry."""

        if not self.try_set_paint_state(paint_state):
            raise ValueError("paint state references unknown projection ids")

    def try_set_paint_state(self, paint_state: PromptProjectionPaintState) -> bool:
        """Publish paint state only when every referenced projection id exists."""

        if not paint_state.references_only(
            token_ids=self._projection_token_ids,
            run_ids=self._projection_run_ids,
        ):
            return False
        self._paint_state = paint_state
        self._publish_paint_input()
        return True

    def set_palette(self, palette: QPalette) -> None:
        """Publish a changed Qt palette without rebuilding identical paint input."""

        if int(self._palette.cacheKey()) == int(palette.cacheKey()):
            return
        self._palette = QPalette(palette)
        self._publish_base_text_styles()
        self._publish_paint_input()

    def set_semantic_palette(self, palette: SemanticPalette | None) -> None:
        """Publish changed semantic colors without rebuilding identical paint input."""

        if self._semantic_palette == palette:
            return
        self._semantic_palette = palette
        self._publish_base_text_styles()
        self._publish_paint_input()

    def prepare_selection_layer(
        self,
        selection: PromptProjectionSelection,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> PromptProjectionSelectionLayer:
        """Prepare viewport-bounded selection commands for this exact frame."""

        return prepare_projection_selection_layer(
            selection,
            geometry=self._geometry,
            layout_snapshot=self.output.snapshot,
            inline_bindings=self._base_inline_bindings,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            palette=self._palette,
        )

    def _publish_geometry(self) -> None:
        """Bind geometry queries to the exact current layout references."""

        output = self.output
        configuration = output.configuration
        snapshot = output.snapshot
        projection_document = output.projection_document
        self._projection_token_ids = frozenset(
            token.token_id for token in projection_document.tokens
        )
        self._projection_run_ids = frozenset(
            run.run_id for run in projection_document.runs
        )
        self._geometry = PromptProjectionGeometry(
            PromptProjectionGeometryInput(
                projection_document=projection_document,
                layout_snapshot=snapshot,
                base_font=QFont(configuration.base_font),
                document_margin=configuration.document_margin,
                metrics=configuration.metrics,
                text_width=configuration.text_width,
                inline_object_renderers=configuration.inline_object_renderers,
                layout_identity=id(snapshot),
            )
        )
        self._base_inline_bindings = prepare_base_inline_bindings(
            projection_document,
            snapshot,
            renderers=configuration.inline_object_renderers,
        )
        self._publish_base_text_styles()
        self._publish_paint_input()

    def _publish_base_text_styles(self) -> None:
        """Prepare document-wide base run styles outside paint-state updates."""

        output = self.output
        self._base_text_styles = prepare_base_text_styles(
            output.projection_document,
            base_font=output.configuration.base_font,
            palette=self._palette,
            semantic_palette=self._semantic_palette,
        )

    def _publish_paint_input(self) -> None:
        """Bind painting to the exact current layout and visual state."""

        output = self.output
        self._paint_input = PromptProjectionPaintInput(
            projection_document=output.projection_document,
            layout_snapshot=output.snapshot,
            paint_state=self._paint_state,
            geometry=self._geometry,
            inline_object_renderers=(output.configuration.inline_object_renderers),
            base_font=output.configuration.base_font,
            palette=self._palette,
            semantic_palette=self._semantic_palette,
            base_inline_bindings=self._base_inline_bindings,
            base_text_styles=self._base_text_styles,
        )


__all__ = ["PromptProjectionPreparedFrame"]
