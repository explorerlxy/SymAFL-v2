#!/usr/bin/env python3
"""Extract SymAFL v2 throughput samples from one AFL run.

Primary metric for PCBT is *test throughput*:

  screened / elapsed_seconds

Each post_process decision is one test unit: either screen-only (veto, no
target execution) or screen+execute (admit). This is NOT the same as AFL's
target-execution rate (`execs_done / elapsed`).

When screening is off or PCBT stats are absent, the primary metric falls back
to AFL execution throughput.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

PCBT_PATTERN = re.compile(r"^\[pcbt\]\s+(?P<fields>.*)$", re.MULTILINE)
FIELD_PATTERN = re.compile(r"(?P<key>[a-z_]+)=(?P<value>\d+)")
# CheckInput outcome histogram keys emitted by the instrumented mutator.
CHECK_OUTCOME_KEYS = (
    "admit_empty", "admit_opaque", "admit_frontier",
    "veto_terminal", "veto_rlimit", "opaque",
)


def parse_stats(path: Path) -> dict[str, str]:
    stats: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        stats[key.strip()] = value.strip()
    return stats


def number(stats: dict[str, str], key: str) -> int | float | None:
    raw = stats.get(key)
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return int(value) if value.is_integer() else value


def parse_pcbt(log_path: Path | None) -> dict[str, int]:
    if log_path is None or not log_path.is_file():
        return {}
    matches = list(PCBT_PATTERN.finditer(
        log_path.read_text(encoding="utf-8", errors="replace")))
    if not matches:
        return {}
    return {
        match.group("key"): int(match.group("value"))
        for match in FIELD_PATTERN.finditer(matches[-1].group("fields"))
    }


def collect(stats_path: Path, log_path: Path | None,
            metadata: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = dict(metadata)
    result["stats_path"] = str(stats_path)
    result["complete"] = False
    result["problems"] = []
    result["metric_notes"] = []
    pcbt = parse_pcbt(log_path)
    result["pcbt"] = pcbt

    if not stats_path.is_file():
        result["problems"].append("missing fuzzer_stats")
        return result

    try:
        stats = parse_stats(stats_path)
    except OSError as exc:
        result["problems"].append(f"could not read fuzzer_stats: {exc}")
        return result

    fields = (
        "execs_done", "execs_per_sec", "start_time", "last_update",
        "paths_total", "paths_found", "paths_imported", "unique_crashes",
        "unique_hangs", "execs_since_crash", "corpus_count", "bitmap_cvg",
        "edges_found", "total_edges", "run_time",
    )
    result["afl"] = {key: number(stats, key) for key in fields if key in stats}
    executions = number(stats, "execs_done")
    started = number(stats, "start_time")
    updated = number(stats, "last_update")

    if executions is None:
        result["problems"].append("missing or invalid execs_done")
    if started is None or updated is None:
        result["problems"].append("missing or invalid start_time/last_update")
        return result
    if updated <= started:
        result["problems"].append("non-positive fuzzer_stats elapsed time")
        return result

    elapsed = updated - started
    result["elapsed_seconds"] = elapsed
    if executions is not None:
        result["afl_execution_throughput_per_sec"] = executions / elapsed

    screened = pcbt.get("screened")
    admitted = pcbt.get("admitted")
    vetoed = pcbt.get("vetoed")
    if screened is None and admitted is not None and vetoed is not None:
        screened = admitted + vetoed
        pcbt["screened"] = screened
        result["metric_notes"].append(
            "screened reconstructed as admitted+vetoed")

    # Primary: PCBT test throughput counts every post_process decision.
    # Fallback: plain AFL execution throughput when screening is inactive.
    if screened is not None and screened > 0:
        result["test_units"] = screened
        result["test_throughput_per_sec"] = screened / elapsed
        result["primary_throughput_metric"] = "test_throughput_per_sec"
        result["primary_throughput_definition"] = (
            "screened/elapsed = (admitted+vetoed)/elapsed; each unit is one "
            "post_process decision (screen-only veto or screen+execute admit)")
        result["complete"] = executions is not None
    elif executions is not None:
        result["test_units"] = int(executions)
        result["test_throughput_per_sec"] = executions / elapsed
        result["primary_throughput_metric"] = "afl_execution_throughput_per_sec"
        result["primary_throughput_definition"] = (
            "execs_done/elapsed; screening inactive or PCBT stats absent")
        result["complete"] = True
    else:
        result["problems"].append("no usable throughput numerator")

    if (screened is not None and screened > 0
            and admitted is not None and executions is not None
            and admitted != executions):
        result["admitted_vs_execs_delta"] = admitted - int(executions)
        result["metric_notes"].append(
            "admitted counts post_process admits; execs_done counts "
            "forkserver runs. They are related but not identical counters "
            f"(delta={admitted - int(executions)}).")

    if pcbt.get("selfcheck_fail"):
        result["metric_notes"].append(
            "selfcheck_fail increments when CheckInput still admits an input "
            "after its own trace was inserted (expected: should veto). "
            "Common causes: opaque predicates, concrete predicate re-eval "
            "diverging from symbolic branch results, short-input d=0 rule.")

    outcomes = {k: pcbt[k] for k in CHECK_OUTCOME_KEYS if k in pcbt}
    if outcomes:
        result["check_outcomes"] = outcomes
        if outcomes.get("admit_opaque", 0) and screened:
            result["metric_notes"].append(
                "admit_opaque dominates when many CheckInput walks hit an "
                "opaque/missing predicate and conservatively admit with no "
                "frontier bookkeeping; this prevents terminal/rlimit vetoes.")
        if outcomes.get("admit_frontier", 0) and not outcomes.get(
                "veto_terminal", 0) and not outcomes.get("veto_rlimit", 0):
            result["metric_notes"].append(
                "all precise walks reached open frontiers under rlimit; "
                "veto=0 is expected until paths terminate or rCnt saturates.")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stats", required=True, type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mode")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--afl-exit-status", type=int)
    args = parser.parse_args()
    metadata = {
        key: value for key, value in {
            "mode": args.mode,
            "run_dir": str(args.run_dir) if args.run_dir else None,
            "afl_exit_status": args.afl_exit_status,
            "log_path": str(args.log) if args.log else None,
        }.items() if value is not None
    }
    result = collect(args.stats, args.log, metadata)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if result["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
