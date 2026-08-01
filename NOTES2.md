# CuteCanvas Migration Worktree Review

## Review status

This document is the remediation record for the committed migration.
Findings are rewritten as their authoritative owners and proofs change. The
review was reopened because detail inspection was incorrectly linked across
scenes and batches, comparison navigation was not source-aware, and users
still observed corrupted comparison tiles despite the prior green suite.

Current status:

- The user's saved workflow is a clean relaunch control. Corruption begins
  during live comparison panning after zoom; reopening the cached session does
  not itself produce a corrupt frame.
- The accepted reproduction mounts an unmistakable two-source comparison with
  960×1344 and 1144×1608 sources, zooms through the real top-level wheel path,
  and repeatedly traverses most of the available pan range in both directions.
  Before the correction, the retained frame differed from a same-state full
  redraw in 889,119 pixels, with maximum channel error 251. The captured frame
  contained the same rectangular stale-source regions reported by the user.
- The pan harness had been invalid. Its full-redraw oracle ran inside the
  abused renderer and restored the result through `WidgetRenderSurface`, which
  linearized circular storage and reset the storage origin at every checkpoint.
  Verification therefore repaired the accumulated state it claimed to test.
  The headless harness now owns an independent reference QPane. The accepted
  native Windows reproduction remains available as an explicit diagnostic, but
  it is not part of ordinary test execution: the test requires
  `QPANE_RUN_NATIVE_DESKTOP_TESTS=1`, and the command also requires
  `--allow-desktop-window`. This prevents probes from foregrounding windows
  during normal development or complete gates.
- QPane retains fast scroll reuse. Plans with visible layer clips now use a
  native linear pixmap scroll before exposed-strip repair, preserving one
  global clip phase for the comparison seam. Ordinary unclipped single-image
  plans retain circular scroll storage. The default offscreen regression
  requires clipped comparison storage to remain at the global origin and
  retained pixels to match a same-state full redraw. Fault-injecting the former
  circular policy makes that test fail at `QPoint(216, 0)`; the production
  policy passes.
- Earlier P0 repairs remain present: exact `(workflow, scene, batch)` inspection
  groups, source-aware comparison FIT/1:1 behavior, transient scene-relative
  comparison clipping, seam-aligned divider interaction, atomic pair changes,
  safe source replacement/removal, live Cube-output target remounting, and
  projection replay that cannot recurse through user intent.
- Inpaint failure had two independent regressions. CuteCanvas migration left
  mask-click presentation reading obsolete binding attributes, so an existing
  blank mask could not select its owning image/mask or activate the brush.
  Separately, SugarSubstitute still queued absolute paths through core
  `LoadImage` nodes after Comfy security commit `96e0e3585` stopped accepting
  prompt paths outside its input directory. The local path behavior had worked
  only because the former Windows path join escaped that directory.
- Local inpaint execution now retains the original no-copy contract. The
  loopback-only Substitute BackEnd authorization route binds an exact existing
  file to an opaque, expiring, class-specific token; execution-only loader
  nodes resolve that token. SugarSubstitute rewrites only its deep-copied queue
  payload, while the cube, workflow buffer, recipe, project mask, and selected
  image remain standard core-node data. Remote targets retain their existing
  native Comfy upload contract.
- A hidden real-Comfy harness uses an external C-volume image, an over-260-
  character E-volume project-mask path, hostile punctuation, non-square
  dimensions, boundary pixels, and both loader branches. Current Comfy accepts
  and executes the staged prompt at 23×17 on both branches, exact boundary
  pixels survive, the authored payload is unchanged, and Comfy input gains
  zero files. The harness uses `CREATE_NO_WINDOW`, never opens a browser, kills
  its exact process tree, and leaves no temporary process or directory behind.
- Comparison chrome now derives each side's scene, batch, and source directly
  from the same comparison selection that resolves that side's rendered
  composition. A restored Text to Image versus Diffusion Upscale comparison
  can no longer render the correct pair while labeling both sides Diffusion
  Upscale. Cross-scene and cross-batch comparisons have the same invariant.
- The committed QPane/CuteCanvas source state passes its complete mandated
  static, structural, and offscreen behavioral gates: `1440 passed, 1 skipped`
  in 159.73 seconds. The one skip is the explicit desktop diagnostic; the
  deterministic clipped-storage comparison regression remains in the default
  suite. SugarSubstitute's current comparison/grid blast area passes `7`
  focused document/tile cases, and the broader offscreen Output blast area
  passes `38` tests across zoom indicators, real-shell tab/linking scenarios,
  the abuse matrix, comparison navigation, and stable grids. Targeted Ruff and
  strict mypy also pass. SugarSubstitute's current 3,444-file format/lint gate,
  strict mypy over 3,146 sources, and complete offscreen parallel suite pass.
  The 123-module serial partition was stopped after the maintainer requested
  that release gating be deferred; it remains the only incomplete commit gate.

The three canvas-migration code surfaces are:

1. SugarSubstitute at `E:\devprojects\SugarSubstitute`, compared with
   `0b3dae9fbf5b5d3bf6093b3a67ee1407ab816ca1` (`HEAD`, release 0.19.0).
2. CuteCanvas under `E:\devprojects\QPane\packages\cutecanvas`, compared with
   QPane-monorepo `HEAD`
   `acc096929ac138d8670b2f7229a850929d9dd022`.
3. QPane under `E:\devprojects\QPane\packages\qpane`, compared with the same
   QPane-monorepo `HEAD`.

CuteCanvas and QPane share one Git worktree today, but they are treated here as
independently published packages with the required dependency direction
`SugarSubstitute -> CuteCanvas -> QPane`.

The inpaint compatibility remediation additionally touches the installed,
versioned Substitute BackEnd liaison at
`E:\ComfyUI\custom_nodes\Substitute-BackEnd`. Those changes are committed
locally and remain unreleased; no BackEnd tag or push was made. SugarCubes and the
inpaint cube remain unchanged.

## Required behavior and ownership

The migration must preserve or improve the SugarSubstitute `HEAD` experience
while transferring generic canvas concerns out of SugarSubstitute:

- Detail images in one Output group share normalized inspection. Moving one
  image and first opening another must expose the corresponding region.
- Detail and comparison zoom indicators retain their former gesture timing,
  placement, formatting, and physical source-scale meaning.
- Reveal comparison uses one responsive native renderer, presents one coherent
  pair, gives both sources the same comparison frame, and changes the divider
  without stale or corrupted tiles.
- Scene and Batch grids preserve ordering, aspect treatment, stable tile
  placement, and equal stable gutters during viewport resize.
- SugarSubstitute imports CuteCanvas as its canvas API. CuteCanvas may use
  QPane's public facade and SDK; SugarSubstitute does not import QPane, and
  neither upstream package contains SugarSubstitute product policy.
- Input and Output each own one long-lived document. Document admission,
  presentation, inspection, editing, and physical execution have distinct
  owners.

The completed direction is coherent: SugarSubstitute now has
long-lived Input and Output documents, output content is admitted as locked
compositions, presentation roles have separate inspection stores, and the
production canvas boundary has no direct QPane import. The findings below
record the lifecycle, geometry, rendering, scheduling, and proof corrections
that completed that direction without restoring the deleted SugarSubstitute
QPane adapter stack.

## Findings

### P0 — Resolved: Cube-output tabs remount live targets

The failure was reproduced against the user's restored `workflow_25871`, not
inferred from synthetic state. Entering `scene 1` produced the three-image
Diffusion Upscale grid. A physical click on Text to Image correctly changed
the route and rendered its three targets; after Qt destroyed the departed grid
surface, clicking Diffusion Upscale changed the tab state but projection raised
`RuntimeError: Internal C++ object (CuteCanvas) already deleted` in
`CanvasTargetPool.mount()`. The visible document therefore remained on the
wrong output.

`CanvasTargetPool` retained inactive canvases in its dictionaries but left
their lightweight mounts parented to the departed presentation surface.
Qt's deferred surface deletion consequently destroyed the canvases that the
pool still claimed to own. This only remained green when tests switched back
before deferred deletion ran or asserted route/session identity without
grabbing the mounted renderer.

CuteCanvas now parks every retained inactive mount under the stable
`CanvasWorkspace` parent before the old surface is deleted. Custom-provider
canvases are first returned to their retained mount; over-budget inactive
targets are still retired through the existing bounded LRU owner. No
SugarSubstitute policy or QPane import participates in the correction.

The upstream red regression switches between disjoint three-target grids,
forces `DeferredDelete`, switches back, and requires the identical live
canvases. A retention-pressure storm cycles three disjoint grids fifteen times
with capacity one and proves every current canvas remains visible while the
live renderer count stays bounded. The formerly shallow hidden-grid reuse
test now forces deferred destruction as well.

The SugarSubstitute real-shell regression physically selects the output source,
allows the old surface to be destroyed, physically returns, checks the durable
route, and grabs both mounted targets for their exact payload colors. Its
failure against the old target-pool code reproduces the same deleted-canvas
trace as production. The complete real-shell matrix also uses physical
workflow tabs, physical source tabs or the compact picker as rendered,
physical canvas targets, live previews, first-open sources, batch fallbacks,
scene overviews, clear/repopulate flows, resize, and repeated workflow
association restoration. The focused `MountedWidgetInput` owner performs the
topmost-widget hit test for every physical fixture action; the harness
orchestrates Output scenarios without owning raw Qt mouse delivery.

### P0 — Resolved: comparison projection cannot recurse through user intent

The production traceback formed a synchronous cycle:
`on_output_compare_changed -> project_workflow -> bind_projection_session ->
present_comparison -> presentationChanged -> activeOutputCompareChanged`.
`OutputCanvas._present_projection()` emitted the same signal used for physical
divider and orientation changes while it was merely replaying persisted route
state. The shell correctly treats that signal as user intent, persists it, and
projects the resulting session, so one presentation replay immediately started
another.

Two upstream setup transitions amplified the loop. `NativeCanvasComparison`
selected the pair before applying the requested divider, causing QPane to
publish its default 0.5 split before the requested split. `CanvasWorkspace`
also released and captured the active native comparison whenever identical
inspection groups were assigned again. Neither transition represented a host
or user mutation.

SugarSubstitute now emits comparison changes only from
`OutputDocumentNavigation`, the owner of physical comparison interaction;
binding a persisted projection only presents it. CuteCanvas applies the
requested split while comparison is inactive and then selects the pair, so the
first visible native state is already authoritative. Reassigning the exact
comparison inspection groups returns without capturing or mutating the live
surface.

The SugarSubstitute regression binds an initial persisted comparison and
requires zero user-intent emissions. It then connects the real compare signal
to a callback that immediately rebuilds and rebinds the production projection,
mirroring the shell cycle from the traceback. A native divider drag and an
orientation change each emit exactly once, rebind successfully, and do not
recurse. Upstream regressions separately require zero inspection capture for
an identical group and exactly one requested presentation state for initial
comparison setup.

### P0 — Resolved: detail inspection follows exact Output scope

The migrated binding flattened every final image from every source, scene, and
batch in the active workflow into one inspection group. This made scene 1
batch 2 and scene 2 batch 1 inherit navigation from scene 1 batch 1, even
though only corresponding Cube outputs for the exact same
`(workflow, scene, batch)` are peers.

The focused application owner `output_detail_inspection_groups()` now derives
stable groups from workflow identity, scene identity, and set index. It
prioritizes explicit scene groups, handles unscened projections, de-duplicates
source identities, and emits only meaningful multi-source groups.
`OutputCanvasSession` carries those definitions, while the focused
`OutputInspectionGroupRegistry` adapts application image IDs to live
composition IDs and retains inactive workflow groups without keeping widget
state. Replacement and retirement republish only currently valid members.

The comparison role retains its independent CuteCanvas inspection session, so
narrowing detail groups does not restrict explicit comparison. CuteCanvas and
QPane remain unaware of scenes, batches, Cubes, or SugarSubstitute workflow
policy.

The mounted real-shell regression seeds three scenes, two batches, and Text to
Image plus Diffusion Upscale output. It failed with one twelve-member group and
now requires the exact six two-member groups. Session and document tests also
prove inactive workflow retention and replacement reconciliation.

### P0 — Resolved: linked detail activation preserves shared inspection

CuteCanvas now resolves first-open viewport intent through the focused
`viewport_activation` owner. Persisted session inspection always outranks a
default fit request, while a target with no inspection still receives the
requested initial fit. Composition removal permission no longer participates
in viewport geometry.

`SessionInspectionBinding` also owns a nest-safe publication suspension.
Composition activation, content-size synchronization, renderer alignment, and
widget resize now restore final inspection before any viewport change can be
published. This closes both the original post-activation FIT overwrite and the
later centered-custom overwrite exposed by real mount resizing.

Mounted regressions begin from zoomed, non-centered inspection and first-open
an unseen linked target at equal sizes and mismatched 640×480/1200×700 sizes.
They assert the exact normalized center, span, and CUSTOM mode through a
single/tabbed/remounted presentation sequence. A protected
`removable=False` composition separately proves that structural permission no
longer blocks content-size and FIT initialization. All four viewport-policy
input combinations have direct unit coverage.

### P0 — Resolved: comparison chrome identifies the rendered pair

A production comparison rendered scene 1 batch 1 Text to Image on the left and
scene 1 batch 1 Diffusion Upscale on the right while both navigation bars said
Diffusion Upscale. The comparison target IDs and pixels were correct. The
right bar described `OutputCompareState.comparison`, but the left bar reused
the ordinary active Output route instead of describing
`OutputCompareState.base`. Persisted comparison restoration can legitimately
leave that hidden ordinary route on another source, so rendering and chrome
had different authorities.

The compare-navigation chrome owner now synchronizes both bars from the two
visible comparison selections. Scene, batch, and source labels, selector
visibility, batch counts, and measured bar widths all derive from the
selection rendered on that side. The hidden ordinary route remains separate;
restoring comparison state does not need to mutate workflow navigation merely
to make its labels truthful.

The real-shell regression first preserves the exact reported mismatch:
ordinary navigation remains on Diffusion Upscale while the restored base is
Text to Image. It requires the document's two resolved image IDs, sampled
left/right pixels from the live comparison surface, and all six bar labels to
agree. The same fixture then changes to scene 1 batch 2 Text to Image versus
scene 2 batch 1 Diffusion Upscale, where scene, batch, source, image ID, and
color differ between sides. The pure chrome fixture independently requires
both side selections and explicit side-specific batch counts. All rendering
remains behind CuteCanvas; this correction adds no QPane dependency or
SugarSubstitute policy upstream.

### P0 — Resolved: normalized comparison navigation is source-aware and bounded

QPane now projects comparison content through the focused,
source-neutral `ComparisonSceneProjector`. The primary source owns the scene
frame; the secondary source receives an explicit affine transform onto the
same frame. This replaces the former maximum-canvas/identity-placement
behavior, so differently sized and differently shaped sources compare
corresponding normalized regions.

Mounted regression coverage uses 640×480 and 1600×900 sources and asserts one
640×480 scene frame, equal rendered placements, and distinct truthful
per-source transforms. A patterned 160×120/400×180 fixture samples all four
normalized quadrants through vertical and horizontal divider extremes,
repeated three times, to detect stale, corrupt, or misregistered pixels.

The correction remains entirely in QPane. CuteCanvas consumes the public
comparison facade and SugarSubstitute does not resize payloads or inject
renderer geometry.

That normalized projection also means source-native zoom is not globally
`1.0`. A 4096×3072 source projected onto a 2048×1536 comparison frame requires
viewport zoom `2.0` for source pixels to reach 1:1 physical scale, while the
2048×1536 source requires `1.0`.

QPane now delegates native zoom to the focused `SceneNativeZoomResolver`. It
hit-tests the topmost visible clipped render item under the pointer and derives
its native zoom from the authoritative source-to-scene transform. Double-click
and wheel snap carry the gesture anchor through the navigation port; ordinary
single-image scenes retain the viewport's normal native scale fallback.

Source-native 1:1 also preserves the source coordinate under the clicked point.
`Viewport` accepts the resolved native target and keeps bounded anchored pan in
1:1 mode even when a projected comparison frame fits on one axis. FIT continues
to normalize both sources onto the same comparison frame, while 1:1 truthfully
differs by source resolution.

The mounted red regression double-clicks both sides through QTest. It failed
because both sides reached `1.0`; it now proves primary `1.0`, secondary `2.0`,
FIT toggling, and source-coordinate anchoring.

Custom comparison zoom also had no effective upper bound. Forty mounted wheel
steps reached viewport zoom `20061.77` in the smaller-primary case and
`10030.89` in the inverse case. QPane's viewport contained a nominal `10×`
limit, but wheel and public custom-zoom paths bypassed it.

The viewport now owns upper-bound enforcement while the source-relative scene
navigation owner derives the comparison ceiling from both immutable layer
transforms. The ceiling is `10 × max(primary native zoom, secondary native
zoom)`: the side that reaches 1000% last stops at exactly 1000%, while the
other side may truthfully exceed 1000%. A 320×240/640×480 pair therefore stops
at viewport zoom `20`; the inverse stops at `10`. A non-uniform
320×240/800×300 pair stops at `12.5`, preserving the existing max-axis
source-native definition. Replacing a source with one that lowers the ceiling
immediately reconciles the preserved custom view around its center.

The bound is derived from the cheap immutable comparison scene rather than a
compiled render plan, so scene switching retains its interaction budget.
Wheel/API upper clamping remains separate from touch navigation's minimum-size
clamp; zooming out below `1×` continues to work. Regressions cover forty-step
wheel abuse, oversized smooth-wheel bursts, equal, inverse, heterogeneous
shape/resolution pairs, live source replacement, ordinary zoom-out, the
CuteCanvas comparison surface, and SugarSubstitute's Output document.

### P0 — Resolved: tiled comparison navigation preserves one clip phase

The first patterned comparison test exercised only 160×120/400×180 images at
FIT and sampled four quadrant centers. QPane selected `RenderStrategy.DIRECT`
when the projected canvas fit the viewport, so that test never requested,
received, or composited a tile. The later forced-tile tests corrected that
coverage gap but still did not preserve hostile live-pan state.

The mounted CuteCanvas red fixture uses normalized 29×23 patterns with
source-specific palettes at 2048×1536 through 4096×3072. It applies custom
zoom and pan so both layers report `RenderStrategy.TILE`, changes the divider,
switches pairs, alternates divider orientation, resizes the real workspace, and
samples dozens of pattern interiors from the transforms in the active render
plan. The observed mismatch was an exact color from the other source, not an
edge interpolation difference, and remained after the five-second settle
window.

Two clip owners caused that stale frame. `ComparisonSceneProjector` baked the
initial clip into durable scene content while later divider changes wrote a
transient clip, allowing scene replacement and live presentation to disagree.
QPane now keeps durable comparison geometry clip-free and reapplies the current
transient clip after every accepted scene. Comparison splits remain
`NORMALIZED_SCENE`, matching the QPane-only user contract: the seam belongs to
the compared image frame and transforms with it.

The permanent upstream abuse runs 24 pair changes with divider extremes and
partial splits, alternating orientation, custom pan/zoom, and workspace
resize. Every settled frame must remain tiled and all dense pattern interiors
must match the active source. SugarSubstitute adds its own public
`OutputCanvasDocument` fixture with three heterogeneous patterned outputs and
12 production pair/navigation/resize transitions; it observes strategy values
and pixels through the CuteCanvas-owned native surface without importing
QPane.

The original tile oracles incorrectly located the expected seam by multiplying
the split against the viewport. That assumption hid the later viewport-relative
regression. Both permanent oracles now independently project the normalized
scene boundary through the active render item before deciding which source must
own each dense pixel sample. They therefore reject stale/cross-source tiles and
any disagreement between rendered clipping and transformed seam geometry.

That proof still missed the production panning failure. The shared
`HeadlessPanHarness` captured a clean oracle by fully redrawing the same
renderer and then restoring its saved image. `WidgetRenderSurface.restore()`
publishes a linear image and resets the wrapped storage origin, so every
checkpoint silently repaired the circular scroll state before the next pan.
The green result could not say anything about accumulated wrapped comparison
repairs.

The replacement oracle is a second independent QPane. The abused renderer is
never redrawn, restored, or normalized by verification. The accepted native
Windows diagnostic mounts deliberately distinguishable normal/inverted
sources at the reported 960×1344 and 1144×1608 geometry, uses the production
top-level wheel path, performs nine released long drags with twelve
intermediate samples each, and captures actual window pixels under sustained
event-loop pressure. The first broken implementation finished with 889,119
pixels different from a same-state full redraw and maximum RGB channel error
251. Because it foregrounds a real window, this diagnostic is now doubly
opt-in and is excluded from ordinary gates.

The defect was confined to wrapped scroll storage for clipped scene plans.
Repeated exposed-strip repairs could lose the comparison clip's global phase
and publish rectangular regions from obsolete source ownership. The focused
`navigation_reuse_policy` owner now selects linear native pixmap scrolling for
plans containing a visible layer clip. Strip repair and scroll reuse remain
active, but the seam has one materialized coordinate phase. Unclipped plans
continue to use circular storage, preserving the ordinary single-image fast
path. The default offscreen renderer regression exercises a public clipped
two-source scene, requires a scroll hit, requires a null storage origin, and
compares retained pixels with a forced redraw. Fault injection that restores
the former circular choice fails deterministically at the storage-origin
assertion, so the normal suite now catches the owning failure without opening
a desktop window.

Document mutation is covered separately. `ComparisonCatalogSynchronizer`
refreshes only admitted compositions that reference the changed resource, uses
monotonic source revisions, and preserves the active viewport. Removing an
active secondary now makes QPane immediately project the surviving primary
before CuteCanvas reconciles the workspace presentation. Mounted replacement
and deletion regressions prove exact pixels, preserved pan/zoom, comparison
cleanup, and safe transition to the surviving composition.

### P0 — Resolved: divider movement is transient presentation

QPane now owns live layer clips in `LayerClipPresentationRegistry`, separately
from durable `RenderScene` content. The presenter applies an active clip to
both the render item and its descriptor, preserving painting, hit testing,
divider geometry, and diagnostics without recompiling or replacing the scene.
Scene acceptance reconciles stale overrides so repeated pair changes cannot
retain old targets.

A mounted 4096×4096/3072×2048 regression alternates orientation and drives 102
clamped split positions. It observes zero `sceneChanged` emissions, retains
the identical scene object, and verifies the final render-plan clip. The
patterned settled-frame test then revisits both extremes and both orientations
to prove that rapid transient changes do not expose stale tiles.

### P0 — Resolved: the divider is inseparable from the comparison seam

The migrated implementation changed QPane comparison clips from
`NORMALIZED_SCENE` to `NORMALIZED_VIEWPORT`. The host-painted divider was
therefore fixed to the widget while the comparison image retained an
independently transformed scene. This broke the QPane-only behavior at `HEAD`
and allowed the visible comparison seam and divider artwork to drift during
pan and zoom.

QPane again expresses the transient reveal in normalized scene coordinates.
`ProjectedClipBoundary` projects that exact clip through the active comparison
render item for drawing, hit testing, and pointer-to-split conversion. A mounted
red regression measured the broken divider at viewport x `297.6` while the
transformed scene seam was x `-83.96`. It now requires exact projected
agreement before and after distinct zoom/pan states, and the SugarSubstitute
fixture verifies that its two-pixel material line stays between primary and
secondary pixels after the seam moves.

`CompareDividerInteraction` also owns middle-button summon-and-drag. A middle
press anywhere with valid comparison geometry moves the seam to the pointer's
scene position, captures that button, follows movement, and releases only when
the same button is released. Normal left-button dragging still requires the
existing seam hit target. Touch ownership remains independent, and disabling
divider interaction rejects both mouse paths.

Mounted vertical and horizontal regressions summon far from the existing seam,
drag again, verify the projected line under the pointer, preserve pan/zoom, and
exercise disabled interaction. The SugarSubstitute Output regression routes a
real middle-button sequence through immediate comparison persistence and
reprojection, proving the new gesture does not revive the former recursive
feedback loop.

### P1 — Resolved: comparison pair replacement is atomic

QPane now exposes `setComparisonPair(primary_id, secondary_id)`. It validates
both sources and distinct identities before mutating state, installs the
secondary intent before selecting the primary, and therefore submits only the
requested final pair through the existing catalog selection lifecycle.

Mounted regression coverage records exactly one `sceneChanged` emission while
moving from `A/B` to `C/D`, verifies the exact final layer identities, and
proves that same-source and unknown-source requests leave selection, state,
scene identity, and emissions unchanged. QPane's stub, API reference,
narrative guides, and public demo use the atomic operation.

### P1 — Resolved: detail and comparison zoom feedback retain physical meaning

Comparison overlay scale no longer infers both sources from the primary image.
`NativeCanvasComparison` registers a QPane scene overlay and maps each
composition identity to its prepared `SceneSnapshotOverlayLayer`. Horizontal
and vertical physical scale come directly from that layer's source-to-panel
transform and the current device-pixel ratio.

A mounted 640×480/1600×900 regression compares all four reported scale values
against the two actual render-item transforms and asserts that the secondary's
independent horizontal and vertical scales differ from the primary as
expected.

Detail overlays now receive `CanvasOverlayState.display_scale`, a CuteCanvas
value derived from the actual source-to-panel transform and physical/logical
viewport ratio. SugarSubstitute therefore reports physical source scale
without importing QPane or treating logical viewport zoom as equivalent. The
upstream contract is tested at 1.0 and 1.5 DPR, with anisotropic transforms and
an empty-viewport fallback.

`tests/test_cutecanvas_zoom_indicator.py` restores the renderer-neutral
interaction contract through 12 cases. Mounted detail and native comparison
surfaces receive real wheel and double-click events; their actual overlay
snapshots drive the asserted labels and geometry. The suite also covers
pointer tracking, fade restart, floating-window parity, Output material
tokens, anisotropic formatting, reveal-region clamping, and offscreen
dividers. Heterogeneous 320×240/800×300 comparison sources prove that the two
labels remain independently truthful.

### P1 — Resolved: native comparison uses document execution ownership

`CanvasWorkspace` now passes its `CanvasDocumentRuntime` into
`NativeCanvasComparison`, which constructs QPane with that runtime's supported
physical execution runtime. Normal target canvases and the comparison surface
therefore share one host-supplied admission topology without exposing QPane to
SugarSubstitute.

A mounted comparison with a controllable host backend proves that QPane render
product work is submitted to the document runtime. The prior implementation
left that backend empty because comparison silently owned a separate default
runtime. The same integration now uses QPane's atomic pair API and scene
overlay API rather than independent selection calls or primary-only geometry.

### P0 — Resolved: inpaint uses no-copy local assets and document-owned mask intent

There was no historical local upload or Comfy-input copy contract to restore.
SugarSubstitute release 0.9.0 already staged local image inputs as their
absolute filesystem paths, and the current long-path work only changed that
value to the equivalent Windows subprocess path. Before July 2, Comfy's
`get_annotated_filepath()` used `os.path.join(input_dir, name)` without
containment; on Windows, an absolute `name` replaced `input_dir`. Comfy commit
`96e0e3585` fixed CVE-2026-56673 by resolving the joined path and rejecting
anything outside the selected input directory. Both the ordinary Desktop JPG
and the extended-length project-mask path in the reported error now fail that
same validation. The `\\?\` prefix makes the second value conspicuous but is
not the cause.

SugarSubstitute commit `0727533` added compatibility coverage for updated
Comfy contracts after that security change, but its probe never submitted an
external-path `LoadImage` or `LoadImageMask` prompt. Unit tests stopped at a
fake queue gateway and asserted the obsolete absolute value, so they encoded
the regression instead of detecting it.

Substitute BackEnd now owns secure local execution. Its
authorization service accepts only loopback requests, existing absolute files,
the two supported core loader identities, and valid SHA-256 metadata. It
returns no path, only a random token and the BackEnd-owned execution node
class. Authorizations expire, have a fixed capacity, are lock-protected,
cannot cross image/mask node identity, and fail if the file is removed or its
identity changes. The two execution-only nodes decode the authorized file and
preserve core `LoadImage` image/alpha behavior plus `LoadImageMask` channel
behavior. This does not relax Comfy's global path validation and does not make
arbitrary paths valid in ordinary prompts.

SugarSubstitute's local stager calls the new BackEnd route and applies the
BackEnd-returned node class plus opaque token only to the deep-copied execution
prompt. Its authored core class and path remain untouched. Remote execution
continues to use `/upload/image`, because a remote Comfy process cannot read a
local source. For maintainer testing, both repositories retain the currently
released 1.8.0 compatibility metadata. No speculative version, tag, installer
pin, or startup capability gate was added. Coordinated versioning and release
gating are intentionally deferred until the behavior is accepted.

The contemporaneous mask interaction failure was independent. The migrated
presenter asked the real `InputCanvasMaskBinding` for removed
`cube_alias`/`image_node_name` attributes; its authoritative fields are
`section_key`/`surface_key`. The failed lookup returned before activating the
associated image, mask, Input route, and brush. The presenter now consumes the
document binding contract. A mounted integration selects an inpaint image,
requires every pixel in the automatically materialized 83×61 mask to be
transparent zero, switches to pan/zoom, clicks the real mask binding, and
requires the owning image, mask, Input tab, and brush mode to become active.

Hostile BackEnd coverage rejects relative, missing, directory, malformed-hash,
wrong-class, remote-peer, expired, replaced, and cross-node requests; floods
the bounded registry concurrently; and proves token opacity and zero writes.
SugarSubstitute coverage proves execution-only mutation and performs full
generation dispatch through both inpaint loader branches. The explicit hidden
real-Comfy harness then crosses actual `/prompt` validation and execution with
ordinary and extended Windows paths, checks output dimensions and edge pixels,
and proves the Comfy input directory remains empty.

### P1 — Resolved: Input admission is headless and replacement is identity-stable

`InputCanvasDocument.ensure_image_cached()` now mutates its `CanvasDocument`
without opening a composition. Only the authorized route projection calls
`openComposition()`, so preload and restore order cannot change the visible
Input image.

CuteCanvas now exposes the generic
`CanvasDocument.replace_composition_image()` workflow. It replaces the
embedded content resource and intrinsic canvas bounds while retaining the
composition, content layer, resource, masks, and mounted inspection. The
operation publishes content changes to mounted views but never activates its
target. Its implementation lives with the existing image-document workflow,
placed-resource store, and composition service rather than adding image
lifecycle work to a widget.

Hostile upstream cases replace active masked content under custom pan/zoom and
resize an inactive image while another target remains focused. SugarSubstitute
cases independently prove that adding and repeatedly replacing a background
image cannot steal the route, and that active regeneration retains the exact
composition ID, mask ID, pan, and zoom.

### P2 — Resolved: hidden role-target renderers have an explicit lifetime budget

CuteCanvas now assigns role-target renderer lifetime to the focused
`CanvasTargetPool`. All targets required by the current surface remain live;
hidden renderers are retained through a least-recently-used budget and their
view execution scopes close on eviction. `CanvasWorkspace` exposes
`retained_target_capacity` with a default of 16, bounding duplicate overhead
without restoring a SugarSubstitute-specific renderer cache.

The common six-target detail/grid/comparison storm retains both hot role sets
and remains below its established 8 ms average switch budget. A 48-target
hostile case uses a capacity of five, verifies that leaving a grid drops from
48 renderers to at most six for detail and five for comparison, and rejects
negative budgets. Durable inspection remains in role sessions, so evicted
detail targets remount with linked viewport state rather than relying on a
hidden widget as storage.

### P2 — Resolved: host canvas execution is resource-aware and independently bounded

SugarSubstitute now gives canvas blocking I/O, Python CPU, native CPU, and
device work dedicated physical lanes instead of sharing the two-worker
`image_decode` FIFO. The focused `CanvasExecutionScheduler` owns the policy
ahead of those admissions: urgency with starvation-preventing aging,
per-resource and per-request concurrency, resource identities, exclusive
leases including adoption-held release, accepted-task capacity, and retained-
byte capacity.

The adapter remains SugarSubstitute-owned host policy, while CuteCanvas now
re-exports `ExecutionUrgency` and `ExecutionLeaseRelease` so the host imports
no QPane package. Normal targets and native comparison share this one runtime
through `CanvasDocumentRuntime`.

Deterministic contention tests block image decoding and still observe
interactive native canvas completion, queue background grid work before
interactive detail work and observe the interactive job start first, submit
eight same-resource jobs and prove physical concurrency never exceeds the
declared two, and reject a retained-payload estimate one byte above the host
budget. The tests use explicit one/four-worker fixtures rather than deriving
success from this machine's core count.

### P2 — Resolved: serial verification is repeatable across hostile temp state

The full gate exposed that the serial test runner reused deterministic
repository-local base-temp paths. A second invocation could encounter a prior
Windows directory tree and fail a valid atomic directory replacement even
though the same launcher module passed on the first run.

The serial runner now owns one fresh OS temporary root per invocation, gives
every isolated module a child base temp, and removes the root after the run.
Its fixture proves that all module processes receive the live shared root and
that the root no longer exists afterward. A hostile probe ran the launcher
first-install module through two consecutive serial-runner invocations; both
passed. The complete 123-module serial partition also passed at that point.
Later inpaint changes invalidated that full-gate result; the committed-state
serial status is recorded in the verification summary below.

## Confirmed good boundaries and non-regressions

### Dependency encapsulation

- Production SugarSubstitute canvas/bootstrap/execution sources contain no
  direct `qpane` import.
- `requirements.txt` pins `cutecanvas[sam]==0.1.1` and does not pin QPane;
  CuteCanvas owns its QPane dependency.
- No SugarSubstitute, Output, Scene-grid, or Batch-grid product terminology was
  found in the CuteCanvas or QPane package source.
- CuteCanvas uses QPane's public facade/SDK for rendering, inspection, layout,
  execution, and comparison. No reverse QPane-to-CuteCanvas dependency was
  introduced.

### Document ownership

- SugarSubstitute now owns one long-lived Input `CanvasDocument` and one
  long-lived Output `CanvasDocument`.
- Output images are document compositions with locked layer interaction and
  application UUID-to-composition identity mapping.
- Detail, grid, and comparison inspection are separated by presentation role;
  comparison has its own stable group identity.
- Context menus, drag/export, material seam, and zoom artwork consume
  CuteCanvas content/overlay contracts rather than importing a native pane.

### Scene and Batch grids

The grid contract is now complete for the reviewed migration blast area.
QPane's new `ResponsiveGridLayout` is an appropriate source-neutral extraction
of SugarSubstitute's former maximum-area topology, 1.02 hysteresis, centered
incomplete rows, native-aspect packing, and two-pixel visible gutter policy.
CuteCanvas keeps the grid inspection independent, fits and locks each tile
after reflow, and applies shared integer geometry so adjacent widgets do not
develop unequal rounded gutters.

Passing mounted coverage includes:

- compact native packing and a rendered two-pixel seam;
- mixed portrait/landscape sources in equal cells;
- one-pixel width changes with equal tile sizes and fixed gutters; and
- stable centered final-row placement over repeated resize;
- a forced 1.5 DPR mounted grid with equal logical tiles and exact three-
  physical-pixel gutters through one-pixel resize steps;
- a 7×5 width-starved mount with bounded, positive, non-overlapping targets;
  and
- repeated wide/tall topology changes whose settled rendered center pixels
  remain assigned to the correct colored source.

Grid viewports remain role-isolated, fitted, and navigation-locked after every
reflow. Comparison and linked-detail corrections do not participate in grid
inspection or alter its gutter owner.

## Failure modes now covered by transition-level proof

The initial replacement tests verified final object state while omitting the
transition that users see. Remediation added direct coverage for each omission:

- linked views assert normalized center and span before and after first-open
  activation, remount, and resize;
- comparison uses heterogeneous large patterned sources, requires tiled
  strategy, and samples dense settled pixels across pair changes, source
  replacement/removal, orientations, divider extremes, pan, zoom, and resize;
- comparison double-click and wheel navigation resolve the visible clipped
  source, including distinct 1:1 scales for equal-shape heterogeneous
  resolutions;
- comparison wheel and API storms stop when the slower source reaches 1000%,
  including inverse, equal, and non-uniform source transforms, while replacing
  a comparison source reconciles an existing over-limit view;
- pair replacement counts scene emissions and rejects invalid mutations
  atomically;
- divider storms count zero durable scene replacements across 102 updates;
- comparison seam projection follows pan and zoom exactly, while vertical and
  horizontal middle-button gestures summon, drag, release, and respect disabled
  interaction;
- zoom labels derive from mounted render snapshots after real gestures;
- Input admission asserts that background add and replacement never route; and
- Cube-output navigation forces deferred surface deletion between physical
  A -> B -> A clicks and verifies settled renderer pixels, while an upstream
  capacity-one storm combines disjoint targets, eviction, recreation, and
  teardown;
- restored comparison chrome requires each side's scene, batch, and source
  labels to agree with its resolved document target and rendered pixels,
  including a cross-scene/cross-batch pair;
- comparison projection replay emits no user intent, while real divider and
  orientation mutations survive immediate synchronous persistence/reprojection
  exactly once; and
- grid and execution fixtures apply fractional-DPR, width-starved,
  many-target, retained-byte, priority, and concurrency pressure.

The former adapter stack's observable contracts are therefore established at
the new generic owners rather than inferred from final-state smoke tests.

## Completed remediation sequence

1. Correct QPane comparison geometry so both sources occupy one explicit common
   frame with testable per-layer physical transforms.
2. Make QPane divider updates presentation-only and pair replacement atomic;
   add patterned large-image settled-frame and latency tests.
3. Bind `NativeCanvasComparison` to `CanvasDocumentRuntime`, then derive
   comparison overlay scales from actual layer transforms.
4. Correct CuteCanvas first-mount inspection ordering and separate initial
   viewport policy from composition removability.
5. Restore end-to-end zoom indicator characterization on the corrected detail
   and comparison paths.
6. Make Input composition admission headless and leave activation exclusively
   to the authorized route projector.
7. Preserve the passing grid geometry while adding fractional-DPR,
   width-starved, settled-pixel, and many-target resource coverage.
8. Size and characterize SugarSubstitute's shared canvas execution admission.
9. Correct CuteCanvas target-pool ownership across deferred presentation
   destruction and replace route-only Output tab tests with mounted mouse and
   settled-pixel proof.
10. Scope SugarSubstitute detail inspection to stable
    `(workflow, scene, batch)` groups while leaving comparison role-local.
11. Route QPane native zoom through visible-source hit testing and preserve
    the clicked source coordinate at source-native 1:1.
12. Make comparison clipping presentation-transient, add forced-tile pixel
    abuse, and reconcile source replacement and deletion without viewport
    resets or stale scenes.
13. Separate persisted comparison presentation from user-intent publication,
    suppress native setup transitions, and make identical inspection-group
    assignment a no-op.
14. Restore the QPane-only scene-relative seam contract, project divider chrome
    from that seam, add middle-button summon-and-drag, and correct both tile
    oracles to use transformed scene geometry.
15. Run the complete required repository gates on the exact remediated
    worktrees.
16. Make both comparison navigation bars projections of their rendered side
    selections and prove identity agreement through restored and
    cross-scene/cross-batch comparisons.
17. Bound custom comparison zoom at 1000% of the slower source-native scale,
    preserve zoom-out semantics, and prove wheel storms plus source replacement
    through QPane, CuteCanvas, and the Output document.
18. Recover the historical inpaint path contract, add a secure no-copy local
    authorization capability to Substitute BackEnd, rewrite only queue
    payloads, repair document-owned mask-click intent, and execute both
    branches against current real Comfy with an extended-path abuse fixture.

Each upstream change must remain source-neutral. SugarSubstitute should provide
document content, groups, presentation intent, styling overlays, transfer
policy, and physical execution policy; it should not recover direct QPane
imports or duplicate inspection/render geometry.

## Verification evidence

Observed commands and probes:

- Production restored-session probe:
  physical scene entry followed by source `workflow_25871:16 -> :7 -> :16`
  presents the exact expected three image UUIDs at every step. Before the fix,
  the return click raised from `CanvasTargetPool.mount()` because the cached
  `CuteCanvas` had been deleted.
- Red/green tab lifecycle proof:
  the upstream disjoint-grid deferred-destruction regression and
  SugarSubstitute real-shell A -> B -> A regression both fail against the
  broken target pool and pass against the correction.
- Red/green inspection proof:
  the mounted three-scene/two-batch/two-source Output projection failed with
  one twelve-member linked group and now reports the exact six two-member
  groups. Session and document ownership cases pass in the same focused run.
- Red/green source-native navigation proof:
  the mounted QPane comparison failed because double-clicking the
  higher-resolution side selected zoom `1.0`; it now selects `2.0`, preserves
  the clicked source coordinate, and toggles independently through FIT.
- Red/green comparison zoom-bound proof:
  forty production wheel steps formerly reached viewport zoom `20061.77` for a
  320×240/640×480 pair. The mounted parameterized fixture now stops at `20`,
  `10`, or `12.5` according to which equal, inverse, or non-uniform source
  reaches 1000% last. Smooth wheel bursts, live comparison-source replacement,
  ordinary sub-1× zoom-out, CuteCanvas presentation, and the SugarSubstitute
  Output document pass the same owner contract.
- Red/green tile proof:
  the upstream five-second dense-pattern oracle observed an exact color from
  the wrong source on the former implementation. The corrected upstream
  fixture completes 24 tiled pair/navigation/resize transitions, and the
  SugarSubstitute Output fixture completes 12 production transitions without
  a mismatched interior sample.
- Red/green mutation proof:
  active source replacement initially reset zoom `1.75` and pan
  `(117, -83)` to FIT through an unrelated primary refresh. Targeted resource
  refresh now preserves that viewport and presents the replacement pixels.
  Active secondary removal initially left the deleted blue layer visible;
  QPane now presents the surviving red primary and CuteCanvas safely
  reconciles to its composition.
- Red/green comparison-feedback proof:
  initial persisted projection formerly emitted three comparison states. The
  corrected bind emits none. The permanent fixture then synchronously rebinds
  every real native divider/orientation signal through the production
  projection sink and requires one completed replay per user mutation without
  recursion. Upstream setup tests require one initial requested presentation
  and no inspection capture for identical group assignment.
- Red/green seam and middle-button proof:
  the broken divider remained at viewport x `297.6` while its transformed
  scene seam was x `-83.96`; the corrected mounted fixture requires exact
  agreement through two custom zoom/pan states. Middle-button press was
  previously unclaimed; vertical and horizontal gestures now summon and drag
  the seam under the pointer, preserve the viewport, and stop on matching
  release. SugarSubstitute paints its two-pixel material line between the two
  source colors after moving the seam and persists a real middle-button drag
  through immediate projection replay.
- Current comparison-renderer red/green proof:
  fault-injecting the former circular-storage choice makes the default
  offscreen clipped-scene regression fail with storage origin
  `QPoint(216, 0)`. The production linear-storage policy passes that invariant,
  the same-state retained/full-redraw pixel comparison, and the independent
  long-pan oracle. The visible Windows diagnostic reproduced 889,119
  mismatched pixels before the correction and passed afterward, but now
  requires both `QPANE_RUN_NATIVE_DESKTOP_TESTS=1` and
  `--allow-desktop-window`.
- Current focused SugarSubstitute runs:
  `7 passed` across production Output comparison abuse, comparison document
  behavior, and fixed grid gutters, followed by `38 passed` across zoom
  indicators, the Output document, real-shell Output scenarios and abuse
  matrix, and the extended comparison tile/pan fixture. Targeted Ruff and
  strict mypy pass for the changed fixture.
- Inpaint history and live-execution proof:
  - SugarSubstitute `0380833` returns the selected absolute path directly;
  - Comfy `96e0e3585` changes that acceptance to a realpath containment check;
  - SugarSubstitute `0727533` adds update probes without a loader prompt;
  - 29 focused SugarSubstitute staging and inpaint-document cases pass
    offscreen;
  - Substitute BackEnd's complete format, lint, strict-mypy, and 254-test
    parallel gates pass; and
  - the hidden real-Comfy fixture reports core authored payload preserved,
    zero copied files, both Substitute execution classes, and exact 23×17
    image/mask results, including the extended E-volume mask path.
- Current comparison-chrome red/green proof:
  the exact restored comparison fixture rendered Text to Image on the left and
  Diffusion Upscale on the right but failed because the left source label was
  `Diffusion Upscale`. The corrected fixture passes that case and a second
  scene 1 batch 2 versus scene 2 batch 1 case while checking resolved IDs,
  sampled side colors, and all six labels. The focused navigation,
  controller, picker, document, and real-shell selection passes 84 cases;
  targeted Ruff formatting/lint and strict mypy pass for all five touched
  source and test files.
- Complete QPane/CuteCanvas verification:
  - Ruff and Black leave all 850 Python files clean;
  - encoding, 577-file docstring, facade/API-order, independent Public API
    Trinity, and license-header checks pass;
  - the exact offscreen full suite reports `1440 passed, 1 skipped in
    159.73s`; the skip is solely the explicit native desktop diagnostic;
  - strict interactive-performance probes now use a real shared/exclusive
    worker barrier instead of contending with ordinary xdist workers;
  - `git diff --check` passes.
- SugarSubstitute's current complete format, lint, strict typing, and offscreen
  parallel gates pass. The serial runner was first invalidated at module 92 by
  removing a speculative unreleased-version policy, then deliberately stopped
  at module 22 when the maintainer clarified that local testing must precede
  release gating. Neither partial run had a failure. A complete serial run
  remains pending for commit/release readiness.
- Dependency checks find no direct QPane import in SugarSubstitute source or
  tests and no SugarSubstitute policy terminology in either upstream package.

The SugarSubstitute root contains old untracked `.pytest-tmp*` fixture trees
owned by another local Windows account. Some intentionally contain invalid
nested `pyproject.toml` fixtures, so the prior complete format and lint gates
excluded only those generated trees by passing all 3,442 Python and stub files
reported by `rg --files`; every accessible tracked and untracked source file
remained in scope. The corrected serial runner no longer creates or reuses
those repository-local variants.
