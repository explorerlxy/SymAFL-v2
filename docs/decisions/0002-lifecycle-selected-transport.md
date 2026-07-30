# ADR 0002: Lifecycle-Selected Trace Transport

- Status: Accepted
- Scope: runtime protocol

## Context

Streaming every steady-state trace through a blocking pipe wastes work for
inputs that do not produce coverage gain. Allowing arbitrary mode overrides can
also create pipe data that no later callback consumes.

## Decision

Fix transport by lifecycle:

- initial corpus or no concrete frontier: full pipe stream;
- known frontier: bounded SHM suffix;
- SHM overflow plus confirmed coverage gain: pipe suffix replay.

Ignore `SYMAFL_TRACE_MODE` in production.

## Consequences

- Pipe bytes are produced only for data expected to be consumed.
- Normal gaining inputs need one concolic execution.
- Overflowing gaining inputs need a second concolic replay.
- Dedicated tests, not production overrides, must compare full and suffix modes.
