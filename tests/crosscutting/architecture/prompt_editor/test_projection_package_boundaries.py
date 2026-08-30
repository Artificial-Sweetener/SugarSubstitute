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

"""Keep prompt projection values and package boundaries focused."""

from __future__ import annotations

import ast

from .inventory import (
    PROJECT_ROOT,
    PROMPT_DOMAIN_ROOT,
    PROMPT_APPLICATION_ROOT,
    PROMPT_PRESENTATION_ROOT,
    _TARGET_DOMAIN_PACKAGES,
    _TARGET_APPLICATION_PACKAGES,
    prompt_editor_architecture_inventory,
)
from .source_shape import (
    immediate_package_names,
    immediate_python_files,
    protocol_class_count,
)


def test_region_chrome_consumes_immutable_output_without_a_host_protocol() -> None:
    """Keep separator preparation keyed by layout values, not broad hosts."""

    source_path = PROMPT_PRESENTATION_ROOT / "projection" / "region_chrome.py"
    architecture = prompt_editor_architecture_inventory()
    graph = architecture.graph
    module_name = (
        "substitute.presentation.editor.prompt_editor.projection.region_chrome"
    )

    assert (
        "substitute.presentation.editor.prompt_editor.projection.layout_engine"
        not in graph[module_name]
    )
    assert protocol_class_count(source_path) == 0


def test_projection_values_have_focused_qt_free_core_owners() -> None:
    """Keep immutable projection values below layout without a compatibility barrel."""

    projection_root = PROMPT_PRESENTATION_ROOT / "core" / "projection"
    assert immediate_python_files(projection_root) == {
        "__init__.py",
        "caret.py",
        "document.py",
        "mapping.py",
        "runs.py",
        "tokens.py",
    }
    assert not (PROMPT_PRESENTATION_ROOT / "projection" / "model.py").exists()

    package_tree = ast.parse(
        (projection_root / "__init__.py").read_text(encoding="utf-8")
    )
    assert not any(
        isinstance(node, ast.Import | ast.ImportFrom)
        for node in package_tree.body
        if not (isinstance(node, ast.ImportFrom) and node.module == "__future__")
    )


def test_immutable_geometry_owners_do_not_depend_on_mutable_hosts() -> None:
    """Keep focused geometry owners below layout, paint, and surface hosts."""

    architecture = prompt_editor_architecture_inventory()
    graph = architecture.graph
    geometry_prefix = "substitute.presentation.editor.prompt_editor.geometry."
    forbidden_hosts = {
        "substitute.presentation.editor.prompt_editor.projection.layout_engine",
        "substitute.presentation.editor.prompt_editor.projection.painter",
        "substitute.presentation.editor.prompt_editor.projection.surface",
    }
    violations = {
        module_name: tuple(sorted(graph[module_name] & forbidden_hosts))
        for module_name in graph
        if module_name.startswith(geometry_prefix)
        and graph[module_name] & forbidden_hosts
    }

    assert violations == {}


def test_geometry_aggregate_cannot_become_a_forwarding_facade() -> None:
    """Keep publication as composition instead of a list of delegated queries."""

    aggregate_path = PROMPT_PRESENTATION_ROOT / "geometry" / "aggregate.py"
    tree = ast.parse(aggregate_path.read_text(encoding="utf-8"))
    aggregate_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "PromptProjectionGeometry"
    )
    methods = {
        node.name
        for node in aggregate_class.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    public_fields = {
        node.target.id
        for node in aggregate_class.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and not node.target.id.startswith("_")
    }

    assert methods == {"__post_init__"}
    assert public_fields == {
        "input",
        "caret",
        "hit_testing",
        "selection",
        "source_lines",
        "tokens",
        "viewport",
    }


def test_pure_prompt_owners_use_cohesive_subpackages() -> None:
    """Keep pure prompt owners out of flat mixed-responsibility packages."""

    assert immediate_python_files(PROMPT_DOMAIN_ROOT) == {"__init__.py"}
    assert immediate_python_files(PROMPT_APPLICATION_ROOT) == {"__init__.py"}
    assert immediate_package_names(PROMPT_DOMAIN_ROOT) == _TARGET_DOMAIN_PACKAGES
    assert (
        immediate_package_names(PROMPT_APPLICATION_ROOT) == _TARGET_APPLICATION_PACKAGES
    )


def test_prompt_internal_imports_bypass_package_barrels() -> None:
    """Require internal consumers to import the authoritative owner directly."""

    forbidden_modules = {
        "substitute.application.prompt_editor",
        "substitute.domain.prompt",
    }
    violations: list[str] = []
    source_paths = (
        *(PROJECT_ROOT / "substitute").rglob("*.py"),
        *(PROJECT_ROOT / "substitute").rglob("*.pyi"),
    )
    for source_path in source_paths:
        if source_path.name == "__init__.py":
            continue
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in forbidden_modules:
                relative_path = source_path.relative_to(PROJECT_ROOT).as_posix()
                violations.append(f"{relative_path}:{node.lineno}:{node.module}")

    assert violations == []


def test_prompt_package_roots_do_not_dispatch_lazy_exports() -> None:
    """Keep package roots inert and free of service-locator export registries."""

    violations: dict[str, list[str]] = {}
    for package_root in (PROMPT_DOMAIN_ROOT, PROMPT_APPLICATION_ROOT):
        init_path = package_root / "__init__.py"
        tree = ast.parse(init_path.read_text(encoding="utf-8"))
        forbidden_nodes = [
            f"{type(node).__name__}:{getattr(node, 'lineno', 0)}"
            for node in tree.body
            if isinstance(
                node,
                ast.Assign
                | ast.AnnAssign
                | ast.FunctionDef
                | ast.AsyncFunctionDef
                | ast.ClassDef,
            )
        ]
        forbidden_imports = [
            f"{type(node).__name__}:{getattr(node, 'lineno', 0)}"
            for node in tree.body
            if isinstance(node, ast.Import)
            or (isinstance(node, ast.ImportFrom) and node.module != "__future__")
        ]
        if forbidden_nodes or forbidden_imports:
            violations[init_path.relative_to(PROJECT_ROOT).as_posix()] = [
                *forbidden_nodes,
                *forbidden_imports,
            ]

    assert violations == {}


def test_lora_catalog_values_do_not_depend_on_catalog_algorithms() -> None:
    """Keep immutable LoRA values below catalog construction and ranking."""

    models_path = PROMPT_APPLICATION_ROOT / "lora" / "catalog_models.py"
    tree = ast.parse(models_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert not {
        module_name
        for module_name in imported_modules
        if module_name.startswith("substitute.application.prompt_editor.lora.")
    }


def test_revision_owner_replaces_obsolete_prompt_state_mirrors() -> None:
    """Prevent deleted raw revision and derived-state authorities from returning."""

    forbidden_fragments = {
        PROMPT_PRESENTATION_ROOT / "projection" / "surface.py": (
            "self._source_revision",
            "self._projection_document",
            "self._document_view",
            "self._render_plan",
        ),
        PROMPT_PRESENTATION_ROOT / "projection" / "diagnostic_layer_owner.py": (
            "self._layout_revision",
            "advance_layout_revision",
        ),
        PROMPT_PRESENTATION_ROOT / "async_work" / "execution.py": (
            "source_revision: int | None",
            "source_length: int | None",
        ),
        PROMPT_PRESENTATION_ROOT / "projection" / "transient_edit_overlays.py": (
            "source_revision: int",
            "committed_source_revision",
        ),
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_overlay.py": (
            "self._source_revision",
            "source_revision: int | None",
        ),
        PROMPT_PRESENTATION_ROOT / "core" / "state" / "editor_state.py": (
            "_require_source_text(",
            "_require_matching_source_text(",
            "derived.source_text != ",
            "downstream.source_text != ",
        ),
        PROMPT_PRESENTATION_ROOT / "syntax_renderers.py": ("self._state.revisions",),
        PROMPT_PRESENTATION_ROOT / "core" / "editing" / "source_commands.py": (
            "self._source_buffer.source_text =",
            "self._source_buffer.source_revision +=",
            "self._source_buffer.parenthesis_intents =",
            "self._source_buffer.generated_emphases =",
        ),
    }
    violations: list[str] = []
    for source_path, fragments in forbidden_fragments.items():
        source = source_path.read_text(encoding="utf-8")
        violations.extend(
            f"{source_path.relative_to(PROJECT_ROOT).as_posix()}:{fragment}"
            for fragment in fragments
            if fragment in source
        )

    assert violations == []
