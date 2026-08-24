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

"""Compose the narrow owners required by one real-shell prompt scenario."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from functools import partial
from pathlib import Path
from typing import cast

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QWidget

from substitute.app.bootstrap.canvas_execution_runtime import CanvasExecutionRuntime
from substitute.application.danbooru import (
    DanbooruUrlImportService,
    DanbooruWikiContentService,
)
from substitute.application.model_metadata import (
    ModelCatalogLookup,
    ThumbnailAssetRepository,
)
from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardCatalogGateway,
)
from substitute.application.prompt_editor.diagnostics.spellcheck import (
    PromptSpellcheckService,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogLookup,
)
from substitute.application.user_presets import UserPresetService
from substitute.domain.prompt.features.models import PromptEditorFeatureProfile
from substitute.domain.prompt.preferences.models import PromptWheelAdjustmentMode
from substitute.presentation.editor.panel.widgets.scroll_surface import (
    EditorPanelScrollSurface,
)
from tests.support.prompt_editor.autocomplete_support import (
    RecordingPromptAutocompleteGateway,
)
from tests.support.prompt_editor.real_shell.abuse import PromptEditorAbuseCampaign
from tests.support.prompt_editor.real_shell.autocomplete_state import (
    compact_editor_state,
    short_repr,
)
from tests.support.prompt_editor.real_shell.artifacts import PromptEditorArtifactStore
from tests.support.prompt_editor.real_shell.context_menu_probe import (
    PromptContextMenuProbe,
)
from tests.support.prompt_editor.real_shell.input_driver import PromptEditorInputDriver
from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.invariants.transitions import (
    transition_violations,
)
from tests.support.prompt_editor.real_shell.models import (
    PromptEditorObservedEvent,
    PromptEditorTrace,
    PromptEditorTraceAction,
    PromptWorkflowHandle,
)
from tests.support.prompt_editor.real_shell.observability import (
    PromptEditorObservability,
)
from tests.support.prompt_editor.real_shell.projection_probes import (
    PromptProjectionProbes,
)
from tests.support.prompt_editor.real_shell.projection_state import (
    projection_owner_state,
)
from tests.support.prompt_editor.real_shell.session import PromptEditorRealShell
from tests.support.prompt_editor.real_shell.snapshots import (
    PromptEditorSnapshotCapture,
)
from tests.support.prompt_editor.real_shell.trace import PromptEditorTraceReplay
from tests.support.prompt_editor.real_shell.workflows import PromptWorkflowMounts
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import (
    wait_for_qt_condition,
    wait_for_queued_qt_turn,
)


class PromptEditorRealShellScenario:
    """Own the lifecycle and direct collaborators for one mounted prompt scenario.

    The scenario is a composition root only. Snapshotting, invariant evaluation,
    trace replay, and abuse campaigns remain separate owners so consumers depend
    on the smallest contract that proves their behavior.
    """

    def __init__(
        self,
        *,
        autocomplete_results: (
            Mapping[str, tuple[PromptAutocompleteSuggestion, ...]] | None
        ) = None,
        prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway | None = None,
        prompt_lora_catalog_service: PromptLoraCatalogLookup | None = None,
        prompt_spellcheck_service: PromptSpellcheckService | None = None,
        danbooru_url_import_service: DanbooruUrlImportService | None = None,
        danbooru_wiki_service: DanbooruWikiContentService | None = None,
        prompt_feature_profile: PromptEditorFeatureProfile | None = None,
        wheel_adjustment_mode: PromptWheelAdjustmentMode = (
            PromptWheelAdjustmentMode.HOVER_DWELL
        ),
        thumbnail_asset_repository: ThumbnailAssetRepository | None = None,
        user_preset_service: UserPresetService | None = None,
        model_catalog_service: ModelCatalogLookup | None = None,
        artifact_root: Path,
        observe_owner_calls: bool = True,
    ) -> None:
        """Mount the production shell beneath the caller-owned artifact root."""

        self.app = ensure_qapplication()
        self.artifact_root = artifact_root
        self.canvas_execution_runtime_owner = CanvasExecutionRuntime()
        self.autocomplete_results = (
            autocomplete_results or default_autocomplete_results()
        )
        self.autocomplete_gateway = RecordingPromptAutocompleteGateway(
            self.autocomplete_results
        )
        self.shell = PromptEditorRealShell(
            self.autocomplete_gateway,
            canvas_execution_runtime=self.canvas_execution_runtime_owner.runtime,
            prompt_wildcard_catalog_gateway=prompt_wildcard_catalog_gateway,
            prompt_lora_catalog_service=prompt_lora_catalog_service,
            prompt_spellcheck_service=prompt_spellcheck_service,
            danbooru_url_import_service=danbooru_url_import_service,
            danbooru_wiki_service=danbooru_wiki_service,
            prompt_feature_profile=prompt_feature_profile,
            wheel_adjustment_mode=wheel_adjustment_mode,
            thumbnail_asset_repository=thumbnail_asset_repository,
            user_preset_service=user_preset_service,
            model_catalog_service=model_catalog_service,
        )
        self.workflow_handles: dict[str, PromptWorkflowHandle] = {}
        self.trace_actions: list[PromptEditorTraceAction] = []
        self.observed_events: list[PromptEditorObservedEvent] = []
        self.snapshots = PromptEditorSnapshotCapture(
            shell=self.shell,
            autocomplete_gateway=self.autocomplete_gateway,
            observed_events=self.observed_events,
            projection_state_reader=projection_owner_state,
        )
        self.observability = PromptEditorObservability(
            enabled=observe_owner_calls,
            observed_events=self.observed_events,
            compact_state=compact_editor_state,
            result_formatter=short_repr,
        )
        self.input = PromptEditorInputDriver(
            shell=self.shell,
            shell_activator=self.shell.activate_for_input,
            click_away_target_provider=self._click_away_target,
            canvas_provider=lambda label: cast(
                QWidget | None, self.shell.canvas_host.canvas_for(label)
            ),
            canvas_activator=lambda label: self.shell.canvas_host.activate_canvas(
                label, keyboard_focus=False
            ),
            trace_actions=self.trace_actions,
            snapshot_capture=self.snapshots.capture,
        )
        self.context_menus = PromptContextMenuProbe(self.trace_actions)
        self.workflows = PromptWorkflowMounts(
            shell=self.shell,
            handles=self.workflow_handles,
            wait_until=self.wait_until,
            observability=self.observability,
            trace_actions=self.trace_actions,
        )
        self.trace_replay = PromptEditorTraceReplay(
            actions=self.trace_actions,
            input_driver=self.input,
            workflow_handles=self.workflow_handles,
            workflows=self.workflows,
        )
        self.artifacts = PromptEditorArtifactStore(
            self.artifact_root,
            active_workflow_id_provider=(
                lambda: self.shell.workflow_session_service.active_workflow_id
            ),
            trace_provider=self.trace_replay.trace,
            autocomplete_results=self.autocomplete_results,
        )
        self.projection_probes = PromptProjectionProbes(
            input_driver=self.input,
            trace_actions=self.trace_actions,
        )
        self.abuse_campaign = PromptEditorAbuseCampaign(
            shell=self.shell,
            artifact_root=self.artifact_root,
            artifacts=self.artifacts,
            input_driver=self.input,
            workflows=self.workflows,
            snapshot_capture=self.snapshots.capture,
            transition_invariants=partial(
                transition_violations,
                snapshot_violations=snapshot_invariant_violations,
            ),
        )
        self._closed = False

    def _click_away_target(self) -> QWidget:
        """Return the active production panel scroll focus owner."""

        panel = self.shell.active_editor_panel
        if panel is None:
            raise RuntimeError("Click-away input requires an active editor panel.")
        return cast(EditorPanelScrollSurface, panel.scroll)

    def close(self) -> None:
        """Stop canvas work before synchronously destroying the mounted shell."""

        if self._closed:
            return
        self._closed = True
        self.canvas_execution_runtime_owner.shutdown(wait=True)
        self.shell.close()
        wait_for_queued_qt_turn()
        destroy_qt_object(self.shell)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        wait_for_queued_qt_turn()

    def trace(self) -> PromptEditorTrace:
        """Return the deterministic user actions recorded by direct collaborators."""

        return self.trace_replay.trace()

    def wait_until(
        self,
        predicate: Callable[[], bool],
        *,
        timeout_ms: int = 3000,
        description: str = "real-shell state",
        state: Callable[[], object] | None = None,
    ) -> None:
        """Wait for one observable shell state through the semantic Qt boundary."""

        wait_for_qt_condition(
            predicate,
            timeout_ms=timeout_ms,
            description=description,
            state=state,
        )

    def wait_for_queued_delivery(self) -> None:
        """Deliver callbacks queued by the preceding real-shell operation."""

        wait_for_queued_qt_turn()


def default_autocomplete_results() -> Mapping[
    str,
    tuple[PromptAutocompleteSuggestion, ...],
]:
    """Return deterministic autocomplete data for prompt-editor scenarios."""

    return {
        "re": (
            PromptAutocompleteSuggestion(
                "re:zero kara hajimeru isekai seikatsu", 16370
            ),
            PromptAutocompleteSuggestion("re:stage!", 1501),
            PromptAutocompleteSuggestion("re:creators", 728),
        ),
        "1g": (
            PromptAutocompleteSuggestion("1girl", 5_889_398),
            PromptAutocompleteSuggestion("1girls", 3424),
        ),
        "ha": (
            PromptAutocompleteSuggestion("hair ornament", 4100),
            PromptAutocompleteSuggestion("hair ribbon", 3800),
        ),
        "backpack": (
            PromptAutocompleteSuggestion("backpack basket", 240),
            PromptAutocompleteSuggestion("backpack strap", 120),
        ),
        "backpack ": (PromptAutocompleteSuggestion("backpack basket", 240),),
    }


def ensure_qapplication() -> QApplication:
    """Return the active QApplication or create one for a real-shell scenario."""

    application = QCoreApplication.instance()
    if isinstance(application, QApplication):
        return application
    return QApplication([])
