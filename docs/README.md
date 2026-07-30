# Documentation Map

Docs are split by role. One fact lives in one place; other files link, they do not restate.

| Role | Files |
|---|---|
| Normative behavior | `system.md`, `protocol.md`, `pcbt.md`, `config.md` |
| Evidence / next action | `status.md`, `next.md` |
| How to test / experiment | `verify.md`, `research.md` |
| Collaboration / browser sync | `workflow.md`, `sync-docs.md`, `sync-code.md` |
| Why (accepted decisions) | `adr/` |
| History | **Git only** — no `docs/archive/` |

## Read by task

| Task | Open |
|---|---|
| Whole system | [system.md](system.md) |
| Trace transport / forkserver / phase switch | [protocol.md](protocol.md) |
| Tree / predicate semantics | [pcbt.md](pcbt.md) |
| Env vars and run modes | [config.md](config.md) |
| What is implemented + evidence | [status.md](status.md) |
| What to do next | [next.md](next.md) |
| Commands and expected observations | [verify.md](verify.md) |
| Experiment identity / reproducibility | [research.md](research.md) |
| Local agent ↔ ChatGPT Project | [workflow.md](workflow.md) |
| Browser upload: docs digest | [sync-docs.md](sync-docs.md) |
| Browser upload: code digest | [sync-code.md](sync-code.md) |
| Why a design was chosen | [adr/](adr/) |
| Doc routing (this file) | [README.md](README.md) |

Root entrypoints outside `docs/`:

- [`../README.md`](../README.md) — human project entry
- [`../AGENTS.md`](../AGENTS.md) — repository operating contract
- [`../CLAUDE.md`](../CLAUDE.md) — local agent skim of the same contract

## Evidence labels

Use only in `status.md` (and briefly mirrored in digests):

- **Verified** — code present + recorded PASS
- **Code-reviewed** — code present; directed PASS missing or partial
- **Documented** — claimed by normative docs; implementation/test incomplete
- **Planned** — not current behavior

Only `system.md`, `protocol.md`, `pcbt.md`, and `config.md` define normative
current behavior. `status.md` decides whether that behavior is Verified,
Code-reviewed, Documented, or Planned.

## status vs next

| File | Owns | Does not own |
|---|---|---|
| [status.md](status.md) | feature matrix, PASS/FAIL, durable gaps | next owner/action story |
| [next.md](next.md) | one next objective, acceptance, owner | matrix / long logs |

Rules:

1. Facts → `status.md`. Actions → `next.md`.
2. Never paste the same paragraph into both.
3. Milestone end: always update `status.md` if evidence changed; update
   `next.md` only if objective/owner/acceptance changed.
4. Keep `next.md` under ~30 lines.

## Browser sync

Default ChatGPT Project upload:

1. [sync-docs.md](sync-docs.md)
2. [sync-code.md](sync-code.md)
3. optional [next.md](next.md) when the next action is the topic

Upload full sources only for files under active edit. Digests can lag; Git
worktree + submodule SHAs remain truth.

## Maintenance

1. Root README stays short and task-oriented.
2. Architecture invariants live in normative docs, not in `next.md`.
3. Durable decisions go under `adr/` as ADRs.
4. Do **not** keep superseded design prose under `docs/`. Recover old text from
   Git history when needed (`git log -- docs/`, `git show <rev>:docs/...`).
5. Behavioral claims name an implementation path and a verification command in
   `status.md`.
6. When normative behavior, evidence, or critical code anchors change, refresh
   `sync-docs.md` / `sync-code.md` if browser summaries would drift.

## Rename legend (this refactor)

| Old | New |
|---|---|
| `ARCHITECTURE.md` | `system.md` |
| `RUNTIME_PROTOCOL.md` | `protocol.md` |
| `PCBT.md` | `pcbt.md` |
| `CONFIGURATION.md` | `config.md` |
| `VERIFICATION.md` | `verify.md` |
| `STATUS.md` | `status.md` |
| `NEXT_SESSION.md` | `next.md` |
| `RESEARCH_CONTEXT.md` | `research.md` |
| `COLLABORATION.md` | `workflow.md` |
| `SYNC_DOCS.md` / `SYNC_CODE.md` | `sync-docs.md` / `sync-code.md` |
| `decisions/` | `adr/` |
| `archive/`, `MIGRATION.md` | removed (Git history) |
