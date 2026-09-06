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

"""Own process-lifetime execution-lane configuration policy."""

from __future__ import annotations

from dataclasses import dataclass

_QUEUE_CAPACITY_MULTIPLIER = 4


@dataclass(frozen=True, slots=True)
class ExecutionLaneConfig:
    """Describe one process-lifetime short-task execution lane."""

    name: str
    max_workers: int
    queue_capacity: int
    thread_name_prefix: str


def require_non_blank(value: str, *, field_name: str) -> None:
    """Reject blank runtime labels."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")


def _lane_config(name: str, *, max_workers: int) -> ExecutionLaneConfig:
    """Build one default lane config."""

    require_non_blank(name, field_name="name")
    if max_workers <= 0:
        raise ValueError("max_workers must be positive.")
    return ExecutionLaneConfig(
        name=name,
        max_workers=max_workers,
        queue_capacity=max_workers * _QUEUE_CAPACITY_MULTIPLIER,
        thread_name_prefix=f"substitute-{name.replace('_', '-')}",
    )


def _lane_config_with_capacity(
    name: str,
    *,
    max_workers: int,
    queue_capacity: int,
) -> ExecutionLaneConfig:
    """Build one lane config with explicit burst capacity."""

    require_non_blank(name, field_name="name")
    if max_workers <= 0:
        raise ValueError("max_workers must be positive.")
    if queue_capacity <= 0:
        raise ValueError("queue_capacity must be positive.")
    return ExecutionLaneConfig(
        name=name,
        max_workers=max_workers,
        queue_capacity=queue_capacity,
        thread_name_prefix=f"substitute-{name.replace('_', '-')}",
    )


def validate_lane_config(config: ExecutionLaneConfig) -> None:
    """Validate one externally supplied execution lane config."""

    require_non_blank(config.name, field_name="name")
    require_non_blank(config.thread_name_prefix, field_name="thread_name_prefix")
    if config.max_workers <= 0:
        raise ValueError("max_workers must be positive.")
    if config.queue_capacity <= 0:
        raise ValueError("queue_capacity must be positive.")


DEFAULT_EXECUTION_LANE_CONFIGS = (
    _lane_config_with_capacity("prompt_editor", max_workers=2, queue_capacity=128),
    _lane_config("settings_io", max_workers=2),
    _lane_config("package_maintenance", max_workers=1),
    _lane_config("onboarding_provisioning", max_workers=1),
    _lane_config("onboarding_environment", max_workers=1),
    _lane_config("onboarding_models", max_workers=2),
    _lane_config_with_capacity(
        "onboarding_model_thumbnails",
        max_workers=4,
        queue_capacity=64,
    ),
    _lane_config("generation_dispatch", max_workers=1),
    _lane_config("generation_preparation", max_workers=1),
    _lane_config("cube_load", max_workers=2),
    _lane_config("cube_library_update", max_workers=1),
    _lane_config("model_catalog", max_workers=1),
    _lane_config("model_metadata", max_workers=1),
    _lane_config("node_definition", max_workers=2),
    _lane_config("recipe_model_resolution", max_workers=1),
    _lane_config("danbooru_refresh", max_workers=2),
    _lane_config("image_decode", max_workers=2),
    _lane_config_with_capacity(
        "thumbnail_decode",
        max_workers=4,
        queue_capacity=64,
    ),
    _lane_config("disk_io_low_priority", max_workers=1),
    _lane_config("model_download", max_workers=2),
    _lane_config("startup", max_workers=2),
    _lane_config("shutdown", max_workers=1),
)


__all__ = [
    "DEFAULT_EXECUTION_LANE_CONFIGS",
    "ExecutionLaneConfig",
    "require_non_blank",
    "validate_lane_config",
]
