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

"""Compose and mount prompt-editor host integration in lifecycle order."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QPoint
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import QWidget

from ..host_event_router import (
    PromptEditorHostEventBindings,
    PromptEditorHostEventRouter,
)
from ..shell import PromptEditorShellRuntime
from .bundle_factory import build_resize_handle, bundle_collaborators
from .collaborator_bundle import PromptEditorConstructionInputs
from .context import PromptEditorCompositionContext
from .core_runtime import PromptEditorCoreRuntime
from .feature_runtime import PromptEditorFeatureRuntime
from .menu_runtime import (
    PromptEditorMenuActionBindings,
    PromptEditorMenuFeatureOwners,
    PromptEditorMenuHostBindings,
    PromptEditorMenuRuntime,
    build_prompt_editor_menu_runtime,
)
from .signal_bindings import PromptEditorSignalHost, bind_prompt_editor_signals
from .wiring import (
    PromptEditorConstructionObserver,
    PromptEditorInitialLayoutHost,
    apply_prompt_editor_initial_layout,
    wire_prompt_editor_construction_lifecycle,
)


@dataclass(frozen=True, slots=True)
class PromptEditorHostRuntimeBindings:
    """Declare public-host operations consumed during mounted integration."""

    signal_host: PromptEditorSignalHost
    layout_host: PromptEditorInitialLayoutHost
    mount_runtime: Callable[[PromptEditorHostRuntime], None]
    queue_scene: Callable[[str], None]
    is_read_only: Callable[[], bool]
    rich_prompt_rendering_enabled: Callable[[], bool]
    toggle_rich_prompt_rendering: Callable[[bool], None]
    has_text_selection: Callable[[], bool]
    source_position_for_global_pos: Callable[[QPoint], int]
    current_source_position: Callable[[], int]
    prompt_menu_requires_custom_actions: Callable[[], bool]
    show_native_context_menu: Callable[[QContextMenuEvent], None]
    cursor_global_position: Callable[[], QPoint]


@dataclass(frozen=True, slots=True)
class PromptEditorHostRuntime:
    """Carry menu, event-routing, and resize owners mounted on the public host."""

    menu: PromptEditorMenuRuntime
    events: PromptEditorHostEventRouter
    resize_handle: QWidget


def build_prompt_editor_host_runtime(
    inputs: PromptEditorConstructionInputs,
    context: PromptEditorCompositionContext,
    shell: PromptEditorShellRuntime,
    core: PromptEditorCoreRuntime,
    features: PromptEditorFeatureRuntime,
    bindings: PromptEditorHostRuntimeBindings,
    observer: PromptEditorConstructionObserver,
) -> PromptEditorHostRuntime:
    """Mount menus, event routing, lifecycle, signals, and initial layout."""

    services = core.services
    projection = core.projection
    syntax = core.syntax
    menu = build_prompt_editor_menu_runtime(
        context,
        PromptEditorMenuFeatureOwners(
            diagnostics=core.diagnostics,
            lora_metadata=features.lora_metadata,
            lora_trigger_words=features.lora_trigger_words,
            scene_publication=services.scene_context_publication,
            scene_positions=services.scene_position_preparation,
            segment_presets=services.segment_preset_controller,
            danbooru=services.danbooru_action_controller,
            source_identity=projection.source_commands.source_identity,
            feature_profile_id=(
                lambda: services.feature_profile_controller.identity.feature_profile_id
            ),
        ),
        PromptEditorMenuActionBindings(
            context_insertion=core.context_insertion,
            lora_thumbnail_cache=projection.lora_thumbnail_cache,
            clipboard=projection.clipboard_history_controller,
            external_url_actions=core.external_url_actions,
            open_danbooru_wiki_for_selection=(
                core.danbooru_dialog.open_wiki_for_selection
            ),
            queue_scene=bindings.queue_scene,
            is_read_only=bindings.is_read_only,
            rich_prompt_rendering_enabled=bindings.rich_prompt_rendering_enabled,
            toggle_rich_prompt_rendering=bindings.toggle_rich_prompt_rendering,
            metadata_action_handler=inputs.model_metadata_action_handler,
        ),
        PromptEditorMenuHostBindings(
            finish_pending_key_edit_block=(
                lambda reason: projection.edit_execution.finish_pending_key_edit_block(
                    reason=reason
                )
            ),
            has_text_selection=bindings.has_text_selection,
            source_position_for_global_pos=bindings.source_position_for_global_pos,
            current_source_position=bindings.current_source_position,
            prompt_menu_requires_custom_actions=(
                bindings.prompt_menu_requires_custom_actions
            ),
            show_native_context_menu=bindings.show_native_context_menu,
            cursor_global_position=bindings.cursor_global_position,
        ),
    )
    events = PromptEditorHostEventRouter(
        PromptEditorHostEventBindings(
            surface=projection.surface,
            shell_viewport=context.shell_viewport,
            content_viewport=projection.surface.viewport(),
            handle_focus_in=shell.chrome.handle_focus_in,
            schedule_focus_out_cleanup=shell.chrome.schedule_focus_out_cleanup,
            handle_key_press=core.key_router.handle_key_press,
            handle_key_release=core.key_router.handle_key_release,
            handle_chrome_event=shell.chrome.handle_event_filter,
            record_context_menu_press=menu.shell.record_context_menu_press,
            forward_context_menu=menu.shell.forward_context_menu_event_to_host,
        )
    )
    services.segment_preset_controller.refresh_menu_model(
        reason="prompt_editor_constructed"
    )
    phase_started_at = observer.started_at()
    lifecycle = wire_prompt_editor_construction_lifecycle(core.diagnostics)
    observer.log_timing(
        "Scheduled prompt editor spellcheck services",
        started_at=phase_started_at,
        diagnostics_controller_enabled=lifecycle.diagnostics_controller_enabled,
        diagnostics_activation_pending=lifecycle.diagnostics_activation_pending,
        level="debug",
    )

    phase_started_at = observer.started_at()
    resize_handle = build_resize_handle(context)
    runtime = PromptEditorHostRuntime(
        menu=menu,
        events=events,
        resize_handle=resize_handle,
    )
    bindings.mount_runtime(runtime)
    resize_handle.hide()
    collaborators = bundle_collaborators(
        projection,
        services,
        core.autocomplete.autocomplete,
        syntax,
        menu.inline_lora,
        resize_handle,
    )
    bind_prompt_editor_signals(
        bindings.signal_host,
        collaborators,
        lora_source_changes=features.lora_trigger_words,
    )
    apply_prompt_editor_initial_layout(bindings.layout_host)
    observer.log_timing(
        "Initialized prompt editor layout",
        started_at=phase_started_at,
        maximum_visible_lines=inputs.maximum_visible_lines,
        level="debug",
    )
    return runtime


__all__ = [
    "PromptEditorHostRuntime",
    "PromptEditorHostRuntimeBindings",
    "build_prompt_editor_host_runtime",
]
