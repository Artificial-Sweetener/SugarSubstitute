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

"""Verify frame-coalesced stale-safe Output grid reflow."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_canvas_route_scope import (
    source_grid_route_identity,
)
from substitute.domain.workflow import (
    CanvasKind,
    CanvasSessionRevision,
    CanvasSessionToken,
    CanvasWorkflowIdentity,
    ImageMeta,
)
from substitute.presentation.canvas.output.output_grid_reflow_context import (
    OutputSourceGridContext,
)
from substitute.presentation.canvas.output.output_grid_reflow_controller import (
    OutputGridReflowController,
)
from substitute.presentation.canvas.output.output_grid_route_application_controller import (
    OutputGridApplicationResult,
)
from substitute.presentation.canvas.output.output_grid_scene_builder import (
    OutputGridSceneBuilder,
    OutputGridScenePlan,
)
from substitute.presentation.canvas.output.output_source_grid_composer import (
    OutputSourceGridComposer,
)
from substitute.presentation.canvas.shared.responsive_canvas_grid_policy import (
    CanvasViewportExtent,
)


def test_resize_burst_applies_once_using_latest_viewport() -> None:
    """Many resize signals should produce one application for the latest rect."""

    controller, timer, application, _context = _controller()

    for width in range(1001, 1201):
        controller.on_viewport_rect_changed(_rect(width, 500))
    assert application.payload_loads == []
    controller.deliver_pending()

    assert timer.starts == [16]
    assert len(application.plans) == 1
    assert len(application.payload_loads) == 4
    assert application.plans[0].layout_signature.dimensions[0] >= 2


def test_unchanged_topology_and_content_skips_recomposition() -> None:
    """Viewport changes retaining one signature should not reapply QPane routes."""

    controller, _timer, application, _context = _controller(tile_count=1)

    assert controller.present_current_grid(CanvasViewportExtent(800, 600)) is True
    assert controller.present_current_grid(CanvasViewportExtent(1600, 1200)) is True

    assert len(application.plans) == 1


def test_breakpoint_crossing_replaces_grid_once() -> None:
    """A topology change should publish exactly one replacement plan."""

    controller, _timer, application, _context = _controller(tile_count=2)

    controller.present_current_grid(CanvasViewportExtent(500, 1200))
    controller.present_current_grid(CanvasViewportExtent(1400, 500))

    assert [plan.layout_signature.dimensions for plan in application.plans] == [
        (1, 2),
        (2, 1),
    ]


def test_stale_pending_session_is_rejected() -> None:
    """A session change before timer delivery should reject pending geometry."""

    controller, _timer, application, context = _controller()
    controller.on_viewport_rect_changed(_rect(1200, 600))
    context.value = _source_context(revision=2)

    controller.deliver_pending()

    assert application.plans == []


def test_rejected_application_does_not_poison_signature_cache() -> None:
    """A rejected route should remain eligible for the next presentation attempt."""

    controller, _timer, application, _context = _controller()
    application.accept = False
    assert controller.present_current_grid(CanvasViewportExtent(1200, 600)) is False
    application.accept = True
    assert controller.present_current_grid(CanvasViewportExtent(1200, 600)) is True

    assert len(application.plans) == 2


def test_non_grid_context_schedules_no_timer() -> None:
    """Image, compare, and empty contexts should not schedule grid work."""

    controller, timer, application, context = _controller()
    context.value = None

    controller.on_viewport_rect_changed(_rect(1200, 600))
    controller.deliver_pending()

    assert timer.starts == []
    assert application.plans == []


def test_repeated_delivered_viewports_apply_only_first_signature() -> None:
    """Repeated timer generations within one topology should not reapply routes."""

    controller, timer, application, _context = _controller(tile_count=2)

    for width in range(900, 1000, 5):
        controller.on_viewport_rect_changed(_rect(width, 500))
        controller.deliver_pending()
        timer.active = False

    assert len(application.plans) == 1


def test_cancel_stops_timer_and_discards_pending_generation() -> None:
    """Teardown cancellation should prevent queued viewport delivery."""

    controller, timer, application, _context = _controller()
    controller.on_viewport_rect_changed(_rect(1200, 500))

    controller.cancel()
    controller.deliver_pending()

    assert timer.active is False
    assert application.plans == []


class _Timer:
    """Record single-shot timer state for reflow tests."""

    def __init__(self) -> None:
        """Create an inactive timer."""

        self.active = False
        self.starts: list[int] = []

    def start(self, interval_ms: int) -> None:
        """Record one timer start."""

        self.active = True
        self.starts.append(interval_ms)

    def stop(self) -> None:
        """Stop pending delivery."""

        self.active = False

    def isActive(self) -> bool:  # noqa: N802
        """Return whether the timer is pending."""

        return self.active


@dataclass(slots=True)
class _Context:
    """Expose mutable current context for stale-delivery tests."""

    value: OutputSourceGridContext | None

    def current_context(self) -> OutputSourceGridContext | None:
        """Return the configured current context."""

        return self.value


class _Application:
    """Record prepared plans and optionally reject them."""

    def __init__(self) -> None:
        """Create an accepting application recorder."""

        self.accept = True
        self.plans: list[OutputGridScenePlan] = []
        self.payload_loads: list[UUID] = []

    def apply(
        self, plan: OutputGridScenePlan, *, activate: bool
    ) -> OutputGridApplicationResult:
        """Record and return the configured application result."""

        assert activate is True
        self.plans.append(plan)
        return OutputGridApplicationResult(
            accepted=self.accept,
            composition_id=uuid4() if self.accept else None,
            layout_signature=plan.layout_signature if self.accept else None,
        )


def _controller(
    *, tile_count: int = 4
) -> tuple[OutputGridReflowController, _Timer, _Application, _Context]:
    """Build a reflow controller with deterministic source-grid collaborators."""

    context = _Context(_source_context(tile_count=tile_count))
    timer = _Timer()
    application = _Application()
    payloads = {
        item.image_id: SimpleNamespace(
            size=lambda: SimpleNamespace(width=lambda: 512, height=lambda: 512)
        )
        for item in cast(
            OutputSourceGridContext, context.value
        ).source.images_by_set.values()
    }

    def payload_lookup(image_id: UUID) -> object | None:
        """Record bounded cached payload reads performed during one planning pass."""

        application.payload_loads.append(image_id)
        return payloads.get(image_id)

    source_composer = OutputSourceGridComposer(
        payload_lookup,
        scene_builder=OutputGridSceneBuilder(),
        viewport_extent=lambda: CanvasViewportExtent(1, 1),
    )
    controller = OutputGridReflowController(
        timer=timer,
        context_resolver=cast(Any, context),
        source_composer=source_composer,
        scene_composer=cast(Any, object()),
        route_application=cast(Any, application),
    )
    return controller, timer, application, context


def _source_context(
    *, revision: int = 1, tile_count: int = 4
) -> OutputSourceGridContext:
    """Return one authorized source-grid context."""

    source = OutputCanvasSourceGroup(
        source_key="source-a",
        label="Source A",
        images_by_set={
            index: OutputCanvasImageItem(
                image_id=uuid4(),
                image_meta=ImageMeta("wf", "Source A", index, "", ""),
                set_index=index,
            )
            for index in range(1, tile_count + 1)
        },
    )
    route = source_grid_route_identity(source_key="source-a", active_scene_key=None)
    token = CanvasSessionToken(
        CanvasWorkflowIdentity("wf"),
        CanvasKind.OUTPUT,
        CanvasSessionRevision(revision),
        route,
    )
    return OutputSourceGridContext(token, route, source, None)


def _rect(width: float, height: float) -> object:
    """Return a QRectF-like viewport double."""

    return SimpleNamespace(width=lambda: width, height=lambda: height)
