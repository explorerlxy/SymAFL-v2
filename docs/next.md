# Next Action

Action-only relay. Evidence and feature status belong in
[status.md](status.md).

```text
Snapshot: superproject main 5eff0b8 (dirty), AFLplusplus ef727c6,
          symsan v2-dev 193cfd7 (dirty), 2026-08-01
Next objective: make XZ screening sound and useful across distinct entry
                condition sequences, without reintroducing opaque predicates.
Evidence: /tmp/symafl-v2-xz/opaque-total-20260801T000000Z (10 s PCBT):
          opaque=0 and veto_terminal=18615, but traces=1/nodes=1/depth=1,
          admit_frontier=0, single_pass=0, and admit_eval_failure=3167.
          The learned tree represents only the first bootstrap entry trace;
          this does not yet establish safe screening for the valid seed's
          different entry sequence or suffix capture.
Invariants: never veto a candidate unless its entry trace class is known to
            match the screened PCBT; retain deterministic conflict discard;
            do not merge distinct root CIDs speculatively; failed concrete
            evaluation remains an explicit conservative admission.
Start in:
- Write an ADR selecting either queue/trace-class affinity or a conservative
  multi-root dispatcher.  Define how a candidate is associated with a root
  before CheckInput may veto it.
- symsan/driver/aflpp/{symsan,pcbt}.{cpp,hpp}: bootstrap both declared XZ
  seed classes, preserve their provenance, and admit unknown classes until a
  full trace establishes them.  Keep suffix insertion frontier-anchored.
- Add focused regressions for distinct first CIDs, valid/malformed seed
  bootstrap, and short-input evaluation admission; keep the iterative scalar
  converter and <=8-byte direct fmemcmp-to-zero semantics total.
Acceptance:
- No cross-class candidate is vetoed; each learned root/class is independently
  screenable, with conflicting traces still discarded inside that class.
- Representative XZ valid, malformed, and coverage-gaining traces report
  opaque=0; unsupported/wide semantics are explicit conservative admissions
  or fail target preflight, never guessed or silently vetoed.
- XZ PCBT diagnostic records admit_frontier>0, suffix capture after bootstrap,
  and veto_terminal>0 or veto_rlimit>0 with executed < screened.
- Run predicate regression, trace_check direct/afl, pcbt_pipe_check,
  pcbt_toy_modes_check, collector tests, paired-XZ smoke, then the sequential
  XZ PCBT diagnostic. Record exact PASS/FAIL evidence in status.md.
Owner: Codex VS Code
```
