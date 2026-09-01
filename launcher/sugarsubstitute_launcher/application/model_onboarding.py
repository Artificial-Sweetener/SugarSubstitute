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

"""Compose reusable installer and empty-picker model onboarding use cases."""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path

from sugarsubstitute_shared.model_acquisition import (
    ModelAcquisitionService,
)
from sugarsubstitute_shared.model_discovery import (
    CivitaiDiscoveryClient,
    CubeModelCapability,
    LocalModel,
    ModelCategory,
    ModelOnboardingService,
    ModelDiscoveryPlanner,
)

_MODEL_EXTENSIONS = frozenset({".safetensors", ".ckpt", ".pt", ".pth", ".bin"})
_BUNDLED_SUGARCUBES_MODEL_CATEGORIES = frozenset(
    {
        ModelCategory.CHECKPOINTS,
        ModelCategory.DIFFUSION_MODELS,
        ModelCategory.LORAS,
        ModelCategory.VAE,
        ModelCategory.CONTROLNET,
        ModelCategory.UPSCALE_MODELS,
    }
)


class ManagedComfyModelFolders:
    """Own installer-safe inventory and destinations below one managed Comfy root."""

    def __init__(self, model_root: Path) -> None:
        """Store the model root without creating it during eligibility checks."""

        self._model_root = Path(model_root)

    def list_models(
        self,
        categories: Collection[ModelCategory],
    ) -> tuple[LocalModel, ...]:
        """List existing model files from only requested category folders."""

        models: list[LocalModel] = []
        for category in ModelCategory:
            if category not in categories:
                continue
            folder = self.destination_for(category)
            if not folder.is_dir() or folder.is_symlink():
                continue
            for path in folder.rglob("*"):
                if (
                    path.is_file()
                    and not path.is_symlink()
                    and path.suffix.casefold() in _MODEL_EXTENSIONS
                ):
                    models.append(LocalModel(category=category, path=path))
        return tuple(models)

    def destination_for(self, category: ModelCategory) -> Path:
        """Return the standard managed-Comfy model folder for one category."""

        return self._model_root / category.value


def default_installer_capabilities() -> tuple[CubeModelCapability, ...]:
    """Return categories supported by the release's bundled SugarCubes contract."""

    return (
        CubeModelCapability(
            cube_id="bundled-sugarcubes",
            categories=_BUNDLED_SUGARCUBES_MODEL_CATEGORIES,
        ),
    )


def build_installer_model_onboarding(
    *,
    model_root: Path,
) -> ModelOnboardingService:
    """Compose side-effect-free model onboarding for one managed model root."""

    folders = ManagedComfyModelFolders(model_root)
    planner = ModelDiscoveryPlanner(
        inventory=folders,
        discovery=CivitaiDiscoveryClient(),
        destinations=folders,
    )
    return ModelOnboardingService(
        planner=planner,
        acquisition=ModelAcquisitionService(allowed_roots=(model_root,)),
    )


__all__ = [
    "ManagedComfyModelFolders",
    "build_installer_model_onboarding",
    "default_installer_capabilities",
]
