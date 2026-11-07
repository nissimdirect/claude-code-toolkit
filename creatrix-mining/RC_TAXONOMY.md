# Root-cause clusters (assign exactly one per row)

Derived from the 10% spot-check of 183 classified rows (2026-11-04). Pick the cluster that names the MECHANISM, not the area.

| code | cluster | mechanism | plan-time check |
|---|---|---|---|
| RC01 | persistence-roundtrip-gap | new state saved but not restored (or neither); serialize/hydrate/whitelist miss | Plan lists serialize + hydrate + schema/whitelist entry for every new persisted field, plus a round-trip test |
| RC02 | unwired-feature | built and unit-tested but no caller, UI entry point, or consumer (dead code, write-only flag, disabled entry) | Plan names the user entry point + the call site that consumes each new module/flag; acceptance is a live UI path |
| RC03 | contract-drift | frontend/backend/IPC field name, shape, unit or key mismatch (camel/snake, choices/options, mix placement) | Plan pins the wire contract (field names, types, units) and adds a contract test across the boundary |
| RC04 | preview-export-parity | export/render path diverges from live preview (seed, automation scope, sample rate, layers) | Plan states which code path export uses for each new behavior + a preview-vs-export parity test |
| RC05 | react-state-lifecycle | stale closures, hook order, selectors returning fresh refs, render loops, missing re-render triggers | Plan identifies store subscriptions/selectors touched and requires a component test for re-render + no loop |
| RC06 | cross-store-integrity | delete/undo/move leaves orphans or stale refs in other stores (automation lanes, mappings, keyframes) | Plan enumerates every store referencing the entity and the cleanup/rebase on delete, undo, move, split, ripple |
| RC07 | trust-boundary-validation | missing clamp/NaN/type/path/size/depth guard on user- or file-supplied input | Plan lists every new input crossing a trust boundary (IPC, project file, env) with its validator + a malformed-input test |
| RC08 | layout-css | grid/specificity/overflow/clipping/z-order/unbounded growth | Plan includes the layout at narrow + tall states and a visual/geometry oracle (no overlap, min sizes) |
| RC09 | input-event-handling | click bubbling, capture phase, pointer interception, shortcuts blocked, hit-target errors | Plan lists the event path (target, propagation, competing listeners) for each new interaction + an E2E on the real element |
| RC10 | timing-concurrency | races, debounce/throttle, socket busy, async ordering, timeouts, heartbeat on disposed windows | Plan states concurrency model (who can call concurrently, timeouts, cancellation) + a stress/timing test |
| RC11 | test-gap-or-wrong-layer | missing/inadequate tests, wrong test layer, stale selectors, flaky thresholds, tests asserting removed markup | Plan names the test layer per behavior and the oracle; selectors via stable test-ids |
| RC12 | ci-env-drift | CI runner/env/deps differ from dev; standing red CI; missing binaries | Plan includes CI impact (new deps/binaries/env) and requires green CI on the exact job set before merge |
| RC13 | unverified-done-claim | declared done/fixed/covered without live verification; "still broken" after claim | Plan defines done = named live-runtime evidence (screenshot/log/E2E) per acceptance item, not "tests pass" |
| RC14 | intent-misread | built the wrong thing, wrong interpretation, rebuilt something that exists, ignored user spec | Plan quotes the user's words per requirement and lists existing components reused (inventory before build) |
| RC15 | stale-plan-or-doc | plan/packet/audit/bug-list facts wrong vs code at execution time (preconditions, counts, file paths) | Plan preconditions are executable greps/commands re-run at dispatch, not prose claims |
| RC16 | git-workflow-hygiene | wrong branch/checkout/runtime path, stranded/uncommitted work, stacked-PR fallout, push w/o review, merge conflicts | Plan names branch, base, worktree, runtime path, and merge order for stacked work |
| RC17 | missing-baseline-ux | expected baseline capability absent (NLE/DAW conventions: cross-track drag, marquee, feedback toasts, error messages) | Plan checks the feature against a reference app's baseline interactions list (Ableton/Premiere/Photoshop) |
| RC18 | numeric-edge-case | divide-by-zero, zero-width/empty ranges, boundaries, overflow, unit/scale errors | Plan lists boundary values (0, empty, max, negative, NaN) for each new numeric param + tests |
| RC19 | perf-resource-budget | over frame budget, memory/OOM, leaks, unbounded caches/loops, strobing degrade | Plan states a perf/memory budget and the measurement harness for new hot-path code |
| RC20 | rename-config-residue | partial renames, split-brain paths/dirs/consts, version strings hard-coded in N places | Plan includes a repo-wide grep inventory for every renamed identifier/path and a single source of truth |
| RC21 | design-churn | design decided then reversed (layout, interaction model, architecture placement) without upfront options/prototype | Plan presents >=2 options with the user's choice recorded before build; reversible prototype for UI layout |
| RC99 | other | none of the above fits | — |
