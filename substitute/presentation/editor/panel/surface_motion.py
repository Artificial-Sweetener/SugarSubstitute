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

"""Apply editor-specific policy to shared structural surface motion."""

from __future__ import annotations

from typing import cast

from PySide6.QtWidgets import QWidget

from substitute.presentation.motion import MotionSpec, SurfaceMotionController

_EDITOR_INSERT_SPEC = MotionSpec(
    duration_ms=190,
    stagger_ms=16,
    translation_y=16.0,
    start_opacity=0.0,
)


class EditorSurfaceMotionController:
    """Coordinate optional cube and node-card transitions for one editor viewport."""

    def __init__(self, panel: object) -> None:
        """Bind shared motion to the panel viewport without owning workflow state."""

        self._panel = panel
        self._motion = SurfaceMotionController(
            viewport_provider=self._viewport,
            default_spec=_EDITOR_INSERT_SPEC,
        )

    @property
    def telemetry(self) -> object:
        """Return shared motion qualification counters and timings."""

        return self._motion.telemetry

    def prepare_cube_insert(self, cube_alias: str) -> int | None:
        """Capture the visible surface before a user-requested cube insertion."""

        return self._motion.prepare(reason=f"cube_insert:{cube_alias}")

    def present_cube_insert(
        self,
        *,
        generation: int | None,
        cube_alias: str,
        cube_widget: object,
    ) -> bool:
        """Present one committed visible cube through the shared motion layer."""

        if generation is None or not isinstance(cube_widget, QWidget):
            self._motion.cancel(reason="cube_insert_not_presentable")
            return False
        return self._motion.animate_widgets(
            generation=generation,
            widgets=((f"cube:{cube_alias}", cube_widget),),
        )

    def present_node_cards(
        self,
        *,
        generation: int,
        cube_alias: str,
        cards: tuple[tuple[str, QWidget], ...],
    ) -> bool:
        """Present committed node cards using the same bounded timeline and overlay."""

        return self._motion.animate_widgets(
            generation=generation,
            widgets=tuple(
                (f"node-card:{cube_alias}:{node_name}", card)
                for node_name, card in cards
            ),
        )

    def present_node_card_replacement(
        self,
        *,
        generation: int | None,
        cube_alias: str,
    ) -> bool:
        """Present all committed cards in a replaced cube as staggered targets."""

        if generation is None:
            self._motion.cancel(reason="node_card_replacement_not_presentable")
            return False
        wrappers = getattr(self._panel, "card_wrappers", {})
        if not isinstance(wrappers, dict):
            self._motion.cancel(reason="node_card_registry_unavailable")
            return False
        cards = tuple(
            (str(node_name), wrapper)
            for key, wrapper in wrappers.items()
            if (
                isinstance(key, tuple)
                and len(key) == 2
                and key[0] == cube_alias
                and isinstance(node_name := key[1], str)
                and isinstance(wrapper, QWidget)
            )
        )
        if not cards:
            self._motion.cancel(reason="node_card_replacement_has_no_targets")
            return False
        return self.present_node_cards(
            generation=generation,
            cube_alias=cube_alias,
            cards=cards,
        )

    def cancel(self, *, reason: str) -> None:
        """Settle active motion immediately without changing committed state."""

        self._motion.cancel(reason=reason)

    def is_animating(self) -> bool:
        """Return whether one editor surface transition is visible."""

        return self._motion.is_animating()

    def _viewport(self) -> QWidget | None:
        """Return the live editor scroll viewport when mounted."""

        scroll = getattr(self._panel, "scroll", None)
        viewport = getattr(scroll, "viewport", None)
        if not callable(viewport):
            return None
        return cast(QWidget, viewport())


__all__ = ["EditorSurfaceMotionController"]
