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

"""Compose startup UI objects and application shell wiring."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import set_localized_window_title

import hashlib
import importlib
import os
import sys
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any, Protocol, Sequence, cast

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.about import AboutInfoService
from substitute.application.appearance import (
    AppearanceResolver,
    AppearanceRestartCoordinator,
    ResolvedAppearance,
)
from substitute.application.appearance.appearance_preference_service import (
    AppearancePreferenceService,
)
from substitute.app.bootstrap.appearance_runtime import AppearanceRuntimeController
from substitute.app.bootstrap.localization_composition import (
    build_application_localization_runtime,
    build_node_presentation_service,
)
from substitute.application.comfy_environment import ComfyEnvironmentService
from substitute.application.execution import (
    DirectExecutionDispatcher,
    ExecutionContext,
    TaskIdentity,
    TaskScope,
    TaskRequest,
)
from substitute.application.ports.startup_diagnostics_ignore_repository import (
    StartupDiagnosticsIgnoreRepository,
)
from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyEndpoint,
    InstallationContext,
    ReadinessAssessment,
    SetupTransactionMode,
)
from substitute.application.workspace_state import (
    InitialShellPlacement,
    WorkspaceSnapshot,
)
from substitute.app.bootstrap.app_layout import resolve_app_layout
from substitute.app.bootstrap.runtime import (
    ApplicationRuntimeServices,
    build_application_runtime_services,
)
from substitute.app.bootstrap.prompt_editor_execution import (
    create_editor_panel_execution_factories,
)
from substitute.app.bootstrap.settings_execution import (
    create_settings_task_runner_factory,
)
from substitute.app.bootstrap.execution_runtime import ExecutionRuntime
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.app.bootstrap.startup_trace import (
    StartupVisibilityEventFilter,
    trace_mark,
    trace_span,
)
from substitute.app.bootstrap.model_metadata_refresh import (
    StartupModelMetadataRefreshHandle,
)
from substitute.infrastructure.comfy.preview_image_decoder import decode_preview_image
from substitute.infrastructure.appearance import (
    build_system_appearance_provider,
    probe_window_material_capabilities,
)
from substitute.infrastructure.execution import LongLivedTaskHandle
from substitute.infrastructure.execution.long_lived_task import LongLivedWork
from substitute.infrastructure.persistence import FileAppearancePreferenceRepository
from substitute.infrastructure.python_packages import installed_distribution_version
from substitute.presentation.qt.execution import QtOwnerThreadDispatcher
from substitute.presentation.qt.preview_qimage_adapter import preview_image_to_qimage
from substitute.presentation.resources.app_icon import application_icon
from substitute.presentation.shell.generation_titlebar_control_registry import (
    GenerationTitleBarControlRegistry,
)
from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_exception,
    log_warning,
)

_LOGGER = get_logger("app.bootstrap.composition")
ShutdownRequest = Callable[[QWidget | None], None]
WINDOWS_APP_USER_MODEL_ID = "SugarSubstitute.SugarSubstitute"
DISABLE_WINDOWS_APP_USER_MODEL_ID_ENV = "SUBSTITUTE_DISABLE_APP_USER_MODEL_ID"

if TYPE_CHECKING:
    from substitute.application.model_metadata import ModelCatalogSnapshot
    from substitute.application.ports import NodeDefinitionHydrationResult
    from substitute.application.ports.comfy_gateway import (
        ComfyGateway,
        ComfyQueueMutationResult,
        ComfyQueueSnapshot,
        InterruptResult,
        ListenerCallbacks,
        ListenerSessionHandle,
        ListenerSessionConnectRequest,
        ListenerSessionConnectResult,
        ListenerStartRequest,
        ListenerStartResult,
        QueuePromptResult,
        QueueVisualRunContext,
    )
    from substitute.application.danbooru.image_preview_service import (
        DanbooruImagePreviewClient,
        DanbooruImagePreviewService,
    )
    from substitute.application.danbooru.preferences_service import (
        DanbooruPreferenceService,
    )
    from substitute.application.danbooru.recent_posts_service import (
        DanbooruRecentPostsClient,
        DanbooruRecentPostsService,
    )
    from substitute.application.danbooru.url_import_service import (
        DanbooruPostLookupClient,
        DanbooruUrlImportService,
    )
    from substitute.application.danbooru.wiki_content_service import (
        DanbooruWikiContentClient,
        DanbooruWikiContentService,
    )
    from substitute.application.execution import TaskSubmitter
    from substitute.infrastructure.external.danbooru_client import DanbooruClient
    from substitute.application.model_metadata import (
        CivitaiMetadataGateway,
        RichChoiceResolver,
    )
    from substitute.application.prompt_editor.effective_scheduled_lora_provider import (
        RecipeWorkflowSerializer,
        WorkflowPayloadCompiler,
    )
    from substitute.application.prompt_editor import (
        PromptLoraCatalogLookup,
        PromptScheduledLora,
        PromptScheduledLoraService,
        ScheduledLoraProvider,
        WorkflowPromptContext,
    )
    from substitute.application.ports import (
        DanbooruCacheRepository,
        NodeDefinitionGateway,
        NodeDefinitionRefreshObserver,
    )
    from substitute.domain.comfy_runtime import ComfyRuntimeInfo
    from substitute.domain.danbooru import (
        DanbooruMediaAssetLookupResult,
        DanbooruPostLookupResult,
        DanbooruPostRecord,
        DanbooruTagLookupResult,
        DanbooruWikiPageLookupResult,
    )
    from substitute.domain.model_metadata import CivitaiImage, ThumbnailStoreResult
    from substitute.domain.model_metadata import CivitaiLookupResult
    from substitute.app.bootstrap.custom_window import CustomWindow
    from substitute.infrastructure.comfy.cube_library_event_listener import (
        CubeLibraryEventListener,
    )
    from substitute.infrastructure.comfy.model_catalog_event_listener import (
        ModelCatalogEventListener,
    )
    from substitute.presentation.onboarding import OnboardingFlowMode, OnboardingWindow
    from substitute.presentation.shell.window_frame import ShellBackdropMode


class _ShellMainWindowProtocol(Protocol):
    """Describe the MainWindow surface reused during shell-frame reload."""

    workflow_tabbar: QWidget
    workspace_controller: Any
    workspace_generation_actions: Any
    generation_action_controller: Any
    generation_queue_controller: Any
    comfy_runtime_actions: Any
    shell_frame_integration_controller: Any
    comfy_output_panel_visibility_changed: Any


class GenerationQueueTransitionRelay(QObject):
    """Relay queue state transitions back onto the Qt owner thread."""

    transition_requested = Signal(object)

    def __init__(self) -> None:
        """Connect the signal bridge to execute scheduled callbacks."""

        super().__init__()
        self.transition_requested.connect(lambda callback: callback())

    def schedule(self, callback: Callable[[], None]) -> None:
        """Schedule one queue transition through Qt signal delivery."""

        self.transition_requested.emit(callback)


class _LazyComfyGateway:
    """Defer Comfy transport imports until generation actually uses the gateway."""

    def __init__(
        self,
        endpoint: ComfyEndpoint,
        *,
        listener_task_factory: Callable[..., object] | None = None,
        listener_preview_image_decoder: Callable[[bytes], object] | None = None,
    ) -> None:
        """Store the endpoint used to construct the concrete transport gateway."""

        self._endpoint = endpoint
        self._listener_task_factory = listener_task_factory
        self._listener_preview_image_decoder = listener_preview_image_decoder
        self._gateway: ComfyGateway | None = None

    def connect_listener_session(
        self,
        request: "ListenerSessionConnectRequest",
    ) -> "ListenerSessionConnectResult":
        """Open a listener session through the concrete gateway on first use."""

        return self._resolve().connect_listener_session(request)

    def queue_prompt(
        self,
        workflow_payload: dict[str, object],
        *,
        client_id: str,
        execution_targets: tuple[str, ...] | None = None,
        preview_method: str | None = None,
        sugar_script: str | None = None,
        visual_context: "QueueVisualRunContext | None" = None,
    ) -> "QueuePromptResult":
        """Queue one workflow through the concrete gateway on first use."""

        return self._resolve().queue_prompt(
            workflow_payload,
            client_id=client_id,
            execution_targets=execution_targets,
            preview_method=preview_method,
            sugar_script=sugar_script,
            visual_context=visual_context,
        )

    def start_listener(
        self,
        request: "ListenerStartRequest",
        callbacks: "ListenerCallbacks",
    ) -> "ListenerStartResult":
        """Start a generation listener through the concrete gateway on first use."""

        return self._resolve().start_listener(request, callbacks)

    def interrupt(self) -> "InterruptResult":
        """Interrupt active generation through the concrete gateway on first use."""

        return self._resolve().interrupt()

    def get_queue(self) -> "ComfyQueueSnapshot":
        """Load the Comfy queue snapshot through the concrete gateway on first use."""

        return self._resolve().get_queue()

    def delete_pending_prompt(self, prompt_id: str) -> "ComfyQueueMutationResult":
        """Delete one queued prompt through the concrete gateway on first use."""

        return self._resolve().delete_pending_prompt(prompt_id)

    def close_listener_session(self, handle: "ListenerSessionHandle") -> None:
        """Close a preconnected listener session through the concrete gateway."""

        self._resolve().close_listener_session(handle)

    def _resolve(self) -> "ComfyGateway":
        """Build and cache the concrete Comfy gateway implementation."""

        if self._gateway is None:
            from substitute.infrastructure.comfy.gateway_adapter import (
                InfrastructureComfyGatewayAdapter,
            )
            from substitute.infrastructure.comfy.prompt_gateway import (
                ComfyPromptGateway,
            )

            self._gateway = InfrastructureComfyGatewayAdapter(
                ComfyPromptGateway(
                    endpoint=self._endpoint,
                    listener_task_factory=self._listener_task_factory,
                    listener_preview_image_decoder=self._listener_preview_image_decoder,
                )
            )
        return self._gateway


class _LazyDanbooruImagePreviewService:
    """Defer Danbooru preview-service imports until a preview is requested."""

    def __init__(
        self,
        *,
        client: "DanbooruImagePreviewClient",
        cache_repository: "DanbooruCacheRepository",
        preference_service: "DanbooruPreferenceService",
        refresh_submitter: "TaskSubmitter",
    ) -> None:
        """Store dependencies needed to construct the concrete preview service."""

        self._client = client
        self._cache_repository = cache_repository
        self._preference_service = preference_service
        self._refresh_submitter = refresh_submitter
        self._service: DanbooruImagePreviewService | None = None

    def resolve_preview_for_reference(
        self,
        *,
        source_kind: str,
        source_id: int,
    ) -> object:
        """Resolve one preview through the concrete service on first use."""

        return self._resolve().resolve_preview_for_reference(
            source_kind=source_kind,
            source_id=source_id,
        )

    def shutdown(self) -> None:
        """Shut down the concrete preview service if it has been created."""

        service = self._service
        if service is not None:
            service.shutdown()

    def _resolve(self) -> "DanbooruImagePreviewService":
        """Build and cache the concrete Danbooru image preview service."""

        if self._service is None:
            from substitute.application.danbooru.image_preview_service import (
                DanbooruImagePreviewService,
            )

            self._service = DanbooruImagePreviewService(
                client=self._client,
                cache_repository=self._cache_repository,
                preference_service=self._preference_service,
                refresh_submitter=self._refresh_submitter,
            )
        return self._service


class _DanbooruUrlImportServiceProtocol(Protocol):
    """Describe the Danbooru URL import service surface used by composition."""

    def classify_url(self, text: str) -> object | None:
        """Classify one pasted text value as a supported Danbooru URL."""

    def import_prompt_from_url(self, text: str) -> object:
        """Import prompt text from one supported Danbooru URL."""


class _DanbooruRecentPostsServiceProtocol(Protocol):
    """Describe the recent-post lookup surface used by composition."""

    def list_recent_visible_post_ids(
        self,
        tag_name: str,
        *,
        desired_count: int = 5,
    ) -> tuple[int, ...]:
        """List recent visible Danbooru post ids for one tag."""


class _DanbooruWikiContentServiceProtocol(Protocol):
    """Describe the Danbooru wiki service surface used by composition."""

    def lookup_selection(self, selection_text: str) -> object:
        """Resolve selected prompt text to wiki lookup content."""

    def lookup_title(self, title: str) -> object:
        """Resolve one wiki title to lookup content."""

    def resolve_sections(self, sections: tuple[object, ...]) -> tuple[object, ...]:
        """Resolve wiki section references to renderable sections."""

    def shutdown(self) -> None:
        """Release service-owned background work."""


class _LazyDanbooruUrlImportService:
    """Defer Danbooru URL import service imports until paste handling needs them."""

    def __init__(self, *, client: "DanbooruPostLookupClient") -> None:
        """Store the client used by the concrete URL import service."""

        self._client = client
        self._service: _DanbooruUrlImportServiceProtocol | None = None

    def classify_url(self, text: str) -> object | None:
        """Classify a URL through the concrete service on first use."""

        return self._resolve().classify_url(text)

    def import_prompt_from_url(self, text: str) -> object:
        """Import prompt text through the concrete service on first use."""

        return self._resolve().import_prompt_from_url(text)

    def _resolve(self) -> _DanbooruUrlImportServiceProtocol:
        """Build and cache the concrete Danbooru URL import service."""

        if self._service is None:
            from substitute.application.danbooru.url_import_service import (
                DanbooruUrlImportService,
            )

            self._service = cast(
                _DanbooruUrlImportServiceProtocol,
                DanbooruUrlImportService(client=self._client),
            )
        return self._service


class _LazyDanbooruRecentPostsService:
    """Defer Danbooru recent-post service imports until wiki galleries need them."""

    def __init__(
        self,
        *,
        client: "DanbooruRecentPostsClient",
        cache_repository: "DanbooruCacheRepository",
        preference_service: "DanbooruPreferenceService",
    ) -> None:
        """Store dependencies for the concrete recent-post service."""

        self._client = client
        self._cache_repository = cache_repository
        self._preference_service = preference_service
        self._service: _DanbooruRecentPostsServiceProtocol | None = None

    def list_recent_visible_post_ids(
        self,
        tag_name: str,
        *,
        desired_count: int = 5,
    ) -> tuple[int, ...]:
        """List recent visible post ids through the concrete service on first use."""

        return self._resolve().list_recent_visible_post_ids(
            tag_name,
            desired_count=desired_count,
        )

    def _resolve(self) -> _DanbooruRecentPostsServiceProtocol:
        """Build and cache the concrete Danbooru recent-post service."""

        if self._service is None:
            from substitute.application.danbooru.recent_posts_service import (
                DanbooruRecentPostsService,
            )

            self._service = cast(
                _DanbooruRecentPostsServiceProtocol,
                DanbooruRecentPostsService(
                    client=self._client,
                    cache_repository=self._cache_repository,
                    preference_service=self._preference_service,
                ),
            )
        return self._service


class _LazyDanbooruWikiContentService:
    """Defer Danbooru wiki service imports until wiki lookup actions need them."""

    def __init__(
        self,
        *,
        client: "DanbooruWikiContentClient",
        cache_repository: "DanbooruCacheRepository",
        preference_service: "DanbooruPreferenceService",
        refresh_submitter: "TaskSubmitter",
    ) -> None:
        """Store dependencies for the concrete wiki content service."""

        self._client = client
        self._cache_repository = cache_repository
        self._preference_service = preference_service
        self._refresh_submitter = refresh_submitter
        self._service: _DanbooruWikiContentServiceProtocol | None = None

    def lookup_selection(self, selection_text: str) -> object:
        """Resolve selected prompt text through the concrete service on first use."""

        return self._resolve().lookup_selection(selection_text)

    def lookup_title(self, title: str) -> object:
        """Resolve one wiki title through the concrete service on first use."""

        return self._resolve().lookup_title(title)

    def resolve_sections(self, sections: tuple[object, ...]) -> tuple[object, ...]:
        """Resolve wiki sections through the concrete service on first use."""

        return self._resolve().resolve_sections(sections)

    def shutdown(self) -> None:
        """Shut down the concrete wiki service if it has been created."""

        service = self._service
        if service is not None:
            service.shutdown()

    def _resolve(self) -> _DanbooruWikiContentServiceProtocol:
        """Build and cache the concrete Danbooru wiki content service."""

        if self._service is None:
            from substitute.application.danbooru.wiki_content_service import (
                DanbooruWikiContentService,
            )
            from substitute.application.danbooru.wiki_inline_resolution_service import (
                DanbooruWikiInlineResolutionService,
            )

            self._service = cast(
                _DanbooruWikiContentServiceProtocol,
                DanbooruWikiContentService(
                    client=self._client,
                    cache_repository=self._cache_repository,
                    preference_service=self._preference_service,
                    inline_resolution_service=DanbooruWikiInlineResolutionService(
                        cache_repository=self._cache_repository
                    ),
                    refresh_submitter=self._refresh_submitter,
                ),
            )
        return self._service


class _LazyScheduledLoraProvider:
    """Defer effective scheduled-LoRA analysis imports until prompt context use."""

    def __init__(
        self,
        *,
        recipe_io_service: "RecipeWorkflowSerializer",
        workflow_export_service: "WorkflowPayloadCompiler",
        prompt_scheduled_lora_service: "PromptScheduledLoraService",
        prompt_lora_catalog_service: "PromptLoraCatalogLookup",
        rich_choice_resolver: "RichChoiceResolver",
        node_definition_gateway: "NodeDefinitionGateway",
        output_dir: Path,
    ) -> None:
        """Store dependencies needed by the concrete scheduled-LoRA provider."""

        self._recipe_io_service = recipe_io_service
        self._workflow_export_service = workflow_export_service
        self._prompt_scheduled_lora_service = prompt_scheduled_lora_service
        self._prompt_lora_catalog_service = prompt_lora_catalog_service
        self._rich_choice_resolver = rich_choice_resolver
        self._node_definition_gateway = node_definition_gateway
        self._output_dir = output_dir
        self._provider: ScheduledLoraProvider | None = None

    def scheduled_loras_for_prompt_context(
        self,
        *,
        workflow_context: "WorkflowPromptContext",
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
        prompt_text: str,
    ) -> tuple["PromptScheduledLora", ...]:
        """Resolve scheduled LoRAs through the concrete provider on first use."""

        provider = self._resolve()
        scheduled_loras = provider.scheduled_loras_for_prompt_context(
            workflow_context=workflow_context,
            cube_alias=cube_alias,
            prompt_node_name=prompt_node_name,
            prompt_field_key=prompt_field_key,
            prompt_text=prompt_text,
        )
        return scheduled_loras

    def _resolve(self) -> "ScheduledLoraProvider":
        """Build and cache the concrete scheduled-LoRA provider."""

        if self._provider is None:
            from substitute.application.prompt_editor.effective_scheduled_lora_provider import (
                EffectiveScheduledLoraProvider,
            )

            self._provider = EffectiveScheduledLoraProvider(
                recipe_io_service=self._recipe_io_service,
                workflow_export_service=self._workflow_export_service,
                prompt_scheduled_lora_service=self._prompt_scheduled_lora_service,
                prompt_lora_catalog_service=self._prompt_lora_catalog_service,
                rich_choice_resolver=self._rich_choice_resolver,
                node_definition_gateway=self._node_definition_gateway,
                output_dir=self._output_dir,
            )
        return self._provider


class _LazyCivitaiClient:
    """Defer CivitAI HTTP client imports until metadata lookup is requested."""

    def __init__(self, *, api_key_provider: Callable[[], str | None]) -> None:
        """Store the API key provider for the concrete CivitAI client."""

        self._api_key_provider = api_key_provider
        self._client: CivitaiMetadataGateway | None = None

    def lookup_model_version_by_hash(self, sha256: str) -> "CivitaiLookupResult":
        """Look up CivitAI metadata through the concrete client on first use."""

        return self._resolve().lookup_model_version_by_hash(sha256)

    def _resolve(self) -> "CivitaiMetadataGateway":
        """Build and cache the concrete CivitAI client."""

        if self._client is None:
            from substitute.infrastructure.external.civitai_client import (
                CivitaiClient,
            )

            self._client = CivitaiClient(api_key_provider=self._api_key_provider)
        return self._client


class _LazyDanbooruClient:
    """Defer Danbooru HTTP client imports until Danbooru features are used."""

    def __init__(self) -> None:
        """Initialize an unresolved Danbooru client holder."""

        self._client: DanbooruClient | None = None

    def get_post_by_id(self, post_id: int) -> "DanbooruPostLookupResult":
        """Return one Danbooru post through the concrete client on first use."""

        return self._resolve().get_post_by_id(post_id)

    def get_post_by_md5(self, md5: str) -> "DanbooruPostLookupResult":
        """Return one Danbooru post by MD5 through the concrete client."""

        return self._resolve().get_post_by_md5(md5)

    def get_wiki_page(self, title: str) -> "DanbooruWikiPageLookupResult":
        """Return one Danbooru wiki page through the concrete client."""

        return self._resolve().get_wiki_page(title)

    def get_media_asset_by_id(self, asset_id: int) -> "DanbooruMediaAssetLookupResult":
        """Return one Danbooru media asset through the concrete client."""

        return self._resolve().get_media_asset_by_id(asset_id)

    def list_posts_by_tag(
        self,
        tag_name: str,
        *,
        limit: int,
        before_post_id: int | None = None,
    ) -> tuple["DanbooruPostRecord", ...]:
        """Return Danbooru posts for one tag through the concrete client."""

        return self._resolve().list_posts_by_tag(
            tag_name,
            limit=limit,
            before_post_id=before_post_id,
        )

    def get_tag_by_name(self, name: str) -> "DanbooruTagLookupResult":
        """Return one Danbooru tag through the concrete client."""

        return self._resolve().get_tag_by_name(name)

    def download_binary(self, url: str) -> bytes | None:
        """Return remote bytes through the concrete client."""

        return self._resolve().download_binary(url)

    def _resolve(self) -> "DanbooruClient":
        """Build and cache the concrete Danbooru client."""

        if self._client is None:
            from substitute.infrastructure.external.danbooru_client import (
                DanbooruClient,
            )

            self._client = DanbooruClient()
        return self._client


class _LazyComfyObjectInfoClient:
    """Defer Comfy object-info HTTP client imports until definitions are needed."""

    def __init__(
        self,
        *,
        endpoint: ComfyEndpoint,
        background_scheduler: Callable[[Callable[[], None]], object],
        shutdown_background_scheduler: Callable[[], None],
    ) -> None:
        """Store construction inputs for the concrete object-info client."""

        self._endpoint = endpoint
        self._background_scheduler = background_scheduler
        self._shutdown_background_scheduler: Callable[[], None] | None = (
            shutdown_background_scheduler
        )
        self._client: Any | None = None
        self._refresh_observers: list[NodeDefinitionRefreshObserver] = []

    def add_refresh_observer(
        self,
        observer: "NodeDefinitionRefreshObserver",
    ) -> Callable[[], None]:
        """Register a refresh observer without resolving the HTTP client."""

        client = self._client
        if client is not None:
            return cast(Callable[[], None], client.add_refresh_observer(observer))
        self._refresh_observers.append(observer)

        def unsubscribe() -> None:
            """Remove the observer before the concrete client is resolved."""

            try:
                self._refresh_observers.remove(observer)
            except ValueError:
                return

        return unsubscribe

    def clear_cache(self) -> None:
        """Clear the concrete cache when the HTTP client has been created."""

        client = self._client
        if client is not None:
            client.clear_cache()

    def shutdown(self) -> None:
        """Release concrete or pending node-definition refresh resources."""

        client = self._client
        if client is not None:
            client.shutdown()
            return
        shutdown_background_scheduler = self._shutdown_background_scheduler
        if shutdown_background_scheduler is not None:
            shutdown_background_scheduler()
            self._shutdown_background_scheduler = None

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return cached node metadata through the concrete client on first use."""

        return cast(dict[str, object], self._resolve().get_node_definition(node_class))

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Fetch required node metadata through the concrete client on first use."""

        return cast(
            dict[str, object],
            self._resolve().get_required_node_definition(node_class),
        )

    def prewarm_node_classes(self, node_classes: Iterable[str]) -> int:
        """Queue background node-definition refreshes on first use."""

        return cast(int, self._resolve().prewarm_node_classes(node_classes))

    def ensure_node_definitions(
        self,
        node_classes: Iterable[str],
    ) -> "NodeDefinitionHydrationResult":
        """Hydrate node definitions through the concrete client on first use."""

        return cast(
            "NodeDefinitionHydrationResult",
            self._resolve().ensure_node_definitions(node_classes),
        )

    def refresh_node_definitions(
        self,
        node_classes: Iterable[str],
    ) -> tuple[str, ...]:
        """Force-refresh affected node definitions through the concrete client."""

        return cast(
            tuple[str, ...],
            self._resolve().refresh_node_definitions(node_classes),
        )

    def _resolve(self) -> Any:
        """Build and cache the concrete Comfy object-info client."""

        if self._client is None:
            from substitute.infrastructure.external.comfy_object_info_client import (
                ComfyObjectInfoClient,
            )

            client = ComfyObjectInfoClient(
                endpoint=self._endpoint,
                background_scheduler=self._background_scheduler,
                shutdown_background_scheduler=self._shutdown_background_scheduler,
            )
            self._shutdown_background_scheduler = None
            for observer in tuple(self._refresh_observers):
                client.add_refresh_observer(observer)
            self._refresh_observers.clear()
            self._client = client
        return self._client


class _LazyModelThumbnailStore:
    """Defer Qt thumbnail persistence imports until thumbnail caching is needed."""

    def __init__(
        self,
        model_metadata_root: Path,
        *,
        timeout_seconds: float = 20.0,
    ) -> None:
        """Store construction inputs for the concrete thumbnail store."""

        self._model_metadata_root = model_metadata_root
        self._timeout_seconds = timeout_seconds
        self._store: Any | None = None

    def cache_thumbnail(
        self,
        *,
        sha256: str,
        image: CivitaiImage,
        selection_policy: str,
    ) -> ThumbnailStoreResult | None:
        """Download and cache one remote thumbnail through the concrete store."""

        return cast(
            "ThumbnailStoreResult | None",
            self._resolve().cache_thumbnail(
                sha256=sha256,
                image=image,
                selection_policy=selection_policy,
            ),
        )

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
    ) -> ThumbnailStoreResult | None:
        """Cache one local thumbnail through the concrete store."""

        return cast(
            "ThumbnailStoreResult | None",
            self._resolve().cache_local_thumbnail(
                sha256=sha256,
                image=image,
                source=source,
                source_label=source_label,
                source_path=source_path,
                source_width=source_width,
                source_height=source_height,
            ),
        )

    def _resolve(self) -> Any:
        """Build and cache the concrete thumbnail store on first use."""

        if self._store is None:
            from substitute.infrastructure.persistence.model_thumbnail_store import (
                ModelThumbnailStore,
            )

            self._store = ModelThumbnailStore(
                self._model_metadata_root,
                timeout_seconds=self._timeout_seconds,
            )
        return self._store


class _LazyModelCatalogSnapshotStore:
    """Defer model catalog snapshot SQLite setup until snapshots are used."""

    def __init__(self, model_metadata_root: Path) -> None:
        """Store the model metadata root for later snapshot-store construction."""

        self._model_metadata_root = model_metadata_root
        self._store: Any | None = None

    def load_snapshot(self, kind: str) -> "ModelCatalogSnapshot | None":
        """Load the newest durable snapshot through the concrete store on first use."""

        return cast("ModelCatalogSnapshot | None", self._resolve().load_snapshot(kind))

    def save_snapshot(self, snapshot: "ModelCatalogSnapshot") -> None:
        """Persist a durable snapshot through the concrete store on first use."""

        self._resolve().save_snapshot(snapshot)

    def _resolve(self) -> Any:
        """Build and cache the concrete SQLite snapshot store."""

        if self._store is None:
            from substitute.infrastructure.persistence.sqlite_model_catalog_snapshot_store import (
                SqliteModelCatalogSnapshotStore,
            )

            self._store = SqliteModelCatalogSnapshotStore(self._model_metadata_root)
        return self._store


def _custom_window_class() -> type[CustomWindow]:
    """Return the shell frame class without importing it during module load."""

    existing = globals().get("CustomWindow")
    if existing is not None:
        return cast(type[CustomWindow], existing)
    from substitute.app.bootstrap.custom_window import CustomWindow as window_class

    globals()["CustomWindow"] = window_class
    return window_class


def __getattr__(name: str) -> object:
    """Resolve shell-frame exports lazily for legacy composition callers."""

    if name == "CustomWindow":
        return _custom_window_class()
    if name in {
        "ShellBackdropMode",
        "SubstituteWindowFrame",
        "titlebar_menu_content_insert_index",
    }:
        from substitute.presentation.shell import window_frame

        value = getattr(window_frame, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _decode_generation_preview_image_to_qimage(image_bytes: bytes) -> object:
    """Decode Comfy preview bytes into the Qt image type expected by the shell."""

    return preview_image_to_qimage(decode_preview_image(image_bytes))


def _create_generation_listener_task(
    *,
    runtime_services: ApplicationRuntimeServices,
    dispatcher: QtOwnerThreadDispatcher,
    identity: TaskIdentity,
    context: ExecutionContext,
    work: LongLivedWork[None],
    thread_name: str,
) -> LongLivedTaskHandle[None]:
    """Create and register one long-lived generation listener task."""

    key = f"{identity.domain}:{identity.request_id}"
    return runtime_services.execution_runtime.start_long_lived(
        "generation_listener",
        key,
        identity=identity,
        context=context,
        work=work,
        dispatcher=dispatcher,
        thread_name=thread_name,
    )


def _create_backend_event_listener_task(
    *,
    runtime_services: ApplicationRuntimeServices,
    registry_key: str,
    identity: TaskIdentity,
    context: ExecutionContext,
    work: LongLivedWork[None],
    thread_name: str,
) -> LongLivedTaskHandle[None]:
    """Create and register one long-lived backend event listener task."""

    return runtime_services.execution_runtime.start_long_lived(
        "backend_event_listener",
        registry_key,
        identity=identity,
        context=context,
        work=work,
        dispatcher=DirectExecutionDispatcher(),
        thread_name=thread_name,
    )


class _SettingsModelMetadataProgressSink:
    """Log Settings-triggered metadata refresh progress without touching widgets."""

    def __init__(self, on_model_updated: Callable[[], None]) -> None:
        """Store the model-catalog invalidation callback."""

        self._on_model_updated = on_model_updated

    def emit_line(self, line: str) -> None:
        """Log one refresh progress line."""

        log_debug(_LOGGER, "Settings CivitAI metadata refresh progress", line=line)

    def emit_progress(self, line: str) -> None:
        """Log transient refresh progress."""

        log_debug(_LOGGER, "Settings CivitAI metadata refresh progress", line=line)

    def emit_model_updated(self, event: object) -> None:
        """Invalidate model catalog snapshots after a metadata update."""

        log_debug(
            _LOGGER,
            "Settings CivitAI metadata refresh updated model",
            event=repr(event),
        )
        self._on_model_updated()


def create_application(argv: Sequence[str]) -> QApplication:
    """Create and configure the QApplication instance."""
    configure_windows_app_user_model_id()
    app = QApplication(list(argv))
    app.setWindowIcon(application_icon())
    try:
        app.setQuitOnLastWindowClosed(True)
    except Exception:
        log_warning(_LOGGER, "Failed to enforce quit-on-last-window-closed")
    return app


def configure_windows_app_user_model_id(
    *,
    platform: str | None = None,
    shell32: object | None = None,
) -> None:
    """Set stable Windows taskbar identity before Qt creates application windows."""

    resolved_platform = sys.platform if platform is None else platform
    if resolved_platform != "win32":
        return
    if shell32 is None and os.environ.get(DISABLE_WINDOWS_APP_USER_MODEL_ID_ENV):
        return
    resolved_shell32 = shell32 if shell32 is not None else _windows_shell32()
    set_app_user_model_id = getattr(
        resolved_shell32,
        "SetCurrentProcessExplicitAppUserModelID",
        None,
    )
    if not callable(set_app_user_model_id):
        log_warning(_LOGGER, "Windows shell AppUserModelID API is unavailable")
        return
    try:
        result = int(cast(Any, set_app_user_model_id)(WINDOWS_APP_USER_MODEL_ID))
    except (OSError, TypeError, ValueError) as error:
        log_warning(
            _LOGGER,
            "Failed to set Windows AppUserModelID",
            error=repr(error),
            app_user_model_id=WINDOWS_APP_USER_MODEL_ID,
        )
        return
    if result != 0:
        log_warning(
            _LOGGER,
            "Windows AppUserModelID API returned failure",
            hresult=result,
            app_user_model_id=WINDOWS_APP_USER_MODEL_ID,
        )


def _windows_shell32() -> object | None:
    """Return the Windows shell32 library object when available."""

    import ctypes

    windll = getattr(ctypes, "windll", None)
    if windll is None:
        return None
    return cast(object | None, getattr(windll, "shell32", None))


def build_appearance_runtime(
    context: InstallationContext,
) -> AppearanceRuntimeController:
    """Build the appearance runtime controller for one installation context."""

    preference_service = AppearancePreferenceService(
        FileAppearancePreferenceRepository(context.user_settings_dir)
    )
    return AppearanceRuntimeController(
        preference_service=preference_service,
        system_appearance_provider=build_system_appearance_provider(),
        resolver=AppearanceResolver(probe_window_material_capabilities()),
    )


def configure_theme(
    appearance_runtime: AppearanceRuntimeController,
) -> ResolvedAppearance:
    """Apply persisted project appearance settings to QFluent."""

    return appearance_runtime.apply_persisted_preferences()


def _configure_control_registry_service() -> None:
    """Bind control-registry infrastructure adapters into application service layer."""

    from substitute.application.overrides.control_registry_service import (
        configure_control_registry_service,
    )
    from substitute.infrastructure.controls.registry import (
        get_registry,
        register_builtin_control_builders,
    )

    def _lookup_builder(control: str) -> Callable[..., object] | None:
        """Resolve control-name widget builder from infrastructure registry."""

        return cast(Callable[..., object] | None, get_registry().get(control))

    configure_control_registry_service(
        widget_builder_lookup=_lookup_builder,
        builtin_control_registrar=register_builtin_control_builders,
    )


def _build_comfy_asset_staging_service(
    context: InstallationContext,
    *,
    input_asset_staging_plan_service: Any | None = None,
) -> Any:
    """Compose target-specific Comfy asset staging at the bootstrap boundary."""

    from substitute.application.generation.asset_staging_service import (
        ComfyAssetStagingService,
    )
    from substitute.application.ports.comfy_asset_stager import ComfyAssetStager
    from substitute.domain.onboarding import ComfyTargetMode
    from substitute.infrastructure.comfy import (
        LocalComfyAssetStager,
        RemoteUploadComfyAssetStager,
    )

    if context.comfy_target.mode is ComfyTargetMode.REMOTE:
        stager: ComfyAssetStager = RemoteUploadComfyAssetStager(
            endpoint=context.comfy_target.endpoint
        )
    else:
        stager = LocalComfyAssetStager()
    return ComfyAssetStagingService.with_projects_dir(
        stager=stager,
        projects_dir=context.projects_dir,
        input_asset_staging_plan_service=input_asset_staging_plan_service,
    )


def _build_main_window_dependencies(
    runtime_services: ApplicationRuntimeServices,
) -> Any:
    """Compose typed MainWindow dependencies at bootstrap boundary."""
    trace_mark("composition.dependencies.compose.enter")
    phase_started_at = perf_counter()

    def record_dependency_phase(name: str) -> None:
        """Record elapsed time for one dependency composition phase."""

        nonlocal phase_started_at
        now = perf_counter()
        trace_mark(
            "composition.dependencies.phase",
            phase=name,
            elapsed_ms=round((now - phase_started_at) * 1000, 3),
        )
        phase_started_at = now

    def record_dependency_checkpoint(name: str, started_at: float) -> None:
        """Record a nested dependency timing without resetting phase attribution."""

        trace_mark(
            "composition.dependencies.phase",
            phase=name,
            elapsed_ms=round((perf_counter() - started_at) * 1000, 3),
        )

    from substitute.application.cubes import CubeLoadService
    from substitute.application.cube_library import CubeLibraryManagementService

    record_dependency_phase("imports.application.cubes")

    from substitute.application.danbooru.preferences_service import (
        DanbooruPreferenceService,
    )

    record_dependency_phase("imports.application.danbooru.preferences")

    from substitute.application.civitai import (
        CivitaiCacheService,
        CivitaiCredentialService,
        CivitaiPreferenceService,
    )

    record_dependency_phase("imports.application.civitai")

    from substitute.domain.civitai import CivitaiThumbnailSafetyPolicy
    from substitute.domain.model_metadata import (
        BackendModelDownloadResult,
        CivitaiFile,
        CivitaiImage,
        CivitaiModelVersion,
        CivitaiThumbnailPolicy,
        LocalModelEvidence,
        ModelMetadataCacheRecord,
        ThumbnailSelectionStatus,
    )

    record_dependency_phase("imports.application.domain_metadata")

    from substitute.application.generation.job_queue_service import (
        GenerationJobQueueService,
    )

    record_dependency_phase("imports.application.generation.queue")

    from substitute.application.generation.preview_preference_service import (
        GenerationPreviewPreferenceService,
    )

    record_dependency_phase("imports.application.generation.preview_preferences")

    from substitute.application.generation.generation_result_snapshot_service import (
        GenerationResultSnapshotService,
    )

    record_dependency_phase("imports.application.generation.result_snapshot")

    from substitute.application.generation.generation_service import GenerationService
    from substitute.application.direct_workflows import (
        DirectWorkflowGenerationPlanService,
    )

    record_dependency_phase("imports.application.generation.service")

    from substitute.application.generation.output_preference_service import (
        OutputPreferenceService,
    )

    record_dependency_phase("imports.application.generation.output_organization")

    from substitute.application.generation.progress_service import ProgressService

    record_dependency_phase("imports.application.generation.progress")

    from substitute.application.generation.recipe_output_sibling_discovery_service import (
        RecipeOutputSiblingDiscoveryService,
    )

    record_dependency_phase("imports.application.generation.recipe_output_sibling")

    from substitute.application.node_behavior import (
        ModelBackedNodeDetector,
        NodeBehaviorService,
    )

    record_dependency_phase("imports.application.node_behavior")

    from substitute.application.overrides import PinnedOverrideService

    record_dependency_phase("imports.application.overrides")

    from substitute.application.model_metadata import (
        ManualModelMetadataRefreshService,
        ModelCatalogService,
        ModelChoiceCatalogIndex,
        ModelMetadataRefreshService,
        RichChoiceResolver,
        ScopedMetadataRefreshService,
        SetModelThumbnailFromOutputService,
    )

    record_dependency_phase("imports.application.model_metadata")

    from substitute.application.prompt_editor.prompt_editor_preference_service import (
        PromptEditorPreferenceService,
    )

    record_dependency_phase("imports.application.prompt_editor.preferences")

    from substitute.application.prompt_editor.prompt_feature_profile_service import (
        PromptFeatureProfileService,
    )

    record_dependency_phase("imports.application.prompt_editor.feature_profile")

    from substitute.application.prompt_editor.prompt_lora_catalog_service import (
        PromptLoraCatalogService,
    )

    record_dependency_phase("imports.application.prompt_editor.lora_catalog")

    from substitute.application.prompt_editor.prompt_scheduled_lora_service import (
        PromptScheduledLoraService,
    )

    record_dependency_phase("imports.application.prompt_editor.scheduled_lora")

    from substitute.application.prompt_editor.prompt_spellcheck_candidates import (
        PromptSpellcheckCandidateService,
    )

    record_dependency_phase("imports.application.prompt_editor.spellcheck_candidates")

    from substitute.application.prompt_editor.prompt_spellcheck_service import (
        PromptSpellcheckService,
    )

    record_dependency_phase("imports.application.prompt_editor.spellcheck")

    from substitute.domain.prompt import PromptEditorFeature

    record_dependency_phase("imports.application.prompt_editor.domain_feature")

    from substitute.application.prompt_wildcards import (
        PromptWildcardFileManagementService,
        PromptWildcardPreferenceService,
        PromptWildcardPreprocessingService,
    )

    record_dependency_phase("imports.application.prompt_wildcards")

    from substitute.application.recipes import (
        CachedPromptLoraHashLookup,
        CachedRecipeModelHashLookup,
        RecipeIoService,
        RecipeModelDownloadResolutionService,
        RecipeModelLoadResolver,
        RecipeModelResolutionIndex,
        WorkflowExportService,
    )

    record_dependency_phase("imports.application.recipes")

    from substitute.application.user_presets import UserPresetService

    record_dependency_phase("imports.application.user_presets")

    from substitute.application.workflows import (
        AssetRevealService,
        CanvasIoService,
        WorkflowAssetService,
    )
    from substitute.application.workflows.input_asset_endpoint_service import (
        InputAssetEndpointService,
    )
    from substitute.application.workflows.input_canvas_plan_service import (
        InputCanvasPlanService,
    )
    from substitute.application.workflows.workflow_graph_section_service import (
        WorkflowGraphSectionService,
    )
    from substitute.application.workflows.workflow_node_definition_service import (
        WorkflowNodeDefinitionService,
    )

    record_dependency_phase("imports.application.workflows")

    from substitute.application.onboarding import (
        ComfyConnectionSettingsService,
        ComfyTargetService,
    )

    record_dependency_phase("imports.application.onboarding")

    from substitute.application.restart_requirements import RestartRequirementService

    record_dependency_phase("imports.application.restart_requirements")

    from substitute.infrastructure.cubes.backend_cube_repository import (
        BackendCubeRepository,
    )

    record_dependency_phase("imports.infrastructure.cube_repository")

    from substitute.infrastructure.external.photoshop_gateway import PhotoshopGateway

    record_dependency_phase("imports.infrastructure.external.photoshop")

    from substitute.infrastructure.external.native_file_manager_gateway import (
        NativeFileManagerGateway,
    )

    record_dependency_phase("imports.infrastructure.external.file_manager")

    from substitute.infrastructure.external.substitute_backend_cube_icon_asset_client import (
        SubstituteBackendCubeIconAssetClient,
    )

    record_dependency_phase("imports.infrastructure.external.cube_icon_asset")

    from substitute.infrastructure.external.substitute_backend_cube_library_client import (
        SubstituteBackendCubeLibraryClient,
    )

    record_dependency_phase("imports.infrastructure.external.cube_library")

    from substitute.infrastructure.external.substitute_backend_environment_client import (
        SubstituteBackendEnvironmentClient,
    )

    record_dependency_phase("imports.infrastructure.external.environment")

    from substitute.infrastructure.external.substitute_backend_model_metadata_client import (
        SubstituteBackendModelMetadataClient,
    )

    record_dependency_phase("imports.infrastructure.external.model_metadata")

    from substitute.infrastructure.external.substitute_backend_preview_assets_client import (
        SubstituteBackendPreviewAssetsClient,
    )

    record_dependency_phase("imports.infrastructure.external.preview_assets")

    from substitute.infrastructure.external.substitute_backend_sugar_compile_client import (
        BackendSugarWorkflowPayloadCompiler,
        SubstituteBackendSugarCompileClient,
    )

    record_dependency_phase("imports.infrastructure.external.sugar_compile")

    from substitute.infrastructure.onboarding import (
        FileComfyTargetConfigurationRepository,
    )
    from substitute.infrastructure.onboarding.readiness_checks import (
        FileSystemReadinessChecks,
    )
    from substitute.infrastructure.persistence.file_danbooru_preference_repository import (
        FileDanbooruPreferenceRepository,
    )

    record_dependency_phase("imports.infrastructure.persistence.danbooru_preferences")

    from substitute.infrastructure.persistence.file_civitai_preference_repository import (
        FileCivitaiPreferenceRepository,
    )

    record_dependency_phase("imports.infrastructure.persistence.civitai_preferences")

    from substitute.infrastructure.persistence.file_prompt_autocomplete_gateway import (
        FilePromptAutocompleteGateway,
    )
    from substitute.infrastructure.persistence.configured_prompt_autocomplete_gateway import (
        ConfiguredPromptAutocompleteGateway,
    )
    from substitute.infrastructure.persistence.file_prompt_autocomplete_list_repository import (
        FilePromptAutocompleteListRepository,
    )
    from substitute.application.prompt_autocomplete_lists import (
        PromptAutocompleteListService,
    )

    record_dependency_phase("imports.infrastructure.persistence.prompt_autocomplete")

    from substitute.infrastructure.persistence.file_prompt_editor_preference_repository import (
        FilePromptEditorPreferenceRepository,
    )

    record_dependency_phase(
        "imports.infrastructure.persistence.prompt_editor_preferences"
    )

    from substitute.infrastructure.persistence.file_generation_preview_preference_repository import (
        FileGenerationPreviewPreferenceRepository,
    )

    record_dependency_phase(
        "imports.infrastructure.persistence.generation_preview_preferences"
    )

    from substitute.infrastructure.persistence.file_output_preference_repository import (
        FileOutputPreferenceRepository,
    )

    record_dependency_phase(
        "imports.infrastructure.persistence.output_organization_preferences"
    )

    from substitute.infrastructure.persistence.file_prompt_wildcard_catalog_gateway import (
        FilePromptWildcardCatalogGateway,
    )

    record_dependency_phase(
        "imports.infrastructure.persistence.prompt_wildcard_catalog"
    )

    from substitute.infrastructure.persistence.file_prompt_wildcard_file_repository import (
        FilePromptWildcardFileRepository,
    )

    record_dependency_phase("imports.infrastructure.persistence.prompt_wildcard_file")

    from substitute.infrastructure.persistence.file_prompt_wildcard_preference_repository import (
        FilePromptWildcardPreferenceRepository,
    )

    record_dependency_phase(
        "imports.infrastructure.persistence.prompt_wildcard_preferences"
    )

    from substitute.infrastructure.persistence.file_recipe_repository import (
        FileRecipeRepository,
    )
    from substitute.infrastructure.persistence.file_workflow_repository import (
        FileWorkflowRepository,
    )

    record_dependency_phase("imports.infrastructure.persistence.recipe_workflow")

    from substitute.infrastructure.persistence.output_run_number_allocator import (
        FileOutputRunNumberAllocator,
    )

    record_dependency_phase("imports.infrastructure.persistence.output_run_number")

    from substitute.infrastructure.persistence.user_presets_json_repository import (
        JsonUserPresetRepository,
    )

    record_dependency_phase("imports.infrastructure.persistence.user_presets")

    record_dependency_phase("imports.infrastructure.persistence.model_thumbnail")

    from substitute.infrastructure.persistence.image_store import QtImageStore

    record_dependency_phase("imports.infrastructure.persistence.image_store")

    from substitute.infrastructure.persistence.danbooru_cache_store import (
        SqliteDanbooruCacheStore,
    )

    record_dependency_phase("imports.infrastructure.persistence.danbooru_cache")

    from substitute.infrastructure.persistence.sqlite_cube_classification_cache import (
        SqliteCubeClassificationCache,
    )
    from substitute.infrastructure.persistence.sqlite_cube_icon_cache import (
        SqliteCubeIconCache,
    )

    record_dependency_phase("imports.infrastructure.persistence.cube_sqlite")

    from substitute.infrastructure.persistence.sqlite_model_metadata_store import (
        SqliteModelMetadataStore,
    )

    record_dependency_phase("imports.infrastructure.persistence.model_sqlite")

    from substitute.infrastructure.security import build_civitai_credential_store

    record_dependency_phase("imports.infrastructure.security")

    from substitute.infrastructure.spellcheck import (
        build_spellcheck_gateway,
        default_spellcheck_language_tag,
    )

    record_dependency_phase("imports.infrastructure.spellcheck")

    from substitute.presentation.shell.main_window_dependencies import (
        InstallationPathBundle,
        MainWindowDependencies,
    )
    from substitute.presentation.shell.shell_resource_lifecycle import (
        ShellResourceLifecycle,
    )
    from substitute.presentation.managed_text_assets import (
        AutocompleteListManagementOpener,
        WildcardManagementOpener,
    )
    from substitute.presentation.shell.workspace_generation_controller import (
        GenerationPreparationExecutor,
        WorkspaceGenerationController,
    )
    from substitute.presentation.shell.model_metadata_context_action_handler import (
        ModelMetadataContextActionScheduler,
    )
    from substitute.presentation.shell.output_canvas_thumbnail_choices import (
        ProjectionOutputCanvasThumbnailChoiceProvider,
    )
    from substitute.presentation.shell.model_metadata_update_bridge import (
        ModelMetadataUpdateBridge,
    )
    from substitute.presentation.resources.cube_icon_factory import CubeIconFactory

    record_dependency_phase("imports.presentation")

    context = runtime_services.context
    appearance_runtime = runtime_services.appearance_runtime
    comfy_output_stream = runtime_services.comfy_output_stream
    shell_resource_lifecycle = ShellResourceLifecycle()
    recipe_repository = FileRecipeRepository()
    workflow_repository = FileWorkflowRepository()
    cube_library_backend = SubstituteBackendCubeLibraryClient(
        context.comfy_target.endpoint
    )
    cube_icon_asset_client = SubstituteBackendCubeIconAssetClient(
        context.comfy_target.endpoint
    )
    sugar_compile_client = SubstituteBackendSugarCompileClient(
        context.comfy_target.endpoint
    )
    workflow_payload_compiler = BackendSugarWorkflowPayloadCompiler(
        client=sugar_compile_client
    )
    cube_repository = BackendCubeRepository(client=cube_library_backend)
    progress_service = ProgressService()
    cube_cache_target_key = _cube_cache_target_key(context)
    cube_icon_cache = SqliteCubeIconCache(context.cache_dir / "cube")
    cube_classification_cache = SqliteCubeClassificationCache(
        context.cache_dir / "cube"
    )
    cube_icon_factory = CubeIconFactory(
        asset_fetcher=cube_icon_asset_client,
        rendered_cache=cube_icon_cache,
        target_key=cube_cache_target_key,
    )
    cube_load_service = CubeLoadService(
        cube_repository=cube_repository,
        classification_cache=cube_classification_cache,
        target_key=cube_cache_target_key,
        icon_cache_invalidator=lambda: _invalidate_cube_icon_cache(
            cube_icon_factory=cube_icon_factory,
            cube_icon_cache=cube_icon_cache,
            target_key=cube_cache_target_key,
        ),
    )
    graph_section_service = WorkflowGraphSectionService()
    image_store = QtImageStore()
    photoshop_gateway = PhotoshopGateway()
    asset_reveal_service = AssetRevealService(NativeFileManagerGateway())
    canvas_io_service = CanvasIoService(
        image_repository=image_store,
        external_image_gateway=photoshop_gateway,
    )
    workflow_asset_service = WorkflowAssetService(graph_section_service)
    record_dependency_phase("cube_canvas_services")
    generation_queue_transition_relay = GenerationQueueTransitionRelay()
    generation_listener_dispatcher = QtOwnerThreadDispatcher(
        generation_queue_transition_relay
    )
    comfy_gateway = _LazyComfyGateway(
        context.comfy_target.endpoint,
        listener_task_factory=(
            lambda identity, task_context, work, thread_name: (
                _create_generation_listener_task(
                    runtime_services=runtime_services,
                    dispatcher=generation_listener_dispatcher,
                    identity=identity,
                    context=task_context,
                    work=work,
                    thread_name=thread_name,
                )
            )
        ),
        listener_preview_image_decoder=_decode_generation_preview_image_to_qimage,
    )
    node_definition_step_started_at = perf_counter()
    node_definition_submitter = runtime_services.execution_runtime.submitter(
        "node_definition",
        owner_id="node_definition_cache",
        dispatcher=DirectExecutionDispatcher(),
    )
    record_dependency_checkpoint(
        "comfy_node_definition_services.submitter",
        node_definition_step_started_at,
    )
    node_definition_step_started_at = perf_counter()
    node_definition_scope = TaskScope(
        submitter=node_definition_submitter,
        scope_id="node_definition_cache",
    )
    record_dependency_checkpoint(
        "comfy_node_definition_services.scope",
        node_definition_step_started_at,
    )
    node_definition_request_id = 0

    node_definition_step_started_at = perf_counter()

    def schedule_node_definition_refresh(callback: Callable[[], None]) -> object:
        """Schedule one node-definition cache refresh through the app runtime."""

        nonlocal node_definition_request_id
        node_definition_request_id += 1
        return node_definition_scope.submit(
            TaskRequest(
                identity=TaskIdentity(
                    request_id=node_definition_request_id,
                    domain="node_definition",
                    parts=(("operation_key", "refresh_node_class"),),
                ),
                context=ExecutionContext(
                    operation="refresh_node_class",
                    reason="node_definition_cache_miss",
                    lane="node_definition",
                    safe_fields=(("operation_key", "refresh_node_class"),),
                ),
                work=lambda _token: callback(),
            )
        )

    def shutdown_node_definition_refresh() -> None:
        """Release node-definition refresh execution owned by composition."""

        node_definition_scope.close(reason="node_definition_cache_shutdown")
        node_definition_submitter.close()

    record_dependency_checkpoint(
        "comfy_node_definition_services.callbacks",
        node_definition_step_started_at,
    )
    node_definition_step_started_at = perf_counter()
    node_definition_gateway = _LazyComfyObjectInfoClient(
        endpoint=context.comfy_target.endpoint,
        background_scheduler=schedule_node_definition_refresh,
        shutdown_background_scheduler=shutdown_node_definition_refresh,
    )
    workflow_node_definition_service = WorkflowNodeDefinitionService(
        node_definition_gateway
    )
    input_asset_endpoint_service = InputAssetEndpointService(
        workflow_node_definition_service
    )
    input_canvas_plan_service = InputCanvasPlanService(
        node_definition_service=workflow_node_definition_service,
        endpoint_service=input_asset_endpoint_service,
    )
    from substitute.application.generation.input_asset_staging_plan_service import (
        InputAssetStagingPlanService,
    )

    input_asset_staging_plan_service = InputAssetStagingPlanService(
        input_asset_endpoint_service,
        graph_section_service,
    )
    comfy_asset_staging_service = _build_comfy_asset_staging_service(
        context,
        input_asset_staging_plan_service=input_asset_staging_plan_service,
    )
    shell_resource_lifecycle.register(
        "node_definition_cache",
        node_definition_gateway.shutdown,
    )
    record_dependency_checkpoint(
        "comfy_node_definition_services.gateway",
        node_definition_step_started_at,
    )
    node_definition_step_started_at = perf_counter()
    workflow_export_service = WorkflowExportService(
        workflow_repository=workflow_repository,
        workflow_payload_compiler=workflow_payload_compiler,
        node_definition_gateway=node_definition_gateway,
    )
    record_dependency_checkpoint(
        "comfy_node_definition_services.workflow_export",
        node_definition_step_started_at,
    )
    record_dependency_phase("comfy_node_definition_services")
    bundled_prompt_autocomplete_gateway = FilePromptAutocompleteGateway()
    prompt_autocomplete_list_service = PromptAutocompleteListService(
        FilePromptAutocompleteListRepository(context.user_dir)
    )
    prompt_autocomplete_gateway = ConfiguredPromptAutocompleteGateway(
        bundled_prompt_autocomplete_gateway,
        prompt_autocomplete_list_service,
    )
    prompt_autocomplete_list_service.set_change_callback(
        prompt_autocomplete_gateway.refresh
    )
    prompt_autocomplete_gateway.load_prompt_tag_snapshot()
    danbooru_client = _LazyDanbooruClient()
    danbooru_cache_repository = SqliteDanbooruCacheStore(context.cache_dir / "danbooru")
    danbooru_preference_service = DanbooruPreferenceService(
        FileDanbooruPreferenceRepository(context.user_settings_dir)
    )

    def connected_civitai_preview_root() -> Path:
        """Resolve the active Comfy model root only when Settings needs a preview."""

        status = SubstituteBackendEnvironmentClient(
            context.comfy_target.endpoint
        ).get_model_root()
        if status is None or context.comfy_target.workspace_path is None:
            return Path("models") / "diffusion_models"
        return Path(status.active_model_root) / "diffusion_models"

    civitai_preference_service = CivitaiPreferenceService(
        FileCivitaiPreferenceRepository(context.user_settings_dir),
        preview_comfy_root=connected_civitai_preview_root,
    )
    civitai_credential_service = CivitaiCredentialService(
        build_civitai_credential_store(context.user_settings_dir)
    )
    danbooru_url_import_service = _LazyDanbooruUrlImportService(client=danbooru_client)
    danbooru_wiki_refresh_submitter = runtime_services.execution_runtime.submitter(
        "danbooru_refresh",
        owner_id=f"danbooru_wiki_refresh_{id(danbooru_cache_repository):x}",
        dispatcher=DirectExecutionDispatcher(),
    )
    danbooru_wiki_service = _LazyDanbooruWikiContentService(
        client=danbooru_client,
        cache_repository=danbooru_cache_repository,
        preference_service=danbooru_preference_service,
        refresh_submitter=danbooru_wiki_refresh_submitter,
    )
    shell_resource_lifecycle.register(
        "danbooru_wiki_refresh_route",
        danbooru_wiki_refresh_submitter.close,
    )
    shell_resource_lifecycle.register(
        "danbooru_wiki_service",
        danbooru_wiki_service.shutdown,
    )
    danbooru_image_refresh_submitter = runtime_services.execution_runtime.submitter(
        "danbooru_refresh",
        owner_id=f"danbooru_image_refresh_{id(danbooru_cache_repository):x}",
        dispatcher=DirectExecutionDispatcher(),
    )
    danbooru_image_preview_service = _LazyDanbooruImagePreviewService(
        client=danbooru_client,
        cache_repository=danbooru_cache_repository,
        preference_service=danbooru_preference_service,
        refresh_submitter=danbooru_image_refresh_submitter,
    )
    shell_resource_lifecycle.register(
        "danbooru_image_refresh_route",
        danbooru_image_refresh_submitter.close,
    )
    shell_resource_lifecycle.register(
        "danbooru_image_preview_service",
        danbooru_image_preview_service.shutdown,
    )
    danbooru_recent_posts_service = _LazyDanbooruRecentPostsService(
        client=danbooru_client,
        cache_repository=danbooru_cache_repository,
        preference_service=danbooru_preference_service,
    )
    prompt_wildcard_catalog_gateway = FilePromptWildcardCatalogGateway(
        user_wildcards_root=context.wildcards_dir,
        comfy_custom_nodes_root=context.active_comfy_custom_nodes_dir,
    )
    prompt_wildcard_preference_service = PromptWildcardPreferenceService(
        FilePromptWildcardPreferenceRepository(context.user_settings_dir)
    )
    prompt_wildcard_file_management_service = PromptWildcardFileManagementService(
        FilePromptWildcardFileRepository(context.wildcards_dir)
    )
    prompt_wildcard_preprocessing_service = PromptWildcardPreprocessingService(
        source_provider=prompt_wildcard_catalog_gateway,
        preference_service=prompt_wildcard_preference_service,
    )
    record_dependency_phase("danbooru_wildcard_services")
    model_recipe_phase_started_at = perf_counter()
    civitai_preferences = civitai_preference_service.load_preferences()
    record_dependency_checkpoint(
        "model_catalog_recipe_services.civitai_preferences",
        model_recipe_phase_started_at,
    )
    model_recipe_step_started_at = perf_counter()
    model_metadata_store = SqliteModelMetadataStore(
        context.model_metadata_dir,
        thumbnail_policy_key=CivitaiThumbnailPolicy(
            civitai_preferences.thumbnail_safety_policy
            if civitai_preferences.thumbnail_downloads_enabled
            else CivitaiThumbnailSafetyPolicy.DISABLED
        ).selection_policy,
    )
    record_dependency_checkpoint(
        "model_catalog_recipe_services.metadata_store",
        model_recipe_step_started_at,
    )
    model_recipe_step_started_at = perf_counter()
    model_thumbnail_store = _LazyModelThumbnailStore(
        context.model_metadata_dir,
        timeout_seconds=5.0,
    )
    record_dependency_checkpoint(
        "model_catalog_recipe_services.thumbnail_store",
        model_recipe_step_started_at,
    )
    model_recipe_step_started_at = perf_counter()
    model_metadata_backend = SubstituteBackendModelMetadataClient(
        context.comfy_target.endpoint
    )
    environment_backend = SubstituteBackendEnvironmentClient(
        context.comfy_target.endpoint
    )
    preview_assets_backend = SubstituteBackendPreviewAssetsClient(
        context.comfy_target.endpoint
    )
    comfy_environment_service = ComfyEnvironmentService(environment_backend)
    record_dependency_checkpoint(
        "model_catalog_recipe_services.backend_clients",
        model_recipe_step_started_at,
    )

    from substitute.infrastructure.comfy.workspace_python_discovery import (
        resolve_attached_comfy_python,
    )

    def fetch_runtime_info() -> "ComfyRuntimeInfo | None":
        """Fetch Comfy runtime facts when the About page requests them."""

        from substitute.infrastructure.comfy.runtime_info_client import (
            fetch_comfy_runtime_info,
        )

        return fetch_comfy_runtime_info(context.comfy_target.endpoint)

    model_recipe_step_started_at = perf_counter()
    about_info_service = AboutInfoService(
        backend_capabilities=model_metadata_backend,
        comfy_runtime_info=fetch_runtime_info,
        local_versions=installed_distribution_version,
    )
    cube_library_management_service = CubeLibraryManagementService(
        endpoint=context.comfy_target.endpoint,
        client=cube_library_backend,
    )
    generation_preview_preference_service = GenerationPreviewPreferenceService(
        FileGenerationPreviewPreferenceRepository(context.user_settings_dir),
        preview_assets_backend,
    )
    output_preference_service = OutputPreferenceService(
        FileOutputPreferenceRepository(context.user_settings_dir),
        default_output_root=context.outputs_dir,
    )
    restart_requirement_service = RestartRequirementService()
    appearance_restart_coordinator = AppearanceRestartCoordinator(
        appearance_runtime=runtime_services.appearance_runtime,
        active_baseline=runtime_services.active_appearance_baseline,
        restart_requirements=restart_requirement_service,
    )
    comfy_connection_settings_service = ComfyConnectionSettingsService(
        target_service=ComfyTargetService(
            FileComfyTargetConfigurationRepository(context.installation)
        ),
        checks=FileSystemReadinessChecks(),
        environment_client_factory=SubstituteBackendEnvironmentClient,
        restart_requirements=restart_requirement_service,
        attached_python_resolver=resolve_attached_comfy_python,
    )
    record_dependency_checkpoint(
        "model_catalog_recipe_services.settings_services",
        model_recipe_step_started_at,
    )
    model_recipe_step_started_at = perf_counter()
    model_catalog_service = ModelCatalogService(
        backend=model_metadata_backend,
        metadata_catalog=model_metadata_store,
        model_metadata_root=context.model_metadata_dir,
        snapshot_store=_LazyModelCatalogSnapshotStore(context.model_metadata_dir),
    )
    prompt_lora_catalog_service = PromptLoraCatalogService(
        model_catalog=model_catalog_service,
    )
    model_hash_lookup = CachedRecipeModelHashLookup(
        model_metadata_store,
        catalog=model_catalog_service,
    )
    record_dependency_checkpoint(
        "model_catalog_recipe_services.catalog_services",
        model_recipe_step_started_at,
    )
    model_recipe_step_started_at = perf_counter()
    recipe_io_service = RecipeIoService(
        recipe_repository=recipe_repository,
        node_definition_gateway=node_definition_gateway,
        cube_definition_provider=cube_load_service,
        model_hash_lookup=model_hash_lookup,
        prompt_lora_hash_lookup=CachedPromptLoraHashLookup(
            prompt_lora_catalog=prompt_lora_catalog_service,
            model_hash_lookup=model_hash_lookup,
        ),
    )
    record_dependency_checkpoint(
        "model_catalog_recipe_services.recipe_services",
        model_recipe_step_started_at,
    )
    record_dependency_phase("model_catalog_recipe_services")
    settings_metadata_refreshes: list[StartupModelMetadataRefreshHandle] = []
    settings_metadata_refresh_request_id = 0

    def shutdown_settings_metadata_refreshes() -> None:
        """Release Settings-triggered metadata refreshes owned by this shell."""

        for handle in tuple(settings_metadata_refreshes):
            handle.shutdown()
        settings_metadata_refreshes.clear()

    shell_resource_lifecycle.register(
        "settings_model_metadata_refreshes",
        shutdown_settings_metadata_refreshes,
    )

    def schedule_settings_metadata_refresh() -> None:
        """Queue one CivitAI metadata refresh from Settings."""

        nonlocal settings_metadata_refresh_request_id

        handle: StartupModelMetadataRefreshHandle

        def finish_refresh() -> None:
            """Release the completed Settings-triggered refresh handle."""

            model_catalog_service.invalidate()
            if handle in settings_metadata_refreshes:
                settings_metadata_refreshes.remove(handle)
            handle.shutdown()

        settings_metadata_refresh_request_id += 1
        settings_metadata_submitter = runtime_services.execution_runtime.submitter(
            "model_metadata",
            owner_id=(
                "settings_model_metadata_refresh_"
                f"{settings_metadata_refresh_request_id}"
            ),
            dispatcher=DirectExecutionDispatcher(),
        )
        handle = StartupModelMetadataRefreshHandle(
            service_factory=lambda: build_model_metadata_refresh_service(context),
            progress_sink=_SettingsModelMetadataProgressSink(
                model_catalog_service.invalidate
            ),
            submitter=settings_metadata_submitter,
            close_submitter=settings_metadata_submitter.close,
            startup_budget_seconds=0.0,
            finished_callback=finish_refresh,
        )
        settings_metadata_refreshes.append(handle)
        handle.start()

    civitai_cache_service = CivitaiCacheService(
        model_metadata_store,
        invalidate_model_catalog=model_catalog_service.invalidate,
        schedule_metadata_refresh=schedule_settings_metadata_refresh,
    )
    model_backed_node_detector = ModelBackedNodeDetector()
    model_choice_resolver = RichChoiceResolver(
        catalog_index=ModelChoiceCatalogIndex(model_catalog=model_catalog_service)
    )
    user_preset_service = UserPresetService(JsonUserPresetRepository(context.user_dir))
    prompt_scheduled_lora_service = PromptScheduledLoraService()
    prompt_editor_preference_service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(context.user_settings_dir)
    )
    editor_panel_execution_factories = create_editor_panel_execution_factories(
        runtime_services.execution_runtime
    )
    open_wildcard_management_modal = WildcardManagementOpener(
        wildcard_file_management_service=prompt_wildcard_file_management_service,
        prompt_autocomplete_gateway=prompt_autocomplete_gateway,
        prompt_wildcard_catalog_gateway=prompt_wildcard_catalog_gateway,
        editor_panel_execution_factories=editor_panel_execution_factories,
        prompt_wheel_adjustment_mode=(
            lambda: (
                prompt_editor_preference_service.load_preferences().wheel_adjustment_mode
            )
        ),
    )
    open_autocomplete_list_management_modal = AutocompleteListManagementOpener(
        list_service=prompt_autocomplete_list_service,
        prompt_autocomplete_gateway=prompt_autocomplete_gateway,
        prompt_wildcard_catalog_gateway=prompt_wildcard_catalog_gateway,
        editor_panel_execution_factories=editor_panel_execution_factories,
        prompt_wheel_adjustment_mode=(
            lambda: (
                prompt_editor_preference_service.load_preferences().wheel_adjustment_mode
            )
        ),
    )
    prompt_spellcheck_language_tag = default_spellcheck_language_tag()
    prompt_spellcheck_gateway = build_spellcheck_gateway(
        enabled=prompt_editor_preference_service.load_preferences().user_allows(
            PromptEditorFeature.SPELLCHECK
        ),
        language_tag=prompt_spellcheck_language_tag,
    )
    prompt_spellcheck_service = PromptSpellcheckService(
        gateway=prompt_spellcheck_gateway,
        candidate_service=PromptSpellcheckCandidateService(
            tag_lexicon=prompt_autocomplete_gateway
        ),
        language_tag=prompt_spellcheck_language_tag,
        backend_name=type(prompt_spellcheck_gateway).__name__,
    )
    prompt_feature_profile_service = PromptFeatureProfileService(
        preference_service=prompt_editor_preference_service,
    )
    scheduled_lora_provider = _LazyScheduledLoraProvider(
        recipe_io_service=recipe_io_service,
        workflow_export_service=workflow_export_service,
        prompt_scheduled_lora_service=prompt_scheduled_lora_service,
        prompt_lora_catalog_service=prompt_lora_catalog_service,
        rich_choice_resolver=model_choice_resolver,
        node_definition_gateway=node_definition_gateway,
        output_dir=context.projects_dir,
    )
    record_dependency_phase("prompt_editor_services")
    node_behavior_service = NodeBehaviorService(
        node_definition_gateway=node_definition_gateway,
        model_backed_node_detector=model_backed_node_detector,
    )
    pinned_override_service = PinnedOverrideService()
    entrypoint_path = resolve_app_layout(context.install_root).entrypoint_path
    generation_service = GenerationService(
        recipe_io_service=recipe_io_service,
        workflow_export_service=workflow_export_service,
        comfy_gateway=comfy_gateway,
        asset_staging_service=comfy_asset_staging_service,
        prompt_wildcard_preprocessing_service=(prompt_wildcard_preprocessing_service),
        preview_method_resolver=generation_preview_preference_service,
        output_preference_service=output_preference_service,
        direct_workflow_graph_service=DirectWorkflowGenerationPlanService(
            node_definition_hydrator=node_definition_gateway,
            node_definition_gateway=node_definition_gateway,
        ),
        output_dir=context.projects_dir,
    )
    generation_dispatch_submitter = runtime_services.execution_runtime.submitter(
        "generation_dispatch",
        owner_id="generation_queue_dispatch",
        dispatcher=QtOwnerThreadDispatcher(generation_queue_transition_relay),
    )
    generation_preparation_submitter = runtime_services.execution_runtime.submitter(
        "generation_preparation",
        owner_id="workspace_generation_preparation",
        dispatcher=QtOwnerThreadDispatcher(generation_queue_transition_relay),
    )
    recipe_output_sibling_discovery_service = RecipeOutputSiblingDiscoveryService(
        output_preferences=output_preference_service,
    )
    generation_job_queue_service = GenerationJobQueueService(
        generation_service,
        transition_scheduler=generation_queue_transition_relay.schedule,
        dispatch_submitter=generation_dispatch_submitter,
        close_dispatch_submitter=generation_dispatch_submitter.close,
        owner_thread_scheduler=generation_queue_transition_relay.schedule,
        output_run_number_allocator=FileOutputRunNumberAllocator(
            output_preference_service
        ),
        output_root=context.outputs_dir,
        output_run_bucket_resolver=output_preference_service,
        output_run_projection_cache_key_provider=(output_preference_service),
    )
    generation_result_snapshot_service = GenerationResultSnapshotService(
        live_results=generation_job_queue_service,
        recipe_parser=recipe_io_service,
    )
    workspace_generation_controller = WorkspaceGenerationController(
        generation_service,
        generation_job_queue_service,
        GenerationPreparationExecutor(
            generation_preparation_submitter,
            close_submitter=generation_preparation_submitter.close,
        ),
    )
    shell_resource_lifecycle.register(
        "generation_job_queue",
        generation_job_queue_service.shutdown,
    )
    shell_resource_lifecycle.register(
        "workspace_generation",
        workspace_generation_controller.close,
    )
    record_dependency_phase("generation_services")

    def record_downloaded_model(
        result: BackendModelDownloadResult,
        candidate: Any,
    ) -> None:
        """Persist provider metadata for a backend-verified model download."""

        evidence = LocalModelEvidence(
            target_id=(
                f"{context.comfy_target.endpoint.host}:"
                f"{context.comfy_target.endpoint.port}:"
                f"{result.kind}:{result.value}"
            ),
            root_id=result.source.root_id,
            relative_path=result.source.relative_path,
            kind=result.kind,
            value=result.value,
            display_name=result.display_name,
            size_bytes=result.file.size_bytes,
            modified_at=result.file.modified_at,
            sha256=result.sha256,
        )
        preferences = civitai_preference_service.load_preferences()
        thumbnail_policy = CivitaiThumbnailPolicy(
            preferences.thumbnail_safety_policy
            if preferences.thumbnail_downloads_enabled
            else CivitaiThumbnailSafetyPolicy.DISABLED
        )
        thumbnail_url = _candidate_str(candidate, "thumbnail_url")
        selected_image = (
            CivitaiImage(
                image_id=None,
                url=thumbnail_url,
                image_type="image",
                nsfw=None,
                nsfw_level=None,
                width=None,
                height=None,
                meta=None,
            )
            if thumbnail_url and preferences.thumbnail_downloads_enabled
            else None
        )
        cached_thumbnail = (
            model_thumbnail_store.cache_thumbnail(
                sha256=evidence.sha256,
                image=selected_image,
                selection_policy=thumbnail_policy.selection_policy,
            )
            if selected_image is not None
            else None
        )
        now = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
        model_metadata_store.save_record(
            ModelMetadataCacheRecord(
                schema_version=1,
                local=evidence,
                provider=CivitaiModelVersion(
                    model_id=int(getattr(candidate, "model_id", 0) or 0),
                    model_version_id=int(
                        getattr(candidate, "model_version_id", 0) or 0
                    ),
                    model_name=_candidate_str(candidate, "model_name")
                    or result.display_name,
                    model_type=None,
                    version_name=_candidate_str(candidate, "version_name")
                    or result.display_name,
                    base_model=_candidate_optional_str(candidate, "base_model"),
                    trained_words=(),
                    description=None,
                    version_description=None,
                    tags=(),
                    creator_username=_candidate_optional_str(candidate, "creator"),
                    creator_image=None,
                    nsfw=None,
                    nsfw_level=None,
                    availability=None,
                    files=(
                        CivitaiFile(
                            file_id=getattr(candidate, "file_id", None),
                            name=_candidate_str(candidate, "name") or result.value,
                            size_kb=getattr(candidate, "size_kb", None),
                            file_type=_candidate_optional_str(candidate, "file_type"),
                            download_url=_candidate_optional_str(
                                candidate,
                                "download_url",
                            ),
                            pickle_scan_result=_candidate_optional_str(
                                candidate,
                                "pickle_scan_result",
                            ),
                            virus_scan_result=_candidate_optional_str(
                                candidate,
                                "virus_scan_result",
                            ),
                            primary=True,
                            hashes={"SHA256": result.sha256},
                            metadata={
                                "format": _candidate_str(
                                    candidate,
                                    "metadata_format",
                                )
                            },
                        ),
                    ),
                    images=(selected_image,) if selected_image is not None else (),
                    stats={},
                    model_page_url=_candidate_str(candidate, "model_page_url"),
                    source_url=(
                        "https://civitai.com/api/v1/model-versions/by-hash/"
                        f"{result.sha256}"
                    ),
                    fetched_at=now,
                    raw_provider_payload={},
                ),
                provider_status="found",
                thumbnail=cached_thumbnail,
                thumbnail_status=(
                    ThumbnailSelectionStatus.SELECTED
                    if selected_image is not None
                    else ThumbnailSelectionStatus.NO_SFW_IMAGE
                ),
                updated_at=now,
            )
        )
        model_catalog_service.invalidate(result.kind)
        model_choice_resolver.invalidate(result.kind)

    def current_civitai_thumbnail_policy() -> CivitaiThumbnailPolicy:
        """Return the active CivitAI thumbnail policy from Settings."""

        preferences = civitai_preference_service.load_preferences()
        return CivitaiThumbnailPolicy(
            preferences.thumbnail_safety_policy
            if preferences.thumbnail_downloads_enabled
            else CivitaiThumbnailSafetyPolicy.DISABLED
        )

    manual_model_metadata_update_bridge = ModelMetadataUpdateBridge()
    manual_model_metadata_submitter = runtime_services.execution_runtime.submitter(
        "model_metadata",
        owner_id="manual_model_metadata_context_actions",
        dispatcher=DirectExecutionDispatcher(),
    )
    model_metadata_context_action_handler = ModelMetadataContextActionScheduler(
        refresh_service=ManualModelMetadataRefreshService(
            backend=model_metadata_backend,
            civitai=_LazyCivitaiClient(
                api_key_provider=civitai_credential_service.load_api_key
            ),
            catalog=model_metadata_store,
            thumbnails=model_thumbnail_store,
            update_sink=manual_model_metadata_update_bridge,
            thumbnail_policy=current_civitai_thumbnail_policy(),
            civitai_preferences=civitai_preference_service,
        ),
        submitter=manual_model_metadata_submitter,
        close_submitter=manual_model_metadata_submitter.close,
    )
    shell_resource_lifecycle.register(
        "manual_model_metadata_context_actions",
        model_metadata_context_action_handler.shutdown,
    )
    record_dependency_phase("manual_model_metadata_services")

    def configure_output_thumbnail_context(
        image_registry: Any,
        projection_lookup: Callable[[], Any],
    ) -> None:
        """Connect output-canvas thumbnail assignment after canvas construction."""

        model_metadata_context_action_handler.configure_output_thumbnail_assignment(
            output_thumbnail_service=SetModelThumbnailFromOutputService(
                backend=model_metadata_backend,
                catalog=model_metadata_store,
                thumbnails=model_thumbnail_store,
                image_registry=image_registry,
                update_sink=manual_model_metadata_update_bridge,
            ),
            output_thumbnail_choices=ProjectionOutputCanvasThumbnailChoiceProvider(
                projection_lookup
            ),
        )

    def create_scoped_metadata_refresh_service(
        update_sink: Any,
    ) -> ScopedMetadataRefreshService:
        """Build delta-only model metadata refresh for live folder changes."""

        scoped_metadata_submitter = runtime_services.execution_runtime.submitter(
            "model_metadata",
            owner_id=f"scoped_model_metadata_refresh_{id(update_sink):x}",
            dispatcher=DirectExecutionDispatcher(),
        )
        return ScopedMetadataRefreshService(
            backend=model_metadata_backend,
            refresh_service=ModelMetadataRefreshService(
                backend=model_metadata_backend,
                civitai=_LazyCivitaiClient(
                    api_key_provider=civitai_credential_service.load_api_key
                ),
                catalog=model_metadata_store,
                thumbnails=model_thumbnail_store,
                thumbnail_policy=current_civitai_thumbnail_policy(),
                civitai_preferences=civitai_preference_service,
                capability_wait_timeout_seconds=0.0,
            ),
            update_sink=update_sink,
            submitter=scoped_metadata_submitter,
            close_submitter=scoped_metadata_submitter.close,
        )

    def create_cube_library_event_listener(
        on_update: Any,
    ) -> "CubeLibraryEventListener":
        """Create a Cube Library listener backed by the execution runtime."""

        from substitute.infrastructure.comfy.cube_library_event_listener import (
            CubeLibraryEventListener,
        )

        update_dispatcher = QtOwnerThreadDispatcher(generation_queue_transition_relay)
        return CubeLibraryEventListener(
            endpoint=context.comfy_target.endpoint,
            on_update=lambda update: update_dispatcher.publish(
                lambda: on_update(update),
                reason="cube_library_event_received",
            ),
            task_factory=lambda identity, task_context, work, thread_name: (
                _create_backend_event_listener_task(
                    runtime_services=runtime_services,
                    registry_key="cube_library",
                    identity=identity,
                    context=task_context,
                    work=work,
                    thread_name=thread_name,
                )
            ),
        )

    def create_model_catalog_event_listener(
        on_update: Any,
    ) -> "ModelCatalogEventListener":
        """Create a model catalog listener backed by the execution runtime."""

        from substitute.infrastructure.comfy.model_catalog_event_listener import (
            ModelCatalogEventListener,
        )

        update_dispatcher = QtOwnerThreadDispatcher(generation_queue_transition_relay)
        return ModelCatalogEventListener(
            endpoint=context.comfy_target.endpoint,
            on_update=lambda update: update_dispatcher.publish(
                lambda: on_update(update),
                reason="model_catalog_event_received",
            ),
            latest_change_provider=model_metadata_backend.get_latest_model_catalog_change,
            task_factory=lambda identity, task_context, work, thread_name: (
                _create_backend_event_listener_task(
                    runtime_services=runtime_services,
                    registry_key="model_catalog",
                    identity=identity,
                    context=task_context,
                    work=work,
                    thread_name=thread_name,
                )
            ),
        )

    record_dependency_phase("listener_factories")

    dependencies = MainWindowDependencies(
        cube_load_service=cube_load_service,
        cube_library_client=cube_library_backend,
        create_cube_library_event_listener=create_cube_library_event_listener,
        create_model_catalog_event_listener=create_model_catalog_event_listener,
        create_scoped_metadata_refresh_service=create_scoped_metadata_refresh_service,
        cube_icon_factory=cube_icon_factory,
        invalidate_cube_catalog_cache=cube_repository.invalidate_cache,
        input_asset_endpoint_service=input_asset_endpoint_service,
        input_canvas_plan_service=input_canvas_plan_service,
        graph_section_service=graph_section_service,
        recipe_io_service=recipe_io_service,
        create_recipe_model_load_resolver=lambda: RecipeModelLoadResolver(
            RecipeModelResolutionIndex.from_catalog(
                model_catalog_service,
                kinds=(
                    "checkpoints",
                    "loras",
                    "vae",
                    "diffusion_models",
                    "upscale_models",
                    "controlnet",
                ),
            ),
            backend=model_metadata_backend,
            fingerprint_jobs=model_metadata_backend,
            civitai=_LazyCivitaiClient(
                api_key_provider=civitai_credential_service.load_api_key
            ),
            civitai_missing_model_lookup_enabled=(
                lambda: (
                    civitai_preference_service.load_preferences().missing_model_lookup_enabled
                )
            ),
            thumbnail_policy_provider=current_civitai_thumbnail_policy,
        ),
        recipe_model_download_resolution_service=RecipeModelDownloadResolutionService(
            backend=model_metadata_backend,
            api_key_provider=civitai_credential_service.load_api_key,
            downloads_enabled=(
                lambda: civitai_preference_service.load_preferences().downloads_enabled
            ),
            download_path_pattern_provider=(
                lambda: (
                    civitai_preference_service.load_preferences().download_path_pattern
                )
            ),
            model_downloaded=record_downloaded_model,
        ),
        workflow_export_service=workflow_export_service,
        progress_service=progress_service,
        generation_service=generation_service,
        generation_job_queue_service=generation_job_queue_service,
        asset_reveal_service=asset_reveal_service,
        canvas_io_service=canvas_io_service,
        workflow_asset_service=workflow_asset_service,
        workspace_generation_controller=workspace_generation_controller,
        shell_resource_lifecycle=shell_resource_lifecycle,
        comfy_output_stream=comfy_output_stream,
        localization_manager=runtime_services.localization_manager,
        node_presentation_service=build_node_presentation_service(
            runtime_services.localization_manager,
            runtime_services.comfy_node_localization.store,
        ),
        node_definition_gateway=node_definition_gateway,
        prompt_autocomplete_gateway=prompt_autocomplete_gateway,
        prompt_wildcard_catalog_gateway=prompt_wildcard_catalog_gateway,
        danbooru_url_import_service=cast(
            "DanbooruUrlImportService",
            danbooru_url_import_service,
        ),
        danbooru_wiki_service=cast(
            "DanbooruWikiContentService",
            danbooru_wiki_service,
        ),
        danbooru_image_preview_service=cast(
            "DanbooruImagePreviewService",
            danbooru_image_preview_service,
        ),
        danbooru_recent_posts_service=cast(
            "DanbooruRecentPostsService",
            danbooru_recent_posts_service,
        ),
        danbooru_preference_service=danbooru_preference_service,
        danbooru_cache_repository=danbooru_cache_repository,
        civitai_preference_service=civitai_preference_service,
        civitai_credential_service=civitai_credential_service,
        civitai_cache_service=civitai_cache_service,
        prompt_wildcard_file_management_service=(
            prompt_wildcard_file_management_service
        ),
        open_wildcard_management_modal=open_wildcard_management_modal,
        open_autocomplete_list_management_modal=(
            open_autocomplete_list_management_modal
        ),
        prompt_wildcard_preference_service=prompt_wildcard_preference_service,
        prompt_wildcard_preprocessing_service=(prompt_wildcard_preprocessing_service),
        prompt_lora_catalog_service=prompt_lora_catalog_service,
        prompt_scheduled_lora_service=prompt_scheduled_lora_service,
        prompt_spellcheck_service=prompt_spellcheck_service,
        scheduled_lora_provider=scheduled_lora_provider,
        prompt_feature_profile_service=prompt_feature_profile_service,
        user_preset_service=user_preset_service,
        model_catalog_service=model_catalog_service,
        model_choice_resolver=model_choice_resolver,
        thumbnail_asset_repository=model_metadata_store,
        model_metadata_context_action_handler=model_metadata_context_action_handler,
        manual_model_metadata_update_sink=manual_model_metadata_update_bridge,
        configure_output_thumbnail_context=configure_output_thumbnail_context,
        node_behavior_service=node_behavior_service,
        pinned_override_service=pinned_override_service,
        open_reconfigure_window=lambda: show_reconfigure_window(
            context=context,
            entrypoint_path=entrypoint_path,
            execution_runtime=runtime_services.execution_runtime,
        ),
        appearance_runtime=appearance_runtime,
        appearance_restart_coordinator=appearance_restart_coordinator,
        about_info_service=about_info_service,
        comfy_connection_settings_service=comfy_connection_settings_service,
        restart_requirement_service=restart_requirement_service,
        comfy_environment_service=comfy_environment_service,
        cube_library_management_service=cube_library_management_service,
        generation_preview_preference_service=generation_preview_preference_service,
        output_preference_service=output_preference_service,
        prompt_editor_preference_service=prompt_editor_preference_service,
        session_snapshot_repository=(runtime_services.session_snapshot_repository),
        session_autosave_service=runtime_services.session_autosave_service,
        execution_runtime=runtime_services.execution_runtime,
        settings_task_runner_factory=create_settings_task_runner_factory(
            runtime_services.execution_runtime,
            resource_lifecycle=shell_resource_lifecycle,
        ),
        editor_panel_execution_factories=editor_panel_execution_factories,
        generation_result_snapshot_service=generation_result_snapshot_service,
        recipe_output_sibling_discovery_service=(
            recipe_output_sibling_discovery_service
        ),
        restore_projection_cache_repository=(
            runtime_services.restore_projection_cache_repository
        ),
        restore_projection_target_key=_cube_cache_target_key(context),
        path_bundle=InstallationPathBundle(
            install_root=context.install_root,
            user_dir=context.user_dir,
            projects_dir=context.projects_dir,
            outputs_dir=context.outputs_dir,
            sugar_scripts_dir=context.sugar_scripts_dir,
            wildcards_dir=context.wildcards_dir,
            managed_comfy_dir=context.managed_comfy_dir,
        ),
    )
    record_dependency_phase("main_window_dependencies_dataclass")
    trace_mark("composition.dependencies.compose.end")
    return dependencies


def _cube_cache_target_key(context: InstallationContext) -> str:
    """Return a stable non-secret key for cube-derived cache rows."""

    target = context.comfy_target
    workspace = target.workspace_path.resolve() if target.workspace_path else None
    workspace_hash = (
        hashlib.sha256(str(workspace).encode("utf-8")).hexdigest()
        if workspace is not None
        else ""
    )
    payload = "|".join(
        (
            str(target.mode.value),
            target.endpoint.host,
            str(target.endpoint.port),
            workspace_hash,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cube_icon_target_key(context: InstallationContext) -> str:
    """Return the shared cube cache target key for icon cache compatibility."""

    return _cube_cache_target_key(context)


def _invalidate_cube_icon_cache(
    *,
    cube_icon_factory: Any,
    cube_icon_cache: Any,
    target_key: str,
) -> None:
    """Clear process icon cache and target-scoped durable rendered rows."""

    cube_icon_factory.clear_asset_cache()
    cube_icon_cache.delete_for_target(target_key)


def _candidate_str(candidate: Any, field_name: str) -> str:
    """Return a stripped string field from a CivitAI download candidate."""

    value = getattr(candidate, field_name, "")
    return value.strip() if isinstance(value, str) else ""


def _candidate_optional_str(candidate: Any, field_name: str) -> str | None:
    """Return a non-empty candidate string field, or ``None``."""

    value = _candidate_str(candidate, field_name)
    return value or None


def build_model_metadata_refresh_service(
    context: InstallationContext,
) -> Any:
    """Compose the startup model metadata refresh service for the active context."""

    from substitute.application.model_metadata import ModelMetadataRefreshService
    from substitute.application.civitai import (
        CivitaiCredentialService,
        CivitaiPreferenceService,
    )
    from substitute.domain.civitai import CivitaiThumbnailSafetyPolicy
    from substitute.domain.model_metadata import CivitaiThumbnailPolicy
    from substitute.infrastructure.external.civitai_client import CivitaiClient
    from substitute.infrastructure.external.substitute_backend_model_metadata_client import (
        SubstituteBackendModelMetadataClient,
    )
    from substitute.infrastructure.persistence import (
        FileCivitaiPreferenceRepository,
        SqliteModelMetadataStore,
    )
    from substitute.infrastructure.security import build_civitai_credential_store

    civitai_preferences = CivitaiPreferenceService(
        FileCivitaiPreferenceRepository(context.user_settings_dir)
    )
    civitai_credentials = CivitaiCredentialService(
        build_civitai_credential_store(context.user_settings_dir)
    )
    preferences = civitai_preferences.load_preferences()
    thumbnail_policy = CivitaiThumbnailPolicy(
        preferences.thumbnail_safety_policy
        if preferences.thumbnail_downloads_enabled
        else CivitaiThumbnailSafetyPolicy.DISABLED
    )
    model_metadata_store = SqliteModelMetadataStore(
        context.model_metadata_dir,
        thumbnail_policy_key=thumbnail_policy.selection_policy,
    )
    return ModelMetadataRefreshService(
        backend=SubstituteBackendModelMetadataClient(context.comfy_target.endpoint),
        civitai=CivitaiClient(api_key_provider=civitai_credentials.load_api_key),
        catalog=model_metadata_store,
        thumbnails=_LazyModelThumbnailStore(context.model_metadata_dir),
        thumbnail_policy=thumbnail_policy,
        civitai_preferences=civitai_preferences,
    )


def build_main_window(
    context: InstallationContext,
    *,
    comfy_output_stream: TerminalOutputStream,
    shutdown_request: ShutdownRequest | None = None,
    startup_timer: StartupTimer | None = None,
    runtime_services: ApplicationRuntimeServices | None = None,
    startup_diagnostics_ignore_repository: StartupDiagnosticsIgnoreRepository
    | None = None,
) -> CustomWindow:
    """Build the main shell frame without showing it."""

    trace_mark(
        "composition.build_main_window.enter",
        runtime_services_supplied=runtime_services is not None,
    )
    if runtime_services is None:
        appearance_runtime = build_appearance_runtime(context)
        application = QApplication.instance()
        if not isinstance(application, QApplication):
            raise RuntimeError("QApplication is required before shell composition.")
        localization_runtime = build_application_localization_runtime(
            application,
            context,
            None,
        )
        runtime_services = build_application_runtime_services(
            context=context,
            comfy_output_stream=comfy_output_stream,
            localization_manager=localization_runtime.manager,
            appearance_runtime=appearance_runtime,
        )
    else:
        appearance_runtime = runtime_services.appearance_runtime
    with _startup_phase(startup_timer, "composition.configure_control_registry"):
        _configure_control_registry_service()
    with _startup_phase(startup_timer, "composition.build_main_window_dependencies"):
        with trace_span("composition.dependencies"):
            dependencies = _build_main_window_dependencies(runtime_services)

    with _startup_phase(startup_timer, "composition.import_main_window"):
        with trace_span("composition.import_main_window"):
            module = importlib.import_module(
                "substitute.presentation.shell.main_window"
            )
            main_window_class = getattr(module, "MainWindow")
            from substitute.presentation.shell.taskbar_progress import (
                create_taskbar_progress_presenter,
            )

    with _startup_phase(startup_timer, "composition.create_custom_window"):
        with trace_span("composition.create_custom_window"):
            frame = _custom_window_class()(
                appearance_runtime=appearance_runtime,
                shutdown_request=shutdown_request,
                backdrop_mode=_resolved_shell_backdrop_mode(appearance_runtime),
                create_body_material_surface=False,
            )
            set_localized_window_title(frame, "Sugar Substitute")
            frame.setWindowIcon(application_icon())
            frame.destroyed.connect(dependencies.shell_resource_lifecycle.shutdown)

    _apply_main_window_geometry(frame)

    with _startup_phase(startup_timer, "composition.construct_main_window"):
        with trace_span("composition.construct_main_window"):
            resolved_backdrop_mode = _resolved_shell_backdrop_mode(appearance_runtime)
            main_window = main_window_class(
                menu_container=frame.menuContainer,
                dependencies=dependencies,
                startup_timer=startup_timer,
                generation_action_cluster=getattr(
                    frame, "generationActionCluster", None
                ),
                backdrop_mode=resolved_backdrop_mode,
            )
            main_window.shell_frame_integration_controller.set_taskbar_progress_presenter(
                create_taskbar_progress_presenter(frame)
            )
            app_orb = getattr(frame, "appOrbMenuButton", None)
            if app_orb is not None:
                main_window.shell_frame_integration_controller.attach_app_orb_menu(
                    app_orb
                )
    _set_main_window_widget(frame, main_window)
    with trace_span("composition.attach_main_window"):
        _attach_main_window_to_shell(
            frame,
            main_window,
            startup_diagnostics_ignore_repository=startup_diagnostics_ignore_repository,
        )
    _install_startup_visibility_filters(frame, main_window)
    _wire_shell_close_button(frame)
    trace_mark("composition.build_main_window.end", **_widget_geometry_fields(frame))
    return frame


def _wire_shell_close_button(frame: CustomWindow) -> None:
    """Route the shell titlebar close button through the frame close event."""

    try:
        frame.titleBar.closeBtn.clicked.connect(frame.close)
    except Exception:
        log_exception(_LOGGER, "Failed to connect shell close button")


def _apply_main_window_geometry(frame: QWidget) -> None:
    """Apply the standard shell size and centered position to a frame."""

    trace_mark("shell.geometry.default.apply.start", **_widget_geometry_fields(frame))
    screen = frame.screen().availableGeometry()
    screen_width = screen.width()
    screen_height = screen.height()
    max_width = int(screen_width * 0.85)
    max_height = int(screen_height * 0.85)
    aspect_ratio = 16 / 9
    target_width = max_width
    target_height = int(target_width / aspect_ratio)
    if target_height > max_height:
        target_height = max_height
        target_width = int(target_height * aspect_ratio)

    frame.resize(target_width, target_height)
    frame.move(
        screen.left() + (screen_width - target_width) // 2,
        screen.top() + (screen_height - target_height) // 2,
    )
    trace_mark("shell.geometry.default.apply.end", **_widget_geometry_fields(frame))


def _show_with_initial_shell_placement(
    frame: QWidget,
    placement: InitialShellPlacement,
) -> None:
    """Show a shell frame using saved placement as its first visible state."""

    trace_mark("shell.show_built.placement_path", placement="restored")
    geometry = placement.geometry
    if geometry is not None:
        frame.setGeometry(geometry.x, geometry.y, geometry.width, geometry.height)

    display_state = placement.window_display_state
    if placement.maximized and display_state == "normal":
        display_state = "maximized"
    if display_state == "fullscreen":
        trace_mark("shell.qt_show.start", display_state=display_state)
        frame.showFullScreen()
        trace_mark("shell.qt_show.end", **_widget_geometry_fields(frame))
        _request_shell_activation(frame)
        return
    if display_state == "maximized":
        trace_mark("shell.qt_show.start", display_state=display_state)
        frame.showMaximized()
        trace_mark("shell.qt_show.end", **_widget_geometry_fields(frame))
        _request_shell_activation(frame)
        return
    trace_mark("shell.qt_show.start", display_state=display_state)
    frame.show()
    trace_mark("shell.qt_show.end", **_widget_geometry_fields(frame))
    _request_shell_activation(frame)


def _activate_shell_window(frame: object) -> None:
    """Ask the window manager to foreground the shown shell frame."""

    trace_mark("shell.activation.start", frame_type=type(frame).__name__)
    raise_window = getattr(frame, "raise_", None)
    if callable(raise_window):
        raise_window()
    activate_window = getattr(frame, "activateWindow", None)
    if callable(activate_window):
        activate_window()
    trace_mark("shell.activation.end", frame_type=type(frame).__name__)


def _request_shell_activation(frame: QWidget) -> None:
    """Request shell foreground activation immediately and after Qt settles."""

    trace_mark("shell.activation.requested", **_widget_geometry_fields(frame))
    _activate_shell_window(frame)
    trace_mark(
        "shell.activation.delayed",
        delay_ms=0,
    )
    QTimer.singleShot(0, lambda: _activate_shell_window(frame))


def _startup_phase(startup_timer: StartupTimer | None, name: str) -> Any:
    """Return a timing context for optional startup instrumentation."""

    from contextlib import nullcontext

    return startup_timer.phase(name) if startup_timer is not None else nullcontext()


def main_window_widget(frame: object) -> QWidget | None:
    """Return the Substitute MainWindow widget stored on a shell frame."""

    widget = getattr(frame, "_substitute_main_window", None)
    return widget if isinstance(widget, QWidget) else None


def _set_main_window_widget(frame: object, widget: QWidget) -> None:
    """Store the presentation MainWindow without colliding with frame internals."""

    setattr(frame, "_substitute_main_window", widget)


def _attach_main_window_to_shell(
    frame: CustomWindow,
    main_window: QWidget,
    *,
    startup_diagnostics_ignore_repository: StartupDiagnosticsIgnoreRepository
    | None = None,
) -> None:
    """Attach one existing MainWindow widget to the provided shell frame."""

    trace_mark(
        "composition.attach_main_window.enter",
        frame_type=type(frame).__name__,
        main_window_type=type(main_window).__name__,
    )
    typed_main_window = cast(_ShellMainWindowProtocol, main_window)
    generation_action_cluster = getattr(frame, "generationActionCluster", None)
    if generation_action_cluster is not None:
        generation_control_registry = GenerationTitleBarControlRegistry(
            on_generate=typed_main_window.workspace_generation_actions.on_generate_clicked,
            on_skip=(
                typed_main_window.workspace_generation_actions.on_skip_generation_clicked
            ),
            on_stop=(
                typed_main_window.workspace_generation_actions.on_stop_generation_clicked
            ),
            show_queue_for=typed_main_window.generation_queue_controller.show_for,
            show_queue_context_menu_for=(
                typed_main_window.generation_queue_controller.show_context_menu_for
            ),
            on_generate_mode_selected=(
                typed_main_window.generation_action_controller.set_generation_selected_mode
            ),
            parent=frame,
        )
        typed_main_window.shell_frame_integration_controller.set_generation_titlebar_control_registry(
            generation_control_registry
        )
    if frame.comfyOutputToggleButton is not None:
        frame.comfyOutputToggleButton.toggled.connect(
            typed_main_window.comfy_runtime_actions.set_comfy_output_panel_visible
        )
        typed_main_window.comfy_output_panel_visibility_changed.connect(
            frame.set_comfy_output_toggle_checked
        )
        frame.set_comfy_output_toggle_checked(
            typed_main_window.comfy_runtime_actions.is_comfy_output_panel_visible()
        )
    startup_diagnostics_button = getattr(frame, "startupDiagnosticsButton", None)
    if (
        startup_diagnostics_button is not None
        and startup_diagnostics_ignore_repository is not None
    ):
        typed_main_window.shell_frame_integration_controller.attach_startup_diagnostics_titlebar(
            startup_diagnostics_button,
            startup_diagnostics_ignore_repository,
        )
    _move_workflow_tabbar_to_shell(frame, typed_main_window)
    frame.add_body_widget(main_window)
    sync_app_orb_overlay = getattr(frame, "sync_app_orb_overlay", None)
    if callable(sync_app_orb_overlay):
        sync_app_orb_overlay()
    trace_mark("composition.attach_main_window.end")


def _move_workflow_tabbar_to_shell(
    frame: CustomWindow,
    main_window: _ShellMainWindowProtocol,
) -> None:
    """Move the existing workflow tabbar into the provided shell frame titlebar."""

    trace_mark("composition.workflow_tabbar.move.start")
    workflow_tabbar = getattr(main_window, "workflow_tabbar", None)
    if workflow_tabbar is None or frame.menuContainer is None:
        trace_mark("composition.workflow_tabbar.move.skip", reason="missing_widget")
        return
    parent = workflow_tabbar.parentWidget()
    if parent is not None and parent is not frame.menuContainer:
        parent_layout = parent.layout()
        if parent_layout is not None:
            parent_layout.removeWidget(workflow_tabbar)
    menu_layout = frame.menuContainer.layout()
    if menu_layout is None:
        return
    typed_menu_layout = cast(Any, menu_layout)
    from substitute.presentation.shell.window_frame import (
        titlebar_menu_content_insert_index,
    )

    insert_index = titlebar_menu_content_insert_index(frame.menuContainer)
    typed_menu_layout.insertWidget(insert_index, workflow_tabbar)
    typed_menu_layout.setStretch(insert_index, 8)
    if insert_index > 0:
        typed_menu_layout.setStretch(insert_index - 1, 0)
    if menu_layout.count() > insert_index + 1:
        typed_menu_layout.setStretch(insert_index + 1, 2)
    frame.set_workflow_tab_drag_owner(workflow_tabbar)
    trace_mark("composition.workflow_tabbar.move.end")


def _install_startup_visibility_filters(frame: QWidget, main_window: QWidget) -> None:
    """Attach temporary startup visibility filters and keep them alive on the frame."""

    filters = [
        StartupVisibilityEventFilter("shell_frame"),
        StartupVisibilityEventFilter("main_window"),
    ]
    frame_install = getattr(frame, "installEventFilter", None)
    if callable(frame_install):
        frame_install(filters[0])
    main_window_install = getattr(main_window, "installEventFilter", None)
    if callable(main_window_install):
        main_window_install(filters[1])
    central_widget_getter = getattr(main_window, "centralWidget", None)
    central_widget = (
        central_widget_getter() if callable(central_widget_getter) else None
    )
    if isinstance(central_widget, QWidget):
        central_filter = StartupVisibilityEventFilter("main_window.central")
        central_install = getattr(central_widget, "installEventFilter", None)
        if callable(central_install):
            central_install(central_filter)
        filters.append(central_filter)
    setattr(frame, "_startup_visibility_trace_filters", filters)
    trace_mark(
        "startup.visibility.filters_installed",
        filter_count=len(filters),
        frame_type=type(frame).__name__,
        main_window_type=type(main_window).__name__,
    )


def _widget_geometry_fields(widget: object) -> dict[str, object]:
    """Return safe geometry fields for startup trace records."""

    geometry = _safe_call(widget, "geometry")
    return {
        "widget_type": type(widget).__name__,
        "width": _safe_call_int(widget, "width"),
        "height": _safe_call_int(widget, "height"),
        "x": _safe_geometry_value(geometry, "x"),
        "y": _safe_geometry_value(geometry, "y"),
        "is_maximized": _safe_call_bool(widget, "isMaximized"),
        "is_fullscreen": _safe_call_bool(widget, "isFullScreen"),
    }


def _safe_call(widget: object, method_name: str) -> object | None:
    """Call one zero-argument widget method for trace context."""

    method = getattr(widget, method_name, None)
    if not callable(method):
        return None
    try:
        return cast(object, method())
    except (RuntimeError, TypeError, ValueError):
        return None


def _safe_call_int(widget: object, method_name: str) -> int | None:
    """Return one integer widget method value for trace context."""

    value = _safe_call(widget, method_name)
    try:
        return int(cast(Any, value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def _safe_call_bool(widget: object, method_name: str) -> bool | None:
    """Return one boolean widget method value for trace context."""

    value = _safe_call(widget, method_name)
    return bool(value) if value is not None else None


def _safe_geometry_value(geometry: object | None, method_name: str) -> int | None:
    """Return one integer geometry method value for trace context."""

    if geometry is None:
        return None
    return _safe_call_int(geometry, method_name)


def _resolved_shell_backdrop_mode(
    appearance_runtime: AppearanceRuntimeController,
) -> ShellBackdropMode | None:
    """Resolve the current persisted appearance backdrop into shell-frame terms."""

    from substitute.domain.appearance import AppearanceBackdropMode
    from substitute.presentation.shell.window_frame import ShellBackdropMode

    resolved = appearance_runtime.resolve_preferences()
    if resolved.effective_backdrop_mode is AppearanceBackdropMode.ACRYLIC:
        return ShellBackdropMode.ACRYLIC
    if resolved.effective_backdrop_mode is AppearanceBackdropMode.MICA_ALT:
        return ShellBackdropMode.MICA_ALT
    return None


def reload_shell_frame(frame: CustomWindow) -> CustomWindow:
    """Reload the outer shell frame around the existing MainWindow widget."""

    from substitute.presentation.shell.taskbar_progress import (
        create_taskbar_progress_presenter,
    )

    main_window = main_window_widget(frame)
    if main_window is None:
        return frame
    new_frame = _custom_window_class()(
        appearance_runtime=frame._appearance_runtime,
        shutdown_request=frame._shutdown_request,
        backdrop_mode=_resolved_shell_backdrop_mode(frame._appearance_runtime),
    )
    new_frame.setWindowTitle(frame.windowTitle())
    new_frame.setWindowIcon(frame.windowIcon())
    _wire_shell_close_button(new_frame)
    _set_main_window_widget(new_frame, main_window)
    app_orb = getattr(new_frame, "appOrbMenuButton", None)
    frame_integration_controller = getattr(
        main_window,
        "shell_frame_integration_controller",
        None,
    )
    attach_app_orb_menu = getattr(
        frame_integration_controller,
        "attach_app_orb_menu",
        None,
    )
    if app_orb is not None and callable(attach_app_orb_menu):
        attach_app_orb_menu(app_orb)
    _attach_main_window_to_shell(new_frame, main_window)
    set_taskbar_progress_presenter = getattr(
        frame_integration_controller,
        "set_taskbar_progress_presenter",
        None,
    )
    if callable(set_taskbar_progress_presenter):
        set_taskbar_progress_presenter(create_taskbar_progress_presenter(new_frame))

    geometry = frame.geometry()
    was_maximized = frame.isMaximized()
    if not was_maximized:
        new_frame.setGeometry(geometry)
    frame.suppress_app_quit_on_close()
    frame.allow_direct_close()
    frame.hide()
    if was_maximized:
        new_frame.showMaximized()
    else:
        new_frame.show()
        new_frame.setGeometry(geometry)
    frame.close()
    frame.deleteLater()
    return new_frame


def show_built_main_window(
    frame: CustomWindow,
    *,
    apply_default_geometry: bool = True,
    initial_shell_placement: InitialShellPlacement | None = None,
) -> CustomWindow:
    """Show a prebuilt shell frame and return it for startup ownership."""

    trace_mark(
        "shell.show_built.enter",
        apply_default_geometry=apply_default_geometry,
        initial_shell_placement_present=initial_shell_placement is not None,
        **_widget_geometry_fields(frame),
    )
    if initial_shell_placement is not None:
        _show_with_initial_shell_placement(frame, initial_shell_placement)
        trace_mark("shell.show_built.end", **_widget_geometry_fields(frame))
        return frame
    if apply_default_geometry:
        _apply_main_window_geometry(frame)
    trace_mark("shell.show_built.placement_path", placement="default")
    trace_mark("shell.qt_show.start", display_state="normal")
    frame.show()
    trace_mark("shell.qt_show.end", **_widget_geometry_fields(frame))
    if apply_default_geometry:
        _apply_main_window_geometry(frame)
        trace_mark(
            "shell.geometry.default.delayed_apply",
            delay_ms=0,
        )
        QTimer.singleShot(0, lambda: _apply_main_window_geometry(frame))
    _request_shell_activation(frame)
    trace_mark("shell.show_built.end", **_widget_geometry_fields(frame))
    return frame


def show_main_window(
    context: InstallationContext,
    *,
    comfy_output_stream: TerminalOutputStream,
    shutdown_request: ShutdownRequest | None = None,
    startup_timer: StartupTimer | None = None,
    runtime_services: ApplicationRuntimeServices | None = None,
    startup_diagnostics_ignore_repository: StartupDiagnosticsIgnoreRepository
    | None = None,
    initial_shell_placement: InitialShellPlacement | None = None,
    initial_workspace: WorkspaceSnapshot | None = None,
) -> CustomWindow:
    """Build and show the main shell frame with the presentation MainWindow widget."""

    with trace_span("composition.show_main_window.build"):
        frame = build_main_window(
            context,
            comfy_output_stream=comfy_output_stream,
            shutdown_request=shutdown_request,
            startup_timer=startup_timer,
            runtime_services=runtime_services,
            startup_diagnostics_ignore_repository=startup_diagnostics_ignore_repository,
        )
    with trace_span("composition.show_main_window.show"):
        shown_frame = show_built_main_window(
            frame,
            initial_shell_placement=initial_shell_placement,
        )
    main_window = main_window_widget(shown_frame)
    workspace_restore_controller = getattr(
        main_window,
        "workspace_restore_controller",
        None,
    )
    hydrate = getattr(workspace_restore_controller, "hydrate_initial_workspace", None)
    if callable(hydrate):
        with trace_span(
            "composition.show_main_window.hydrate",
            initial_workspace_present=initial_workspace is not None,
        ):
            if initial_workspace is None:
                hydrate()
            else:
                hydrate(initial_workspace)
    return shown_frame


def _show_onboarding_surface(
    *,
    context: InstallationContext,
    readiness_assessment: ReadinessAssessment,
    flow_mode: OnboardingFlowMode,
    entrypoint_path: Path,
    initial_geometry: tuple[int, int, int, int] | None = None,
    execution_runtime: object | None = None,
) -> OnboardingWindow:
    """Build and show the dedicated onboarding, repair, or reconfigure surface."""

    from substitute.application.onboarding import OnboardingFlowService
    from substitute.application.onboarding.comfy_environment_service import (
        ComfyEnvironmentService,
    )
    from substitute.infrastructure.comfy.managed_install import (
        ensure_managed_comfy_setup,
    )
    from substitute.infrastructure.comfy.attached_install import (
        prepare_verified_attached_comfy_setup,
    )
    from substitute.infrastructure.comfy.local_process_gateway import (
        PsutilLocalComfyProcessGateway,
    )
    from substitute.infrastructure.comfy.workspace_python_discovery import (
        WorkspacePythonGateway,
    )
    from substitute.app.bootstrap.installation_context import (
        build_onboarding_service_bundle,
    )
    from substitute.app.bootstrap.onboarding_execution import (
        OnboardingExecutionRuntime,
        create_onboarding_environment_submitter,
        create_onboarding_provisioning_submitter_factory,
    )
    from substitute.presentation.onboarding import (
        OnboardingController,
        OnboardingWindow,
    )
    from substitute.presentation.onboarding.comfy_environment_coordinator import (
        ComfyEnvironmentCoordinator,
    )

    owned_execution_runtime: ExecutionRuntime | None = None
    active_execution_runtime = execution_runtime
    if active_execution_runtime is None:
        owned_execution_runtime = ExecutionRuntime()
        active_execution_runtime = owned_execution_runtime
    flow_service = OnboardingFlowService(
        service_bundle_factory=build_onboarding_service_bundle,
        managed_workspace_provisioner=ensure_managed_comfy_setup,
        entrypoint_path=entrypoint_path,
        attached_workspace_provisioner=prepare_verified_attached_comfy_setup,
        transaction_mode=_transaction_mode_for_flow(flow_mode),
    )
    controller = OnboardingController(
        initial_install_root=context.install_root,
        flow_mode=flow_mode,
        readiness_assessment=readiness_assessment,
        flow_service=flow_service,
        submitter_factory=create_onboarding_provisioning_submitter_factory(
            cast(OnboardingExecutionRuntime, active_execution_runtime)
        ),
    )
    environment_submitter = create_onboarding_environment_submitter(
        cast(OnboardingExecutionRuntime, active_execution_runtime),
        controller,
    )
    environment_coordinator = ComfyEnvironmentCoordinator(
        service=ComfyEnvironmentService(
            process_gateway=PsutilLocalComfyProcessGateway(),
            python_gateway=WorkspacePythonGateway(),
        ),
        submitter=environment_submitter,
        close_submitter=environment_submitter.close,
        parent=controller,
    )
    window = OnboardingWindow(
        controller=controller,
        environment_coordinator=environment_coordinator,
        install_root_locked=resolve_app_layout(context.install_root).installed_payload,
        initial_geometry=initial_geometry,
    )
    if owned_execution_runtime is not None:
        window.destroyed.connect(lambda _obj=None: owned_execution_runtime.shutdown())
    window.show()
    return window


def show_onboarding_window(
    *,
    context: InstallationContext,
    readiness_assessment: ReadinessAssessment,
    entrypoint_path: Path,
    initial_geometry: tuple[int, int, int, int] | None = None,
) -> OnboardingWindow:
    """Show first-run onboarding routed from bootstrap readiness."""

    from substitute.presentation.onboarding import OnboardingFlowMode

    return _show_onboarding_surface(
        context=context,
        readiness_assessment=readiness_assessment,
        flow_mode=OnboardingFlowMode.FIRST_RUN,
        entrypoint_path=entrypoint_path,
        initial_geometry=initial_geometry,
    )


def show_repair_window(
    *,
    context: InstallationContext,
    readiness_assessment: ReadinessAssessment,
    entrypoint_path: Path,
    initial_geometry: tuple[int, int, int, int] | None = None,
) -> OnboardingWindow:
    """Show repair onboarding routed from bootstrap readiness."""

    from substitute.presentation.onboarding import OnboardingFlowMode

    return _show_onboarding_surface(
        context=context,
        readiness_assessment=readiness_assessment,
        flow_mode=OnboardingFlowMode.REPAIR,
        entrypoint_path=entrypoint_path,
        initial_geometry=initial_geometry,
    )


def show_reconfigure_window(
    *,
    context: InstallationContext,
    entrypoint_path: Path,
    execution_runtime: object | None = None,
) -> OnboardingWindow:
    """Show reconfigure onboarding from the live shell."""

    from substitute.presentation.onboarding import OnboardingFlowMode

    return _show_onboarding_surface(
        context=context,
        readiness_assessment=ReadinessAssessment(
            route=BootstrapRoute.READY,
            issues=(),
        ),
        flow_mode=OnboardingFlowMode.RECONFIGURE,
        entrypoint_path=entrypoint_path,
        execution_runtime=execution_runtime,
    )


def _transaction_mode_for_flow(flow_mode: OnboardingFlowMode) -> SetupTransactionMode:
    """Map one UI flow entry mode to durable setup transaction intent."""

    from substitute.presentation.onboarding import OnboardingFlowMode

    if flow_mode is OnboardingFlowMode.FIRST_RUN:
        return SetupTransactionMode.FIRST_RUN
    if flow_mode is OnboardingFlowMode.RECONFIGURE:
        return SetupTransactionMode.RECONFIGURE
    return SetupTransactionMode.REPAIR


def create_splash_window() -> Any:
    """Create and display splash window while ComfyUI initializes."""

    module = importlib.import_module("substitute.presentation.shell.splash_window")
    splash_window_class = getattr(module, "SplashWindow")
    splash = splash_window_class(icon=application_icon())
    splash.center_on_screen()
    splash.show()
    return splash


def is_port_open(host: str, port: int, timeout: float = 0.2) -> bool:
    """Return True when TCP host/port accepts a connection."""
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def is_comfy_http_ready(host: str, port: int) -> bool:
    """Return True when ComfyUI responds to its HTTP readiness endpoint."""

    from substitute.infrastructure.comfy.managed_readiness import probe_http_ready

    return bool(probe_http_ready(host=host, port=port))


__all__ = [
    "build_appearance_runtime",
    "build_application_runtime_services",
    "CustomWindow",
    "build_main_window",
    "configure_windows_app_user_model_id",
    "create_application",
    "build_application_localization_runtime",
    "configure_theme",
    "build_model_metadata_refresh_service",
    "show_onboarding_window",
    "show_reconfigure_window",
    "show_repair_window",
    "show_built_main_window",
    "show_main_window",
    "create_splash_window",
    "is_comfy_http_ready",
    "is_port_open",
    "main_window_widget",
]
