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

"""Verify editor-panel signal routing and layout autosave."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.presentation.shell.main_window_signal_binder import (
    MainWindowSignalBinder,
)

from .support import _Signal


def test_editor_panel_signals_route_editor_events_and_layout_autosave() -> None:
    """Editor-panel wiring should bind image, mask, prompt, and layout events."""

    events: list[tuple[str, object]] = []
    editor_panel = SimpleNamespace(
        currentCubeVisibleChanged=_Signal(),
        inputImageChanged=_Signal(),
        inputImageClicked=_Signal(),
        inputMaskChanged=_Signal(),
        inputMaskClicked=_Signal(),
        inputMaskOpacityChanged=_Signal(),
        inputMaskOpacityCommitted=_Signal(),
        promptSceneQueueRequested=_Signal(),
        promptEditorLayoutChanged=_Signal(),
    )
    shell = SimpleNamespace(
        workspace_cube_stack_actions=SimpleNamespace(
            highlight_tab_for_cube=lambda alias: events.append(("visible", alias)),
        ),
        workspace_scene_generation_actions=SimpleNamespace(
            enqueue_prompt_scene=lambda scene_key: events.append(
                ("prompt_scene", scene_key)
            ),
        ),
        input_node_interaction_controller=SimpleNamespace(
            handle_image_changed=lambda alias, node, path: events.append(
                ("image_changed", (alias, node, path))
            ),
            handle_image_clicked=lambda alias, node, path: events.append(
                ("image_clicked", (alias, node, path))
            ),
            handle_mask_changed=lambda alias, node, path: events.append(
                ("mask_changed", (alias, node, path))
            ),
            handle_mask_clicked=lambda alias, node, path: events.append(
                ("mask_clicked", (alias, node, path))
            ),
        ),
        input_mask_visual_opacity_controller=SimpleNamespace(
            handle=lambda alias, node, opacity: events.append(
                ("mask_opacity", (alias, node, opacity))
            ),
            handle_commit=lambda alias, node, before, after: events.append(
                ("mask_opacity_commit", (alias, node, before, after))
            ),
        ),
        request_session_autosave=lambda: events.append(("autosave", None)),
    )

    MainWindowSignalBinder(shell).connect_editor_panel_signals(editor_panel)
    editor_panel.currentCubeVisibleChanged.fire("CubeA")
    editor_panel.inputImageChanged.fire("CubeA", "ImageNode", "image.png")
    editor_panel.inputImageClicked.fire("CubeA", "ImageNode", "image.png")
    editor_panel.inputMaskChanged.fire("CubeA", "MaskNode", "mask.png")
    editor_panel.inputMaskClicked.fire("CubeA", "MaskNode", "mask.png")
    editor_panel.inputMaskOpacityChanged.fire("CubeA", "MaskNode", 0.37)
    editor_panel.inputMaskOpacityCommitted.fire("CubeA", "MaskNode", 0.5, 0.37)
    editor_panel.promptSceneQueueRequested.fire("portrait")
    editor_panel.promptEditorLayoutChanged.fire()

    assert events == [
        ("visible", "CubeA"),
        ("image_changed", ("CubeA", "ImageNode", "image.png")),
        ("image_clicked", ("CubeA", "ImageNode", "image.png")),
        ("mask_changed", ("CubeA", "MaskNode", "mask.png")),
        ("mask_clicked", ("CubeA", "MaskNode", "mask.png")),
        ("mask_opacity", ("CubeA", "MaskNode", 0.37)),
        ("mask_opacity_commit", ("CubeA", "MaskNode", 0.5, 0.37)),
        ("prompt_scene", "portrait"),
        ("autosave", None),
    ]
