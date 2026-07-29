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

"""Verify Output retains its established menu apart from grid-target transfer."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

from cutecanvas import (
    CanvasContentKind,
    CanvasContentReference,
    CanvasPresentationKind,
)
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
)
from substitute.domain.workflow import ImageMeta
from substitute.presentation.canvas.output.output_canvas_context_menu import (
    OutputCanvasContextMenu,
)
from substitute.presentation.canvas.output.output_context_menu_router import (
    OutputContextMenuRouter,
)
from substitute.presentation.canvas.output.output_grid_context_menu import (
    OutputGridContextMenu,
)
from substitute.presentation.canvas.shared.types import OutputImageMeta
from substitute.presentation.widgets.menu_model import MenuItem


def test_existing_output_menu_retains_its_complete_action_set() -> None:
    """A non-grid Output canvas must not regress to a Copy-only context menu."""

    image_id = uuid4()
    reference = CanvasContentReference(
        document_id=uuid4(),
        kind=CanvasContentKind.COMPOSITION,
        composition_id=uuid4(),
    )
    copied: list[CanvasContentReference] = []
    menu = OutputCanvasContextMenu(
        parent=object(),  # type: ignore[arg-type]
        current_image_id=lambda: image_id,
        content_reference_for=lambda _image_id: reference,
        image_payload=lambda _image_id: object(),
        image_metadata=lambda _image_id: cast(
            OutputImageMeta,
            SimpleNamespace(path="E:/outputs/result.png"),
        ),
        projection=lambda: None,
        image_is_authorized=lambda candidate: candidate == image_id,
        compare_enabled=lambda: False,
        set_compare_enabled=lambda _enabled: None,
        active_scene_overview=lambda: False,
        active_set_index=lambda: 1,
        request_copy=copied.append,
        open_single_editor=None,
        open_all_editor=None,
        reveal_asset=None,
        canvas_detached=lambda: False,
        request_dock_action=lambda: None,
    )

    model = menu.menu_model()

    assert model is not None
    actions = tuple(entry for entry in model.entries if isinstance(entry, MenuItem))
    assert tuple(action.action_id for action in actions) == (
        "output_canvas.copy",
        "output_canvas.open_current_external",
        "output_canvas.open_all_external",
        "output_canvas.reveal_current_asset",
        "output_canvas.dock_action",
    )
    assert actions[0].callback is not None
    actions[0].callback()
    assert copied == [reference]


def test_output_menu_preserves_the_original_icon_assignments() -> None:
    """Keep the established Output-menu icon vocabulary during the document move."""

    first_id = uuid4()
    second_id = uuid4()
    model = _output_menu(
        current_image_id=first_id,
        projection=_projection(first_id, second_id),
    ).menu_model()

    assert model is not None
    actions = {
        entry.action_id: entry for entry in model.entries if isinstance(entry, MenuItem)
    }
    assert actions["output_canvas.compare_outputs"].icon is not None
    assert actions["output_canvas.copy"].icon is FIF.COPY
    assert actions["output_canvas.open_current_external"].icon is FIF.PHOTO
    assert (
        actions["output_canvas.open_all_external"].icon
        is not actions["output_canvas.open_current_external"].icon
    )
    assert actions["output_canvas.dock_action"].icon is FIF.FULL_SCREEN


def test_grid_menu_preserves_the_original_icon_assignments() -> None:
    """Keep addressed grid actions visually identical to their established actions."""

    reference = CanvasContentReference(
        document_id=uuid4(),
        kind=CanvasContentKind.COMPOSITION,
        composition_id=uuid4(),
    )
    menu = OutputGridContextMenu(
        parent=object(),  # type: ignore[arg-type]
        request_copy=lambda _reference: None,
        image_id_for_reference=lambda _reference: None,
        image_payload=lambda _image_id: None,
        image_metadata=lambda _image_id: None,
        image_is_authorized=lambda _image_id: False,
        open_single_editor=None,
        canvas_detached=lambda: False,
        request_dock_action=lambda: None,
    )

    actions = {
        entry.action_id: entry
        for entry in menu.menu_model(reference).entries
        if isinstance(entry, MenuItem)
    }
    assert actions["output_canvas.copy"].icon is FIF.COPY
    assert actions["output_canvas.open_current_external"].icon is FIF.PHOTO
    assert actions["output_canvas.dock_action"].icon is FIF.FULL_SCREEN


def test_output_menu_suppresses_detail_actions_for_non_compare_grid_routes() -> None:
    """A source or scene grid must retain its dedicated addressed-tile menu."""

    menu = _output_menu(
        current_image_id=uuid4(),
        active_set_index=0,
    )

    assert menu.menu_model() is None


def test_output_menu_exposes_compare_only_for_distinct_projected_images() -> None:
    """Compare remains available only when the active projection has two outputs."""

    first_id = uuid4()
    second_id = uuid4()
    compare_requests: list[bool] = []
    menu = _output_menu(
        current_image_id=first_id,
        projection=_projection(first_id, second_id),
        compare_requests=compare_requests,
    )

    model = menu.menu_model()

    assert model is not None
    compare = next(
        entry
        for entry in model.entries
        if isinstance(entry, MenuItem)
        and entry.action_id == "output_canvas.compare_outputs"
    )
    assert compare.checkable is True
    assert compare.checked is False
    assert compare.checked_callback is not None
    compare.checked_callback(True)
    assert compare_requests == [True]

    duplicate_model = _output_menu(
        current_image_id=first_id,
        projection=_projection(first_id, first_id),
    ).menu_model()
    assert duplicate_model is not None
    assert all(
        not isinstance(entry, MenuItem)
        or entry.action_id != "output_canvas.compare_outputs"
        for entry in duplicate_model.entries
    )


def test_output_menu_actions_use_only_authorized_resolved_outputs() -> None:
    """Copy and external actions must preserve the projection authorization boundary."""

    allowed_id = uuid4()
    blocked_id = uuid4()
    reference = CanvasContentReference(
        document_id=uuid4(),
        kind=CanvasContentKind.COMPOSITION,
        composition_id=uuid4(),
    )
    allowed_payload = object()
    blocked_payload = object()
    metadata = _metadata(allowed_id, path="E:/outputs/allowed.png")
    copied: list[CanvasContentReference] = []
    opened_current: list[tuple[object, OutputImageMeta]] = []
    opened_all: list[list[tuple[object, OutputImageMeta]]] = []
    revealed: list[OutputImageMeta] = []

    def open_current(payload: object, image_metadata: OutputImageMeta) -> bool:
        """Record an external-editor request for the current output."""

        opened_current.append((payload, image_metadata))
        return True

    def open_all(images: list[tuple[object, OutputImageMeta]]) -> bool:
        """Record an external-editor request for every eligible output."""

        opened_all.append(images)
        return True

    def reveal(image_metadata: OutputImageMeta) -> bool:
        """Record a file-manager request for the eligible output."""

        revealed.append(image_metadata)
        return True

    menu = OutputCanvasContextMenu(
        parent=object(),  # type: ignore[arg-type]
        current_image_id=lambda: allowed_id,
        content_reference_for=lambda _image_id: reference,
        image_payload=lambda image_id: {
            allowed_id: allowed_payload,
            blocked_id: blocked_payload,
        }.get(image_id),
        image_metadata=lambda image_id: metadata if image_id == allowed_id else None,
        projection=lambda: _projection(allowed_id, blocked_id),
        image_is_authorized=lambda image_id: image_id == allowed_id,
        compare_enabled=lambda: False,
        set_compare_enabled=lambda _enabled: None,
        active_scene_overview=lambda: False,
        active_set_index=lambda: 1,
        request_copy=copied.append,
        open_single_editor=open_current,
        open_all_editor=open_all,
        reveal_asset=reveal,
        canvas_detached=lambda: False,
        request_dock_action=lambda: None,
    )
    model = menu.menu_model()
    assert model is not None
    actions = {
        entry.action_id: entry for entry in model.entries if isinstance(entry, MenuItem)
    }

    for action_id in (
        "output_canvas.copy",
        "output_canvas.open_current_external",
        "output_canvas.open_all_external",
        "output_canvas.reveal_current_asset",
    ):
        callback = actions[action_id].callback
        assert callback is not None
        callback()

    assert copied == [reference]
    assert opened_current == [(allowed_payload, metadata)]
    assert opened_all == [[(allowed_payload, metadata)]]
    assert revealed == [metadata]


def test_output_menu_disables_pathless_reveal_and_labels_redock() -> None:
    """Asset absence and detached state remain visible in the established menu."""

    image_id = uuid4()
    menu = _output_menu(
        current_image_id=image_id,
        metadata=_metadata(image_id, path=""),
        canvas_detached=True,
    )

    model = menu.menu_model()
    assert model is not None
    actions = {
        entry.action_id: entry for entry in model.entries if isinstance(entry, MenuItem)
    }
    assert actions["output_canvas.reveal_current_asset"].enabled is False
    assert actions["output_canvas.dock_action"].label == "Redock canvas"


def test_context_router_uses_addressed_copy_only_for_grid_targets() -> None:
    """Grid Copy must not replace the existing non-grid Output menu."""

    output_calls: list[object] = []
    grid_calls: list[tuple[object, object]] = []

    class _OutputMenu:
        """Record established Output menu requests."""

        def show(self, position: object) -> None:
            """Record one established-menu request."""

            output_calls.append(position)

    class _GridMenu:
        """Record addressed grid-target menu requests."""

        def show(self, subject: object, position: object) -> None:
            """Record one targeted grid request."""

            grid_calls.append((subject, position))

    presentation_kind = CanvasPresentationKind.GRID
    router = OutputContextMenuRouter(
        presentation_kind=lambda: presentation_kind,
        output_menu=cast(OutputCanvasContextMenu, _OutputMenu()),
        grid_menu=cast(OutputGridContextMenu, _GridMenu()),
    )
    subject = object()
    position = object()

    router.show(subject, position)
    presentation_kind = CanvasPresentationKind.SINGLE
    router.show(subject, position)

    assert grid_calls == [(subject, position)]
    assert output_calls == [position]


def _output_menu(
    *,
    current_image_id: UUID,
    projection: OutputCanvasProjection | None = None,
    active_set_index: int = 1,
    compare_requests: list[bool] | None = None,
    metadata: OutputImageMeta | None = None,
    canvas_detached: bool = False,
) -> OutputCanvasContextMenu:
    """Build one deterministic Output menu for contract-level assertions."""

    active_compare_requests = compare_requests if compare_requests is not None else []
    return OutputCanvasContextMenu(
        parent=object(),  # type: ignore[arg-type]
        current_image_id=lambda: current_image_id,
        content_reference_for=lambda _image_id: None,
        image_payload=lambda _image_id: None,
        image_metadata=lambda candidate: (
            metadata if candidate == current_image_id else None
        ),
        projection=lambda: projection,
        image_is_authorized=lambda candidate: candidate == current_image_id,
        compare_enabled=lambda: False,
        set_compare_enabled=active_compare_requests.append,
        active_scene_overview=lambda: False,
        active_set_index=lambda: active_set_index,
        request_copy=lambda _reference: None,
        open_single_editor=None,
        open_all_editor=None,
        reveal_asset=None,
        canvas_detached=lambda: canvas_detached,
        request_dock_action=lambda: None,
    )


def _projection(*image_ids: UUID) -> OutputCanvasProjection:
    """Build one ordered source projection for context-menu contract tests."""

    return OutputCanvasProjection(
        sources=(
            OutputCanvasSourceGroup(
                source_key="source",
                label="Source",
                images_by_set={
                    index: OutputCanvasImageItem(
                        image_id=image_id,
                        image_meta=_metadata(image_id, path="E:/outputs/image.png"),
                        set_index=index,
                    )
                    for index, image_id in enumerate(image_ids, start=1)
                },
            ),
        ),
        active_source_key="source",
        active_set_index=1,
        active_uuid=image_ids[0],
        set_count=len(image_ids),
    )


def _metadata(image_id: UUID, *, path: str) -> ImageMeta:
    """Build one complete final-output metadata record for menu actions."""

    del image_id
    return ImageMeta(
        workflow_name="workflow",
        cube_name="cube",
        image_number=1,
        suffix="",
        path=path,
        source_key="source",
        source_label="Source",
    )
