# Reproducible Experiment Context

## Scope

SymAFL v2 is a local program-analysis and automated-testing platform for
measuring path exploration, candidate screening, trace transport, crash
classification, root-cause diagnosis, and regression behavior.

Experiments are limited to local source trees, offline-buildable public
benchmarks, or declared laboratory fixtures. Do not extend a test to unrelated
systems or networks.

## Minimum experiment identity

Every result must record:

- target name, version, source revision, and build configuration;
- superproject and both submodule revisions;
- compiler/toolchain version;
- seed or corpus identity;
- mode and all non-default environment variables;
- time, memory, CPU, disk, and timeout limits;
- exact command;
- expected and observed behavior;
- log/output location;
- whether the worktree was clean.

## Default constraints

- Prefer local processes, containers, or network-isolated VMs.
- Pin compiler and dependency versions.
- Use deterministic targets for PCBT/suffix equivalence experiments.
- Keep outputs under a dedicated `/tmp` directory on an appropriate local
  filesystem.
- Bound CPU, memory, time, and disk usage.
- Preserve raw logs locally; summarize only the salient evidence in Git.
- Remove credentials, environment secrets, personal paths, and unrelated host
  details before publishing results.

## Research observables

Use measurable outcomes rather than vague success language:

- executions per second;
- admitted/vetoed ratio;
- coverage over time;
- PCBT nodes, depth, conflicts, opaque predicates, and saturation state;
- SHM captures, overflows, replay count, pipe bytes, and event count;
- RSS and CPU utilization;
- unique crash stacks and minimized reproductions;
- patch regression PASS/FAIL.

Caveated introspection fields listed in `config.md` must not be treated as
validated metrics until corrected.

## Copyable request context

```text
This task runs in a local or isolated reproducible environment.
Target: <name>, version/revision <version>.
Research question: <coverage | screening | transport | diagnosis | regression>.
Inputs and execution remain within the declared target and fixture boundary.
Please report exact commands, resource limits, observable results, and any
uncertainty about the snapshot or verification state.
```
