# Next Action

Action-only relay. Evidence and feature status belong in
[status.md](status.md).

```text
Snapshot: superproject main 5eff0b8 (dirty), AFLplusplus ef727c6,
          symsan v2-dev 6ea7116, 2026-08-01
Next objective: restore precise XZ screening by copying fmemcmp constant
                bytes in the runtime, then establish multi-class screening.
Evidence: /tmp/symafl-v2-xz/final-verify (10 s PCBT): opaque=3,
          veto_terminal=0, veto_rlimit=0, traces=29, nodes=3259, depth=2357,
          admit_opaque=220, admit_eval_failure=0, admit_frontier=0.
          The tree now grows from both XZ seeds and mutated inputs, but
          all admissions are opaque (no terminal/rlimit vetoes possible).
          Precise screening requires copying constant bytes in the runtime,
          which crashes for invalid pointers; a safe copy mechanism is needed.
Invariants: never veto a candidate unless its entry trace class is known to
            match the screened PCBT; retain deterministic conflict discard;
            do not merge distinct root CIDs speculatively; failed concrete
            evaluation remains an explicit conservative admission.
Start in:
- symsan/runtime/dfsan/dfsan.cpp: implement a safe copy for fmemcmp
  constant operands (signal-safe or bounds-checked). The copy must not
  crash on invalid pointers. Verify with the XZ valid seed (currently
  segfaults with unconditional copy).
- Once precise fmemcmp predicates are available, rerun the XZ PCBT
  diagnostic and verify admit_frontier>0, veto_terminal>0 or veto_rlimit>0,
  and suffix capture after bootstrap.
- Then address multi-class screening: write an ADR selecting either
  queue/trace-class affinity or a conservative multi-root dispatcher.
Acceptance:
- XZ PCBT diagnostic records admit_frontier>0, veto_terminal>0 or
  veto_rlimit>0, and suffix capture after bootstrap.
- No incorrect vetoes (valid seed is not vetoed).
- Run predicate regression, trace_check direct/afl, pcbt_pipe_check,
  pcbt_toy_modes_check, collector tests, paired-XZ smoke, then the sequential
  XZ PCBT diagnostic. Record exact PASS/FAIL evidence in status.md.
Owner: Codex VS Code
```
