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

"""Test ready-shell restore restore-asset preload contracts."""

from __future__ import annotations


import pytest

from substitute.app.bootstrap.ready_shell_restore_controller import (
    attach_restore_asset_preload_to_shell,
)

from .restore_support import (
    _patch_trace,
)


class _RestoreAssetMainWindow:
    """Expose a restore image adapter for preload handoff tests."""

    def __init__(self, restore_adapter: object) -> None:
        """Store the restore adapter double."""

        self.workspace_restore_image_adapter = restore_adapter


class _RestoreImageAdapter:
    """Record restore asset preload handoff."""

    def __init__(self) -> None:
        """Create empty preload records."""

        self.preloads: list[object] = []

    def set_restore_asset_preload(self, preload: object) -> None:
        """Record one restore asset preload."""

        self.preloads.append(preload)


def test_attach_restore_asset_preload_to_shell_sets_restore_preload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Restore asset preloads should be passed to the shell restore adapter."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    preload = object()
    restore_adapter = _RestoreImageAdapter()
    main_window = _RestoreAssetMainWindow(restore_adapter)

    attached = attach_restore_asset_preload_to_shell(
        main_window=main_window,
        restore_asset_preload=preload,
        trace_fields=lambda: {"route": "ready"},
    )

    assert attached is True
    assert restore_adapter.preloads == [preload]
    assert events == [
        (
            "build_shell_task.restore_asset_preload.attached",
            {"route": "ready"},
        )
    ]


def test_attach_restore_asset_preload_to_shell_skips_without_preload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing restore preloads should not inspect shell adapters."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    main_window = object()

    attached = attach_restore_asset_preload_to_shell(
        main_window=main_window,
        restore_asset_preload=None,
        trace_fields=lambda: {"route": "ready"},
    )

    assert attached is False
    assert events == [
        (
            "build_shell_task.restore_asset_preload.skip",
            {"reason": "no_restore_asset_preload", "route": "ready"},
        )
    ]


def test_attach_restore_asset_preload_to_shell_skips_without_adapter_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incomplete shell adapters should not fail restore preload handoff."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    main_window = _RestoreAssetMainWindow(restore_adapter=object())

    attached = attach_restore_asset_preload_to_shell(
        main_window=main_window,
        restore_asset_preload=object(),
        trace_fields=lambda: {"route": "ready"},
    )

    assert attached is False
    assert events == [
        (
            "build_shell_task.restore_asset_preload.skip",
            {"reason": "no_restore_asset_preload_port", "route": "ready"},
        )
    ]
