# CuteCanvas Adoption Investigation

## Executive conclusion

SugarSubstitute should move both canvases onto CuteCanvas, with two
application-lifetime documents:

- The Input canvas should use one long-lived CuteCanvas `CanvasDocument`.
  Input images become compositions and masks become document resources/layers.
- The Output canvas should use a separate long-lived CuteCanvas
  `CanvasDocument`. Each generated image becomes a read-only composition;
  batch and scene views use CuteCanvas's responsive grid presentation; content
  compositions retain presentation-role-specific viewports; host-selected
  detail views remain linked across selector switching, grids remain
  independent, and comparison has its own exact two-composition linked group;
  reveal comparison remains transient `CanvasWorkspace` presentation state.
- SugarSubstitute must remain authoritative for workflow identity, graph
  bindings, route projection, preview/final acceptance, project assets,
  persistence, docking, and chrome.
- Output drag-out and `Copy` should share one SugarSubstitute transfer policy.
  CuteCanvas supplies the stable composition subject; SugarSubstitute selects
  canonical PNG or companion JPEG and materializes durable or staged MIME
  data.

CuteCanvas is therefore the only application-facing canvas integration.
QPane remains the renderer, viewport, execution, and input substrate beneath
both documents. CuteCanvas owns the native-QPane comparison presentation;
SugarSubstitute only routes/persists it and supplies existing Output styling.

The move is feasible. All eight public integration contracts are implemented in
the local QPane/CuteCanvas worktree and passed its complete required gate on
2026-07-27:

1. **Implemented locally:** CuteCanvas exports an arbitrary mask by UUID,
   without activating it or changing visible editor state.
2. **Implemented locally:** CuteCanvas replaces existing mask pixels from a
   file or `QImage` while retaining mask identity.
3. **Implemented locally:** QPane owns source-neutral maximum-reference-area
   topology, 2% hysteresis, centered incomplete rows, exact physical geometry,
   and immutable snapshots. CuteCanvas exposes workspace policy, snapshots,
   activation, context subjects, and drag subjects without private surface
   access.
4. **Implemented locally:** `CanvasWorkspace` retires target canvases and
   mounts when their compositions leave the document.
5. **Implemented locally:** `CanvasWorkspace` preserves host-owned linked
   inspection groups across presentation changes.
6. **Implemented locally:** CuteCanvas forwards outbound materialization
   failure from target canvases through the workspace with the gesture's stable
   `DragSubject`.
7. **Implemented locally:** CuteCanvas now owns `CanvasInspectionGroup` and
   accepts it from `CanvasWorkspace.setInspectionGroups(...)`; SugarSubstitute
   no longer needs to name QPane's linked-inspection type.
8. **Implemented locally:** CuteCanvas exposes its host execution and outbound
   MIME contract through its own runtime facade and standard package typing
   entry points. SugarSubstitute presentation imports `ExecutionRuntime`,
   `DragSubject`, `OutboundMimeProvider`, `OutboundDragPayload`, and
   `OutboundMimeItem` from CuteCanvas rather than QPane UI/runtime modules.

The editable package installation itself is viable. A pip dry run from the
SugarSubstitute virtual environment successfully resolved both split packages
from `E:\devprojects\qpane`.

### Maintainer direction

The selected target is two CuteCanvas documents: one Input document and one
Output document. QPane remains CuteCanvas's underlying rendering/runtime
dependency for application canvas surfaces.

There are no existing external consumers of the split QPane or CuteCanvas
packages. The migration may therefore make cohesive breaking changes to their
public APIs when needed; it must update every in-repository call site and
remove superseded APIs rather than retain compatibility aliases, shims, or
deprecated parallel paths. SugarSubstitute's host-facing and persisted-data
contracts remain the behavior boundary.

## Current correction status (2026-07-27)

The implementation is not complete. The earlier status table is retained as
historical investigation context, but its completion and full-gate claims are
superseded by the findings below.

### Migration owner audit (2026-07-28)

SugarSubstitute must not import or call QPane as an application canvas seam.
The supported dependency direction is SugarSubstitute → CuteCanvas → QPane.
The editable development installer deliberately installs both local packages,
because CuteCanvas depends on QPane; that installer knowledge is packaging
setup, not an application integration surface.

The current refactor removes SugarSubstitute's direct QPane production imports
for responsive-grid types, drag subjects, execution contracts, and comparison
overlays. CuteCanvas exports the required public facades instead. The
application requirement and launcher import probes name `cutecanvas`, not
`qpane`; the latter remains a transitive CuteCanvas dependency.

Comparison chrome is now a CuteCanvas public presentation contract. A host
registers artwork with `CanvasWorkspace.registerComparisonOverlay(...)` and
receives a typed `CanvasComparisonOverlayState`: document comparison IDs,
divider geometry, native viewport, and the physical display scale of both
sources. `CanvasWorkspace.comparisonZoomGesture` and
`comparisonPointerMoved` expose pointer-originated comparison feedback without
returning QPane state. CuteCanvas alone bridges those values to its persistent
native QPane comparison renderer and owns repaint requests. SugarSubstitute's
normal `CanvasZoomIndicator` is therefore detail-only; its separate
comparison indicator draws the two established labels from CuteCanvas values,
one constrained to each reveal side. It no longer reads a QPane catalog,
divider, transform, or widget method.

Ordinary detail chrome now follows the same boundary. CuteCanvas exposes
`CanvasOverlayState` and `registerCanvasOverlay(...)`; its state names the
logical and physical viewport, pan, zoom, transform, and source image without
leaking QPane's `OverlayState.qpane_rect` or pan fields. SugarSubstitute's
detail percentage indicator uses this contract exclusively. The old generic
overlay hook remains inside CuteCanvas for its own low-level feature tooling;
application hosts use the renderer-neutral hook.

The remaining legacy `CanvasPaneCatalogPort` was removed. Input workflow
services now depend on `InputCanvasDocumentPort` and its
`CanvasDocumentMutation` result, which describes CuteCanvas composition
admission rather than a renderer catalog cache. SugarSubstitute does not own
or name a QPane cache, viewport, layout, comparison, transfer, or execution
surface.

The shell already injects one host-owned `ExecutionRuntime` into both Input
and Output through CuteCanvas's documented `CanvasDocumentRuntime`/
`CanvasWorkspace` API. `CanvasDocumentRuntime` remains document-scoped state;
it is not a cue for SugarSubstitute to create another resource owner.
SugarSubstitute must consume that existing CuteCanvas composition boundary and
leave QPane resource ownership encapsulated there.

Focused offscreen verification after this correction passes: SugarSubstitute's
Input/Output document, real-shell Output abuse, transfer/context, dependency,
license/header, localization, and execution slices; plus CuteCanvas workspace
and presentation-abuse coverage (`20 passed`). The CuteCanvas regressions
exercise both the comparison overlay contract and the ordinary
`CanvasOverlayState` contract. The SugarSubstitute menu regression asserts the
established icon identities as well as the action order. This is focused
evidence only; it does not make historical full-gate claims current.

### Established Output behavior that remains the migration contract

- The existing Output canvas context menu is a normal Output action set, not a
  `Copy`-only menu. Outside grids it contains Compare outputs when available,
  Copy, Open in Photoshop, Open All in Photoshop, Reveal in File Manager, and
  Undock/Redock canvas. Its route and authorization behavior comes from the
  pre-migration controller at baseline `0b3dae9`; its implementation must be
  CuteCanvas-native rather than copied QPane code.
- A source or scene grid requires a targeted `Copy` action for the actual tile
  under the pointer. That one-item targeted action is additional grid behavior;
  it must never replace the existing Output canvas context menu.
- Drag-out and both Copy entry points must capture a `CanvasContentReference`
  at gesture time and use the same SugarSubstitute MIME preference and
  materialization policy. They must not change selection or consult later UI
  state while transfer work is pending.
- Grid packing must match the old visual contract: gutters, ordering, native
  aspect treatment, and responsive reflow. The implementation may improve
  responsiveness but must not change the product's visible packing.
- Grid, detail, and comparison presentations must own independent viewport
  state. A zoom/pan from a grid or comparison cannot affect detail. Host-linked
  detail views intentionally synchronize as the user switches individual
  outputs. Comparison uses its own exact two-target linked group.

### Corrected current ownership

`CanvasWorkspace` keys mounted CuteCanvas renderers by presentation role and
composition for detail and grid only. The `SINGLE` role covers
individual/tabbed output views and receives the host-selected linked inspection
group. The `GRID` role owns non-navigable tile renderers with independent
inspection state. The `COMPARISON` role is instead one
`NativeCanvasComparison`: a single native QPane render scene built from two
CuteCanvas document compositions. It has no overlapping CuteCanvas child
widgets, QWidget masks, or child-widget reveal geometry. QPane owns the clip,
divider hit testing, drag, pan, and zoom inside that one render plan.

The comparison session's `InspectionStateStore` is injected into QPane's
catalog navigation. Composition UUIDs are the QPane catalog source IDs, so the
CuteCanvas two-target inspection group is the linked-viewport owner without an
identity translation layer. Detail, grid, and comparison retain separate
inspection stores. Changing divider position or orientation updates the same
native QPane scene with `fit=False`; it never refits or inherits a grid/detail
viewport. Initial activation remains in QPane's FIT mode until its final
mounted viewport has non-zero geometry, which avoids the old activation-time
wrong-zoom bug.

SugarSubstitute preserves the original Output material seam as a QPane overlay
only. It does not participate in divider geometry or input. Native comparison
right-clicks emit the primary `CanvasContentReference` through the workspace,
so the established full Output context menu remains available rather than a
Copy-only menu.

The document bridge deliberately accepts a direct imported-image composition
(or a blank composition for general workspace tests). It fails rather than
silently flattening a layered editable composition; Output generated images
are direct imported-image compositions, so this is the correct present scope.

Responsive-grid layout owns cell geometry; `GridViewportController` fits a
tile only after its final grid geometry is applied, then locks navigation.
`GridTargetGestureController` owns click-versus-drag threshold arbitration and
targeted context dispatch. These are distinct responsibilities; the grid
surface composes them without becoming their policy owner.

Output supplies an explicit `ResponsiveGridPolicy` to CuteCanvas rather than
relying on QPane defaults: maximum-reference-area topology, 1.02 topology
hysteresis, centered incomplete final rows, and packed native tiles. Its gutter
is the original native-scene ratio (1/512, with a two-pixel minimum), not an
incorrect fixed viewport-space value. QPane owns that native-layout
calculation; CuteCanvas owns the single integer cell partition that rasterizes
it to a stable two-pixel visible gutter. Shared row/column edges are rounded
once, all grid canvases mount to those full cells, then each image fits inside
its cell. That preserves every pixel of a source image, keeps gutters fixed
during resize, and prevents same-size tiles from acquiring independent
rounding offsets. A grid surface releases its gesture filters before a
retained canvas is re-mounted in a replacement surface, so returning from
detail cannot leave stale grid gesture owners attached.

SugarSubstitute now composes `OutputCanvasContextMenu` and
`OutputGridContextMenu` through `OutputContextMenuRouter`. The router selects
the grid-target menu only for a `GRID` presentation. A grid action retains the
exact `CanvasContentReference` received from CuteCanvas: Copy materializes that
target, Open in Photoshop opens that target, and the dock action uses the same
Undock/Redock state as detail. Any other presentation uses the established
full Output menu. The non-grid Copy action also goes through
`OutputTransferClipboardController`, so its MIME target is the same configured
PNG/JPEG target as drag-out and grid Copy.

CuteCanvas distinguishes a deliberate target selection from a change to the
session's active ID. A visible grid click always emits `targetActivated` after
validating the composition exists, even when a return-to-grid presentation has
left that composition active. This is required for Output navigation to drill
into the same tile again after Back; state equality must not suppress the
user's navigation event.

The router is a `weakref_slot` dataclass because PySide stores a bound signal
handler through a weak reference. Without that slot, composing the Output menu
raised `TypeError: cannot create weak reference to 'OutputContextMenuRouter'
object` during `build_main_window`. The context-menu composition now consumes
an explicit typed Output host action surface instead of reaching into private
host fields; the host remains the owner of its compare state, metadata lookup,
external-editor integrations, and dock state.

### Verified so far

- QPane/CuteCanvas focused workspace, content-reference, responsive-layout,
  session, and presentation-storm suite: `37 passed`. This includes a real
  image grid-fit regression, linked detail switching, independent
  grid/detail/comparison viewport regression, and linked comparison zoom.
- SugarSubstitute focused Output document, Output context menu, transfer menu,
  main-composition, Output host-contract, and workspace drag/drop suite:
  `88 passed`.
- Latest composed context-menu startup regression and baseline-menu contract:
  `36 passed` across Output document/context-menu/transfer-composition/
  main-composition tests. It
  constructs the real offscreen Output canvas, attaches the router to the
  public CuteCanvas context signal, emits a grid-target request, and requires
  the addressed Copy model to be produced without opening a native popup.
- Complete serial offscreen real Output-shell scenario, abuse-matrix, and
  floating-grid suite: `63 passed`.
- The new serial offscreen real-shell packed-gutter regression passes. It
  proves production route projection uses two columns/two rows for that
  baseline fixture, preserves the original 1/512 native-scene gutter across
  stable reflow, and rasterizes it to the stable two-pixel visible gap.
- Targeted SugarSubstitute Ruff and format checks pass; targeted strict mypy
  passes for the seven changed source files.

### Resolved Output-correction proof (2026-07-27)

The following failures have been corrected at their rendering or presentation
owner and have focused offscreen proof. These checks use the normal Qt test
harness; they do not launch a headed application window.

- **Reveal comparison:** `NativeCanvasComparison` retains one native QPane
  catalog scene while pairs change. It selects the next two document sources
  and updates QPane's native comparison state in place; it does not rebuild a
  widget, apply a QWidget mask, or echo its own persisted divider state back
  into QPane. The comparison-pair abuse harness changes 120 pairs, requires
  the same native pane and correct final primary/secondary identities, and
  stays below the interactive presentation-switch budget.
- **Comparison opening and linked inspection:** a newly created detail canvas
  restores the linked normalized inspection state as soon as its target is
  activated. The workspace regression covers switching to a never-before-seen
  linked output with a different source size. Grid and comparison roles remain
  separate from detail inspection state.
- **Zoom feedback:** the standard `CanvasZoomIndicator` is attached only to
  active Output detail surfaces. CuteCanvas supplies comparison divider,
  viewport, pointer, and physical-scale state to a separate comparison
  indicator, which renders two independent source-scale labels on the
  appropriate sides without SugarSubstitute querying QPane.
- **Menu icon parity:** the document-backed detail and grid menus use the same
  icon assignments as the retired Output menu: Copy, Photo, Image Multiple,
  Folder Open, Full Screen/Back to Window, and the checked Compare icon. The
  action set and target routing are unchanged.
- **Grid geometry:** CuteCanvas's grid owner forces the visible nonzero gap to
  the old two-pixel gutter on both axes while retaining the original 1/512
  native-scene packing rule. Existing direct document regressions resize one
  pixel at a time, require equal same-source mounts, require both horizontal
  and vertical two-pixel gaps, and require the centered incomplete row to keep
  its relative position. No image is clipped to obtain this result.
- **Transient Comfy previews:** the full strict `PreviewImageUpdate` to
  `LivePreviewEvent` to registry to `OutputDocumentPreviewPresenter` path now
  has a rendered-pixel regression. It requires the first green preview and a
  same-lane blue replacement to become visible in the real Output target. The
  real-shell abuse harness's preview assertion now also samples the mounted
  target pixels, not merely registry or document state.

The focused final verification set is: 35 Output document/menu/transfer tests,
62 real-shell Output scenario and abuse tests, 23 CuteCanvas workspace/session
tests, two mounted CuteCanvas presentation-abuse tests, and QPane's native
comparison-abuse test. Source-level Ruff and strict mypy pass for every
modified SugarSubstitute and CuteCanvas implementation module. The broader
repository gates remain commit-time work rather than evidence for this focused
correction set.

### Native comparison implementation status (2026-07-27)

The old `IndependentCanvasComparison` stacked two full-size CuteCanvas widgets
and applied a QWidget mask on every divider update. It is superseded for the
built-in comparison presentation and has been removed rather than retained as
a compatibility surface. CuteCanvas now mounts one QPane and calls QPane's
native `setComparisonImage` / `setComparisonSplit` APIs. QPane's
`ViewerComparison` updates only its render scene and normalized layer clip;
its divider interaction uses the current render plan directly.

QPane now accepts a host-owned `InspectionStateStore` for catalog navigation.
CuteCanvas gives that QPane the comparison role's inspection owner and uses the
two composition UUIDs as catalog source IDs. This preserves a linked
comparison viewport without coupling it to detail or grid viewports. The
comparison QPane is inserted into its final layout before it is shown; its
first selection remains FIT and recalculates against the real viewport rather
than retaining a zero-size activation fit.

Focused offscreen proof currently passes:

- SugarSubstitute Output: `30 passed` across document, context menu, transfer,
  and real-shell focused suites. The new regression drags the real native
  divider and requires one unchanged widget geometry, an empty widget mask,
  FIT activation, persisted split, in-place orientation, real pointer pan,
  and preserved comparison/detail viewport state. A second regression sends a real context-menu event to the native pane
  and requires the normal Output context route. A third renders the original
  two-pixel, square-capped material seam through QPane's overlay API and
  verifies both source images remain visible on either side of it. A composed
  Output test sends a real native divider drag and then an orientation update,
  requiring both to reach the persisted `OutputCompareState` event boundary.
- QPane/CuteCanvas: `25 passed` across the focused native catalog and complete
  workspace suites. These verify QPane-owned clip/divider updates, injected
  linked inspection, comparison-role isolation, in-place orientation, and the
  absence of a masked overlay surface.
- Ruff passes for all changed files. Strict mypy passes for changed Sugar
  source files. A strict direct upstream source run still reports pre-existing
  QPane typing errors outside this work and is not a full upstream gate.

The exact material seam is now covered in an offscreen native render. Remaining
comparison proof is production-route end-to-end coverage for preview,
persistence, and all navigation routes before calling the migration complete.

## Superseded implementation status

| Field | Current state |
| --- | --- |
| Current phase | 6 — Complete for the historical implementation described in this status table; the current migration-owner audit above is the authoritative record for follow-up work. |
| SugarSubstitute baseline | `0b3dae9`; worktree contains the completed local CuteCanvas integration and this maintained `NOTES.md` |
| QPane/CuteCanvas baseline | `acc0969`; local worktree contains the uncommitted, fully verified upstream contract implementation described below |
| Completed implementation | Superseded by the 2026-07-28 migration-owner audit above. The historical implementation description in this row used `QPaneExecutionBackend`; the active SugarSubstitute adapter is `CuteCanvasExecutionBackend`, which consumes CuteCanvas's public execution contract while CuteCanvas encapsulates its QPane dependency. |
| Verification | Focused upstream slices: `117 passed`; complete upstream suite: `1371 passed` in 111.00 seconds, including non-positive navigation-buffer fallback. After the target-lifetime regression, the focused workspace suite passes (`9 passed`) and the real Output-shell suite passes (`42 passed`) with every displayed final output required to have a live, parented, visible CuteCanvas target. The direct offscreen Output widget regression now admits known red and blue `QImage` final outputs, renders the first image, changes through grid reflow, restores the first single presentation, and asserts the visible CuteCanvas target still contains the admitted red pixels. Ruff passes for the changed upstream and SugarSubstitute files. Ruff, Black, encoding, docstrings, API order, public API Trinity, GPL-header normalization, and `git diff --check` pass for the earlier full upstream state. Both split wheels build and import from an isolated installation. SugarSubstitute focused Input, route, workspace-composition, signal, SAM warmup, startup resource, managed-ready, and bootstrap tests: `254 passed`; direct offscreen InputCanvas construction and document identity/export checks passed. Output document characterization, including document-target activation, public reveal-divider persistence, source-preview activation, scene-preview overview representation, unchanged-payload replacement detection, and warm document lifetime across widget close, plus host/workspace/coordinator coverage: `135 passed`. Transfer artifact cancellation, resolver, drag, and clipboard coverage: `12 passed`; editable-install, runtime-requirement, release-payload, launcher, and installed-layout coverage: `37 passed`; the real local editable install and `pip check` passed. The complete real Output shell matrix passes (`74` checks), including reflow and abuse scenarios. SugarSubstitute strict mypy passes (`3131` sources); Ruff and format checks pass. Full parallel tests pass (`8445` tests, `103` expected serial skips), and all `122` serial modules passed before the final dead-test removal; the affected real-shell serial subset and localization coverage pass afterward. |
| Remaining work | Publish `qpane==0.1.1` and `cutecanvas[sam]==0.1.1` to PyPI, then run a fresh release-pin install/CI bootstrap against those published distributions. |
| Known blockers | Split-package PyPI releases do not yet exist. The verified local editable overlay remains the executable development path; exact published release pins cannot be exercised until those distributions are released. |
| Next safe step | Tag and publish the two packages, then verify the release workflow from a fresh SugarSubstitute environment. |

Update this table as each vertical slice lands. It records actual implemented
state and verification, not intentions or a chronological work log.

The current Output foundation is
`substitute.presentation.canvas.output.output_document.OutputCanvasDocument`.
It owns the one Output document/runtime/session/workspace quartet, locked
base-layer policy, application-to-composition registry, stable content
references, replacement, retirement, linked inspection, and single/grid/reveal
presentation. The live projection path synchronizes authorized application
content into that document and projects every Output route through its public
workspace.

The first-image rendering invariant is explicit: `CanvasWorkspace` lets the
new child canvas open its composition before the workspace session is
activated. `CuteCanvas.openComposition(...)` therefore performs the initial
scene and viewport setup exactly once. A workspace-level regression admits an
image and requires a live scene with a positive fit zoom; the real Output-shell
regression also samples the rendered target pixels after a real output update.

Target mounts are document-lifetime owners, not presentation-surface children.
When a grid changes membership, the workspace detaches every retained mount
that the replacement surface did not adopt before deleting the old surface.
This prevents a stale Python `CuteCanvas` wrapper from surviving after Qt has
deleted its C++ object; a workspace regression narrows a grid then restores its
targets and requires the original renderers to remain usable.

Outbound gesture ownership is now equally explicit. Every grid target uses the
cursor/drag tool with pan and zoom locked: release without crossing Qt's drag
threshold activates the tile; crossing it starts the configured per-tile
transfer and captures that target's content reference. A right-click is routed
through the same addressed target to the grid-target Copy action without
activation. That action is separate from, and must not replace, the existing
Output canvas context menu used by non-grid presentations.
The workspace fallback drop controller rejects any source that is the current
Input or Output canvas, or a QObject descendant of either, before it considers
MIME data. This preserves native exports from batch and scene grids while
preventing their own file URLs from being loaded back as workflow documents.

`OutputCanvasProjectionCoordinator` now depends on the application-facing
`OutputProjectionContentSynchronizer` port rather than a QPane catalog warmer
and payload hydrator. The production
`OutputProjectionContentSynchronizer` admits authoritative registry payloads
into `OutputCanvasDocument` and retires them only after application workflow
ownership releases them. `OutputCanvas` now mounts that document's workspace,
uses `OutputDocumentRouteProjector` for guarded final-image/reveal routes,
and maps source grids, scene overviews, and linked groups to workspace
presentations. The coordinator no longer receives a route projector or linked
group sink: `OutputCanvas.bind_projection_session(...)` is the sole live
presentation owner. It has no direct QPane widget, catalog, or synthetic
scene composition dependency.

The dead `OutputLinkedGroupPresenter` public export and its QPane-backed
module have been removed. `OutputCanvasDocument` now remains the only owner
of Output linked inspection, deriving its stable two-member
`CanvasInspectionGroup` only for the authorized active comparison.

The complete legacy direct-QPane Output island is removed: the QPane adapter
package, synthetic composition runtime, QPane catalog/presenter, source and
scene composition builders, reflow controller, grid route controller, route
binding controller, and their dedicated fixtures/tests no longer exist.
`OutputCanvasDocument`, `OutputDocumentNavigation`, and
`OutputDocumentPreviewPresenter` are the only Output canvas presentation
owners. The old QPane zoom indicator was removed with its QPane overlay
dependency. `OutputRevealZoomIndicator` now owns the replacement as a
transparent child of the public `CanvasWorkspace`: it binds only the two
canvases returned by `canvasFor(...)` for the public comparison presentation,
captures public wheel/double-click gestures and `zoomChanged` signals, and
draws transient per-target zoom labels from `currentZoom()` against the public
split and orientation state. It neither traverses workspace widgets nor changes
the broader inspection group or document state.

`OutputDocumentNavigation` is the live navigation presentation owner. It
builds source tabs and set/scene/source pickers from the application
projection, delegates selection policy to the existing source-neutral
navigation model, and publishes the resulting product intent through the
existing Output signals. A workspace grid activation resolves the captured
CuteCanvas composition back to an application image identity before that same
navigation policy runs. Reveal splitter movement comes through the public
workspace presentation snapshot; the adapter emits a changed
`OutputCompareState` only when the split actually differs, so the application
continues to own persistence and projection refresh.

`OutputDocumentPreviewPresenter` is the corresponding preview presentation
owner. It never writes the preview registry or application route state. It
filters an acceptance to the current Output session, mirrors its already
authorized pixels into locked Output compositions, refreshes the expanded
preview scope, and asks the host to present a source preview or scene
representative overview. Final-output closure and clear commands first obtain
the registry's exact retired IDs, then retire only those document compositions.
`OutputCanvasDocument` uses the Qt image cache key plus the authorized path to
recognize unchanged payloads; it does not use transient Python object identity,
which can be reused after a generated image wrapper is released.

## Scope and non-negotiable constraints

This document is the maintained technical foundation for the migration. It
describes source state observed on 2026-07-27 and should be revised when the
QPane/CuteCanvas checkout changes.

The parity migration must preserve:

- existing visible Input and Output behavior;
- persisted SugarSubstitute project and asset formats;
- application/workflow UUID meaning;
- stale-workflow and stale-generation rejection;
- one warm Input surface and one warm Output surface across workflow switches;
- graph binding, mask ownership, preview/final lifecycle, and navigation
  semantics;
- SugarSubstitute's fail-closed mask-save preflight before generation; and
- current docking, floating, menu, overlay, and navigation chrome.

The migration should not:

- turn SugarSubstitute workflow state into CuteCanvas document state;
- expose new editing tools or layer-management behavior;
- silently replace PNG project assets with `.cutecanvas` files;
- depend on CuteCanvas or QPane private implementation objects;
- add compatibility shims around the old monolithic QPane API; or
- retain a second SugarSubstitute-owned responsive-grid engine beside the
  CuteCanvas workspace layout owner.

The requested per-tile drag-out, per-tile `Copy`, and configurable companion
JPEG transfer target are approved additions to this otherwise behavior-parity
migration.

## Repository baselines

### SugarSubstitute

- Repository: `E:\devprojects\SugarSubstitute`
- Initial worktree state: clean
- Release dependency contract: `qpane==0.1.1` and `cutecanvas[sam]==0.1.1`
- Active development installation: paired editable `qpane` and `cutecanvas`
  source roots under `E:\devprojects\qpane\packages`
- Canvas rules: `substitute\presentation\canvas\AGENTS.md`
- Project workspace schema: version `"1"`

The installed QPane is the pre-split, combined viewer/editor library. It
contains mask editing and SAM under the `qpane` package.

### QPane/CuteCanvas monorepo

- Repository: `E:\devprojects\qpane`
- Branch: `main`
- Initial worktree state: clean
- Observed HEAD: `acc0969`
  (`test(fixtures): add retained mask reproduction project`)
- Package split commit: `13659e7` on 2026-07-23
- Relevant later commits:
  - `c6be506` — project resources and sampled painting
  - `bf899ad` — unified host-supplied execution runtimes
  - `6fd3cd7` — high-resolution navigation stabilization
  - `acc0969` — retained-mask reproduction coverage

The monorepo now contains independent packages:

| Package | Authoritative responsibilities |
| --- | --- |
| `qpane` | Immutable render scenes, raster/vector rendering, viewport navigation, viewer catalog, comparison, hit testing, cache management, and the execution kernel |
| `cutecanvas` | Editable documents, compositions, resources, layers, masks, selections, tools, history, editor policy, SAM, editable persistence, and multi-view presentation |

The dependency direction is intentionally one-way:

```text
SugarSubstitute Input  -> CuteCanvas -> QPane
SugarSubstitute Output -> CuteCanvas -> QPane
```

QPane must not import CuteCanvas. SugarSubstitute should respect the same
boundary.

Current local package metadata resolves both packages as
`0.1.1.dev50+gacc096929`. CuteCanvas declares
`qpane>=0.1.0,<0.2.0`. The repository has older monolithic tags such as
`v2.1.1`, but no package-specific release tags for this split line yet.

## Current SugarSubstitute ownership

### Product state is already outside QPane

The existing architecture keeps most application meaning out of the widget:

- `WorkflowCanvasState` owns input keys, input image IDs, mask associations,
  mask-to-image ownership, active input image/mask, and active canvas route.
- `CanvasSessionBoundary` owns Input and Output workflow identity, monotonic
  revisions, route identity, and stale visible-mutation rejection. Output
  scopes additionally carry generation identity.
- `WorkflowInputCanvasService` interprets graph bindings, creates synthetic
  mask-only canvases, validates mask dimensions, and rejects ambiguous input
  ownership.
- `OutputCanvasProjection` owns backend identity, source/set/batch grouping,
  scene grouping, active source/set/image, active scene/overview, and compare
  state.
- Shell/presentation code owns docking, floating windows, tab availability,
  focus, and SugarSubstitute's navigation chrome.

These are application semantics. CuteCanvas documents must derive their
visible route from this state rather than replace it.

### Warm-widget invariant

SugarSubstitute intentionally owns exactly:

- one Input CuteCanvas widget and its document; and
- one Output CuteCanvas workspace and its document.

Both stay warm across workflow switches. Catalog eviction is a memory/lifetime
operation, not the correctness boundary. Correctness comes from
workflow-scoped state plus guarded route projection. The migration should keep
the same widget lifetime and authorization model.

## Current Input behavior contract

### Content and routing

`InputCanvas` now hosts `InputCanvasDocument`, which constructs the one
application-lifetime `CanvasDocument`, `CanvasDocumentRuntime`,
`CanvasViewSession`, and `CuteCanvas(features=("mask", "sam"))` widget.
`InputCanvasDocument` maps the application Input image UUID to a separately
generated document composition UUID and publishes a host-owned materialization
event after registry admission. Authorized routes flow through the
source-neutral `InputRouteProjector`; there is no Input QPane route adapter in
the live integration.

The application:

- creates images with SugarSubstitute UUIDs;
- maps those UUIDs to CuteCanvas composition identities after document
  admission;
- maps graph input keys to image UUIDs;
- maps each workflow mask binding to a mask UUID;
- maps mask UUIDs back to their owning image UUID;
- recreates masks from project assets during restore;
- remaps persisted mask UUIDs to live editor mask UUIDs;
- activates the authorized image and mask on workflow switches; and
- removes cached images only after proving no workflow references them.

Mask-only graph sections receive a synthetic blank input composition whose
size comes from the graph's dimension authority. A loaded mask is rejected
before state or pixels change when its dimensions are wrong or unverified.

### Mask tools and policy

The visible Input mask menu exposes:

- Pan & Zoom
- Brush
- Smart Select

The active image must have a mask before edit tools are available. The base
image is not user-editable or movable. SugarSubstitute does not present a layer
manager or general transform/reorder workflow.

### Asset persistence and generation preflight

SugarSubstitute, not QPane, owns canonical mask assets:

1. Blank-mask materialization writes an initial PNG to the application-owned
   project path.
2. The PNG is associated with the workflow cube/node binding.
3. The live mask is created in the editor.
4. Subsequent mask changes mark that associated mask dirty.
5. A debounced save updates the canonical PNG.
6. Before generation, every dirty associated mask is synchronously flushed.
7. Failure to resolve, export, or save any required mask blocks generation.

The save controller can flush masks that are not currently active. This is a
critical API requirement: exporting only the active mask is insufficient.

### Removed private dependencies

The Input persistence path no longer reaches through QPane ownership:

- `InputCanvasDocument.image_has_masks(...)` uses
  `listMasksForComposition(...)` behind the registry mapping;
- `InputMaskSaveController` listens to `CuteCanvas.maskUndoStackChanged`;
- `InputMaskSaveController` receives `InputCanvasDocument.export_mask_image`,
  which calls public `exportMaskImage(...)` without route mutation; and
- `InputCanvasStateService` replaces pixels through
  `InputCanvasDocument.replace_mask_from_file`, backed by public
  `replaceMaskFromFile(...)`.

The debounce is now an explicit SugarSubstitute-owned value at composition
time rather than a QPane settings read. The remaining legacy QPane Input
sources are obsolete removal work and must not regain consumers.

### Meaning of `imageLoaded`

The current installed QPane emits `imageLoaded` from its image-swap
coordinator. SugarSubstitute relays the event with the route-authorized image
ID and uses it for graph association.

The current CuteCanvas public facade has no `imageLoaded` signal or inbound
file/drop API. This should not be replaced with an internal signal. Document
composition creation is already initiated and identified by the host, so the
future Input document adapter should publish a host-owned
"composition/image materialized" event after the registry is updated. That
event can feed the existing graph-association use case with explicit
SugarSubstitute identity.

## Legacy Output behavior contract

### Output projection

Before the document migration, the Output canvas used QPane as an immutable
viewer and retained payload catalog. `OutputCanvasProjection` and its
controllers owned four visible route shapes:

- `empty`
- `image`
- `source_grid`
- `scene_overview`

Generated content is admitted only when its workflow/generation scope is
current. Preview/final replacement, preview retirement, focus, grouping, and
route selection remain application-owned.

### Grids and overviews

Before migration, source grids and scene overviews were one synthetic layered
scene in one QPane viewport:

- the scene builder derives rows and columns from the physical viewport;
- every tile has deterministic scene geometry and an application tile model;
- one viewport supplies pan/zoom behavior for the whole layout;
- a click is mapped back to the tile's application meaning;
- resize reflow rebuilds the scene topology; and
- scene overviews select one representative preview/final per scene.

The migration contract is the resulting packing and interaction semantics, not
the old synthetic-scene implementation. CuteCanvas uses independent grid tile
renderers so drag-out and addressed context actions have a stable target; the
tiles must remain non-navigable and the grid must reproduce the old packing.

### Linked inspection and reveal comparison

The removed direct-QPane Output canvas had two related behaviors:

- `OutputLinkedGroupPresenter` placed every projected workflow output image
  into one QPane `LinkedGroup` when at least two unique outputs exist. This is
  baseline behavior to characterize, not a permission to share viewport state
  between CuteCanvas grids, details, and comparison targets.
- Compare mode selects an independent base and comparison output, then uses
  QPane's reveal divider. Its two sides have independent scene/source/set
  selectors, orientation, and split position.

The reveal slider complements linked switching; it does not replace it. The
custom SugarSubstitute zoom indicator can report the distinct effective scales
of the compared sources. Clearing comparison and moving among single-image,
grid, and overview routes are guarded by the active Output projection.

### Old QPane APIs in use

The current adapters depend on pre-split APIs including:

- `addImage(image_id, image, path)`
- `imageIDs()`
- `removeImageByID(image_id)`
- `getCatalogSnapshot()`
- `setCurrentImageID(...)` / `currentImageID()`
- `composeScene(...)`
- `openComposition(...)`
- `removeComposition(...)`
- `getCompositionSnapshot()`
- `setComparisonImageID(...)`
- `clearComparisonImage()`
- `sceneHitTest(...)`

These calls must be replaced completely when moving to the split package line.

### Current drag-out and copy behavior

QPane's legacy drag-out is path-based. It offers the current image path as a
native file URL and uses the current `QImage` as the drag preview. A synthetic
batch or scene grid has no per-tile current path, so the legacy behavior cannot
drag an individual grid tile.

The current Output context menu is deliberately suppressed for source grids
and scene overviews. On a single-image route its `Copy` action obtains the
route-authorized current image ID, then copies `pane.currentImage` to the
clipboard. It does not copy a selected file representation and it cannot bind
an action to the tile under the context-menu pointer.

The new product behavior changes that boundary:

- dragging from a batch or scene tile exports that tile's underlying image;
- right-clicking a tile offers `Copy` for that captured tile;
- one output-transfer preference selects canonical PNG or companion JPEG for
  both operations; and
- existing single-image drag/copy remains available through the same policy,
  with canonical PNG as the default target.

The target must be captured when the gesture or context request occurs.
Neither operation may re-read whichever image happens to be active after a
menu has opened or asynchronous encoding has started.

## CuteCanvas document model fit

### Durable and transient ownership

`CanvasDocument` is a headless durable model. It owns:

- a stable document ID;
- independent compositions and their coordinate spaces;
- resource-backed ordered layer instances;
- masks, vectors, and reusable content;
- document events; and
- composition-scoped edit history.

`CanvasViewSession` separately owns detachable presentation state such as the
active composition and inspection state. View/session state is not document
edit history.

`CanvasDocumentRuntime` owns document execution scope and freshness. A host can
inject a shared QPane `ExecutionRuntime`; a CuteCanvas widget does not close a
host-owned runtime.

This separation is a strong match for the Input canvas:

- the document owns editable image/mask content;
- the view session mirrors the currently authorized Input route;
- SugarSubstitute retains workflow and graph semantics; and
- the document runtime can participate in the application execution system.

### Resource/layer identity

CuteCanvas distinguishes:

- a composition;
- a reusable resource;
- a layer instance referencing a resource; and
- a mask resource whose editable coverage may have one or more composition
  layer associations.

SugarSubstitute currently treats its input image UUID as both application
identity and the old QPane catalog identity. CuteCanvas generates its own
composition/resource/layer UUIDs and does not accept a caller-supplied
composition ID when creating a composition from an image.

The future integration therefore needs an application-owned identity registry:

| SugarSubstitute identity | CuteCanvas identities to retain |
| --- | --- |
| Input image UUID | Composition ID, base-layer ID, base resource ID |
| Workflow cube/node mask binding | Mask resource ID and composition layer ID |
| Persisted mask UUID | Remapped current mask resource ID |

Application UUID meaning must not be overloaded with a CuteCanvas UUID merely
because both use `UUID`.

### Recommended document lifetime

Use one application-lifetime Input `CanvasDocument`, one
`CanvasDocumentRuntime`, one `CanvasViewSession`, and one CuteCanvas widget.
Create one composition per cached Input image.

Reasons:

- CuteCanvas binds a document/runtime at widget construction and has no public
  document-rebind operation.
- one document preserves the current warm-widget behavior;
- histories are maintained per composition scope, so edits in one workflow
  composition do not make undo cross into another; and
- SugarSubstitute can remove a composition when it has proved that no workflow
  references the corresponding input image.

The registry needs global reference accounting. The same input image UUID can
be referenced by more than one workflow, so composition lifetime must not be
owned by only the currently active workflow.

### Interaction policy required for parity

CuteCanvas's standard `MASK_AUTHORING` mode permits more than the current
SugarSubstitute UI, including layer movement and transform. A parity migration
should supply an explicit host policy:

- editor capabilities: select pixels, edit pixels, and paint only;
- non-editable paint behavior: reject;
- base image layer: fixed, nonselectable, nonmovable, noneditable,
  nonreorderable, and nonremovable;
- mask layers: pixel-editable, nonmovable, and nonreorderable; and
- no general layer-management surface.

The host can set layer policies through
`setLayerInteractionPolicy(...)`. Brush and Smart Select behavior must be
characterized with this exact policy before the widget switch.

### Public Input API mapping

| Current need | CuteCanvas public contract | Status |
| --- | --- | --- |
| Create image-backed editable target | `createCompositionFromImage(...)` | Available |
| Activate image target | `openComposition(composition_id)` | Available |
| Create blank mask | `createBlankMask(size)` | Available |
| Load mask | `loadMaskFromFile(path)` | Available |
| Activate mask | `setActiveMaskID(mask_id)` | Available |
| Remove mask association | `removeMaskFromComposition(...)` | Available |
| List masks for image/composition | `listMasksForComposition(...)` | Available; replaces private manager query |
| Observe durable mask edits | `maskUndoStackChanged(mask_id)` | Available |
| Read active mask pixels | `getActiveMaskImage()` | Available but too narrow for preflight |
| Export any mask by ID | `exportMaskImage(mask_id, composition_id=...)` | Implemented locally; returns detached grayscale, canvas-clipped pixels without changing active composition/mask. `composition_id` is required for an ambiguous shared non-active mask. |
| Replace existing mask pixels, preserving ID | `replaceMaskFromFile(mask_id, path)` and `replaceMaskImage(mask_id, image)` | Implemented locally; both retain the mask UUID, layer associations, and history ownership. |
| Apply restricted layer behavior | `setLayerInteractionPolicy(...)` and `setEditorPolicy(...)` | Available |
| Smart Select/SAM | CuteCanvas `sam` feature and SAM facade | Available |
| Observe host materialization | No `imageLoaded` equivalent | Use a SugarSubstitute-owned adapter event |

`listMasksForComposition()` returns public `MaskInfo`, including mask,
scene/layer, composition, interaction, appearance, and active-state
information. It is the supported replacement for querying a private mask
manager.

`maskUndoStackChanged(mask_id)` is emitted for committed brush strokes,
retained-coverage changes, Smart Select/generated edits, rasterization, and
undo/redo. It is a suitable dirty signal. Merely activating a mask does not
emit it.

`getActiveMaskImage()` does not solve pre-generation flush because the save
controller must export every dirty associated mask without mutating the
visible active composition/mask. A general layer projection is also not a
replacement: it may include presentation tint/effects instead of the exact
clipped grayscale mask coverage.

CuteCanvas contains an internal `AutosaveManager.saveMaskToPath(...)`, but
SugarSubstitute must not call it. The public export operation should either:

- return a detached clipped grayscale `QImage` for a requested mask ID; or
- provide an explicit host save operation with terminal success/failure.

It must not change active UI state. Its completion contract must allow
SugarSubstitute's generation preflight to remain fail closed.

## Output document target

### Document and surface lifetime

Create one application-lifetime Output `CanvasDocument`, one
`CanvasDocumentRuntime`, one `CanvasViewSession`, and one `CanvasWorkspace`.
Apply `CanvasInteractionMode.READ_ONLY` to every workspace view.

The Output document contains one read-only content composition for every
admitted preview or final image. Grid, single, linked-switching, and reveal
arrangements are workspace presentation state; they do not create synthetic
document compositions.

Linked inspection and comparison are not document content. The host supplies a
transient group for linked detail switching and CuteCanvas creates a separate
two-member group for the active comparison. Grid views remain independent.

The Output registry should retain:

| SugarSubstitute identity | CuteCanvas identities |
| --- | --- |
| Output image UUID/backend identity | Content composition ID, base-layer ID, resource ID |
| Active source grid | Ordered content composition IDs and target-to-set/source map |
| Active scene overview | Ordered representative composition IDs and target-to-scene map |
| Linked detail switching | Stable inspection group ID and ordered composition members |
| Active reveal comparison | Separate stable inspection group ID and its two content composition members |
| Preview/final lifecycle | Current content composition ID plus retirement ownership |

As with Input, SugarSubstitute UUIDs and CuteCanvas UUIDs are separate
identity domains.

### Route mapping

| Existing route | Output document presentation |
| --- | --- |
| `empty` | Registered zero-target custom workspace presentation, followed by `CanvasViewSession.clear_activation()`, behind the existing availability overlay |
| `image` | `CanvasWorkspace.setSinglePresentation(content_composition_id)` with host-linked detail viewport state |
| `source_grid` | `CanvasWorkspace.setGridPresentation(ordered_batch_composition_ids, ...)` |
| `scene_overview` | `CanvasWorkspace.setGridPresentation(ordered_representative_composition_ids, ...)` |
| reveal comparison | Set the separate exact two-member comparison group, then `setComparisonPresentation(primary_id, secondary_id, split_position=..., orientation=...)` |

### Content compositions

Admit each accepted Output image with
`CanvasDocument.create_composition_from_image(...)`. Keep its composition
host-removable for lifecycle cleanup, while `READ_ONLY` editor policy prevents
user structural operations. Make the base layer nonselectable, nonmovable,
noneditable, nonreorderable, and nonremovable. Record the returned
composition/resource/layer identities in the Output registry.

When a preview is retired or an image becomes globally unreferenced:

1. remove or redirect every active presentation that names it;
2. remove it from the linked inspection group;
3. remove its content composition; and
4. release its registry entry only after document/workspace retirement is
   confirmed.

### Output MIME transfer and clipboard target

#### Existing upstream fit

The split QPane/CuteCanvas line already has most of the correct drag boundary:

- QPane's pan/zoom tool promotes a fitted-image pointer move to drag-out only
  after the platform drag threshold is crossed.
- `OutboundDragController` owns one native drag lifecycle, cancels superseded
  materialization, rejects late results, marshals completion to the GUI
  thread, and executes a copy drag.
- `OutboundDragPayload` can carry file URLs, arbitrary MIME bytes, text, and a
  `QImage` preview.
- CuteCanvas resolves the default drag subject to a revision-bearing
  `CanvasContentReference` for the visible composition.
- `CanvasWorkspace.setOutboundMimeProvider(...)` installs one host provider on
  every current and future target canvas.
- The built-in independent-view grid mounts one CuteCanvas per composition, so
  a drag that starts in a cell naturally identifies that cell's composition.

CuteCanvas now forwards QPane's `OutboundDragController.failed` signal through
both the target canvas and its workspace as `outboundDragFailed(subject,
message)`. The signal retains the subject captured when the gesture started,
so SugarSubstitute can log structured technical context and translate the
failure into its normal user-facing error surface without inspecting child
widgets.

SugarSubstitute should install one Output workspace provider. The provider is
an adapter around application-owned transfer materialization, not the owner of
JPEG or filesystem policy.

There is one interaction caveat. A future shared-viewport grid cannot rely on
the child-canvas default subject because it has only one renderer. The public
workspace grid contract must therefore resolve a pointer to a composition
subject from the same immutable layout snapshot used for hit testing. The
click/drag arbiter must ensure that crossing the drag threshold starts one
drag and suppresses tile activation on release.

QPane's standalone PanZoom tool permits drag-out only while content fits its
viewport; the same left-button gesture pans zoomed content. Workspace grids do
not use that navigation tool: their cursor/drag targets lock navigation, so a
tile always resolves a primary gesture as either click activation or outbound
drag at the platform threshold. Grid interaction characterization must verify
that linked inspection state does not make a visible tile ineligible for
drag-out.

CuteCanvas now publishes `contentContextRequested(subject, global_position)`
from `CanvasWorkspace`, forwarding the stable subject from every current and
future presentation target. SugarSubstitute must consume that public signal;
it must not walk child widgets through `canvasFor(...)` or inspect workspace
collections to infer the context target.

#### Authoritative transfer preference

Add a separate output-transfer preference rather than placing transfer state
inside `JpegOutputSettings`:

```text
OutputTransferFormat.CANONICAL_PNG
OutputTransferFormat.COMPANION_JPEG
```

The default is canonical PNG, preserving the existing single-image drag
target and clipboard pixels. The Settings control belongs visually with the
JPEG companion controls and should read as one localized choice such as
“Use companion JPEG for drag and copy.”

The effective format is companion JPEG only when both:

1. the transfer preference selects companion JPEG; and
2. JPEG companion generation is enabled.

Disabling JPEG companions preserves the stored transfer choice but makes PNG
effective. Re-enabling companions restores the choice. Keeping transfer state
separate is important because `JpegOutputSettings` is copied into immutable
generation save plans and consumed by the encoder; clipboard and drag policy
must not leak into output generation.

The persisted output-preference schema is now version `"3"`. Legacy payloads
load with `canonical_png`; normalization preserves the independent stored
choice; and the localized Settings catalog exposes it beside JPEG companions.
The remaining work is to consume the effective choice only in the shared
transfer resolver.

`OutputTransferArtifactStore` now owns the representation materialization
below that resolver. It only reuses a regular registered `.png` canonical path
or its exact `.jpg` sibling, validates the bytes as the selected image, and
otherwise stages the explicit PNG or JPEG representation from the authorized
current pixels. Each staged artifact carries a one-shot lease. The active drag
and clipboard controllers retain at most one selected staged artifact each,
release the previous artifact when it is superseded, and the lifecycle closes
all remaining files at shutdown. Store construction reclaims only regular
`output-transfer-*.png` and `output-transfer-*.jpg` files in its managed cache
root; unrelated files, directories, and symlinks are never removed.
`OutputTransferArtifactStore.materialize(...)` receives the application task's
cancellation predicate. It checks before image/file work and before staging;
if cancellation arrives after encoding, it avoids committing a file, and if it
arrives after a write, it deletes that unleased file before returning. The drag
and clipboard task adapters pass their own `CancellationToken` predicate through
the shared resolver, so a stale task cannot leave a staged artifact.

`OutputTransferResolver` now maps one captured `CanvasContentReference` back
through `OutputCanvasDocument`, requires the supplied product authorization,
snapshots preferences, materializes through that store, and revalidates the
same reference before returning. It does not present MIME data or run on the
GUI interaction path; those responsibilities remain with the pending
execution-backed drag and clipboard adapters.

`output_transfer_payloads` is the deliberately thin native representation
boundary: it converts only a resolved artifact into matching `OutboundDragPayload`
or `QMimeData` file URL, raw MIME bytes, and decoded image data. It cannot
choose a transfer format or touch document/workflow state. The remaining
adapter owns dispatch, cancellation, stale completion suppression, workspace
provider installation, captured context-menu presentation, and clipboard
publication on the GUI thread.

`OutputTransferDragProvider` submits captured `CanvasContentReference`
resolution through SugarSubstitute's bounded `image_decode` task lane and
returns the task as QPane's per-gesture cancellation handle. QPane continues
to own native-drag generation invalidation and GUI-thread execution.
`OutputTransferClipboardController` uses the same captured reference and
resolver, cancels a superseded Copy operation, and publishes matching native
MIME data only for the latest current result. `OutputTransferContextMenu`
receives `CanvasWorkspace.contentContextRequested(...)` and binds its Copy
action to that exact reference without route activation. The Output shell
composition installs both controllers; `OutputTransferLifecycle` closes them,
unregisters both runtime submitters, and removes staged artifacts during shell
shutdown. The shell also forwards captured drag failures and clipboard
materialization failures through `OutputTransferFailurePresenter`, which logs
the technical reason and presents localized non-blocking feedback. Bounded
leases, cancellation-aware staging, and the shared CuteCanvas execution backend
are complete.

`OutputDocumentRouteProjector.is_image_allowed_for_transfer(...)` is the
single current-session authorization query supplied to the transfer resolver.
`OutputCanvas.install_transfer_drag_provider(...)` is the narrow workspace
installation seam. The Output shell composition constructs and installs the
provider with the app runtime and staging store rather than adding policy to
the widget.

#### One transfer resolver for drag and copy

Create one application-owned output transfer service with a small immutable
result, conceptually:

```text
Output composition reference
          |
          v
authorize and map to Sugar output image identity
          |
          v
resolve effective PNG/JPEG policy
          |
          v
reuse durable file or stage encoded current pixels
          |
          v
OutputTransferArtifact(path, MIME type, bytes/image, content revision, lease)
             |                                  |
             v                                  v
 CuteCanvas outbound provider             clipboard adapter
```

This service is authoritative for:

- mapping a CuteCanvas composition ID back to the SugarSubstitute output image
  record;
- verifying the content reference, current Output session, and registry
  membership are still authorized;
- resolving the effective target format from one captured preference
  snapshot;
- validating and reusing an exact registered canonical path or its exact
  `.jpg` sibling;
- encoding a managed staged artifact when no reusable file exists;
- returning bytes/pixels derived from the same selected representation; and
- owning staged-artifact leases and cleanup.

The drag adapter converts the result to `OutboundDragPayload`. The clipboard
adapter converts it to `QMimeData`. Neither adapter chooses a format, derives a
companion path, or performs its own fallback.

#### Durable and memory-only targets

The resolver cannot assume every visible Output composition has a file.
`OutputPersistenceMode.FINAL_CUBE` intentionally keeps non-final cube outputs
in memory, and a scene-overview representative can be a live preview. Both are
valid grid tiles.

Resolution therefore follows these rules:

1. For PNG, reuse the registered canonical file when it is still a regular
   file; otherwise encode the current authorized pixels to a managed staged
   PNG.
2. For JPEG, reuse the exact `.jpg` sibling when it exists; otherwise encode
   the current authorized pixels with the current companion sizing policy and
   stage a JPEG.
3. JPEG encoding must retain the existing companion semantics, including
   white flattening for transparency and the selected quality or target-size
   mode.
4. If the configured representation cannot be encoded, reject the operation
   with user-visible failure feedback. Do not silently export PNG under an
   explicit effective JPEG preference.
5. Never derive a path from arbitrary composition metadata. Start from the
   authorized SugarSubstitute registry record, then accept only its exact
   canonical path or derived companion sibling.

The staged filename should be readable and collision-safe. Staged URLs must
remain valid for the native drag/drop or clipboard consumer, so they cannot be
created in a context manager and deleted as soon as the callback returns.
Use a bounded application cache with leases, cleanup when clipboard ownership
changes where safe, and managed stale-cache cleanup on startup/shutdown.
Cancellation must discard uncommitted artifacts.

#### Native drag payload

For a successful drag, offer:

- one file URL to the selected durable or staged artifact;
- the selected encoded bytes under `image/png` or `image/jpeg`;
- a decoded image of that same selected representation for image-aware drop
  targets and the drag preview; and
- an optional safe display label, not an unrelated filesystem path.

QPane currently uses `OutboundDragPayload.preview` both as the drag pixmap
source and as `QMimeData` image data. That is acceptable here only if the
preview is decoded from the selected artifact. Using the original lossless
pixels as the preview/image MIME while offering a lossy JPEG URL would create
two conflicting transfer targets.

The provider captures the `CanvasContentReference` at gesture start. Before
publishing an asynchronously encoded result it must resolve that reference
again and verify the Sugar registry record still maps to the same composition.
Preview replacement, workflow switching, composition retirement, a new drag,
or workspace teardown must prevent a stale drag from starting.

Durable-file reads, image encoding, and staging must run through the
host-owned execution boundary rather than block the GUI thread. The final
native drag execution remains on the GUI thread through QPane's controller.

#### Tile context menu and clipboard

The context request should carry a stable document subject and global
position. CuteCanvas owns resolving the right-click to the visible composition
across single, grid, and comparison presentations and forwarding that subject
through the workspace. SugarSubstitute owns the menu model and actions.

The current grid-menu suppression and `pane.currentImage` lookup must be
replaced. A grid `Copy` callback binds to the captured tile subject without
activating the tile, changing the Output route, or depending on later active
selection. If the subject becomes stale before the action runs, the action
does nothing destructive and reports that the image is no longer available.

The clipboard payload should contain:

- image data decoded from the selected PNG or JPEG representation;
- the matching raw `image/png` or `image/jpeg` bytes; and
- the selected durable or staged file URL for file-oriented paste targets.

This preserves normal image paste while allowing file-oriented targets to see
the configured JPEG companion. Clipboard publication must be atomic and occur
on the GUI thread only after successful materialization. A scene live-preview
tile is copyable through staged materialization, subject to the same revision
check.

The requested grid menu contract adds `Copy`; it does not implicitly broaden
unrelated grid actions. Single-image `Copy` moves onto the same transfer
policy, while the other existing single-image menu actions retain their
current behavior until deliberately moved onto the captured-subject model.

#### Ownership boundary

| Owner | Output-transfer responsibilities |
| --- | --- |
| QPane | Drag threshold and native gesture arbitration; cancellable/stale-safe drag execution; generic MIME payload conversion |
| CuteCanvas | Stable document content references; resolve the visible composition subject; propagate the host provider and context-subject requests across current/future workspace targets and presentation kinds |
| SugarSubstitute | Output authorization and identity mapping; PNG/JPEG preference; canonical/companion path policy; encoding and staged-file lifetime; menu contents; clipboard publication; localized settings and failure feedback |

The JPEG companion setting, Sugar output paths, temporary filenames, and
clipboard/menu product policy do not belong in CuteCanvas. Presentation-aware
subject resolution does belong there because a host should not inspect
`CanvasWorkspace._surface`, `_canvases`, `_mounts`, or child QWidget topology
to discover which document target received a gesture.

### Responsive batch and scene reflow

CuteCanvas `CanvasWorkspace.setGridPresentation(...)` is backed by QPane's
public source-neutral layout SDK:

- `ViewTargetSpec` pairs stable composition identity with native dimensions.
- `ResponsiveGridLayout` partitions the viewport in integer physical pixels,
  then returns logical Qt geometry without fractional-DPI drift.
- `ResponsiveGridPacking.NATIVE_TILES` preserves the former Output scene
  geometry: one reference native tile size, maximum-area topology with 2%
  hysteresis, proportional gutters with a two-scene-unit floor, row-major
  packing, and centered incomplete final rows. The dominant scene axis alone
  determines the proportional gutter, matching the retired scene formula.
- `ResponsiveGridSnapshot` contains stable target frames, cell and
  aspect-preserving content rectangles, rows/columns, hit testing,
  visible-target queries, center-biased prefetch order, and bounded damage
  against the previous snapshot.
- `ResponsiveCanvasGrid.resizeEvent(...)` reflows retained composition views
  directly; it does not rebuild document content or render scenes.

This is the correct authoritative primitive for both Output grid routes:

1. a batch/source grid supplies the active source's ordered set compositions;
2. a scene overview supplies one ordered representative composition per scene;
3. SugarSubstitute retains the mapping from composition ID to set/source or
   scene navigation meaning;
4. `CanvasWorkspace` owns resize observation, physical layout, retained target
   views, and reflow; and
5. target activation routes through the existing guarded Output projection.

No aggregate composition, QPane scene request, route-composition identity, or
host resize timer is needed.

#### Ownership boundary

| Owner | Responsive-grid responsibilities |
| --- | --- |
| QPane | Source-neutral `ViewTargetSpec` geometry; topology strategy; physical-pixel partitioning; gaps and row alignment; previous-snapshot hysteresis; immutable frames; hit testing; visibility; prefetch order; and bounded damage |
| CuteCanvas | Convert document composition IDs/native bounds into layout targets; expose workspace grid policy and snapshots; mount/reuse/retire target views; publish target activation; apply cell inspection behavior; and provide independent- or shared-viewport presentation |
| SugarSubstitute | Select and order batch or scene compositions; map composition IDs to workflow source/set/scene meaning; authorize the active route; and interpret target activation as product navigation |

Maximum-area scoring, centered incomplete rows, and breakpoint hysteresis are
not SugarSubstitute domain rules. They are reusable target-layout policy and
belong in QPane's layout SDK. CuteCanvas should configure and expose that
policy for document compositions rather than reimplementing it.

Conversely, QPane should not know about documents, batches, scenes, workflows,
or workspace widgets. Those remain CuteCanvas and SugarSubstitute concerns at
their respective boundaries.

#### Comparison with the current SugarSubstitute engine

| Concern | Current SugarSubstitute implementation | CuteCanvas/QPane primitive |
| --- | --- | --- |
| Render targets | One synthetic QPane scene with image layers | Independent retained composition views |
| Topology | Scores every column count for maximum displayed reference-tile area | Output selects QPane native-tile packing with the same maximum-reference-area topology |
| Resize | 16 ms coalescing timer, session capture, stale delivery rejection, scene rebuild | Synchronous widget resize reflow over current validated presentation targets |
| Pixel geometry | Native tiles with proportional scene-unit gutters, followed by viewport fit | The same native packed tiles and gutter formula, scaled from physical viewport geometry into logical Qt geometry |
| Mixed aspect ratios | Topology uses the first valid reference extent; each layer is then fitted | Every `ViewTargetSpec` carries its own native size and content frame |
| Stability | 2% topology hysteresis and layout signatures | Output policy retains the prior topology within its 2% hysteresis window |
| Partial final row | Centers the incomplete row | Output native-tile policy centers the incomplete final row |
| Hit/navigation | QPane layer hit plus application metadata | Workspace grid publishes immutable snapshots and composition activation; context/drag gestures publish stable content subjects |
| Incremental work | Skips unchanged signatures | Snapshot provides visibility, prefetch order, and bounded damage; CuteCanvas retains target canvases across reflow and retires removed targets |

The QPane primitive is now the authoritative policy superset for the required
geometry. Output explicitly selects native-tile packing rather than the
generic equal-cell mode, so its existing gutters and packing are preserved;
only responsive topology and physical-DPI reflow change. CuteCanvas exposes
the policy and snapshot through `CanvasWorkspace`, while gesture routing
supplies stable content subjects without exposing private child-widget
topology.

The built-in grid uses retained independent child viewports. Its layout now
matches the established Output packing contract, including the native tile
frames, so SugarSubstitute's former `ResponsiveCanvasGridPolicy` and
`grid_layout_for_dimensions(...)` have been removed. SugarSubstitute selects
and orders the batch/scene targets because those are workflow semantics;
CuteCanvas and QPane own how those composition targets reflow.

### Linked composition switching

Translate the active workflow's ordered, deduplicated output image IDs into
content composition IDs. When at least two exist, publish one stable
`LinkedGroup` to the Output `CanvasViewSession.inspection` store. Entering a
batch or scene grid changes presentation targets without changing that group.

The existing source, set, and scene navigation controls remain the switching
UI. Selecting another output changes the workspace's single presentation to
that content composition. `SessionInspectionBinding` captures the normalized
visible region from the old composition and restores the group's state on the
new composition, including correct scale projection when native dimensions
differ.

The group ID should remain stable while the active projection's membership is
updated so `InspectionStateStore.replace_groups(...)` retains the group's
stored inspection state. Empty Output state clears the group.

This uses CuteCanvas/QPane's linked-inspection model without adding visible
tabs or replacing SugarSubstitute's current navigation chrome.

### Reveal comparison

`CanvasWorkspace.setComparisonPresentation(...)` is the document-native match
for Output comparison. It clips two independent views at a physical-pixel
divider. Both compared targets remain compositions in the same Output
document and members of the broader linked inspection group.

The implementation must preserve the current external behavior:

- SugarSubstitute remains authoritative for selected primary/secondary image,
  divider orientation, and split position;
- moving the divider changes view-session state, not document history;
- the existing comparison chrome remains in place;
- navigation across the reveal uses the same linked inspection state as normal
  composition switching;
- the zoom indicator obtains both effective target scales through
  `CanvasWorkspace.canvasFor(...)`; and
- leaving comparison restores the route selected by
  `OutputCanvasProjection`.

The current implementation uses one QPane comparison view while the workspace
uses two clipped views. That internal difference is acceptable only after
rendered and interaction characterization proves equivalent user-facing
divider, navigation, alignment, and zoom behavior. Entering and leaving reveal
mode must not narrow, clear, or reset the linked state shared by the rest of
the workflow's output compositions.

### Output upstream contract status

All required Output contracts are public and verified upstream. The workspace
accepts a `ResponsiveGridPolicy`, exposes its `ResponsiveGridSnapshot`, and
publishes target activation. Its document reconciliation retires unavailable
target canvases and mounts. `setInspectionGroups(...)` makes linked inspection
explicitly host-owned and presentation-independent. Drag failures and context
gestures retain a stable captured content subject. SugarSubstitute must use
these supported APIs and must not reach into `_surface`, `_canvases`, `_mounts`,
or document resource internals.

## Persistence boundary

SugarSubstitute schema version `"1"` persists:

- application image and mask UUIDs;
- workflow canvas maps and active route hints;
- canonical PNG asset paths; and
- workflow/project ordering and metadata.

It does not persist an editor document graph.

CuteCanvas `.cutecanvas` persistence atomically saves a root composition and
its referenced resource graph. It can preserve retained/off-canvas mask
coverage and other editable structure that a clipped PNG cannot.

For the parity migration:

1. keep SugarSubstitute schema version `"1"` and its PNG assets;
2. reconstruct the Input `CanvasDocument` and identity registry from those
   assets on restore;
3. reconstruct the Output `CanvasDocument` from the output assets admitted by
   the existing projection/lifecycle services;
4. derive batch and scene grid presentations from current Output projection
   state rather than persisted project content;
5. continue saving clipped mask PNGs at the existing application paths; and
6. do not expose `.cutecanvas` files to existing projects.

This deliberately keeps the current flattened persistence boundary. It does
not initially preserve CuteCanvas-only retained/off-canvas authorship across
application restarts. Adding native `.cutecanvas` project persistence is a
later, explicit product/schema feature with its own compatibility design.

CuteCanvas autosave should not write the same masks independently. Its generic
path templating does not know SugarSubstitute workflow/cube/node ownership and
would create dual writers. SugarSubstitute's save controller should remain the
single owner, using CuteCanvas edit signals and the requested public export
contract.

## Execution integration

The current QPane/CuteCanvas work includes a typed `ExecutionRuntime` and
host-supplied `ExecutionBackend`. CuteCanvas receives the shared runtime
through `CanvasDocumentRuntime` in the live SugarSubstitute canvas factory.

The QPane repository's `EXECUTION_NOTES.md` includes an audit of
SugarSubstitute:

- SugarSubstitute already has nineteen bounded named execution lanes;
- it has owner scopes, cancellation, outcome handling, freshness policies,
  Qt delivery, and lifecycle shutdown;
- its common lane boundary does not currently express stable native-thread
  affinity, device routing, or adoption-held exclusive leases; and
- passing the application `TaskSubmitter` directly would duplicate lifecycle
  state and risk executor-inside-executor behavior.

The clean integration is a SugarSubstitute `ExecutionBackend` adapter beneath
QPane's `ExecutionRuntime`:

1. accept the typed QPane job and requirements;
2. map resource, urgency, device, affinity, and exclusivity to a capable
   application lane or the declared QPane fallback;
3. schedule `job.run` exactly once;
4. preserve QPane's job settlement and adoption rules; and
5. keep application/QPane cancellation ownership unambiguous.

This is implemented by `ThreadPoolAdmission` and `CuteCanvasExecutionBackend`.
The former is the physical bounded admission owner shared by an application
lane and an optional QPane host backend; the latter schedules only the public
`ExecutionJob.run` callable. It declares no affinity, exclusivity, or
adoption-held-lease capability, so CuteCanvas's existing QPane-native fallback
continues to own those requirements. Stable-affinity/SAM work therefore never
pretends to be supported by the host lane.

## SAM ownership

SAM now belongs to CuteCanvas, including its service/checkpoint lifecycle.
SugarSubstitute startup warmup imports `cutecanvas.sam.service`, while
preserving its existing scheduling, disabled/deferred behavior, trace
semantics, failure reporting, and tests. The removed QPane SAM bootstrap and
state modules must not regain callers.

This is an internal ownership/name change, not a reason to change startup UI.

## Editable installation and release transition

### Verified local resolution

The following dry run was executed from the SugarSubstitute repository and
completed successfully without modifying the environment:

```powershell
.\.venv\Scripts\python.exe -m pip install --dry-run `
  --editable E:\devprojects\qpane\packages\qpane `
  --editable "E:\devprojects\qpane\packages\cutecanvas[sam]"
```

It resolved editable builds of both current packages, and the existing
SugarSubstitute environment already satisfied their third-party dependencies.

Do not install these editables into the current main development environment
before an implementation branch is prepared. The editable QPane shadows
2.1.1, and the application still imports APIs removed by the split.

### Development dependency shape

The base `requirements.txt` is a release contract. Repository tests require
each direct runtime dependency to have an exact registry pin, so local paths or
`-e` entries do not belong there.

The implementation should use a dedicated development overlay/bootstrap step:

1. install the normal SugarSubstitute requirements;
2. install editable `packages\qpane`;
3. install editable `packages\cutecanvas[sam]`; and
4. validate both imports and resolved distribution paths.

The exact repository mechanism can be chosen during implementation from the
project’s existing environment/bootstrap ownership. It should not weaken the
release requirements contract.

`tools\install_local_canvas_editables.py` is the reproducible development
overlay installer. It installs every non-canvas runtime requirement, overlays
paired editable `qpane` and `cutecanvas[sam]` roots with `--no-deps`, and uses
a fresh interpreter to prove both imports resolve below those roots.

The active SugarSubstitute `.venv` now uses the verified local editable
distributions at `E:\devprojects\qpane\packages\qpane` and
`E:\devprojects\qpane\packages\cutecanvas`. They resolve `qpane` and
`cutecanvas` imports from those source trees, pass `pip check`, and preserve
the split exact-pin release contract in `requirements.txt`. The overlay was
installed with `--no-deps` because CuteCanvas's pre-release metadata retains a
development QPane compatibility range; the local paired worktree is the
intentional development dependency set.

### Release dependency shape

The intended published release contract is:

- exact direct pin `qpane==0.1.1`;
- exact direct pin `cutecanvas[sam]==0.1.1`; and
- CuteCanvas's own compatible QPane bound as a secondary consistency check.

QPane no longer owns `mask` or `sam` extras. Both distributions should be
directly pinned because SugarSubstitute directly imports both.

Release/runtime integration must also update:

- `tests/test_runtime_requirements_contract.py`;
- the release payload dependency assertion;
- launcher and installed-layout import validation, which currently checks
  `qpane` but not `cutecanvas`;
- package version diagnostics; and
- any startup harness expectations that name QPane-owned mask/SAM behavior.

Adding a new visible About-page card for CuteCanvas is not required for the
parity migration. Runtime diagnostics should still record both versions. A
visible dependency card is a separate product/localization decision.

## Target ownership and data flow

```text
WorkflowCanvasState + CanvasSessionBoundary
                 |
                 | authorized Input route and graph bindings
                 v
     Input document adapter + identity registry
                 |
                 v
       CanvasDocument / CanvasViewSession
                 |
                 v
             CuteCanvas
                 |
                 v
                QPane

OutputCanvasProjection + CanvasSessionBoundary
                 |
                 | authorized content, grid targets, and comparison state
                 v
    Output document adapter + identity registry
                 |
                 v
       CanvasDocument / CanvasViewSession
                 |
                 v
           CanvasWorkspace
                 |
                 v
                QPane
```

Both live documents share one host-adapted QPane `ExecutionRuntime`. Each has
its own `CanvasDocumentRuntime`, so document freshness and lifecycle remain
separate while physical capacity is shared. The widgets/workspace do not own
application runtime shutdown; standalone document construction retains
CuteCanvas's ordinary owned-runtime behavior for isolated tools and tests.

## Recommended migration sequence

This order keeps behavior safeguarded and avoids internal compatibility
layers.

### 0. Stabilize the upstream contracts — complete

The local QPane/CuteCanvas worktree implements and verifies all required
public contracts: arbitrary mask export, identity-preserving mask replacement,
responsive policy/snapshot/activation, context and drag subjects, bounded
workspace target retirement, CuteCanvas-owned persistent inspection groups,
and outbound failure forwarding. The full upstream suite passed with 1,369
tests before the later `CanvasInspectionGroup` boundary cleanup; its focused
workspace/inspection regression selection now passes with 9 tests.

The integration must record the exact QPane/CuteCanvas commit when the local
worktree is committed; until then, SugarSubstitute consumes these verified
packages through the editable development overlay only.

### 1. Add characterization coverage

Add or strengthen tests around the current behavior boundary:

- Input composition/image activation across workflow switches;
- image-load/materialization association and UUID preservation;
- blank and loaded mask creation;
- mask restore remapping;
- wrong-size and unverified-mask rejection before mutation;
- Brush and Smart Select pixel results;
- mask edit, undo, redo, dirty tracking, debounce, and save completion;
- flushing multiple dirty inactive masks before generation;
- fail-closed generation when export/save fails;
- document/composition removal only after final workflow reference;
- Output image, source-grid, scene-overview, and empty routes;
- responsive reflow and composition-target activation;
- legacy single-image PNG drag-out and image clipboard behavior;
- per-tile batch/scene drag gesture arbitration and captured target identity;
- per-tile context-menu Copy without route activation;
- canonical-PNG versus companion-JPEG transfer selection;
- memory-only final and live-preview transfer materialization;
- stale/cancelled transfer rejection and staged-artifact cleanup;
- linked pan/zoom continuity while source/set/scene controls switch among
  compositions with equal and unequal native sizes;
- comparison reveal, linked navigation, split, dual-scale zoom indicator, and
  route exit without resetting the broader linked group;
- stale/foreign workflow and generation mutation rejection; and
- warm widget/dock/floating lifecycle.

Existing Input, Output, real-shell, abuse, and host-window tests provide a
large foundation. New tests should assert observable behavior through the
owner rather than reproduce old private QPane call order.

### 2. Integrate execution and editable packages

Status: complete for the development editable overlay and host-runtime
injection. `ThreadPoolAdmission` owns physical bounded capacity;
`CuteCanvasExecutionBackend` adapts its `image_decode` lane to the public CuteCanvas
SDK; process runtime composition owns one QPane runtime; and the live canvas
factory injects it into both document runtimes. Focused tests prove ordinary
execution, synchronous saturation rejection, pending cancellation, distinct
document scopes, and shared host-runtime identity. Package/release diagnostics
and pinned published dependencies remain later release-transition work.

### 3. Build the Input document boundary

Status: complete for image/mask document admission, identity mapping, guarded
route projection, restricted policy, and reference-counted composition
retirement. `InputCanvasDocument` is the only live Input content adapter.

1. introduce a cohesive document/identity registry owned by the Input canvas
   integration;
2. construct one long-lived `CanvasDocument`, runtime, view session, and
   CuteCanvas widget;
3. map cached SugarSubstitute images to compositions/resources/layers;
4. map workflow mask bindings to mask resources/layers;
5. make route projection open the registered composition and activate the
   registered mask;
6. publish a host materialization event after successful registry admission;
7. apply the restricted editor/layer policies; and
8. preserve reference-counted cleanup across workflows.

### 4. Move mask persistence and SAM

Status: complete. Mask persistence uses
`maskUndoStackChanged`, inactive export uses `exportMaskImage`, and external
replacement uses `replaceMaskFromFile`. SAM startup/runtime warmup ownership
now imports CuteCanvas. Real-shell Brush and Smart Select verification remains
part of the final UI matrix.

1. bind dirty tracking to `maskUndoStackChanged`;
2. export arbitrary dirty masks through the new public API;
3. retain the existing debounce and fail-closed generation preflight;
4. keep SugarSubstitute as the sole PNG/path owner;
5. replace existing mask content through the new public operation;
6. move SAM startup/runtime imports to CuteCanvas; and
7. verify Brush and Smart Select end to end in the real shell.

### 5. Build the Output document boundary

Characterization checkpoint: the legacy Output stack requested removed
monolithic QPane `QPaneCatalogImageLayerRequest` APIs. It has now been removed
instead of receiving an upstream compatibility export. The active Output
widget uses only the document-backed workspace path.

1. construct one long-lived Output `CanvasDocument`, document runtime, view
   session, and `CanvasWorkspace`;
2. map every accepted output image to a locked content composition;
3. map the active workflow's ordered output compositions to one stable
   `CanvasInspectionGroup`;
4. map single-image routes and existing navigation controls to workspace
   single presentation without clearing that group;
5. map source grids and scene overviews to ordered workspace grid
   presentations over existing content compositions;
6. retain composition-ID-to-set/source/scene maps and resolve activation
   through the public workspace grid target contract;
7. add the separate output-transfer preference and a shared authorized
   transfer resolver for durable or staged PNG/JPEG artifacts;
8. install its outbound-MIME adapter on the workspace and bind captured
   content-context requests to target-aware `Copy`;
9. map comparison routes to workspace reveal presentation over two group
   members while preserving the broader linked group and host-owned
   split/orientation/zoom chrome state;
10. retire preview, transfer leases, content, linked-group, registry, and
   workspace-view state in
   dependency order; and
11. retain all workflow/session/generation route guards.

### 6. Switch atomically and remove obsolete integration

The constructor/dependency switch should land only when both Input and Output
adapters target the split packages. Then:

1. remove the old `substitute.presentation.canvas.qpane` assumptions and
   fallback shims;
2. remove all private mask manager/controller access;
3. remove old QPane feature and SAM ownership names;
4. update runtime/release/import/version contracts;
5. run focused canvas and execution verification; and
6. run the complete repository format, lint, strict type, parallel test, and
   serial test gates before commit.

#### Output legacy-removal boundary

The remaining Output QPane stack is not a live dependency of the current
`OutputCanvas`, but it still has an internally coherent legacy test/runtime
island. It must be removed atomically rather than bypassed piecemeal:

1. Completed: replace the coordinator's temporary direct route-projector and
   linked-group dependencies with the existing document presentation sink. Its
   characterization harness now mirrors payloads into a document-facing fake;
   it imports neither `OutputRouteProjector` nor `OutputQPaneRouteAdapter`.
2. Completed: remove the synthetic scene/grid builders, reflow controller,
   grid route controller, QPane output adapter/catalog/presenter, and linked
   group presenter together.
3. Completed: retire the legacy composition runtime assembly (`core_runtime`,
   `grid_runtime`, `qt_interaction`, `qt_navigation`, `compare`, `qpane`, and
   their runtime types), the QPane-only pointer controllers, and their
   isolated fixtures/tests.
4. Completed: replace the old broad QPane route-projector port with a narrow
   document comparison route protocol; the application route port no longer
   models synthetic grid, hit, or composition commands.
5. Completed: remove the associated QPane assertions and fake catalog
   fixtures. Current Output characterization observes document membership,
   presentations, linked groups, activation, preview retirement, and reveal
   state through public CuteCanvas APIs.

## Verification matrix

| Concern | Required observed result |
| --- | --- |
| Input route | Active workflow alone controls visible composition/mask |
| Stale safety | Old workflow/revision events cannot change either canvas |
| Identity | SugarSubstitute image UUIDs retain their application meaning |
| Mask binding | Cube/node association resolves to exactly one live mask |
| Mask validation | Wrong/unverified dimensions mutate neither state nor pixels |
| Dirty tracking | Every durable mask edit, undo, and redo schedules persistence |
| Preflight | All dirty masks export/save, including inactive masks; any failure blocks generation |
| Tool policy | Only Pan & Zoom, Brush, and Smart Select are available |
| Base image | Cannot be moved, transformed, painted, reordered, or removed |
| Restore | Existing schema-v1 projects reconstruct equivalent live content |
| Batch/scene reflow | CuteCanvas grid reflows at equivalent breakpoints without DPR gaps, drift, or topology chatter |
| Output target activation | Clicking a grid target resolves to the same source/set/scene meaning through composition identity |
| Drag gesture | Crossing the drag threshold exports the pressed tile and does not activate it on release |
| Transfer default | Existing preferences resolve drag and Copy to canonical PNG |
| JPEG transfer | When companion generation and JPEG transfer are enabled, URL, raw MIME bytes, decoded image data, and preview all represent JPEG |
| Memory-only transfer | Non-persisted finals and live previews stage the configured format and remain consumable for the required native lifetime |
| Tile Copy | Right-click Copy uses the captured batch/scene tile without changing the active route |
| Transfer freshness | Preview replacement, workflow switch, composition removal, cancellation, or teardown cannot publish a stale drag or clipboard payload |
| Linked switching | Existing source/set/scene controls switch compositions while preserving normalized inspection |
| Reveal comparison | Workspace reveal, linked navigation, split, alignment, and dual-scale zoom reporting are observably equivalent without narrowing/resetting the full linked group |
| Preview lifecycle | Final replaces/retires preview exactly as today |
| Lifetime | One warm surface and document per canvas; removed compositions, resources, and target views are reclaimed |
| Runtime | No duplicate scheduling/lifecycle; shutdown leaves no work owners |
| Packaging | Editable dev imports resolve locally; release pins remain exact |

Windows is the actually inspected platform. The repository's normal
cross-platform gates remain required during implementation; this
investigation does not infer Linux or macOS runtime success.

## Principal risks and mitigations

| Risk | Mitigation |
| --- | --- |
| CuteCanvas changes while integration is underway | Pin the integration to an observed commit and re-audit public stubs when updating |
| App/document UUID conflation | Use explicit typed registry records; never infer equivalence |
| Hidden behavior expansion from default editor policy | Apply a restrictive host policy and characterize tools |
| Inactive dirty masks cannot be saved | Resolve arbitrary public export upstream before switching |
| Existing mask IDs are lost on external replacement | Resolve public identity-preserving replacement upstream |
| Independent grid views expose different navigation behavior | Configure an explicit grid-cell inspection/activation policy and characterize it against the current overview |
| Default grid topology differs from current maximum-area/hysteresis policy | Extend the shared responsive policy and verify current tall/wide/square scenarios |
| Workspace hides target hit and layout snapshot behind private surface state | Complete the public grid snapshot and activation contract upstream |
| Grid context/drag code binds to private child widgets | Make presentation-aware content-subject forwarding part of the public workspace grid contract |
| Context-menu callback copies the later active image | Capture and revalidate the document subject when the menu opens |
| JPEG URL and image MIME contain different pixels | Derive raw bytes, decoded image data, and drag preview from one selected transfer artifact |
| Memory-only or failed companion output has no reusable path | Stage the explicitly selected format from authorized current pixels; report encoding failure instead of silently changing format |
| Native consumers outlive a temporary-file callback | Use managed transfer leases plus bounded startup/shutdown cleanup |
| Drag materialization fails without reaching the host | Forward structured failure through CuteCanvas/workspace and route it to SugarSubstitute logging and localized feedback |
| Workspace comparison differs internally from old same-pane comparison | Characterize rendered divider, navigation, alignment, and zoom behavior before the switch |
| Workspace presentation changes clear or narrow the active linked group | Complete a host-owned persistent inspection-group contract upstream |
| Output preview/grid churn retains target widgets | Complete bounded workspace target retirement upstream |
| Duplicate mask writers corrupt canonical assets | Disable/avoid CuteCanvas autosave; keep one host save owner |
| `.cutecanvas` persistence changes project compatibility | Keep schema-v1 PNG persistence for parity |
| Nested execution runtimes duplicate cancellation/state | Adapt the physical backend and schedule `job.run` once |
| Editable QPane breaks current old imports immediately | Install only on the prepared migration branch/environment |

## Decisions established by this investigation

1. SugarSubstitute workflow state is not a CuteCanvas document.
2. SugarSubstitute should own two long-lived CuteCanvas documents: one Input
   document and one Output document.
3. Input images/masks are editable document content; Output images are locked
   content compositions in the separate read-only document.
4. Batch/source grids and scene overviews use a CuteCanvas-owned responsive
   presentation over existing content compositions. The built-in independent
   view grid uses QPane native-tile packing so it retains the established
   gutters and row packing while reflowing responsively. SugarSubstitute no
   longer owns a second grid/reflow engine.
5. Output content compositions form a linked inspection group so the existing
   controls can switch among them without losing the normalized region.
6. Reveal comparison is transient `CanvasWorkspace` presentation state between
   two members of that broader linked group; it does not replace or narrow the
   group.
7. SugarSubstitute needs explicit mappings between application IDs and
   CuteCanvas composition/resource/layer IDs.
8. Existing schema-v1 PNG persistence remains authoritative during the parity
   migration.
9. SugarSubstitute remains the sole mask save/preflight owner.
10. Default CuteCanvas mask-authoring policy is broader than the current
   product and must be restricted.
11. The eight public integration contracts listed in the executive conclusion
    should be fixed upstream before application integration.
12. The editable install is a development overlay; published exact pins remain
    the release contract.
13. QPane/CuteCanvas execution should run through a host `ExecutionBackend`,
    not through a nested application task lifecycle.
14. Native `.cutecanvas` project persistence remains a future product/schema
    change even though both live canvas surfaces use CuteCanvas documents.
15. Output drag and Copy share one SugarSubstitute-owned transfer resolver and
    one preferred-format setting; they do not derive companion paths
    independently.
16. Canonical PNG is the backward-compatible transfer default. Companion JPEG
    is effective only while JPEG generation is enabled, and the stored choice
    survives temporary disablement.
17. Valid memory-only finals and live scene previews are transferable through
    managed staging; lack of a durable path is not a reason to disable a tile.
18. CuteCanvas owns presentation-aware gesture-to-content subject resolution.
    SugarSubstitute owns JPEG policy, output authorization, materialization,
    context-menu contents, and clipboard publication.
19. There are no existing external consumers of the split QPane or CuteCanvas
    APIs. Upstream may make clean breaking API changes for this migration,
    provided every in-repository call site is updated and obsolete surfaces are
    removed rather than preserved as compatibility paths.

## Primary source index

### SugarSubstitute

- `requirements.txt`
- `tools\install_local_canvas_editables.py`
- `substitute\presentation\canvas\AGENTS.md`
- `substitute\domain\workflow\canvas_models.py`
- `substitute\domain\workflow\canvas_session.py`
- `substitute\application\workflows\input_canvas_state_service.py`
- `substitute\application\workflows\workflow_input_canvas_service.py`
- `substitute\presentation\canvas\input\input_canvas_view.py`
- `substitute\presentation\canvas\input\input_document.py`
- `substitute\presentation\canvas\input\input_route_projector.py`
- `substitute\presentation\canvas\input\input_canvas_presenter.py`
- `substitute\presentation\canvas\input\input_mask_save_controller.py`
- `substitute\presentation\canvas\input\input_mask_tool_controller.py`
- `substitute\application\workflows\output_canvas_projection.py`
- `substitute\application\workflows\canvas_image_registry.py`
- `substitute\application\workflows\canvas_io_service.py`
- `substitute\domain\generation\output_preferences.py`
- `substitute\application\generation\output_preference_service.py`
- `substitute\infrastructure\persistence\file_output_preference_repository.py`
- `substitute\infrastructure\execution\thread_pool_admission.py`
- `substitute\infrastructure\execution\cutecanvas_execution_backend.py`
- `substitute\infrastructure\persistence\output_transfer_artifact_store.py`
- `substitute\infrastructure\comfy\output_image_persistence.py`
- `substitute\infrastructure\comfy\jpeg_companion_encoder.py`
- `substitute\presentation\settings\jpeg_companion_settings.py`
- `substitute\presentation\settings\output_transfer_settings.py`
- `substitute\presentation\settings\generation_output_settings_catalog.py`
- `substitute\presentation\canvas\output\output_canvas_asset_lookup.py`
- `substitute\presentation\canvas\output\output_document.py`
- `substitute\presentation\canvas\output\output_transfer_resolver.py`
- `substitute\presentation\canvas\output\output_transfer_payloads.py`
- `substitute\presentation\canvas\output\output_transfer_drag_provider.py`
- `substitute\presentation\canvas\output\output_transfer_composition.py`
- `substitute\presentation\canvas\output\output_transfer_clipboard_controller.py`
- `substitute\presentation\canvas\output\output_transfer_clipboard_publisher.py`
- `substitute\presentation\canvas\output\output_grid_context_menu.py`
- `substitute\presentation\canvas\output\output_transfer_failure_presenter.py`
- `substitute\presentation\canvas\output\output_document_route_projector.py`
- `substitute\presentation\canvas\output\output_document_navigation.py`
- `substitute\presentation\canvas\output\output_document_preview_presenter.py`
- `substitute\presentation\canvas\output\output_projection_content_synchronizer.py`
- `substitute\presentation\canvas\output\output_reveal_zoom_indicator.py`
- `substitute\presentation\canvas\output\output_canvas_context_menu_controller.py`
- `substitute\infrastructure\onboarding\launcher_managed_runtime_provisioner.py`
- `tests\test_runtime_requirements_contract.py`
- `tests\test_release_payload_builder.py`
- `tests\test_output_canvas_document.py`
- `tests\test_canvas_execution_integration.py`
- `tests\test_cutecanvas_execution_backend.py`
- `tests\test_output_canvas_host_contract.py`
- `tests\test_output_compare_presenter.py`
- `tests\test_output_organization.py`
- `tests\test_output_transfer_artifact_store.py`
- `tests\test_output_transfer_resolver.py`
- `tests\test_output_transfer_payloads.py`
- `tests\test_output_transfer_drag_provider.py`
- `tests\test_output_transfer_composition.py`
- `tests\test_output_transfer_clipboard_controller.py`
- `tests\test_output_transfer_context_menu.py`
- `tests\test_settings_integrated_workspace.py`
- `tests\test_real_shell_output_canvas_scenarios.py`

### QPane/CuteCanvas

- `E:\devprojects\qpane\AGENTS.md`
- `E:\devprojects\qpane\packages\qpane\AGENTS.md`
- `E:\devprojects\qpane\packages\cutecanvas\AGENTS.md`
- `E:\devprojects\qpane\packages\qpane\pyproject.toml`
- `E:\devprojects\qpane\packages\cutecanvas\pyproject.toml`
- `E:\devprojects\qpane\requirements-dev.txt`
- `E:\devprojects\qpane\EXECUTION_NOTES.md`
- `E:\devprojects\qpane\packages\qpane\src\qpane\viewer.py`
- `E:\devprojects\qpane\packages\qpane\src\qpane\qpane.pyi`
- `E:\devprojects\qpane\packages\qpane\src\qpane\rendering\sdk.py`
- `E:\devprojects\qpane\packages\qpane\src\qpane\rendering\presenter.py`
- `E:\devprojects\qpane\packages\qpane\src\qpane\layout\grid.py`
- `E:\devprojects\qpane\packages\qpane\src\qpane\sdk\layout.py`
- `E:\devprojects\qpane\packages\qpane\src\qpane\ui\outbound_drag.py`
- `E:\devprojects\qpane\packages\qpane\src\qpane\interaction\navigation_tool.py`
- `E:\devprojects\qpane\packages\qpane\tests\test_outbound_drag.py`
- `E:\devprojects\qpane\packages\qpane\tests\test_responsive_layout.py`
- `E:\devprojects\qpane\packages\cutecanvas\src\cutecanvas\cutecanvas.pyi`
- `E:\devprojects\qpane\packages\cutecanvas\src\cutecanvas\__init__.pyi`
- `E:\devprojects\qpane\packages\cutecanvas\src\cutecanvas\canvas.pyi`
- `E:\devprojects\qpane\packages\cutecanvas\src\cutecanvas\canvas.py`
- `E:\devprojects\qpane\packages\cutecanvas\src\cutecanvas\document\document.py`
- `E:\devprojects\qpane\packages\cutecanvas\src\cutecanvas\document\inspection.py`
- `E:\devprojects\qpane\packages\cutecanvas\src\cutecanvas\runtime\document_runtime.py`
- `E:\devprojects\qpane\packages\cutecanvas\src\cutecanvas\runtime\lifecycle.py`
- `E:\devprojects\qpane\packages\cutecanvas\src\cutecanvas\masks\workflow.py`
- `E:\devprojects\qpane\packages\cutecanvas\src\cutecanvas\masks\autosave.py`
- `E:\devprojects\qpane\packages\cutecanvas\src\cutecanvas\document\session.py`
- `E:\devprojects\qpane\packages\cutecanvas\src\cutecanvas\presentation\contracts.py`
- `E:\devprojects\qpane\packages\cutecanvas\src\cutecanvas\presentation\surfaces.py`
- `E:\devprojects\qpane\packages\cutecanvas\src\cutecanvas\presentation\workspace.py`
- `E:\devprojects\qpane\packages\cutecanvas\src\cutecanvas\facade\drag_api.py`
- `E:\devprojects\qpane\packages\qpane\docs\integration-sdk.md`
- `E:\devprojects\qpane\packages\cutecanvas\docs\documents-and-presentations.md`
- `E:\devprojects\qpane\packages\cutecanvas\docs\scenes.md`
- `E:\devprojects\qpane\packages\cutecanvas\docs\host-cookbook.md`
