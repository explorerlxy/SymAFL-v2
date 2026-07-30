# Repository Operating Contract

## Source of truth

The local Git worktree and its recorded submodule revisions are authoritative.
Do not infer current implementation state from a chat summary, an old design
note, or an uploaded file without a named repository snapshot.

A claim about current code is valid only when it identifies:

- the branch and short commit SHA, or explicitly states that the worktree is
  dirty;
- the relevant submodule revisions;
- the affected files; and
- the exact verification command and PASS/FAIL observation.

Before changing architecture or runtime behavior, read:

- `docs/system.md`
- `docs/protocol.md`
- `docs/pcbt.md`
- `docs/status.md`
- `docs/verify.md`

Git history records superseded documentation and code. Do not retain obsolete
design documents under `docs/`; they are not normative implementation sources.

## Research operating context

SymAFL v2 is an experimental software-engineering project for automated test
generation, program-behavior measurement, path exploration, candidate-input
screening, defect diagnosis, and regression evaluation.

- Work only with local source trees, published offline-buildable benchmarks, or
  explicitly declared laboratory fixtures.
- Do not expand an experiment beyond the stated program, version, build
  configuration, input boundary, or execution environment.
- Default to local, containerized, or otherwise isolated execution.
- Use pinned toolchains, deterministic inputs, bounded CPU/memory/time/disk
  resources, and retained experiment logs where practical.
- Keep fuzzing outputs, corpora generated during runs, logs, crashes, and other
  transient artifacts under `/tmp`, not in the repository worktree.
- Describe objectives and results through measurable observables such as path
  coverage, admitted/vetoed execution counts, trace volume, unique failures,
  minimized inputs, root-cause evidence, and regression status.
- Prefer precise research language over vague operational descriptions.

See `docs/research.md` for the experiment statement, reproducibility record,
and copyable session context.

## Architecture invariants

Preserve the following contracts unless an explicitly documented architecture
decision changes them:

- SymAFL v2 has two execution phases:
  1. a concolic PCBT-guided phase using the SymSan target; and
  2. a concrete AFL++ phase after PCBT saturation.
- PCBT mode requires explicit local `SYMAFL_CONCOLIC_TARGET` and
  `SYMAFL_CONCRETE_TARGET` executables.
- Bootstrap tracing uses `pipe-full`.
- Steady-state admitted candidates use frontier-anchored `shm-suffix`.
- A coverage-gaining candidate whose SHM suffix overflows may be replayed using
  `pipe-suffix`.
- The `afl-fuzz` parent drains the trace pipe while waiting for forkserver
  status. AFL++ stores raw bytes; the custom mutator owns trace decoding and
  PCBT insertion.
- `InsertSuffix` is a strict-invariant API. Its caller must provide the
  unexplored frontier edge selected for the same candidate execution and the
  suffix beginning after that frontier depth.
- Terminal edges represent explored paths with no following symbolic branch and
  must not be treated as unexplored frontiers.
- Unsupported or opaque predicates must not be silently interpreted with
  truncated or invented semantics.
- The current PCBT hot path contains no constraint solving. Retained Jigsaw code
  is not proof that JIT evaluation is active.
- AFL++ modifications must remain limited to scheduling, forkserver trace
  draining, phase switching, and the minimum state reset needed for those
  responsibilities.
- PCBT policy, predicate conversion/evaluation, and trace insertion belong in
  the SymSan custom mutator.
- Deterministic targets are required for PCBT experiments. Conflicting traces
  are discarded rather than merged speculatively.

Do not claim that a feature is implemented merely because it appears in a
historical design or plan. `docs/status.md` must identify the code path and a
passing verification command.

## Project structure and ownership

The superproject contains two private Git submodules:

- `AFLplusplus/`:
  `explorerlxy/SymAFL-AFLplusplus-v2`, normally on `main`, based on AFL++
  v4.31c. Changes here must stay constrained to SymAFL scheduling,
  forkserver integration, trace draining, phase switching, and related
  coverage-state reset.
- `symsan/`:
  `explorerlxy/SymAFL-Symsan`, normally on `v2-dev`. This is the main
  development tree for the custom mutator, PCBT, predicate evaluation, DFSan
  runtime, instrumentation, and tracing protocol.

Important paths include:

- `symsan/driver/aflpp/`: custom mutator, PCBT, and predicate evaluation;
- `symsan/runtime/dfsan/`: DFSan runtime and shared tracing control;
- `symsan/instrumentation/`: LLVM instrumentation;
- `symsan/solvers/jigsaw/`: retained dependency code, not the current PCBT hot
  path;
- `tests/`: target-level fixtures, seeds, smoke checks, and trace checks;
- `symsan/tests/`: focused LLVM/lit regressions;
- `scripts/`: build, run, and evaluation automation;
- `docs/`: normative architecture, protocol, verification, status, and
  collaboration records.

Source changes must be committed in the submodule that owns them. The
superproject records only the resulting submodule pointer update plus
superproject-owned scripts, tests, and documentation.

## Build and verification

Use the pinned LLVM toolchain (`clang-18` and `clang++-18`).

Typical build commands:

```bash
scripts/build-z3.sh             # only when the pinned local Z3 build is needed
scripts/build-all.sh            # AFL++ followed by SymSan
scripts/build-all.sh symsan     # configure/rebuild SymSan only
```

Core verification commands:

```bash
python3 tests/trace_check.py direct
python3 tests/trace_check.py afl
python3 tests/pcbt_pipe_check.py
python3 tests/pcbt_toy_modes_check.py
scripts/run-fuzz.sh single-taint
scripts/run-fuzz.sh pcbt
```

For extended xz evaluation:

```bash
scripts/eval-xz.sh [afl|noscreen|screen|all]
```

Run the smallest relevant check first, then run the full affected matrix
documented in `docs/verify.md`.

Verification records must include:

- the exact command;
- relevant environment overrides;
- PASS or FAIL;
- the key observable, such as non-zero symbolic labels, trace mode, overflow
  fallback, node/depth counts, phase transition, coverage, execution rate, or
  memory use; and
- the location of retained logs when detailed output is needed.

Do not report an unexecuted command as passing. Do not turn an expected design
property into an observed result without evidence.

## Change discipline

- Inspect the named local files before editing them.
- Preserve user changes outside the stated task.
- Prefer the smallest coherent change that establishes one behavior.
- Avoid unrelated cleanup, repository-wide formatting, or opportunistic API
  redesign.
- Add or update focused regression coverage for behavioral changes.
- Update user-facing documentation when commands, configuration, lifecycle,
  semantics, or expected observations change.
- Update `docs/status.md` when implementation or verification evidence changes.
  It owns the feature matrix, PASS/FAIL records, and durable open issues.
- Update `docs/next.md` only when the next objective, owner, or acceptance
  commands change. Keep it action-only and short; never restate the matrix or
  long verification logs there.
- Facts go to status; actions go to next. Do not duplicate paragraphs.
- When browser-facing summaries would drift, refresh `docs/sync-docs.md` and/or
  `docs/sync-code.md` (the default ChatGPT Project upload pair).
- Record durable architecture decisions under `docs/adr/`.
- Recover superseded documentation from Git history rather than retaining it in
  the active `docs/` tree.

## Coding style

Follow the surrounding file.

- C and C++ use two-space indentation, braces on the declaration line, and
  concise `//` comments.
- C++ types use `PascalCase`; methods use established project naming; variables
  and free functions generally use `snake_case` unless an existing API requires
  another form.
- Preserve the `pcbt` namespace and short invariant-focused comments.
- Bash scripts use `#!/usr/bin/env bash`, `set -euo pipefail`, uppercase
  environment/configuration names, and lowercase local variables.
- Python uses four-space indentation and deterministic fixtures.
- No repository-wide formatter or linter is configured. Avoid style-only churn.

## Testing guidelines

- Add focused C/C++ regressions under `symsan/tests/` with descriptive names.
- Add target-level fixtures, harnesses, and integration checks under `tests/`.
- Exercise both direct tracing and the AFL forkserver path when changing
  tainting, event streams, shared-memory control, pipe transport, mutator
  callbacks, or phase switching.
- Cover normal suffix insertion, empty/terminal suffixes, overflow fallback,
  malformed traces, opaque predicates, and deterministic conflict handling when
  those paths are affected.
- Keep fixtures deterministic and small.
- Do not commit large corpora, fuzz queues, raw benchmark output, binaries, core
  dumps, or transient logs.

## VS Code Codex and ChatGPT Project collaboration

Browser-side ChatGPT Project work and the local VS Code/Codex checkout do not
share conversation history or a live file view. Treat the Project as a curated
planning/review surface and the local Git worktree as the only implementation
truth.

See `docs/workflow.md` for the full protocol. The following rules are mandatory.

### Roles

- **ChatGPT Project:** architecture discussion, literature/design analysis,
  task decomposition, review criteria, and durable decisions.
- **Codex in VS Code:** inspect and edit the local checkout, run builds/tests,
  and update repository records.
- **Git and repository documents:** canonical implementation and verification
  state.

### Synchronization protocol

1. Start a browser planning or review turn with a snapshot header containing:
   branch, short HEAD, clean/dirty status, submodule status, current objective,
   and latest passed checks.
2. When the tree is dirty, summarize `git diff --stat` and list uncommitted
   files. Never describe a dirty worktree as a committed revision.
3. Give Codex a self-contained implementation handoff containing the approved
   objective, invariants, acceptance checks, decision IDs, and named local files
   to inspect.
4. End each Codex milestone with a repository handoff. Always update
   `docs/status.md` if evidence changed. Update `docs/next.md` only if the next
   objective/owner/acceptance changed. Refresh `docs/sync-docs.md` and
   `docs/sync-code.md` when the browser digests would otherwise drift.
5. Refresh Project files deliberately. Default upload is the two digests in
   `docs/sync-docs.md` and `docs/sync-code.md` (optionally `next.md`).
   Remove obsolete uploaded sources before uploading replacements; do not
   assume same-name uploads form a reliable version history.
6. Serialize authority. Do not run conflicting browser-directed and local edits
   concurrently.

### Upload hygiene

Upload text-first, reviewable source files. Do not upload:

- `.git/` contents;
- build trees;
- fuzz outputs or corpora;
- binaries, objects, core dumps, or large raw logs;
- credentials, API keys, access tokens, SSH material, or `.env*`; or
- data outside the declared research boundary.

**Default Project upload:** `docs/sync-docs.md` + `docs/sync-code.md`.
Add full source files only for paths under active edit when digests are not
enough. Prefer concise milestone summaries over full terminal logs; retain
detailed logs locally under `/tmp`.

### Required handoff format

Use this compact structure when moving work between surfaces:

```text
Snapshot: <branch>, <short HEAD or "dirty">, submodules <summary>, <timestamp>
Objective: <one concrete outcome>
Decisions/invariants: <bullets or IDs>
Changed/inspected files: <paths>
Verification: <command> -> <PASS/FAIL and key observation>
Open risks/blockers: <none or concrete issue>
Next owner/action: <ChatGPT Project | Codex VS Code> — <action>
```

## Commit and pull-request guidelines

Use short, imperative, scoped commit subjects consistent with repository
history, for example:

```text
tests: add predicate interpreter microbenchmark
v2: fix trace timeout
docs: clarify suffix insertion invariant
```

A commit should represent one coherent intent, not an unrelated collection of
changes.

Pull requests should:

- explain the behavioral change;
- identify the affected execution or verification mode;
- state the relevant architecture invariant;
- include exact PASS/FAIL commands and salient observations;
- identify submodule pointer changes explicitly; and
- include logs, plots, or screenshots only when they help review a measurable
  result.

### Local commit vs remote push

**Commit is local history; push is shared state.** Prefer frequent, small local
commits. Push only when the remote will help with backup, review,
collaboration, or handoff.

#### When to commit

Commit locally:

- after one coherent change lands, such as one bug fix, script, document
  section, test harness change, or invariant-preserving refactor;
- before a risky refactor, task switch, or end-of-session pause;
- after a meaningful verification step passes and should become a recoverable
  checkpoint.

Commits should be understandable from their subject and diff. Temporary local
`wip:` commits are acceptable on a private branch, but clean them up before
sharing when practical.

#### When to push

Push after a shareable milestone, for example when:

- the feature or fix is usable;
- documentation and handoff records are current;
- an experiment is reproducible on another machine/session;
- backup, review, collaboration, or a pull request is needed.

Prefer `feature/*` or `exp/*` branches for daily work. Push `main` only when the
tree is relatively stable, documented, verified on the relevant path, and not
in the middle of a spike.

#### Do not push yet when

Do not push when:

- APIs or design are still changing rapidly;
- the tree contains debug-only code, secrets, absolute local paths, large fuzz
  artifacts, or known unverified breakage;
- history is still expected to be rebased or squashed on a shared branch,
  especially `main`; or
- a referenced submodule commit is not yet available on its remote.

#### Split uncommitted work by theme

Before committing, separate unrelated work into coherent buckets. Typical
superproject buckets are:

- repository metadata: `.gitignore`, `.gitmodules`;
- agent and documentation files: `AGENTS.md`, `CLAUDE.md`, `README.md`,
  `docs/`;
- automation: `scripts/`;
- tests: `tests/`;
- submodule pointer updates.

Keep scratch directories, generated corpora, `/tmp` fuzz queues, binaries, and
logs out of Git unless they are deliberately small, reviewable,
reproducibility fixtures.

### Submodule publication order

This order is mandatory:

1. Commit inside `AFLplusplus/` or `symsan/`.
2. Push that submodule commit to its remote.
3. Commit the superproject submodule pointer update.
4. Push the superproject commit.

Never publish a superproject commit whose referenced submodule SHA is missing
from the corresponding submodule remote.

Keep AFL++ edits limited to scheduling/forkserver integration. PCBT,
predicate-evaluation, and SymSan tracing work belongs in `symsan/`.

### Default development rhythm

```text
small coherent change -> local commit
  -> next coherent change -> local commit
  -> milestone / backup / review needed
  -> optional history cleanup on a private branch
  -> push feature branch (or stable main)
  -> update docs/status.md if evidence changed
  -> update docs/next.md only if next action/owner/acceptance changed
  -> refresh docs/sync-docs.md / docs/sync-code.md if browser digests would drift
