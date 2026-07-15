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

"""Own Input mask save debounce and generation preflight persistence."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol, cast
from uuid import UUID

from PySide6.QtCore import QTimer

from substitute.presentation.canvas.input.input_mask_dirty_tracker import (
    InputMaskDirtyTracker,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_error,
    log_info,
    log_warning,
)

_LOGGER = get_logger("presentation.canvas.input.input_mask_save_controller")


class SignalPort(Protocol):
    """Describe a Qt-like signal used by QPane collaborators."""

    def connect(self, callback: Callable[..., object]) -> object:
        """Connect one callback to this signal."""


class TimerPort(Protocol):
    """Describe the timer API needed for mask save debounce."""

    timeout: SignalPort

    def setSingleShot(self, value: bool) -> None:  # noqa: N802
        """Set whether this timer fires only once."""

    def start(self, delay_ms: int) -> None:
        """Start or restart this timer."""

    def stop(self) -> None:
        """Stop this timer."""


class InputPanePort(Protocol):
    """Describe QPane mask APIs consumed by the save controller."""

    maskSaved: SignalPort
    mask_controller: object
    settings: object

    def catalog(self) -> object:
        """Return QPane catalog object."""


class WorkflowSessionServicePort(Protocol):
    """Describe active workflow session data needed for mask preflight."""

    active_workflow_id: str
    workflows: Mapping[str, object]


class CanvasIoServicePort(Protocol):
    """Describe canvas mask path and image persistence APIs."""

    def resolve_mask_save_path(
        self,
        *,
        workflow_name: str,
        mask_filename: str,
        projects_dir: Path,
    ) -> Path:
        """Resolve canonical mask save path from graph buffer state."""

    def save_mask_image(self, *, destination: Path, image: object) -> bool:
        """Persist one mask image payload to disk."""


class WorkflowAssetServicePort(Protocol):
    """Describe workflow mask asset persistence APIs."""

    def associate_project_input_mask(
        self,
        workflow: object,
        *,
        cube_alias: str,
        node_name: str,
        relative_path: Path | str,
    ) -> bool:
        """Associate one mask node with a project mask path."""


class InputMaskSaveController:
    """Persist dirty Input masks from QPane signals and generation preflight."""

    def __init__(
        self,
        *,
        input_pane: InputPanePort,
        dirty_tracker: InputMaskDirtyTracker,
        workflow_session_service: WorkflowSessionServicePort,
        canvas_io_service: CanvasIoServicePort,
        workflow_asset_service: WorkflowAssetServicePort,
        workflow_name_provider: Callable[[str], str],
        projects_dir_provider: Callable[[], Path],
        refresh_saved_mask: Callable[[str, str, str], None] | None = None,
        timer_factory: Callable[[object | None], TimerPort] | None = None,
    ) -> None:
        """Store Input mask persistence collaborators and bind QPane signals."""

        self._input_pane = input_pane
        self._dirty_tracker = dirty_tracker
        self._workflow_session_service = workflow_session_service
        self._canvas_io_service = canvas_io_service
        self._workflow_asset_service = workflow_asset_service
        self._workflow_name_provider = workflow_name_provider
        self._projects_dir_provider = projects_dir_provider
        self._refresh_saved_mask = refresh_saved_mask
        self._timer_factory = timer_factory or self._create_qtimer
        self._save_timers: dict[UUID, TimerPort] = {}
        self._mask_update_signal_bound = False
        self._bind_qpane_signals()

    @staticmethod
    def _create_qtimer(_parent: object | None) -> TimerPort:
        """Create the Qt timer behind the narrow debounce timer port."""

        return cast(TimerPort, QTimer())

    def flush_dirty_associated_masks_before_generation(self) -> bool:
        """Persist all dirty masks associated with the active workflow."""

        workflow_id = self._workflow_session_service.active_workflow_id
        workflow = self._workflow_session_service.workflows.get(workflow_id)
        if workflow is None:
            log_info(
                _LOGGER,
                "Skipping dirty input mask preflight without active workflow",
                workflow_id=workflow_id,
                skip_reason="no_active_workflow",
            )
            return True

        mask_associations = self._mask_associations(workflow)
        if not mask_associations:
            log_info(
                _LOGGER,
                "Skipping dirty input mask preflight because workflow has no associated masks",
                workflow_id=workflow_id,
                skip_reason="no_associated_masks",
            )
            return True

        workflow_name = self._workflow_name_provider(workflow_id)
        projects_dir = self._projects_dir_provider()
        if not self._mask_update_signal_bound:
            log_error(
                _LOGGER,
                "Cannot flush dirty input masks because dirty-state source is unavailable",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                associated_mask_count=len(mask_associations),
                failure_reason="missing_dirty_state_source",
            )
            return False
        log_info(
            _LOGGER,
            "Pre-generation dirty mask flush starting",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            associated_mask_count=len(mask_associations),
        )

        all_flushed = True
        for association_key, mask_id in mask_associations.items():
            resolved_key = self._resolve_association_key(association_key)
            resolved_mask_id = self._dirty_tracker.resolve_mask_id(mask_id)
            if resolved_key is None or resolved_mask_id is None:
                log_error(
                    _LOGGER,
                    "Cannot flush dirty input mask because association state is invalid",
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    association_key=str(association_key),
                    mask_id=str(mask_id),
                    failure_reason="invalid_mask_association",
                )
                all_flushed = False
                continue
            cube_alias, node_name = resolved_key
            if not self._dirty_tracker.is_dirty(resolved_mask_id):
                log_debug(
                    _LOGGER,
                    "Skipping clean input mask during pre-generation flush",
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    cube_alias=cube_alias,
                    node_name=node_name,
                    mask_id=str(resolved_mask_id),
                    dirty=False,
                    flushed=False,
                    skip_reason="clean_mask",
                )
                continue
            if not self._mask_belongs_to_workflow_input(workflow, resolved_mask_id):
                log_error(
                    _LOGGER,
                    "Cannot flush dirty input mask because workflow state does not prove mask ownership",
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    cube_alias=cube_alias,
                    node_name=node_name,
                    mask_id=str(resolved_mask_id),
                    failure_reason="unproven_mask_ownership",
                )
                all_flushed = False
                continue
            flushed = self._persist_associated_mask(
                workflow=workflow,
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                projects_dir=projects_dir,
                cube_alias=cube_alias,
                node_name=node_name,
                mask_id=resolved_mask_id,
                reason="pre_generation_flush",
                refresh_picker=False,
            )
            all_flushed = all_flushed and flushed
        return all_flushed

    def handle_mask_save_completed(self, mask_id: object, path: str) -> None:
        """Clear dirty state when QPane reports a completed mask save."""

        resolved_mask_id = self._dirty_tracker.resolve_mask_id(mask_id)
        if resolved_mask_id is None:
            log_warning(
                _LOGGER,
                "Ignoring QPane mask save completion with invalid mask id",
                mask_id=str(mask_id),
                path=path,
            )
            return
        self._mark_persisted(resolved_mask_id, path=path, reason="pane_mask_saved")
        log_debug(
            _LOGGER,
            "Input mask save controller observed QPane maskSaved signal",
            mask_id=str(resolved_mask_id),
            path=path,
        )

    def handle_mask_updated(self, mask_id: object, rect: object = None) -> None:
        """Mark one mask dirty and debounce canonical save handling."""

        resolved_mask_id = self._dirty_tracker.mark_dirty(mask_id)
        if resolved_mask_id is None:
            log_warning(
                _LOGGER,
                "Input mask save controller ignored update without valid mask id",
                mask_id=str(mask_id),
                rect=str(rect),
            )
            return
        timer = self._save_timers.get(resolved_mask_id)
        created_timer = False
        if timer is None:
            timer = self._timer_factory(None)
            timer.setSingleShot(True)
            timer.timeout.connect(
                lambda mid=resolved_mask_id: self.handle_debounced_save_request(mid)
            )
            self._save_timers[resolved_mask_id] = timer
            created_timer = True
        debounce_ms = self._mask_autosave_debounce_ms()
        log_info(
            _LOGGER,
            "Input mask update scheduled debounced save",
            mask_id=str(resolved_mask_id),
            rect=str(rect),
            debounce_ms=debounce_ms,
            created_timer=created_timer,
        )
        timer.start(debounce_ms)

    def handle_debounced_save_request(self, mask_id: object) -> bool:
        """Persist one dirty associated mask after debounce expiry."""

        workflow_id = self._workflow_session_service.active_workflow_id
        workflow = self._workflow_session_service.workflows.get(workflow_id)
        resolved_mask_id = self._dirty_tracker.resolve_mask_id(mask_id)
        if workflow is None or resolved_mask_id is None:
            return False
        association_key = self._association_key_for_mask(workflow, resolved_mask_id)
        if association_key is None:
            log_debug(
                _LOGGER,
                "Ignoring debounced input mask save for unassociated mask",
                workflow_id=workflow_id,
                mask_id=str(resolved_mask_id),
            )
            return False
        if not self._dirty_tracker.is_dirty(resolved_mask_id):
            log_debug(
                _LOGGER,
                "Skipping debounced input mask save because mask is clean",
                workflow_id=workflow_id,
                mask_id=str(resolved_mask_id),
                dirty=False,
                flushed=False,
                skip_reason="clean_mask",
            )
            return True
        if not self._mask_belongs_to_workflow_input(workflow, resolved_mask_id):
            log_error(
                _LOGGER,
                "Cannot persist debounced input mask because workflow state does not prove mask ownership",
                workflow_id=workflow_id,
                mask_id=str(resolved_mask_id),
                failure_reason="unproven_mask_ownership",
            )
            return False
        workflow_name = self._workflow_name_provider(workflow_id)
        return self._persist_associated_mask(
            workflow=workflow,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            projects_dir=self._projects_dir_provider(),
            cube_alias=association_key[0],
            node_name=association_key[1],
            mask_id=resolved_mask_id,
            reason="debounced_save_request",
            refresh_picker=True,
        )

    def _bind_qpane_signals(self) -> None:
        """Connect QPane mask update and save signals to controller handlers."""

        controller = getattr(self._input_pane, "mask_controller", None)
        mask_updated = getattr(controller, "mask_updated", None)
        connect_mask_updated = getattr(mask_updated, "connect", None)
        if callable(connect_mask_updated):
            connect_mask_updated(self.handle_mask_updated)
            self._mask_update_signal_bound = True
            log_info(_LOGGER, "Input mask save controller bound mask_updated signal")
        else:
            log_warning(
                _LOGGER,
                "Input mask save controller could not bind mask_updated signal",
                has_controller=controller is not None,
            )

        mask_saved = getattr(self._input_pane, "maskSaved", None)
        connect_mask_saved = getattr(mask_saved, "connect", None)
        if callable(connect_mask_saved):
            connect_mask_saved(self.handle_mask_save_completed)
            log_info(_LOGGER, "Input mask save controller bound maskSaved signal")
        else:
            log_warning(
                _LOGGER,
                "Input mask save controller could not bind maskSaved signal",
            )

    def _persist_associated_mask(
        self,
        *,
        workflow: object,
        workflow_id: str,
        workflow_name: str,
        projects_dir: Path,
        cube_alias: str,
        node_name: str,
        mask_id: UUID,
        reason: str,
        refresh_picker: bool,
    ) -> bool:
        """Persist one dirty workflow-associated mask and update asset state."""

        path = self._resolve_mask_save_path(
            workflow=workflow,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            projects_dir=projects_dir,
            cube_alias=cube_alias,
            node_name=node_name,
            mask_id=mask_id,
        )
        if path is None:
            return False

        mask_image = self._mask_image(mask_id)
        if mask_image is None:
            log_error(
                _LOGGER,
                "Failed to persist dirty input mask because current pixels are unavailable",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=node_name,
                mask_id=str(mask_id),
                path=str(path),
                dirty=True,
                flushed=False,
                failure_reason="missing_mask_image",
            )
            return False

        save_mask_image = getattr(self._canvas_io_service, "save_mask_image", None)
        if not callable(save_mask_image):
            log_error(
                _LOGGER,
                "Failed to persist dirty input mask because save IO API is unavailable",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=node_name,
                mask_id=str(mask_id),
                path=str(path),
                dirty=True,
                flushed=False,
                failure_reason="missing_save_io_api",
            )
            return False
        try:
            saved = bool(save_mask_image(destination=path, image=mask_image))
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as error:
            log_error(
                _LOGGER,
                "Failed to persist dirty input mask because save IO raised",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=node_name,
                mask_id=str(mask_id),
                path=str(path),
                error=error,
                dirty=True,
                flushed=False,
                failure_reason="save_io_error",
            )
            return False
        if not saved:
            log_error(
                _LOGGER,
                "Failed to persist dirty input mask because save IO returned false",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=node_name,
                mask_id=str(mask_id),
                path=str(path),
                dirty=True,
                flushed=False,
                failure_reason="save_failed",
            )
            return False

        associate_project_input_mask = getattr(
            self._workflow_asset_service,
            "associate_project_input_mask",
            None,
        )
        if not callable(associate_project_input_mask):
            log_error(
                _LOGGER,
                "Failed to persist dirty input mask because asset association API is unavailable",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=node_name,
                mask_id=str(mask_id),
                path=str(path),
                dirty=True,
                flushed=False,
                failure_reason="missing_asset_association_api",
            )
            return False
        try:
            associated = bool(
                associate_project_input_mask(
                    workflow,
                    cube_alias=cube_alias,
                    node_name=node_name,
                    relative_path=path.name,
                )
            )
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            log_error(
                _LOGGER,
                "Failed to persist dirty input mask because asset association raised",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=node_name,
                mask_id=str(mask_id),
                path=str(path),
                error=error,
                dirty=True,
                flushed=False,
                failure_reason="asset_association_error",
            )
            return False
        if not associated:
            log_error(
                _LOGGER,
                "Failed to persist dirty input mask because asset association failed",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=node_name,
                mask_id=str(mask_id),
                path=str(path),
                dirty=True,
                flushed=False,
                failure_reason="asset_association_failed",
            )
            return False

        self._mark_persisted(mask_id, path=str(path), reason=reason)
        if refresh_picker and self._refresh_saved_mask is not None:
            self._refresh_saved_mask(cube_alias, node_name, str(path))
        log_debug(
            _LOGGER,
            "Persisted dirty input mask",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            cube_alias=cube_alias,
            node_name=node_name,
            mask_id=str(mask_id),
            path=str(path),
            dirty=True,
            flushed=True,
            reason=reason,
        )
        return True

    def _resolve_mask_save_path(
        self,
        *,
        workflow: object,
        workflow_id: str,
        workflow_name: str,
        projects_dir: Path,
        cube_alias: str,
        node_name: str,
        mask_id: UUID,
    ) -> Path | None:
        """Resolve the canonical graph-backed save path for one mask."""

        mask_filename = self._mask_filename(workflow, cube_alias, node_name)
        if not mask_filename:
            log_error(
                _LOGGER,
                "Failed to resolve dirty input mask path because graph buffer path is unavailable",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=node_name,
                mask_id=str(mask_id),
                dirty=True,
                flushed=False,
                failure_reason="missing_mask_filename",
            )
            return None
        try:
            return self._canvas_io_service.resolve_mask_save_path(
                workflow_name=workflow_name,
                mask_filename=mask_filename,
                projects_dir=projects_dir,
            )
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as error:
            log_error(
                _LOGGER,
                "Failed to resolve dirty input mask path",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=node_name,
                mask_id=str(mask_id),
                mask_filename=mask_filename,
                error=error,
                dirty=True,
                flushed=False,
                failure_reason="path_resolution_failed",
            )
            return None

    def _mark_persisted(self, mask_id: UUID, *, path: str, reason: str) -> None:
        """Clear dirty state and cancel any pending debounce for one mask."""

        self._dirty_tracker.mark_persisted(mask_id, path=path, reason=reason)
        timer = self._save_timers.pop(mask_id, None)
        if timer is not None:
            stop = getattr(timer, "stop", None)
            if callable(stop):
                stop()

    def _mask_image(self, mask_id: UUID) -> object | None:
        """Return non-null QPane mask image for one mask identifier."""

        catalog = getattr(self._input_pane, "catalog", None)
        if not callable(catalog):
            return None
        mask_catalog = catalog()
        mask_manager = (
            getattr(mask_catalog, "maskManager", lambda: None)()
            if mask_catalog is not None
            else None
        )
        get_layer = getattr(mask_manager, "get_layer", None)
        if not callable(get_layer):
            return None
        layer = get_layer(mask_id)
        if layer is None:
            return None
        mask_image = getattr(layer, "mask_image", None)
        is_null = getattr(mask_image, "isNull", None)
        if mask_image is None or (callable(is_null) and bool(is_null())):
            return None
        image: object = mask_image
        return image

    def _mask_autosave_debounce_ms(self) -> int:
        """Resolve QPane mask autosave debounce delay with a safe fallback."""

        settings = getattr(self._input_pane, "settings", None)
        delay = getattr(settings, "mask_autosave_debounce_ms", 2000)
        try:
            resolved = int(delay)
        except (TypeError, ValueError):
            resolved = 2000
        return max(0, resolved)

    @staticmethod
    def _mask_associations(workflow: object) -> Mapping[object, object]:
        """Return workflow mask associations when present and well-formed."""

        canvas = getattr(workflow, "canvas", None)
        associations = getattr(canvas, "mask_associations", {})
        return associations if isinstance(associations, Mapping) else {}

    @staticmethod
    def _mask_belongs_to_workflow_input(workflow: object, mask_id: UUID) -> bool:
        """Return whether workflow state proves a mask belongs to an input image."""

        canvas = getattr(workflow, "canvas", None)
        mask_to_image_map = getattr(canvas, "mask_to_image_map", {})
        if not isinstance(mask_to_image_map, Mapping):
            return False
        image_id = InputMaskDirtyTracker.resolve_mask_id(mask_to_image_map.get(mask_id))
        if image_id is None:
            return False
        input_key_map = getattr(canvas, "input_key_map", {})
        if not isinstance(input_key_map, Mapping):
            return False
        return any(
            InputMaskDirtyTracker.resolve_mask_id(value) == image_id
            for value in input_key_map.values()
        )

    @classmethod
    def _association_key_for_mask(
        cls, workflow: object, mask_id: UUID
    ) -> tuple[str, str] | None:
        """Return the workflow association key for one mask id."""

        for key, value in cls._mask_associations(workflow).items():
            resolved_mask_id = InputMaskDirtyTracker.resolve_mask_id(value)
            if resolved_mask_id == mask_id:
                return cls._resolve_association_key(key)
        return None

    @staticmethod
    def _resolve_association_key(key: object) -> tuple[str, str] | None:
        """Return valid cube and mask node names from an association key."""

        if not (isinstance(key, tuple) and len(key) == 2):
            return None
        cube_alias, node_name = key
        if not isinstance(cube_alias, str) or not isinstance(node_name, str):
            return None
        if not cube_alias or not node_name:
            return None
        return cube_alias, node_name

    @staticmethod
    def _mask_filename(workflow: object, cube_alias: str, node_name: str) -> str | None:
        """Return the current graph buffer image value for one mask node."""

        cubes = getattr(workflow, "cubes", {})
        cube_state = cubes.get(cube_alias) if isinstance(cubes, Mapping) else None
        buffer = getattr(cube_state, "buffer", {}) if cube_state is not None else {}
        nodes = buffer.get("nodes", {}) if isinstance(buffer, Mapping) else {}
        node = nodes.get(node_name, {}) if isinstance(nodes, Mapping) else {}
        inputs = node.get("inputs", {}) if isinstance(node, Mapping) else {}
        value = inputs.get("image") if isinstance(inputs, Mapping) else None
        return value if isinstance(value, str) and value else None


__all__ = ["InputMaskSaveController"]
