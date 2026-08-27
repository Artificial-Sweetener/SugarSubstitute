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

"""Build workflow-action test doubles."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any


from substitute.domain.workflow import WorkflowState
from substitute.domain.workspace_snapshot import (
    EditorViewportSnapshot,
    InputImageReference,
    InputMaskReference,
    OutputImageReference,
)


def _import_module() -> Any:
    """Import the workflow workspace coordinator module."""

    return importlib.import_module(
        "substitute.presentation.shell.workflow_workspace_coordinator"
    )


class _TabItem:
    """Workflow-tab item double with mutable text and route key."""

    def __init__(self, route_key: str, text: str | None = None) -> None:
        """Store route key and label text."""

        self._route_key = route_key
        self._text = text or route_key

    def routeKey(self) -> str:
        """Return the current route key."""

        return self._route_key

    def text(self) -> str:
        """Return the current label text."""

        return self._text

    def setText(self, text: str) -> None:
        """Record text updates."""

        self._text = text

    def setRouteKey(self, key: str) -> None:
        """Record route-key updates."""

        self._route_key = key


class _TabBar:
    """Workflow tabbar double with workflow-id silent operations."""

    def __init__(self, workflow_ids: list[str]) -> None:
        """Create tab items for ids."""

        self.items = [_TabItem(workflow_id) for workflow_id in workflow_ids]
        self.itemMap = {item.routeKey(): item for item in self.items}
        self.selected: list[tuple[str, bool]] = []
        self.removed: list[tuple[str, bool]] = []

    def addTab(self, routeKey: str, text: str) -> _TabItem:
        """Add and return a workflow tab item."""

        item = _TabItem(routeKey, text)
        self.items.append(item)
        self.itemMap[routeKey] = item
        return item

    def insertTab(self, index: int, routeKey: str, text: str) -> _TabItem:
        """Insert and return a workflow tab item."""

        item = _TabItem(routeKey, text)
        self.items.insert(index, item)
        self.itemMap[routeKey] = item
        return item

    def count(self) -> int:
        """Return current tab count."""

        return len(self.items)

    def currentIndex(self) -> int:
        """Return the first selected tab index for legacy fallback."""

        if not self.items:
            return -1
        if not self.selected:
            return 0
        selected_id = self.selected[-1][0]
        return self.items.index(self.itemMap[selected_id])

    def tabItem(self, index: int) -> _TabItem:
        """Return tab item at index."""

        return self.items[index]

    def workflow_ids_in_order(self) -> list[str]:
        """Return current tab ids in order."""

        return [item.routeKey() for item in self.items]

    def select_workflow_tab(self, workflow_id: str, *, emit: bool = False) -> None:
        """Record tab selection."""

        self.selected.append((workflow_id, emit))

    def remove_workflow_tab(self, workflow_id: str, *, emit: bool = False) -> None:
        """Record and apply tab removal."""

        self.removed.append((workflow_id, emit))
        tab_item = self.itemMap.pop(workflow_id)
        self.items.remove(tab_item)


class _Manager:
    """Override-manager double recording lifecycle calls."""

    def __init__(self, workflow_id: str, calls: list[str]) -> None:
        """Store workflow id and shared call log."""

        self._workflow_id = workflow_id
        self._calls = calls

    def _clear_all_override_widgets(self) -> None:
        """Record toolbar clearing."""

        self._calls.append(f"{self._workflow_id}:clear")

    def detach_override_widgets(self) -> None:
        """Record toolbar detachment."""

        self._calls.append(f"{self._workflow_id}:detach")

    def sync_state_from_workflow(self) -> None:
        """Record per-workflow override state projection."""

        self._calls.append(f"{self._workflow_id}:sync")

    def rebuild_override_menu(self) -> None:
        """Record per-workflow override menu projection."""

        self._calls.append(f"{self._workflow_id}:menu")

    def rebuild_active_override_controls(self) -> None:
        """Record per-workflow override toolbar projection."""

        self._calls.append(f"{self._workflow_id}:controls")

    def dispose(self) -> None:
        """Record manager disposal."""

        self._calls.append(f"{self._workflow_id}:dispose")


class _CubeStack:
    """Cube-stack double recording tab materialization."""

    def __init__(self, label: str, calls: list[str]) -> None:
        """Store label and mutable tab collection."""

        self._label = label
        self._calls = calls
        self.tabs: list[dict[str, object]] = []
        self.current_index: int | None = None

    def clear(self) -> None:
        """Clear recorded tabs."""

        self.tabs.clear()
        self._calls.append(f"{self._label}:clear")

    def count(self) -> int:
        """Return recorded tab count."""

        return len(self.tabs)

    def insertTab(
        self,
        index: int,
        *,
        routeKey: str,
        text: str,
        icon: object | None = None,
    ) -> object:
        """Insert and record one tab."""

        tab = {"routeKey": routeKey, "text": text, "icon": icon}
        self.tabs.insert(index, tab)
        self._calls.append(f"{self._label}:insert:{routeKey}:{text}")
        return tab

    def setCurrentIndex(self, index: int) -> None:
        """Record selected tab index."""

        self.current_index = index
        self._calls.append(f"{self._label}:current:{index}")

    def setTabIcon(self, index: int, icon: object) -> None:
        """Record one tab icon update."""

        self.tabs[index]["icon"] = icon
        self._calls.append(f"{self._label}:icon:{index}:{icon}")

    def deleteLater(self) -> None:
        """Record deletion."""

        self._calls.append(f"{self._label}:delete")


class _ProjectionAwareEditorPanel:
    """Editor-panel double exposing projection-cleanliness APIs."""

    def __init__(self, *, clean: bool) -> None:
        """Store whether the panel should report a clean projection."""

        self.clean = clean
        self.signature_requests: list[dict[str, object]] = []

    def current_projection_signature(self, **kwargs: object) -> object:
        """Return a signature token for requested projection inputs."""

        self.signature_requests.append(kwargs)
        return "signature"

    def is_projection_clean(self, signature: object) -> bool:
        """Return configured cleanliness for the supplied signature."""

        return signature == "signature" and self.clean

    def clear_model_field_load_progress(self) -> None:
        """Accept generation-feedback progress cleanup."""

    def deleteLater(self) -> None:
        """Provide lifecycle compatibility for coordinator disposal."""


def _deletable(label: str, calls: list[str]) -> SimpleNamespace:
    """Return a widget double with delete recording."""

    return SimpleNamespace(
        clear_model_field_load_progress=lambda: calls.append(f"{label}:model:clear"),
        deleteLater=lambda: calls.append(f"{label}:delete"),
    )


class _SnapshotCapture:
    """Capture close-time workflow snapshot calls for coordinator tests."""

    def __init__(self, calls: list[str]) -> None:
        """Store the shared call log."""

        self._calls = calls

    def workflow_tab_label(self, workflow_id: str) -> str:
        """Return an adapter-provided workflow label."""

        self._calls.append(f"snapshot:label:{workflow_id}")
        return f"Snapshot {workflow_id}"

    def active_cube_alias(self, workflow_id: str) -> str | None:
        """Return an adapter-provided active cube alias."""

        self._calls.append(f"snapshot:active-cube:{workflow_id}")
        return "SnapshotCube"

    def editor_viewport_snapshot(
        self,
        workflow_id: str,
    ) -> EditorViewportSnapshot | None:
        """Return no viewport while recording the adapter call."""

        self._calls.append(f"snapshot:viewport:{workflow_id}")
        return None

    def input_image_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[InputImageReference, ...]:
        """Return no input images while recording the adapter call."""

        del workflow
        self._calls.append(f"snapshot:input-images:{workflow_id}")
        return ()

    def input_mask_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[InputMaskReference, ...]:
        """Return no input masks while recording the adapter call."""

        del workflow
        self._calls.append(f"snapshot:input-masks:{workflow_id}")
        return ()

    def output_image_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[OutputImageReference, ...]:
        """Return no output images while recording the adapter call."""

        del workflow
        self._calls.append(f"snapshot:output-images:{workflow_id}")
        return ()
