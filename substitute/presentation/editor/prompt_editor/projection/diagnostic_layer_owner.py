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

"""Publish immutable diagnostic commands before prompt-editor paint events."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace
from time import perf_counter
from typing import Final

from PySide6.QtCore import QObject, QRectF, QTimer

from substitute.application.prompt_editor.diagnostics.models import PromptDiagnostic
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionSelection,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptLayoutIdentity,
)
from substitute.presentation.editor.prompt_editor.geometry.aggregate import (
    PromptProjectionGeometry,
)
from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    prompt_editor_work_event,
)

from .diagnostic_fragment_cache import diagnostic_viewport_identity
from .diagnostic_layer_assets import PromptDiagnosticLayerAssetPreparer
from .diagnostic_layer_preparer import PromptDiagnosticLayerPreparer
from .diagnostic_render_layer import (
    EMPTY_DIAGNOSTIC_RENDER_LAYER,
    PromptDiagnosticLayerKey,
    PromptDiagnosticRenderLayer,
)
from .diagnostic_layer_state import (
    PromptDiagnosticLayerSnapshot,
    PromptDiagnosticWarmState,
)

_DIAGNOSTIC_FRAGMENT_WARM_BUDGET_MS: Final[float] = 4.0
_DIAGNOSTIC_FRAGMENT_WARM_BATCH_LIMIT: Final[int] = 4


class PromptDiagnosticLayerOwner:
    """Own diagnostic command preparation, warming, and publication."""

    def __init__(
        self,
        *,
        parent: QObject,
        diagnostics: Callable[[], Sequence[PromptDiagnostic]],
        selection: Callable[[], PromptProjectionSelection],
        geometry: Callable[[], PromptProjectionGeometry],
        layout_identity: Callable[[], PromptLayoutIdentity | None],
        viewport_rect: Callable[[], QRectF],
        scroll_offset: Callable[[], float],
        color_rgba: Callable[[], int],
        device_pixel_ratio: Callable[[], float],
        is_alive: Callable[[], bool],
        request_update: Callable[[], None],
    ) -> None:
        """Bind narrow state queries used only at explicit refresh boundaries."""

        self._diagnostics = diagnostics
        self._selection = selection
        self._geometry = geometry
        self._layout_identity = layout_identity
        self._viewport_rect = viewport_rect
        self._scroll_offset = scroll_offset
        self._color_rgba = color_rgba
        self._device_pixel_ratio = device_pixel_ratio
        self._is_alive = is_alive
        self._request_update = request_update
        self._preparer = PromptDiagnosticLayerPreparer()
        self._assets = PromptDiagnosticLayerAssetPreparer()
        self._layer = EMPTY_DIAGNOSTIC_RENDER_LAYER
        self._key: PromptDiagnosticLayerKey | None = None
        self._warm_timer = QTimer(parent)
        self._warm_timer.setSingleShot(True)
        self._warm_timer.setInterval(0)
        self._warm_timer.timeout.connect(self._warm_missing_fragments)
        self._warm_index = 0
        self._warm_state: PromptDiagnosticWarmState | None = None

    @property
    def layer(self) -> PromptDiagnosticRenderLayer:
        """Return the currently published immutable diagnostic layer."""

        return self._layer

    def refresh(self, *, reason: str) -> None:
        """Prepare and publish the current diagnostic layer outside paint."""

        del reason
        if not self._is_alive():
            return
        diagnostics = tuple(self._diagnostics())
        if not diagnostics:
            self.stop_warm()
            self._key = None
            self._publish(EMPTY_DIAGNOSTIC_RENDER_LAYER)
            return
        layout_identity = self._layout_identity()
        if layout_identity is None:
            self.stop_warm()
            self._key = None
            self._publish(EMPTY_DIAGNOSTIC_RENDER_LAYER)
            return

        geometry = self._geometry()
        viewport_rect = QRectF(self._viewport_rect())
        scroll_offset = self._scroll_offset()
        selection = self._selection()
        color_rgba = self._color_rgba()
        device_pixel_ratio = max(1.0, self._device_pixel_ratio())
        visible_diagnostics = self._preparer.visible_diagnostics(
            diagnostics,
            geometry=geometry,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )
        viewport_identity = diagnostic_viewport_identity(
            layout_identity=layout_identity,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )
        snapshot = PromptDiagnosticLayerSnapshot.capture(
            visible_diagnostics=visible_diagnostics,
            selection=selection,
            geometry=geometry,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            layout_identity=layout_identity,
            viewport_identity=viewport_identity,
            color_rgba=color_rgba,
            device_pixel_ratio=device_pixel_ratio,
        )
        if snapshot.key == self._key:
            return

        self.stop_warm()
        layer, missing_diagnostics = self._preparer.prepare_visible_cached(
            diagnostics=snapshot.visible_diagnostics,
            selection=snapshot.selection,
            preview_geometry=None,
            viewport_rect=snapshot.viewport_rect,
            scroll_offset=snapshot.scroll_offset,
            layout_identity=snapshot.layout_identity,
            color_rgba=snapshot.color_rgba,
        )
        layer = self._assets.prepare(
            layer,
            device_pixel_ratio=snapshot.device_pixel_ratio,
        )
        layer = replace(layer, revision=snapshot.key)
        self._key = snapshot.key
        self._publish(layer)
        if not missing_diagnostics:
            return
        self._warm_state = PromptDiagnosticWarmState(
            snapshot=snapshot,
            missing_diagnostics=missing_diagnostics,
        )
        self._warm_timer.start(0)

    def stop_warm(self) -> None:
        """Stop pending diagnostic cache warming."""

        self._warm_timer.stop()
        self._warm_index = 0
        self._warm_state = None

    @prompt_editor_work_event(PromptEditorWorkEvent.DIAGNOSTIC_FRAGMENT_LOOKUP)
    def fragments(
        self,
        diagnostic: PromptDiagnostic,
        *,
        geometry: PromptProjectionGeometry,
        viewport_rect: QRectF,
        scroll_offset: float,
        layout_identity: PromptLayoutIdentity,
    ) -> tuple[QRectF, ...]:
        """Return retained or newly prepared geometry for one diagnostic."""

        return self._preparer.fragments(
            diagnostic,
            geometry=geometry,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            layout_identity=layout_identity,
        )

    def clear_fragment_cache(self, *, reason: str) -> None:
        """Discard cached fragments and any layer built from their geometry."""

        del reason
        self.stop_warm()
        self._preparer.clear()
        self._key = None
        self._publish(EMPTY_DIAGNOSTIC_RENDER_LAYER)

    def preserve_fragment_cache_for_incremental_edit(
        self,
        *,
        diagnostics: Sequence[PromptDiagnostic],
        start: int,
        end: int,
        replacement_text: str,
        previous_layout_identity: PromptLayoutIdentity,
        next_layout_identity: PromptLayoutIdentity,
        fragment_y_delta: float = 0.0,
    ) -> None:
        """Keep unaffected diagnostic fragments after an accepted local edit."""

        self.stop_warm()
        self._key = None
        self._preparer.preserve_for_incremental_edit(
            diagnostics=diagnostics,
            start=start,
            end=end,
            replacement_text=replacement_text,
            previous_layout_identity=previous_layout_identity,
            next_layout_identity=next_layout_identity,
            fragment_y_delta=fragment_y_delta,
        )

    def _warm_missing_fragments(self) -> None:
        """Populate missing fragments in bounded GUI-thread chunks."""

        state = self._warm_state
        if state is None or not self._is_alive() or state.snapshot.key != self._key:
            return
        snapshot = state.snapshot
        started_at = perf_counter()
        warmed_count = 0
        while self._warm_index < len(state.missing_diagnostics):
            diagnostic = state.missing_diagnostics[self._warm_index]
            self._warm_index += 1
            if self._preparer.contains(
                diagnostic,
                layout_identity=snapshot.layout_identity,
                viewport_rect=snapshot.viewport_rect,
                scroll_offset=snapshot.scroll_offset,
            ):
                continue
            elapsed_ms = (perf_counter() - started_at) * 1000.0
            if (
                warmed_count >= _DIAGNOSTIC_FRAGMENT_WARM_BATCH_LIMIT
                or elapsed_ms >= _DIAGNOSTIC_FRAGMENT_WARM_BUDGET_MS
            ):
                self._warm_index -= 1
                break
            self.fragments(
                diagnostic,
                geometry=snapshot.geometry,
                viewport_rect=snapshot.viewport_rect,
                scroll_offset=snapshot.scroll_offset,
                layout_identity=snapshot.layout_identity,
            )
            warmed_count += 1
        if snapshot.key != self._key:
            return
        layer, _missing = self._preparer.prepare_visible_cached(
            diagnostics=snapshot.visible_diagnostics,
            selection=snapshot.selection,
            preview_geometry=None,
            viewport_rect=snapshot.viewport_rect,
            scroll_offset=snapshot.scroll_offset,
            layout_identity=snapshot.layout_identity,
            color_rgba=snapshot.color_rgba,
        )
        layer = self._assets.prepare(
            layer,
            device_pixel_ratio=snapshot.device_pixel_ratio,
        )
        layer = replace(layer, revision=snapshot.key)
        self._publish(layer)
        if self._warm_index < len(state.missing_diagnostics):
            self._warm_timer.start(0)
            return
        self._warm_state = None

    def _publish(self, layer: PromptDiagnosticRenderLayer) -> None:
        """Publish one changed immutable layer and request its repaint."""

        if layer == self._layer:
            return
        self._layer = layer
        self._request_update()


__all__ = ["PromptDiagnosticLayerOwner"]
