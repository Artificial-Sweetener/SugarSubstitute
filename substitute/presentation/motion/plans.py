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

"""Plan immutable entrance and structural surface transitions."""

from __future__ import annotations

from .capture import CapturedSurface
from .models import MotionSpec, MotionTarget


def plan_entrances(
    surfaces: tuple[CapturedSurface, ...],
    spec: MotionSpec,
) -> tuple[MotionTarget, ...]:
    """Return entrance targets translated from the committed endpoints."""

    return tuple(
        MotionTarget(
            identity=surface.identity,
            start_rect=surface.rect.translated(
                spec.translation_x,
                spec.translation_y,
            ),
            final_rect=surface.rect,
            snapshot=surface.snapshot,
            start_opacity=spec.start_opacity,
            order=surface.order,
        )
        for surface in surfaces
    )


def plan_layout_transition(
    prepared_surfaces: tuple[CapturedSurface, ...],
    final_surfaces: tuple[CapturedSurface, ...],
    spec: MotionSpec,
    *,
    exit_translation_y: float,
) -> tuple[MotionTarget, ...]:
    """Return targets for entering, moved, and exiting structural surfaces."""

    prepared_by_identity = {surface.identity: surface for surface in prepared_surfaces}
    final_by_identity = {surface.identity: surface for surface in final_surfaces}
    targets: list[MotionTarget] = []
    enter_order = 0
    for final in final_surfaces:
        prepared = prepared_by_identity.get(final.identity)
        if prepared is None:
            targets.append(
                MotionTarget(
                    identity=final.identity,
                    start_rect=final.rect.translated(
                        spec.translation_x,
                        spec.translation_y,
                    ),
                    final_rect=final.rect,
                    snapshot=final.snapshot,
                    start_opacity=spec.start_opacity,
                    order=enter_order,
                )
            )
            enter_order += 1
        elif prepared.rect != final.rect:
            targets.append(
                MotionTarget(
                    identity=final.identity,
                    start_rect=prepared.rect,
                    final_rect=final.rect,
                    snapshot=final.snapshot,
                )
            )
    for prepared in prepared_surfaces:
        if prepared.identity in final_by_identity:
            continue
        targets.append(
            MotionTarget(
                identity=prepared.identity,
                start_rect=prepared.rect,
                final_rect=prepared.rect.translated(0.0, exit_translation_y),
                snapshot=prepared.snapshot,
                final_opacity=0.0,
            )
        )
    return tuple(targets)


__all__ = ["plan_entrances", "plan_layout_transition"]
