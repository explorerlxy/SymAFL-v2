# Configuration Reference

## Required for PCBT mode

| Variable | Meaning | Validation |
|---|---|---|
| `SYMAFL_CONCOLIC_TARGET` | executable target used during PCBT phase | must exist and be executable |
| `SYMAFL_CONCRETE_TARGET` | executable target used after phase switch | must exist and be executable |
| `TAINT_OPTIONS` | SymSan/DFSan target options, normally including `taint_file` and `taint_max_len` | mutator appends pipe and SHM options |

Example:

```bash
export AFL_CUSTOM_MUTATOR_LIBRARY="$PWD/symsan/build/bin/libSymSanMutator.so"
export SYMAFL_CONCOLIC_TARGET="$PWD/tests/toy"
export SYMAFL_CONCRETE_TARGET="$PWD/tests/toy-afl"
export TAINT_OPTIONS="taint_file=/tmp/symafl-out/default/.cur_input:taint_max_len=65536:exit_on_memerror=false"
```

## Optional SymAFL variables

| Variable | Default | Current behavior |
|---|---:|---|
| `SYMAFL_SINGLE_PASS_CAPACITY` | `1048576` events | positive integer up to `UINT32_MAX`; sizes the SHM suffix array |
| `SYMAFL_RCNT_LIMIT` | `16` | maximum non-gaining admissions per frontier direction |
| `SYMAFL_NO_SCREEN` | unset | disables PCBT screening and capture arming; useful for concolic overhead baseline |
| `SYMAFL_TRACE_MODE` | unset | ignored with a warning; lifecycle selects transport |

`SYMAFL_RCNT_LIMIT` is parsed with `atoi` in the reviewed code. Supply a
non-negative decimal value; malformed or negative values are not robustly
validated.

## AFL++ variables used by project scripts

| Variable | Script behavior |
|---|---|
| `AFL_DISABLE_TRIM=1` | prevents queue-entry content changes that would invalidate recorded paths |
| `AFL_MAP_SIZE=65536` | toy smoke default |
| `AFL_SKIP_BIN_CHECK=1` | permits custom target setup in smoke scripts |
| `AFL_NO_UI=1` | non-interactive output |
| `AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1` | smoke convenience |

Use target-appropriate map size, timeout, and memory limits for real experiments.
Do not generalize the toy script defaults to benchmark runs without recording
the change.

## `scripts/run-fuzz.sh` modes

| Mode | Target and purpose |
|---|---|
| `baseline` | concrete AFL++ control, no mutator |
| `single` | concolic-compatible binary with AFL forkserver/coverage, no taint options |
| `single-taint` | same binary with DFSan taint enabled, no PCBT mutator |
| `pcbt` | PCBT concolic phase followed by concrete fallback smoke |

The smoke script defaults `SYMAFL_RCNT_LIMIT` to `0` in `pcbt` mode to reach the
phase boundary quickly. It is not a research-quality screening setting.

## Introspection fields

The mutator exposes:

```text
traces nodes depth conflicts failed timeouts memerr screened admitted vetoed
saturated selfcheck_fail single_pass single_pass_overflow
```

Interpretation caveats:

- `traces` is `Tree::num_traces`, including full and suffix insert attempts.
- `single_pass` counts successful SHM suffix captures.
- `timeouts` and `memerr` are declared but not updated by the reviewed mutator.
- `saturated` currently reflects `screening == false`; it also becomes `1` under
  `SYMAFL_NO_SCREEN`, so it is not a pure saturation indicator.

Do not use caveated fields as paper metrics until their semantics are corrected
and regression-tested.
