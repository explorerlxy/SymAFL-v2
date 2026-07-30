# ChatGPT-Codex Cooperation

## Roles and authority

ChatGPT Project and local VS Code/Codex do not share a live worktree or a
conversation history. Their roles are deliberately different:

| Surface | Primary responsibility |
|---|---|
| ChatGPT Project | innovation framing, literature and design analysis, architecture planning, task decomposition, decision analysis, and acceptance criteria |
| Codex in VS Code | local repository inspection, implementation, builds, tests, evidence collection, documentation updates, and Git handoff preparation |
| Git worktree and recorded submodule SHAs | canonical implementation and verification truth |

Browser proposals are planning input, not current-code facts. A proposal becomes
a durable project decision only after Codex checks it against the local snapshot,
records the accepted result in a normative document or ADR, and supplies relevant
verification evidence. Codex must return a proposal for revision when local code,
constraints, or evidence contradict it.

## Context synchronization

The active documentation is intentionally small enough to upload directly. There
is no `sync-docs.md`: it would duplicate `system.md`, `evaluation.md`, and
`status.md` and create avoidable drift.

The default browser context bundle is:

1. [system.md](system.md) for logical system design and invariants;
2. [evaluation.md](evaluation.md) for logical experiment design, configuration,
   and verification criteria;
3. [status.md](status.md) for current engineering realization and recorded
   evidence;
4. [next.md](next.md) only when the next action is relevant; and
5. [sync-code.md](sync-code.md) for selected critical source excerpts and code
   anchors.

Replace obsolete Project uploads rather than assuming same-name uploads create a
reliable history. Upload an individual full source file only when it is under
active discussion and `sync-code.md` does not provide enough context.

Do not upload `.git/`, build trees, fuzz outputs, corpora unless explicitly
approved, binaries, cores, raw large logs, credentials, tokens, SSH material,
`.env*`, or data outside the declared research boundary.

## `sync-code.md` contract

`sync-code.md` is the only maintained synchronization digest. It is a curated
implementation aid, not a second specification and not a substitute for the
local checkout. Its required sections are:

1. **Snapshot** — superproject branch/HEAD, dirty state, submodule SHAs, and
   timestamp.
2. **Source map** — critical path-to-responsibility mapping.
3. **Behavior anchors** — concise excerpts or exact file/line references for the
   current control flow, ownership boundary, or invariant under discussion.
4. **Verification snapshot** — relevant executed command and recorded result,
   with a pointer to `status.md` for full evidence.
5. **Open implementation risks** — current code-level gaps, with a pointer to
   `status.md` where the engineering record is authoritative.
6. **Freshness record** — changed sections, reason, and snapshot revision.

Incremental refresh rules:

| Change | Required update |
|---|---|
| Critical code behavior, source anchor, submodule SHA, or code-risk summary changes | refresh only the affected `sync-code.md` sections and its snapshot/freshness record |
| Logical system design changes | update `system.md`; refresh `sync-code.md` only when its anchors or summary become stale |
| Experiment design, setup, criteria, or interpretation changes | update `evaluation.md`; refresh `sync-code.md` only when code context changes |
| Implemented behavior, measured result, or durable engineering gap changes | update `status.md`; refresh `sync-code.md` only if its verification or risk section drifts |
| Next objective, owner, or acceptance changes | update `next.md` only |

Do not rewrite unchanged digest sections. Each refresh names its changed sections
and the revision that made them current.

## Cross-surface handoffs

Start a browser planning or review turn with:

```text
Snapshot: <branch>, <short HEAD or dirty>, submodules <summary>, <timestamp>
Worktree: <clean or changed files + diff stat>
Objective: <one concrete outcome>
Latest verification: <command -> PASS/FAIL>
Open decision: <none or one question>
Context bundle: <uploaded docs and sync-code freshness>
```

A browser-to-local implementation handoff must name the approved objective,
non-negotiable invariants, files to inspect, acceptance commands, applicable ADRs,
and explicit non-goals.

End each local milestone with:

```text
Snapshot: <branch>, <short HEAD or dirty>, submodules <summary>, <timestamp>
Objective: <one concrete outcome>
Decisions/invariants: <IDs or bullets>
Changed/inspected files: <paths>
Behavioral result: <what changed>
Verification: <command -> PASS/FAIL and key observation>
Documentation updated: <system/evaluation/status/next/sync-code as applicable>
Open risks/blockers: <none or pointer into status.md>
Next owner/action: <ChatGPT Project | Codex VS Code> — <action>
```

Facts and measured evidence belong in `status.md`; actions belong in `next.md`.
Do not duplicate their text in a handoff. History of superseded design documents
lives in Git, not under `docs/`.
