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

"""Coordinate UI-facing work after backend model catalog changes."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Protocol

from substitute.application.execution import (
    ExecutionContext,
    TaskIdentity,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.application.model_metadata import (
    BackendModelCatalogChangeEvent,
    ModelCatalogService,
    RichChoiceResolver,
    ScopedMetadataRefreshService,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_exception

_LOGGER = get_logger("presentation.shell.model_catalog_change_coordinator")


class _NodeDefinitionBatchRefresher(Protocol):
    """Describe targeted node-definition refresh support."""

    def refresh_node_definitions(self, node_classes: Iterable[str]) -> tuple[str, ...]:
        """Force-refresh selected node definitions and return available classes."""


class _LoraCatalogRefreshCoordinator(Protocol):
    """Describe the LoRA catalog refresh surface used by the shell."""

    def request_refresh(self, kind: str, context: object | None = None) -> None:
        """Request a canonical model catalog snapshot refresh."""


class ModelCatalogChangeCoordinator:
    """Apply backend model catalog changes to cached app state and live surfaces."""

    def __init__(
        self,
        *,
        model_catalog_service: ModelCatalogService,
        model_choice_resolver: RichChoiceResolver,
        node_definition_gateway: object,
        lora_refresh_coordinator: _LoraCatalogRefreshCoordinator,
        scoped_metadata_refresh_service: ScopedMetadataRefreshService,
        submitter: TaskSubmitter | None = None,
        close_submitter: Callable[[], None] | None = None,
    ) -> None:
        """Store collaborators used to fan out one backend catalog change."""

        self._model_catalog_service = model_catalog_service
        self._model_choice_resolver = model_choice_resolver
        self._node_definition_gateway = node_definition_gateway
        self._lora_refresh_coordinator = lora_refresh_coordinator
        self._scoped_metadata_refresh_service = scoped_metadata_refresh_service
        if submitter is None:
            raise TypeError(
                "submitter is required for model catalog change coordination."
            )
        self._submitter = submitter
        self._scope = TaskScope(
            submitter=submitter,
            scope_id=f"model_catalog_change_{id(self):x}",
        )
        self._close_submitter = close_submitter
        self._request_id = 0

    def handle_change(self, event: BackendModelCatalogChangeEvent) -> None:
        """Invalidate caches, refresh affected nodes, and queue scoped metadata."""

        for kind in event.kinds:
            self._model_catalog_service.invalidate(kind)
            self._model_choice_resolver.invalidate(kind)
            if kind == "loras":
                self._lora_refresh_coordinator.request_refresh("loras", event)
        if event.affected_node_classes:
            self._refresh_node_definitions_async(event.affected_node_classes)
        self._scoped_metadata_refresh_service.queue_entries(event.enrichable_entries)
        log_debug(
            _LOGGER,
            "Handled model catalog change",
            revision=event.revision,
            kinds=event.kinds,
            affected_node_classes=event.affected_node_classes,
            enrichable_count=len(event.enrichable_entries),
        )

    def shutdown(self) -> None:
        """Release coordinator-owned background resources."""

        self._scope.close(reason="model_catalog_change_shutdown")
        if self._close_submitter is not None:
            self._close_submitter()
            self._close_submitter = None
        self._scoped_metadata_refresh_service.shutdown()

    def _refresh_node_definitions_async(
        self,
        node_classes: tuple[str, ...],
    ) -> None:
        """Force-refresh affected node definitions away from the GUI thread."""

        refresher = self._node_definition_gateway
        refresh = getattr(refresher, "refresh_node_definitions", None)
        if not callable(refresh):
            log_debug(
                _LOGGER,
                "Skipped model catalog node refresh; gateway has no batch refresher",
                node_classes=node_classes,
            )
            return

        def run_refresh() -> None:
            """Run one targeted node-definition refresh batch."""

            try:
                refreshed = refresh(node_classes)
            except Exception:
                log_exception(
                    _LOGGER,
                    "Model catalog node definition refresh failed",
                    node_classes=node_classes,
                )
                return
            log_debug(
                _LOGGER,
                "Model catalog node definition refresh completed",
                requested_node_classes=node_classes,
                refreshed_node_classes=refreshed,
            )

        try:
            self._request_id += 1
            self._scope.submit(
                TaskRequest(
                    identity=TaskIdentity(
                        request_id=self._request_id,
                        domain="node_definition",
                        parts=(("operation_key", "model_catalog_change"),),
                    ),
                    context=ExecutionContext(
                        operation="model_catalog_node_definition_refresh",
                        reason="model_catalog_change",
                        lane="node_definition",
                        safe_fields=(
                            ("operation_key", "model_catalog_change"),
                            ("request_id", self._request_id),
                        ),
                    ),
                    work=lambda _token: run_refresh(),
                )
            )
        except Exception:
            log_exception(
                _LOGGER,
                "Failed to schedule model catalog node definition refresh",
                node_classes=node_classes,
            )


__all__ = ["ModelCatalogChangeCoordinator"]
