# AGENTS.md

## Mission Statement

This project exists to provide a high-quality PySide6 frontend for ComfyUI with excellent usability, reliability, and maintainability.
Engineering priority is strict architecture, strong separation of concerns, behavior safety during structural change, and long-term developer velocity.

## Purpose

- This file defines engineering guardrails for this repository.
- This file governs architecture, code quality, typing, testing, observability, and safety.
- Do not use this file for feature specs or product planning.

## Behavior Boundary

- Preserve existing user-facing behavior unless explicitly approved to change.
- Preserve compatibility for persisted files and project data unless explicitly approved to change.
- Treat current behavior and persisted formats as the contract; change internals freely within that boundary.

## Cache Architecture and Governance

- Classify stored or retained data before implementation as persistent cache,
  process-lifetime memoization, or authoritative application/user state.
- Register every persistent cache in the authoritative application cache
  catalog. The catalog owns persistent cache identifiers, storage namespaces,
  compatibility inputs, retention, recovery, and invalidation policy.
- Obtain persistent cache storage through the prepared catalog namespace. Do
  not construct persistent cache paths directly from an installation cache
  root or create cache-owned directories during general installation setup.
- Give each persistent cache one non-overlapping namespace and one cohesive
  domain owner. Split caches whose records have independent compatibility,
  retention, or lifecycle requirements instead of coordinating them through a
  shared incidental directory.
- Declare storage schema, semantic producer inputs, relevant runtime or asset
  dependencies, entry-level freshness rules, and an emergency compatibility
  epoch. An application version alone is not a cache compatibility input.
- Invalidate only the incompatible cache owner. Preserve compatible cache
  generations across releases and development branch changes, and bound old
  generations through explicit age, count, or size retention.
- Treat unreadable, corrupt, incomplete, or incompatible cache data as an
  observable cache miss. Quarantine or replace it safely; a disposable cache
  must not abort application startup or permit stale data to be read.
- Never register preferences, sessions, projects, outputs, user-authored
  artifacts, trust state, or other authoritative state as cache. Cache cleanup
  must remain incapable of deleting authoritative data.
- Keep process-only memoization with its runtime owner. It does not receive a
  persistent namespace, but it must still define input identity and explicit
  invalidation where stale reuse is possible.
- Add or change a persistent cache atomically with its catalog registration,
  compatibility and recovery behavior, structured diagnostics, architecture
  enforcement, and tests for reuse, relevant and unrelated changes,
  corruption, upgrade, and cross-platform path safety.
- Unknown cache-root content is not proof of ownership. Report it and leave it
  intact until a verified migration identifies its producer and safe
  disposition.

## Localization Policy

- Route all SugarSubstitute-owned user-facing text, including installer text, through its explicit localization owner. Hard-coded visible copy is not allowed.
- Treat `languages.json` as the sole supported-locale registry. Do not duplicate locale inventories in source, tools, or tests.
- Every release-enabled locale must have complete application and installer coverage. Add or change owned text and all supported translations atomically; add a locale only with complete coverage for every owned surface.
- When one source string is intentionally shared or repeated, update every matching occurrence and catalog entry together. Do not leave inconsistent near-duplicates for later cleanup.
- English is the canonical source and fallback language. Write translations directly and do not use external translation aids.
- Every release-enabled non-English locale in `languages.json` must have a complete `README.<language-id>.md`, and every README language selector must list the full release-enabled set. Treat `README.md` as the authority for README facts, voice, tone, and style. Any change to it must update every localized README in the same change. Keep each version complete and factually aligned, but localize the writing so it creates the same experience for its readers; a mechanical translation is not sufficient.
- Preserve cube-authored and user-authored text exactly. Resolve eligible ComfyUI-owned node text from the connected ComfyUI server and never maintain a parallel local ComfyUI corpus.
- Preserve Unicode and IME input, widget behavior, styling, and layout across locales. A localization change that regresses text entry or presentation behavior is a failure.
- Keep the source-ownership and absolute-coverage gates strict. Fix violations at their owner; do not weaken extraction, parity, completion, or runtime-catalog checks to pass CI.

## Environment and Gate Execution

- All verification commands must run against the repository virtual environment at `.venv`.
- Do not run quality gates with global/system Python.
- If `.venv` is missing or stale, recreate it with a supported Python version
  and install `requirements-toolchain.txt`.
- Run all commands from the repository root using the platform-appropriate
  shell and the repository virtual environment's Python interpreter.

### Required gate commands

The commands below assume the repository virtual environment is active or that
`python` otherwise resolves to its interpreter.

- Focused tests: `python -m pytest -n auto -q <paths>`
- Full parallel tests: `python -m pytest -n auto -q -m "not serial"`
- Full serial tests: `python -m tools.ci.run_serial_test_modules --junit-dir=build/test-results/local-serial`
- Architecture: `python -m tools.check_architecture`
- Lint: `python -m ruff check .`
- Format: `python -m ruff format .`
- Type check: `python -m mypy --strict substitute tests`

## Core Engineering Principles

- Use strict object-oriented design.
- Enforce strong separation of concerns as the primary architecture objective.
- Keep modules cohesive and boundaries explicit.
- Assign one authoritative owner per concern; other components may participate,
  but must derive their behavior, state, and geometry from that owner rather
  than re-implementing the concern in parallel.
- Before extending a module, class, subsystem, or workflow, identify its
  concern, authoritative state owner, dependency direction, public boundary,
  behavior and performance contracts, and change cadence.
- Reassess ownership before extending an existing structure. If a change
  introduces a distinct responsibility, change cadence, lifecycle, or
  collaboration boundary, extract it as part of the same change.
- Prefer clean replacement over compatibility layers in internal code.
- Structural changes must be complete: update callsites, remove dead code, remove temporary bridges.
- Favor DRY when it reduces repeated change risk.
- Avoid abstractions that hide intent.

## Architecture Rules

- Organize code into clear layers with one-way dependencies.
- UI/Presentation layer: widgets, view composition, Qt-specific interaction.
- Application/Orchestration layer: use-case coordination, workflow orchestration, lifecycle control.
- Domain layer: core models, business rules, visibility/activation/policy logic, pure logic where possible.
- Infrastructure/Adapter layer: filesystem, network, subprocess, Comfy integration, plugin/custom-node operations.
- Higher-level layers may depend on lower-level layers; lower-level layers must not depend on higher-level layers.
- Keep Qt types out of domain logic whenever feasible.
- Place code by ownership and dependency direction, not convenience or proximity.
- Avoid god classes and monolithic files; split by responsibility, not by convenience.

DRY means single ownership, not merely fewer lines. Consumers may observe,
delegate, adapt, or cache derived results, but must not reproduce authoritative
rules or state.

## Structural Change Rules

- For behavior-critical areas, work in two steps:
  1. Add characterization/regression tests for existing behavior.
  2. Perform structural changes behind those tests.
- Do not start structural changes in an area without behavior safeguards for that area.
- When a behavior spans multiple components, trace the current ownership and data flow before editing; prefer correcting the ownership model over layering compensating patches across consumers.
- Prefer vertical slices that land safely over large unverified rewrites.
- If behavior changes are intentional, they must be explicitly called out and tested as new behavior.
- Current module layout does not constrain improvement; reorganize freely when it improves architecture.
- Align touched modules with the ownership and dependency rules in this file.

Do not add behavior to a mixed-responsibility file. If existing code touched by
the work mixes responsibilities:

1. Characterize the existing behavior with tests.
2. Identify the authoritative owners.
3. Extract each touched responsibility into cohesive, focused files.
4. Migrate every caller completely.
5. Remove replaced code and temporary bridges.
6. Verify behavior and the resulting ownership boundaries.

Do not defer this blast-area work, hide it behind a forwarding shim, move lines
into a generic dumping ground, or duplicate ownership during the migration. A
structural waiver can exempt a justified size gate; it never authorizes mixed
ownership or new behavior in a mixed file.

## Architecture Governance

`ARCHITECTURE_POLICY.toml` defines the enforced authored-runtime scope. The
structural soft ceiling is 350 nonblank, noncomment lines and the hard gate is
500. Generated Qt resource modules are exact policy exclusions because their
shape is owned by the resource compiler. File size is an ownership alarm, not
proof that a file is mixed or cohesive.

The current repository has two explicit state mechanisms:

- `ARCHITECTURE_DEBT.toml` records assessed current mixed ownership. Each debt
  names the owner, exact paths and fingerprint, distinct responsibilities,
  tracking issue, review date, and next extraction. It is a current-state
  snapshot, not a historical ledger.
- `ARCHITECTURE_WAIVERS.toml` records exact, bounded hard-gate exceptions. A
  `structural` waiver is reserved for a genuinely cohesive owner whose size is
  justified. A `remediation` waiver must link assessed debt, cap the current
  line count, and name a lower next limit.

A structural waiver is exceptional, not the default disposition for an
existing large file. It requires a source-level review and a file-specific
rationale that:

- names the concrete authoritative state, contract, algorithm, or mounted
  control;
- identifies the operations and invariants that require the contents to change
  together;
- explains why a plausible extraction would divide authority, duplicate an
  invariant, or fragment one atomic contract; and
- distinguishes supporting private parts from independently changing
  collaborators.

A module docstring, one broad feature theme, one large class, or the fact that
code currently lives together is not evidence of cohesion. When independent
change cadences, lifecycles, policies, adapters, projections, or reusable
collaborators are present, record debt and a concrete next extraction. The
checker validates registry completeness and bounds; it cannot make this human
architectural judgment.

Every file above the hard gate must receive an explicit ownership assessment.
There is no legacy, grandfathered, frozen, or unassessed exception. After a
change, reassess the file and choose the truthful current state: reduce it below
the hard gate, record updated debt with a tightening remediation waiver, or
justify a structural waiver for one cohesive owner. Delete resolved and unused
records. Debt and waivers expire; raising a limit or extending a review date
solely to pass the gate is prohibited. Every waiver limit must equal the exact
current production line count, so any growth forces a new source-level review.

Run `python -m tools.check_architecture` after changing authored runtime
structure or architecture state. The checker runs in pre-commit and CI and
rejects new hard-gate overages, stale fingerprints, expired records, unbounded
remediation, invalid links, duplicate dispositions, and unused waivers.

## Code Organization and Readability

- Write self-documenting code with expressive, concise names.
- Place new code deliberately in the module where it naturally belongs.
- Keep files intentionally organized so reading order reflects design intent.
- Keep source files focused on one coherent responsibility and one primary
  reason to change.
- Split mixed-concern files as part of the change that exposes the mixed
  concern. Adding behavior to a broad mixed file because it is nearby is not
  allowed.
- Do not place code opportunistically "where it works".
- Remove obsolete code paths when replacements are complete.

## Docstrings and Comments

- Docstrings are mandatory for all new and changed modules, classes, functions, and methods.
- Use concise imperative docstrings for simple logic.
- Use Google-style docstrings for complex logic.
- Docstrings must explain rationale, constraints, and intent.
- Docstrings must not restate obvious mechanics.
- Inline comments are allowed only for non-obvious behavior, invariants, edge cases, or external constraints.

## Documentation Policy

- Do not create new docs files (README variants, design docs, ADRs, notes) unless explicitly requested by the maintainer.
- Required context should live in code, type hints, tests, and docstrings.

## Third-Party Vendoring Policy

- When vendoring third-party source, assets, icons, models, datasets, or generated derivatives, update `third_party/manifest.toml` in the same change.
- Store third-party license text under `third_party/licenses/` and reference it from the manifest.
- Add or update `third_party/NOTICE.md` when a new third-party component is introduced.
- Record source repository, source path when applicable, license, and vendored runtime file paths.
- Keep runtime assets in the package/resource location owned by the application code that consumes them; keep licensing and provenance centralized under `third_party/`.

## Typing Policy

- Strong typing is required for all new code.
- Modified code must be typed as part of the change.
- Type hints are mandatory on function signatures and key internal state.
- Type narrowing and explicit domain types are preferred over `Any`.
- Run `mypy --strict` for type verification.
- Temporary typing relaxations are allowed only if explicitly justified inline and tracked for removal.

## Logging, Errors, and Observability

- Observability is mandatory.
- Use structured, actionable logging with context identifiers where relevant.
- Include enough context to diagnose failures quickly (workflow ID, cube alias, node name, prompt ID, path, operation).
- Use log levels consistently (`debug`, `info`, `warning`, `error`).
- Preserve exception context and stack traces for unexpected failures.
- `print` is not allowed for runtime diagnostics.
- Bare `except:` is not allowed.
- `except Exception` must be narrow, intentional, and log context plus failure reason.
- Silent exception swallowing is not allowed.

## Desktop Security and Safety Rules

- Treat cubepak loading, trust decisions, custom-node installation, subprocess execution, and network access as security-sensitive.
- Never execute untrusted code paths without explicit trust checks.
- Validate and sanitize external paths and user-provided file references.
- Use subprocess argument lists, never shell-string execution.
- Set explicit timeouts for network operations.
- Fail closed when trust or validation is uncertain.
- Never log secrets, tokens, credentials, or sensitive local paths beyond what is necessary for diagnosis.

## Testing Policy

- Treat Windows, Linux, and macOS as first-class supported platforms.
- Tests are cross-platform by default. Use `@pytest.mark.platforms(...)` only when behavior genuinely depends on the host operating system.
- Never add a platform exclusion merely to suppress a failure. Fix portable behavior and portable assertions instead.
- Add or update tests for every behavior change and every bug fix.
- Add characterization tests before structural changes to behavior-critical areas.
- New behavior must not be unverified.
- Test observable behavior through the component that owns it. Avoid coupling tests to private helpers, incidental call order, or implementation details.
- Include success, failure, boundary, and regression coverage.
- Keep tests deterministic, isolated, order-independent, and safe for repeated execution.
- Control clocks, randomness, environment variables, filesystem state, subprocesses, and network boundaries when they affect test results.
- Use `tmp_path` and `pathlib.Path`. Portable tests must not assume drive letters, path separators, case sensitivity, permission models, executable bits, or process behavior.
- When native operating-system behavior is the subject of a test, exercise the real native behavior and mark the applicable platforms explicitly.
- Prefer real application components over mocks. Mock or fake external boundaries, not the behavior being tested.
- Qt tests must wait for observable signals or state transitions with bounded timeouts. Do not use arbitrary sleeps or assume queued work completes immediately.
- Qt tests must clean up widgets, timers, threads, subprocesses, and event-loop work they create.
- Assert semantic state and relationships. Exact font metrics, pixel geometry, and rendering details belong in controlled rendering harnesses.
- UI-critical behavior must have automated coverage where technically feasible.
- Do not weaken assertions, add retries, skip tests, or serialize tests to conceal nondeterminism.

### Test Classification

- Use `@pytest.mark.platforms(...)` for individual platform-specific tests.
- Use a module-level platform marker when every test in that module has the same applicability.
- Use `PLATFORM_TEST_MODULES` only when unsupported platform imports prevent the module from being collected.
- Tests are parallel-safe by default.
- Add a module to `SERIAL_TEST_MODULES` only for a demonstrated native Qt, process, or resource-isolation constraint.
- Document non-obvious platform and serial classifications in `tests/ci_test_policy.py`.

### Prompt Editor Harness

- Use the real-shell prompt editor harness for prompt editor and editor panel behavior debugging: `tests/real_shell_prompt_editor_harness.py`.
- Prefer harness owner-state diagnostics over screenshots. The harness mounts the production prompt editor through the real shell/editor panel path and captures autocomplete, projection, caret, selection, scroll, popup, paint/cache, undo, and transient-overlay state.
- Add or expand deterministic real-shell scenarios in `tests/test_real_shell_prompt_editor_autocomplete_scenarios.py` and invariant coverage in `tests/test_real_shell_prompt_editor_harness.py` whenever a prompt editor bug exposes a new failure class.
- Expand the seeded abuse actions and invariants when debugging editor panel behavior that the harness cannot yet explain. The harness is expected to grow with newly discovered editor failure modes rather than being bypassed.

### Toolbar Rendering Harness

- Use the rendered toolbar harness for workflow chrome toolbar layout debugging: `tests/test_toolbar_rendering_harness.py`.
- Prefer this harness over screenshots or hand-built widget rows for toolbar geometry bugs. It mounts the production `build_main_window_menu()` toolbar, drives the real `GlobalOverridesManager.rebuild_active_override_controls()` path, and verifies settings search centering, override packing, restart advisory alignment, width-starved behavior, and cached-control recompaction.
- Add or expand rendered toolbar scenarios whenever toolbar chrome, global overrides, settings search, or pending-restart indicators expose a new layout failure class.

## Test Execution Rules

- Run local tests against the repository `.venv`.
- Run focused tests continuously during development.
- Before ending a normal implementation turn, run tests covering the changed behavior and its blast area, plus targeted formatting, lint, and strict typing checks for changed files.
- Report the checks run and state when full commit gates remain pending.
- A documentation-only change modifies Markdown (`*.md`) files and nothing
  else. Review its rendered content and diff, run `git diff --check`, and run
  any documentation-specific validator that governs the changed files.
  Documentation-only commits do not require the repository format, lint,
  type, or test gates. A push whose complete changed-file set is
  documentation-only may proceed without CI; automatic push and pull-request
  workflows must ignore it.
- A commit containing any non-Markdown file is not documentation-only,
  including changes to workflows, dependency or release metadata,
  architecture registries, scripts, tests, resources, or generated artifacts.
  Run the complete repository format, lint, strict type, parallel test, and
  serial test gates before committing it, not merely because a turn is ending.
- Full-gate results remain valid for the exact commit-relevant worktree they verified and may be reused if that content has not changed. Staging, unstaging, and ignored verification artifacts do not invalidate them.
- After a commit-relevant change, rerun every affected gate; rerun all gates when impact is uncertain.
- CI must run the complete applicable suite on Windows, Linux, and macOS for
  every change that is not documentation-only.
- Report which platforms were actually verified; do not infer cross-platform success from one operating system.
- Failing and flaky applicable tests are blocking.

## Python Toolchain

- Formatter: `ruff format`
- Linter: `ruff check`
- Type checker: `mypy --strict`
- Test runner: `pytest -n auto -q`

## Verification Workflow

- Run focused checks continuously while implementing.
- Verify the specific reported behavior directly when feasible; do not declare a UI or interaction issue fixed from code inspection alone.
- Use focused blast-area verification for normal turn completion and full repository gates for commit readiness.
- Distinguish observed results from inferred results in updates and completion reports.
- Do not introduce new lint/type failures in modified files.
- Do not report completion when an applicable focused gate fails; do not commit when any full gate fails or remains incomplete.
- If a gate is intentionally deferred, explicitly state the reason and risk.

## Definition of Done

- Behavior safeguarded by tests.
- New/modified code follows architecture boundaries.
- New/modified code placement reflects ownership and dependency rules in this file.
- New/modified code is typed.
- Required docstrings are present and meaningful.
- Logging/error handling is actionable.
- A normal implementation handoff has passing focused tests and targeted format, lint, and strict typing checks for the blast area.
- Architecture governance passes for the exact current source and registry state.
- A non-documentation-only commit has passing full repository format, lint,
  strict typing, parallel test, and serial test gates for its exact contents.
- A documentation-only commit has an inspected diff, clean `git diff --check`,
  and passing applicable documentation-specific validation.

## Commit Policy

- Commit only when explicitly asked. Each commit must deliver one coherent
  user- or integrator-meaningful outcome and be independently releasable.
- Commit subjects feed generated changelogs. Use
  `type(scope): changelog-ready outcome`, with the scope naming the primary
  product or repository concern.
- `feat`, `fix`, and `perf` subjects must describe the delivered capability,
  corrected behavior, or measurable improvement in audience-facing product
  language. A changelog reader must be able to understand the outcome without
  knowing the affected files, classes, adapters, internal architecture, or
  implementation technique.
- Use `refactor`, `test`, `docs`, `build`, `ci`, or `chore` only for a coherent
  internal outcome. Choose the type according to the actual release impact; do
  not present internal maintenance as a user-facing feature or bug fix.
- Include supporting tests, documentation, cleanup, and refactoring in the
  outcome commit they support. Do not create WIP, checkpoint, miscellaneous,
  mechanical file-movement, or implementation-diary commits.
- Mark a public breaking change with `!`. Explain its compatibility impact and
  migration path in the commit body.
- Use the commit body when the subject cannot carry essential context. Explain
  why the outcome matters, its behavioral constraints, and coordinated product
  effects rather than listing implementation steps.

## Maintainer Authority

- Maintainer instructions override this file.
- If constraints conflict, pause and ask for maintainer direction before proceeding.
