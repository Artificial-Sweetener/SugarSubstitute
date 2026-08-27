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

"""Own CI test execution and platform-applicability policy."""

from __future__ import annotations

import sys
from enum import StrEnum
from typing import Final


class CiPlatform(StrEnum):
    """Identify one operating system supported by the application test suite."""

    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"


MAX_PARALLEL_TEST_WORKERS = 4
MAX_ISOLATED_TEST_WORKERS = 4


PLATFORM_TEST_MODULES: Final[dict[str, frozenset[CiPlatform]]] = {
    # The Windows gateway imports COM bindings that are unavailable before
    # pytest can apply item-level platform markers on Linux and macOS.
    "tests/infrastructure/spellcheck/test_windows_gateway.py": frozenset(
        {CiPlatform.WINDOWS}
    ),
}


ISOLATED_TEST_MODULES = frozenset(
    {
        # This real-shell restore qualification can abort after prior native Qt
        # work in one xdist process, while fresh concurrent processes are stable.
        "tests/qualification/prompt_editor/abuse/test_restored_mounts.py",
        # This real-shell field-wiring owner aborts after prior native Qt work
        # in a reused worker, while fresh processes retain its editor-to-buffer
        # persistence contract.
        "tests/qualification/prompt_editor/real_shell/field_wiring/test_buffer_sync.py",
        # This real-shell autocomplete control-key owner aborts after prior
        # native Qt work in a reused worker, while fresh processes retain its
        # native key-routing and source-safety contracts.
        "tests/qualification/prompt_editor/real_shell/autocomplete_surface/test_control_character_safety.py",
        # This real-shell autocomplete-dismissal owner aborts after prior
        # native Qt work in a reused worker, while fresh processes retain its
        # visible dropdown and ghost-state contracts.
        "tests/qualification/prompt_editor/real_shell/autocomplete_surface/test_dismissal.py",
        # This real-shell autocomplete selection-navigation owner aborts after
        # prior native Qt work in a reused worker, while fresh processes retain
        # its native selection and keyboard-routing contracts.
        "tests/qualification/prompt_editor/real_shell/autocomplete_surface/test_selection_navigation.py",
        # This real-shell autocomplete whitespace-lifecycle owner aborts after
        # prior native Qt work in a reused worker, while fresh processes retain
        # its native selection and whitespace lifecycle contracts.
        "tests/qualification/prompt_editor/real_shell/autocomplete_surface/test_whitespace_lifecycle.py",
        # This real-shell undo-grouping owner aborts after prior native Qt work
        # in a reused worker, while fresh processes retain its history and
        # projection-invariant contracts.
        "tests/qualification/prompt_editor/real_shell/history/test_undo_grouping.py",
        # This real-shell exact-keyboard-edits owner aborts after prior native
        # Qt work in a reused worker, while fresh processes retain its signed
        # emphasis-step and selected-text replacement contracts.
        "tests/qualification/prompt_editor/real_shell/keyboard_input/test_exact_edits.py",
        # This real-shell row-shift diagnostic owner aborts after prior native
        # Qt work in a reused worker, while fresh processes retain its
        # diagnostic-invariant contract.
        "tests/qualification/prompt_editor/real_shell/projection_diagnostics/test_row_shift.py",
        # This real-shell selection-cache overlay diagnostic owner aborts after
        # prior native Qt work in a reused worker, while fresh processes retain
        # its snapshot-invariant contract.
        "tests/qualification/prompt_editor/real_shell/projection_diagnostics/test_selection_cache_overlays.py",
        # This real-shell layout-metrics diagnostic owner aborts after prior
        # native Qt work in a reused worker, while fresh processes retain its
        # projection-metric invariant contracts.
        "tests/qualification/prompt_editor/real_shell/projection_diagnostics/test_layout_metrics.py",
        # This real-shell autocomplete-ghost diagnostic owner aborts after
        # prior native Qt work in a reused worker, while fresh processes retain
        # its projection-owner invariant contract.
        "tests/qualification/prompt_editor/real_shell/projection_diagnostics/test_autocomplete_ghost_state.py",
        # This real-shell pale-skin space diagnostic owner aborts after prior
        # native Qt work in a reused worker, while fresh processes retain its
        # narrow-layout and visible-row stability contract.
        "tests/qualification/prompt_editor/real_shell/projection_diagnostics/test_pale_skin_space.py",
        # This real-shell observability owner-state contract aborts after prior
        # native Qt work in a reused worker, while fresh processes retain its
        # production tracing-owner behavior.
        "tests/qualification/prompt_editor/real_shell/observability/test_owner_state.py",
        # This real-shell projection-path owner aborts after unrelated native
        # Qt work in a reused worker, while repeated fresh four-worker launches
        # remain stable.
        "tests/qualification/prompt_editor/real_shell/projection_paths/test_incremental_edits.py",
        # This real-shell caret-layout owner aborts after prior native Qt work
        # in a reused worker, while a fresh process retains its navigation and
        # resize projection contract.
        "tests/qualification/prompt_editor/real_shell/projection_paths/test_caret_layout.py",
        # This real-shell transient-editing owner aborts after prior native Qt
        # work in a reused worker, while fresh processes retain its projection
        # and transient-overlay contracts.
        "tests/qualification/prompt_editor/real_shell/projection_paths/test_transient_editing.py",
        # This production abuse-driver owner aborts after prior native Qt work
        # in a reused worker, while fresh processes retain its instrumentation
        # and lifecycle-route proof.
        "tests/qualification/prompt_editor/real_shell/abuse_driver/test_instrumentation.py",
        # This real-shell weight-normalization owner aborts after prior native
        # Qt work in a reused worker, while fresh processes retain its paste,
        # typing, wrapping, and history canonicalization contracts.
        "tests/qualification/prompt_editor/real_shell/canonicalization/test_weight_normalization.py",
        # This region-separator abuse owner aborts after prior native Qt work
        # in an ordinary xdist worker, while repeated fresh-process launches
        # retain its complete cross-surface lifecycle proof.
        "tests/qualification/prompt_editor/real_shell/region_separator_abuse/test_scenarios.py",
        # This real-shell lazy menu-population owner aborts after prior native
        # Qt work in a reused worker, while a fresh process retains its
        # deferred-menu and catalog-cache contract.
        "tests/qualification/prompt_editor/real_shell/lora_trigger_menu/test_lazy_population.py",
        # This real-shell LoRA trigger context-action owner aborts after prior
        # native Qt work in a reused worker, while fresh processes retain its
        # real menu and catalog-state contract.
        "tests/qualification/prompt_editor/real_shell/lora_trigger_menu/test_context_actions.py",
        # This real-shell LoRA trigger lifecycle owner aborts after prior
        # native Qt work in a reused worker, while fresh processes retain its
        # prepared-action and inline-trigger contracts.
        "tests/qualification/prompt_editor/real_shell/lora_trigger_menu/test_lifecycle.py",
        # This real-shell semantic-mode owner aborts after prior native Qt work
        # in a reused worker, while a fresh process retains its scene and
        # diagnostics transition contract.
        "tests/qualification/prompt_editor/real_shell/semantic_modes/test_scene_marker_transition.py",
        # This real-shell scene-editing owner aborts after prior native Qt work
        # in a reused worker, while a fresh process retains its decorated-row
        # editing and metric contracts.
        "tests/qualification/prompt_editor/real_shell/scene_editing/test_marker_editing.py",
        # This real-shell separator-naming owner loses its native inline-editor
        # focus after prior Qt work in a reused worker, while fresh processes
        # retain its source-backed naming and commit contracts.
        "tests/qualification/prompt_editor/real_shell/scene_editing/test_separator_naming.py",
        # This real-shell separator-navigation owner aborts after prior native
        # Qt work in a reused worker, while fresh processes retain its
        # source-order, caret-routing, and visible-caret contracts.
        "tests/qualification/prompt_editor/real_shell/scene_editing/test_separator_navigation.py",
        # This real-shell separator-line-break owner aborts after prior native
        # Qt work in a reused worker, while fresh processes retain its native
        # Return-key projection and separator-chrome contracts.
        "tests/qualification/prompt_editor/real_shell/scene_editing/test_separator_line_breaks.py",
        # This real-shell separator-editing owner aborts after prior native Qt
        # work in a reused worker, while fresh processes retain its rich/raw
        # projection and regional-chrome contracts.
        "tests/qualification/prompt_editor/real_shell/scene_editing/test_separator_editing.py",
        # This real-shell separator-deletion owner aborts after prior native Qt
        # work in a reused worker, while fresh processes retain its immediate
        # deletion-projection and structural-chrome contracts.
        "tests/qualification/prompt_editor/real_shell/scene_editing/test_separator_deletion.py",
        # This real-shell separator-completion owner aborts after prior native
        # Qt work in a reused worker, while fresh processes retain its marker
        # normalization and regional-publication contracts.
        "tests/qualification/prompt_editor/real_shell/scene_editing/test_separator_completion.py",
        # This real-shell replay and abuse-report owner aborts after prior
        # native Qt work in a reused worker, while fresh processes retain its
        # multi-shell replay and reporting contract.
        "tests/qualification/prompt_editor/real_shell/replay_reporting/test_replay_and_report.py",
        # This real-shell regional reorder-preview owner aborts after prior
        # native Qt work in a reused worker, while fresh processes retain its
        # keyboard preview and settled-layout contract.
        "tests/qualification/prompt_editor/real_shell/reorder_preview/test_regional_preview.py",
        # This real-shell keyboard reorder-preview owner aborts after prior
        # native Qt work in a reused worker, while fresh processes retain its
        # held-key preview and animation-chrome contract.
        "tests/qualification/prompt_editor/real_shell/reorder_preview/test_keyboard_preview.py",
        # This real-shell saved-segment menu owner aborts after prior native Qt
        # work in a reused worker, while fresh processes retain its model and
        # preset scope contract.
        "tests/qualification/prompt_editor/real_shell/saved_segment_menu/test_scopes.py",
        # This real-shell selection and autocomplete owner aborts after prior
        # native Qt work in a reused worker, while fresh processes retain its
        # selection, paste, and projection contract.
        "tests/qualification/prompt_editor/real_shell/selection_rendering/test_selection_interactions.py",
        # This real-shell blank-row selection owner aborts after prior native
        # Qt work in a reused worker, while fresh processes retain its
        # select-all, projection-row, and selection-paint contract.
        "tests/qualification/prompt_editor/real_shell/selection_rendering/test_blank_rows.py",
        # This real-shell composition owner aborts after prior native Qt work
        # in a reused worker, while fresh processes retain its production
        # mount, collaborator, and autocomplete-wiring contracts.
        "tests/qualification/prompt_editor/real_shell/shell_composition/test_mount.py",
        # This rendered QFluent visual-parity owner aborts after unrelated
        # native Qt work in a reused worker, while repeated fresh four-worker
        # launches remain stable.
        "tests/qualification/prompt_editor/visual_parity/test_qfluent_shell.py",
        # This prompt-wheel integration owner has the same native fresh-process
        # requirement, while its repeated four-way isolated lane remains stable.
        "tests/presentation/widgets/wheel_intent/test_prompt_weight_wheel_integration.py",
        # This one-test prompt-scroll boundary owner aborts after unrelated Qt
        # work in a reused worker, while repeated fresh four-worker launches
        # remain stable.
        "tests/presentation/widgets/wheel_intent/test_boundary_spill.py",
        # This prompt-scrolling owner aborts after prior native Qt work in a
        # reused worker, while fresh processes retain its widget-local focus
        # and controlled-wheel routing proof.
        "tests/presentation/widgets/wheel_intent/test_prompt_scrolling.py",
        # This numeric-control owner aborts after unrelated native Qt work in
        # a reused worker, while repeated fresh four-worker launches remain
        # stable.
        "tests/presentation/widgets/wheel_intent/test_numeric_controls.py",
        # This numeric-widget integration owner aborts after unrelated native
        # Qt work in a reused worker, while repeated fresh four-worker launches
        # remain stable.
        "tests/presentation/widgets/wheel_intent/test_numeric_integration.py",
        # This spinner-slider wheel-intent owner aborts after prior native Qt
        # work in a reused worker, while fresh processes retain its control and
        # field-state synchronization proof.
        "tests/presentation/widgets/wheel_intent/test_spinner_slider_integration.py",
        # This prompt-scroll integration owner aborts after unrelated native
        # Qt work in a reused worker, while repeated fresh-process launches
        # retain its widget-local controlled-dwell proof.
        "tests/presentation/widgets/wheel_intent/test_prompt_scroll_integration.py",
        # This real prompt-weight manual-control owner aborts after prior native
        # Qt work in a reused worker, while fresh processes retain its hover,
        # click, undo, and scroll-preservation contract.
        "tests/presentation/widgets/wheel_intent/test_prompt_weight_manual_integration.py",
        # This focus-gated prompt-weight wheel owner aborts after prior native
        # Qt work in a reused worker, while repeated fresh-process launches
        # retain its token-local activation and controlled-wheel proof.
        "tests/presentation/widgets/wheel_intent/test_prompt_weights.py",
        # These real prompt-weight owners all require a fresh native process
        # after unrelated Qt work, while repeated four-worker fresh launches
        # preserve their independent visible-control contracts.
        "tests/presentation/editor/prompt_editor/interactions/weight/exact_editing/test_contract.py",
        "tests/presentation/editor/prompt_editor/interactions/weight/step_controls/test_contract.py",
        "tests/presentation/editor/prompt_editor/interactions/weight/transient_neutral/test_contract.py",
        "tests/presentation/editor/prompt_editor/interactions/weight/visibility/test_contract.py",
        "tests/presentation/editor/prompt_editor/interactions/weight/wheel_input/test_contract.py",
        # This Qt event-loop proof also requires a fresh process after prior
        # native Qt work, while its bounded isolated lane is stable.
        "tests/support/qt/test_semantic_wait.py",
        # These real-shell workflow qualifications require a fresh native
        # process after prior Qt work, while concurrent fresh processes retain
        # their independent direct-workflow contracts without shared resources.
        "tests/qualification/comfy/bundled_workflows/direct_workflow_scenarios/test_node_projection.py",
        "tests/qualification/comfy/bundled_workflows/direct_workflow_scenarios/test_overrides_seed.py",
        "tests/qualification/comfy/bundled_workflows/direct_workflow_scenarios/test_prompt_editor_mount.py",
        "tests/qualification/comfy/bundled_workflows/direct_workflow_scenarios/test_transition_layout.py",
        "tests/qualification/comfy/bundled_workflows/direct_workflow_scenarios/test_workspace_restore.py",
        # This thumbnail-worker-lane contract requires a fresh native Qt
        # process after prior work, while concurrent fresh processes are stable.
        "tests/presentation/widgets/media_wall/test_thumbnail_preloader.py",
        # This model-picker popup lifecycle owner has the same native
        # fresh-process requirement, without a shared external resource.
        "tests/presentation/widgets/model_picker/test_popup_lifecycle.py",
        # This model-picker open-surface owner replaces an open native popup
        # after prior Qt work in a reused worker, while fresh processes retain
        # its search click and drag-selection contracts.
        "tests/presentation/widgets/model_picker/test_open_surface_interaction.py",
        # This cube-stack indicator timer contract requires a fresh native Qt
        # process after prior work, while concurrent fresh processes are stable.
        "tests/presentation/workflows/cube_stack/test_scroll_and_indicator.py",
        # These real-shell Output contracts can abort after prior native Qt work
        # in one xdist process, while concurrent fresh processes are stable.
        "tests/presentation/canvas/output/real_shell/test_hierarchy_persistence.py",
        "tests/presentation/canvas/output/real_shell/test_workflow_lifecycle.py",
        # This real-shell decoration-boundary owner requires a fresh native Qt
        # process after prior work, while concurrent fresh processes are stable.
        "tests/qualification/prompt_editor/real_shell/test_decoration_boundaries.py",
        # This wildcard modal-lifecycle owner requires a fresh native Qt process
        # after prior work, while concurrent fresh processes are stable.
        "tests/tools/prompt_editor_abuse/wildcard_mount/test_mount.py",
        # These native Qt owners require fresh non-xdist processes, but repeated
        # four-way overlap proves they do not require global serialization.
        "tests/presentation/editor/prompt_editor/layout/contracts/test_canonical_wrapping.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_incremental_policy.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_incremental_reuse.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_trailing_incremental.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_newline_incremental.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_token_geometry.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_selection_geometry.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_reorder_geometry.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_scene_geometry.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_token_paint.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_separator_navigation.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_region_chrome.py",
        "tests/presentation/editor/prompt_editor/projection/paint_cache/test_cache.py",
        "tests/shared/presentation/localization/test_qfluent_font_adapter.py",
        "tests/presentation/widgets/qfluent_menu_renderer/test_renderer.py",
        # This real mouse-interaction owner is stable in a fresh native Qt
        # process but can lose delivery after unrelated Qt work in one worker.
        "tests/presentation/cube_picker/test_staging_removal.py",
        # This real keyboard interaction is stable in a fresh native Qt process
        # but can lose key delivery after unrelated Qt work in one worker.
        "tests/presentation/cubes/cube_alias_editor/test_editor.py",
        # This real placeholder-card click is stable in a fresh native Qt
        # process but can lose pointer delivery after unrelated Qt work.
        "tests/presentation/cubes/placeholder_card/test_card.py",
    }
)


SERIAL_TEST_MODULES: Final[frozenset[str]] = frozenset(
    {
        # This model-picker module exercises real top-level window activation
        # and native focus transfer. Concurrent Qt worker processes compete
        # for that single operating-system focus owner, while repeated
        # exclusive executions preserve its mouse and keyboard contracts.
        "tests/presentation/widgets/model_picker/test_search_interaction.py",
    }
)


def parallel_test_worker_count(available_workers: int | None) -> int:
    """Bound xdist concurrency to the native Qt suite's stable envelope."""

    if available_workers is None or available_workers < 1:
        return 1
    return min(available_workers, MAX_PARALLEL_TEST_WORKERS)


def isolated_test_worker_count(available_workers: int | None) -> int:
    """Bound concurrent fresh processes to the qualified native Qt envelope."""

    if available_workers is None or available_workers < 1:
        return 1
    return min(available_workers, MAX_ISOLATED_TEST_WORKERS)


def current_test_platform(sys_platform: str = sys.platform) -> CiPlatform:
    """Return the supported test platform represented by ``sys.platform``."""

    if sys_platform == "win32":
        return CiPlatform.WINDOWS
    if sys_platform.startswith("linux"):
        return CiPlatform.LINUX
    if sys_platform == "darwin":
        return CiPlatform.MACOS
    raise ValueError(f"Unsupported test platform: {sys_platform}")


def marker_test_platforms(values: tuple[object, ...]) -> frozenset[CiPlatform]:
    """Validate and return platform names declared by a pytest marker."""

    if not values:
        raise ValueError("The platforms marker requires at least one platform name.")
    try:
        platforms = frozenset(CiPlatform(str(value)) for value in values)
    except ValueError as error:
        supported = ", ".join(platform.value for platform in CiPlatform)
        raise ValueError(
            f"Unsupported platforms marker value; expected one of: {supported}"
        ) from error
    return platforms


def platform_skip_reason(
    *,
    supported: frozenset[CiPlatform],
    current: CiPlatform,
) -> str | None:
    """Return a skip reason when a test does not apply to the current platform."""

    if current in supported:
        return None
    supported_names = ", ".join(sorted(platform.value for platform in supported))
    return (
        f"Test applies only to: {supported_names}; current platform: {current.value}."
    )


__all__ = [
    "ISOLATED_TEST_MODULES",
    "MAX_ISOLATED_TEST_WORKERS",
    "MAX_PARALLEL_TEST_WORKERS",
    "PLATFORM_TEST_MODULES",
    "SERIAL_TEST_MODULES",
    "CiPlatform",
    "current_test_platform",
    "isolated_test_worker_count",
    "marker_test_platforms",
    "parallel_test_worker_count",
    "platform_skip_reason",
]
