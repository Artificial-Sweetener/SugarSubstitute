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

"""Verify prompt-reorder interaction-controller orchestration."""

from __future__ import annotations

from typing import Any

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutationService,
)
from substitute.application.prompt_editor.reorder.views import (
    PromptReorderLayoutView,
    PromptReorderStateView,
)
from substitute.application.prompt_editor.reorder.intents import (
    PromptReorderCancelIntent,
    PromptReorderCommitIntent,
)
from substitute.application.prompt_editor.reorder.session import (
    PromptReorderCommitSnapshot,
)
from substitute.domain.prompt.features.models import PromptEditorFeatureProfile
from substitute.presentation.editor.prompt_editor.features.feature_profile_controller import (
    PromptFeatureProfileController,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_overlay_port import (
    PromptReorderOverlayAssembly,
)
from tests.support.prompt_editor.autocomplete_support import prompt_syntax_profile
from tests.presentation.editor.prompt_editor.interactions.support.editor import (
    ControllerEditorDouble,
    MenuCursorDouble,
)
from tests.presentation.editor.prompt_editor.interactions.support.reorder_overlay import (
    OverlayDouble,
    OverlayFactoryDouble,
    reorder_state_for_indices,
)
from tests.presentation.editor.prompt_editor.interactions.support.collaborators import (
    autocomplete_double,
    semantic_refresh_controller_double,
    syntax_renderer_double,
    syntax_service,
)
from tests.presentation.editor.prompt_editor.interactions.support.controller import (
    prompt_interaction_controller,
)


def test_show_segment_overlay_clears_autocomplete_before_entering_reorder_mode() -> (
    None
):
    """Entering segment reorder mode dismisses autocomplete before overlay entry."""

    call_order: list[Any] = []

    class _FakeSegmentOverlay(OverlayDouble):
        """Record overlay entry calls through the factory seam."""

        def set_chips(
            self,
            document_view: object,
            reorder_layout_view: PromptReorderLayoutView,
            reorder_state: PromptReorderStateView,
            *,
            chips: tuple[Any, ...],
            active_chip_index: int | None = None,
            source_identity: PromptSourceIdentity | None = None,
        ) -> None:
            super().set_chips(
                document_view,
                reorder_layout_view,
                reorder_state,
                chips=chips,
                active_chip_index=active_chip_index,
                source_identity=source_identity,
            )
            call_order.append(
                (
                    "set_chips",
                    tuple(segment.index for segment in chips),
                    reorder_layout_view,
                    active_chip_index,
                )
            )

        def set_preview_snapshot(
            self,
            snapshot: object | None,
            *,
            base_drag_snapshot: object | None = None,
            ordered_chip_indices: tuple[int, ...],
        ) -> None:
            """Record preview snapshot pushes without affecting call-order assertions."""

            call_order.append(
                (
                    "set_preview_snapshot",
                    snapshot,
                    base_drag_snapshot,
                    ordered_chip_indices,
                )
            )

        def refresh_geometry(self, *, reason: str = "test") -> None:
            """Record overlay geometry refresh ordering."""

            super().refresh_geometry(reason=reason)
            call_order.append(("refresh_geometry", reason))

        def show(self) -> None:
            """Record overlay show ordering."""

            super().show()
            call_order.append("show")

    class _Factory(OverlayFactoryDouble):
        """Record overlay creation in the test call order."""

        def create_segment_overlay(
            self,
            editor: object,
            *,
            layout_policy: object,
        ) -> PromptReorderOverlayAssembly:
            call_order.append(("overlay_init", editor))
            return super().create_segment_overlay(
                editor,
                layout_policy=layout_policy,
            )

    overlay = _FakeSegmentOverlay([0, 1])
    overlay_factory = _Factory(overlay)
    autocomplete = autocomplete_double()
    autocomplete.dismiss_autocomplete = lambda _reason: call_order.append("clear")
    editor = ControllerEditorDouble(
        clicked_cursor=MenuCursorDouble(text="alpha, beta", position=7),
        current_cursor=MenuCursorDouble(text="alpha, beta", position=7),
        text="alpha, beta",
    )
    syntax_renderers = syntax_renderer_double()
    controller = prompt_interaction_controller(
        editor,
        autocomplete=autocomplete,
        semantic_refresh_controller=semantic_refresh_controller_double(),
        syntax_renderers=syntax_renderers,
        document_service=PromptDocumentService(),
        mutation_service=PromptMutationService(),
        syntax_service_=syntax_service(),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        reorder_overlay_factory=overlay_factory,
    )

    controller.enter_segment_reorder_mode_from_keymap()

    assert call_order[0] == "clear"
    assert syntax_renderers.clear_transient_state_calls == 1
    assert ("overlay_init", editor) in call_order
    assert any(
        entry[0] == "set_chips" and entry[1] == (0, 1) and entry[3] == 1
        for entry in call_order
    )
    assert ("refresh_geometry", "interaction_position_overlay") not in call_order
    assert call_order.index("show") < next(
        index
        for index, entry in enumerate(call_order)
        if isinstance(entry, tuple) and entry[0] == "set_chips"
    )
    assert controller.segment_overlay is not None


def test_show_segment_overlay_is_a_noop_when_reorder_is_disabled() -> None:
    """Disabled reorder entry leaves source, transients, and overlay untouched."""

    overlay_factory = OverlayFactoryDouble()
    editor = ControllerEditorDouble(
        clicked_cursor=MenuCursorDouble(text="alpha, beta", position=7),
        current_cursor=MenuCursorDouble(text="alpha, beta", position=7),
        text="alpha, beta",
    )
    syntax_renderers = syntax_renderer_double()
    controller = prompt_interaction_controller(
        editor,
        autocomplete=autocomplete_double(),
        semantic_refresh_controller=semantic_refresh_controller_double(),
        syntax_renderers=syntax_renderers,
        feature_profile=PromptFeatureProfileController(
            PromptEditorFeatureProfile.enabled_profile(())
        ),
        reorder_overlay_factory=overlay_factory,
    )

    controller.enter_segment_reorder_mode_from_keymap()

    assert overlay_factory.create_calls == []
    assert syntax_renderers.clear_transient_state_calls == 0
    assert controller.segment_overlay is None
    assert controller.interaction_mode.name == "TEXT_EDITING"


def test_show_segment_overlay_is_idempotent_while_session_is_active() -> None:
    """Repeated entry retains the original overlay and captured selection."""

    overlay = OverlayDouble([0, 1])
    overlay_factory = OverlayFactoryDouble(overlay)
    editor = ControllerEditorDouble(
        clicked_cursor=MenuCursorDouble(text="alpha, beta", position=7),
        current_cursor=MenuCursorDouble(text="alpha, beta", position=7),
        text="alpha, beta",
    )
    controller = prompt_interaction_controller(
        editor,
        autocomplete=autocomplete_double(),
        semantic_refresh_controller=semantic_refresh_controller_double(),
        syntax_renderers=syntax_renderer_double(),
        reorder_overlay_factory=overlay_factory,
    )

    controller.enter_segment_reorder_mode_from_keymap()
    controller.enter_segment_reorder_mode_from_keymap()

    assert len(overlay_factory.create_calls) == 1
    assert overlay.show_calls == 1
    assert controller.segment_overlay is overlay


def test_show_segment_overlay_with_no_chips_leaves_interaction_in_text_mode() -> None:
    """Empty prompts do not clear transients or construct a reorder overlay."""

    overlay_factory = OverlayFactoryDouble()
    editor = ControllerEditorDouble(
        clicked_cursor=MenuCursorDouble(text="", position=0),
        current_cursor=MenuCursorDouble(text="", position=0),
        text="",
    )
    syntax_renderers = syntax_renderer_double()
    controller = prompt_interaction_controller(
        editor,
        autocomplete=autocomplete_double(),
        semantic_refresh_controller=semantic_refresh_controller_double(),
        syntax_renderers=syntax_renderers,
        reorder_overlay_factory=overlay_factory,
    )

    controller.enter_segment_reorder_mode_from_keymap()

    assert overlay_factory.create_calls == []
    assert syntax_renderers.clear_transient_state_calls == 0
    assert controller.segment_overlay is None
    assert controller.interaction_mode.name == "TEXT_EDITING"


def test_close_segment_overlay_restores_live_paint_after_overlay_is_hidden() -> None:
    """Final live-paint invalidation must run after the covering overlay closes."""

    call_order: list[str] = []

    class _Editor(ControllerEditorDouble):
        """Record when live projection painting is restored."""

        def clear_reorder_preview_state(self) -> None:
            super().clear_reorder_preview_state()
            call_order.append("clear_preview")

    class _Overlay(OverlayDouble):
        """Record when the viewport-covering overlay is hidden."""

        def close(self) -> bool:
            call_order.append("close_overlay")
            return super().close()

    overlay = _Overlay([0, 1])
    editor = _Editor(
        clicked_cursor=MenuCursorDouble(text="alpha, beta", position=7),
        current_cursor=MenuCursorDouble(text="alpha, beta", position=7),
        text="alpha, beta",
    )
    controller = prompt_interaction_controller(
        editor,
        autocomplete=autocomplete_double(),
        semantic_refresh_controller=semantic_refresh_controller_double(),
        syntax_renderers=syntax_renderer_double(),
        document_service=PromptDocumentService(),
        mutation_service=PromptMutationService(),
        syntax_service_=syntax_service(),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        reorder_overlay_factory=OverlayFactoryDouble(overlay),
    )
    controller.enter_segment_reorder_mode_from_keymap()

    controller.cancel_segment_reorder_mode_from_keymap(
        PromptReorderCancelIntent(reason="test", restore_selection=False)
    )

    assert call_order[-2:] == ["close_overlay", "clear_preview"]
    assert controller.segment_overlay is None


def test_overlay_pointer_drop_updates_commit_snapshot_without_source_mutation() -> None:
    """Pointer-drop intent prepares commit state without executing source mutation."""

    overlay = OverlayDouble([0, 1])
    controller, editor, _document_service, layout_view = _controller_for_reorder_text(
        "alpha, beta", reorder_overlay_factory=OverlayFactoryDouble(overlay)
    )
    controller.enter_segment_reorder_mode_from_keymap()
    snapshot = PromptReorderCommitSnapshot(
        reorder_state=reorder_state_for_indices((1, 0)),
        layout_view=layout_view,
        ordered_chip_indices=(1, 0),
        active_segment_index=1,
        dragged_segment_index=1,
        has_reordered=True,
    )

    assert overlay.commit_handler is not None
    overlay.commit_handler(
        PromptReorderCommitIntent(reason="pointer_drop", snapshot=snapshot)
    )

    assert editor.toPlainText() == "alpha, beta"
    assert editor.executed_reorder_requests == []
    assert controller.segment_overlay is overlay


def _controller_for_reorder_text(
    text: str,
    *,
    reorder_overlay_factory: OverlayFactoryDouble | None = None,
) -> tuple[Any, ControllerEditorDouble, PromptDocumentService, PromptReorderLayoutView]:
    """Build a reorder interaction controller and layout for one prompt."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(text)
    layout_view = document_service.build_reorder_layout_view(document_view)
    editor = ControllerEditorDouble(
        clicked_cursor=MenuCursorDouble(text=text, position=7),
        current_cursor=MenuCursorDouble(text=text, position=7),
        text=text,
    )
    controller = prompt_interaction_controller(
        editor,
        autocomplete=autocomplete_double(),
        semantic_refresh_controller=semantic_refresh_controller_double(),
        syntax_renderers=syntax_renderer_double(),
        document_service=document_service,
        mutation_service=PromptMutationService(),
        syntax_service_=syntax_service(),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        reorder_overlay_factory=reorder_overlay_factory,
    )
    return controller, editor, document_service, layout_view
