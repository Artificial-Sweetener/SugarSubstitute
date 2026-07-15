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

"""Tests for prompt segment preset feature controller ownership."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.domain.user_presets import GLOBAL_PRESET_ASSOCIATION
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandResult,
    PromptCommandSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.features import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
    PromptFeatureProfileController,
    PromptSegmentPresetController,
    PromptSegmentPresetMenuModel,
    PromptSegmentPresetSaveDialogRequest,
    PromptSegmentPresetSourceSnapshot,
    PromptSegmentSelectionSnapshot,
    prompt_feature_profile_from_legacy_syntax,
)
from substitute.presentation.widgets.save_preset_dialog import PresetSaveScope


@dataclass(slots=True)
class _Cursor:
    """Provide the cursor reads needed by the segment preset controller."""

    selection_start: int
    selection_end: int
    cursor_position: int

    def hasSelection(self) -> bool:  # noqa: N802
        """Return whether the fake cursor has a selected range."""

        return self.selection_start != self.selection_end

    def selectionStart(self) -> int:  # noqa: N802
        """Return the fake selection start endpoint."""

        return self.selection_start

    def selectionEnd(self) -> int:  # noqa: N802
        """Return the fake selection end endpoint."""

        return self.selection_end

    def position(self) -> int:
        """Return the fake cursor position."""

        return self.cursor_position


class _Host:
    """Capture host calls made by the segment preset controller."""

    def __init__(
        self,
        *,
        text: str = "alpha beta gamma",
        cursor: _Cursor | None = None,
    ) -> None:
        """Store fake prompt state and command observations."""

        self.text = text
        self.cursor = cursor or _Cursor(0, 0, 0)
        self.parent = object()
        self.restored_selections: list[tuple[int, int]] = []
        self.source_revision = 7

    def textCursor(self) -> _Cursor:  # noqa: N802
        """Return the fake cursor."""

        return self.cursor

    def toPlainText(self) -> str:  # noqa: N802
        """Return the fake prompt source."""

        return self.text

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity:
        """Return a stable fake source identity."""

        return PromptCommandSourceIdentity(
            source_revision=self.source_revision,
            source_length=len(self.text),
        )

    def prompt_segment_dialog_parent(self) -> object:
        """Return the fake dialog parent."""

        return self.parent

    def restore_prompt_segment_selection(self, *, start: int, end: int) -> None:
        """Record restored source selection bounds."""

        self.restored_selections.append((start, end))


class _Source:
    """Provide preset source behavior for controller tests."""

    def __init__(self, *, scopes: tuple[PresetSaveScope, ...] | None = None) -> None:
        """Store fake scopes and saved prompt segments."""

        self.model = PromptSegmentPresetMenuModel(
            save_scopes=scopes if scopes is not None else (_scope(),)
        )
        self.scopes = scopes if scopes is not None else (_scope(),)
        self.saved: list[tuple[str, str, PresetSaveScope]] = []
        self.list_calls = 0
        self.fail_list = False
        self.status = CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM)

    def list_prompt_segment_presets(self) -> PromptSegmentPresetSourceSnapshot:
        """Return the fake menu model."""

        self.list_calls += 1
        if self.fail_list:
            raise RuntimeError("preset source unavailable")
        return PromptSegmentPresetSourceSnapshot(
            menu_model=self.model,
            catalog_identity=CatalogSnapshotIdentity(
                catalog_revision=self.list_calls,
                prompt_context_token=("checkpoint", "test"),
            ),
            status=self.status,
        )

    def save_prompt_segment(
        self,
        *,
        label: str,
        text: str,
        scope: PresetSaveScope,
    ) -> None:
        """Record one saved prompt segment."""

        self.saved.append((label, text, scope))


class _TextInsertionExecutor:
    """Capture saved segment insertion requests routed through the adapter seam."""

    def __init__(self) -> None:
        """Prepare empty insertion observations."""

        self.inserted_texts: list[str] = []
        self.command_names: list[str] = []

    def insert_context_menu_text(
        self,
        insertion_text: str,
        *,
        command_name: str = "context_menu_insert_text",
    ) -> PromptCommandResult[object]:
        """Record one context-menu insertion request."""

        self.inserted_texts.append(insertion_text)
        self.command_names.append(command_name)
        return PromptCommandResult.completed(command_name)


def test_controller_captures_exact_selection_snapshot() -> None:
    """Selection snapshots should preserve exact source ranges and text."""

    host = _Host(cursor=_Cursor(6, 10, 10))
    controller = _controller(host=host)

    snapshot = controller.selected_prompt_range_and_text()

    assert snapshot is not None
    assert snapshot == PromptSegmentSelectionSnapshot(start=6, end=10, text="beta")
    controller.restore_selection_snapshot(snapshot)
    assert host.restored_selections == [(6, 10)]


def test_controller_saves_selected_segment_through_dialog_request() -> None:
    """Save flow should request a dialog and persist the accepted segment."""

    host = _Host(cursor=_Cursor(0, 5, 5))
    source = _Source()
    controller = _controller(host=host, source=source)
    requests: list[PromptSegmentPresetSaveDialogRequest] = []
    controller.refresh_menu_model(reason="test")

    def run_dialog(
        request: PromptSegmentPresetSaveDialogRequest,
    ) -> tuple[str, PresetSaveScope]:
        """Capture the prepared save dialog request."""

        requests.append(request)
        return ("Opening", request.scopes[0])

    assert controller.save_selected_segment_as_preset(dialog_runner=run_dialog)
    assert source.saved == [("Opening", "alpha", source.scopes[0])]
    assert source.list_calls == 2
    assert requests == [
        PromptSegmentPresetSaveDialogRequest(
            parent=host.parent,
            title="Save segment",
            scopes=source.scopes,
            selected_text="alpha",
        )
    ]


def test_controller_does_not_prompt_without_source_or_selected_text() -> None:
    """Save flow should fail closed when no source or selected text is available."""

    host = _Host(cursor=_Cursor(0, 0, 0))
    source = _Source()
    called = False

    def run_dialog(
        _request: PromptSegmentPresetSaveDialogRequest,
    ) -> tuple[str, PresetSaveScope]:
        """Fail the test if the controller requests a dialog."""

        nonlocal called
        called = True
        return ("Unused", _scope())

    assert not _controller(
        host=host,
        source_available=False,
    ).save_selected_segment_as_preset(dialog_runner=run_dialog)
    assert not _controller(host=host, source=source).save_selected_segment_as_preset(
        dialog_runner=run_dialog
    )
    assert called is False
    assert source.saved == []


def test_controller_inserts_saved_segment_through_text_insertion_executor() -> None:
    """Saved segment insertion should route through the adapter-owned seam."""

    host = _Host(cursor=_Cursor(0, 0, 3))
    insertion_executor = _TextInsertionExecutor()
    controller = _controller(host=host, insertion_executor=insertion_executor)

    result = controller.insert_saved_prompt_segment("delta")

    assert result.status == "completed"
    assert insertion_executor.inserted_texts == ["delta"]
    assert insertion_executor.command_names == ["context_menu_insert_text"]


def test_controller_prepared_menu_snapshot_uses_cached_model_without_source_lookup() -> (
    None
):
    """Prepared context-menu snapshots should not list presets from the source."""

    source = _Source()
    controller = _controller(host=_Host(cursor=_Cursor(0, 5, 5)), source=source)

    assert controller.refresh_menu_model(reason="test") is source.model
    assert source.list_calls == 1

    controller.prepare_menu_snapshot_for_selection(
        selected_text="alpha",
        selection_range=(0, 5),
        read_only=False,
        reason="test",
    )
    snapshot = controller.prepared_menu_snapshot_for_selection(
        selected_text="alpha",
        selection_range=(0, 5),
        read_only=False,
    )

    assert snapshot.menu_model is source.model
    assert snapshot.insert_ready is True
    assert snapshot.status.readiness is CatalogSnapshotReadiness.WARM
    assert snapshot.save_state.save_scopes == source.scopes
    assert source.list_calls == 1


def test_controller_allows_global_save_when_model_catalog_is_unavailable() -> None:
    """Global saving should not depend on model-specific catalog readiness."""

    source = _Source(scopes=(_scope(),))
    source.status = CatalogSnapshotStatus(
        CatalogSnapshotReadiness.UNAVAILABLE,
        unavailable_reason="active_model_unavailable",
    )
    controller = _controller(host=_Host(cursor=_Cursor(0, 5, 5)), source=source)
    controller.refresh_menu_model(reason="test")

    snapshot = controller.prepare_menu_snapshot_for_selection(
        selected_text="alpha",
        selection_range=(0, 5),
        read_only=False,
        reason="test",
    )

    assert snapshot.status.readiness is CatalogSnapshotReadiness.UNAVAILABLE
    assert snapshot.save_state.ready
    assert [scope.title for scope in snapshot.save_state.save_scopes] == ["Global"]


def test_controller_prepared_menu_snapshot_reports_unprepared_selection() -> None:
    """Menu reads without matching preparation should fail closed."""

    source = _Source()
    controller = _controller(host=_Host(cursor=_Cursor(0, 5, 5)), source=source)
    controller.refresh_menu_model(reason="test")

    snapshot = controller.prepared_menu_snapshot_for_selection(
        selected_text="alpha",
        selection_range=(0, 5),
        read_only=False,
    )

    assert snapshot.menu_model is source.model
    assert snapshot.insert_ready is False
    assert snapshot.save_state.ready is False
    assert snapshot.status.readiness is CatalogSnapshotReadiness.UNAVAILABLE
    assert snapshot.unavailable_reason == "segment_menu_snapshot_unprepared"
    assert source.list_calls == 1


def test_controller_prepared_menu_snapshot_read_only_disables_mutations() -> None:
    """Read-only prepared state should suppress save and insert callbacks."""

    source = _Source()
    controller = _controller(host=_Host(cursor=_Cursor(0, 5, 5)), source=source)
    controller.refresh_menu_model(reason="test")

    snapshot = controller.prepare_menu_snapshot_for_selection(
        selected_text="alpha",
        selection_range=(0, 5),
        read_only=True,
        reason="read_only_test",
    )

    assert snapshot.menu_model is source.model
    assert snapshot.insert_ready is False
    assert snapshot.save_state.ready is False
    assert snapshot.save_state.disabled_reason == "read_only"
    assert snapshot.read_only is True
    assert source.list_calls == 1


def test_controller_snapshot_records_unavailable_preset_source() -> None:
    """Missing preset source should produce a cheap unavailable snapshot."""

    controller = _controller(host=_Host(), source_available=False)

    assert controller.menu_model() is None

    assert controller.snapshot.menu_model is None
    assert controller.snapshot.insert_ready is False
    assert controller.snapshot.status.readiness is CatalogSnapshotReadiness.DISABLED
    assert controller.snapshot.unavailable_reason == "preset_source_unavailable"
    assert controller.snapshot.save_state.disabled_reason == "preset_source_unavailable"


def test_controller_refresh_failure_records_failed_snapshot() -> None:
    """Explicit refresh failures should publish an unavailable snapshot state."""

    source = _Source()
    source.fail_list = True
    controller = _controller(host=_Host(), source=source)

    assert controller.refresh_menu_model(reason="phase23") is None
    assert source.list_calls == 1
    assert (
        controller.snapshot.status.readiness is CatalogSnapshotReadiness.REFRESH_FAILED
    )
    assert controller.snapshot.unavailable_reason == "refresh_failed"


def test_controller_refresh_failure_preserves_stale_prepared_model() -> None:
    """Explicit refresh failures should keep prior prepared menu data consumable."""

    source = _Source()
    controller = _controller(host=_Host(cursor=_Cursor(0, 5, 5)), source=source)
    assert controller.refresh_menu_model(reason="warm") is source.model

    source.fail_list = True

    assert controller.refresh_menu_model(reason="phase23") is source.model
    assert source.list_calls == 2
    assert controller.snapshot.status.readiness is CatalogSnapshotReadiness.STALE
    assert controller.snapshot.menu_model is source.model


def test_controller_save_uses_prepared_scopes_without_source_scope_lookup() -> None:
    """Save flow should use scopes from the prepared snapshot only."""

    source = _Source()
    controller = _controller(host=_Host(cursor=_Cursor(0, 5, 5)), source=source)
    controller.refresh_menu_model(reason="warm")
    requests: list[PromptSegmentPresetSaveDialogRequest] = []

    def run_dialog(
        request: PromptSegmentPresetSaveDialogRequest,
    ) -> tuple[str, PresetSaveScope]:
        """Capture the prepared save dialog request."""

        requests.append(request)
        return ("Opening", request.scopes[0])

    assert controller.save_selected_segment_as_preset(dialog_runner=run_dialog)

    assert requests[0].scopes == source.model.save_scopes
    assert source.list_calls == 2


def test_controller_blocks_save_when_prepared_scopes_unavailable() -> None:
    """Save flow should not refresh hidden scope data when scopes are cold."""

    source = _Source(scopes=())
    controller = _controller(host=_Host(cursor=_Cursor(0, 5, 5)), source=source)
    controller.refresh_menu_model(reason="warm_without_scopes")
    called = False

    def run_dialog(
        _request: PromptSegmentPresetSaveDialogRequest,
    ) -> tuple[str, PresetSaveScope]:
        """Fail the test if the controller requests a dialog."""

        nonlocal called
        called = True
        return ("Unused", _scope())

    assert not controller.save_selected_segment_as_preset(dialog_runner=run_dialog)

    assert called is False
    assert source.saved == []
    assert source.list_calls == 1
    assert controller.snapshot.unavailable_reason == "save_scopes_unavailable"
    assert controller.snapshot.status.readiness is CatalogSnapshotReadiness.UNAVAILABLE


def test_controller_snapshot_identity_tracks_source_revision_changes() -> None:
    """Preset snapshots should carry source revision for stale rejection."""

    host = _Host()
    controller = _controller(host=host)

    controller.prepare_menu_snapshot_for_selection(
        selected_text="alpha",
        selection_range=(0, 5),
        read_only=False,
        reason="test",
    )
    assert (
        controller.prepared_menu_snapshot_for_selection(
            selected_text="alpha",
            selection_range=(0, 5),
            read_only=False,
        ).identity.source_revision
        == 7
    )
    host.text = "alpha beta gamma delta"
    host.source_revision = 8
    controller.prepare_menu_snapshot_for_selection(
        selected_text="delta",
        selection_range=(17, 22),
        read_only=False,
        reason="test",
    )
    snapshot = controller.prepared_menu_snapshot_for_selection(
        selected_text="delta",
        selection_range=(17, 22),
        read_only=False,
    )

    assert snapshot.identity.source_revision == 8
    assert snapshot.save_state.selected_text == "delta"


def _controller(
    *,
    host: _Host,
    insertion_executor: _TextInsertionExecutor | None = None,
    source: _Source | None = None,
    source_available: bool = True,
) -> PromptSegmentPresetController:
    """Build a segment preset controller for tests."""

    return PromptSegmentPresetController(
        host=host,
        text_insertion_executor=insertion_executor or _TextInsertionExecutor(),
        feature_profile=PromptFeatureProfileController(
            prompt_feature_profile_from_legacy_syntax(None)
        ),
        preset_source=(source if source is not None else _Source())
        if source_available
        else None,
    )


def _scope() -> PresetSaveScope:
    """Return the global preset save scope used by tests."""

    return PresetSaveScope(
        title="Global",
        full_label="Global",
        association=GLOBAL_PRESET_ASSOCIATION,
    )
