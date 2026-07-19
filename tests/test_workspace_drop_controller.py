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

"""Contract tests for workspace fallback drag-and-drop workflow loading."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from substitute.application.ports.recipe_repository import LoadedRecipeDocument
from substitute.application.recipes.recipe_io_service import RecipeIoService
from substitute.presentation.shell.workspace_drop_controller import (
    DirectWorkflowDocumentClassifier,
    DropIntent,
    WorkspaceDropController,
    WorkflowRecipeDropClassifier,
)


def _append_then(values: list[Path], value: Path, result: str) -> str:
    """Append one path and return the requested workflow ID."""

    values.append(value)
    return result


class _FakeRecipeRepository:
    """Recipe repository double with deterministic PNG metadata sniffing."""

    def load_recipe_document(self, path: Path) -> LoadedRecipeDocument:
        """Return a placeholder loaded document; not used by these tests."""

        return LoadedRecipeDocument(
            sugar_script_text="use Cube",
            source_path=path,
            source_kind="text",
        )

    def has_embedded_recipe_script(self, path: Path) -> bool:
        """Treat only one PNG filename as recipe-bearing."""

        return path.name == "embedded.png"

    def save_recipe_document(
        self,
        path: Path,
        *,
        project_name: str,
        sugar_script_text: str,
    ) -> None:
        """Satisfy the repository protocol for the recipe service."""

        _ = path, project_name, sugar_script_text


class _FakeDirectWorkflowSupport:
    """Recognize JSON and selected PNG paths as direct Comfy workflows."""

    def can_load(self, path: Path) -> bool:
        """Return deterministic direct-workflow support for routing tests."""

        return path.suffix.casefold() == ".json" or path.name in {
            "embedded.png",
            "workflow.png",
        }


class _Url:
    """URL test double for local and remote drag payloads."""

    def __init__(self, path: str, *, local: bool = True) -> None:
        self._path = path
        self._local = local

    def isLocalFile(self) -> bool:
        """Return whether this URL represents a local file."""

        return self._local

    def toLocalFile(self) -> str:
        """Return the local file path."""

        return self._path


class _MimeData:
    """Mime-data test double carrying URL payloads."""

    def __init__(self, urls: tuple[_Url, ...]) -> None:
        self._urls = urls

    def hasUrls(self) -> bool:
        """Return whether URLs are present."""

        return bool(self._urls)

    def urls(self) -> tuple[_Url, ...]:
        """Return URL payloads."""

        return self._urls


class _Event:
    """Drag/drop event double that records accept and ignore calls."""

    def __init__(
        self,
        mime_data: _MimeData,
        *,
        source: object | None = None,
    ) -> None:
        self._mime_data = mime_data
        self._source = source
        self.accepted = False
        self.ignored = False

    def mimeData(self) -> _MimeData:
        """Return event mime data."""

        return self._mime_data

    def source(self) -> object | None:
        """Return the originating drag source."""

        return self._source

    def acceptProposedAction(self) -> None:
        """Record accepted drop action."""

        self.accepted = True

    def ignore(self) -> None:
        """Record ignored drop action."""

        self.ignored = True


def _classifier() -> WorkflowRecipeDropClassifier:
    """Build the classifier under test with deterministic recipe sniffing."""

    return WorkflowRecipeDropClassifier(
        RecipeIoService(recipe_repository=_FakeRecipeRepository())
    )


def _direct_workflow_classifier() -> WorkflowRecipeDropClassifier:
    """Build a classifier that additionally recognizes Comfy workflow JSON."""

    return WorkflowRecipeDropClassifier(
        RecipeIoService(recipe_repository=_FakeRecipeRepository()),
        DirectWorkflowDocumentClassifier(_FakeDirectWorkflowSupport()),
    )


def _controller(
    load_recipe_document: Callable[[Path], str | None],
) -> WorkspaceDropController:
    """Build a controller that treats every drag source as external."""

    return WorkspaceDropController(
        classifier=_classifier(),
        ignored_drag_source=lambda _source: False,
        load_recipe_document=load_recipe_document,
    )


def test_workflow_recipe_drop_classifier_accepts_text_recipe_path() -> None:
    """Text recipe files should classify as workflow recipe drops."""

    classified = _classifier().classify_path(Path("E:/recipes/demo.sugar"))

    assert classified.intent is DropIntent.LOAD_WORKFLOW_RECIPE
    assert classified.reason == "text_recipe_extension"


def test_workspace_drop_classifier_accepts_direct_comfy_json() -> None:
    """JSON should route to the direct Comfy document load boundary."""

    classified = _direct_workflow_classifier().classify_path(
        Path("workflows/demo.json")
    )

    assert classified.intent is DropIntent.LOAD_DIRECT_COMFY_WORKFLOW
    assert classified.reason == "comfy_workflow_json"


def test_workflow_recipe_drop_classifier_accepts_recipe_bearing_png() -> None:
    """SugarScript metadata should win even when Comfy workflow metadata also exists."""

    classified = _classifier().classify_path(Path("E:/recipes/embedded.png"))

    assert classified.intent is DropIntent.LOAD_WORKFLOW_RECIPE
    assert classified.reason == "png_embedded_recipe"


def test_workspace_drop_classifier_accepts_workflow_only_png() -> None:
    """PNG workflow metadata should use direct loading when no SugarScript exists."""

    classified = _direct_workflow_classifier().classify_path(
        Path("E:/recipes/workflow.png")
    )

    assert classified.intent is DropIntent.LOAD_DIRECT_COMFY_WORKFLOW
    assert classified.reason == "comfy_workflow_png"


def test_workflow_recipe_drop_classifier_ignores_plain_png() -> None:
    """Plain PNG files should remain available for future node-specific drops."""

    classified = _classifier().classify_path(Path("E:/images/plain.png"))

    assert classified.intent is DropIntent.NONE
    assert classified.reason == "png_without_embedded_recipe"


def test_workflow_recipe_drop_classifier_ignores_other_images() -> None:
    """Workspace fallback should not consume generic image extensions."""

    classified = _classifier().classify_path(Path("E:/images/plain.jpg"))

    assert classified.intent is DropIntent.NONE
    assert classified.reason == "unsupported_extension"


def test_workflow_recipe_drop_classifier_ignores_directories(tmp_path: Path) -> None:
    """Directory drops should not be treated as workflow recipe drops."""

    classified = _classifier().classify_path(tmp_path)

    assert classified.intent is DropIntent.NONE
    assert classified.reason == "directory"


def test_workflow_recipe_drop_classifier_ignores_multiple_urls() -> None:
    """Multiple-file drops should be ignored by the first workspace fallback slice."""

    classified = _classifier().classify_mime_data(
        _MimeData(
            (
                _Url("E:/recipes/one.sugar"),
                _Url("E:/recipes/two.sugar"),
            )
        )
    )

    assert classified.intent is DropIntent.NONE
    assert classified.reason == "not_single_file"


def test_workflow_recipe_drop_classifier_ignores_non_local_urls() -> None:
    """Remote URL payloads should not be accepted as local workflow recipes."""

    classified = _classifier().classify_mime_data(
        _MimeData((_Url("https://example.invalid/recipe.sugar", local=False),))
    )

    assert classified.intent is DropIntent.NONE
    assert classified.reason == "non_local_url"


def test_workspace_drop_controller_accepts_recipe_drag_enter() -> None:
    """Drag-enter should accept only workflow recipe payloads."""

    event = _Event(_MimeData((_Url("E:/recipes/demo.sugar"),)))
    loaded_paths: list[Path] = []
    controller = _controller(lambda path: _append_then(loaded_paths, path, "wf-1"))

    handled = controller.handle_drag_enter(event)

    assert handled is True
    assert event.accepted is True
    assert event.ignored is False
    assert loaded_paths == []


def test_workspace_drop_controller_ignores_generic_image_drag_enter() -> None:
    """Drag-enter should ignore images that are not workflow recipes."""

    event = _Event(_MimeData((_Url("E:/images/plain.png"),)))
    controller = _controller(lambda _path: "wf-1")

    handled = controller.handle_drag_enter(event)

    assert handled is False
    assert event.accepted is False
    assert event.ignored is True


def test_workspace_drop_controller_loads_accepted_recipe_drop() -> None:
    """Drop should delegate accepted workflow recipes to the shared load method."""

    event = _Event(_MimeData((_Url("E:/recipes/embedded.png"),)))
    loaded_paths: list[Path] = []
    controller = _controller(lambda path: _append_then(loaded_paths, path, "wf-1"))

    handled = controller.handle_drop(event)

    assert handled is True
    assert event.accepted is True
    assert event.ignored is False
    assert loaded_paths == [Path("E:/recipes/embedded.png")]


def test_workspace_drop_controller_loads_direct_comfy_workflow() -> None:
    """A JSON drop should invoke only the direct-workflow action."""

    event = _Event(_MimeData((_Url("workflows/demo.json"),)))
    recipe_paths: list[Path] = []
    direct_paths: list[Path] = []
    controller = WorkspaceDropController(
        classifier=_direct_workflow_classifier(),
        ignored_drag_source=lambda _source: False,
        load_recipe_document=lambda path: _append_then(recipe_paths, path, "recipe"),
        load_direct_workflow_document=lambda path: _append_then(
            direct_paths, path, "direct"
        ),
    )

    handled = controller.handle_drop(event)

    assert handled is True
    assert event.accepted is True
    assert recipe_paths == []
    assert direct_paths == [Path("workflows/demo.json")]


def test_workspace_drop_controller_does_not_load_ignored_drop() -> None:
    """Ignored workspace drops should not invoke workflow loading."""

    event = _Event(_MimeData((_Url("E:/images/plain.webp"),)))
    loaded_paths: list[Path] = []
    controller = _controller(lambda path: _append_then(loaded_paths, path, "wf-1"))

    handled = controller.handle_drop(event)

    assert handled is False
    assert event.accepted is False
    assert event.ignored is True
    assert loaded_paths == []


def test_workspace_drop_controller_ignores_internal_canvas_drag_enter() -> None:
    """Internal canvas drags should not activate workspace recipe loading."""

    canvas_source = object()
    event = _Event(
        _MimeData((_Url("E:/recipes/embedded.png"),)),
        source=canvas_source,
    )
    controller = WorkspaceDropController(
        classifier=_classifier(),
        ignored_drag_source=lambda source: source is canvas_source,
        load_recipe_document=lambda _path: "wf-1",
    )

    handled = controller.handle_drag_enter(event)

    assert handled is False
    assert event.accepted is False
    assert event.ignored is True


def test_workspace_drop_controller_does_not_load_internal_canvas_drop() -> None:
    """Internal canvas drops should not enter the workflow recipe loader."""

    canvas_source = object()
    event = _Event(
        _MimeData((_Url("E:/recipes/embedded.png"),)),
        source=canvas_source,
    )
    loaded_paths: list[Path] = []
    controller = WorkspaceDropController(
        classifier=_classifier(),
        ignored_drag_source=lambda source: source is canvas_source,
        load_recipe_document=lambda path: _append_then(loaded_paths, path, "wf-1"),
    )

    handled = controller.handle_drop(event)

    assert handled is False
    assert event.accepted is False
    assert event.ignored is True
    assert loaded_paths == []
