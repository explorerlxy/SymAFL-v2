# ChatGPT Project and Local Codex Collaboration

## Authority model

- **Git worktree and submodule revisions:** implementation truth.
- **Local Codex/IDE session:** inspects, edits, builds, and tests the worktree.
- **Browser ChatGPT Project:** architecture discussion, review, decision records,
  and task decomposition based on explicitly uploaded snapshots.

Neither chat surface should assume it sees the other's current files or history.

## Default browser sync (preferred)

For most planning/review turns, upload only:

1. [`SYNC_DOCS.md`](SYNC_DOCS.md) — documentation/system digest
2. [`SYNC_CODE.md`](SYNC_CODE.md) — critical code excerpt digest

Optionally add:

3. [`NEXT_SESSION.md`](NEXT_SESSION.md) — only when the next action is the topic

Replace the previous Project copies of these digests when refreshing. Do **not**
re-upload the full 15–20 file architecture bundle by default.

Upload an individual source file only when:

- the task edits that file; and
- the SYNC_CODE excerpt is insufficient for the decision.

## Start-of-turn snapshot

```text
Snapshot: <branch>, <short HEAD or dirty>, submodules <summary>, <timestamp>
Worktree: <clean or changed files plus diff stat>
Objective: <one concrete outcome>
Latest verification: <command -> PASS/FAIL>
Open decision: <none or one concrete question>
Sync digests: <SYNC_DOCS/SYNC_CODE SHA or "dirty">
```

## Implementation handoff

A browser-approved task must include:

- objective;
- non-negotiable invariants;
- named files to inspect;
- acceptance commands;
- decision/ADR references;
- explicit non-goals.

Do not rely on “the previous version” or a browser-only attachment.

## Milestone handoff

```text
Snapshot: <branch>, <short HEAD or dirty>, submodules <summary>, <timestamp>
Objective: <one concrete outcome>
Decisions/invariants: <IDs or bullets>
Changed/inspected files: <paths>
Behavioral result: <what changed>
Verification: <command -> PASS/FAIL and key observation>
Documentation updated: <STATUS and/or SYNC_* and/or NEXT_SESSION>
Open risks/blockers: <none or pointer into STATUS>
Next owner/action: <ChatGPT Project | local Codex> — <action>
```

### STATUS vs NEXT_SESSION update policy

| Change | Update |
|---|---|
| Implementation or verification evidence | `STATUS.md` (required) |
| Durable open issue list | `STATUS.md` (required) |
| Next objective / owner / acceptance | `NEXT_SESSION.md` (only if changed) |
| Browser-facing system summary would drift | `SYNC_DOCS.md` |
| Critical code anchors / excerpts would drift | `SYNC_CODE.md` |

Facts go to STATUS. Actions go to NEXT_SESSION. Do not duplicate paragraphs.

## Upload hygiene

Upload only the smallest current snapshot needed for the task. Exclude build
trees, `.git`, fuzz output, corpora unless explicitly approved, binaries, core
dumps, credentials, tokens, SSH material, `.env*`, and unrelated benchmark
data. Replace obsolete uploaded files rather than treating same-name uploads as
version history.

## Full-source bundle (exceptional)

Use only when digests are insufficient (e.g. deep code review of a whole path):

1. `README.md`
2. `AGENTS.md`
3. `docs/SYNC_DOCS.md`
4. `docs/SYNC_CODE.md`
5. `docs/STATUS.md`
6. `docs/NEXT_SESSION.md` (if action-relevant)
7. the specific source files under discussion
8. the smallest affected test
9. `scripts/run-fuzz.sh` when operational behavior is in scope

Prefer digests first; expand only as needed.
