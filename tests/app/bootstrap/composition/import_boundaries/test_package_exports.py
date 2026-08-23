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

"""Test package export import boundaries."""

from __future__ import annotations

import textwrap


from .support import (
    run_isolated_import_probe,
)


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

    completed = run_isolated_import_probe(code)

    assert completed.stdout.strip() == '["DanbooruPreferenceService", []]'


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

    completed = run_isolated_import_probe(code)

    assert completed.stdout.strip() == '["safe_only", []]'


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

    completed = run_isolated_import_probe(code)

    assert completed.stdout.strip() == '["PhotoshopGateway", []]'


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

    completed = run_isolated_import_probe(code)

    assert completed.stdout.strip() == "[]"


def test_prompt_editor_preference_owner_does_not_load_editor_feature_stack() -> None:
    """Prompt-editor preference imports should not load document and LoRA stacks."""

    code = textwrap.dedent(
        """
        import json
        import sys

        from substitute.application.prompt_editor.features.preferences import (
            PromptEditorPreferenceService,
        )

        loaded = sorted(
            name
            for name in sys.modules
            if name in {
                "substitute.application.prompt_editor.document.service",
                "substitute.application.prompt_editor.lora.catalog",
                "substitute.application.prompt_editor.projection.syntax_service",
            }
        )
        print(json.dumps([PromptEditorPreferenceService.__name__, loaded]))
        """
    )

    completed = run_isolated_import_probe(code)

    assert completed.stdout.strip() == '["PromptEditorPreferenceService", []]'


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

    completed = run_isolated_import_probe(code)

    assert completed.stdout.strip() == '["GenerationJobQueueService", []]'
