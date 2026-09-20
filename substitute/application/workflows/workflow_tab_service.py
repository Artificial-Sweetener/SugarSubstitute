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

"""Provide workflow-tab naming and immutable identity policies."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Collection
from uuid import UUID

from sugarsubstitute_shared.localization import ApplicationText, app_text, opaque_text

_SAFE_WORKFLOW_NAME_PATTERN = re.compile(r"^[\w \-]+$")
DEFAULT_WORKFLOW_TAB_LABEL = opaque_text("Untitled Workflow")
_LEGACY_DEFAULT_WORKFLOW_TAB_LABEL = opaque_text("Untitled Recipe")
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


def workflow_tab_display_text(tab_label: str) -> ApplicationText:
    """Project generated default labels while preserving authored workflow names."""

    normalized_label = tab_label.strip()
    match = _DEFAULT_WORKFLOW_TAB_LABEL_PATTERN.match(normalized_label)
    if match is None:
        match = _LEGACY_DEFAULT_WORKFLOW_TAB_LABEL_PATTERN.match(normalized_label)
    if match is None:
        return tab_label
    suffix = match.group(1)
    if suffix is None:
        return app_text("Untitled Workflow")
    return app_text("Untitled Workflow (%1)", suffix)


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
    """Own workflow-tab naming and immutable identity generation."""

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
        unique_label = self.resolve_unique_label(base_name, existing_labels)
        workflow_id = self.generate_workflow_id(existing_workflow_ids)
        return WorkflowTabCreation(workflow_id=workflow_id, tab_label=unique_label)

    def resolve_inline_rename(
        self,
        *,
        old_workflow_id: str,
        proposed_name: str,
        existing_labels: Collection[str],
    ) -> WorkflowInlineRenameDecision:
        """Resolve a label-only rename while preserving immutable identity."""
        normalized_name = proposed_name.strip()
        if not normalized_name or not _SAFE_WORKFLOW_NAME_PATTERN.match(
            normalized_name
        ):
            return WorkflowInlineRenameDecision(
                accepted=False,
                workflow_id=old_workflow_id,
                tab_label="",
            )

        unique_name = normalized_name
        counter = 2
        while unique_name in existing_labels:
            unique_name = f"{normalized_name} ({counter})"
            counter += 1

        return WorkflowInlineRenameDecision(
            accepted=True,
            workflow_id=old_workflow_id,
            tab_label=unique_name,
        )

    def resolve_unique_label(
        self, base_name: str, existing_labels: Collection[str]
    ) -> str:
        """Return a unique normalized tab label for document loading or creation."""

        base_name = normalize_default_workflow_tab_label(base_name)
        if base_name not in existing_labels:
            return base_name

        counter = 2
        while True:
            candidate = f"{base_name} ({counter})"
            if candidate not in existing_labels:
                return candidate
            counter += 1

    def generate_workflow_id(self, existing_workflow_ids: Collection[str]) -> str:
        """Generate one unique immutable UUID workflow identity."""
        while True:
            candidate = str(UUID(int=self._random.getrandbits(128), version=4))
            if candidate not in existing_workflow_ids:
                return candidate


__all__ = [
    "DEFAULT_WORKFLOW_TAB_LABEL",
    "WorkflowInlineRenameDecision",
    "WorkflowTabCreation",
    "WorkflowTabService",
    "is_default_workflow_tab_label",
    "normalize_default_workflow_tab_label",
    "workflow_tab_display_text",
]
