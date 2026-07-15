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

"""Provide workflow-tab naming and re-key policies for presentation callers."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Collection, Iterable, MutableMapping, TypeVar

MapValueT = TypeVar("MapValueT")

_SAFE_WORKFLOW_NAME_PATTERN = re.compile(r"^[\w \-]+$")
_INVALID_NAME_MESSAGE = (
    "Invalid characters in name.\n\n"
    "Use only letters, numbers, spaces, underscores (_), or hyphens (-)."
)
DEFAULT_WORKFLOW_TAB_LABEL = "Untitled Workflow"
_LEGACY_DEFAULT_WORKFLOW_TAB_LABEL = "Untitled Recipe"
_DEFAULT_WORKFLOW_TAB_LABEL_PATTERN = re.compile(
    rf"^{re.escape(DEFAULT_WORKFLOW_TAB_LABEL)}(?: \((\d+)\))?$"
)
_LEGACY_DEFAULT_WORKFLOW_TAB_LABEL_PATTERN = re.compile(
    rf"^{re.escape(_LEGACY_DEFAULT_WORKFLOW_TAB_LABEL)}(?: \((\d+)\))?$"
)


def normalize_default_workflow_tab_label(tab_label: str) -> str:
    """Return the current generated default label for blank or legacy labels."""

    normalized_label = tab_label.strip()
    if not normalized_label:
        return DEFAULT_WORKFLOW_TAB_LABEL

    legacy_match = _LEGACY_DEFAULT_WORKFLOW_TAB_LABEL_PATTERN.match(normalized_label)
    if legacy_match is None:
        return normalized_label

    suffix = legacy_match.group(1)
    if suffix is None:
        return DEFAULT_WORKFLOW_TAB_LABEL
    return f"{DEFAULT_WORKFLOW_TAB_LABEL} ({suffix})"


def is_default_workflow_tab_label(tab_label: str) -> bool:
    """Return True when a label is a generated untitled workflow label."""

    normalized_label = tab_label.strip()
    return (
        _DEFAULT_WORKFLOW_TAB_LABEL_PATTERN.match(normalized_label) is not None
        or _LEGACY_DEFAULT_WORKFLOW_TAB_LABEL_PATTERN.match(normalized_label)
        is not None
    )


@dataclass(frozen=True)
class WorkflowTabCreation:
    """Describe newly planned workflow-tab identifiers."""

    workflow_id: str
    tab_label: str


@dataclass(frozen=True)
class WorkflowInlineRenameDecision:
    """Describe finalized inline-rename outcome after policy resolution."""

    accepted: bool
    workflow_id: str
    tab_label: str


class WorkflowTabService:
    """Own deterministic workflow-tab naming and dictionary re-key behavior."""

    def __init__(self, random_generator: random.Random | None = None) -> None:
        """Create service with injectable random source for test determinism."""
        self._random = random_generator or random.Random()

    def plan_new_workflow_tab(
        self,
        *,
        base_name: str,
        existing_labels: Collection[str],
        existing_workflow_ids: Collection[str],
    ) -> WorkflowTabCreation:
        """Plan a unique workflow id and tab label for a new workflow tab."""
        unique_label = self._resolve_unique_label(base_name, existing_labels)
        workflow_id = self._generate_unique_workflow_id(existing_workflow_ids)
        return WorkflowTabCreation(workflow_id=workflow_id, tab_label=unique_label)

    def resolve_inline_rename(
        self,
        *,
        old_workflow_id: str,
        proposed_name: str,
        existing_tab_keys: Collection[str],
        existing_workflow_ids: Collection[str],
    ) -> WorkflowInlineRenameDecision:
        """Resolve inline rename to valid unique id or reject with visual revert."""
        normalized_name = proposed_name.strip()
        if not normalized_name or not _SAFE_WORKFLOW_NAME_PATTERN.match(
            normalized_name
        ):
            return WorkflowInlineRenameDecision(
                accepted=False,
                workflow_id=old_workflow_id,
                tab_label=old_workflow_id,
            )

        unique_name = normalized_name
        counter = 2
        while self._has_name_conflict(
            candidate_name=unique_name,
            old_workflow_id=old_workflow_id,
            existing_tab_keys=existing_tab_keys,
            existing_workflow_ids=existing_workflow_ids,
        ):
            unique_name = f"{normalized_name} ({counter})"
            counter += 1

        return WorkflowInlineRenameDecision(
            accepted=True,
            workflow_id=unique_name,
            tab_label=unique_name,
        )

    @staticmethod
    def rekey_mapping(
        mapping: MutableMapping[str, MapValueT],
        *,
        old_key: str,
        new_key: str,
    ) -> None:
        """Move value from old key to new key in mapping when old key exists."""
        if old_key == new_key or old_key not in mapping:
            return
        mapping[new_key] = mapping.pop(old_key)

    def rekey_workflow_scoped_maps(
        self,
        *,
        old_workflow_id: str,
        new_workflow_id: str,
        mappings: Iterable[MutableMapping[str, object]],
    ) -> None:
        """Re-key every workflow-scoped mapping to match renamed workflow id."""
        for mapping in mappings:
            self.rekey_mapping(
                mapping,
                old_key=old_workflow_id,
                new_key=new_workflow_id,
            )

    def _resolve_unique_label(
        self, base_name: str, existing_labels: Collection[str]
    ) -> str:
        """Return unique tab label by appending numeric suffix when needed."""
        if base_name not in existing_labels:
            return base_name

        counter = 2
        while True:
            candidate = f"{base_name} ({counter})"
            if candidate not in existing_labels:
                return candidate
            counter += 1

    def _generate_unique_workflow_id(
        self, existing_workflow_ids: Collection[str]
    ) -> str:
        """Generate unique internal workflow id in legacy random-id format."""
        while True:
            candidate = f"workflow_{self._random.randint(10000, 99999)}"
            if candidate not in existing_workflow_ids:
                return candidate

    @staticmethod
    def _has_name_conflict(
        *,
        candidate_name: str,
        old_workflow_id: str,
        existing_tab_keys: Collection[str],
        existing_workflow_ids: Collection[str],
    ) -> bool:
        """Return True when candidate collides with another tab/workflow id."""
        in_tabs = (
            candidate_name in existing_tab_keys and candidate_name != old_workflow_id
        )
        in_workflows = (
            candidate_name in existing_workflow_ids
            and candidate_name != old_workflow_id
        )
        return in_tabs or in_workflows


__all__ = [
    "DEFAULT_WORKFLOW_TAB_LABEL",
    "WorkflowInlineRenameDecision",
    "WorkflowTabCreation",
    "WorkflowTabService",
    "is_default_workflow_tab_label",
    "normalize_default_workflow_tab_label",
]
