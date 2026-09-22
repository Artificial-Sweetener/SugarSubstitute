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

"""Build deterministic model-acquisition fixtures and local preview images."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter

from substitute.application.recipes import (
    RecipeModelCivitaiState,
    RecipeModelDownloadCandidate,
    RecipeModelResolutionRequired,
    RecipeModelResolutionSummary,
    RecipeModelUnresolvedReference,
)
from substitute.domain.model_metadata import CivitaiDownloadAccess
from substitute.domain.recipes import ParsedSugarScript, SugarBufferMap


@dataclass(frozen=True, slots=True)
class ModelRenderSpec:
    """Describe one deterministic model card fixture."""

    sha256: str
    kind: str
    value: str
    model_name: str
    version_name: str
    size_kb: float
    color: str
    access: CivitaiDownloadAccess = CivitaiDownloadAccess.PUBLIC
    available: bool = True


def ready_requirement() -> RecipeModelResolutionRequired:
    """Return a dense public-model cart requirement."""

    return _required(_ready_specs())


def gated_requirement() -> RecipeModelResolutionRequired:
    """Return a mixed public and provider-gated cart requirement."""

    ready = _ready_specs()
    return _required(
        (
            ready[0],
            ModelRenderSpec(
                "B" * 64,
                "loras",
                "neon-style.safetensors",
                "Neon Style",
                "Creator release",
                148_000,
                "#d63384",
                access=CivitaiDownloadAccess.API_KEY_REQUIRED,
            ),
            ready[2],
        )
    )


def unavailable_requirement() -> RecipeModelResolutionRequired:
    """Return a cart with one exact hash lacking a safe verified file."""

    ready = _ready_specs()
    return _required(
        (
            ready[0],
            ModelRenderSpec(
                "E" * 64,
                "checkpoints",
                "unverified-model.ckpt",
                "Unverified Model",
                "unknown",
                0,
                "#b02a37",
                available=False,
            ),
            ready[2],
        )
    )


def preview_images(
    required: RecipeModelResolutionRequired,
) -> dict[str, QImage]:
    """Return trusted local previews for every available render fixture."""

    specs = _specs_by_hash()
    return {
        reference.sha256: _thumbnail(
            reference.candidate.model_name,
            specs[reference.sha256].color,
        )
        for reference in required.references
        if reference.candidate is not None
    }


def _required(specs: Sequence[ModelRenderSpec]) -> RecipeModelResolutionRequired:
    """Build unresolved exact-model state for production presentation."""

    references: list[RecipeModelUnresolvedReference] = []
    buffers: OrderedDict[str, object] = OrderedDict()
    hashes: dict[tuple[str, str, str], str] = {}
    for index, spec in enumerate(specs, start=1):
        alias = f"Model {index}"
        node_name = f"loader_{index}"
        input_key = "model_name"
        candidate = _candidate(spec, index) if spec.available else None
        references.append(
            RecipeModelUnresolvedReference(
                alias=alias,
                node_name=node_name,
                input_key=input_key,
                kind=spec.kind,
                value=spec.value,
                sha256=spec.sha256,
                civitai_state=(
                    RecipeModelCivitaiState.FOUND
                    if spec.available
                    else RecipeModelCivitaiState.NO_SAFE_FILE
                ),
                candidate=candidate,
            )
        )
        buffers[alias] = OrderedDict(
            {
                "cube_id": f"qualification-{index}",
                "nodes": {node_name: {"inputs": {input_key: spec.value}}},
            }
        )
        hashes[(alias, node_name, input_key)] = spec.sha256
    parsed = ParsedSugarScript(
        buffers=cast(SugarBufferMap, buffers),
        global_overrides={},
        global_override_selections={},
        field_control_states_by_alias={},
        override_control_states={},
        model_hashes_by_field=hashes,
        prompt_lora_hashes_by_field={},
        project_name=None,
    )
    return RecipeModelResolutionRequired(
        references=tuple(references),
        partial_script=parsed,
        summary=RecipeModelResolutionSummary(unresolved_hashes=len(references)),
    )


def _candidate(
    spec: ModelRenderSpec,
    index: int,
) -> RecipeModelDownloadCandidate:
    """Build one exact safe provider candidate for a model card."""

    return RecipeModelDownloadCandidate(
        kind=spec.kind,
        sha256=spec.sha256,
        name=spec.value,
        download_url=f"https://civitai.com/api/download/models/{100 + index}",
        size_kb=spec.size_kb,
        model_id=200 + index,
        model_version_id=100 + index,
        model_name=spec.model_name,
        version_name=spec.version_name,
        base_model="SDXL 1.0",
        creator="Qualification Studio",
        file_id=300 + index,
        file_type="Model",
        metadata_format="SafeTensor",
        pickle_scan_result="Success",
        virus_scan_result="Success",
        model_page_url=f"https://civitai.com/models/{200 + index}",
        thumbnail_url=None,
        download_access=spec.access,
    )


def _ready_specs() -> tuple[ModelRenderSpec, ...]:
    """Return the public fixture specifications."""

    return (
        ModelRenderSpec(
            "A" * 64,
            "checkpoints",
            "dream-xl.safetensors",
            "Dream XL",
            "v3",
            6_210_000,
            "#6f42c1",
        ),
        ModelRenderSpec(
            "B" * 64,
            "loras",
            "neon-style.safetensors",
            "Neon Style",
            "v2",
            148_000,
            "#d63384",
        ),
        ModelRenderSpec(
            "C" * 64,
            "upscale_models",
            "4x-detail.pth",
            "4x Detail",
            "v1",
            65_000,
            "#0d6efd",
        ),
        ModelRenderSpec(
            "D" * 64,
            "vae",
            "clear-vae.safetensors",
            "Clear VAE",
            "v1",
            320_000,
            "#198754",
        ),
    )


def _specs_by_hash() -> dict[str, ModelRenderSpec]:
    """Return stable preview color ownership for every fixture hash."""

    return {
        spec.sha256: spec
        for spec in (
            *_ready_specs(),
            ModelRenderSpec(
                "E" * 64,
                "checkpoints",
                "unverified-model.ckpt",
                "Unverified Model",
                "unknown",
                0,
                "#b02a37",
                available=False,
            ),
        )
    }


def _thumbnail(title: str, color: str) -> QImage:
    """Create a deterministic local preview so qualification never uses network."""

    image = QImage(368, 400, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    gradient = QLinearGradient(0, 0, image.width(), image.height())
    gradient.setColorAt(0.0, QColor(color))
    gradient.setColorAt(1.0, QColor("#151515"))
    painter.fillRect(image.rect(), gradient)
    painter.setPen(QColor("#ffffff"))
    painter.setFont(QFont("Segoe UI", 44, QFont.Weight.Bold))
    initials = "".join(word[:1] for word in title.split()[:3]).upper()
    painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, initials)
    painter.end()
    return image


__all__ = [
    "gated_requirement",
    "preview_images",
    "ready_requirement",
    "unavailable_requirement",
]
