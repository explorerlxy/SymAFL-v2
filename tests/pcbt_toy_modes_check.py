#!/usr/bin/env python3
"""Exercise SymAFL's three PCBT transports using tests/toy.c.

The only bootstrap seed is ``AAAA``.  AFL++ receives a dictionary token
``SYMA``; when it reaches that new prefix, the candidate gains coverage.
With a single-event SHM buffer its suffix overflows, so the mutator must
replay exactly that gaining input through pipe-suffix.  This verifies:

  pipe-full bootstrap -> shm-suffix steady capture -> pipe-suffix overflow

All generated targets and fuzzing output stay under /tmp.
"""
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AFL = os.path.join(ROOT, "AFLplusplus")
SYMSAN = os.path.join(ROOT, "symsan", "build", "bin")
WORK = "/tmp/symafl2-pcbt-toy-modes"
TRACE = os.path.join(WORK, "toy-concolic")
CONCRETE = os.path.join(WORK, "toy-concrete")
SHIM = os.path.join(WORK, "afl-init-shim.o")


def run(cmd, **kwargs):
    return subprocess.run(cmd, check=True, text=True, **kwargs)


def main():
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(os.path.join(WORK, "in"))
    with open(os.path.join(WORK, "in", "seed"), "wb") as seed:
        seed.write(b"AAAA")

    source = os.path.join(ROOT, "tests", "toy.c")
    shim_source = os.path.join(ROOT, "tests", "afl_init_shim.c")
    build_env = dict(os.environ, KO_CC="clang-18", KO_CXX="clang++-18",
                     KO_USE_FASTGEN="1")
    run(["clang-18", "-c", shim_source, "-o", SHIM], cwd=ROOT)
    run([os.path.join(SYMSAN, "ko-clang"), "-O0",
         "-fno-sanitize-link-runtime", "-fsanitize-coverage=trace-pc-guard",
         source, os.path.join(AFL, "afl-compiler-rt.o"), SHIM, "-o", TRACE],
        cwd=ROOT, env=build_env)
    run([os.path.join(AFL, "afl-clang-fast"), "-O0", source, "-o", CONCRETE],
        cwd=ROOT)

    out = os.path.join(WORK, "out")
    env = dict(os.environ)
    env.update(
        AFL_SKIP_BIN_CHECK="1",
        AFL_DISABLE_TRIM="1",
        AFL_NO_UI="1",
        AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES="1",
        AFL_CUSTOM_MUTATOR_LIBRARY=os.path.join(SYMSAN, "libSymSanMutator.so"),
        SYMAFL_CONCOLIC_TARGET=TRACE,
        SYMAFL_CONCRETE_TARGET=CONCRETE,
        SYMAFL_RCNT_LIMIT="255",
        SYMAFL_SINGLE_PASS_CAPACITY="1",
        TAINT_OPTIONS=(f"taint_file={out}/default/.cur_input:taint_max_len=65536:"
                       "exit_on_memerror=false"),
    )
    result = subprocess.run(
        ["timeout", "--preserve-status", "-s", "INT", "15",
         os.path.join(AFL, "afl-fuzz"), "-i", os.path.join(WORK, "in"),
         "-o", out, "-x", os.path.join(ROOT, "tests", "toy.dict"),
         "-m", "none", "-t", "2000+", "--", TRACE, "@@"],
        cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)

    required = {
        "pipe-full bootstrap": r"mode=full events=",
        "SHM overflow": r"suffix capture overflow",
        "pipe-suffix replay": r"mode=pipe-suffix .*events=",
    }
    missing = [name for name, pattern in required.items()
               if not re.search(pattern, result.stdout)]
    if missing:
        print(result.stdout, file=sys.stderr)
        print("FAIL: missing " + ", ".join(missing), file=sys.stderr)
        return 1
    if "Concrete forkserver ready" in result.stdout:
        print(result.stdout, file=sys.stderr)
        print("FAIL: toy transport test unexpectedly saturated PCBT", file=sys.stderr)
        return 1
    print("PASS: toy exercised pipe-full -> shm-suffix overflow -> pipe-suffix")
    return 0


if __name__ == "__main__":
    sys.exit(main())
