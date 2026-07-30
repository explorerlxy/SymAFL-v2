# Documentation Migration Plan

> **Status: completed (2026-07-30).** This file records how the docs split was
> performed. Current navigation lives in [`README.md`](README.md).

## Replace (done)

- Root `README.md` is the concise entry document.
- `AGENTS.md` is the repository operating contract.
- `docs/RESEARCH_CONTEXT.md` is reproducibility-focused.

## Split and archive (done)

The old `docs/DESIGN_V2.md` was split into architecture / protocol / PCBT /
status / ADRs and archived as `docs/archive/DESIGN_V2-history.md`.

The old `docs/FRONTIER_SUFFIX_TRACE.md` was split into ADR 0003 +
`RUNTIME_PROTOCOL.md` and archived as
`docs/archive/FRONTIER_SUFFIX_TRACE-history.md`.

The pre-refactor audit is archived as
`docs/archive/DOCUMENTATION_REVIEW-history.md`.

## Add (done)

- `docs/README.md`
- `docs/CONFIGURATION.md`
- `docs/VERIFICATION.md`
- `docs/STATUS.md`
- `docs/COLLABORATION.md`
- `docs/NEXT_SESSION.md`
- `docs/decisions/0001-*.md` through `0003-*.md`

## Follow-ups completed during landing

- Root README / AGENTS / CLAUDE point at the new canonical documents.
- Collaboration upload bundle includes `solver_common.cpp`, `dfsan.h`, and the
  AFL++ scheduler path (`AFLplusplus/src/afl-fuzz.c`) for `pcbt_switch_pending`.
- Superproject `.gitignore` versions the documentation system plus intentional
  `scripts/` / `tests/` sources (built binaries remain ignored).
- Matching lifecycle pipe-suffix code in `symsan` was verified with the
  transport-mode harness and a short `run-fuzz.sh pcbt` smoke.

Open implementation issues remain in `STATUS.md` and are intentionally outside
this documentation migration.
