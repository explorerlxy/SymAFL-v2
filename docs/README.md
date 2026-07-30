# Documentation Map

The active documentation has one owner per class of information. Logical design,
engineering realization, and next action are intentionally distinct.

| Role | File |
|---|---|
| Logical system design, runtime workflow, PCBT semantics | [system.md](system.md) |
| Logical evaluation design, configuration, verification criteria, reproducibility | [evaluation.md](evaluation.md) |
| Current code-path mapping, executed results, durable engineering gaps | [status.md](status.md) |
| One next objective, owner, and acceptance | [next.md](next.md) |
| ChatGPT Project and Codex collaboration | [chatgpt-codex-cooperation.md](chatgpt-codex-cooperation.md) |
| Critical-code synchronization digest | [sync-code.md](sync-code.md) |
| Accepted architecture decisions | [adr/](adr/) |
| Superseded documents | Git history only |

## Read by task

| Task | Open |
|---|---|
| Understand the complete system and PCBT contribution | [system.md](system.md) |
| Design an experiment, configure a target, or define validation | [evaluation.md](evaluation.md) |
| Locate the current implementation and its recorded results | [status.md](status.md) |
| Continue assigned work | [next.md](next.md) |
| Coordinate browser ChatGPT and local Codex work | [chatgpt-codex-cooperation.md](chatgpt-codex-cooperation.md) |
| Provide browser code context | [sync-code.md](sync-code.md) |
| Understand why a durable decision was accepted | [adr/](adr/) |

Root entrypoints:

- [README.md](../README.md) — human project entry
- [AGENTS.md](../AGENTS.md) — repository operating contract
- [CLAUDE.md](../CLAUDE.md) — local-agent operating skim

## Logical design versus engineering realization

[system.md](system.md) and [evaluation.md](evaluation.md) define the intended
logical model. `system.md` owns components, data/control flow, PCBT semantics,
and invariants. `evaluation.md` owns evaluation questions, comparison design,
configuration method, verification criteria, metrics, and result interpretation.

[status.md](status.md) owns the current engineering realization for a named
snapshot: code paths implementing the logical system, commands actually run,
measured results, log locations, and durable gaps. A design statement is not
implementation evidence until status identifies both code and an observation.

## Evidence and handoff

| File | Owns | Does not own |
|---|---|---|
| [status.md](status.md) | code mapping, feature evidence, PASS/FAIL, metrics, durable gaps | next action narrative |
| [next.md](next.md) | one next objective, acceptance, owner | evidence matrix and logs |

Facts and evidence go to `status.md`; actions go to `next.md`. Never duplicate
paragraphs. Update `status.md` when implementation evidence changes. Update
`next.md` only when objective, owner, or acceptance changes.

## Browser context

Upload the active documents directly: `system.md`, `evaluation.md`, `status.md`,
optional `next.md`, and `sync-code.md`. There is no `sync-docs.md`; it would
repeat the small canonical documents. The sync-code structure, incremental
refresh rules, upload hygiene, and handoff formats are defined in
[chatgpt-codex-cooperation.md](chatgpt-codex-cooperation.md).

## Maintenance

1. Keep `README.md` short and task-oriented.
2. Keep logical design in `system.md` and `evaluation.md`, not in `next.md`.
3. Keep implementation mapping and actual evidence in `status.md`.
4. Record durable architecture choices under `adr/`.
5. Do not retain superseded prose under `docs/`; recover it through Git history
   with `git log -- docs/` and `git show <revision>:docs/...`.
6. Refresh `sync-code.md` only when its code anchors, snapshot, verification
   excerpt, or code-risk summary would drift.

## Rename legend

| Former active path | Current owner |
|---|---|
| `ARCHITECTURE.md`, `RUNTIME_PROTOCOL.md`, `PCBT.md` | `system.md` |
| `CONFIGURATION.md`, `VERIFICATION.md`, `RESEARCH_CONTEXT.md` | `evaluation.md` |
| `STATUS.md` | `status.md` |
| `NEXT_SESSION.md` | `next.md` |
| `COLLABORATION.md`, `workflow.md` | `chatgpt-codex-cooperation.md` |
| `SYNC_DOCS.md`, `sync-docs.md` | removed; upload canonical docs directly |
| `SYNC_CODE.md` | `sync-code.md` |
| `decisions/` | `adr/` |
| `archive/`, `MIGRATION.md` | removed; Git history |
