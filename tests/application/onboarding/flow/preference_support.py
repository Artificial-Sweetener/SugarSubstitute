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

"""Tests for onboarding flow failure mapping and readiness-driven recovery copy."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


from substitute.application.onboarding import (
    OnboardingCredentialDraft,
    OnboardingPreferenceSetupDraft,
)
from substitute.domain.civitai import (
    CivitaiPreferences,
    default_civitai_preferences,
)
from substitute.domain.comfy_environment import ComfyModelRootStatus
from substitute.domain.danbooru.preferences import (
    DanbooruPreferences,
    default_danbooru_preferences,
)
from substitute.domain.generation import (
    OutputPreferences,
    default_output_preferences,
)
from substitute.domain.onboarding import (
    ComfyTargetConfiguration,
)
from substitute.domain.prompt.preferences.models import PromptEditorPreferences
from substitute.infrastructure.persistence.file_prompt_editor_preference_repository import (
    _default_preferences as _default_prompt_preferences,
)

from .runtime_support import (
    _FakeRuntimeLaunchService,
    _FakeSetupTransactionService,
    _StaticManagedRuntimeService,
    _StaticOnboardingService,
    _StaticReadinessService,
)


@dataclass
class _ModelRootProvider:
    """Return deterministic BackEnd-owned model-root state for flow tests."""

    status: ComfyModelRootStatus | None = None

    def load(
        self,
        _target: ComfyTargetConfiguration,
    ) -> ComfyModelRootStatus | None:
        """Return the configured host state."""

        return self.status


@dataclass
class _OutputPreferenceService:
    """Return deterministic output preferences for flow tests."""

    preferences: OutputPreferences = field(default_factory=default_output_preferences)
    effective_root: Path = Path("Substitute/user/outputs")

    def load_preferences(self) -> OutputPreferences:
        """Return default output organization preferences."""

        return self.preferences

    def effective_output_root(
        self,
        preferences: OutputPreferences | None = None,
    ) -> Path:
        """Return a deterministic effective output root."""

        _ = preferences
        return self.effective_root


class _PromptPreferenceService:
    """Return deterministic prompt editor preferences for flow tests."""

    def load_preferences(self) -> PromptEditorPreferences:
        """Return default prompt editor preferences."""

        return _default_prompt_preferences()


class _DanbooruPreferenceService:
    """Return deterministic Danbooru preferences for flow tests."""

    def load_preferences(self) -> DanbooruPreferences:
        """Return default Danbooru preferences."""

        return default_danbooru_preferences()


class _CivitaiPreferenceService:
    """Return deterministic CivitAI preferences for flow tests."""

    def load_preferences(self) -> CivitaiPreferences:
        """Return default CivitAI preferences."""

        return default_civitai_preferences()


@dataclass
class _CivitaiCredentialService:
    """Return deterministic CivitAI credential status for flow tests."""

    configured: bool = False

    def has_api_key(self) -> bool:
        """Return whether the fake credential store has a key."""

        return self.configured


@dataclass
class _ExternalModelLibraryConfigurator:
    """Return and record one connected WebUI model library for flow tests."""

    models_root: Path | None = None
    calls: list[tuple[Path, Path | None]] = field(default_factory=list)

    def configure(self, workspace: Path, models_root: Path | None) -> None:
        """Record one requested external model-library mapping."""

        self.calls.append((workspace, models_root))

    def load_models_root(self, workspace: Path) -> Path | None:
        """Return the configured external root without touching the workspace."""

        _ = workspace
        return self.models_root


@dataclass
class _PreferenceSetupService:
    """Record onboarding preference and credential saves for flow tests."""

    saved_preferences: list[OnboardingPreferenceSetupDraft] = field(
        default_factory=list
    )
    saved_credentials: list[OnboardingCredentialDraft] = field(default_factory=list)

    def save_preferences(self, draft: OnboardingPreferenceSetupDraft) -> None:
        """Record non-secret onboarding preferences."""

        self.saved_preferences.append(draft)

    def save_credentials(self, draft: OnboardingCredentialDraft) -> None:
        """Record optional onboarding credentials."""

        self.saved_credentials.append(draft)


@dataclass(frozen=True)
class _Bundle:
    """Provide the service bundle consumed by the onboarding flow service."""

    onboarding_service: _StaticOnboardingService
    runtime_service: _FakeRuntimeLaunchService
    readiness_service: _StaticReadinessService
    managed_runtime_service: _StaticManagedRuntimeService
    setup_transaction_service: _FakeSetupTransactionService
    model_root_provider: _ModelRootProvider = field(default_factory=_ModelRootProvider)
    output_preference_service: _OutputPreferenceService = field(
        default_factory=_OutputPreferenceService
    )
    prompt_editor_preference_service: _PromptPreferenceService = field(
        default_factory=_PromptPreferenceService
    )
    danbooru_preference_service: _DanbooruPreferenceService = field(
        default_factory=_DanbooruPreferenceService
    )
    civitai_preference_service: _CivitaiPreferenceService = field(
        default_factory=_CivitaiPreferenceService
    )
    civitai_credential_service: _CivitaiCredentialService = field(
        default_factory=_CivitaiCredentialService
    )
    preference_setup_service: _PreferenceSetupService = field(
        default_factory=_PreferenceSetupService
    )
