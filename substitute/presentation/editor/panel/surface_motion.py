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

"""Apply editor-specific Fluent policy to shared structural surface motion."""

from __future__ import annotations

from typing import cast

from PySide6.QtWidgets import QWidget

from substitute.presentation.motion import (
    FLUENT_ENTRANCE_EASING_CURVE,
    FLUENT_EXIT_EASING_CURVE,
    FLUENT_FAST_DURATION_MS,
    FLUENT_NORMAL_DURATION_MS,
    FLUENT_POINT_TO_POINT_EASING_CURVE,
    MotionSpec,
    MotionTelemetry,
    MotionClockFactory,
    SurfaceMotionController,
)

_EDITOR_ENTRANCE_SPEC = MotionSpec(
    duration_ms=FLUENT_NORMAL_DURATION_MS,
    stagger_ms=16,
    translation_y=16.0,
    start_opacity=0.0,
    easing=FLUENT_ENTRANCE_EASING_CURVE,
)
_EDITOR_REPOSITION_SPEC = MotionSpec(
    duration_ms=FLUENT_NORMAL_DURATION_MS,
    stagger_ms=0,
    translation_y=0.0,
    start_opacity=1.0,
    easing=FLUENT_POINT_TO_POINT_EASING_CURVE,
)
_EDITOR_EXIT_SPEC = MotionSpec(
    duration_ms=FLUENT_FAST_DURATION_MS,
    stagger_ms=0,
    translation_y=0.0,
    start_opacity=1.0,
    easing=FLUENT_EXIT_EASING_CURVE,
)


class EditorSurfaceMotionController:
    """Coordinate cube and node-card transitions for one editor viewport."""

    def __init__(
        self,
        panel: object,
        *,
        clock_factory: MotionClockFactory | None = None,
    ) -> None:
        """Bind shared motion to the panel viewport without owning workflow state."""

        self._panel = panel
        self._motion = SurfaceMotionController(
            viewport_provider=self._viewport,
            default_spec=_EDITOR_ENTRANCE_SPEC,
            clock_factory=clock_factory,
        )

    @property
    def telemetry(self) -> MotionTelemetry:
        """Return shared motion qualification counters and timings."""

        return self._motion.telemetry

    def prepare_cube_insert(
        self,
        cube_alias: str,
        *,
        replace_node_cards: bool = False,
    ) -> int | None:
        """Capture cube or card geometry before an incremental insertion."""

        widgets = (
            self._node_card_targets(cube_alias)
            if replace_node_cards
            else self._cube_targets()
        )
        return self._motion.prepare(
            reason=f"cube_insert:{cube_alias}",
            widgets=widgets,
        )

    def present_cube_insert(
        self,
        *,
        generation: int | None,
        cube_alias: str,
        cube_widget: object,
    ) -> bool:
        """Animate the inserted cube and every displaced existing cube."""

        if generation is None or not isinstance(cube_widget, QWidget):
            self._motion.cancel(reason="cube_insert_not_presentable")
            return False
        self._activate_layout()
        return self._motion.animate_layout(
            generation=generation,
            widgets=self._cube_targets(),
            spec=_EDITOR_ENTRANCE_SPEC,
        )

    def present_node_cards(
        self,
        *,
        generation: int,
        cube_alias: str,
        cards: tuple[tuple[str, QWidget], ...],
    ) -> bool:
        """Present committed node cards with bounded staggered entrance motion."""

        return self._motion.animate_layout(
            generation=generation,
            widgets=tuple(
                (f"node-card:{cube_alias}:{node_name}", card)
                for node_name, card in cards
            ),
            spec=_EDITOR_ENTRANCE_SPEC,
        )

    def present_node_card_replacement(
        self,
        *,
        generation: int | None,
        cube_alias: str,
    ) -> bool:
        """Animate replacement cards from their prior structural positions."""

        if generation is None:
            self._motion.cancel(reason="node_card_replacement_not_presentable")
            return False
        cards = self._node_card_targets(cube_alias)
        if not cards:
            self._motion.cancel(reason="node_card_replacement_has_no_targets")
            return False
        self._activate_layout()
        return self._motion.animate_layout(
            generation=generation,
            widgets=cards,
            spec=_EDITOR_ENTRANCE_SPEC,
        )

    def prepare_cube_reorder(self) -> int | None:
        """Capture cube geometry before the root stack order changes."""

        return self._motion.prepare(
            reason="cube_reorder",
            widgets=self._cube_targets(),
        )

    def present_cube_reorder(self, generation: int | None) -> bool:
        """Slide retained cubes to their committed stack positions."""

        if generation is None:
            return False
        self._activate_layout()
        return self._motion.animate_layout(
            generation=generation,
            widgets=self._cube_targets(),
            spec=_EDITOR_REPOSITION_SPEC,
        )

    def prepare_cube_removal(self, cube_alias: str) -> int | None:
        """Capture the departing cube and retained stack before removal."""

        targets = list(self._cube_targets())
        widgets = getattr(self._panel, "cube_widgets", {})
        departing = widgets.get(cube_alias) if isinstance(widgets, dict) else None
        departing_identity = f"cube:{cube_alias}"
        if isinstance(departing, QWidget) and all(
            identity != departing_identity for identity, _widget in targets
        ):
            targets.append((departing_identity, departing))
        return self._motion.prepare(
            reason=f"cube_remove:{cube_alias}",
            widgets=tuple(targets),
        )

    def present_cube_removal(self, generation: int | None) -> bool:
        """Fade the removed cube while closing the committed stack gap."""

        if generation is None:
            return False
        self._activate_layout()
        return self._motion.animate_layout(
            generation=generation,
            widgets=self._cube_targets(),
            spec=_EDITOR_EXIT_SPEC,
            exit_translation_y=-8.0,
        )

    def prepare_projection_reveal(self) -> int | None:
        """Capture visible cubes before publishing projected sections."""

        return self._motion.prepare(
            reason="projection_reveal",
            widgets=self._cube_targets(),
        )

    def present_projection_reveal(self, generation: int | None) -> bool:
        """Fade and slide projected cubes into the committed editor stack."""

        if generation is None:
            return False
        self._activate_layout()
        return self._motion.animate_layout(
            generation=generation,
            widgets=self._cube_targets(),
            spec=_EDITOR_ENTRANCE_SPEC,
        )

    def cancel(self, *, reason: str) -> None:
        """Settle active motion immediately without changing committed state."""

        self._motion.cancel(reason=reason)

    def is_animating(self) -> bool:
        """Return whether one editor surface transition is visible."""

        return self._motion.is_animating()

    def _cube_targets(self) -> tuple[tuple[str, QWidget], ...]:
        """Return mounted cubes in authoritative stack order."""

        widgets = getattr(self._panel, "cube_widgets", {})
        if not isinstance(widgets, dict):
            return ()
        stack_order = getattr(self._panel, "_stack_order", None) or tuple(widgets)
        return tuple(
            (f"cube:{alias}", widget)
            for alias in stack_order
            if isinstance((widget := widgets.get(alias)), QWidget)
        )

    def _node_card_targets(
        self,
        cube_alias: str,
    ) -> tuple[tuple[str, QWidget], ...]:
        """Return mounted cards for one cube in registry order."""

        wrappers = getattr(self._panel, "card_wrappers", {})
        if not isinstance(wrappers, dict):
            return ()
        return tuple(
            (f"node-card:{cube_alias}:{node_name}", wrapper)
            for key, wrapper in wrappers.items()
            if (
                isinstance(key, tuple)
                and len(key) == 2
                and key[0] == cube_alias
                and isinstance(node_name := key[1], str)
                and isinstance(wrapper, QWidget)
            )
        )

    def _activate_layout(self) -> None:
        """Resolve final widget geometry before capturing committed endpoints."""

        layout = getattr(self._panel, "_layout", None)
        activate = getattr(layout, "activate", None)
        if callable(activate):
            activate()

    def _viewport(self) -> QWidget | None:
        """Return the live editor scroll viewport when mounted."""

        scroll = getattr(self._panel, "scroll", None)
        viewport = getattr(scroll, "viewport", None)
        if not callable(viewport):
            return None
        return cast(QWidget, viewport())


__all__ = ["EditorSurfaceMotionController"]
