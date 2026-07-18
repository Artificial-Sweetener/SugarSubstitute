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

"""Classify and route workspace fallback drag-and-drop workflow loads."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from substitute.application.recipes.recipe_io_service import (
    RecipeDocumentClassification,
)
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("presentation.shell.workspace_drop_controller")


class DropIntent(Enum):
    """Describe the workspace-level action represented by a drag payload."""

    NONE = "none"
    LOAD_WORKFLOW_RECIPE = "load_workflow_recipe"
    LOAD_DIRECT_COMFY_WORKFLOW = "load_direct_comfy_workflow"
    LOAD_NODE_IMAGE = "load_node_image"


@dataclass(frozen=True)
class DropClassification:
    """Capture one workspace fallback drag/drop classification result."""

    intent: DropIntent
    path: Path | None = None
    reason: str = ""


class UrlProtocol(Protocol):
    """Describe the local-file subset of Qt URL objects used for drops."""

    def isLocalFile(self) -> bool:
        """Return whether this URL points at a local filesystem path."""

    def toLocalFile(self) -> str:
        """Return the local filesystem path represented by this URL."""


class MimeDataProtocol(Protocol):
    """Describe the URL-bearing subset of Qt mime data used for drops."""

    def hasUrls(self) -> bool:
        """Return whether the payload contains URLs."""

    def urls(self) -> Sequence[UrlProtocol]:
        """Return URLs carried by the payload."""


class DropEventProtocol(Protocol):
    """Describe the drag/drop event operations used by the controller."""

    def mimeData(self) -> MimeDataProtocol:
        """Return event mime data."""

    def source(self) -> object | None:
        """Return the originating drag source when Qt can identify it."""

    def acceptProposedAction(self) -> None:
        """Accept the proposed drop action."""

    def ignore(self) -> None:
        """Ignore the drop action."""


class RecipeDocumentClassifierProtocol(Protocol):
    """Describe recipe-source classification used by drop routing."""

    def classify_recipe_document(self, path: Path) -> RecipeDocumentClassification:
        """Classify a path for recipe loading."""


class DirectWorkflowDocumentClassifier:
    """Recognize the explicit file boundary for Comfy UI workflow documents."""

    def supports(self, path: Path) -> bool:
        """Return whether the path can contain a direct Comfy workflow."""

        return path.suffix.casefold() == ".json"


class WorkflowRecipeDropClassifier:
    """Classify workspace fallback drops that should load workflow recipes."""

    def __init__(
        self,
        recipe_classifier: RecipeDocumentClassifierProtocol,
        direct_workflow_classifier: DirectWorkflowDocumentClassifier | None = None,
    ) -> None:
        """Store document classification dependencies."""

        self._recipe_classifier = recipe_classifier
        self._direct_workflow_classifier = direct_workflow_classifier

    def classify_mime_data(self, mime_data: MimeDataProtocol) -> DropClassification:
        """Classify mime data for workspace fallback drag/drop handling."""

        if not mime_data.hasUrls():
            return DropClassification(DropIntent.NONE, reason="no_urls")
        urls = tuple(mime_data.urls())
        if len(urls) != 1:
            return DropClassification(DropIntent.NONE, reason="not_single_file")
        url = urls[0]
        if not url.isLocalFile():
            return DropClassification(DropIntent.NONE, reason="non_local_url")
        local_file = url.toLocalFile()
        if not local_file:
            return DropClassification(DropIntent.NONE, reason="empty_local_file")
        return self.classify_path(Path(local_file))

    def classify_path(self, path: Path) -> DropClassification:
        """Classify one local path for workspace fallback drag/drop handling."""

        if (
            self._direct_workflow_classifier is not None
            and self._direct_workflow_classifier.supports(path)
        ):
            return DropClassification(
                DropIntent.LOAD_DIRECT_COMFY_WORKFLOW,
                path=path,
                reason="comfy_workflow_json",
            )

        recipe_classification = self._recipe_classifier.classify_recipe_document(path)
        if not recipe_classification.supported:
            return DropClassification(
                DropIntent.NONE,
                path=path,
                reason=recipe_classification.reason,
            )
        return DropClassification(
            DropIntent.LOAD_WORKFLOW_RECIPE,
            path=path,
            reason=recipe_classification.reason,
        )


class WorkspaceDropController:
    """Route accepted workspace fallback drops into the recipe load pipeline."""

    def __init__(
        self,
        *,
        classifier: WorkflowRecipeDropClassifier,
        ignored_drag_source: Callable[[object | None], bool],
        load_recipe_document: Callable[[Path], str | None],
        load_direct_workflow_document: Callable[[Path], str | None] | None = None,
    ) -> None:
        """Store drop classification and workflow-loading collaborators."""

        self._classifier = classifier
        self._ignored_drag_source = ignored_drag_source
        self._load_recipe_document = load_recipe_document
        self._load_direct_workflow_document = load_direct_workflow_document

    def handle_drag_enter(self, event: DropEventProtocol) -> bool:
        """Accept drag-enter only for workflow recipe drops."""

        return self._classify_and_update_event(event, phase="drag_enter")

    def handle_drag_move(self, event: DropEventProtocol) -> bool:
        """Accept drag-move only for workflow recipe drops."""

        return self._classify_and_update_event(event, phase="drag_move")

    def handle_drop(self, event: DropEventProtocol) -> bool:
        """Load an accepted workflow recipe drop through the shared load path."""

        if self._ignore_internal_drag(event, phase="drop"):
            return False
        classification = self._classifier.classify_mime_data(event.mimeData())
        self._log_classification("drop", classification)
        if classification.intent not in _LOADABLE_WORKSPACE_INTENTS:
            event.ignore()
            return False
        if classification.path is None:
            event.ignore()
            return False
        load_document = self._load_document_for_intent(classification.intent)
        if load_document is None:
            event.ignore()
            return False
        event.acceptProposedAction()
        log_debug(
            _LOGGER,
            "Workspace document drop loading started",
            path=classification.path,
            reason=classification.reason,
            intent=classification.intent.value,
        )
        workflow_id = load_document(classification.path)
        log_debug(
            _LOGGER,
            "Workspace document drop loading completed",
            path=classification.path,
            reason=classification.reason,
            intent=classification.intent.value,
            workflow_id=workflow_id,
        )
        return True

    def _load_document_for_intent(
        self,
        intent: DropIntent,
    ) -> Callable[[Path], str | None] | None:
        """Return the single shell load action owned by a classified intent."""

        if intent is DropIntent.LOAD_WORKFLOW_RECIPE:
            return self._load_recipe_document
        if intent is DropIntent.LOAD_DIRECT_COMFY_WORKFLOW:
            return self._load_direct_workflow_document
        return None

    def _ignore_internal_drag(
        self,
        event: DropEventProtocol,
        *,
        phase: str,
    ) -> bool:
        """Ignore configured in-process drag sources for workspace recipe loading."""

        source = event.source()
        if not self._ignored_drag_source(source):
            return False
        event.ignore()
        log_debug(
            _LOGGER,
            "Workspace recipe drop ignored for internal drag source",
            phase=phase,
            source_type=type(source).__name__ if source is not None else "None",
            reason="internal_drag_source",
        )
        return True

    def _classify_and_update_event(
        self,
        event: DropEventProtocol,
        *,
        phase: str,
    ) -> bool:
        """Classify an event and accept it only for workflow recipe drops."""

        if self._ignore_internal_drag(event, phase=phase):
            return False
        classification = self._classifier.classify_mime_data(event.mimeData())
        should_log = phase != "drag_move"
        if should_log:
            self._log_classification(phase, classification)
        if (
            classification.intent in _LOADABLE_WORKSPACE_INTENTS
            and self._load_document_for_intent(classification.intent) is not None
        ):
            event.acceptProposedAction()
            if should_log:
                log_debug(
                    _LOGGER,
                    "Workspace document drop accepted",
                    phase=phase,
                    path=classification.path,
                    reason=classification.reason,
                )
            return True
        event.ignore()
        if should_log:
            log_debug(
                _LOGGER,
                "Workspace recipe drop ignored",
                phase=phase,
                path=classification.path,
                reason=classification.reason,
                intent=classification.intent.value,
            )
        return False

    def _log_classification(
        self,
        phase: str,
        classification: DropClassification,
    ) -> None:
        """Log one workspace fallback drop classification."""

        log_debug(
            _LOGGER,
            "Workspace drop classified",
            phase=phase,
            path=classification.path,
            reason=classification.reason,
            intent=classification.intent.value,
        )


_LOADABLE_WORKSPACE_INTENTS = frozenset(
    {DropIntent.LOAD_WORKFLOW_RECIPE, DropIntent.LOAD_DIRECT_COMFY_WORKFLOW}
)


__all__ = [
    "DropClassification",
    "DropIntent",
    "DirectWorkflowDocumentClassifier",
    "WorkspaceDropController",
    "WorkflowRecipeDropClassifier",
]
