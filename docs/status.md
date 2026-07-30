# Implementation Status

Durable **truth layer**. Answers: what is implemented, with what evidence, and
which durable gaps remain?

Does **not** own the next session action — that is [`next.md`](next.md).

## Evidence labels

- **Verified** — code present and covered by a recorded PASS
- **Code-reviewed** — code present; no directed PASS yet, or only partial smoke
- **Documented** — claimed by docs; implementation/test evidence incomplete
- **Planned** — desired, not current behavior

## Snapshot

```text
Snapshot: superproject main (doc-system rename),
          AFLplusplus main ef727c6,
          symsan v2-dev ee90b4a
Last matrix run: 2026-07-30
  python3 tests/trace_check.py direct          -> PASS
  python3 tests/trace_check.py afl             -> PASS
  python3 tests/pcbt_pipe_check.py             -> PASS
  python3 tests/pcbt_toy_modes_check.py        -> PASS
  FUZZ_SECONDS=30 scripts/run-fuzz.sh pcbt     -> PASS
    bootstrap full events=11; saturated after 1 veto;
    concrete restart observed; nodes=11 admitted=1 vetoed=1
Logs: /tmp/symafl-verify-142306, /tmp/symafl2-pcbt-smoke
```

## Feature matrix

| Feature | Status | Evidence | Caveat |
|---|---|---|---|
| Required concolic/concrete targets | Verified | `symsan.cpp:afl_custom_init`; pcbt smoke | — |
| PCBT screening in `post_process` | Verified | admitted/vetoed in pcbt smoke | short-input rule needs unit test |
| Full bootstrap insertion | Verified | bootstrap `mode=full events=11` | — |
| SHM frontier suffix | Verified | `pcbt_toy_modes_check.py` | — |
| Pipe-suffix overflow replay | Verified | same harness: overflow → pipe-suffix | — |
| AFL++ parent pipe drain | Verified | `pcbt_pipe_check.py` (65536 events) | — |
| Phase-switch request + concrete restart | Verified | mutator flag + `afl-fuzz.c` smoke | longer benchmarks open |
| Terminal-edge semantics | Code-reviewed | empty suffix → terminal | directed unit test desirable |
| ≤64-bit predicate interpreter | Code-reviewed | `pred.cpp`; size>64 opaque | shared-arena / opacity gaps |
| Memerr/UCSan path binding | Planned | decoder skips non-condition frames | do not claim as-built |
| Timeout metric | Declared only | introspection field | never incremented |
| Jigsaw in PCBT hot path | Not used | local interpreter only | retained dependency |

## Durable open issues

### High

1. **Shared-converter opacity.** `RunConverter::overflow_` is run-global; one
   unsupported expression can make later predicates opaque.
2. **Arena-prefix evaluation.** `eval_predicate` walks indices `0..root`, not
   only the root-reachable subgraph.
3. **Unchecked `InsertSuffix`.** Caller must guarantee an unexplored frontier;
   the API can overwrite an existing child if misused.

### Medium

4. **Metric semantics.** `saturated` means screening disabled (also under
   `SYMAFL_NO_SCREEN`). `timeouts` / `memerr` stay zero.
5. **Short-input rule.** Failed reads choose direction `0`, not opaque admit.

## Doc-system notes

- Normative behavior: `system.md`, `protocol.md`, `pcbt.md`, `config.md`
- Browser digests: `sync-docs.md`, `sync-code.md`
- History: Git only (no `docs/archive/`)
- `status.md` = truth; `next.md` = next action only

When evidence changes, update this file. Refresh [`sync-docs.md`](sync-docs.md)
if the browser-facing summary would otherwise drift. Do not put the next-action
plan here.
