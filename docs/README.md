# Documentation Map

This directory separates **current behavior**, **operational guidance**,
**verification evidence**, and **historical decisions**. A document must not mix
all four.

## Read by task

| Task | Canonical document |
|---|---|
| Understand the whole system | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Change trace transport or forkserver integration | [RUNTIME_PROTOCOL.md](RUNTIME_PROTOCOL.md) |
| Change tree or predicate semantics | [PCBT.md](PCBT.md) |
| Run or configure the system | [CONFIGURATION.md](CONFIGURATION.md) |
| Add tests or interpret results | [VERIFICATION.md](VERIFICATION.md) |
| Check what is actually implemented | [STATUS.md](STATUS.md) |
| Continue from the latest milestone | [NEXT_SESSION.md](NEXT_SESSION.md) |
| Sync ChatGPT Project with docs summary | [SYNC_DOCS.md](SYNC_DOCS.md) |
| Sync ChatGPT Project with code excerpts | [SYNC_CODE.md](SYNC_CODE.md) |
| Run reproducible experiments | [RESEARCH_CONTEXT.md](RESEARCH_CONTEXT.md) |
| Coordinate browser Project and local agents | [COLLABORATION.md](COLLABORATION.md) |
| Understand why a design was chosen | [decisions/](decisions/) |

## Evidence labels

Use these labels consistently:

- **Verified** — directly present in the named code and covered by a recorded
  passing check.
- **Code-reviewed** — directly present in the reviewed code snapshot, but the
  relevant executable test was not available or not run in that snapshot.
- **Documented** — asserted by a canonical document, but the implementation file
  or test evidence was not included in the reviewed snapshot.
- **Planned** — desired work, not current behavior.
- **Historical** — retained only to explain prior reasoning.

Only `ARCHITECTURE.md`, `RUNTIME_PROTOCOL.md`, `PCBT.md`, and
`CONFIGURATION.md` may define normative current behavior. `STATUS.md` decides
whether that behavior is Verified, Code-reviewed, Documented, or Planned.

## STATUS vs NEXT_SESSION

| File | Owns | Does not own |
|---|---|---|
| [STATUS.md](STATUS.md) | feature matrix, evidence, durable gaps | next owner/action narrative |
| [NEXT_SESSION.md](NEXT_SESSION.md) | single next objective, acceptance, owner | feature matrix / long logs |

Rules:

1. Facts → STATUS. Actions → NEXT_SESSION.
2. Never paste the same paragraph into both.
3. Milestone end: **always** update STATUS if evidence changed; update
   NEXT_SESSION **only** if the next objective/owner/acceptance changed.
4. Keep NEXT_SESSION under ~30 lines.

## Browser sync digests

Default ChatGPT Project upload is:

1. [SYNC_DOCS.md](SYNC_DOCS.md) — integrated docs/system summary
2. [SYNC_CODE.md](SYNC_CODE.md) — critical code excerpts

Optional third file: [NEXT_SESSION.md](NEXT_SESSION.md) when planning the next
action. Upload full sources only for the specific files under edit.

## Maintenance rules

1. Keep the root README short and task-oriented.
2. Put architecture invariants in architecture/protocol documents, not in
   milestone notes.
3. Put temporary work and unresolved next actions in `NEXT_SESSION.md`.
4. Record durable design choices as ADRs under `decisions/`.
5. Move superseded brainstorming documents to `archive/`; do not keep two
   competing “current design” documents.
6. Any behavioral claim must name its implementation path and verification
   command in `STATUS.md`.
7. When STATUS/architecture/protocol/code anchors change, refresh the two SYNC
   digests if the browser summary would otherwise drift.
