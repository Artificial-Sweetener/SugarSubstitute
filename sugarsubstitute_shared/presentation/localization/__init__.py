#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Expose reusable Qt localization presentation primitives."""

from sugarsubstitute_shared.presentation.localization.application_text import (
    LocalizedPropertyBinding,
    clear_localized_property,
    set_localized_accessible_description,
    set_localized_accessible_name,
    set_localized_placeholder,
    set_localized_text,
    set_localized_tooltip,
    set_localized_window_title,
    translate_application_message,
    translate_application_text,
)
from sugarsubstitute_shared.localization import (
    ApplicationMessage,
    ApplicationText,
    app_text,
)
from sugarsubstitute_shared.presentation.localization.application_message import (
    ApplicationTextTarget,
    apply_application_text,
    render_application_text,
)
from sugarsubstitute_shared.presentation.localization.bindings import (
    LocalizationBindings,
    LocalizedComboItem,
    LocalizedComboItemTextBinding,
    TextFactory,
    set_localized_combo_item,
    set_localized_combo_items,
)
from sugarsubstitute_shared.presentation.localization.composite_translator import (
    CompositeTranslator,
)
from sugarsubstitute_shared.presentation.localization.catalog_bundle_loader import (
    CatalogRole,
    FluentTranslatorFactory,
    LanguageResourceLoader,
    QtCatalogBundleLoader,
)
from sugarsubstitute_shared.presentation.localization.language_bundle import (
    PreparedLanguageBundle,
)
from sugarsubstitute_shared.presentation.localization.font_profile import (
    localized_application_font,
)
from sugarsubstitute_shared.presentation.localization.qfluent_font_adapter import (
    FontFamilyState,
    QFluentFontFamilyAdapter,
)
from sugarsubstitute_shared.presentation.localization.translation_manager import (
    ApplicationFontAdapter,
    LanguageBundleLoader,
    LanguageSnapshot,
    LocalizationPreferenceStoreProtocol,
    TranslationManager,
)

__all__ = [
    "ApplicationFontAdapter",
    "ApplicationMessage",
    "ApplicationText",
    "ApplicationTextTarget",
    "CompositeTranslator",
    "CatalogRole",
    "FluentTranslatorFactory",
    "FontFamilyState",
    "LanguageResourceLoader",
    "LocalizationBindings",
    "LocalizedPropertyBinding",
    "LocalizationPreferenceStoreProtocol",
    "LocalizedComboItem",
    "LocalizedComboItemTextBinding",
    "LanguageBundleLoader",
    "LanguageSnapshot",
    "PreparedLanguageBundle",
    "QtCatalogBundleLoader",
    "QFluentFontFamilyAdapter",
    "TextFactory",
    "TranslationManager",
    "app_text",
    "apply_application_text",
    "clear_localized_property",
    "render_application_text",
    "set_localized_accessible_description",
    "set_localized_accessible_name",
    "set_localized_combo_item",
    "set_localized_combo_items",
    "set_localized_placeholder",
    "set_localized_text",
    "set_localized_tooltip",
    "set_localized_window_title",
    "translate_application_message",
    "translate_application_text",
    "localized_application_font",
]
