# SymAFL v2 Evaluation Design

## Purpose and evidence boundary

This document defines how to evaluate SymAFL v2's logical claims, configure the
system and benchmarks, verify functional behavior, and make results
reproducible. It does not declare a result current merely because an experiment
is designed here.

[status.md](status.md) is the engineering-realization record for a named
repository snapshot. It maps the system model to current source paths and holds
executed commands, PASS/FAIL results, measured values, retained-log locations,
and durable implementation gaps.

## Evaluation questions

| Claim | Question | Primary evidence |
|---|---|---|
| Functional correctness | Does PCBT screen only according to its defined frontier and predicate semantics while preserving transport and phase-switch contracts? | Directed regressions, trace/mode harnesses, phase smoke |
| Performance and cost | Does in-process screening reduce unnecessary concolic executions at acceptable latency and resource cost? | Execution rate, screening latency, admission/veto ratio, RSS, CPU, trace volume |
| Innovation contribution | Does PCBT-guided frontier screening and suffix export produce measurable path-exploration value without constraint solving? | Coverage over time versus baselines, replay consistency, PCBT topology/saturation, transport-overflow behavior |

The intended performance targets are mean screening latency below 100 microseconds
per candidate, replay consistency of at least 99 percent for admitted candidates,
and coverage at least 95 percent of the concrete-AFL++ baseline. These are
evaluation goals, not recorded results.

## Experiment design

| Claim | Comparison / target | Configuration | Command or fixture | Metric / expected observation | Result record |
|---|---|---|---|---|---|
| Direct condition tracing | `tests/toy.c` with SymSan target | pinned LLVM, deterministic seed | `python3 tests/trace_check.py direct` | nonzero symbolic labels and valid condition events | `status.md` |
| Forkserver trace integration | same target through AFL++ | forkserver and taint setup | `python3 tests/trace_check.py afl` | forkserver execution preserves symbolic events | `status.md` |
| Pipe-drain safety | long local condition stream | bounded local resources | `python3 tests/pcbt_pipe_check.py` | stream larger than pipe capacity completes without deadlock | `status.md` |
| Transport correctness | toy frontier fixture | forced small SHM capacity | `python3 tests/pcbt_toy_modes_check.py` | `pipe-full -> shm-suffix -> pipe-suffix` | `status.md` |
| Phase switch | concolic and concrete toy binaries | PCBT mode, smoke retry limit | `scripts/run-fuzz.sh pcbt` | PCBT activity then concrete restart | `status.md` |
| Concrete control | concrete toy binary | no custom mutator | `scripts/run-fuzz.sh baseline` | normal AFL++ coverage control | `status.md` |
| Concolic overhead controls | traced toy binary | no taint / taint, no PCBT screen | `scripts/run-fuzz.sh single`, `single-taint`; `SYMAFL_NO_SCREEN=1` where needed | isolate forkserver, taint, and screening cost | `status.md` |
| Benchmark evaluation | deterministic published offline-buildable benchmark | declared benchmark build, corpus, resources, baseline variants | `scripts/eval-xz.sh [afl|noscreen|screen|all]` or benchmark-specific entrypoint | coverage, throughput, resource use, admission/veto behavior | `status.md` and retained `/tmp` logs |

A benchmark experiment must compare a clearly specified baseline, no-screen
concolic mode when applicable, and screened PCBT mode. It must report what its
results support and what they do not support.

## System and benchmark configuration

### Reproducibility requirements

Every result records:

- target name, version, source revision, and build configuration;
- superproject and both submodule revisions;
- compiler and dependency versions;
- seed or corpus identity and checksum where applicable;
- mode and every non-default environment variable;
- CPU, memory, time, disk, and timeout limits;
- exact command, expected observation, observed result, and log location; and
- whether the worktree was clean.

Experiments are limited to local source trees, offline-buildable public
benchmarks, or declared laboratory fixtures. Use local, containerized, or
network-isolated execution; pinned dependencies; deterministic targets for PCBT
and suffix-equivalence work; and bounded CPU, memory, time, and disk resources.
Keep raw outputs under a dedicated `/tmp` directory, not the repository tree.

### Required PCBT configuration

| Variable | Meaning | Requirement |
|---|---|---|
| `SYMAFL_CONCOLIC_TARGET` | executable target for Phase A | must exist and be executable |
| `SYMAFL_CONCRETE_TARGET` | executable target for Phase B | must exist and be executable |
| `TAINT_OPTIONS` | SymSan/DFSan options | include `taint_file` and `taint_max_len` |
| `AFL_CUSTOM_MUTATOR_LIBRARY` | PCBT mutator library | point to `libSymSanMutator.so` |
| `AFL_DISABLE_TRIM=1` | preserves traced queue contents | required for fuzzing |

```bash
export AFL_CUSTOM_MUTATOR_LIBRARY="$PWD/symsan/build/bin/libSymSanMutator.so"
export SYMAFL_CONCOLIC_TARGET="$PWD/tests/toy"
export SYMAFL_CONCRETE_TARGET="$PWD/tests/toy-afl"
export TAINT_OPTIONS="taint_file=/tmp/symafl-out/default/.cur_input:taint_max_len=65536:exit_on_memerror=false"
export AFL_DISABLE_TRIM=1
```

`taint_max_len` is mandatory because the forkserver starts before `.cur_input`
exists. Fuzz output must use an ext4 `/tmp` location rather than the NTFS
repository drive.

### Optional PCBT controls

| Variable | Default | Current meaning |
|---|---:|---|
| `SYMAFL_SINGLE_PASS_CAPACITY` | `1048576` events | SHM suffix capacity, positive integer up to `UINT32_MAX` |
| `SYMAFL_RCNT_LIMIT` | `16` | non-gaining admissions allowed per frontier direction |
| `SYMAFL_NO_SCREEN` | unset | disables PCBT screening and capture arming; use as a concolic-overhead control |
| `SYMAFL_TRACE_MODE` | unset | ignored; lifecycle selects transport |

`SYMAFL_RCNT_LIMIT` is parsed with `atoi` in reviewed code. Supply a
non-negative decimal value; malformed or negative values lack robust validation.

### AFL++ script controls and modes

| Variable | Project-script behavior |
|---|---|
| `AFL_MAP_SIZE=65536` | toy-smoke default |
| `AFL_SKIP_BIN_CHECK=1` | permits custom-target smoke setup |
| `AFL_NO_UI=1` | non-interactive output |
| `AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1` | smoke convenience |

Use target-appropriate map size, timeout, memory limits, CPU binding, and disk
limits for benchmarks. Do not generalize toy defaults without recording the
change.

| `scripts/run-fuzz.sh` mode | Purpose |
|---|---|
| `baseline` | concrete AFL++ control without mutator |
| `single` | concolic-compatible target with forkserver/coverage and no taint options |
| `single-taint` | same target with DFSan taint enabled and no PCBT mutator |
| `pcbt` | PCBT concolic phase then concrete-fallback smoke |

The `pcbt` smoke script defaults `SYMAFL_RCNT_LIMIT` to `0` to reach the phase
boundary quickly. It is not a research-quality screening setting.

## Functional verification criteria

Every behavioral claim requires an exact command, expected observation, and
retained log path. Run deterministic toy fixtures before real targets. A command
becomes evidence only when its result is recorded in [status.md](status.md) with
a repository snapshot.

| Area | Command | Required observation |
|---|---|---|
| Direct SymSan trace | `python3 tests/trace_check.py direct` | PASS; nonzero symbolic labels |
| AFL forkserver trace | `python3 tests/trace_check.py afl` | PASS; forkserver and symbolic labels |
| Long pipe drain | `python3 tests/pcbt_pipe_check.py` | stream beyond pipe capacity completes without deadlock |
| Three transport modes | `python3 tests/pcbt_toy_modes_check.py` | full bootstrap, SHM suffix, forced overflow to pipe suffix |
| End-to-end phase smoke | `scripts/run-fuzz.sh pcbt` | concolic PCBT activity then concrete phase request/switch |
| Concrete baseline | `scripts/run-fuzz.sh baseline` | normal AFL++ control run |
| Forkserver integration | `scripts/run-fuzz.sh single` | target handshake and coverage without taint |
| DFSan integration | `scripts/run-fuzz.sh single-taint` | target handshake, coverage, and taint runtime |

### Required focused regressions

**PCBT topology**

1. Insert a full trace with a non-empty suffix.
2. Build the same prefix, call `InsertSuffix`, and compare topology, cids,
   depths, terminal flags, node counts, and `CheckInput` outcomes.
3. Repeat with an empty suffix and verify Terminal state.
4. Attempt suffix insertion on a non-frontier edge and verify the caller rejects
   it before the API call.

**Predicate correctness**

1. Cross-check each supported operation against an independent bit-vector oracle.
2. Cover divide-by-zero, signed minimum divided by `-1`, shift at least width,
   extraction, concatenation, and short inputs.
3. Use two disjoint predicates in one shared arena; make the earlier predicate
   read beyond the candidate length while the later root remains evaluable.
4. Put an unsupported predicate before a supported predicate and establish
   whether run-global opacity is intended.

**Protocol and lifecycle**

1. Confirm pipe frames reset per execution.
2. Confirm non-gaining SHM data is discarded and increments exactly one retry
   count.
3. Confirm overflow replay uses the same queue-file bytes and saved frontier.
4. Confirm opaque admission uses full capture and prevents false saturation.
5. Confirm `SYMAFL_NO_SCREEN` does not report true PCBT saturation.
6. Confirm phase switch kills/restarts the correct forkserver, resets coverage
   state, retains queue files, and recalibrates them.

**Event consumers**

If memerr/UCSan binding is implemented, add a fixture proving it is decoded, has
a stable path location, produces nonzero counter/report values, and does not
produce a report when the event is absent.

## Metrics and interpretation

Use measurable outcomes rather than vague success language:

- executions per second, screening latency, admitted/vetoed ratio, and coverage
  over time;
- PCBT nodes, depth, conflicts, opaque predicates, replay consistency, and
  saturation state;
- SHM captures, overflows, replay count, pipe bytes, and event count;
- RSS and CPU utilization; and
- unique crash stacks, minimized reproductions, and patch-regression PASS/FAIL.

The mutator exposes:

```text
traces nodes depth conflicts failed timeouts memerr screened admitted vetoed
saturated selfcheck_fail single_pass single_pass_overflow
```

Interpret with these caveats:

- `traces` includes full and suffix insertion attempts.
- `single_pass` counts successful SHM suffix captures.
- `timeouts` and `memerr` are declared but not updated by the reviewed mutator.
- `saturated` reflects `screening == false`, including `SYMAFL_NO_SCREEN`; it is
  not a pure PCBT-saturation indicator.

Do not use caveated fields as paper metrics until their semantics are corrected
and regression-tested.

## Experiment record

```text
Snapshot: <branch> <short HEAD>; submodules <revisions>; dirty=<yes/no>
Target: <name/version/source>
Build: <exact command and compiler>
Mode: <baseline|single|single-taint|pcbt|evaluation variant>
Inputs: <seed/corpus identity and checksum>
Resources: <CPU binding, time, memory, disk>
Command: <exact invocation>
Expected: <observable condition>
Observed: <PASS/FAIL and key metrics>
Logs: </tmp/path>
Conclusion: <what this result supports and what it does not>
```
