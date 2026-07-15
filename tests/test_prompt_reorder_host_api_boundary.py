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

"""Lock the public prompt-editor host boundary for reorder refactors."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from substitute.presentation.editor.prompt_editor.shell.widget import (
    PROMPT_EDITOR_HOST_FACADE_INVENTORY,
    PROMPT_EDITOR_PUBLIC_WIDGET_BOUNDARY,
)
from substitute.presentation.editor.prompt_editor.widget import PromptEditor


PROMPT_EDITOR_METHODS: Any = PromptEditor

REORDER_HOST_METHODS = (
    "set_reorder_preview_state",
    "clear_reorder_preview_state",
    "reorder_preview_fragments",
    "reorder_live_chip_geometry_snapshot",
    "reorder_preview_chip_geometry_snapshot",
    "reorder_preview_cursor_rect",
    "reorder_base_drag_fragments",
    "reorder_base_drag_chip_geometry_snapshot",
    "reorder_base_drag_cursor_rect",
    "reorder_base_drag_placement_snapshot",
    "reset_reorder_geometry_cache_counters",
    "reorder_geometry_cache_counters",
    "reorder_placement_at_rect",
    "execute_reorder_action",
)

SURFACE_REORDER_HOST_METHODS = tuple(
    method for method in REORDER_HOST_METHODS if method != "execute_reorder_action"
)

FORBIDDEN_HOST_IMPORT_MODULES = (
    "substitute.presentation.editor.prompt_editor.projection.reorder_preview_projection",
    "substitute.presentation.editor.prompt_editor.projection.reorder_drop_targets",
    "substitute.presentation.editor.prompt_editor.projection.reorder_keyboard_navigation",
    "substitute.presentation.editor.prompt_editor.projection.reorder_animation",
    "substitute.presentation.editor.prompt_editor.interactions.reorder_session",
    "substitute.presentation.editor.prompt_editor.interactions.reorder_preview_sync",
    "substitute.presentation.editor.prompt_editor.overlays.reorder_animation_presenter",
    "substitute.presentation.editor.prompt_editor.overlays.reorder_landing_shadow",
    "substitute.presentation.editor.prompt_editor.overlays.reorder_telemetry",
)


class _RecordingCollaborator:
    """Record forwarded calls while returning deterministic method results."""

    def __init__(self) -> None:
        """Initialize call recording."""

        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def __getattr__(self, name: str) -> Any:
        """Return a recorder for one forwarded method name."""

        def record(*args: object, **kwargs: object) -> object:
            """Record one call and return a method-specific sentinel."""

            self.calls.append((name, args, kwargs))
            return _result_for(name)

        return record


class _PromptEditorHostDouble:
    """Provide only the collaborators used by reorder forwarding methods."""

    def __init__(self) -> None:
        """Create surface and command-adapter fakes."""

        self._surface = _RecordingCollaborator()
        self._command_adapter = _RecordingCollaborator()


def test_prompt_editor_forwards_reorder_surface_methods_to_projection_surface() -> None:
    """Reorder preview and geometry APIs should stay thin surface forwards."""

    host = _PromptEditorHostDouble()

    assert (
        PROMPT_EDITOR_METHODS.set_reorder_preview_state(host, "preview-state") is None
    )
    assert PROMPT_EDITOR_METHODS.clear_reorder_preview_state(host) is None
    assert (
        PROMPT_EDITOR_METHODS.reorder_preview_fragments(host, start=1, end=4)
        == "result:reorder_preview_fragments"
    )
    assert (
        PROMPT_EDITOR_METHODS.reorder_live_chip_geometry_snapshot(
            host,
            layout_view="layout",
            chip_rendered_ranges_by_index="rendered-ranges",
            chip_owned_ranges_by_index="owned-ranges",
        )
        == "result:reorder_live_chip_geometry_snapshot"
    )
    assert (
        PROMPT_EDITOR_METHODS.reorder_preview_chip_geometry_snapshot(
            host,
            snapshot="preview-snapshot",
            layout_view="preview-layout",
        )
        == "result:reorder_preview_chip_geometry_snapshot"
    )
    assert (
        PROMPT_EDITOR_METHODS.reorder_preview_cursor_rect(host, 7)
        == "result:reorder_preview_cursor_rect"
    )
    assert (
        PROMPT_EDITOR_METHODS.reorder_base_drag_fragments(host, start=2, end=8)
        == "result:reorder_base_drag_fragments"
    )
    assert (
        PROMPT_EDITOR_METHODS.reorder_base_drag_chip_geometry_snapshot(
            host,
            snapshot="base-snapshot",
            layout_view="base-layout",
        )
        == "result:reorder_base_drag_chip_geometry_snapshot"
    )
    assert (
        PROMPT_EDITOR_METHODS.reorder_base_drag_cursor_rect(host, 11)
        == "result:reorder_base_drag_cursor_rect"
    )
    assert (
        PROMPT_EDITOR_METHODS.reorder_base_drag_placement_snapshot(
            host,
            snapshot="placement-snapshot",
            layout_view="placement-layout",
        )
        == "result:reorder_base_drag_placement_snapshot"
    )
    assert PROMPT_EDITOR_METHODS.reset_reorder_geometry_cache_counters(host) is None
    assert (
        PROMPT_EDITOR_METHODS.reorder_geometry_cache_counters(host)
        == "result:reorder_geometry_cache_counters"
    )
    assert (
        PROMPT_EDITOR_METHODS.reorder_placement_at_rect(
            host,
            "drag-rect",
            snapshot="placement-snapshot",
            active_placement_id="active-placement",
        )
        == "result:reorder_placement_at_rect"
    )

    assert host._command_adapter.calls == []
    assert host._surface.calls == [
        ("set_reorder_preview_state", ("preview-state",), {}),
        ("clear_reorder_preview_state", (), {}),
        ("reorder_preview_fragments", (), {"start": 1, "end": 4}),
        (
            "reorder_live_chip_geometry_snapshot",
            (),
            {
                "layout_view": "layout",
                "chip_rendered_ranges_by_index": "rendered-ranges",
                "chip_owned_ranges_by_index": "owned-ranges",
            },
        ),
        (
            "reorder_preview_chip_geometry_snapshot",
            (),
            {"snapshot": "preview-snapshot", "layout_view": "preview-layout"},
        ),
        ("reorder_preview_cursor_rect", (7,), {}),
        ("reorder_base_drag_fragments", (), {"start": 2, "end": 8}),
        (
            "reorder_base_drag_chip_geometry_snapshot",
            (),
            {"snapshot": "base-snapshot", "layout_view": "base-layout"},
        ),
        ("reorder_base_drag_cursor_rect", (11,), {}),
        (
            "reorder_base_drag_placement_snapshot",
            (),
            {"snapshot": "placement-snapshot", "layout_view": "placement-layout"},
        ),
        ("reset_reorder_geometry_cache_counters", (), {}),
        ("reorder_geometry_cache_counters", (), {}),
        (
            "reorder_placement_at_rect",
            ("drag-rect",),
            {
                "snapshot": "placement-snapshot",
                "active_placement_id": "active-placement",
            },
        ),
    ]


def test_prompt_editor_forwards_reorder_commits_to_command_adapter() -> None:
    """Reorder source mutation should stay on the command adapter boundary."""

    host = _PromptEditorHostDouble()

    result = PROMPT_EDITOR_METHODS.execute_reorder_action(
        host,
        "request",
        mutation_service="mutation-service",
        syntax_service="syntax-service",
        syntax_profile="syntax-profile",
    )

    assert result == "result:execute_reorder_action"
    assert host._surface.calls == []
    assert host._command_adapter.calls == [
        (
            "execute_reorder_action",
            ("request",),
            {
                "mutation_service": "mutation-service",
                "syntax_service": "syntax-service",
                "syntax_profile": "syntax-profile",
            },
        )
    ]


def test_shell_widget_boundary_exposes_reorder_host_methods() -> None:
    """Shell boundary metadata should keep the full reorder host API visible."""

    boundary_methods = _public_widget_boundary_methods()
    inventory_methods = _host_facade_inventory_methods()

    assert set(REORDER_HOST_METHODS) <= boundary_methods
    assert set(REORDER_HOST_METHODS) <= inventory_methods


def test_host_boundary_files_do_not_import_future_reorder_internals() -> None:
    """Public host files should not expose upcoming internal reorder owners."""

    repository_root = Path(__file__).resolve().parents[1]
    boundary_files = (
        repository_root
        / "substitute"
        / "presentation"
        / "editor"
        / "prompt_editor"
        / "widget.py",
        repository_root
        / "substitute"
        / "presentation"
        / "editor"
        / "prompt_editor"
        / "widget.pyi",
        repository_root
        / "substitute"
        / "presentation"
        / "editor"
        / "prompt_editor"
        / "shell"
        / "widget.py",
    )

    imported_modules = {
        imported_module
        for boundary_file in boundary_files
        for imported_module in _imported_modules(boundary_file)
    }

    assert set(FORBIDDEN_HOST_IMPORT_MODULES).isdisjoint(imported_modules)


def _public_widget_boundary_methods() -> set[str]:
    """Return every method named by the public shell boundary metadata."""

    return {
        *PROMPT_EDITOR_PUBLIC_WIDGET_BOUNDARY.shell_methods,
        *PROMPT_EDITOR_PUBLIC_WIDGET_BOUNDARY.editing_methods,
        *PROMPT_EDITOR_PUBLIC_WIDGET_BOUNDARY.projection_methods,
        *PROMPT_EDITOR_PUBLIC_WIDGET_BOUNDARY.feature_methods,
        *PROMPT_EDITOR_PUBLIC_WIDGET_BOUNDARY.command_methods,
    }


def _host_facade_inventory_methods() -> set[str]:
    """Return every method classified by the host facade inventory."""

    return {
        *PROMPT_EDITOR_HOST_FACADE_INVENTORY.public_compatibility,
        *PROMPT_EDITOR_HOST_FACADE_INVENTORY.lifecycle_signal_owner,
        *PROMPT_EDITOR_HOST_FACADE_INVENTORY.shell_presentation,
        *PROMPT_EDITOR_HOST_FACADE_INVENTORY.feature_action_presentation,
        *PROMPT_EDITOR_HOST_FACADE_INVENTORY.external_action_execution,
        *PROMPT_EDITOR_HOST_FACADE_INVENTORY.command_source_adapter,
        *PROMPT_EDITOR_HOST_FACADE_INVENTORY.obsolete_internal_bridge,
    }


def _imported_modules(path: Path) -> Iterator[str]:
    """Yield fully qualified import module names used by one Python source file."""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package = _package_name_for(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            module = _absolute_import_module(package, node)
            if module is not None:
                yield module


def _absolute_import_module(package: str, node: ast.ImportFrom) -> str | None:
    """Return one absolute import module for an ``ImportFrom`` node."""

    if node.level == 0:
        return node.module
    package_parts = package.split(".")
    prefix_length = len(package_parts) - node.level + 1
    if prefix_length <= 0:
        return node.module
    prefix = ".".join(package_parts[:prefix_length])
    if node.module is None:
        return prefix
    return f"{prefix}.{node.module}"


def _package_name_for(path: Path) -> str:
    """Return the package containing one prompt-editor boundary file."""

    parts = path.with_suffix("").parts
    substitute_index = parts.index("substitute")
    return ".".join(parts[substitute_index:-1])


def _result_for(method_name: str) -> object:
    """Return production-like ``None`` for mutators and sentinels for queries."""

    if method_name in {
        "set_reorder_preview_state",
        "clear_reorder_preview_state",
        "reset_reorder_geometry_cache_counters",
    }:
        return None
    return f"result:{method_name}"
