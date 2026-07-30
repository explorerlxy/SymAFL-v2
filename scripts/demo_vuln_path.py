#!/usr/bin/env python3
"""SymAFL v2 Phase 4 demo: vuln <-> path binding.

Runs the traced binary (SymSan instrumented) on a crashing input and prints
the symbolic branch-decision chain that leads to the crash site. Because
branch events are emitted at branch-notify time (before the branch body
executes), the event stream of a crashing run is complete up to the crash
point — the crash is thereby bound to a concrete path in the PCBT.

Usage: demo_vuln_path.py <target> <crash_input>
"""
import os, struct, subprocess, sys, threading, time

MSG = struct.Struct("<HHIQIIIQ")

def main(target, crash):
    r, w = os.pipe(); os.set_blocking(r, False)
    buf = bytearray(); stop = [False]
    def drain():
        while not stop[0]:
            try:
                c = os.read(r, 1 << 20)
                if not c: break
                buf.extend(c)
            except BlockingIOError: time.sleep(0.001)
            except OSError: break
    t = threading.Thread(target=drain, daemon=True); t.start()
    env = dict(os.environ)
    env["TAINT_OPTIONS"] = (f'taint_file="{crash}":taint_max_len=1048576:'
                            f'pipe_fd={w}:exit_on_memerror=false')
    p = subprocess.Popen([target, crash], env=env, pass_fds=(w,),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.close(w)
    try: rc = p.wait(timeout=30)
    except subprocess.TimeoutExpired: p.kill(); rc = "TIMEOUT"
    time.sleep(0.2); stop[0] = True; t.join(timeout=2)

    i = 0; events = []
    while i + MSG.size <= len(buf):
        mt, fl, inst, addr, ctx, cid, lab, res = MSG.unpack_from(buf, i); i += MSG.size
        if mt == 0 and lab != 0:
            events.append((cid, lab, res, addr))
        elif mt == 1: i += 48
        elif mt == 2: i += 4 + res
        elif mt > 5: break

    print(f"target: {target}")
    print(f"crash input: {crash}")
    print(f"exit: {rc}  ({len(events)} symbolic branch events before termination)")
    print("branch-decision chain to the crash site (vuln <-> path binding):")
    for cid, lab, res, addr in events:
        print(f"  cid={cid:#010x} outcome={res} pred_root_label={lab} site={addr:#x}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
