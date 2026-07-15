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

"""Tests for pure shared canvas session identity and stale rejection."""

from __future__ import annotations

import uuid

import pytest

from substitute.domain.workflow.canvas_session import (
    CanvasGenerationIdentity,
    CanvasKind,
    CanvasRouteIdentity,
    CanvasSessionBoundary,
    CanvasSessionRejectionReason,
    InputCanvasSession,
    OutputCanvasSession,
)


def test_input_session_shape_has_no_generation_identity() -> None:
    """Input sessions explicitly carry no generation/run identity."""

    boundary = CanvasSessionBoundary()

    session = boundary.bind_input_session(
        workflow_id="wf-input",
        active_route=CanvasRouteIdentity.empty(),
    )

    assert isinstance(session, InputCanvasSession)
    assert session.canvas_kind is CanvasKind.INPUT
    assert not hasattr(session, "generation_identity")


def test_output_session_carries_generation_identity() -> None:
    """Output sessions can carry generation/run identity."""

    boundary = CanvasSessionBoundary()
    generation_identity = CanvasGenerationIdentity(
        generation_run_id="run-1",
        prompt_id="prompt-1",
        client_id="client-1",
    )

    session = boundary.bind_output_session(
        workflow_id="wf-output",
        active_route=CanvasRouteIdentity(
            route_kind="output_image",
            route_key="image:one",
        ),
        generation_identity=generation_identity,
    )

    assert isinstance(session, OutputCanvasSession)
    assert session.canvas_kind is CanvasKind.OUTPUT
    assert session.generation_identity == generation_identity


@pytest.mark.parametrize(
    ("generation_run_id", "prompt_id", "client_id"),
    (
        ("", "prompt-1", "client-1"),
        ("run-1", "", "client-1"),
        ("run-1", "prompt-1", ""),
    ),
)
def test_output_generation_identity_rejects_missing_fields(
    generation_run_id: str,
    prompt_id: str,
    client_id: str,
) -> None:
    """Output generation identity must be a complete identity packet."""

    with pytest.raises(ValueError):
        CanvasGenerationIdentity(
            generation_run_id=generation_run_id,
            prompt_id=prompt_id,
            client_id=client_id,
        )


def test_current_revision_authorizes_matching_display_mutation() -> None:
    """A current token authorizes mutation only for its matching route."""

    boundary = CanvasSessionBoundary()
    route = CanvasRouteIdentity(
        route_kind="output_image",
        route_key="image:one",
        primary_image_id=uuid.uuid4(),
    )
    session = boundary.bind_output_session(
        workflow_id="wf",
        active_route=route,
    )

    authorization = boundary.authorize_display_mutation(
        session.token(),
        canvas_kind=CanvasKind.OUTPUT,
        active_route=route,
    )

    assert authorization.accepted is True
    assert authorization.rejection_reason is None


def test_stale_revision_cannot_authorize_display_mutation() -> None:
    """A previous revision cannot authorize visible display mutation."""

    boundary = CanvasSessionBoundary()
    original_route = CanvasRouteIdentity(
        route_kind="output_image",
        route_key="image:one",
    )
    current_route = CanvasRouteIdentity(
        route_kind="output_image",
        route_key="image:two",
    )
    stale_token = boundary.bind_output_session(
        workflow_id="wf",
        active_route=original_route,
    ).token()

    boundary.bind_output_session(
        workflow_id="wf",
        active_route=current_route,
    )
    authorization = boundary.authorize_display_mutation(stale_token)

    assert authorization.accepted is False
    assert authorization.rejection_reason is CanvasSessionRejectionReason.STALE_REVISION


def test_stale_revision_cannot_authorize_its_original_route() -> None:
    """A stale token cannot mutate even when requesting its original route."""

    boundary = CanvasSessionBoundary()
    original_route = CanvasRouteIdentity(
        route_kind="output_image",
        route_key="image:one",
    )
    current_route = CanvasRouteIdentity(
        route_kind="output_image",
        route_key="image:two",
    )
    stale_token = boundary.bind_output_session(
        workflow_id="wf",
        active_route=original_route,
    ).token()

    boundary.bind_output_session(
        workflow_id="wf",
        active_route=current_route,
    )
    authorization = boundary.authorize_display_mutation(
        stale_token,
        active_route=original_route,
    )

    assert authorization.accepted is False
    assert authorization.rejection_reason is CanvasSessionRejectionReason.STALE_REVISION


def test_route_mismatch_cannot_authorize_display_mutation() -> None:
    """A current token cannot mutate a different active route."""

    boundary = CanvasSessionBoundary()
    route = CanvasRouteIdentity(
        route_kind="output_image",
        route_key="image:one",
    )
    other_route = CanvasRouteIdentity(
        route_kind="source_grid",
        route_key="source:two;set:0",
    )
    token = boundary.bind_output_session(
        workflow_id="wf",
        active_route=route,
    ).token()

    authorization = boundary.authorize_display_mutation(
        token,
        active_route=other_route,
    )

    assert authorization.accepted is False
    assert authorization.rejection_reason is CanvasSessionRejectionReason.ROUTE_MISMATCH


def test_canvas_kind_mismatch_cannot_authorize_display_mutation() -> None:
    """A token for one canvas kind cannot authorize another canvas kind."""

    boundary = CanvasSessionBoundary()
    token = boundary.bind_input_session(
        workflow_id="wf",
        active_route=CanvasRouteIdentity.empty(),
    ).token()

    authorization = boundary.authorize_display_mutation(
        token,
        canvas_kind=CanvasKind.OUTPUT,
    )

    assert authorization.accepted is False
    assert (
        authorization.rejection_reason
        is CanvasSessionRejectionReason.CANVAS_KIND_MISMATCH
    )


def test_workflow_switch_rejects_previous_workflow_token() -> None:
    """A token from a previous workflow cannot authorize the current session."""

    boundary = CanvasSessionBoundary()
    stale_token = boundary.bind_input_session(
        workflow_id="wf-old",
        active_route=CanvasRouteIdentity.empty(),
    ).token()

    boundary.bind_input_session(
        workflow_id="wf-new",
        active_route=CanvasRouteIdentity.empty(),
    )
    authorization = boundary.authorize_display_mutation(stale_token)

    assert authorization.accepted is False
    assert (
        authorization.rejection_reason is CanvasSessionRejectionReason.WORKFLOW_MISMATCH
    )
