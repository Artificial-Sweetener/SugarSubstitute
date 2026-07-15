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

"""Verify projected widget builder behavior and ownership boundaries."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from substitute.presentation.editor.panel.projected_widget_builder import (
    ProjectedWidgetBuilder,
)
from substitute.presentation.editor.panel.projection_build_registry import (
    CubeSectionBuildReuseDecision,
)
from substitute.presentation.editor.panel.projection_models import ProjectedCubeBuild
from substitute.presentation.editor.panel.projection_session import (
    ActiveProjectionSession,
    PendingInsertCompletion,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILDER_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projected_widget_builder.py"
)
COORDINATOR_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_coordinator.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.editor.panel.projection_coordinator",
)


class _Widget:
    """Record widget lifecycle calls used by projected builder tests."""

    def __init__(self, label: str = "widget") -> None:
        """Create empty call records."""

        self.label = label
        self.parents: list[object | None] = []
        self.deleted = 0
        self.visible_changes: list[bool] = []
        self.updates_enabled: list[bool] = []

    def hide(self) -> None:
        """Record hidden-build visibility preparation."""

        self.visible_changes.append(False)

    def setUpdatesEnabled(self, enabled: bool) -> None:  # noqa: N802
        """Record update-suppression changes."""

        self.updates_enabled.append(enabled)

    def setParent(self, parent: object | None) -> None:  # noqa: N802
        """Record detach calls."""

        self.parents.append(parent)

    def deleteLater(self) -> None:  # noqa: N802
        """Record deferred deletion calls."""

        self.deleted += 1


class _BuildSession:
    """Hold the widget produced by a staged cube-section build."""

    def __init__(self, widget: _Widget) -> None:
        """Store the final widget."""

        self.widget = widget


class _Panel:
    """Provide panel widget construction collaborators for builder tests."""

    def __init__(self) -> None:
        """Create empty panel state and build records."""

        self.cube_widgets: dict[str, object] = {}
        self.cube_sections: dict[str, object] = {}
        self.built_sync: list[str] = []
        self.built_hidden: list[str] = []
        self.built_errors: list[str] = []
        self.next_widget = _Widget("next")

    def _begin_build_cube_widget(self, cube_alias: str, _cube_state: object) -> object:
        """Create one staged build session."""

        self.built_hidden.append(cube_alias)
        return _BuildSession(self.next_widget)

    def _build_cube_widget(self, cube_alias: str, _cube_state: object) -> object:
        """Create one synchronous cube widget."""

        self.built_sync.append(cube_alias)
        return self.next_widget

    def _build_error_cube_widget(self, cube_alias: str, _cube_state: object) -> object:
        """Create one error cube widget."""

        self.built_errors.append(cube_alias)
        return self.next_widget


class _RuntimeIssues:
    """Record aliases treated as runtime-error cubes."""

    def __init__(self, errored_aliases: set[str] | None = None) -> None:
        """Store aliases that should render error widgets."""

        self._errored_aliases = errored_aliases or set()

    def is_errored_cube(self, cube_alias: str) -> bool:
        """Return whether the alias is currently errored."""

        return cube_alias in self._errored_aliases


class _RuntimeIssueProjection:
    """Provide explicit runtime issue widget decisions for builder tests."""

    def __init__(
        self,
        panel: _Panel,
        *,
        runtime_issues: _RuntimeIssues | None = None,
    ) -> None:
        """Store panel and runtime issue collaborators."""

        self._panel = panel
        self._runtime_issues = runtime_issues or _RuntimeIssues()

    def should_replace_visible_widget_for_runtime_issue(
        self,
        cube_alias: str,
        widget: object,
    ) -> bool:
        """Return whether an existing widget must be replaced by an error widget."""

        if not self._runtime_issues.is_errored_cube(cube_alias):
            return False
        issue_severity = getattr(widget, "issueSeverity", None)
        return (issue_severity() if callable(issue_severity) else None) != "error"

    def build_error_widget_if_required(
        self,
        cube_alias: str,
        cube_state: object,
    ) -> object | None:
        """Build an error widget when runtime issues require it."""

        if not self._runtime_issues.is_errored_cube(cube_alias):
            return None
        return self._panel._build_error_cube_widget(cube_alias, cube_state)


class _BuildRegistry:
    """Record projected build-registry interactions."""

    def __init__(self) -> None:
        """Create default reusable decisions and empty call records."""

        self.reuse_decision_result = CubeSectionBuildReuseDecision(
            can_reuse=True,
            record_present=True,
            record_state="complete",
            active_token=None,
            definition_identity=None,
        )
        self.reuse_calls: list[tuple[str, object, object]] = []
        self.start_calls: list[dict[str, object]] = []
        self.adopt_calls: list[dict[str, object]] = []
        self.next_token = object()

    def reuse_decision(
        self,
        alias: str,
        widget: object,
        definition_identity: object,
    ) -> CubeSectionBuildReuseDecision:
        """Record a reuse-decision request and return the configured result."""

        self.reuse_calls.append((alias, widget, definition_identity))
        return self.reuse_decision_result

    def start(self, **kwargs: object) -> object:
        """Record an active build registration."""

        self.start_calls.append(kwargs)
        return self.next_token

    def adopt_complete(self, **kwargs: object) -> None:
        """Record a complete widget adoption."""

        self.adopt_calls.append(kwargs)


class _CompletionRegistry:
    """Record completion-registry interactions for projected builder tests."""

    def __init__(self) -> None:
        """Create empty claim records."""

        self.claimed: list[dict[str, object]] = []

    def claim_pending_insert_for_projection(
        self,
        *,
        workflow_id: str,
        cube_alias: str,
        token: object | None,
        reason: str,
        projection_session: ActiveProjectionSession,
    ) -> PendingInsertCompletion | None:
        """Record active insert-completion transfer to full projection."""

        self.claimed.append(
            {
                "workflow_id": workflow_id,
                "cube_alias": cube_alias,
                "token": token,
                "reason": reason,
                "projection_session": projection_session,
            }
        )
        return None


class _Lifecycle:
    """Record lifecycle cleanup interactions for projected builder tests."""

    def __init__(self, panel: _Panel) -> None:
        """Store panel state and cleanup records."""

        self._panel = panel
        self.discarded: list[tuple[str, str]] = []
        self.cleared_aliases: list[str] = []

    def discard_cube_widget(self, cube_alias: str, *, reason: str) -> None:
        """Record discarded visible widgets and remove them from panel maps."""

        self.discarded.append((cube_alias, reason))
        self._panel.cube_widgets.pop(cube_alias, None)
        self._panel.cube_sections.pop(cube_alias, None)

    def clear_alias_scoped_panel_registries(self, cube_alias: str) -> None:
        """Record alias-scoped registry cleanup."""

        self.cleared_aliases.append(cube_alias)


class _Coordinator:
    """Provide the narrow coordinator port required by the builder."""

    def __init__(
        self,
        panel: _Panel,
        *,
        runtime_issues: _RuntimeIssues | None = None,
        build_registry: _BuildRegistry | None = None,
    ) -> None:
        """Store projected-builder collaborators and cleanup records."""

        self._panel = panel
        self.runtime_issue_projection = _RuntimeIssueProjection(
            panel,
            runtime_issues=runtime_issues,
        )
        self._build_registry = build_registry or _BuildRegistry()
        self._projection_completions = _CompletionRegistry()
        self._projection_lifecycle = _Lifecycle(panel)


def _projected_widget_builder(coordinator: _Coordinator) -> ProjectedWidgetBuilder:
    """Return a projected widget builder wired to explicit runtime issue decisions."""

    return ProjectedWidgetBuilder(
        panel=coordinator._panel,
        build_registry=coordinator._build_registry,
        projection_completions=coordinator._projection_completions,
        projection_lifecycle=coordinator._projection_lifecycle,
        runtime_issue_projection=coordinator.runtime_issue_projection,
    )


def _imported_module_names(path: Path) -> set[str]:
    """Return imported module names from one Python source file."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def _active_projection_session() -> ActiveProjectionSession:
    """Return a minimal active full-projection session for builder tests."""

    return ActiveProjectionSession(
        workflow_id="workflow-a",
        aliases={"Cube"},
        token=object(),
        claimed_completions=[],
        projection_completions=[],
    )


def test_begin_or_build_cube_widget_starts_hidden_build() -> None:
    """Builder should start staged builds and prepare final widgets as hidden."""

    panel = _Panel()
    coordinator = _Coordinator(panel)
    builder = _projected_widget_builder(coordinator)

    widget, projected_build = builder.begin_or_build_cube_widget(
        "Cube",
        SimpleNamespace(buffer={}),
        workflow_id="workflow-a",
        snapshot_identity="snapshot-a",
    )

    assert widget is None
    assert projected_build is not None
    assert projected_build.final_widget is panel.next_widget
    assert projected_build.token is coordinator._build_registry.next_token
    assert panel.built_hidden == ["Cube"]
    assert panel.next_widget.updates_enabled == [False]
    assert panel.next_widget.visible_changes == [False]
    assert coordinator._build_registry.start_calls[0]["alias"] == "Cube"


def test_build_ordered_widgets_replaces_stale_widget_and_claims_insert() -> None:
    """Stale visible widgets should be discarded and active insert tokens claimed."""

    panel = _Panel()
    old_widget = _Widget("old")
    panel.cube_widgets["Cube"] = old_widget
    panel.cube_sections["Cube"] = old_widget
    stale_token = object()
    registry = _BuildRegistry()
    registry.reuse_decision_result = CubeSectionBuildReuseDecision(
        can_reuse=False,
        record_present=True,
        record_state="building",
        active_token=stale_token,
        definition_identity=None,
    )
    coordinator = _Coordinator(panel, build_registry=registry)
    builder = _projected_widget_builder(coordinator)
    projection_session = _active_projection_session()

    ordered_widgets, projected_builds = builder.build_ordered_widgets(
        [("Cube", SimpleNamespace(buffer={}))],
        workflow_id="workflow-a",
        snapshot_identity="snapshot-a",
        projection_session=projection_session,
    )

    assert ordered_widgets == []
    assert len(projected_builds) == 1
    assert coordinator._projection_completions.claimed == [
        {
            "workflow_id": "workflow-a",
            "cube_alias": "Cube",
            "token": stale_token,
            "reason": "stale_projection",
            "projection_session": projection_session,
        }
    ]
    assert coordinator._projection_lifecycle.discarded == [("Cube", "stale_projection")]


def test_build_ordered_widgets_uses_error_widget_for_errored_cube() -> None:
    """Errored cube aliases should build complete error widgets without staging."""

    panel = _Panel()
    coordinator = _Coordinator(panel, runtime_issues=_RuntimeIssues({"Cube"}))
    builder = _projected_widget_builder(coordinator)

    ordered_widgets, projected_builds = builder.build_ordered_widgets(
        [("Cube", SimpleNamespace(buffer={}))],
        workflow_id="workflow-a",
        snapshot_identity="snapshot-a",
        projection_session=_active_projection_session(),
    )

    assert ordered_widgets == [("Cube", panel.next_widget)]
    assert projected_builds == []
    assert panel.built_errors == ["Cube"]
    assert coordinator._build_registry.adopt_calls[0]["alias"] == "Cube"


def test_discard_cancelled_projected_build_detaches_unrevealed_widget() -> None:
    """Cancelled projected widgets should be detached when not already visible."""

    panel = _Panel()
    coordinator = _Coordinator(panel)
    builder = _projected_widget_builder(coordinator)
    widget = _Widget("cancelled")
    projected_build = ProjectedCubeBuild(
        cube_alias="Cube",
        final_widget=widget,
        build_session=object(),
        started_at=0.0,
        token=object(),
    )

    builder.discard_cancelled_projected_build(
        projected_build,
        workflow_id="workflow-a",
        reason="superseded",
    )

    assert coordinator._projection_lifecycle.cleared_aliases == ["Cube"]
    assert widget.parents == [None]
    assert widget.deleted == 1


def test_projected_widget_builder_does_not_import_coordinator_or_fluent() -> None:
    """Projected widget building should not depend on the coordinator monolith."""

    imports = _imported_module_names(BUILDER_SOURCE)

    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in imports
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    )
    assert "_runtime_issues" not in BUILDER_SOURCE.read_text(encoding="utf-8")
    assert "_build_error_cube_widget" not in BUILDER_SOURCE.read_text(encoding="utf-8")
    assert "_coordinator" not in BUILDER_SOURCE.read_text(encoding="utf-8")


def test_projection_coordinator_no_longer_defines_projected_builder_methods() -> None:
    """Moved projected-widget methods should not return to the coordinator."""

    tree = ast.parse(COORDINATOR_SOURCE.read_text(encoding="utf-8"))
    class_methods: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_methods[node.name] = {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }

    coordinator_methods = class_methods["EditorPanelProjectionCoordinator"]
    assert "EditorHiddenBuildAndInsertPipeline" not in class_methods
    assert "_build_ordered_widgets" not in coordinator_methods
    assert "_begin_or_build_cube_widget" not in coordinator_methods
    assert "_discard_cancelled_projected_build" not in coordinator_methods
    assert "_claim_pending_insert_completion_for_projection" not in coordinator_methods
    assert "_discard_cube_widget" not in coordinator_methods
    assert "_clear_alias_scoped_panel_registries" not in coordinator_methods
