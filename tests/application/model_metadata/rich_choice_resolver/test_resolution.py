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

"""Tests for value-driven rich model choice resolution."""

from __future__ import annotations

from substitute.application.model_metadata import (
    ModelCatalogItem,
    ModelCatalogSnapshot,
    ModelThumbnailVariant,
    ModelChoiceCatalogIndex,
    RichChoiceContext,
    RichChoiceResolver,
)


class _FakeModelCatalog:
    """Return deterministic model catalog rows for rich choice tests."""

    def __init__(self, items: tuple[ModelCatalogItem, ...]) -> None:
        """Store model rows and record kind lookups."""

        self._items = items
        self.list_calls: list[str] = []
        self.refresh_calls: list[str] = []

    def replace_items(self, items: tuple[ModelCatalogItem, ...]) -> None:
        """Replace catalog rows for invalidation tests."""

        self._items = items

    def list_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return fake model rows scoped to one kind."""

        self.list_calls.append(kind)
        return tuple(item for item in self._items if item.kind == kind)

    def refresh_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return fake model rows scoped to one refreshed kind."""

        self.refresh_calls.append(kind)
        return tuple(item for item in self._items if item.kind == kind)

    def invalidate(self, kind: str | None = None) -> None:
        """Ignore invalidation because tests own catalog state."""

        _ = kind


class _SnapshotModelCatalog:
    """Expose canonical snapshots for model choice generation tests."""

    def __init__(self, snapshot: ModelCatalogSnapshot) -> None:
        """Store the current canonical snapshot."""

        self.snapshot = snapshot
        self.refresh_snapshot_calls: list[str] = []

    def list_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return canonical rows for one kind."""

        return self.snapshot_for_kind(kind).items

    def refresh_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Refresh and return canonical rows for one kind."""

        return self.refresh_snapshot(kind).items

    def snapshot_for_kind(self, kind: str) -> ModelCatalogSnapshot:
        """Return the current canonical snapshot for one kind."""

        if kind != self.snapshot.kind:
            return ModelCatalogSnapshot(kind=kind, items=(), generation=0)
        return self.snapshot

    def cached_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return the installed canonical snapshot without loading."""

        if kind != self.snapshot.kind:
            return None
        return self.snapshot

    def refresh_snapshot(self, kind: str) -> ModelCatalogSnapshot:
        """Record refresh fallback use and return the current canonical snapshot."""

        self.refresh_snapshot_calls.append(kind)
        return self.snapshot_for_kind(kind)

    def invalidate(self, kind: str | None = None) -> None:
        """Ignore invalidation because tests own canonical state."""

        _ = kind


class _FailingRefreshModelCatalog(_SnapshotModelCatalog):
    """Raise during canonical refresh while still allowing passive reads."""

    def refresh_snapshot(self, kind: str) -> ModelCatalogSnapshot:
        """Raise to simulate Backend being unavailable on picker open."""

        self.refresh_snapshot_calls.append(kind)
        raise RuntimeError("backend unavailable")


class _ColdCachedModelCatalog(_SnapshotModelCatalog):
    """Expose cached-snapshot API while making cold loads fail."""

    def cached_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return no installed snapshot for the requested kind."""

        _ = kind
        return None

    def snapshot_for_kind(self, kind: str) -> ModelCatalogSnapshot:
        """Fail if a nonblocking GUI lookup attempts to cold-load."""

        raise RuntimeError(f"unexpected cold load for {kind}")


def test_rich_choice_resolver_upgrades_lora_values_without_node_registry() -> None:
    """LoRA LIST choices should qualify from exact catalog values alone."""

    catalog = _FakeModelCatalog(
        (
            _item("loras", "animeLineart.safetensors", "Anime Lineart"),
            _item("loras", "stylePack.safetensors", "Style Pack"),
        )
    )
    resolver = _resolver(catalog)

    resolution = resolver.resolve(
        ("animeLineart.safetensors", "stylePack.safetensors"),
        context=RichChoiceContext(node_class="SomeLoraLoader", field_key="lora_name"),
    )

    assert resolution.should_use_rich_picker is True
    assert resolution.matched_kinds == ("loras",)
    assert resolution.enriched_count == 2
    assert [item.value for item in resolution.items] == [
        "animeLineart.safetensors",
        "stylePack.safetensors",
    ]
    assert [item.title for item in resolution.items] == [
        "Anime Lineart",
        "Style Pack",
    ]
    assert catalog.list_calls == [
        "checkpoints",
        "loras",
        "vae",
        "diffusion_models",
    ]


def test_rich_choice_resolver_keeps_vae_literals_as_no_thumbnail_choices() -> None:
    """VAE lists should include special Comfy literals as unenriched picker choices."""

    catalog = _FakeModelCatalog(
        (
            _item("vae", "ClearVAE.safetensors", "ClearVAE"),
            _item("vae", "Illustrious\\neptunia.safetensors", "Neptunia VAE"),
        )
    )
    resolver = _resolver(catalog)

    resolution = resolver.resolve(
        (
            "ClearVAE.safetensors",
            "Illustrious\\neptunia.safetensors",
            "pixel_space",
        )
    )

    assert resolution.should_use_rich_picker is True
    assert resolution.matched_kinds == ("vae",)
    assert resolution.enriched_count == 2
    assert resolution.unmatched_count == 1
    assert resolution.items[2].value == "pixel_space"
    assert resolution.items[2].is_enriched is False
    assert resolution.items[2].thumbnail_variants == ()


def test_rich_choice_resolver_enables_diffusion_models_by_default() -> None:
    """Diffusion model LIST choices should qualify from default model kinds."""

    catalog = _FakeModelCatalog(
        (
            _item(
                "diffusion_models",
                "Anima\\anima_base_V10.safetensors",
                "Anima Base",
            ),
            _item(
                "diffusion_models",
                "Anima\\animaOfficial_preview3Base.safetensors",
                "Anima Preview",
            ),
        )
    )
    resolver = _resolver(catalog)

    resolution = resolver.resolve(
        (
            "Anima\\anima_base_V10.safetensors",
            "Anima\\animaOfficial_preview3Base.safetensors",
        ),
        context=RichChoiceContext(
            node_class="SimpleSyrup.SimpleLoadAnima",
            field_key="diffusion_model",
        ),
    )

    assert resolution.should_use_rich_picker is True
    assert resolution.matched_kinds == ("diffusion_models",)
    assert resolution.enriched_count == 2
    assert [item.value for item in resolution.items] == [
        "Anima\\anima_base_V10.safetensors",
        "Anima\\animaOfficial_preview3Base.safetensors",
    ]


def test_rich_choice_resolver_keeps_mostly_literal_lists_plain() -> None:
    """A single enriched value among many literals should not upgrade the control."""

    catalog = _FakeModelCatalog(
        (_item("checkpoints", "model-a.safetensors", "Model A"),)
    )
    resolver = _resolver(catalog)

    resolution = resolver.resolve(("model-a.safetensors", "alpha", "beta", "gamma"))

    assert resolution.should_use_rich_picker is False
    assert resolution.enriched_count == 1
    assert resolution.reason == "too few enriched choices"


def test_rich_choice_source_refreshes_only_matched_model_kinds() -> None:
    """Popup refresh should reload the kinds established by the current resolution."""

    catalog = _FakeModelCatalog(
        (
            _item("checkpoints", "base-a.safetensors", "Base A"),
            _item("checkpoints", "base-b.safetensors", "Base B"),
        )
    )
    resolver = _resolver(catalog)
    initial = resolver.resolve(("base-a.safetensors", "base-b.safetensors"))
    source = resolver.source_for_options(
        ("base-a.safetensors", "base-b.safetensors"),
        initial_resolution=initial,
    )

    refreshed = source.refresh()

    assert refreshed.should_use_rich_picker is True
    assert catalog.refresh_calls == ["checkpoints"]


def test_rich_choice_source_refresh_reports_unavailable_on_backend_failure() -> None:
    """Popup refresh failures should not preserve stale choices as selectable rows."""

    item = _item("loras", "old-lora.safetensors", "Old LoRA")
    catalog = _FailingRefreshModelCatalog(
        ModelCatalogSnapshot(kind="loras", items=(item,), generation=1)
    )
    resolver = RichChoiceResolver(
        catalog_index=ModelChoiceCatalogIndex(
            model_catalog=catalog,
            enabled_kinds=("loras",),
        )
    )
    initial = resolver.resolve(("old-lora.safetensors",))
    source = resolver.source_for_options(
        ("old-lora.safetensors",),
        initial_resolution=initial,
    )

    refreshed = source.refresh()

    assert refreshed.items == ()
    assert refreshed.should_use_rich_picker is True
    assert refreshed.unavailable_reason is not None
    assert "backend model catalog refresh failed" in refreshed.unavailable_reason
    assert catalog.refresh_snapshot_calls == ["loras"]


def test_rich_choice_resolver_prewarm_loads_catalog_before_first_resolve() -> None:
    """Prewarm should pay catalog-index loading before editor widget construction."""

    catalog = _FakeModelCatalog(
        (
            _item("checkpoints", "base-a.safetensors", "Base A"),
            _item("checkpoints", "base-b.safetensors", "Base B"),
        )
    )
    resolver = _resolver(catalog)

    warmed_count = resolver.prewarm()
    resolution = resolver.resolve(("base-a.safetensors", "base-b.safetensors"))

    assert warmed_count == 0
    assert resolution.should_use_rich_picker is True
    assert catalog.list_calls == [
        "checkpoints",
        "loras",
        "vae",
        "diffusion_models",
    ]


def test_rich_choice_resolver_exposes_enabled_kinds() -> None:
    """Presentation factories should be able to choose a compatible shared resolver."""

    resolver = _resolver(_FakeModelCatalog(()))

    assert resolver.enabled_kinds == (
        "checkpoints",
        "loras",
        "vae",
        "diffusion_models",
    )


def test_rich_choice_resolver_prewarm_caches_exact_option_lists() -> None:
    """Prewarm should also cache exact LIST resolutions when options are known."""

    catalog = _FakeModelCatalog(
        (
            _item("checkpoints", "base-a.safetensors", "Base A"),
            _item("checkpoints", "base-b.safetensors", "Base B"),
        )
    )
    resolver = _resolver(catalog)

    warmed_count = resolver.prewarm((("base-a.safetensors", "base-b.safetensors"),))
    cached_count = resolver.cached_resolution_count()
    resolution = resolver.resolve(("base-a.safetensors", "base-b.safetensors"))

    assert warmed_count == 1
    assert cached_count == 1
    assert resolution.should_use_rich_picker is True
    assert catalog.list_calls == [
        "checkpoints",
        "loras",
        "vae",
        "diffusion_models",
    ]


def test_rich_choice_resolver_invalidate_reloads_catalog_values() -> None:
    """Invalidation should clear stale exact-value indexes and cached resolutions."""

    catalog = _FakeModelCatalog(())
    resolver = _resolver(catalog)
    first_resolution = resolver.resolve(("base-a.safetensors", "base-b.safetensors"))
    catalog.replace_items(
        (
            _item("checkpoints", "base-a.safetensors", "Base A"),
            _item("checkpoints", "base-b.safetensors", "Base B"),
        )
    )

    resolver.invalidate("checkpoints")
    second_resolution = resolver.resolve(("base-a.safetensors", "base-b.safetensors"))

    assert first_resolution.should_use_rich_picker is False
    assert second_resolution.should_use_rich_picker is True
    assert second_resolution.matched_kinds == ("checkpoints",)
    assert catalog.list_calls == [
        "checkpoints",
        "loras",
        "vae",
        "diffusion_models",
        "checkpoints",
        "loras",
        "vae",
        "diffusion_models",
    ]


def test_model_choice_index_refresh_uses_cached_canonical_lora_generation() -> None:
    """Picker refresh should reuse a newer canonical LoRA snapshot already installed."""

    old_item = _item("loras", "old-lora.safetensors", "Old LoRA")
    new_item = _item(
        "loras",
        "new-lora.safetensors",
        "New LoRA",
        thumbnail_variants=(
            ModelThumbnailVariant(
                size=256,
                storage_key="new-lora:standard:256",
                width=256,
                height=256,
                content_format="sqthumb-qimage-argb32-premultiplied",
                byte_size=262144,
            ),
        ),
    )
    catalog = _SnapshotModelCatalog(
        ModelCatalogSnapshot(kind="loras", items=(old_item,), generation=1)
    )
    index = ModelChoiceCatalogIndex(
        model_catalog=catalog,
        enabled_kinds=("loras",),
    )
    index.prewarm()
    catalog.snapshot = ModelCatalogSnapshot(
        kind="loras",
        items=(new_item,),
        generation=2,
    )

    index.refresh_kinds(("loras",))

    assert catalog.refresh_snapshot_calls == []
    assert index.candidates_for_value("old-lora.safetensors") == ()
    candidates = index.candidates_for_value("new-lora.safetensors")
    assert candidates == (new_item,)
    assert candidates[0].thumbnail_variants[0].storage_key == ("new-lora:standard:256")


def test_rich_choice_resolver_invalidation_observes_canonical_lora_generation() -> None:
    """Rich choice cache invalidation should reload from the canonical LoRA snapshot."""

    catalog = _SnapshotModelCatalog(
        ModelCatalogSnapshot(kind="loras", items=(), generation=0)
    )
    resolver = RichChoiceResolver(
        catalog_index=ModelChoiceCatalogIndex(model_catalog=catalog)
    )
    first_resolution = resolver.resolve(("lora-a.safetensors", "lora-b.safetensors"))
    catalog.snapshot = ModelCatalogSnapshot(
        kind="loras",
        items=(
            _item("loras", "lora-a.safetensors", "LoRA A"),
            _item("loras", "lora-b.safetensors", "LoRA B"),
        ),
        generation=1,
    )

    resolver.invalidate("loras")
    second_resolution = resolver.resolve(("lora-a.safetensors", "lora-b.safetensors"))

    assert first_resolution.should_use_rich_picker is False
    assert second_resolution.should_use_rich_picker is True
    assert second_resolution.matched_kinds == ("loras",)


def test_model_choice_index_main_thread_uses_cached_snapshots_without_loading() -> None:
    """Main-thread rich choice lookup should not cold-load the model catalog."""

    catalog = _ColdCachedModelCatalog(
        ModelCatalogSnapshot(kind="checkpoints", items=(), generation=0)
    )
    resolver = RichChoiceResolver(
        catalog_index=ModelChoiceCatalogIndex(
            model_catalog=catalog,
            enabled_kinds=("checkpoints",),
        )
    )

    resolution = resolver.resolve(("model.safetensors",))

    assert resolution.should_use_rich_picker is False


def test_rich_choice_resolver_marks_cross_kind_ambiguity_without_guessing() -> None:
    """Exact values found in multiple kinds should avoid unsafe enrichment."""

    catalog = _FakeModelCatalog(
        (
            _item("checkpoints", "shared.safetensors", "Checkpoint Shared"),
            _item("loras", "shared.safetensors", "LoRA Shared"),
            _item("vae", "only-vae.safetensors", "VAE Only"),
            _item("vae", "other-vae.safetensors", "Other VAE"),
        )
    )
    resolver = _resolver(catalog)

    resolution = resolver.resolve(
        ("shared.safetensors", "only-vae.safetensors", "other-vae.safetensors")
    )

    assert resolution.should_use_rich_picker is True
    assert resolution.items[0].is_enriched is False
    assert resolution.items[0].is_ambiguous is True
    assert resolution.items[0].model_kind is None
    assert resolution.matched_kinds == ("vae",)


def _resolver(catalog: _FakeModelCatalog) -> RichChoiceResolver:
    """Return a resolver using the default rich-picker model kinds."""

    return RichChoiceResolver(
        catalog_index=ModelChoiceCatalogIndex(model_catalog=catalog)
    )


def _item(
    kind: str,
    value: str,
    display_name: str,
    *,
    thumbnail_variants: tuple[ModelThumbnailVariant, ...] = (),
) -> ModelCatalogItem:
    """Return one minimal catalog item for rich choice tests."""

    basename = value.replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".safetensors")
    folder = value.rsplit("\\", 1)[0] if "\\" in value else ""
    return ModelCatalogItem(
        kind=kind,
        display_name=display_name,
        display_subtitle=None,
        backend_value=value,
        relative_path=value,
        folder=folder,
        basename=basename,
        extension=".safetensors",
        thumbnail_variants=thumbnail_variants,
        base_model=None,
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=basename.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=f"{display_name} {value}".replace("\\", "/").casefold(),
    )
