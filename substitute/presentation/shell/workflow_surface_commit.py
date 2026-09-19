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

"""Commit loaded workflow surfaces only after their authority is final."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from substitute.presentation.shell.cube_loader import CubeLoadUiCallbacks


class DeferredWorkflowSurfaceCommit:
    """Prevent provisional cube state from reaching editor and canvas views."""

    def __init__(
        self,
        *,
        callbacks: CubeLoadUiCallbacks,
        workflow_id: str,
        source_aliases: tuple[str, ...],
        install_authority: Callable[[], None],
        on_complete: Callable[[tuple[str, ...]], None],
    ) -> None:
        """Capture the final authority transition and ordered projection boundary."""

        self._callbacks = callbacks
        self._workflow_id = workflow_id
        self._source_aliases = source_aliases
        self._install_authority = install_authority
        self._on_complete = on_complete
        self._resolved_aliases: dict[str, str | None] = {}
        self._finished = False
        self._loading_callbacks = replace(
            callbacks,
            materialize_loaded_cube_input_canvas=self._suppress_materialization,
            refresh_workflow_after_cube_load=self._suppress_workflow_refresh,
            refresh_loaded_cube_surface=(
                self._suppress_surface_refresh
                if callbacks.refresh_loaded_cube_surface is not None
                else None
            ),
            refresh_workflow_after_cube_load_async=(
                self._suppress_workflow_refresh_async
                if callbacks.refresh_workflow_after_cube_load_async is not None
                else None
            ),
            refresh_loaded_cube_surface_async=(
                self._suppress_surface_refresh_async
                if callbacks.refresh_loaded_cube_surface_async is not None
                else None
            ),
        )

    @property
    def loading_callbacks(self) -> CubeLoadUiCallbacks:
        """Return callbacks that withhold provisional editor and canvas projection."""

        return self._loading_callbacks

    def record_loaded(self, source_alias: str, resolved_alias: str | None) -> None:
        """Record one terminal cube load and commit once every load has settled."""

        if self._finished or source_alias in self._resolved_aliases:
            return
        self._resolved_aliases[source_alias] = resolved_alias
        if len(self._resolved_aliases) != len(self._source_aliases):
            return
        projected_aliases = tuple(
            resolved
            for alias in self._source_aliases
            if (resolved := self._resolved_aliases.get(alias)) is not None
        )
        if len(projected_aliases) == len(self._source_aliases):
            self._install_authority()
        self._project_next(projected_aliases, 0)

    def _project_next(self, aliases: tuple[str, ...], index: int) -> None:
        """Project one final cube surface per GUI turn in canonical order."""

        if index >= len(aliases):
            self._finished = True
            self._on_complete(aliases)
            return
        alias = aliases[index]

        def materialize_and_continue(*_args: object) -> None:
            """Materialize masks after the matching canonical editor surface exists."""

            self._callbacks.materialize_loaded_cube_input_canvas(
                self._workflow_id,
                alias,
            )
            self._callbacks.schedule_next_gui_turn(
                lambda: self._project_next(aliases, index + 1)
            )

        refresh_surface_async = self._callbacks.refresh_loaded_cube_surface_async
        if refresh_surface_async is not None:
            refresh_surface_async(
                self._workflow_id,
                alias,
                materialize_and_continue,
                wait_for_complete=True,
            )
            return
        refresh_workflow_async = self._callbacks.refresh_workflow_after_cube_load_async
        if refresh_workflow_async is not None:
            refresh_workflow_async(
                self._workflow_id,
                alias,
                materialize_and_continue,
            )
            return
        refresh_surface = self._callbacks.refresh_loaded_cube_surface
        if refresh_surface is not None:
            refresh_surface(self._workflow_id, alias)
        else:
            self._callbacks.refresh_workflow_after_cube_load(self._workflow_id, alias)
        materialize_and_continue()

    @staticmethod
    def _suppress_materialization(_workflow_id: str, _alias: str) -> None:
        """Withhold Input materialization until final graph authority is installed."""

    @staticmethod
    def _suppress_workflow_refresh(_workflow_id: str, _alias: str) -> None:
        """Withhold full editor projection during provisional cube loading."""

    @staticmethod
    def _suppress_surface_refresh(_workflow_id: str, _alias: str) -> bool:
        """Report a withheld provisional surface as a completed load phase."""

        return True

    @staticmethod
    def _suppress_workflow_refresh_async(
        _workflow_id: str,
        _alias: str,
        on_complete: Callable[[], None],
    ) -> None:
        """Complete a withheld async full refresh without publishing a surface."""

        on_complete()

    @staticmethod
    def _suppress_surface_refresh_async(
        _workflow_id: str,
        _alias: str,
        on_complete: Callable[[bool], None],
        **_kwargs: object,
    ) -> None:
        """Complete a withheld async silent refresh without publishing a surface."""

        on_complete(True)


__all__ = ["DeferredWorkflowSurfaceCommit"]
