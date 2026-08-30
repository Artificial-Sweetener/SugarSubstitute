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

"""Define the exact current source execution-ownership policy."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SUBSTITUTE_ROOT = PROJECT_ROOT / "substitute"

LEGACY_EXECUTION_FILE_REASONS = {
    "substitute/infrastructure/comfy/posix_guardian_entry.py": (
        "external POSIX helper process cannot consume the app execution runtime; "
        "covered by tests/test_posix_guardian_containment.py"
    ),
}
LEGACY_EXECUTION_FILES = frozenset(LEGACY_EXECUTION_FILE_REASONS)
EXECUTION_ADAPTER_FILES = frozenset(
    {
        "substitute/app/bootstrap/execution_runtime.py",
        "substitute/infrastructure/execution/long_lived_task.py",
        "substitute/infrastructure/execution/parallel_map.py",
        "substitute/infrastructure/execution/process_output.py",
        "substitute/infrastructure/execution/host_execution_scheduler.py",
        "substitute/infrastructure/execution/host_execution_diagnostics.py",
        "substitute/infrastructure/execution/thread_pool_admission.py",
        "substitute/infrastructure/execution/thread_pool_lane.py",
        "substitute/application/execution/cancellation.py",
        "substitute/application/execution/policies.py",
        "substitute/application/execution/task_scope.py",
        "substitute/presentation/editor/prompt_editor/async_work/task_executor.py",
    }
)
EXECUTION_LANE_FACTORY_FILES = frozenset(
    {"substitute/app/bootstrap/execution_runtime.py"}
)
EXECUTION_LANE_CONSTRUCTORS = frozenset({"ThreadPoolExecutionLane"})
DOCUMENTED_NON_EXECUTION_FILES = {
    "substitute/app/bootstrap/launch_splash.py": frozenset(
        {"threading.Event", "threading.Lock"}
    ),
    "substitute/app/bootstrap/lifecycle.py": frozenset({"threading.Lock"}),
    "substitute/app/bootstrap/startup_shutdown.py": frozenset({"threading.Lock"}),
    "substitute/app/bootstrap/workspace_restore_asset_preload.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/application/cube_library/update_coordinator.py": frozenset(
        {"threading.Lock"}
    ),
    "substitute/application/cubes/cube_load_service.py": frozenset({"threading.Lock"}),
    "substitute/application/localization/comfy_node_catalog_store.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/application/model_metadata/model_catalog_service.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/application/model_metadata/model_choice_catalog_index.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/application/model_metadata/rich_choice_resolver.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/application/model_metadata/scoped_metadata_refresh_service.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/application/prompt_editor/document/cache.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/application/prompt_editor/lora/catalog.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/application/prompt_editor/projection/syntax_service.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/application/workspace_state/session_autosave_service.py": frozenset(
        {"threading.Lock"}
    ),
    "substitute/devtools/prompt_editor_performance/instrumentation.py": frozenset(
        {"threading.Lock"}
    ),
    "substitute/application/recipes/model_hash_lookup.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/infrastructure/comfy/managed_launcher.py": frozenset(
        {"threading.Lock"}
    ),
    "substitute/infrastructure/external/comfy_object_info_client.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/infrastructure/localization/comfy_i18n_client.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/infrastructure/persistence/file_prompt_autocomplete_gateway.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/infrastructure/persistence/configured_prompt_autocomplete_gateway.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/infrastructure/persistence/image_naming.py": frozenset(
        {"threading.Lock"}
    ),
    "substitute/presentation/shell/model_catalog_update_bridge.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/presentation/shell/model_metadata_update_bridge.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/presentation/shell/model_metadata_context_action_handler.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/shared/diagnostics/prompt_editor_work.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/presentation/cube_picker/cube_stack_cart_modal.py": frozenset(
        {"QEventLoop"}
    ),
    "substitute/shared/cutecanvas_sam_warmup_state.py": frozenset({"threading.Lock"}),
    "substitute/shared/startup_trace.py": frozenset({"threading.RLock"}),
}
NEVER_CANCELLED_FILE_REASONS: dict[str, str] = {}
LONG_LIVED_HANDLE_CONSTRUCTOR_FILES = {
    "substitute/app/bootstrap/execution_runtime.py": (
        "main process runtime owns long-lived task start and registration"
    ),
    "substitute/app/bootstrap/standalone_long_lived_execution.py": (
        "explicit standalone owner for pre-runtime and helper-process boundaries"
    ),
}
WORKER_TERMINOLOGY_FILE_REASONS = {
    "substitute/app/bootstrap/execution_runtime.py": "runtime lane configuration maps logical lanes to concrete thread pools",
    "substitute/infrastructure/execution/thread_pool_lane.py": "concrete thread-pool adapter owns worker-thread implementation details",
    "substitute/infrastructure/execution/thread_pool_admission.py": "physical bounded-admission adapter owns its worker-thread implementation",
    "substitute/infrastructure/execution/parallel_map.py": "bounded parallel-map adapter owns thread-pool implementation details",
    "substitute/infrastructure/execution/host_execution_scheduler.py": "host scheduler owns bounded physical canvas execution",
    "substitute/infrastructure/execution/host_execution_model.py": "host execution values describe physical worker state",
    "substitute/app/bootstrap/canvas_execution_runtime.py": "canvas execution composition configures host worker capacity",
    "substitute/application/node_behavior/__init__.py": "exports Comfy sampler_worker domain-role inference",
    "substitute/domain/node_behavior/__init__.py": "exports Comfy sampler_worker domain-role inference",
    "substitute/domain/node_behavior/inference.py": "models Comfy sampler_worker as node behavior domain terminology",
    "substitute/domain/node_behavior/models.py": "models Comfy sampler_worker as node behavior domain terminology",
}
WORKER_TERMINOLOGY_TERMS = ("worker", "Worker", "WORKER", "thread_name_prefix")
PROMPT_PRESENTATION_EXECUTION_BOUNDARY_ROOTS = (
    SUBSTITUTE_ROOT / "presentation" / "editor",
    SUBSTITUTE_ROOT / "presentation" / "managed_text_assets",
)
PROMPT_PRESENTATION_EXECUTION_BOUNDARY_FILES = (
    SUBSTITUTE_ROOT / "presentation" / "shell" / "workflow_ui_factory.py",
)
PROMPT_PRESENTATION_QT_DISPATCHER_FILES = frozenset(
    {
        "substitute/presentation/editor/prompt_editor/async_work/main_thread_dispatcher.py"
    }
)
PROMPT_PRESENTATION_RUNTIME_TERMS = (
    "execution_runtime",
    "ExecutionRuntime(",
    ".submitter(",
)
PURE_LAYER_ROOTS = (SUBSTITUTE_ROOT / "domain", SUBSTITUTE_ROOT / "application")
FORBIDDEN_QT_EXECUTION_IMPORT = "substitute.presentation.qt.execution"
RAW_EXECUTION_IMPORTS = {
    "threading.Condition": "threading.Condition",
    "threading.Event": "threading.Event",
    "threading.Lock": "threading.Lock",
    "threading.RLock": "threading.RLock",
    "threading.Thread": "threading.Thread",
    "concurrent.futures.ThreadPoolExecutor": "ThreadPoolExecutor",
    "PySide6.QtCore.QEventLoop": "QEventLoop",
    "PySide6.QtCore.QRunnable": "QRunnable",
    "PySide6.QtCore.QThreadPool": "QThreadPool",
}
