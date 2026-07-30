# Verification Matrix

## Principles

- Every behavioral claim names a command, expected observation, and retained
  log path.
- Run toy tests before real targets.
- Use deterministic inputs and a dedicated `/tmp` output directory.
- A documented command is not evidence until its result is recorded in
  `status.md` with a snapshot revision.

## Existing project checks

| Area | Command | Required observation |
|---|---|---|
| Direct SymSan trace | `python3 tests/trace_check.py direct` | PASS; nonzero symbolic labels |
| AFL forkserver trace | `python3 tests/trace_check.py afl` | PASS; forkserver and symbolic labels |
| Long pipe drain | `python3 tests/pcbt_pipe_check.py` | stream larger than pipe capacity completes without deadlock |
| Three transport modes | `python3 tests/pcbt_toy_modes_check.py` | full bootstrap, SHM suffix, forced overflow to pipe suffix |
| End-to-end phase smoke | `scripts/run-fuzz.sh pcbt` | concolic PCBT activity followed by concrete phase request/switch |
| Concrete baseline | `scripts/run-fuzz.sh baseline` | normal AFL++ control run |
| Forkserver integration | `scripts/run-fuzz.sh single` | target handshake and coverage without taint |
| DFSan integration | `scripts/run-fuzz.sh single-taint` | target handshake, coverage, and taint runtime |

## Required focused regressions

### PCBT topology

1. Insert a full trace with a non-empty suffix.
2. Build the same prefix, call `InsertSuffix`, and compare topology, cids,
   depths, terminal flags, node counts, and `CheckInput` outcomes.
3. Repeat with an empty suffix and verify Terminal state.
4. Attempt suffix insertion on a non-frontier edge and verify the caller rejects
   it before the API call.

### Predicate correctness

1. Cross-check each supported operation against an independent bit-vector oracle.
2. Cover divide-by-zero, signed minimum divided by `-1`, shift greater than or
   equal to width, extraction, concatenation, and short inputs.
3. Use two disjoint predicates in one shared arena; make the earlier predicate
   read beyond the candidate length while the later root remains evaluable.
4. Put an unsupported predicate before a supported predicate and verify whether
   run-global opacity is intended.

### Protocol and lifecycle

1. Confirm pipe frames are reset per execution.
2. Confirm non-gaining SHM data is discarded and increments exactly one rCnt.
3. Confirm overflow replay uses the same queue-file bytes and saved frontier.
4. Confirm opaque admission uses full capture and prevents false saturation.
5. Confirm `SYMAFL_NO_SCREEN` does not report true PCBT saturation.
6. Confirm phase switch kills/restarts the correct forkserver, resets coverage
   state, retains queue files, and recalibrates them.

### Event consumers

If memerr/UCSan binding is implemented, add a fixture that proves:

- the event is decoded rather than merely skipped;
- its path location is stable;
- the counter and report are nonzero;
- a run without memerr does not create a false report.

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
