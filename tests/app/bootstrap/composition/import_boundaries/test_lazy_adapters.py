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

"""Test bootstrap lazy-adapter import boundaries."""

from __future__ import annotations

import textwrap
from collections.abc import Iterable


from .support import (
    run_isolated_import_probe,
)


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

    completed = run_isolated_import_probe(code)

    assert completed.stdout.strip() == (
        '[["_LazyCivitaiClient", "_LazyDanbooruClient", '
        '"_LazyComfyObjectInfoClient"], []]'
    )


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

    completed = run_isolated_import_probe(code)

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

    completed = run_isolated_import_probe(code)

    assert completed.stdout.strip() == (
        '[["_LazyDanbooruUrlImportService", '
        '"_LazyDanbooruRecentPostsService", '
        '"_LazyDanbooruWikiContentService"], []]'
    )


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

    completed = run_isolated_import_probe(code)

    assert completed.stdout.strip() == '["_LazyComfyGateway", []]'


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
            "substitute.application.prompt_editor.lora.effective_provider"
        )
        print(json.dumps([provider.__class__.__name__, module_name in sys.modules]))
        """
    )

    completed = run_isolated_import_probe(code)

    assert completed.stdout.strip() == '["_LazyScheduledLoraProvider", false]'


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
