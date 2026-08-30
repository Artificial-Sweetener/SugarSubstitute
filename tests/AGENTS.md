# AGENTS.md

## Mission Statement

The SugarSubstitute test suite exists to provide fast, deterministic, and
behaviorally meaningful evidence that the application remains correct across
Windows, Linux, and macOS.

Engineering priority is strong behavioral proof, capability-aligned ownership,
parallel-safe execution, reproducibility, and efficient developer feedback.

## Purpose and Scope

- This file supplements the repository-root `AGENTS.md` for every file below
  `tests/`.
- The repository-root engineering, architecture, typing, documentation, and
  verification rules remain in force.
- This file governs test placement, test strength, execution isolation,
  determinism, runtime efficiency, fixtures, harnesses, and test-suite changes.
- `TEST_POLICY.toml`, `TEST_DEBT.toml`, and `TEST_WAIVERS.toml` are the
  authoritative machine-enforced current state for test-layout and execution
  review candidates.
- Existing noncompliant tests are migration work, not precedent for new or
  modified tests.

## Test Ownership and Placement

- Organize tests first by the product capability or authoritative owner they
  verify, then by test level when a capability needs multiple levels.
- Do not add new test modules directly under `tests/`. The root is reserved for
  shared configuration, test policy, and existing modules awaiting migration.
- Place cross-cutting architecture, localization, packaging, release, and
  repository-policy tests under explicit cross-cutting owners rather than a
  generic utility directory.
- Keep capability-specific fixtures, builders, fakes, and harness support with
  that capability. Promote support to `tests/support/` only when several
  independent capabilities share the same stable testing contract.
- Do not create generic `helpers`, `misc`, `common`, or `utils` dumping grounds.
- Split test modules by the behavior owner and reason to change. A production
  feature name alone does not justify combining unrelated contracts, adapters,
  UI surfaces, failure modes, and system scenarios in one file.
- When moving or splitting tests, update every affected policy entry, runner,
  test-governance record, harness import, and targeted-test command in the same
  change. Remove obsolete paths and compatibility shims.

## Behavioral Proof

- State the observable behavior, invariant, or failure mode each test proves.
- Exercise behavior through the component that authoritatively owns it.
- Prefer the lightest real component that can prove the complete contract. Do
  not mount the application shell when a domain, application, adapter, or
  focused presentation component owns the behavior.
- Use real owner components and real value objects. Fake external boundaries
  such as networks, clocks, subprocesses, filesystems, and remote services.
- Do not mock the behavior under test or reproduce production rules inside a
  fake expected-result implementation.
- Assert semantic outcomes, relationships, lifecycle transitions, published
  events, and externally visible side effects. Avoid incidental call order,
  private storage shape, and implementation-only helper calls.
- Include relevant success, failure, boundary, cancellation, cleanup, and
  regression cases.
- A system or real-shell test must prove composition or interaction that a
  lower-level owner test cannot prove. Do not use it as a substitute for
  focused owner coverage.
- Test count and line coverage are not evidence of test strength. Preserve the
  meaningful contracts and failure sensitivity when consolidating or
  optimizing tests.

## Parallelism and Execution Isolation

- Parallel-safe execution is the default and required design target.
- Do not skip, alter, or weaken behavior based on `PYTEST_XDIST_WORKER`.
- Do not serialize a test to conceal nondeterminism, leaked state, unsafe
  cleanup, fixed resource names, or an unexplained native crash.
- Distinguish these constraints explicitly:
  - fresh-process isolation;
  - bounded Qt worker concurrency;
  - exclusive access to one named external resource;
  - platform-specific native behavior;
  - genuine global serial execution.
- Fresh-process isolation does not by itself require global serialization.
  Isolated tests should remain eligible to run concurrently when they do not
  share an exclusive resource.
- A serial classification requires a demonstrated constraint and a concise
  explanation naming the exact native, process-global, or external resource
  that cannot safely overlap.
- Run `python -m tools.check_test_governance` after changing test placement,
  serial policy, process isolation, real-time behavior, or shared resources.
- Do not serialize an entire mixed module because one test is unsafe. Move the
  constrained test into a cohesive, narrowly scoped module when the current
  execution policy operates at module granularity.
- Use dynamically allocated ports, worker-specific directories, unique object
  names, and per-test state. Never rely on a fixed port, repository-global
  scratch path, shared current working directory, or another worker's state.
- Validate parallel safety by running affected tests repeatedly with xdist and
  with different worker counts when the change touches concurrency, Qt,
  processes, or shared resources.

## Determinism and Time

- Control clocks, timers, schedulers, randomness, environment variables,
  process completion, and network responses whenever they affect behavior.
- Do not use `time.sleep()`, `QTest.qWait()`, or repeated event pumping to wait
  for an observable condition.
- Wait for a signal, event, barrier, future, process state, or semantic
  predicate with a bounded failure timeout.
- A timeout is a safety bound for failure diagnosis, not the success condition
  being tested. Size safety bounds for slower supported CI environments.
- Do not assert general functional correctness using wall-clock duration.
  Prove nonblocking behavior with controlled barriers, owner-thread evidence,
  queued completion, or observable responsiveness.
- Keep real elapsed-time thresholds in an explicit performance or
  qualification test running under a controlled measurement policy.
- Drive debounce, retry, timeout, and animation behavior with injected clocks
  or controllable schedulers when technically possible.
- An intentional real-time wait requires the passage of time itself to be the
  subject of the test and must explain why a deterministic clock or completion
  signal cannot prove the same contract.
- Never increase a delay, timeout, or retry count merely to suppress a flaky
  failure.

## Runtime Efficiency

- Treat test runtime, collection cost, setup cost, teardown cost, and process
  startup cost as engineering constraints.
- Optimize tests only while preserving or strengthening their behavioral
  substance and failure sensitivity.
- Avoid reconstructing the full application, real shell, large workflow, or
  native rendering stack for behavior owned by a smaller component.
- Share expensive immutable setup within a worker when its identity is stable
  and reuse cannot leak mutable state between tests.
- Keep mutable application, Qt, filesystem, environment, and process state
  isolated per test unless the shared lifecycle is itself under test.
- Prefer explicit parameterization for input variants that prove the same
  contract. Do not copy setup and execution solely to change test data.
- Consolidate duplicate proof, but keep materially different failure modes and
  ownership boundaries explicit.
- Fail quickly after the relevant condition becomes impossible. Do not consume
  the full timeout after an observable terminal failure.
- Keep focused owner tests fast enough for continuous local execution. Reserve
  real-shell, external-process, rendering, installer, and performance work for
  the narrow suites that require those boundaries.
- Measure before and after optimizing a test path. Report wall time together
  with any changes to isolation, worker use, setup reuse, or behavioral scope.

## Fixtures and Test State

- Give each fixture one cohesive lifecycle and one clear owner.
- Prefer fixtures that return explicit typed objects over fixtures that mutate
  implicit module or process state.
- Use the narrowest fixture scope compatible with isolation. Broader scope is
  justified only for immutable or deliberately shared state.
- Keep autouse fixtures limited to universal safety and cleanup invariants.
  Capability behavior and setup must remain explicit at the test callsite.
- Restore environment variables, module replacements, logging handlers,
  registries, current directories, locale state, and global settings after use.
- Do not depend on test order or on another test having initialized or cleaned
  shared state.
- Use `tmp_path` and `pathlib.Path` for filesystem behavior. Do not write test
  artifacts into the repository unless an explicit harness artifact path is
  the subject of the test.
- Create subprocesses with argument lists, bounded waits, captured diagnostics,
  and guaranteed termination in teardown.

## Qt and Native UI Tests

- Use one clearly owned `QApplication` lifecycle per test process.
- Wait for observable Qt signals or semantic widget state with bounded
  timeouts. Do not assume queued work completes after an arbitrary number of
  event-loop cycles.
- Clean up widgets, menus, popups, animations, timers, threads, clipboard
  changes, posted events, and native resources created by the test.
- Use focused widget or presenter tests for component-owned behavior. Use a
  real-shell harness only for shell composition, routing, native interaction,
  or cross-component behavior that requires the mounted shell.
- Exact pixels, font metrics, paint output, and geometry belong in controlled
  rendering harnesses with explicit environmental assumptions.
- Native input, IME, clipboard, drag, windowing, and accessibility behavior
  should exercise the real native boundary on the applicable platforms.

## Flake Prevention and Diagnosis

- A flaky test is a blocking defect in either the test, the product, or the
  execution boundary.
- Do not add retries, probabilistic assertions, order dependencies, broad
  exception handling, skips, or serial classifications to hide a flake.
- Reproduce suspected flakes with recorded seeds, repeated execution,
  different worker counts, and the applicable supported platforms.
- Capture enough diagnostics to identify the owner state, active operation,
  relevant identifiers, pending asynchronous work, and cleanup status.
- Replace race timing with barriers, events, signals, or controlled schedulers.
  Do not infer ordering from elapsed time.
- When a flake exposes a new failure class, add deterministic regression
  coverage for that class rather than retaining a stress-only reproduction.

## Typing and Test Maintainability

- Type test functions, fixtures, fakes, builders, and harness APIs under the
  repository strict typing policy.
- Do not add `.pyi` files or module-level `Any` fallbacks that shadow test
  modules and remove them from strict type checking.
- Use explicit protocols or small typed fakes for external boundaries. Avoid
  broad `Any`, unstructured `SimpleNamespace` graphs, and dynamic attribute
  bags when a stable contract is known.
- Keep assertions and setup readable at the test callsite. Shared abstractions
  must reduce repeated change risk without hiding the behavior being proved.
- Use comments only for non-obvious platform, lifecycle, concurrency, or
  external constraints.

## Targeted Verification

- Keep test paths aligned with capability ownership so a capability directory
  forms a meaningful focused suite.
- Add or update focused tests at the authoritative owner before relying on a
  broader integration or system suite.
- Run the changed capability's focused tests continuously during development.
- Include direct dependents, cross-cutting contracts, and composition tests in
  the blast area when the changed boundary affects them.
- Treat an unmapped, shared, or cross-cutting change conservatively and widen
  verification rather than claiming narrow proof.
- Targeted verification improves feedback time; it does not replace the full
  applicable parallel and isolated/serial gates required for commit readiness.

## Test Refactoring and Optimization

Before changing the structure or execution of an existing test:

1. Identify the exact behavior owner, assertions, failure modes, and
   environmental boundary currently covered.
2. Determine whether the current test needs its mounted components, real time,
   process isolation, platform restriction, and execution classification.
3. Add missing characterization where the existing behavioral proof is
   unclear.
4. Move the proof to the lightest complete owner boundary, preserving required
   integration or system coverage for composition behavior.
5. Remove obsolete tests, fixtures, helpers, policy entries, and execution
   exceptions after every caller has migrated.
6. Run the focused suite repeatedly in its intended parallel configuration and
   verify cleanup and order independence.
7. Compare behavioral coverage and runtime before and after the change.

For behavior-critical optimizations, use deliberate fault injection or an
equivalent failure-sensitivity check when practical to confirm that the new
test still detects representative defects. Do not approve an optimization
solely because the rewritten tests pass.

## Definition of Done

- The test is placed with its capability and authoritative owner.
- The test proves observable behavior at the lightest complete boundary.
- Success, relevant failure, boundary, lifecycle, and regression behavior are
  covered.
- Execution is parallel-safe by default; every stronger constraint is exact,
  demonstrated, and documented.
- Clocks, randomness, files, ports, processes, environment, and Qt state are
  controlled and cleaned up.
- Completion is state-driven with bounded diagnostic timeouts rather than
  arbitrary sleeps.
- The test is strictly typed and does not rely on a shadowing stub.
- The focused suite is practical for local use and passes repeatedly under its
  intended worker configuration.
- Applicable architecture, lint, format, strict typing, parallel, isolated,
  serial, and cross-platform gates pass as required by the repository root
  policy.

## Maintainer Authority

- Maintainer instructions override this file.
- If this file conflicts with the repository-root `AGENTS.md`, follow the more
  specific requirement unless it weakens a root safety, behavior, architecture,
  or verification guarantee; otherwise pause and ask for maintainer direction.
