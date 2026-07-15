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

"""Define UI-facing onboarding flow models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class OnboardingFlowMode(str, Enum):
    """Describe the top-level onboarding presentation entry mode."""

    FIRST_RUN = "first_run"
    REPAIR = "repair"
    RECONFIGURE = "reconfigure"


class OnboardingPageId(str, Enum):
    """Identify the dedicated pages that make up onboarding flow."""

    WELCOME = "welcome"
    TARGET_MODE = "target_mode"
    MANAGED_LOCAL = "managed_local"
    ATTACHED_LOCAL = "attached_local"
    REMOTE = "remote"
    FOLDERS = "folders"
    INTEGRATIONS = "integrations"
    PROVISIONING = "provisioning"
    COMPLETION = "completion"


class OnboardingTargetMode(str, Enum):
    """Identify target-mode selections inside onboarding presentation state."""

    MANAGED_LOCAL = "managed_local"
    ATTACHED_LOCAL = "attached_local"
    REMOTE = "remote"


def initial_onboarding_page(*, install_root_locked: bool) -> OnboardingPageId:
    """Return the first visible onboarding page for one install mode."""

    if install_root_locked:
        return OnboardingPageId.TARGET_MODE
    return OnboardingPageId.WELCOME


@dataclass(frozen=True)
class OnboardingDraft:
    """Capture the current onboarding selections shown in the UI."""

    installation_root: Path
    target_mode: OnboardingTargetMode
    endpoint_host: str
    endpoint_port: int
    managed_workspace_path: Path
    attached_workspace_path: Path | None
    managed_model_root: Path | None = None
    managed_model_root_uses_default: bool = True
    output_root: Path | None = None
    output_root_uses_default: bool = True
    danbooru_tag_help_enabled: bool = True
    danbooru_safe_previews_enabled: bool = True
    danbooru_image_rating_policy: str = "safe_only"
    civitai_model_help_enabled: bool = True
    civitai_downloads_enabled: bool = True
    civitai_safe_thumbnails_enabled: bool = True
    civitai_thumbnail_safety_policy: str = "sfw_only"
    civitai_api_key_configured: bool = False
    detected_platform: str | None = None
    detected_accelerator: str | None = None
    selected_install_target: str | None = None
    selected_python_version: str | None = None
    selected_comfy_channel: str | None = None
    selected_backend_policy: str | None = None
    selected_torch_channel: str | None = None
    selected_torch_reason: str | None = None
    selected_stability: str | None = None
    force_cpu_mode: bool = False
    prefer_edge_torch: bool = False
    prefer_edge_comfy_channel: bool = False


@dataclass(frozen=True)
class OnboardingCompletion:
    """Capture the result of a successful onboarding or repair run."""

    context: object
    restart_required: bool
    launch_command: tuple[str, ...]
