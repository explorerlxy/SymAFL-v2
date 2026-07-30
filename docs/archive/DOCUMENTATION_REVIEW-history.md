> **Historical:** Pre-refactor documentation audit that motivated the
> current docs map. Canonical structure is defined in `../README.md` and
> current implementation evidence in `../STATUS.md`.

# SymAFL v2 Documentation Review Report

## Overall understanding

The project is a two-phase AFL++ system. During the first phase, a SymSan/DFSan
instrumented target executes every admitted candidate, while a custom mutator
uses an incrementally built PCBT to veto candidates that cannot reach an
unexplored symbolic branch. Initial corpus paths are inserted from full pipe
streams. Known-frontier candidates write only post-frontier condition events to
bounded SHM; an overflowing, coverage-gaining candidate is replayed with a
suffix-only pipe stream. The AFL++ parent drains pipe bytes while waiting for
child status. When evaluable PCBT paths are terminal or rCnt-pruned, the mutator
requests transition to an independently instrumented concrete target.

## Main documentation problems found

1. Current architecture, historical rationale, implementation plan, research
   roadmap, and collaboration rules are mixed in a small set of long files.
2. `DESIGN_V2.md` starts as as-built documentation but later uses completed
   phases and future-tense implementation estimates as if still current.
3. `FRONTIER_SUFFIX_TRACE.md` describes an accepted implementation as both a
   proposal and a current mechanism, including stale “before implementation”
   wording.
4. The README is carrying architecture, protocol, build, validation, research
   scope, and ChatGPT upload policy rather than acting as a navigation entry.
5. There is no single evidence/status page that distinguishes code-reviewed,
   tested, documented-only, planned, and historical claims.
6. Memerr/UCSan path binding is described as part of the design, but the
   reviewed mutator only extracts condition events and does not increment the
   memerr counter.
7. The supplied snapshot does not include the runtime writer implementation,
   phase-switch scheduler path, or named tests, so several claims cannot be
   independently verified from this bundle.

## Static code findings surfaced by the documentation audit

- Converter opacity is run-global through `RunConverter::overflow_`.
- Predicate evaluation walks the entire arena prefix rather than the root's
  reachable subgraph.
- Short-input evaluation failure selects direction zero.
- `InsertSuffix` trusts an unexplored-edge precondition and can replace an
  existing child pointer if the caller violates it.
- Introspection's `saturated` field means screening disabled, including
  no-screen mode; timeout and memerr counters are not updated in the reviewed
  mutator.

These findings are documented as verification targets, not declared runtime
failures without reproduction.

## Proposed documentation architecture

- Root entry: `README.md`
- Agent contract: `AGENTS.md`
- Current behavior: `ARCHITECTURE.md`, `RUNTIME_PROTOCOL.md`, `PCBT.md`
- Operations: `CONFIGURATION.md`, `VERIFICATION.md`
- Evidence and handoff: `STATUS.md`, `NEXT_SESSION.md`
- Research and collaboration: `RESEARCH_CONTEXT.md`, `COLLABORATION.md`
- Durable rationale: ADRs under `docs/decisions/`
- Superseded material: `docs/archive/`

This structure minimizes duplicate truth and makes every current claim traceable
to code and verification evidence.
