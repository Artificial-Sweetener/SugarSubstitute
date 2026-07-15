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

"""Tests for pure live visual event projection helpers."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.application.generation.live_event_projection import (
    live_event_scene_fields,
)
from substitute.application.workflows import (
    LivePreviewEvent,
    OutputSceneIdentity,
    OutputVisualIdentity,
    PreviewNodeIdentity,
    SourceOnlyOutputIdentity,
)


def test_live_event_scene_fields_returns_scene_identity_fields() -> None:
    """Scene-routed live events should expose logging-ready scene fields."""

    event = _preview_event(
        scene=OutputSceneIdentity(
            run_id="run-1",
            key="scene-a",
            title="Scene A",
            order=2,
            count=5,
        )
    )

    assert live_event_scene_fields(event) == ("run-1", "scene-a", "Scene A", 2, 5)


def test_live_event_scene_fields_returns_empty_fields_for_source_only_events() -> None:
    """Source-only live events should project empty scene fields."""

    assert live_event_scene_fields(
        _preview_event(scene=SourceOnlyOutputIdentity())
    ) == (
        None,
        None,
        None,
        None,
        None,
    )


def test_live_event_projection_import_boundary() -> None:
    """Live-event projection must not import Qt or presentation modules."""

    source_path = Path("substitute/application/generation/live_event_projection.py")
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden_prefixes = (
        "PySide6",
        "qfluentwidgets",
        "qframelesswindow",
        "substitute.presentation",
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names = tuple(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_names = (node.module or "",)
        else:
            continue

        assert not any(
            name == prefix or name.startswith(f"{prefix}.")
            for name in imported_names
            for prefix in forbidden_prefixes
        )


def _preview_event(
    *,
    scene: OutputSceneIdentity | SourceOnlyOutputIdentity,
) -> LivePreviewEvent:
    """Build a strict preview event for projection tests."""

    return LivePreviewEvent(
        identity=OutputVisualIdentity(
            workflow_id="wf-1",
            generation_run_id="gen-1",
            prompt_id="prompt-1",
            client_id="client-1",
            source_key="wf-1:node",
            source_label="Node",
            scene=scene,
        ),
        image=object(),
        node_identity=PreviewNodeIdentity(
            resolved_node_id="node",
            metadata_node_id=None,
            display_node_id=None,
            parent_node_id=None,
            real_node_id=None,
        ),
    )
