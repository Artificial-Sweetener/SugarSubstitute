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

"""Test authoritative projected emphasis interaction ownership."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import QObject

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
    PromptProjectionTokenNavigationMode,
    PromptWeightControlIdentity,
)
from substitute.presentation.editor.prompt_editor.projection.emphasis_projection_owner import (
    PromptProjectionEmphasisOwner,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptEmphasisAdjustmentOwner,
    PromptEmphasisCaretBoundary,
    PromptProjectionSession,
    PromptTransientNeutralEmphasisOwner,
)
from tests.support.prompt_editor.projection_engine_support import ensure_qapp


def test_emphasis_owner_coordinates_adjustment_session_and_wheel_identity() -> None:
    """Adjustment state and stable wheel identity should share one owner."""

    token = _emphasis_token()
    custom_identity: PromptWeightControlIdentity = (
        "preserved",
        PromptProjectionTokenKind.EMPHASIS,
        1,
        4,
    )
    owner, session = _owner(tokens=(token,))

    owner.set_adjustment_session(
        owner=PromptEmphasisAdjustmentOwner.OVERLAY,
        content_start=1,
        content_end=4,
        caret_boundary=PromptEmphasisCaretBoundary.END,
        wheel_intent_identity=custom_identity,
    )

    assert owner.adjustment_session() is not None
    assert owner.adjustment_session_range() == (1, 4)
    assert owner.adjustment_session_matches_range(content_start=1, content_end=4)
    assert owner.wheel_identity(token) == custom_identity
    assert session.emphasis_adjustment_session_state is owner.adjustment_session()

    owner.clear_adjustment_session()

    assert owner.adjustment_session() is None


def test_emphasis_owner_publishes_transient_projection_with_bounded_rebuilds() -> None:
    """Transient shells should reuse paint state and rebuild only when required."""

    apply_results = iter((True, False))
    rebuilds: list[None] = []
    owner, session = _owner(
        apply_session_paint_state=lambda: next(apply_results),
        rebuild_projection=lambda: rebuilds.append(None),
    )

    owner.show_transient_neutral(content_start=0, content_end=3)

    assert owner.transient_neutral_range() == (0, 3)
    assert rebuilds == []

    owner.clear_transient_neutral()

    assert owner.transient_neutral_range() is None
    assert rebuilds == [None]

    owner.show_transient_neutral(
        content_start=5,
        content_end=8,
        owner=PromptTransientNeutralEmphasisOwner.OVERLAY,
    )

    assert (
        owner.transient_neutral_owner() is PromptTransientNeutralEmphasisOwner.OVERLAY
    )
    assert rebuilds == [None, None]

    owner.clear_overlay_owned_transient_neutral()

    assert session.transient_neutral_emphasis is None
    assert rebuilds == [None, None, None]


def test_emphasis_owner_preserves_non_overlay_transient_state() -> None:
    """Overlay cleanup should not clear a caret-owned neutral shell."""

    owner, session = _owner()
    owner.show_transient_neutral(content_start=0, content_end=3)

    owner.clear_overlay_owned_transient_neutral()

    assert session.transient_neutral_emphasis is not None


def test_emphasis_owner_publishes_exact_projected_content_boundary() -> None:
    """Caret placement should preserve token content identity and slot geometry."""

    published: list[tuple[PromptProjectionCaretState, PromptProjectionCaretState]] = []

    def publish_caret(
        cursor_state: PromptProjectionCaretState,
        anchor_state: PromptProjectionCaretState,
    ) -> None:
        """Record one projected caret publication."""

        published.append((cursor_state, anchor_state))

    owner, _session = _owner(tokens=(_emphasis_token(),), publish_caret=publish_caret)

    assert owner.set_caret_to_content_boundary(
        content_start=1,
        content_end=4,
        prefer_end=True,
    )
    assert published == [
        (
            PromptProjectionCaretState(
                source_position=4,
                placement=PromptProjectionCaretPlacement.TOKEN_CONTENT,
                token_id="emphasis",
                token_slot=3,
            ),
            PromptProjectionCaretState(
                source_position=4,
                placement=PromptProjectionCaretPlacement.TOKEN_CONTENT,
                token_id="emphasis",
                token_slot=3,
            ),
        )
    ]
    assert not owner.set_caret_to_content_boundary(
        content_start=8,
        content_end=10,
        prefer_end=False,
    )


def _owner(
    *,
    tokens: Sequence[PromptProjectionToken] = (),
    apply_session_paint_state: Callable[[], bool] = lambda: True,
    rebuild_projection: Callable[[], None] = lambda: None,
    publish_caret: Callable[
        [PromptProjectionCaretState, PromptProjectionCaretState], None
    ] = lambda _cursor, _anchor: None,
) -> tuple[PromptProjectionEmphasisOwner, PromptProjectionSession]:
    """Build one deterministic emphasis owner and its backing session."""

    ensure_qapp()
    session = PromptProjectionSession()
    owner = PromptProjectionEmphasisOwner(
        session=session,
        is_projected=lambda: True,
        tokens=lambda: tokens,
        apply_session_paint_state=apply_session_paint_state,
        apply_accent_paint_state=lambda: None,
        rebuild_projection=rebuild_projection,
        publish_caret=publish_caret,
        parent=QObject(),
    )
    return owner, session


def _emphasis_token() -> PromptProjectionToken:
    """Return one content-navigable emphasis token."""

    return PromptProjectionToken(
        token_id="emphasis",
        kind=PromptProjectionTokenKind.EMPHASIS,
        source_start=0,
        source_end=9,
        display_text="cat",
        value_text="1.05",
        content_start=1,
        content_end=4,
        navigation_mode=PromptProjectionTokenNavigationMode.TEXT_CONTENT,
    )
