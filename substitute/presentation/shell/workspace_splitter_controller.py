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

"""Own canonical workflow/canvas splitter geometry and transient width transfer."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QSplitter, QWidget


_DETAILS_MINIMUM_WIDTH = 1
_CANVAS_MINIMUM_WIDTH = 100


@dataclass(frozen=True, slots=True)
class _PresentationOrigin:
    """Capture fixed geometry used for one drift-free presentation transition."""

    sizes: tuple[int, ...]
    stack_width: int
    details_index: int
    canvas_index: int


class WorkspaceSplitterController:
    """Separate durable layout geometry from temporary stack presentation frames."""

    def __init__(
        self,
        *,
        splitter: QSplitter,
        details_widget: QWidget,
        canvas_widget: QWidget,
    ) -> None:
        """Store the production splitter hierarchy owned by the workspace shell."""

        self._splitter = splitter
        self._details_widget = details_widget
        self._canvas_widget = canvas_widget
        self._remembered_sizes: tuple[int, ...] = ()
        self._presentation_origin: _PresentationOrigin | None = None

    @property
    def remembered_sizes(self) -> tuple[int, ...]:
        """Return canonical splitter sizes last owned by restore or user movement."""

        return self._remembered_sizes

    def current_sizes(self) -> tuple[int, ...]:
        """Return live Qt splitter sizes as immutable plain integers."""

        return tuple(int(size) for size in self._splitter.sizes())

    def remember_sizes(self, sizes: tuple[int, ...]) -> bool:
        """Store valid canonical sizes without applying transient presentation state."""

        normalized = tuple(int(size) for size in sizes)
        if len(normalized) < 2:
            return False
        self._remembered_sizes = normalized
        return True

    def sizes_for_snapshot(
        self,
        *,
        effective_stack_width: int,
        preferred_stack_width: int,
    ) -> tuple[int, ...]:
        """Return cube-preference geometry even while the active stack is unavailable."""

        if self._remembered_sizes:
            return self._remembered_sizes
        return self.canonical_sizes(
            self.current_sizes(),
            effective_stack_width=effective_stack_width,
            preferred_stack_width=preferred_stack_width,
        )

    def apply_durable_sizes(self, sizes: tuple[int, ...]) -> bool:
        """Apply and remember validated canonical sizes at a restore boundary."""

        normalized = tuple(int(size) for size in sizes)
        if len(normalized) < 2:
            return False
        self._splitter.setSizes(list(normalized))
        self._remembered_sizes = normalized
        self._presentation_origin = None
        return True

    def remember_user_geometry(
        self,
        *,
        effective_stack_width: int,
        preferred_stack_width: int,
    ) -> tuple[int, ...]:
        """Normalize a user drag to the durable cube-preference coordinate space."""

        canonical = self.canonical_sizes(
            self.current_sizes(),
            effective_stack_width=effective_stack_width,
            preferred_stack_width=preferred_stack_width,
        )
        self.remember_sizes(canonical)
        return canonical

    def begin_stack_width_transition(self, stack_width: int) -> bool:
        """Capture live geometry as the fixed origin for a retargeted transition."""

        sizes = self.current_sizes()
        details_index = self._splitter.indexOf(self._details_widget)
        canvas_index = self._splitter.indexOf(self._canvas_widget)
        if (
            details_index < 0
            or canvas_index < 0
            or details_index >= len(sizes)
            or canvas_index >= len(sizes)
        ):
            self._presentation_origin = None
            return False
        self._presentation_origin = _PresentationOrigin(
            sizes=sizes,
            stack_width=max(0, int(stack_width)),
            details_index=details_index,
            canvas_index=canvas_index,
        )
        return True

    def apply_stack_width_frame(self, stack_width: int) -> tuple[int, ...]:
        """Transfer stack-width delta from details to canvas from one fixed origin."""

        origin = self._presentation_origin
        if origin is None:
            self.begin_stack_width_transition(stack_width)
            return self.current_sizes()

        requested_delta = int(stack_width) - origin.stack_width
        details_start = origin.sizes[origin.details_index]
        canvas_start = origin.sizes[origin.canvas_index]
        minimum_delta = _DETAILS_MINIMUM_WIDTH - details_start
        maximum_delta = canvas_start - _CANVAS_MINIMUM_WIDTH
        applied_delta = max(minimum_delta, min(maximum_delta, requested_delta))

        sizes = list(origin.sizes)
        sizes[origin.details_index] = details_start + applied_delta
        sizes[origin.canvas_index] = canvas_start - applied_delta
        self._splitter.setSizes(sizes)
        return tuple(sizes)

    def finish_stack_width_transition(self) -> None:
        """Release transient origin geometry after the exact endpoint is committed."""

        self._presentation_origin = None

    def canonical_sizes(
        self,
        sizes: tuple[int, ...],
        *,
        effective_stack_width: int,
        preferred_stack_width: int,
    ) -> tuple[int, ...]:
        """Translate live sizes into the user's durable cube-preference geometry."""

        normalized = tuple(int(size) for size in sizes)
        details_index = self._splitter.indexOf(self._details_widget)
        canvas_index = self._splitter.indexOf(self._canvas_widget)
        if (
            details_index < 0
            or canvas_index < 0
            or details_index >= len(normalized)
            or canvas_index >= len(normalized)
        ):
            return normalized

        delta = max(0, int(preferred_stack_width)) - max(0, int(effective_stack_width))
        canonical = list(normalized)
        transferable = min(
            delta, max(0, canonical[canvas_index] - _CANVAS_MINIMUM_WIDTH)
        )
        canonical[details_index] += transferable
        canonical[canvas_index] -= transferable
        return tuple(canonical)


__all__ = ["WorkspaceSplitterController"]
