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

"""Tests for startup composition import boundaries."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import textwrap
from collections.abc import Iterable
from pathlib import Path
from typing import cast

import pytest

from substitute.domain.model_metadata import CivitaiImage


COMPOSITION_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "app"
    / "bootstrap"
    / "composition.py"
)


def test_startup_composition_imports_no_onboarding_ui_at_module_load() -> None:
    """Ready-route composition imports should not pay onboarding UI costs."""

    forbidden = {
        "substitute.app.bootstrap.installation_context",
        "substitute.app.bootstrap.onboarding_execution",
        "substitute.application.onboarding",
        "substitute.presentation.onboarding",
    }

    assert forbidden.isdisjoint(_top_level_imported_module_names(COMPOSITION_SOURCE))


def test_startup_composition_uses_direct_danbooru_service_imports() -> None:
    """Dependency composition should not pay the Danbooru package facade cost."""

    imported_modules = _top_level_imported_module_names(COMPOSITION_SOURCE)
    source = COMPOSITION_SOURCE.read_text(encoding="utf-8")

    assert "substitute.application.danbooru" not in imported_modules
    assert "from substitute.application.danbooru import" not in source
    assert "substitute.application.danbooru.image_preview_service" in source


def test_startup_composition_uses_direct_generation_service_imports() -> None:
    """Dependency composition should not pay the generation package facade cost."""

    imported_modules = _top_level_imported_module_names(COMPOSITION_SOURCE)
    source = COMPOSITION_SOURCE.read_text(encoding="utf-8")

    assert "substitute.application.generation" not in imported_modules
    assert "from substitute.application.generation import" not in source
    assert "substitute.application.generation.generation_service" in source


def test_generation_package_queue_export_does_not_load_dispatch_service() -> None:
    """Generation queue imports should not load dispatch service machinery."""

    code = textwrap.dedent(
        """
        import importlib
        import json
        import sys

        from substitute.application.generation import GenerationJobQueueService

        importlib.import_module("substitute.application.generation.job_queue_service")
        loaded = sorted(
            name
            for name in sys.modules
            if name in {
                "substitute.application.generation.generation_preparation_service",
                "substitute.application.generation.generation_service",
                "substitute.domain.recipes",
            }
        )
        print(json.dumps([GenerationJobQueueService.__name__, loaded]))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=COMPOSITION_SOURCE.parents[3],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == '["GenerationJobQueueService", []]'


def test_prompt_editor_preference_export_does_not_load_editor_feature_stack() -> None:
    """Prompt-editor preference imports should not load document and LoRA stacks."""

    code = textwrap.dedent(
        """
        import json
        import sys

        from substitute.application.prompt_editor import PromptEditorPreferenceService

        loaded = sorted(
            name
            for name in sys.modules
            if name in {
                "substitute.application.prompt_editor.prompt_document_service",
                "substitute.application.prompt_editor.prompt_lora_catalog_service",
                "substitute.application.prompt_editor.prompt_syntax_service",
            }
        )
        print(json.dumps([PromptEditorPreferenceService.__name__, loaded]))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=COMPOSITION_SOURCE.parents[3],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == '["PromptEditorPreferenceService", []]'


def test_external_gateway_export_does_not_load_all_external_clients() -> None:
    """External facade imports should not load unrelated integration clients."""

    code = textwrap.dedent(
        """
        import json
        import sys

        from substitute.infrastructure.external import PhotoshopGateway

        loaded = sorted(
            name
            for name in sys.modules
            if name in {
                "substitute.infrastructure.external.civitai_client",
                "substitute.infrastructure.external.comfy_object_info_client",
                "substitute.infrastructure.external.substitute_backend_cube_library_client",
            }
        )
        print(json.dumps([PhotoshopGateway.__name__, loaded]))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=COMPOSITION_SOURCE.parents[3],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == '["PhotoshopGateway", []]'


def test_danbooru_domain_preference_export_does_not_load_all_domain_models() -> None:
    """Preference-only Danbooru imports should not load cache and record models."""

    code = textwrap.dedent(
        """
        import json
        import sys

        from substitute.domain.danbooru import DanbooruImageRatingPolicy

        loaded = sorted(
            name
            for name in sys.modules
            if name in {
                "substitute.domain.danbooru.cache_models",
                "substitute.domain.danbooru.models",
            }
        )
        print(json.dumps([DanbooruImageRatingPolicy.SAFE_ONLY.value, loaded]))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=COMPOSITION_SOURCE.parents[3],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == '["safe_only", []]'


def test_application_ports_preference_import_does_not_load_comfy_gateway() -> None:
    """Importing one port contract should not load the whole ports facade."""

    code = textwrap.dedent(
        """
        import importlib
        import json
        import sys

        importlib.import_module(
            "substitute.application.ports.danbooru_preference_repository"
        )
        loaded = sorted(
            name
            for name in sys.modules
            if name in {
                "substitute.application.ports.comfy_gateway",
                "substitute.application.ports.cube_repository",
            }
        )
        print(json.dumps(loaded))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=COMPOSITION_SOURCE.parents[3],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "[]"


def test_danbooru_preference_export_does_not_load_danbooru_feature_stack() -> None:
    """Importing Danbooru preferences should not load preview/wiki feature modules."""

    code = textwrap.dedent(
        """
        import json
        import sys

        from substitute.application.danbooru import DanbooruPreferenceService

        loaded = sorted(
            name
            for name in sys.modules
            if name in {
                "substitute.application.danbooru.image_preview_service",
                "substitute.application.danbooru.url_import_service",
                "substitute.application.danbooru.wiki_content_service",
                "substitute.application.danbooru.wiki_render_models",
            }
        )
        print(json.dumps([DanbooruPreferenceService.__name__, loaded]))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=COMPOSITION_SOURCE.parents[3],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == '["DanbooruPreferenceService", []]'


def test_startup_composition_import_does_not_load_qfluentwidgets() -> None:
    """Startup composition import should not load Fluent widgets before UI build."""

    code = textwrap.dedent(
        """
        import importlib
        import json
        import sys

        importlib.import_module("substitute.app.bootstrap.composition")
        loaded = any(
            name == "qfluentwidgets" or name.startswith("qfluentwidgets.")
            for name in sys.modules
        )
        print(json.dumps(loaded))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=COMPOSITION_SOURCE.parents[3],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "false"


def test_main_window_dependencies_import_keeps_ui_and_network_modules_deferred() -> (
    None
):
    """The dependency dataclass import should not force UI or network stacks."""

    code = textwrap.dedent(
        """
        import importlib
        import json
        import sys

        importlib.import_module("substitute.presentation.shell.main_window_dependencies")
        prefixes = ("PySide6", "qfluentwidgets", "requests", "scipy")
        loaded = sorted(
            name
            for name in sys.modules
            if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes)
        )
        print(json.dumps(loaded))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=COMPOSITION_SOURCE.parents[3],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "[]"


def test_wildcard_management_opener_import_keeps_modal_stack_deferred() -> None:
    """The wildcard opener export should not import the prompt-editor modal."""

    code = textwrap.dedent(
        """
        import json
        import sys

        from substitute.presentation.managed_text_assets import WildcardManagementOpener

        prefixes = (
            "PySide6",
            "qfluentwidgets",
            "scipy",
            "substitute.presentation.editor.prompt_editor",
            "substitute.presentation.managed_text_assets.managed_text_asset_modal",
            "substitute.presentation.managed_text_assets.wildcard_management_modal",
        )
        loaded = sorted(
            name
            for name in sys.modules
            if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes)
        )
        print(json.dumps([WildcardManagementOpener.__name__, loaded]))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=COMPOSITION_SOURCE.parents[3],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == '["WildcardManagementOpener", []]'


def test_cube_icon_factory_import_keeps_fluent_theme_deferred() -> None:
    """Constructing the icon factory should not import Fluent theme helpers."""

    code = textwrap.dedent(
        """
        import json
        import sys

        from substitute.presentation.resources.cube_icon_factory import CubeIconFactory

        factory = CubeIconFactory()
        loaded = sorted(
            name
            for name in sys.modules
            if name == "qfluentwidgets" or name.startswith("qfluentwidgets.")
        )
        print(json.dumps([factory.__class__.__name__, loaded]))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=COMPOSITION_SOURCE.parents[3],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == '["CubeIconFactory", []]'


def test_lazy_comfy_gateway_defers_prompt_transport_imports() -> None:
    """Gateway injection should not import prompt transport before generation."""

    code = textwrap.dedent(
        """
        import json
        import sys

        from substitute.app.bootstrap.composition import _LazyComfyGateway
        from substitute.domain.onboarding import ComfyEndpoint

        gateway = _LazyComfyGateway(ComfyEndpoint(host="127.0.0.1", port=8188))
        prefixes = (
            "substitute.infrastructure.comfy.gateway_adapter",
            "substitute.infrastructure.comfy.prompt_gateway",
            "substitute.infrastructure.comfy.websocket_listener",
            "substitute.infrastructure.comfy.websocket_transport",
        )
        loaded = sorted(
            name
            for name in sys.modules
            if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes)
        )
        print(json.dumps([gateway.__class__.__name__, loaded]))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=COMPOSITION_SOURCE.parents[3],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == '["_LazyComfyGateway", []]'


def test_lazy_model_catalog_snapshot_store_defers_sqlite_setup() -> None:
    """Snapshot-store injection should not initialize the SQLite cache at startup."""

    code = textwrap.dedent(
        """
        import json
        import sys
        import tempfile
        from pathlib import Path

        from substitute.app.bootstrap.composition import (
            _LazyModelCatalogSnapshotStore,
        )

        root = Path(tempfile.mkdtemp())
        store = _LazyModelCatalogSnapshotStore(root)
        module_name = (
            "substitute.infrastructure.persistence."
            "sqlite_model_catalog_snapshot_store"
        )
        print(json.dumps({
            "class": store.__class__.__name__,
            "module_loaded": module_name in sys.modules,
            "database_exists": (root / "model_catalog_snapshots.sqlite3").exists(),
        }))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=COMPOSITION_SOURCE.parents[3],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout.strip()) == {
        "class": "_LazyModelCatalogSnapshotStore",
        "module_loaded": False,
        "database_exists": False,
    }


def test_lazy_danbooru_preview_service_defers_preview_imports() -> None:
    """Preview service injection should not import preview logic before use."""

    code = textwrap.dedent(
        """
        import json
        import sys

        from substitute.app.bootstrap.composition import (
            _LazyDanbooruImagePreviewService,
        )

        service = _LazyDanbooruImagePreviewService(
            client=object(),
            cache_repository=object(),
            preference_service=object(),
            refresh_submitter=object(),
        )
        module_name = "substitute.application.danbooru.image_preview_service"
        print(json.dumps([service.__class__.__name__, module_name in sys.modules]))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=COMPOSITION_SOURCE.parents[3],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == '["_LazyDanbooruImagePreviewService", false]'


def test_lazy_danbooru_feature_services_defer_feature_imports() -> None:
    """Danbooru feature injections should not import concrete services before use."""

    code = textwrap.dedent(
        """
        import json
        import sys

        from substitute.app.bootstrap.composition import (
            _LazyDanbooruRecentPostsService,
            _LazyDanbooruUrlImportService,
            _LazyDanbooruWikiContentService,
        )

        services = [
            _LazyDanbooruUrlImportService(client=object()),
            _LazyDanbooruRecentPostsService(
                client=object(),
                cache_repository=object(),
                preference_service=object(),
            ),
            _LazyDanbooruWikiContentService(
                client=object(),
                cache_repository=object(),
                preference_service=object(),
                refresh_submitter=object(),
            ),
        ]
        forbidden = {
            "substitute.application.danbooru.recent_posts_service",
            "substitute.application.danbooru.url_import_service",
            "substitute.application.danbooru.wiki_content_service",
            "substitute.application.danbooru.wiki_inline_resolution_service",
        }
        loaded = sorted(name for name in sys.modules if name in forbidden)
        print(json.dumps([[service.__class__.__name__ for service in services], loaded]))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=COMPOSITION_SOURCE.parents[3],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == (
        '[["_LazyDanbooruUrlImportService", '
        '"_LazyDanbooruRecentPostsService", '
        '"_LazyDanbooruWikiContentService"], []]'
    )


def test_lazy_scheduled_lora_provider_defers_effective_lora_imports() -> None:
    """Scheduled-LoRA injection should not import graph analysis before use."""

    code = textwrap.dedent(
        """
        import json
        import sys
        from pathlib import Path

        from substitute.app.bootstrap.composition import _LazyScheduledLoraProvider

        provider = _LazyScheduledLoraProvider(
            recipe_io_service=object(),
            workflow_export_service=object(),
            prompt_scheduled_lora_service=object(),
            prompt_lora_catalog_service=object(),
            rich_choice_resolver=object(),
            node_definition_gateway=object(),
            output_dir=Path("."),
        )
        module_name = (
            "substitute.application.prompt_editor.effective_scheduled_lora_provider"
        )
        print(json.dumps([provider.__class__.__name__, module_name in sys.modules]))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=COMPOSITION_SOURCE.parents[3],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == '["_LazyScheduledLoraProvider", false]'


def test_lazy_http_clients_defer_requests_backed_imports() -> None:
    """Startup HTTP gateway injections should not import concrete clients before use."""

    code = textwrap.dedent(
        """
        import json
        import sys

        from substitute.app.bootstrap.composition import (
            _LazyCivitaiClient,
            _LazyComfyObjectInfoClient,
            _LazyDanbooruClient,
        )
        from substitute.domain.onboarding import ComfyEndpoint

        clients = [
            _LazyCivitaiClient(api_key_provider=lambda: None),
            _LazyDanbooruClient(),
            _LazyComfyObjectInfoClient(
                endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
                background_scheduler=lambda callback: object(),
                shutdown_background_scheduler=lambda: None,
            ),
        ]
        forbidden = {
            "requests",
            "substitute.infrastructure.external.civitai_client",
            "substitute.infrastructure.external.comfy_object_info_client",
            "substitute.infrastructure.external.danbooru_client",
        }
        loaded = sorted(name for name in sys.modules if name in forbidden)
        print(json.dumps([[client.__class__.__name__ for client in clients], loaded]))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=COMPOSITION_SOURCE.parents[3],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == (
        '[["_LazyCivitaiClient", "_LazyDanbooruClient", '
        '"_LazyComfyObjectInfoClient"], []]'
    )


def test_lazy_comfy_object_info_client_forwards_batch_definition_refresh() -> None:
    """Lazy object-info access should preserve forced batch refresh support."""

    from substitute.app.bootstrap.composition import _LazyComfyObjectInfoClient
    from substitute.domain.onboarding import ComfyEndpoint

    class _ObjectInfoClient:
        """Record affected node classes sent through the lazy boundary."""

        def __init__(self) -> None:
            """Initialize an empty refresh call list."""

            self.refresh_calls: list[tuple[str, ...]] = []

        def refresh_node_definitions(
            self,
            node_classes: Iterable[str],
        ) -> tuple[str, ...]:
            """Record and return the normalized node classes."""

            normalized = tuple(node_classes)
            self.refresh_calls.append(normalized)
            return normalized

    concrete_client = _ObjectInfoClient()
    lazy_client = _LazyComfyObjectInfoClient(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        background_scheduler=lambda callback: object(),
        shutdown_background_scheduler=lambda: None,
    )
    setattr(lazy_client, "_client", concrete_client)

    refreshed = lazy_client.refresh_node_definitions(
        ("SimpleSyrup.SimpleLoadAnima", "UNETLoader")
    )

    assert refreshed == ("SimpleSyrup.SimpleLoadAnima", "UNETLoader")
    assert concrete_client.refresh_calls == [
        ("SimpleSyrup.SimpleLoadAnima", "UNETLoader")
    ]


def test_lazy_model_thumbnail_store_defers_thumbnail_caching_imports() -> None:
    """Startup model metadata wiring should not load thumbnail caching machinery."""

    code = textwrap.dedent(
        """
        import json
        import sys
        from pathlib import Path

        from substitute.app.bootstrap.composition import _LazyModelThumbnailStore

        store = _LazyModelThumbnailStore(Path("."))
        forbidden = {
            "requests",
            "substitute.infrastructure.persistence.model_thumbnail_store",
            "substitute.infrastructure.persistence.thumbnail_banner_cropper",
            "substitute.shared.qt_thumbnail_codec",
        }
        loaded = sorted(name for name in sys.modules if name in forbidden)
        print(json.dumps([store.__class__.__name__, loaded]))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=COMPOSITION_SOURCE.parents[3],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == '["_LazyModelThumbnailStore", []]'


def test_lazy_model_thumbnail_store_cache_calls_do_not_evaluate_type_only_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lazy thumbnail cache casts should not require type-only imports at runtime."""

    from substitute.app.bootstrap.composition import _LazyModelThumbnailStore

    remote_result = object()
    local_result = object()

    class _Store:
        """Return sentinels from the concrete thumbnail store surface."""

        def cache_thumbnail(
            self,
            *,
            sha256: str,
            image: object,
            selection_policy: str,
        ) -> object:
            """Return the remote thumbnail sentinel."""

            _ = sha256, image, selection_policy
            return remote_result

        def cache_local_thumbnail(
            self,
            *,
            sha256: str,
            image: object | None,
            source: str,
            source_label: str,
            source_path: str | None = None,
            source_width: int | None = None,
            source_height: int | None = None,
        ) -> object:
            """Return the local thumbnail sentinel."""

            _ = (
                sha256,
                image,
                source,
                source_label,
                source_path,
                source_width,
                source_height,
            )
            return local_result

    store = _LazyModelThumbnailStore(Path("."))
    monkeypatch.setattr(store, "_resolve", lambda: _Store())

    assert (
        store.cache_thumbnail(
            sha256="abc",
            image=cast(CivitaiImage, object()),
            selection_policy="first_sfw",
        )
        is remote_result
    )
    assert (
        store.cache_local_thumbnail(
            sha256="abc",
            image=None,
            source="output",
            source_label="Output",
        )
        is local_result
    )


def test_model_metadata_action_scheduler_import_keeps_menu_ui_deferred() -> None:
    """The action scheduler should not import the context-menu UI stack."""

    code = textwrap.dedent(
        """
        import json
        import sys

        from substitute.presentation.shell.model_metadata_context_action_handler import (
            ModelMetadataContextActionScheduler,
        )

        prefixes = (
            "PySide6",
            "qfluentwidgets",
            "scipy",
            "substitute.presentation.widgets.model_metadata_context_menu",
        )
        loaded = sorted(
            name
            for name in sys.modules
            if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes)
        )
        print(json.dumps([ModelMetadataContextActionScheduler.__name__, loaded]))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=COMPOSITION_SOURCE.parents[3],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == '["ModelMetadataContextActionScheduler", []]'


def test_main_window_composition_import_keeps_canvas_view_deferred() -> None:
    """Main-window composition imports should not load concrete canvas widgets."""

    code = textwrap.dedent(
        """
        import importlib
        import json
        import sys

        importlib.import_module("substitute.presentation.shell.main_window_composition")
        forbidden = {
            "cv2",
            "substitute.presentation.canvas.factory",
            "substitute.presentation.canvas.input.input_canvas_view",
            "substitute.presentation.canvas.output.output_canvas_view",
        }
        loaded = sorted(name for name in sys.modules if name in forbidden)
        print(json.dumps(loaded))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=COMPOSITION_SOURCE.parents[3],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "[]"


def _top_level_imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported at top level by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
