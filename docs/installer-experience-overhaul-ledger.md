# Installer experience overhaul: research and execution ledger

## Purpose

This ledger governs the redesign of the complete SugarSubstitute installer: the
launcher installation, first-run application setup, ComfyUI selection or managed
installation, model discovery and acquisition, integrations, progress, recovery,
and completion. Users experience these as one setup journey, so the product must
present them as one coherent surface even where implementation ownership crosses
process or package boundaries.

The target is a calm, beautiful, accessible wizard that preserves the current
capabilities while asking one understandable question at a time. The first
interaction is language selection. A generous persistent brand bar displays the
SugarSubstitute README wordmark. Mica Alt is the window foundation; a washed
content layer covers most of the window and leaves the top brand bar visibly
Mica Alt.

## Part 1 — Research

Status: complete.

### Source findings

1. Setup should be deliberately lightweight. Microsoft's setup guidance says to
   remove every question, option, page, and path that is not essential; detect
   system state instead of asking the user; keep technical-support details out of
   the normal path; collect decisions before the installation phase; run the
   installation phase unattended; preserve progress across interrupted long
   setups; and use a window sized to its content rather than maximizing it.
   ([Microsoft: Setup](https://learn.microsoft.com/en-us/windows/win32/uxguide/exper-setup))
2. Fluent navigation should be consistent, simple, and clear. Fewer visible
   choices reduce decision cost. Ordered tasks should use a predictable
   hierarchical path with conventional Back behavior rather than presenting a
   dense dashboard of all possible settings.
   ([Microsoft: Navigation design basics](https://learn.microsoft.com/en-us/windows/apps/design/basics/navigation-basics))
3. Windows 11 uses a base layer and a content layer to communicate hierarchy.
   Mica Alt is appropriate when stronger separation is needed between the title
   or commanding area and app content. Microsoft recommends Mica Alt as the base,
   a lightly washed commanding layer, and a further washed content layer.
   ([Microsoft: Mica material](https://learn.microsoft.com/en-us/windows/apps/design/style/mica),
   [Microsoft: Layering and elevation](https://learn.microsoft.com/en-us/windows/apps/design/signature-experiences/layering))
4. Interface writing should be warm, helpful, concise, action-led, and easy to
   scan. Users should not need to read every word, and errors should explain the
   problem and offer a practical recovery action without blame.
   ([Microsoft: Writing style](https://learn.microsoft.com/en-us/windows/apps/design/style/writing-style))
5. Typography should create hierarchy without visual noise: sentence case,
   regular body text, semibold headings, left alignment in normal layouts, and a
   legible Windows type ramp. Body copy should remain short enough that increased
   text scaling does not turn each step into a wall of prose.
   ([Microsoft: Typography in Windows](https://learn.microsoft.com/en-us/windows/apps/design/signature-experiences/typography),
   [Microsoft: Content layout and spacing](https://learn.microsoft.com/en-us/windows/apps/design/basics/content-basics))
6. Determinate progress is preferred whenever work has bounded stages, even if
   timing is approximate. Indeterminate bars fit non-blocking work with unknown
   duration; rings fit a locally blocked interaction. Long setup should show a
   clear current activity and completion state while keeping logs secondary.
   ([Microsoft: Progress controls](https://learn.microsoft.com/en-us/windows/apps/develop/ui/controls/progress-controls),
   [Microsoft: Progress bars](https://learn.microsoft.com/en-us/windows/win32/uxguide/progress-bars))
7. Accessibility is structural: every action needs an accessible name and role,
   keyboard operation, visible focus, predictable reading/tab order, sufficient
   contrast, high-contrast adaptability, and layouts that survive display and
   text scaling. Accessibility must be verified throughout development.
   ([Microsoft: Accessibility overview](https://learn.microsoft.com/en-us/windows/apps/design/accessibility/accessibility-overview),
   [Microsoft: Keyboard interactions](https://learn.microsoft.com/en-us/windows/apps/develop/input/keyboard-interactions),
   [Microsoft: Accessible text requirements](https://learn.microsoft.com/en-us/windows/apps/design/accessibility/accessible-text-requirements))
8. The system's preferred language is the best automatic default, including
   locale fallback, but a product that supports an explicit app language should
   make that choice discoverable and immediately preview the selected language.
   ([Microsoft: Identifying user preferences](https://learn.microsoft.com/en-us/globalization/locale/user-preferences))

### Applied design principles

- Treat installation and ComfyUI setup as one continuous journey.
- Start with language and apply it immediately across both process-owned surfaces.
- Ask one consequential question per step. Reveal dependent controls on the next
  step, not inside the choice that triggers them.
- Prefer automatic detection and a recommended path. Keep advanced or technical
  details available without making them part of the default reading path.
- Use short headlines, one short supporting sentence, recognizable controls, and
  direct button labels. Remove instructional prose that merely explains widgets.
- Keep Back and the primary action in stable positions. Make the primary action
  describe the next meaningful outcome where practical.
- Start safe background preparation once enough information is known. Never make
  users stare at console output to understand whether setup is alive.
- Use one overall progress model plus a concise current-stage label. Use real byte
  progress for downloads and landmark-weighted progress for environment setup.
- Keep logs collapsed by default. Open the dedicated error experience with a
  copyable report when work fails.
- Use imagery as content, not decoration: the persistent wordmark establishes
  product identity; real CivitAI portraits help users choose models.
- Preserve user choices when moving backward or recovering an interrupted setup.
- Make the no-pointer path complete and make visible focus order match reading
  order in every supported locale.

### Visual system decision

- Foundation: native Mica Alt where supported, with the existing cross-platform
  fallback policy elsewhere.
- Persistent brand bar: generous top region showing the README wordmark and native
  window controls; this is the only large region that exposes full dark Mica Alt.
- Content: one contiguous low-opacity wash over Mica Alt, matching the MainWindow
  hierarchy rather than floating the whole wizard directly on the material.
- Cards: reserve card elevation for meaningful choices, summaries, and errors.
  Do not put ordinary labels or single binary questions inside oversized panels.
- Rhythm: a constrained readable content column, generous whitespace, and a
  stable footer. Density grows only for inherently visual content such as model
  recommendations.

## Part 2 — Current-experience audit

Status: complete. The baseline was rendered through the production launcher and
production onboarding windows with the deterministic full-journey qualification
harness. Evidence is under
`build/qualification/installer-overhaul-baseline/`.

### Journey-level findings

1. **The first interaction is an installation path, not language.** The launcher
   resolves the operating-system or command-line locale before constructing the
   window and has an explicit regression test requiring that no language selector
   exist. This makes the supported language choice undiscoverable at the moment
   it matters most.
2. **The journey looks and reads like two products.** The launcher and installed
   app use separate shell implementations, separate geometry/effect owners, and
   duplicated rail/hero/card styling. The process handoff retains geometry, but
   identity, hierarchy, and page composition visibly reset.
3. **Mica is exposed as an undifferentiated background.** Both baseline windows
   place almost everything directly on one dark material. There is no persistent
   brand bar and no MainWindow-like content wash, so the backdrop supplies mood
   but not hierarchy.
4. **The fixed 1260 × 800 canvas is poorly composed.** Most steps occupy a small
   island near the top while an always-visible 280-pixel rail consumes horizontal
   space. The result is simultaneously sparse and dense: too much empty window,
   too little room for the actual task.
5. **The rail duplicates rather than aids orientation.** Each page shows a step
   count, current title, helper sentence, four numbered items, a hero eyebrow,
   another title, and another description. Users must scan the same information
   in several typographic forms before reaching the control.
6. **Copy explains the interface instead of moving the user forward.** Repeated
   phrases about later changes, default choices, what happens next, and setup
   mechanics turn simple decisions into prose-heavy forms.
7. **The default route exposes expert configuration.** The managed-ComfyUI page
   shows host, port, backend/platform/Python diagnostics, channel choices, CPU
   overrides, and explanatory panels at once. Most of these are derivable or
   advanced and should not compete with the one meaningful folder choice.
8. **Choice pages lack a strong scan path.** Three ComfyUI modes are verbose
   radio-card columns with a second explanatory panel. Binary questions use
   large button rows but still inherit all the surrounding rail and hero copy.
9. **Model recommendations are the strongest existing surface but are visually
   disconnected from the rest of setup.** Real-image cards already support
   portrait presentation, exact-version thumbnails, loading activity, direct
   selection, per-family skip, and “I’ll find my own models.” They need the new
   shell, clearer family context, and less surrounding chrome—not a new workflow.
10. **Review and completion contain useful information with weak prioritization.**
    The download review is grouped and legible, but filenames and implementation
    roles receive almost equal weight to the chosen models. Completion repeats
    “ready” several times and surfaces an “advanced details” block even when it
    adds no actionable information.
11. **Progress behavior is substantially correct but visually secondary.** The
    provisioner already reports landmarks, model downloads report bytes, logs
    are collapsed, errors use the dedicated report experience, and taskbar/window
    attention is requested. The page needs one dominant current state, a clear
    overall trajectory, and stable layout when log content is expanded.
12. **The qualification harness is broad enough to protect the overhaul.** It
    renders launcher installation, managed/attached/remote ComfyUI routes,
    existing-model detection outcomes, CivitAI success/failure, download retry,
    provisioning, and completion without mutating the real machine. Its current
    synthetic model cards intentionally replace network content, so a separate
    live-CivitAI visual capture is required for recommendation-card judgment.

### Baseline visual evidence

- `install.png`: no language entry point or wordmark; tiny task content inside a
  very large undifferentiated window.
- `comfy-setup/managed-sdxl-and-anima/target-mode.png`: repeated headings and a
  prose-heavy three-column decision plus redundant explanation panel.
- `comfy-setup/managed-sdxl-and-anima/configuration.png`: expert diagnostics and
  advanced switches dominate the recommended route.
- `comfy-setup/managed-sdxl-and-anima/recommendations-sdxl.png`: correct card
  concept, but the left rail shrinks the gallery and the synthetic baseline cannot
  establish final real-image quality.
- `comfy-setup/managed-sdxl-and-anima/model-download-review.png`: useful grouping,
  but excessive chrome and technical filenames dilute the confirmation decision.
- `comfy-setup/managed-sdxl-and-anima/provisioning.png`: appropriate progressive
  disclosure, but competing shell text and low-emphasis progress weaken focus.
- `comfy-setup/managed-sdxl-and-anima/completion.png`: repeated completion copy
  and non-actionable advanced detail prevent a crisp finish.

## Part 3 — Implementation ledger

Status: implemented and qualified on Windows 11. The corrective goal below is
complete and the installer is ready for maintainer smoke.

### Current corrective goal

- Preserve the working native Mica Alt composition and make the complete brand
  bar draggable while leaving its controls interactive and startup centered and
  on-screen.
- Give the shared page stage one authoritative centering and height model. Every
  fitting page must center horizontally and vertically; disclosures, Back and
  Forward navigation, logs, and async content must not leave stale geometry,
  meaningless scrollbars, clipping, or disabled dead ends.
- Keep the existing-model question as a direct footer decision. Preserve the
  computed default model-folder path, use neutral “models folder” terminology,
  and keep future WebUI support to a simple ComfyUI-shaped linked directory.
- Redesign managed Advanced settings as one coherent, bounded dialog with
  detected facts separated from understandable editable choices. Do not nest
  another Advanced section or reflow the installer page when it opens.
- Preserve every original Danbooru and CivitAI capability as an ordinary,
  directly visible first-class choice: Danbooru tag help and image-rating policy;
  CivitAI model help, download offers, thumbnail content policy including all
  SFW/NSFW choices, and optional API key. These controls are not Advanced and
  must not be hidden behind “options” buttons or compressed away.
- Download only the exact primary models the user selected. SimpleSyrup owns
  Anima text-encoder and image-decoder dependencies.
- Keep three stable, exact-version CivitAI recommendations per missing family
  with high-resolution centered portrait crops, title wash, immediate loading
  activity, and no author/version subtext. Returning to a page must not change
  the chosen model version or thumbnail.
- Present selected models as an editable checkout with centered image cards,
  family and size, removal, count, total, free space, destination, and one clear
  confirmation action.
- Open setup logs in a bounded dedicated live/copyable surface that cannot
  reflow the progress page. Successful completion is terminal and cannot return
  to a stale Working state.
- Prove every correction with focused behavior and geometry regressions, the
  deterministic full journey, live exact-version CivitAI evidence, fully rendered
  Windows screenshots at real dimensions and scaling, and every repository gate.
  Do not claim completion before personally inspecting the rendered result.

### Earlier overhaul milestones

The work is ordered so every slice leaves the qualification path usable.

- [x] **1. Safeguard the complete journey.** Update characterization tests to
  assert one install-root prompt, a language-first clean-install route, preserved
  state through the launcher/app handoff, conventional Back behavior, all current
  setup routes, and unchanged error/progress capabilities.
- [x] **2. Establish one shared visual contract.** Add a shared setup-surface
  owner for dimensions, top brand bar, README SVG wordmark, washed content layer,
  compact progress treatment, stable footer, focus/accessibility conventions,
  and cross-platform fallback styling. Package the wordmark in both executables.
- [x] **3. Make language the first clean-install page.** Populate choices only
  from `languages.json`, preselect the resolved system preference, apply selection
  immediately, persist it in the selected installation root once known, and hand
  it into the installed app. Repair and already-installed launch routes retain
  their existing locale without inserting onboarding.
- [x] **4. Recompose the launcher.** Replace the permanent rail with the shared
  brand bar, compact progress, washed task surface, restrained readable column,
  and stable footer. Keep install-location selection, repair scope, live progress,
  retry, and diagnostic output capabilities while reducing normal-path copy.
- [x] **5. Make the launcher-to-app handoff continuous.** Preserve geometry,
  language, material, header, progress position, and visual rhythm so the process
  boundary reads as one wizard rather than a second setup application.
- [x] **6. Recompose the ComfyUI setup shell.** Adopt Mica Alt, the shared brand
  bar and content wash, compact journey progress, wider task area, stable
  navigation, and scroll-safe/text-scale-safe content without changing routing.
- [x] **7. Simplify each decision page.** Keep one headline, at most one short
  supporting sentence, and only the controls needed for that decision. Reduce the
  ComfyUI target cards to scannable outcomes and remove duplicated summaries.
- [x] **8. Move expert controls to a focused surface.** On managed setup show the
  ComfyUI location and recommended automatic configuration. Put host, port,
  detected runtime details, channels, CPU mode, and experimental backend controls
  in one bounded Advanced dialog. Apply equivalent restraint to attached and
  remote routes without removing their required inputs.
- [x] **9. Refine model selection in the shared surface.** Keep automatic SDXL
  compatibility detection; suggest three popular Illustrious choices only when no
  SDXL-compatible model exists; suggest Anima only when missing; retain family
  skip and “I’ll find my own models”; show high-resolution exact-version portrait
  thumbnails with loading activity and title wash; verify with live CivitAI data.
- [x] **10. Simplify review, progress, recovery, and completion.** Prioritize user
  choices and total size over filenames, make overall/current progress dominant,
  keep logs opt-in, preserve byte progress and attention requests, retain the
  copyable dedicated error modal, and end with one clear completion statement and
  action.
- [x] **11. Complete localization and accessibility.** Route every new visible
  string through its owner, update every release catalog atomically, verify native
  language names, accessible names/descriptions, labels, tab order, keyboard
  activation, focus visibility, contrast, high contrast, and pseudo-locale fit.
- [x] **12. Render, judge, and qualify.** Run focused tests continuously; render
  the complete deterministic journey; run a live-CivitAI recommendation capture;
  inspect representative pages at normal and pseudo-locale text; refine until the
  visuals are coherent and professional; then run architecture, governance,
  localization, format, lint, strict typing, parallel, isolated, and serial gates.

### Final qualification evidence

- The shared 1180 × 760 Mica Alt surface, persistent README SVG wordmark bar,
  washed content layer, compact five-stage progress, scroll-safe task area, and
  stable footer now span the launcher and application-owned ComfyUI setup.
- Clean install begins with the manifest-owned, visibly centered language
  selector. Selection retranslates immediately, persists with the chosen
  installation, and is handed across the process boundary. All four release
  catalogs compile with zero unfinished messages: 1,662 application strings and
  122 launcher strings per locale.
- Default managed setup keeps host, port, runtime diagnosis, channel, CPU, and
  experimental controls in a bounded Advanced dialog. Opening it leaves the
  centered page, stage height, scrollbar state, and footer geometry unchanged.
  Repair, attached, and remote routes retain their required controls and recovery
  behavior.
- Danbooru tag help and image-rating policy, plus CivitAI model help, download
  offers, complete thumbnail-content policy, and optional API key remain directly
  visible as first-class controls. None is classified or hidden as Advanced.
- Model onboarding detects SDXL compatibility and Anima presence, recommends only
  missing families, presents three exact-version portrait cards, keeps per-family
  skip and find-own exits, and reveals real names immediately while 1024-pixel
  CivitAI images load behind per-card activity indicators.
- Deterministic visual evidence for every route and recovery state is in
  `build/qualification/installer-remediation-dialog-v3/`. Its side-effect audit is
  zero for network, downloads, installs, subprocesses, handoffs, configuration
  writes, and target mutations, and protected-file hashes remain unchanged.
- Live read-only CivitAI evidence is in
  `build/qualification/installer-live-final/live-civitai/`. It proves
  loading, settled Illustrious/SDXL-compatible, and settled Anima presentation
  with three current real models per family and 1024-pixel source images. Shared
  model pages use distinct exact-version IDs and thumbnail URLs between families;
  returning to a recommendation page preserves the exact model, version, image,
  URL, cache key, and downloaded thumbnail payload.
- The exact checkout presents centered portrait cards for each selected primary
  model with family, size, removal, count, total, free space, and destination.
  SimpleSyrup remains the owner of Anima text-encoder and image-decoder support.
- Setup logs open in a dedicated 860 × 520 live, copyable dialog without changing
  page geometry. Closing the launcher localization runtime restores its complete
  application presentation state before releasing locale font resources, so the
  log dialog remains readable in the full handoff smoke. Completion is terminal:
  Back is absent and revisiting cannot restore a disabled “Working...” action.
- Native Windows evidence is in `build/qualification/installer-goal-native/`.
  The verifier observes DWM backdrop type 4 (Mica Alt) on both process-owned
  windows, a transparent native-material header, an independently washed body,
  centered launcher placement, stable Advanced-page stage/footer geometry, and
  three portrait loading cards. The maintainer also visually confirmed the
  material composition in the running launcher.
- Native localized and display-scaled evidence is in
  `build/qualification/installer-overhaul-es/`; the Spanish configuration and
  integration pages remain readable, correctly localized, and scroll-safe.
- The implementation passes formatting, lint, strict typing, architecture
  governance, test governance, localization policy, the full parallel suite, all
  90 isolated modules, the serial module, deterministic installer qualification,
  live-CivitAI qualification, and `git diff --check`. Verification was performed
  on Windows 11; Linux and macOS remain CI responsibilities.

### Acceptance criteria

- A clean installation opens on language selection before any path or technical
  choice; changing language immediately updates the page and persists across the
  launcher/app handoff.
- Every screen visibly belongs to one installer: identical wordmark bar, Mica Alt
  foundation, washed body, progress treatment, margins, content width, and footer.
- The ordinary managed-ComfyUI route never presents expert runtime configuration
  unless Advanced is opened.
- No page explains a visible control with avoidable prose or presents more than
  one primary decision.
- All pre-overhaul capabilities and routes remain available and covered.
- Deterministic screenshots and a live-CivitAI gallery have been inspected, not
  merely generated; no clipping, placeholder leakage, broken hierarchy, or stale
  state remains.
- All applicable gates pass for the exact worktree delivered for maintainer smoke.

Completion requires every ledger item to be implemented and verified, the full
installer qualification journey to pass without real machine mutation, and the
maintainer-facing smoke to be the final review rather than the first visual check.
