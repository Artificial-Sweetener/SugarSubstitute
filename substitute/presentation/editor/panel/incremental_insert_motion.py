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

"""Coordinate optional motion around incremental editor commits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

IncrementalInsertMotionTarget = Literal["cube", "node_cards"]


class IncrementalInsertMotionPort(Protocol):
    """Describe visual motion available after functional insertion."""

    def prepare_cube_insert(self, cube_alias: str) -> int | None:
        """Capture visible pre-commit state for one cube insertion."""

    def present_cube_insert(
        self,
        *,
        generation: int | None,
        cube_alias: str,
        cube_widget: object,
    ) -> bool:
        """Present a committed cube without delaying functional completion."""

    def present_node_card_replacement(
        self,
        *,
        generation: int | None,
        cube_alias: str,
    ) -> bool:
        """Present committed node cards after one cube replacement."""

    def cancel(self, *, reason: str) -> None:
        """Settle active or prepared motion immediately."""


@dataclass(frozen=True, slots=True)
class PreparedIncrementalInsertMotion:
    """Describe motion prepared before an incremental structural commit."""

    generation: int | None = None
    target: IncrementalInsertMotionTarget | None = None


class EditorIncrementalInsertMotion:
    """Keep cosmetic transition policy outside functional insert orchestration."""

    def __init__(self, motion: IncrementalInsertMotionPort) -> None:
        """Store the shared surface-motion boundary."""

        self._motion = motion

    def prepare(
        self,
        *,
        requested: bool,
        cube_alias: str,
        creates_widget: bool,
        replaces_widget: bool,
    ) -> PreparedIncrementalInsertMotion:
        """Capture the old surface and classify the eventual visual target."""

        if not requested or not creates_widget:
            return PreparedIncrementalInsertMotion()
        generation = self._motion.prepare_cube_insert(cube_alias)
        if generation is None:
            return PreparedIncrementalInsertMotion()
        return PreparedIncrementalInsertMotion(
            generation=generation,
            target="node_cards" if replaces_widget else "cube",
        )

    def present_cube(
        self,
        *,
        prepared: PreparedIncrementalInsertMotion,
        already_started: bool,
        cube_alias: str,
        cube_widget: object,
    ) -> bool:
        """Start a new-cube transition at the first usable commit."""

        if already_started or prepared.target != "cube":
            return already_started
        return self._motion.present_cube_insert(
            generation=prepared.generation,
            cube_alias=cube_alias,
            cube_widget=cube_widget,
        )

    def present_node_cards(
        self,
        *,
        prepared: PreparedIncrementalInsertMotion,
        already_started: bool,
        cube_alias: str,
    ) -> bool:
        """Start replacement-card motion after the final functional commit."""

        if already_started or prepared.target != "node_cards":
            return already_started
        return self._motion.present_node_card_replacement(
            generation=prepared.generation,
            cube_alias=cube_alias,
        )

    def cancel(self) -> None:
        """Settle any prepared or active insert transition."""

        self._motion.cancel(reason="incremental_insert_cancelled")


__all__ = [
    "EditorIncrementalInsertMotion",
    "IncrementalInsertMotionPort",
    "IncrementalInsertMotionTarget",
    "PreparedIncrementalInsertMotion",
]
