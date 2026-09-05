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

"""Own the ordered catalog of supported model families."""

from __future__ import annotations

from collections.abc import Collection, Iterable

from sugarsubstitute_shared.model_discovery import ModelArtifactKind

from substitute.domain.model_recommendations.models import (
    CivitaiFamilyMapping,
    FamilyDetectionPolicy,
    ModelFamilyDefinition,
    ModelFamilyId,
    ModelRecipeRole,
    TensorShapeSignature,
    TrustedRecipeAsset,
)


class SupportedModelFamilyCatalog:
    """Provide ordered, uniquely identified model-family definitions."""

    def __init__(self, families: Iterable[ModelFamilyDefinition]) -> None:
        """Validate and retain one immutable family catalog."""

        ordered = tuple(sorted(families, key=lambda family: family.catalog_order))
        identities = tuple(family.family_id for family in ordered)
        orders = tuple(family.catalog_order for family in ordered)
        if len(identities) != len(set(identities)):
            raise ValueError("Model family identifiers must be unique.")
        if len(orders) != len(set(orders)):
            raise ValueError("Model family catalog orders must be unique.")
        self._families = ordered
        self._by_id = {family.family_id: family for family in ordered}

    def families(self) -> tuple[ModelFamilyDefinition, ...]:
        """Return all supported families in product order."""

        return self._families

    def get(self, family_id: ModelFamilyId) -> ModelFamilyDefinition:
        """Return the exact definition for one supported family."""

        try:
            return self._by_id[family_id]
        except KeyError as error:
            raise ValueError(f"Unsupported model family: {family_id.value}") from error

    def missing_from(
        self,
        detected: Collection[ModelFamilyId],
    ) -> tuple[ModelFamilyId, ...]:
        """Return absent supported families in stable recommendation order."""

        present = frozenset(detected)
        return tuple(
            family.family_id
            for family in self._families
            if family.family_id not in present
        )


SUPPORTED_MODEL_FAMILIES = SupportedModelFamilyCatalog(
    (
        ModelFamilyDefinition(
            family_id=ModelFamilyId.SDXL,
            catalog_order=10,
            civitai=CivitaiFamilyMapping(
                recommendation_base_model="Illustrious",
                model_type="Checkpoint",
            ),
            detection=FamilyDetectionPolicy(
                artifact_kind=ModelArtifactKind.CHECKPOINTS,
                metadata_values=frozenset(
                    {
                        "sdxl",
                        "sdxl 1.0",
                        "stable diffusion xl",
                        "stable-diffusion-xl-v1-base",
                        "stable-diffusion-xl-v1-refiner",
                        "sdxl_base_v1-0",
                        "pony",
                        "pony diffusion",
                        "illustrious",
                        "noobai",
                    }
                ),
                tensor_key_prefixes=(),
                tensor_shape_signatures=(
                    TensorShapeSignature(
                        "input_blocks.0.0.weight",
                        (320, 4, 3, 3),
                    ),
                    TensorShapeSignature(
                        "label_emb.0.0.weight",
                        (None, 2816),
                    ),
                    TensorShapeSignature(
                        "attn2.to_k.weight",
                        (None, 2048),
                    ),
                ),
            ),
            primary_artifact_kind=ModelArtifactKind.CHECKPOINTS,
        ),
        ModelFamilyDefinition(
            family_id=ModelFamilyId.ANIMA,
            catalog_order=20,
            civitai=CivitaiFamilyMapping(
                recommendation_base_model="Anima",
                model_type="Checkpoint",
            ),
            detection=FamilyDetectionPolicy(
                artifact_kind=ModelArtifactKind.DIFFUSION_MODELS,
                metadata_values=frozenset({"anima"}),
                tensor_key_prefixes=(
                    "model.diffusion_model.double_blocks.",
                    "diffusion_model.double_blocks.",
                ),
            ),
            primary_artifact_kind=ModelArtifactKind.DIFFUSION_MODELS,
            auxiliaries=(
                TrustedRecipeAsset(
                    role=ModelRecipeRole.TEXT_ENCODER,
                    artifact_kind=ModelArtifactKind.TEXT_ENCODERS,
                    filename="qwen_3_06b_base.safetensors",
                    subfolder="qwen",
                    source_url=(
                        "https://huggingface.co/circlestone-labs/Anima/resolve/main/"
                        "split_files/text_encoders/qwen_3_06b_base.safetensors"
                    ),
                    sha256=(
                        "cd2a512003e2f9f3cd3c32a9c3573f820bb28c940f73c57b1ddaa983d9223eba"
                    ),
                    size_bytes=1_192_135_096,
                ),
                TrustedRecipeAsset(
                    role=ModelRecipeRole.VAE,
                    artifact_kind=ModelArtifactKind.VAE,
                    filename="qwen_image_vae.safetensors",
                    subfolder="qwen",
                    source_url=(
                        "https://huggingface.co/circlestone-labs/Anima/resolve/main/"
                        "split_files/vae/qwen_image_vae.safetensors"
                    ),
                    sha256=(
                        "a70580f0213e67967ee9c95f05bb400e8fb08307e017a924bf3441223e023d1f"
                    ),
                    size_bytes=253_806_246,
                ),
            ),
        ),
    )
)


__all__ = ["SUPPORTED_MODEL_FAMILIES", "SupportedModelFamilyCatalog"]
