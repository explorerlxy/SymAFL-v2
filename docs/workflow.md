# Collaboration Workflow

## Authority

- **Git worktree + submodule revisions:** implementation truth
- **Local Codex / Claude / IDE:** edit, build, test
- **Browser ChatGPT Project:** architecture discussion, review, task split
  based on uploaded digests — not a live file view

## Default browser sync

Upload only:

1. [`sync-docs.md`](sync-docs.md) — system/docs digest
2. [`sync-code.md`](sync-code.md) — critical code digest
3. optional [`next.md`](next.md) — when the next action is the topic

Replace previous Project copies when refreshing. Do not re-upload the full docs
tree or whole source files by default.

Upload an individual source file only when that path is under edit and the code
digest is insufficient.

## Start-of-turn snapshot

```text
Snapshot: <branch>, <short HEAD or dirty>, submodules <summary>, <timestamp>
Worktree: <clean or changed files + diff stat>
Objective: <one concrete outcome>
Latest verification: <command -> PASS/FAIL>
Open decision: <none or one question>
Sync digests: <sync-docs/sync-code clean or dirty>
```

## Implementation handoff (browser → local)

Must include: objective, non-negotiable invariants, named files, acceptance
commands, ADR refs, explicit non-goals.

## Milestone handoff (local → browser/next owner)

```text
Snapshot: <branch>, <short HEAD or dirty>, submodules <summary>, <timestamp>
Objective: <one concrete outcome>
Decisions/invariants: <IDs or bullets>
Changed/inspected files: <paths>
Behavioral result: <what changed>
Verification: <command -> PASS/FAIL and key observation>
Documentation updated: <status and/or sync-* and/or next>
Open risks/blockers: <none or pointer into status.md>
Next owner/action: <ChatGPT Project | local agent> — <action>
```

### What to update

| Change | Update |
|---|---|
| Implementation or verification evidence | `status.md` (required) |
| Durable open issues | `status.md` (required) |
| Next objective / owner / acceptance | `next.md` (only if changed) |
| Browser system summary would drift | `sync-docs.md` |
| Critical code anchors would drift | `sync-code.md` |

Facts → `status.md`. Actions → `next.md`. No duplicate paragraphs.

## Upload hygiene

Exclude: `.git/`, build trees, fuzz output, corpora (unless approved), binaries,
cores, credentials, tokens, SSH material, `.env*`, unrelated benchmarks.
Replace obsolete uploads; same-name uploads are not version history.

## Full-source bundle (exceptional)

Only when digests are not enough:

1. `README.md`, `AGENTS.md`
2. `docs/sync-docs.md`, `docs/sync-code.md`
3. `docs/status.md`, optional `docs/next.md`
4. the specific source files under discussion
5. smallest affected test; `scripts/run-fuzz.sh` if operational

History of removed design docs lives in Git, not under `docs/`.
