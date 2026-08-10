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

"""Verify captured CuteCanvas subjects become target-aware grid actions."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

from cutecanvas import CanvasContentKind, CanvasContentReference
from pytest import MonkeyPatch
from cutecanvas import DragSubject

from substitute.presentation.canvas.output.output_grid_context_menu import (
    OutputGridContextMenu,
)
from substitute.presentation.canvas.shared.types import OutputImageMeta
from substitute.presentation.widgets.menu_model import MenuItem, MenuModel


def test_context_menu_binds_actions_to_the_captured_subject(
    monkeypatch: MonkeyPatch,
) -> None:
    """Each action must retain the clicked target instead of reading later UI state."""

    captured_models: list[object] = []
    copy_requests: list[CanvasContentReference] = []
    external_requests: list[tuple[object, OutputImageMeta]] = []
    reveal_requests: list[OutputImageMeta] = []
    dock_requests: list[None] = []
    menu = SimpleNamespace(exec=lambda position, **kwargs: None)

    class _Renderer:
        """Capture the generated menu model without creating a native widget."""

        def __init__(self, *, parent: object) -> None:
            """Accept the presenter parent."""

            del parent

        def render(self, model: object) -> object:
            """Record the single action model and return the fake menu."""

            captured_models.append(model)
            return menu

    monkeypatch.setattr(
        "substitute.presentation.canvas.output.output_grid_context_menu.QFluentMenuRenderer",
        _Renderer,
    )
    subject = _reference()
    image_id = uuid4()
    payload = object()
    metadata = cast(OutputImageMeta, SimpleNamespace(path="E:/outputs/result.png"))

    def open_external(image: object, image_metadata: OutputImageMeta) -> bool:
        """Record the exact target supplied to the external editor action."""

        external_requests.append((image, image_metadata))
        return True

    def request_dock_action() -> None:
        """Record the grid menu's dock toggle request."""

        dock_requests.append(None)

    def reveal_asset(image_metadata: OutputImageMeta) -> bool:
        """Record the asset supplied to the reveal action."""

        reveal_requests.append(image_metadata)
        return True

    presenter = _presenter(
        copy_requests=copy_requests,
        image_id_for_reference=lambda candidate: (
            image_id if candidate == subject else None
        ),
        image_payload=lambda candidate: payload if candidate == image_id else None,
        image_metadata=lambda candidate: metadata if candidate == image_id else None,
        open_single_editor=open_external,
        reveal_asset=reveal_asset,
        request_dock_action=request_dock_action,
    )

    presenter.show(subject, object())

    assert len(captured_models) == 1
    actions = tuple(
        entry
        for entry in cast(MenuModel, captured_models[0]).entries
        if isinstance(entry, MenuItem)
    )
    assert tuple(action.action_id for action in actions) == (
        "output_canvas.copy",
        "output_canvas.open_current_external",
        "output_canvas.reveal_current_asset",
        "output_canvas.dock_action",
    )
    for action in actions:
        assert action.callback is not None
        action.callback()
    assert copy_requests == [subject]
    assert external_requests == [(payload, metadata)]
    assert reveal_requests == [metadata]
    assert dock_requests == [None]


def test_context_menu_ignores_non_document_context_subject() -> None:
    """A malformed forwarded signal must never create a Copy action."""

    presenter = _presenter(copy_requests=[])

    presenter.show(object(), object())


def test_context_menu_unwraps_the_captured_canvas_drag_subject(
    monkeypatch: MonkeyPatch,
) -> None:
    """A real CuteCanvas context envelope must bind actions to its inner reference."""

    captured_models: list[object] = []
    copy_requests: list[CanvasContentReference] = []
    menu = SimpleNamespace(exec=lambda position, **kwargs: None)

    class _Renderer:
        """Capture menu construction without opening a native popup."""

        def __init__(self, *, parent: object) -> None:
            """Accept the menu parent supplied by the presentation owner."""

            del parent

        def render(self, model: object) -> object:
            """Retain the menu model and return a no-op native-menu stand-in."""

            captured_models.append(model)
            return menu

    monkeypatch.setattr(
        "substitute.presentation.canvas.output.output_grid_context_menu.QFluentMenuRenderer",
        _Renderer,
    )
    reference = _reference()
    presenter = _presenter(copy_requests=copy_requests)

    presenter.show(DragSubject(reference, target_id=reference.composition_id), object())

    action = cast(MenuModel, captured_models[0]).entries[0]
    assert isinstance(action, MenuItem)
    assert action.callback is not None
    action.callback()
    assert copy_requests == [reference]


def _presenter(
    *,
    copy_requests: list[CanvasContentReference],
    image_id_for_reference: Callable[
        [CanvasContentReference], UUID | None
    ] = lambda _reference: None,
    image_payload: Callable[[UUID], object | None] = lambda _image_id: None,
    image_metadata: Callable[[UUID], OutputImageMeta | None] = lambda _image_id: None,
    open_single_editor: Callable[[object, OutputImageMeta], bool] | None = None,
    reveal_asset: Callable[[OutputImageMeta], bool] | None = None,
    request_dock_action: Callable[[], None] = lambda: None,
) -> OutputGridContextMenu:
    """Build one target-addressed grid menu with deterministic dependencies."""

    return OutputGridContextMenu(
        parent=object(),  # type: ignore[arg-type]
        request_copy=copy_requests.append,
        image_id_for_reference=image_id_for_reference,
        image_payload=image_payload,
        image_metadata=image_metadata,
        image_is_authorized=lambda _image_id: True,
        open_single_editor=open_single_editor,
        reveal_asset=reveal_asset,
        canvas_detached=lambda: False,
        request_dock_action=request_dock_action,
    )


def _reference() -> CanvasContentReference:
    """Return one immutable document content reference."""

    return CanvasContentReference(
        document_id=uuid4(),
        kind=CanvasContentKind.COMPOSITION,
        composition_id=uuid4(),
    )
