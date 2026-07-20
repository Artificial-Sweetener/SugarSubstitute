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

"""Tests for shared model metadata context-menu action ownership."""

from __future__ import annotations

from sugarsubstitute_shared.localization import render_source_application_text

import os
from typing import cast
from uuid import UUID, uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.shell.output_canvas_thumbnail_choices import (
    OutputCanvasThumbnailChoice,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextMenuActionBuilder,
    ModelMetadataContextMenuPresenter,
    ModelMetadataContextMenuTarget,
    ModelMetadataMenuAction,
    ModelMetadataMenuSubmenu,
)


class _MetadataActionHandler:
    """Record metadata context-menu command targets."""

    def __init__(
        self,
        choices: tuple[OutputCanvasThumbnailChoice, ...] = (),
        active_choice: OutputCanvasThumbnailChoice | None = None,
    ) -> None:
        """Prepare action observations."""

        self.refresh_targets: list[ModelMetadataContextMenuTarget] = []
        self.thumbnail_targets: list[tuple[ModelMetadataContextMenuTarget, UUID]] = []
        self._choices = choices
        self._active_choice = active_choice

    def refresh_civitai_metadata(
        self,
        target: ModelMetadataContextMenuTarget,
    ) -> None:
        """Record one refresh request."""

        self.refresh_targets.append(target)

    def output_canvas_thumbnail_choices(
        self,
    ) -> tuple[OutputCanvasThumbnailChoice, ...]:
        """Return no output choices for existing action tests."""

        return self._choices

    def active_output_canvas_thumbnail_choice(
        self,
    ) -> OutputCanvasThumbnailChoice | None:
        """Return no active output choice for existing action tests."""

        return self._active_choice

    def set_thumbnail_from_output_image(
        self,
        target: ModelMetadataContextMenuTarget,
        image_id: UUID,
    ) -> None:
        """Record one thumbnail assignment request."""

        self.thumbnail_targets.append((target, image_id))


def test_metadata_context_menu_builds_civitai_page_action() -> None:
    """The shared action builder should own CivitAI page action creation."""

    _ensure_qapp()
    opened_urls: list[str] = []

    def open_url(url: str) -> bool:
        """Record opened URLs without launching a browser."""

        opened_urls.append(url)
        return True

    builder = ModelMetadataContextMenuActionBuilder(
        open_url=open_url,
    )
    target = ModelMetadataContextMenuTarget(
        title="Civit Base",
        subtitle="v2",
        backend_value="models/base.safetensors",
        model_page_url=" https://civitai.com/models/1?modelVersionId=2 ",
    )

    actions = _actions(builder.menu_items_for_target(target))

    assert len(actions) == 1
    assert actions[0].label == "Go to CivitAI page"
    actions[0].callback()
    assert opened_urls == ["https://civitai.com/models/1?modelVersionId=2"]


def test_metadata_context_menu_builds_refresh_action_for_local_identity() -> None:
    """The shared action builder should own manual refresh action creation."""

    _ensure_qapp()
    handler = _MetadataActionHandler()
    builder = ModelMetadataContextMenuActionBuilder(
        open_url=lambda _url: True,
        action_handler=handler,
    )
    target = ModelMetadataContextMenuTarget(
        title="Civit Base",
        backend_value="models/base.safetensors",
        model_kind="checkpoints",
    )

    actions = _actions(builder.menu_items_for_target(target))

    assert [action.label for action in actions] == [
        "Refresh CivitAI metadata",
        "Set thumbnail from canvas",
    ]
    actions[0].callback()
    assert handler.refresh_targets == [target]
    assert actions[1].enabled is False


def test_metadata_context_menu_combines_page_and_refresh_actions() -> None:
    """Targets with provider and local identity should expose both actions."""

    _ensure_qapp()
    handler = _MetadataActionHandler()
    builder = ModelMetadataContextMenuActionBuilder(
        open_url=lambda _url: True,
        action_handler=handler,
    )

    actions = _actions(
        builder.menu_items_for_target(
            ModelMetadataContextMenuTarget(
                title="Civit Base",
                backend_value="models/base.safetensors",
                model_kind="checkpoints",
                model_page_url="https://civitai.com/models/1?modelVersionId=2",
            )
        )
    )

    assert [action.label for action in actions] == [
        "Go to CivitAI page",
        "Refresh CivitAI metadata",
        "Set thumbnail from canvas",
    ]
    assert actions[2].enabled is False


def test_metadata_context_menu_omits_actions_without_metadata() -> None:
    """Targets without supported metadata should not create empty menu rows."""

    _ensure_qapp()
    builder = ModelMetadataContextMenuActionBuilder(open_url=lambda _url: True)

    assert (
        builder.menu_items_for_target(
            ModelMetadataContextMenuTarget(
                title="Local Model",
                backend_value="models/local.safetensors",
            )
        )
        == ()
    )


def test_metadata_context_menu_presenter_reports_empty_menu() -> None:
    """The presenter should return false when no target actions are available."""

    app = _ensure_qapp()
    parent = QWidget()
    presenter = ModelMetadataContextMenuPresenter(
        parent=parent,
        open_url=lambda _url: True,
    )

    shown = presenter.show_menu(
        ModelMetadataContextMenuTarget(title="Local Model"),
        QPoint(1, 2),
    )

    assert app is not None
    assert shown is False
    parent.deleteLater()


def test_metadata_context_menu_builds_direct_output_thumbnail_action() -> None:
    """A single output image should become one direct thumbnail action."""

    _ensure_qapp()
    choice = _choice(set_index=1)
    handler = _MetadataActionHandler((choice,), choice)
    builder = ModelMetadataContextMenuActionBuilder(
        open_url=lambda _url: True,
        action_handler=handler,
    )
    target = _local_target()

    actions = _actions(builder.menu_items_for_target(target))

    assert [action.label for action in actions] == [
        "Refresh CivitAI metadata",
        "Set thumbnail from canvas",
    ]
    actions[1].callback()
    assert handler.thumbnail_targets == [(target, choice.image_id)]


def test_metadata_context_menu_builds_batch_output_thumbnail_submenu() -> None:
    """Simple multi-batch output should collapse to batch leaves."""

    _ensure_qapp()
    first = _choice(set_index=1)
    second = _choice(set_index=2)
    handler = _MetadataActionHandler((first, second), first)
    builder = ModelMetadataContextMenuActionBuilder(
        open_url=lambda _url: True,
        action_handler=handler,
    )

    submenu = _submenu(builder.menu_items_for_target(_local_target()))

    assert submenu.label == "Set thumbnail from canvas"
    assert _labels(submenu.children) == ["Current image", "Batch 1", "Batch 2"]


def test_metadata_context_menu_builds_complex_output_thumbnail_submenus() -> None:
    """Scene choices should mirror the output canvas hierarchy."""

    _ensure_qapp()
    choices = (
        _choice(
            scene_key="scene-a",
            scene_title="Scene A",
            scene_order=1,
            source_key="main",
            source_label="Main output",
            set_index=1,
        ),
        _choice(
            scene_key="scene-a",
            scene_title="Scene A",
            scene_order=1,
            source_key="preview",
            source_label="Preview output",
            set_index=1,
        ),
        _choice(
            scene_key="scene-b",
            scene_title="Scene B",
            scene_order=2,
            source_key="main",
            source_label="Main output",
            set_index=2,
        ),
    )
    handler = _MetadataActionHandler(choices, choices[0])
    builder = ModelMetadataContextMenuActionBuilder(
        open_url=lambda _url: True,
        action_handler=handler,
    )

    submenu = _submenu(builder.menu_items_for_target(_local_target()))

    assert _labels(submenu.children) == [
        "Current image",
        "Scene A",
        "Scene B",
    ]
    scene_a = _submenu_child(submenu.children, "Scene A")
    assert _labels(scene_a.children) == ["Main output", "Preview output"]


def test_metadata_context_menu_follows_scene_batch_cube_output_path() -> None:
    """A structured canvas should expose Scene > Batch > cube output navigation."""

    _ensure_qapp()
    choices: list[OutputCanvasThumbnailChoice] = []
    diffusion_upscale_choice: OutputCanvasThumbnailChoice | None = None
    for scene_index in range(1, 4):
        for batch_index in range(1, 5):
            for source_key, source_label in (
                ("main", "Main output"),
                ("diffusion-upscale", "Diffusion Upscale"),
            ):
                choice = _choice(
                    scene_key=f"scene-{scene_index}",
                    scene_title=f"Scene {scene_index}",
                    scene_order=scene_index,
                    source_key=source_key,
                    source_label=source_label,
                    set_index=batch_index,
                )
                choices.append(choice)
                if (
                    scene_index == 3
                    and batch_index == 2
                    and source_key == "diffusion-upscale"
                ):
                    diffusion_upscale_choice = choice
    assert diffusion_upscale_choice is not None
    target = _local_target()
    handler = _MetadataActionHandler(tuple(choices), choices[0])
    builder = ModelMetadataContextMenuActionBuilder(
        open_url=lambda _url: True,
        action_handler=handler,
    )

    submenu = _submenu(builder.menu_items_for_target(target))
    scene_3 = _submenu_child(submenu.children, "Scene 3")
    batch_2 = _submenu_child(scene_3.children, "Batch 2")
    diffusion_upscale = _action_child(batch_2.children, "Diffusion Upscale")

    assert _labels(submenu.children) == [
        "Current image",
        "Scene 1",
        "Scene 2",
        "Scene 3",
    ]
    assert _labels(scene_3.children) == ["Batch 1", "Batch 2", "Batch 3", "Batch 4"]
    assert _labels(batch_2.children) == ["Main output", "Diffusion Upscale"]
    diffusion_upscale.callback()
    assert handler.thumbnail_targets == [(target, diffusion_upscale_choice.image_id)]


def _ensure_qapp() -> QApplication:
    """Return the active QApplication for QFluent action construction."""

    return cast(QApplication, QApplication.instance() or QApplication([]))


def _actions(
    items: tuple[object, ...],
) -> tuple[ModelMetadataMenuAction, ...]:
    """Return action items from one menu item tuple."""

    return tuple(item for item in items if isinstance(item, ModelMetadataMenuAction))


def _submenu(items: tuple[object, ...]) -> ModelMetadataMenuSubmenu:
    """Return the first submenu item from one menu item tuple."""

    for item in items:
        if isinstance(item, ModelMetadataMenuSubmenu):
            return item
    raise AssertionError("expected a submenu")


def _submenu_child(
    items: tuple[object, ...],
    label: str,
) -> ModelMetadataMenuSubmenu:
    """Return a submenu child by label."""

    for item in items:
        if (
            isinstance(item, ModelMetadataMenuSubmenu)
            and render_source_application_text(item.label) == label
        ):
            return item
    raise AssertionError(f"expected submenu {label!r}")


def _action_child(
    items: tuple[object, ...],
    label: str,
) -> ModelMetadataMenuAction:
    """Return an action child by label."""

    for item in items:
        if (
            isinstance(item, ModelMetadataMenuAction)
            and render_source_application_text(item.label) == label
        ):
            return item
    raise AssertionError(f"expected action {label!r}")


def _labels(items: tuple[object, ...]) -> list[str]:
    """Return labels from action and submenu menu items."""

    return [
        render_source_application_text(item.label)
        for item in items
        if isinstance(item, ModelMetadataMenuAction | ModelMetadataMenuSubmenu)
    ]


def _local_target() -> ModelMetadataContextMenuTarget:
    """Return a target with local model identity."""

    return ModelMetadataContextMenuTarget(
        title="Local Model",
        backend_value="models/local.safetensors",
        model_kind="checkpoints",
    )


def _choice(
    *,
    set_index: int,
    scene_key: str = "",
    scene_title: str = "",
    scene_order: int = 0,
    source_key: str = "main",
    source_label: str = "Main output",
) -> OutputCanvasThumbnailChoice:
    """Return one output thumbnail menu choice."""

    return OutputCanvasThumbnailChoice(
        image_id=uuid4(),
        scene_key=scene_key,
        scene_title=scene_title,
        scene_order=scene_order,
        source_key=source_key,
        source_label=source_label,
        set_index=set_index,
        width=512,
        height=384,
    )
