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

"""Coordinate saved prompt-segment menu state, saving, and insertion."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import app_text

import logging
from collections.abc import Hashable

from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandResult,
    PromptFeatureSnapshotIdentity,
)
from substitute.presentation.editor.prompt_editor.features.catalog_snapshots import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)
from substitute.presentation.editor.prompt_editor.features.feature_profile_controller import (
    PromptFeatureProfileController,
)
from substitute.presentation.editor.prompt_editor.features.prompt_segment_preset_models import (
    PromptSegmentPresetDialogRunner,
    PromptSegmentPresetMenuModel,
    PromptSegmentPresetSaveDialogRequest,
    PromptSegmentPresetSaveState,
    PromptSegmentPresetSnapshot,
    PromptSegmentPresetSource,
)
from substitute.presentation.editor.prompt_editor.features.prompt_segment_selection import (
    PromptSegmentPresetHost,
    PromptSegmentSelectionSnapshot,
    PromptSegmentTextInsertionExecutor,
)

LOGGER = logging.getLogger(__name__)


class PromptSegmentPresetController:
    """Coordinate prompt segment preset menu data, save flow, and insertion."""

    def __init__(
        self,
        *,
        host: PromptSegmentPresetHost,
        text_insertion_executor: PromptSegmentTextInsertionExecutor,
        feature_profile: PromptFeatureProfileController,
        preset_source: PromptSegmentPresetSource | None,
    ) -> None:
        """Store prompt segment collaborators and publish an initial snapshot."""

        self._host = host
        self._text_insertion_executor = text_insertion_executor
        self._feature_profile = feature_profile
        self._preset_source = preset_source
        self._snapshot = self._build_snapshot(
            menu_model=None,
            selected_text="",
            selection_range=None,
            read_only=False,
            insert_ready=False,
            status=self._base_status(),
        )
        self._prepared_menu_snapshots: dict[
            tuple[object, ...],
            PromptSegmentPresetSnapshot,
        ] = {}

    @property
    def snapshot(self) -> PromptSegmentPresetSnapshot:
        """Return the last prepared prompt segment preset snapshot."""

        return self._snapshot

    def menu_model(self) -> PromptSegmentPresetMenuModel | None:
        """Refresh and return saved prompt segment menu data outside menu open."""

        return self.refresh_menu_model(reason="menu_model")

    def refresh_menu_model(self, *, reason: str) -> PromptSegmentPresetMenuModel | None:
        """Refresh saved segment menu data at an explicit non-hot-path boundary."""

        if self._preset_source is None:
            self._snapshot = self._build_snapshot(
                menu_model=None,
                selected_text="",
                selection_range=None,
                read_only=False,
                insert_ready=False,
                unavailable_reason="preset_source_unavailable",
                status=CatalogSnapshotStatus(
                    CatalogSnapshotReadiness.DISABLED,
                    unavailable_reason="preset_source_unavailable",
                ),
            )
            self._prepared_menu_snapshots.clear()
            return None
        try:
            source_snapshot = self._preset_source.list_prompt_segment_presets()
        except (RuntimeError, TypeError, ValueError):
            LOGGER.warning(
                "Prompt segment preset refresh failed.",
                extra={"reason": reason},
                exc_info=True,
            )
            status = (
                CatalogSnapshotStatus(
                    CatalogSnapshotReadiness.STALE,
                    unavailable_reason="refresh_failed",
                )
                if self._snapshot.menu_model is not None
                else CatalogSnapshotStatus(
                    CatalogSnapshotReadiness.REFRESH_FAILED,
                    unavailable_reason="refresh_failed",
                )
            )
            self._snapshot = self._build_snapshot(
                menu_model=self._snapshot.menu_model,
                selected_text=self.selected_prompt_text(),
                selection_range=self._current_selection_range(),
                read_only=False,
                insert_ready=self._snapshot.menu_model is not None,
                unavailable_reason="refresh_failed",
                status=status,
            )
            self._prepared_menu_snapshots.clear()
            return self._snapshot.menu_model
        model = source_snapshot.menu_model
        self._snapshot = self._build_snapshot(
            menu_model=model,
            selected_text=self.selected_prompt_text(),
            selection_range=self._current_selection_range(),
            read_only=False,
            insert_ready=True,
            catalog_identity=source_snapshot.catalog_identity,
            status=source_snapshot.status,
            unavailable_reason=source_snapshot.catalog_identity.unavailable_reason,
        )
        self._prepared_menu_snapshots.clear()
        return model

    def prepare_menu_snapshot_for_selection(
        self,
        *,
        selected_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
        reason: str,
    ) -> PromptSegmentPresetSnapshot:
        """Prepare context-menu segment state for one captured selection."""

        _ = reason
        snapshot = self._build_snapshot(
            menu_model=self._snapshot.menu_model,
            selected_text=selected_text,
            selection_range=selection_range,
            read_only=read_only,
            insert_ready=(
                self._preset_source is not None
                and self._snapshot.menu_model is not None
                and not read_only
            ),
            catalog_identity=self._snapshot.catalog_identity,
            status=self._snapshot.status,
            unavailable_reason=self._snapshot.unavailable_reason,
        )
        self._prepared_menu_snapshots[
            self._menu_selection_key(
                selected_text=selected_text,
                selection_range=selection_range,
                read_only=read_only,
            )
        ] = snapshot
        self._snapshot = snapshot
        return snapshot

    def prepared_menu_snapshot_for_selection(
        self,
        *,
        selected_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
    ) -> PromptSegmentPresetSnapshot:
        """Return prepared selected-text segment state without deriving it."""

        key = self._menu_selection_key(
            selected_text=selected_text,
            selection_range=selection_range,
            read_only=read_only,
        )
        snapshot = self._prepared_menu_snapshots.get(key)
        if snapshot is not None:
            return snapshot
        return self._unavailable_menu_snapshot(
            selected_text=selected_text,
            selection_range=selection_range,
            read_only=read_only,
            unavailable_reason="segment_menu_snapshot_unprepared",
        )

    def selected_prompt_text(self) -> str:
        """Return the exact currently selected source text."""

        selection_snapshot = self.selected_prompt_range_and_text()
        if selection_snapshot is None:
            return ""
        return selection_snapshot.text

    def selected_prompt_range_and_text(
        self,
    ) -> PromptSegmentSelectionSnapshot | None:
        """Return the exact current selected source range and text."""

        cursor = self._host.textCursor()
        if not cursor.hasSelection():
            return None
        start = min(int(cursor.selectionStart()), int(cursor.selectionEnd()))
        end = max(int(cursor.selectionStart()), int(cursor.selectionEnd()))
        return PromptSegmentSelectionSnapshot(
            start=start,
            end=end,
            text=self._host.toPlainText()[start:end],
        )

    def restore_selection_snapshot(
        self,
        selection_snapshot: PromptSegmentSelectionSnapshot,
    ) -> None:
        """Restore a source selection captured before a context-menu side effect."""

        self._host.restore_prompt_segment_selection(
            start=selection_snapshot.start,
            end=selection_snapshot.end,
        )

    def save_selected_segment_as_preset(
        self,
        selected_text: str | None = None,
        *,
        dialog_runner: PromptSegmentPresetDialogRunner,
    ) -> bool:
        """Run the save-segment flow and persist the accepted preset."""

        if self._preset_source is None:
            self._snapshot = self._build_snapshot(
                menu_model=None,
                selected_text="",
                selection_range=None,
                read_only=False,
                insert_ready=False,
                unavailable_reason="preset_source_unavailable",
                status=CatalogSnapshotStatus(
                    CatalogSnapshotReadiness.DISABLED,
                    unavailable_reason="preset_source_unavailable",
                ),
            )
            return False
        if selected_text is None:
            selected_text = self.selected_prompt_text()
        if not selected_text.strip():
            self._snapshot = self._build_snapshot(
                menu_model=self._snapshot.menu_model,
                selected_text=selected_text,
                selection_range=self._current_selection_range(),
                read_only=False,
                insert_ready=True,
                unavailable_reason="empty_selection",
                catalog_identity=self._snapshot.catalog_identity,
                status=self._snapshot.status,
            )
            return False
        scopes = self._snapshot.save_state.save_scopes
        if not scopes:
            self._snapshot = self._build_snapshot(
                menu_model=self._snapshot.menu_model,
                selected_text=selected_text,
                selection_range=self._current_selection_range(),
                read_only=False,
                insert_ready=True,
                unavailable_reason="save_scopes_unavailable",
                catalog_identity=self._snapshot.catalog_identity,
                status=CatalogSnapshotStatus(
                    CatalogSnapshotReadiness.UNAVAILABLE,
                    unavailable_reason="save_scopes_unavailable",
                ),
            )
            return False
        request = PromptSegmentPresetSaveDialogRequest(
            parent=self._host.prompt_segment_dialog_parent(),
            title=app_text("Save segment"),
            scopes=scopes,
            selected_text=selected_text,
        )
        result = dialog_runner(request)
        if result is None:
            return False
        label, scope = result
        self._preset_source.save_prompt_segment(
            label=label,
            text=selected_text,
            scope=scope,
        )
        menu_model = self.refresh_menu_model(reason="prompt_segment_saved")
        self._snapshot = self._build_snapshot(
            menu_model=menu_model,
            selected_text=selected_text,
            selection_range=self._current_selection_range(),
            read_only=False,
            insert_ready=True,
            catalog_identity=self._snapshot.catalog_identity,
            status=self._snapshot.status,
            unavailable_reason=self._snapshot.unavailable_reason,
        )
        return True

    def insert_saved_prompt_segment(
        self,
        insertion_text: str,
    ) -> PromptCommandResult[object]:
        """Insert a saved prompt segment at the active menu target."""

        result = self._text_insertion_executor.insert_context_menu_text(
            insertion_text,
            command_name="context_menu_insert_text",
        )
        self._snapshot = self._build_snapshot(
            menu_model=self._snapshot.menu_model,
            selected_text=self.selected_prompt_text(),
            selection_range=self._current_selection_range(),
            read_only=False,
            insert_ready=True,
            catalog_identity=self._snapshot.catalog_identity,
            status=self._snapshot.status,
            unavailable_reason=self._snapshot.unavailable_reason,
        )
        return result

    def _build_snapshot(
        self,
        *,
        menu_model: PromptSegmentPresetMenuModel | None,
        selected_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
        insert_ready: bool,
        unavailable_reason: str | None = None,
        catalog_identity: CatalogSnapshotIdentity | None = None,
        status: CatalogSnapshotStatus | None = None,
        save_allowed: bool = True,
    ) -> PromptSegmentPresetSnapshot:
        """Build the prompt segment preset snapshot for current host state."""

        source_identity = self._host.prompt_command_source_identity()
        raw_source_revision = getattr(source_identity, "source_revision", None)
        source_revision = (
            raw_source_revision if isinstance(raw_source_revision, int) else None
        )
        prepared_status = status if status is not None else self._base_status()
        source_available = self._preset_source is not None
        save_ready = (
            save_allowed
            and source_available
            and not read_only
            and bool(selected_text.strip())
        )
        disabled_reason = None
        if not source_available:
            disabled_reason = "preset_source_unavailable"
        elif read_only:
            disabled_reason = "read_only"
        elif not selected_text.strip():
            disabled_reason = "empty_selection"
        selection_identity = _selected_text_identity(selected_text)
        prepared_catalog_identity = self._catalog_identity(
            source_revision=source_revision,
            catalog_identity=catalog_identity,
            status=prepared_status,
            selection_identity=selection_identity,
            selection_range=selection_range,
            read_only=read_only,
        )
        save_scopes = menu_model.save_scopes if menu_model is not None else ()
        if save_ready and not save_scopes:
            disabled_reason = "save_scopes_unavailable"
        return PromptSegmentPresetSnapshot(
            identity=PromptFeatureSnapshotIdentity(
                source_revision=source_revision,
                feature_profile_id=self._feature_profile.identity.feature_profile_id,
                query_identity=(
                    "prompt_segment_menu_selection",
                    selection_identity,
                    selection_range,
                    read_only,
                ),
            ),
            catalog_identity=prepared_catalog_identity,
            status=prepared_status,
            menu_model=menu_model,
            save_state=PromptSegmentPresetSaveState(
                source_available=source_available,
                selected_text=selected_text,
                ready=save_ready and bool(save_scopes),
                disabled_reason=disabled_reason,
                save_scopes=save_scopes,
            ),
            insert_ready=insert_ready and not read_only,
            selected_text_identity=selection_identity,
            selection_range=selection_range,
            read_only=read_only,
            unavailable_reason=unavailable_reason,
        )

    def _base_status(self) -> CatalogSnapshotStatus:
        """Return the catalog snapshot status implied by source availability."""

        if self._preset_source is None:
            return CatalogSnapshotStatus(
                CatalogSnapshotReadiness.DISABLED,
                unavailable_reason="preset_source_unavailable",
            )
        return CatalogSnapshotStatus(CatalogSnapshotReadiness.COLD)

    def _catalog_identity(
        self,
        *,
        source_revision: int | None,
        catalog_identity: CatalogSnapshotIdentity | None,
        status: CatalogSnapshotStatus,
        selection_identity: Hashable | None = None,
        selection_range: tuple[int, int] | None = None,
        read_only: bool = False,
    ) -> CatalogSnapshotIdentity:
        """Return segment preset catalog identity for the current publication."""

        identity = catalog_identity or CatalogSnapshotIdentity()
        return CatalogSnapshotIdentity(
            source_revision=source_revision,
            editor_context_id=identity.editor_context_id,
            panel_context_id=identity.panel_context_id,
            feature_profile_id=self._feature_profile.identity.feature_profile_id,
            catalog_revision=identity.catalog_revision,
            prompt_context_token=identity.prompt_context_token,
            cube_context_token=identity.cube_context_token,
            scene_context_token=identity.scene_context_token,
            query_identity=(
                identity.query_identity,
                selection_identity,
                selection_range,
                read_only,
            ),
            request_identity=identity.request_identity,
            stale=status.readiness is CatalogSnapshotReadiness.STALE,
            unavailable_reason=status.unavailable_reason or identity.unavailable_reason,
        )

    def _menu_selection_key(
        self,
        *,
        selected_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
    ) -> tuple[object, ...]:
        """Return the cache key for one prepared context-menu selection."""

        source_identity = self._host.prompt_command_source_identity()
        raw_source_revision = getattr(source_identity, "source_revision", None)
        source_revision = (
            raw_source_revision if isinstance(raw_source_revision, int) else None
        )
        return (
            source_revision,
            self._feature_profile.identity.feature_profile_id,
            self._snapshot.catalog_identity.editor_context_id,
            self._snapshot.catalog_identity.panel_context_id,
            self._snapshot.catalog_identity.feature_profile_id,
            self._snapshot.catalog_identity.catalog_revision,
            self._snapshot.catalog_identity.prompt_context_token,
            self._snapshot.catalog_identity.cube_context_token,
            self._snapshot.catalog_identity.scene_context_token,
            self._snapshot.status.readiness,
            self._snapshot.status.unavailable_reason,
            _selected_text_identity(selected_text),
            selection_range,
            read_only,
        )

    def _unavailable_menu_snapshot(
        self,
        *,
        selected_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
        unavailable_reason: str,
    ) -> PromptSegmentPresetSnapshot:
        """Return a stale-safe unavailable selected-text menu snapshot."""

        return self._build_snapshot(
            menu_model=self._snapshot.menu_model,
            selected_text=selected_text,
            selection_range=selection_range,
            read_only=read_only,
            insert_ready=False,
            unavailable_reason=unavailable_reason,
            catalog_identity=self._snapshot.catalog_identity.with_stale_state(
                stale=True,
                unavailable_reason=unavailable_reason,
            ),
            status=CatalogSnapshotStatus(
                CatalogSnapshotReadiness.UNAVAILABLE,
                unavailable_reason=unavailable_reason,
            ),
            save_allowed=False,
        )

    def _current_selection_range(self) -> tuple[int, int] | None:
        """Return the current host selection range when one exists."""

        selection = self.selected_prompt_range_and_text()
        if selection is None:
            return None
        return (selection.start, selection.end)


def _selected_text_identity(selected_text: str) -> tuple[str, int, int]:
    """Return a prompt-safe identity for selected prompt text."""

    return ("selected_text", len(selected_text), hash(selected_text))


__all__ = ["PromptSegmentPresetController"]
