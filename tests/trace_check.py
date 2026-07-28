#!/usr/bin/env python3
"""SymAFL v2 验证 B harness: prove forkserver children taint per-run input.

Mode direct: run tests/toy once with TAINT_OPTIONS(taint_file=seed, pipe_fd).
Mode afl:    run afl-fuzz briefly with TAINT_OPTIONS(taint_file=.cur_input, pipe_fd)
             inherited through afl-fuzz -> forkserver -> children.

Parses 36-byte packed pipe_msg records:
  u16 msg_type | u16 flags | u32 instance | u64 addr | u32 context | u32 id(cid) | u32 label | u64 result
"""
import os, struct, subprocess, sys, threading, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOY = os.path.join(ROOT, "tests", "toy")
AFL = os.path.join(ROOT, "AFLplusplus", "afl-fuzz")
SEEDS = os.path.join(ROOT, "tests", "seeds")
MSG = struct.Struct("<HHIQIIIQ")
COND, GEP, MEMCMP, MEMERR = 0, 1, 2, 4

def drain(fd, buf, stop):
    while not stop[0]:
        try:
            chunk = os.read(fd, 1 << 16)
            if not chunk:
                break
            buf += chunk
        except BlockingIOError:
            time.sleep(0.001)
        except OSError:
            break

def parse(buf):
    n_cond = n_gep = n_memcmp = n_memerr = 0
    cids, labels, results = set(), set(), set()
    i = 0
    while i + MSG.size <= len(buf):
        t, flags, inst, addr, ctx, cid, label, result = MSG.unpack_from(buf, i)
        i += MSG.size
        if t == COND:
            n_cond += 1; cids.add(cid); labels.add(label); results.add(result)
        elif t == GEP:
            n_gep += 1
            i += 48  # gep_msg trailer
        elif t == MEMCMP:
            n_memcmp += 1
            break  # variable length; stop parsing (not needed for this check)
        elif t == MEMERR:
            n_memerr += 1
        else:
            break  # desync guard
    return n_cond, n_gep, n_memcmp, n_memerr, cids, labels, results

def run(mode):
    r, w = os.pipe()
    os.set_blocking(r, False)
    buf = bytearray()
    stop = [False]
    th = threading.Thread(target=drain, args=(r, buf, stop), daemon=True)
    th.start()

    env = dict(os.environ)
    if mode == "direct":
        env["TAINT_OPTIONS"] = f'taint_file="{SEEDS}/seed1":pipe_fd={w}:exit_on_memerror=false'
        cmd = [TOY, f"{SEEDS}/seed1"]
    else:
        out = "/tmp/v2-out-b"
        subprocess.run(["rm", "-rf", out])
        # AFL++ per-fuzzer input lives in <out>/default/.cur_input; the
        # forkserver starts before it exists -> needs taint_max_len patch.
        subprocess.run(["mkdir", "-p", f"{out}/default"])
        env["TAINT_OPTIONS"] = (f'taint_file="{out}/default/.cur_input":'
                                f'taint_max_len=65536:pipe_fd={w}:exit_on_memerror=false')
        env.update(AFL_SKIP_BIN_CHECK="1", AFL_DISABLE_TRIM="1", AFL_NO_UI="1",
                   AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES="1", AFL_MAP_SIZE="65536")
        cmd = ["timeout", "-s", "INT", "20", AFL, "-i", SEEDS, "-o", out,
               "-m", "none", "-t", "2000+", "--", TOY, "@@"]

    p = subprocess.Popen(cmd, env=env, pass_fds=(w,),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.close(w)
    p.wait()
    time.sleep(0.3)
    stop[0] = True
    th.join(timeout=2)
    os.close(r)

    n_cond, n_gep, n_memcmp, n_memerr, cids, labels, results = parse(buf)
    print(f"[{mode}] bytes={len(buf)} cond={n_cond} gep={n_gep} memcmp={n_memcmp} "
          f"memerr={n_memerr} uniq_cids={len(cids)} "
          f"label_range=({min(labels) if labels else '-'},{max(labels) if labels else '-'}) "
          f"results={sorted(results)[:6]}")
    ok = n_cond > 0 and any(l > 0 for l in labels)
    print(f"[{mode}] {'PASS: symbolic branch events with non-zero labels received' if ok else 'FAIL'}")
    return ok

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "direct"
    sys.exit(0 if run(mode) else 1)
