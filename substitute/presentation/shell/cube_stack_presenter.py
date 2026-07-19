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

"""Apply complete cube-stack tab presentation from workflow cube state."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from substitute.application.cubes import (
    build_cube_stack_tooltip_for_state,
    build_cube_tab_presentation,
)
from substitute.application.workflows import WorkflowIssueState
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("presentation.shell.cube_stack_presenter")


class CubeTabItemProtocol(Protocol):
    """Describe mutable route-key behavior for one cube-stack tab item."""

    def routeKey(self) -> str:
        """Return the tab route key."""

    def setRouteKey(self, key: str) -> None:
        """Replace the tab route key."""


class CubeStackProtocol(Protocol):
    """Describe the cube-stack operations needed for complete presentation."""

    itemMap: MutableMapping[str, CubeTabItemProtocol]

    def clear(self) -> None:
        """Remove all tabs."""

    def count(self) -> int:
        """Return tab count."""

    def insertTab(
        self,
        index: int,
        *,
        routeKey: str,
        text: str,
        icon: object | None = None,
    ) -> object:
        """Insert one tab."""

    def setCurrentIndex(self, index: int) -> None:
        """Select one tab index."""

    def setTabIcon(self, index: int, icon: object) -> None:
        """Set one tab icon."""

    def setTabPresentation(
        self,
        index: int,
        *,
        primary_text: str,
        secondary_text: str,
        tooltip_text: str,
    ) -> None:
        """Set one tab label, secondary label, and tooltip."""

    def setTabIssueSeverity(self, route_key: str, severity: str | None) -> None:
        """Set one tab issue severity by route key."""

    def setTabBypassed(self, index: int, bypassed: bool) -> None:
        """Set one tab cube-level bypass presentation state."""

    def tabItem(self, index: int) -> CubeTabItemProtocol:
        """Return one tab item."""


class CubeIconFactoryProtocol(Protocol):
    """Resolve cube metadata into a presentation-compatible icon object."""

    def icon_for_cube(
        self,
        *,
        cube_id: str,
        display_name: str,
        icon: object | None,
        catalog_revision: str = "",
        cube_content_hash: str = "",
        render_size: int | None = None,
    ) -> object:
        """Return a concrete icon object for one cube tab."""


@dataclass(frozen=True)
class CubeTabIconResult:
    """Describe the icon selected for one cube tab."""

    icon: object
    used_fallback_icon: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CubeTabPresentationResult:
    """Describe presentation work applied to one cube-stack tab."""

    applied_icon: bool
    used_fallback_icon: bool
    applied_presentation: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CubeStackPresentationResult:
    """Describe a complete cube-stack rebuild operation."""

    inserted_count: int
    selected_index: int | None
    tab_results: tuple[CubeTabPresentationResult, ...]
    warnings: tuple[str, ...] = ()


class CubeTabIconResolver:
    """Resolve cube tab icons while always returning an immediate fallback."""

    def __init__(
        self,
        *,
        cube_icon_factory: CubeIconFactoryProtocol | None,
        fallback_icon: object | None = None,
    ) -> None:
        """Store icon dependencies for deterministic tab icon resolution."""

        self._cube_icon_factory = cube_icon_factory
        self._fallback_icon = (
            fallback_icon if fallback_icon is not None else _default_cube_icon()
        )

    def icon_for_cube_state(
        self,
        cube_state: object,
        *,
        workflow_id: str,
        cube_alias: str,
    ) -> CubeTabIconResult:
        """Return a resolved cube icon or the deterministic fallback icon."""

        cube_id = str(getattr(cube_state, "cube_id", cube_alias))
        display_name = str(getattr(cube_state, "display_name", cube_alias))
        return self.icon_for_cube_source(
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            cube_id=cube_id,
            display_name=display_name,
            icon=_cube_ui_value(cube_state, "cube_icon"),
            catalog_revision=_cube_ui_text(cube_state, "catalog_revision"),
            content_hash=_cube_ui_text(cube_state, "content_hash"),
        )

    def icon_for_cube_source(
        self,
        *,
        workflow_id: str,
        cube_alias: str,
        cube_id: str,
        display_name: str,
        icon: object | None,
        catalog_revision: str,
        content_hash: str,
    ) -> CubeTabIconResult:
        """Return a resolved source icon or the deterministic fallback icon."""

        if self._cube_icon_factory is None:
            warning = "missing_cube_icon_factory"
            log_warning(
                _LOGGER,
                "Fell back to default cube-stack icon because factory was missing",
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                cube_id=cube_id,
            )
            return CubeTabIconResult(
                icon=self._fallback_icon,
                used_fallback_icon=True,
                warnings=(warning,),
            )

        try:
            resolved_icon = self._cube_icon_factory.icon_for_cube(
                cube_id=cube_id,
                display_name=display_name,
                icon=icon,
                catalog_revision=catalog_revision,
                cube_content_hash=content_hash,
            )
        except (RuntimeError, TypeError, ValueError) as error:
            warning = "cube_icon_resolution_failed"
            log_warning(
                _LOGGER,
                "Fell back to default cube-stack icon after resolution failure",
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                cube_id=cube_id,
                error=repr(error),
            )
            return CubeTabIconResult(
                icon=self._fallback_icon,
                used_fallback_icon=True,
                warnings=(warning,),
            )

        return CubeTabIconResult(icon=resolved_icon, used_fallback_icon=False)


class CubeStackPresenter:
    """Apply complete cube-stack tab presentation from workflow cube state."""

    def __init__(self, *, icon_resolver: CubeTabIconResolver) -> None:
        """Store presentation dependencies."""

        self._icon_resolver = icon_resolver

    def rebuild_stack(
        self,
        cube_stack: CubeStackProtocol,
        *,
        workflow_id: str,
        workflow: object,
        active_cube_alias: str | None,
        issue_state: WorkflowIssueState | None = None,
    ) -> CubeStackPresentationResult:
        """Clear and rebuild one cube stack with complete tab presentation."""

        cubes = getattr(workflow, "cubes", {})
        stack_order = tuple(
            str(alias) for alias in getattr(workflow, "stack_order", ())
        )
        if not isinstance(cubes, Mapping):
            warning = "invalid_workflow_cubes"
            log_warning(
                _LOGGER,
                "Skipped cube-stack rebuild because workflow cubes were invalid",
                workflow_id=workflow_id,
                cube_state_type=type(cubes).__name__,
            )
            return CubeStackPresentationResult(
                inserted_count=0,
                selected_index=None,
                tab_results=(),
                warnings=(warning,),
            )

        cube_stack.clear()
        warnings: list[str] = []
        tab_results: list[CubeTabPresentationResult] = []
        inserted_aliases: list[str] = []
        for cube_alias in stack_order:
            cube_state = cubes.get(cube_alias)
            if cube_state is None:
                warnings.append("missing_cube_state")
                log_warning(
                    _LOGGER,
                    "Skipped missing cube while rebuilding cube stack",
                    workflow_id=workflow_id,
                    cube_alias=cube_alias,
                )
                continue
            tab_index = cube_stack.count()
            self._insert_tab(
                cube_stack,
                tab_index,
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                cube_state=cube_state,
            )
            tab_result = self.apply_tab(
                cube_stack,
                tab_index,
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                cube_state=cube_state,
                issue_state=issue_state,
            )
            tab_results.append(tab_result)
            warnings.extend(tab_result.warnings)
            inserted_aliases.append(cube_alias)

        selected_index = self._select_rebuilt_tab(
            cube_stack,
            inserted_aliases=tuple(inserted_aliases),
            active_cube_alias=active_cube_alias,
        )
        log_info(
            _LOGGER,
            "Rebuilt cube-stack presentation",
            workflow_id=workflow_id,
            inserted_count=len(inserted_aliases),
            selected_index=selected_index,
            warning_count=len(warnings),
        )
        return CubeStackPresentationResult(
            inserted_count=len(inserted_aliases),
            selected_index=selected_index,
            tab_results=tuple(tab_results),
            warnings=tuple(warnings),
        )

    def apply_tab(
        self,
        cube_stack: CubeStackProtocol,
        tab_index: int,
        *,
        workflow_id: str,
        cube_alias: str,
        cube_state: object,
        issue_state: WorkflowIssueState | None = None,
    ) -> CubeTabPresentationResult:
        """Apply route key, labels, tooltip, and icon for one cube tab."""

        warnings: list[str] = []
        self._apply_route_key(cube_stack, tab_index, cube_alias, warnings)
        presentation = build_cube_tab_presentation(
            alias=cube_alias,
            cube_id=str(getattr(cube_state, "cube_id", cube_alias)),
            version=str(getattr(cube_state, "version", "")),
        )
        tooltip_text = build_cube_stack_tooltip_for_state(
            alias=cube_alias,
            cube_state=cube_state,
        )
        applied_presentation = self._apply_presentation(
            cube_stack,
            tab_index,
            primary_text=presentation.primary_text,
            secondary_text=presentation.secondary_text,
            tooltip_text=tooltip_text,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            warnings=warnings,
        )
        icon_result = self._icon_resolver.icon_for_cube_state(
            cube_state,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
        )
        warnings.extend(icon_result.warnings)
        applied_icon = self._apply_icon(
            cube_stack,
            tab_index,
            icon=icon_result.icon,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            warnings=warnings,
        )
        self._apply_issue_state(
            cube_stack,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            issue_state=issue_state,
        )
        self._apply_bypass_state(
            cube_stack,
            tab_index=tab_index,
            cube_state=cube_state,
        )
        return CubeTabPresentationResult(
            applied_icon=applied_icon,
            used_fallback_icon=icon_result.used_fallback_icon,
            applied_presentation=applied_presentation,
            warnings=tuple(warnings),
        )

    def append_cube(
        self,
        cube_stack: CubeStackProtocol,
        *,
        workflow_id: str,
        cube_alias: str,
        cube_state: object,
        issue_state: WorkflowIssueState | None = None,
        select: bool = True,
    ) -> CubeTabPresentationResult:
        """Append and fully present one cube card at the end of a stack."""

        tab_index = cube_stack.count()
        self._insert_tab(
            cube_stack,
            tab_index,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            cube_state=cube_state,
        )
        result = self.apply_tab(
            cube_stack,
            tab_index,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            cube_state=cube_state,
            issue_state=issue_state,
        )
        if select:
            cube_stack.setCurrentIndex(tab_index)
        return result

    def promote_placeholder(
        self,
        cube_stack: CubeStackProtocol,
        tab_index: int,
        *,
        workflow_id: str,
        cube_alias: str,
        cube_state: object,
        select: bool = True,
    ) -> CubeTabPresentationResult:
        """Convert one loading placeholder into a complete cube tab."""

        result = self.apply_tab(
            cube_stack,
            tab_index,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            cube_state=cube_state,
            issue_state=None,
        )
        if select:
            cube_stack.setCurrentIndex(tab_index)
        return result

    def _insert_tab(
        self,
        cube_stack: CubeStackProtocol,
        tab_index: int,
        *,
        workflow_id: str,
        cube_alias: str,
        cube_state: object,
    ) -> None:
        """Insert one tab before applying complete presentation."""

        presentation = build_cube_tab_presentation(
            alias=cube_alias,
            cube_id=str(getattr(cube_state, "cube_id", cube_alias)),
            version=str(getattr(cube_state, "version", "")),
        )
        del workflow_id
        cube_stack.insertTab(
            tab_index,
            routeKey=cube_alias,
            text=presentation.primary_text,
        )

    def _select_rebuilt_tab(
        self,
        cube_stack: CubeStackProtocol,
        *,
        inserted_aliases: Sequence[str],
        active_cube_alias: str | None,
    ) -> int | None:
        """Apply restored selection and return the selected index."""

        if active_cube_alias in inserted_aliases:
            selected_index = inserted_aliases.index(cast(str, active_cube_alias))
            cube_stack.setCurrentIndex(selected_index)
            return selected_index
        if cube_stack.count() > 0:
            selected_index = cube_stack.count() - 1
            cube_stack.setCurrentIndex(selected_index)
            return selected_index
        return None

    def _apply_route_key(
        self,
        cube_stack: CubeStackProtocol,
        tab_index: int,
        cube_alias: str,
        warnings: list[str],
    ) -> None:
        """Ensure the tab item and item map use the cube alias route key."""

        tab_item_at = getattr(cube_stack, "tabItem", None)
        if not callable(tab_item_at):
            warnings.append("tab_item_unavailable")
            return
        try:
            tab_item = tab_item_at(tab_index)
        except (IndexError, TypeError, ValueError):
            warnings.append("tab_item_unavailable")
            return
        route_key = getattr(tab_item, "routeKey", None)
        set_route_key = getattr(tab_item, "setRouteKey", None)
        if not callable(route_key) or not callable(set_route_key):
            warnings.append("tab_item_route_key_unavailable")
            return
        old_key = route_key()
        if old_key == cube_alias:
            return
        item_map = getattr(cube_stack, "itemMap", None)
        if isinstance(item_map, MutableMapping):
            item_map.pop(old_key, None)
        set_route_key(cube_alias)
        if isinstance(item_map, MutableMapping):
            item_map[cube_alias] = tab_item

    def _apply_presentation(
        self,
        cube_stack: CubeStackProtocol,
        tab_index: int,
        *,
        primary_text: str,
        secondary_text: str,
        tooltip_text: str,
        workflow_id: str,
        cube_alias: str,
        warnings: list[str],
    ) -> bool:
        """Apply rich label and tooltip presentation when the widget supports it."""

        set_presentation = getattr(cube_stack, "setTabPresentation", None)
        if callable(set_presentation):
            set_presentation(
                tab_index,
                primary_text=primary_text,
                secondary_text=secondary_text,
                tooltip_text=tooltip_text,
            )
            return True

        warnings.append("set_tab_presentation_unavailable")
        log_warning(
            _LOGGER,
            "Cube-stack widget cannot apply rich tab presentation",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
        )
        set_text = getattr(cube_stack, "setTabText", None)
        if callable(set_text):
            set_text(tab_index, primary_text)
        return False

    def _apply_icon(
        self,
        cube_stack: CubeStackProtocol,
        tab_index: int,
        *,
        icon: object,
        workflow_id: str,
        cube_alias: str,
        warnings: list[str],
    ) -> bool:
        """Apply one mandatory tab icon when the widget supports it."""

        set_tab_icon = getattr(cube_stack, "setTabIcon", None)
        if callable(set_tab_icon):
            set_tab_icon(tab_index, icon)
            return True

        warnings.append("set_tab_icon_unavailable")
        log_warning(
            _LOGGER,
            "Cube-stack widget cannot apply mandatory tab icon",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
        )
        return False

    def _apply_issue_state(
        self,
        cube_stack: CubeStackProtocol,
        *,
        workflow_id: str,
        cube_alias: str,
        issue_state: WorkflowIssueState | None,
    ) -> None:
        """Apply cube issue severity to the stack when issue state is available."""

        set_issue = getattr(cube_stack, "setTabIssueSeverity", None)
        if not callable(set_issue):
            return
        severity = (
            "error"
            if issue_state is not None
            and issue_state.has_error(workflow_id, cube_alias)
            else None
        )
        set_issue(cube_alias, severity)

    def _apply_bypass_state(
        self,
        cube_stack: CubeStackProtocol,
        *,
        tab_index: int,
        cube_state: object,
    ) -> None:
        """Apply cube bypass state to the stack when the widget supports it."""

        set_bypassed = getattr(cube_stack, "setTabBypassed", None)
        if callable(set_bypassed):
            set_bypassed(tab_index, getattr(cube_state, "bypassed", False) is True)
        set_output_persistence = getattr(
            cube_stack, "setTabOutputPersistenceEnabled", None
        )
        if callable(set_output_persistence):
            set_output_persistence(
                tab_index,
                getattr(cube_state, "output_persistence_enabled", True) is not False,
            )


def _cube_ui_value(cube_state: object, key: str) -> object | None:
    """Return one cube UI payload value when present."""

    ui_payload = getattr(cube_state, "ui", None)
    if isinstance(ui_payload, Mapping):
        return ui_payload.get(key)
    return None


def _cube_ui_text(cube_state: object, key: str) -> str:
    """Return one cube UI payload string when present."""

    value = _cube_ui_value(cube_state, key)
    return value if isinstance(value, str) else ""


def _default_cube_icon() -> object:
    """Return the deterministic app cube icon used for fallback presentation."""

    from substitute.presentation.resources.app_icon import AppIcon

    return AppIcon.CUBE_20_FILLED


__all__ = [
    "CubeIconFactoryProtocol",
    "CubeStackPresentationResult",
    "CubeStackPresenter",
    "CubeStackProtocol",
    "CubeTabIconResolver",
    "CubeTabIconResult",
    "CubeTabPresentationResult",
]
