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

"""Test ready-shell restore source-boundary and facade-delegation contracts."""

from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]


READY_SHELL_RESTORE_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "ready_shell_restore_controller.py"
)


READY_SHELL_CONTROLLER_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "ready_shell_controller.py"
)


STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"


STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)


FORBIDDEN_READY_SHELL_RESTORE_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def _imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_ready_shell_restore_controller_imports_no_forbidden_boundaries() -> None:
    """Ready-shell restore controller should stay Qt-free and adapter-light."""

    imported_modules = _imported_module_names(READY_SHELL_RESTORE_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_READY_SHELL_RESTORE_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_post_show_hydration_logic() -> None:
    """Startup should delegate post-show hydration branch ownership."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    ready_shell_controller_source = READY_SHELL_CONTROLLER_SOURCE.read_text(
        encoding="utf-8"
    )

    assert (
        "managed_ready_launch.create_initial_workspace_prehydration_task("
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_initial_workspace_prehydration_task("
        not in source
    )
    assert "create_ready_shell_initial_workspace_prehydration_task(" not in source
    assert "ReadyShellInitialWorkspacePrehydrationTask(" not in source
    assert "def prehydrate_initial_workspace_task" not in source
    assert "prehydrate_ready_shell_initial_workspace_task(" not in source
    assert " prehydrate_ready_shell_initial_workspace(" not in source
    assert "ready_state.prehydration_attempted = True" not in source
    assert "prehydration_result.attempted" not in source
    assert "prehydrate_initial_workspace_before_show(" not in source
    assert "prehydrate_initial_workspace_before_show(" in ready_shell_controller_source
    assert "Hidden workspace prehydration exceeded budget" not in source
    assert "managed_ready_launch.create_post_show_controller(" in launch_source
    assert "managed_ready_runtime.create_post_show_controller(" not in source
    assert "create_bound_ready_shell_post_show_controller(" not in source
    assert "create_ready_shell_post_show_controller(" not in source
    assert "ReadyShellPostShowController(" not in source
    assert "def hydrate_initial_workspace_task" not in source
    assert " hydrate_ready_shell_initial_workspace(" not in source
    assert "hydrate_ready_shell_initial_workspace(" in ready_shell_controller_source
    assert "hydrate_initial_workspace_after_show(" not in source
    assert "hydrate_initial_workspace_after_show(" in ready_shell_controller_source
    assert "managed_ready_launch.create_show_gate_task(" in launch_source
    assert "managed_ready_runtime.create_show_gate_task(" not in source
    assert "create_ready_shell_show_gate_task(" not in source
    assert "ReadyShellShowGateTask(" not in source
    assert "try_reveal_ready_shell(" not in source
    assert "prepare_ready_shell_hidden_restore_runtime(" not in source
    assert (
        "prepare_ready_shell_hidden_restore_runtime(" in ready_shell_controller_source
    )
    assert "prepare_hidden_restore_runtime_before_show(" not in source
    assert (
        "prepare_hidden_restore_runtime_before_show(" in ready_shell_controller_source
    )
    assert "post_comfy.hidden_restore_runtime_prepare.skip" not in source
    assert "Failed to prepare restored workspace runtime before reveal" not in source
    assert "project_ready_shell_backend_state(" not in source
    assert "project_ready_shell_backend_state(" in ready_shell_controller_source
    assert "update_built_shell_backend_state(" not in source
    assert "update_shell_backend_state(" in ready_shell_controller_source
    assert "generation_action_controller" not in source
    assert "shell_backend_state.update" not in source
    assert "schedule_ready_shell_post_show_hydration(" not in source
    assert "schedule_ready_shell_post_show_hydration(" in ready_shell_controller_source
    assert "schedule_post_show_hydration_after_reveal(" not in source
    assert "schedule_post_show_hydration_after_reveal(" in ready_shell_controller_source
    assert "post_show.hydration.queued" not in source
    assert 'reason="already_started"' not in source
    assert "post_show.hydration.finish_restore_layout.fallback" not in source
    assert "post_show.hydration.full_hydrate" not in source
    assert "post_comfy.nonessential_warmups.waiting_after_hydration" not in source
    assert "managed_ready_launch.create_minimum_ready_task(" in launch_source
    assert "managed_ready_runtime.create_minimum_ready_task(" not in source
    assert "create_ready_shell_minimum_ready_task(" not in source
    assert "ReadyShellMinimumReadyTask(" not in source
    assert "def mark_minimum_shell_ready_task" not in source
    assert "mark_ready_shell_minimum_ready_task(" not in source
    assert "mark_ready_shell_minimum_ready(" not in source
    assert "mark_minimum_shell_ready_task.start" not in source
    assert "mark_minimum_shell_ready_task.end" not in source
    assert "managed_ready_launch.create_prompt_editor_warmup_task(" in launch_source
    assert "managed_ready_runtime.create_prompt_editor_warmup_task(" not in source
    assert "create_ready_shell_prompt_editor_warmup_task(" not in source
    assert "ReadyShellPromptEditorWarmupTask(" not in source
    assert "warm_ready_shell_prompt_editor_gui(" not in source
    assert "warm_prompt_editor_gui_before_reveal(" not in source
    assert "warm_prompt_editor_gui_before_reveal(" in ready_shell_controller_source
    assert "warm_prompt_editor_gui_task.start" not in source
    assert "warm_prompt_editor_gui_task.run" not in source
    assert "emit_ready_shell_visible_startup_summary(" not in source
    assert "emit_ready_shell_visible_startup_summary(" in ready_shell_controller_source
    assert "emit_visible_startup_summary(" not in source
    assert "log_visible_startup_summary(" in ready_shell_controller_source
    assert "build_visible_loading_summary(" not in source
    assert "startup.visible_loading.summary" not in source
    assert "attach_restore_asset_preload_to_shell(" not in source
    assert "attach_restore_asset_preload_to_shell(" in ready_shell_controller_source
    assert "workspace_restore_image_adapter" not in source
    assert "set_restore_asset_preload" not in source
