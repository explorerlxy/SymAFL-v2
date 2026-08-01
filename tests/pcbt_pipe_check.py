#!/usr/bin/env python3
"""Regression: AFL++ drains a multi-megabyte PCBT event pipe mid-run.

Only builds and fuzzes the repository's pipe_stress.c fixture in /tmp.  The
single concolic execution emits >2 MiB of condition records, so a consumer
that waits for child completion (or for a full pipe) deadlocks.
"""
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AFL = os.path.join(ROOT, "AFLplusplus")
SYMSAN = os.path.join(ROOT, "symsan", "build", "bin")
WORK = "/tmp/symafl2-pcbt-pipe-check"
TRACE = os.path.join(WORK, "pipe-stress-trace")
CONCRETE = os.path.join(WORK, "pipe-stress-concrete")
SHIM = os.path.join(WORK, "afl-init-shim.o")


def run(cmd, **kwargs):
    return subprocess.run(cmd, check=True, text=True, **kwargs)


def main():
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(os.path.join(WORK, "in"))
    with open(os.path.join(WORK, "in", "seed"), "wb") as f:
        f.write(bytes(range(256)) * 256)

    source = os.path.join(ROOT, "tests", "pipe_stress.c")
    shim_source = os.path.join(ROOT, "tests", "afl_init_shim.c")
    build_env = dict(os.environ, KO_CC="clang-18", KO_CXX="clang++-18",
                     KO_USE_FASTGEN="1")
    run(["clang-18", "-c", shim_source, "-o", SHIM], cwd=ROOT)
    run([os.path.join(SYMSAN, "ko-clang"), "-O0",
         "-fno-sanitize-link-runtime", "-fsanitize-coverage=trace-pc-guard",
         source, os.path.join(AFL, "afl-compiler-rt.o"),
         SHIM, "-o", TRACE],
        cwd=ROOT, env=build_env)
    run([os.path.join(AFL, "afl-clang-fast"), "-O0", source, "-o",
         CONCRETE], cwd=ROOT)

    env = dict(os.environ)
    out = os.path.join(WORK, "out")
    env.update(
        AFL_SKIP_BIN_CHECK="1",
        AFL_DISABLE_TRIM="1",
        AFL_NO_UI="1",
        AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES="1",
        AFL_CUSTOM_MUTATOR_LIBRARY=os.path.join(SYMSAN, "libSymSanMutator.so"),
        SYMAFL_CONCOLIC_TARGET=TRACE,
        SYMAFL_CONCRETE_TARGET=CONCRETE,
        SYMAFL_RCNT_LIMIT="255",
        TAINT_OPTIONS=(f"taint_file={out}/default/.cur_input:taint_max_len=65536:"
                       "exit_on_memerror=false"),
    )
    result = subprocess.run(
        ["timeout", "--preserve-status", "-s", "INT", "8",
         os.path.join(AFL, "afl-fuzz"), "-i", os.path.join(WORK, "in"),
         "-o", out, "-m", "none", "-t", "2000+", "--", TRACE, "@@"],
        cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)

    matches = [int(value) for value in re.findall(r"events=(\d+)", result.stdout)]
    largest = max(matches, default=0)
    if largest < 65536:
        print(result.stdout, file=sys.stderr)
        print(f"FAIL: expected a 65536-event trace, got {largest}", file=sys.stderr)
        return 1
    if "Concrete forkserver ready" in result.stdout:
        print(result.stdout, file=sys.stderr)
        print("FAIL: stress run unexpectedly left PCBT mode", file=sys.stderr)
        return 1
    print(f"PASS: AFL++ drained {largest} PCBT events (>2 MiB) during one run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
