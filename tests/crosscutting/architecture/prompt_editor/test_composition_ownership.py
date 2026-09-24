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

"""Enforce direct ownership for prompt-editor composition families."""

from __future__ import annotations

import ast

from .inventory import PROMPT_PRESENTATION_ROOT


def _class_methods(path_name: str, class_name: str) -> set[str]:
    """Return directly declared method names for one composition class."""
    path = PROMPT_PRESENTATION_ROOT / "composition" / path_name
    tree = ast.parse(path.read_text(encoding="utf-8"))
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    return {
        node.name
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_projection_and_execution_composition_have_direct_owners() -> None:
    """Keep projection and async construction behind the core runtime."""
    assert not (PROMPT_PRESENTATION_ROOT / "composition" / "factory.py").exists()
    execution_methods = _class_methods(
        "execution_factory.py",
        "PromptEditorExecutionFactory",
    )
    projection_methods = _class_methods(
        "projection_factory.py",
        "PromptEditorProjectionFactory",
    )

    assert {"build_task_executor", "build_request_channel"} <= execution_methods
    assert "build" in projection_methods

    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    core_runtime_source = (
        PROMPT_PRESENTATION_ROOT / "composition" / "core_runtime.py"
    ).read_text(encoding="utf-8")
    assert "build_prompt_editor_core_runtime(" in widget_source
    assert "PromptEditorExecutionFactory(" in core_runtime_source
    assert "PromptEditorProjectionFactory(" in core_runtime_source
    assert "PromptEditorExecutionFactory(" not in widget_source
    assert "PromptEditorProjectionFactory(" not in widget_source


def test_autocomplete_and_menu_composition_have_direct_owners() -> None:
    """Keep autocomplete and menu construction out of the mixed factory."""
    autocomplete_methods = _class_methods(
        "autocomplete_factory.py",
        "PromptEditorAutocompleteFactory",
    )
    menu_methods = _class_methods("menu_factory.py", "PromptEditorMenuFactory")

    assert "build" in autocomplete_methods
    assert {
        "build_prompt_menu_presenter",
        "build_inline_lora_menu_presenter",
        "build_lora_picker_popup_presenter",
    } <= menu_methods

    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    menu_runtime_source = (
        PROMPT_PRESENTATION_ROOT / "composition" / "menu_runtime.py"
    ).read_text(encoding="utf-8")
    host_runtime_source = (
        PROMPT_PRESENTATION_ROOT / "composition" / "host_runtime.py"
    ).read_text(encoding="utf-8")
    core_runtime_source = (
        PROMPT_PRESENTATION_ROOT / "composition" / "core_runtime.py"
    ).read_text(encoding="utf-8")
    assert "PromptEditorAutocompleteFactory(" in core_runtime_source
    assert "PromptEditorAutocompleteFactory(" not in widget_source
    assert "build_prompt_editor_host_runtime(" in widget_source
    assert "build_prompt_editor_menu_runtime(" in host_runtime_source
    assert "build_prompt_editor_menu_runtime(" not in widget_source
    assert "PromptEditorMenuFactory(" in menu_runtime_source
    assert "PromptContextMenuSnapshotAssembler(" in menu_runtime_source
    assert "PromptShellContextMenuController(" in menu_runtime_source
    assert "_shell_context_menu" not in widget_source
    assert "_prompt_menu_presenter" not in widget_source
    assert "_inline_lora_menu_presenter" not in widget_source


def test_syntax_interaction_composition_has_a_direct_owner() -> None:
    """Keep syntax, reorder, and weight construction behind the core runtime."""
    syntax_methods = _class_methods("syntax_factory.py", "PromptEditorSyntaxFactory")

    assert "build" in syntax_methods

    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    core_runtime_source = (
        PROMPT_PRESENTATION_ROOT / "composition" / "core_runtime.py"
    ).read_text(encoding="utf-8")
    assert "PromptEditorSyntaxFactory(" in core_runtime_source
    assert "PromptEditorSyntaxFactory(" not in widget_source


def test_feature_presentation_composition_has_one_runtime_owner() -> None:
    """Keep catalog, trigger-word, and document composition out of the widget."""

    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    feature_runtime_source = (
        PROMPT_PRESENTATION_ROOT / "composition" / "feature_runtime.py"
    ).read_text(encoding="utf-8")

    assert "build_prompt_editor_feature_runtime(" in widget_source
    assert "PromptLoraMetadataPresentation(" in feature_runtime_source
    assert "build_prompt_editor_catalog_refresh_facade(" in feature_runtime_source
    assert "PromptLoraTriggerWordController(" in feature_runtime_source
    assert "build_prompt_editor_document_facade(" in feature_runtime_source
    assert "PromptLoraMetadataPresentation(" not in widget_source
    assert "build_prompt_editor_catalog_refresh_facade(" not in widget_source
    assert "PromptLoraTriggerWordController(" not in widget_source
    assert "build_prompt_editor_document_facade(" not in widget_source


def test_mounted_host_integration_has_one_runtime_owner() -> None:
    """Keep event, signal, lifecycle, resize, and layout mounting together."""

    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    host_runtime_source = (
        PROMPT_PRESENTATION_ROOT / "composition" / "host_runtime.py"
    ).read_text(encoding="utf-8")

    assert "build_prompt_editor_host_runtime(" in widget_source
    assert "PromptEditorHostEventRouter(" in host_runtime_source
    assert "wire_prompt_editor_construction_lifecycle(" in host_runtime_source
    assert "build_resize_handle(" in host_runtime_source
    assert "bind_prompt_editor_signals(" in host_runtime_source
    assert "apply_prompt_editor_initial_layout(" in host_runtime_source
    assert "PromptEditorHostEventRouter(" not in widget_source
    assert "wire_prompt_editor_construction_lifecycle(" not in widget_source
    assert "build_resize_handle(" not in widget_source
    assert "bind_prompt_editor_signals(" not in widget_source
    assert "apply_prompt_editor_initial_layout(" not in widget_source


def test_shell_mechanics_have_one_runtime_composition_owner() -> None:
    """Keep mutually dependent shell mechanics outside the public widget."""

    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    shell_runtime_source = (
        PROMPT_PRESENTATION_ROOT / "shell" / "runtime.py"
    ).read_text(encoding="utf-8")

    assert "build_prompt_editor_shell_runtime(" in widget_source
    assert "PromptEditorShell(" in shell_runtime_source
    assert "PromptShellQFluentChrome(" in shell_runtime_source
    assert "PromptShellScrollDelegate(" in shell_runtime_source
    assert "PromptShellSizingController(" in shell_runtime_source
    assert "PromptClipboardPasteCompletionOwner(" in shell_runtime_source
    assert "self._qfluent_chrome" not in widget_source
    assert "self._scroll_delegate" not in widget_source
    assert "self._sizing" not in widget_source
    assert "self._clipboard_paste_completion" not in widget_source


def test_widget_publishes_one_staged_runtime_without_collaborator_aliases() -> None:
    """Keep mounted collaborator identity and lifecycle in one explicit owner."""

    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    mount_source = (PROMPT_PRESENTATION_ROOT / "runtime_mount.py").read_text(
        encoding="utf-8"
    )

    assert "self._runtime = PromptEditorRuntimeMount()" in widget_source
    assert "self._runtime.mount_shell(shell_runtime)" in widget_source
    assert "mount_projection=self._runtime.mount_projection" in widget_source
    assert "self._runtime.mount_core(core_runtime)" in widget_source
    assert "self._runtime.mount_features(feature_runtime)" in widget_source
    assert "mount_runtime=self._runtime.mount_host" in widget_source
    assert "core.projection is not projection" in mount_source

    for replaced_alias in (
        "self._shell_runtime =",
        "self._surface =",
        "self._interaction_controller =",
        "self._diagnostics_feature_controller =",
        "self._menu_runtime =",
        "self._document_facade =",
        "self._catalog_refresh_facade =",
    ):
        assert replaced_alias not in widget_source


def test_mounted_host_adapter_owns_shell_callbacks_and_panel_wheel_routing() -> None:
    """Keep late-bound shell integration out of the public Qt facade."""

    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    adapter_source = (PROMPT_PRESENTATION_ROOT / "host_adapter.py").read_text(
        encoding="utf-8"
    )

    assert "host_adapter = PromptEditorHostAdapter(" in widget_source
    assert "current = self._host.parentWidget()" in adapter_source
    assert "handler(event)" in adapter_source
    assert "current = self.parentWidget()" not in widget_source

    for moved_callback in (
        "content_viewport",
        "chrome_surface",
        "scroll_surface",
        "update_backing_fill",
        "handle_viewport_wheel_event",
        "forward_wheel_event_to_editor_panel",
        "handle_surface_text_changed",
        "handle_surface_syntax_action",
        "handle_surface_mouse_release",
        "surface_content_height",
        "surface_is_alive",
        "resize_handle",
    ):
        assert f"def {moved_callback}(" in adapter_source
        assert f"def {moved_callback}(" not in widget_source
