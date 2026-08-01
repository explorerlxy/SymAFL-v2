#!/usr/bin/env bash
# SymAFL v2 XZ benchmark pilot: sequential afl / noscreen / pcbt runs.
#
# Targets are file-input (@@) binaries from scripts/build-xz-benchmark.sh.
# Default pilot: FUZZ_SECONDS=30, one sequential run per selected mode.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AFLPP="$ROOT/AFLplusplus"
MUT="$ROOT/symsan/build/bin/libSymSanMutator.so"
COLLECTOR="$ROOT/scripts/collect-fuzz-metrics.py"

BUILD_ROOT="${BUILD_ROOT:-/tmp/symafl-v2-realworld-build}"
CONCOLIC="${CONCOLIC:-$BUILD_ROOT/xz/concolic/xz}"
CONCRETE="${CONCRETE:-$BUILD_ROOT/xz/concrete/xz}"
SEEDS="${SEEDS:-/media/hahafish/Data/ForUbuntu/test/Realworld/xz/seeds}"
OUT_ROOT="${OUT_ROOT:-/tmp/symafl-v2-xz}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="${RUN_DIR:-$OUT_ROOT/$RUN_ID}"
FUZZ_SECONDS="${FUZZ_SECONDS:-30}"
FUZZ_TIMEOUT="${FUZZ_TIMEOUT:-2000}"
TAINT_MAX_LEN="${TAINT_MAX_LEN:-65536}"
SMOKE_ONLY=0
MODES=()

usage() {
  cat <<EOF
usage: $0 [--smoke] [afl|noscreen|pcbt|all]

Environment:
  BUILD_ROOT / CONCOLIC / CONCRETE  paired targets from build-xz-benchmark.sh
  SEEDS                            default: Realworld/xz/seeds
  OUT_ROOT / RUN_ID / RUN_DIR      output location under /tmp
  FUZZ_SECONDS (default 30)
  FUZZ_TIMEOUT (default 2000 ms, passed as -t TIMEOUT+)
  SYMAFL_RCNT_LIMIT                optional PCBT research setting
EOF
}

fail() { printf 'eval-xz: %s\n' "$*" >&2; exit 1; }
need_file() { [[ -f "$1" ]] || fail "missing file: $1"; }
need_exec() { [[ -x "$1" ]] || fail "missing executable: $1"; }

while (($#)); do
  case "$1" in
    --smoke) SMOKE_ONLY=1 ;;
    -h|--help) usage; exit 0 ;;
    afl|noscreen|pcbt) MODES+=("$1") ;;
    all) MODES=(afl noscreen pcbt) ;;
    *) usage >&2; exit 2 ;;
  esac
  shift
done
((${#MODES[@]})) || MODES=(afl noscreen pcbt)

need_exec "$AFLPP/afl-fuzz"
need_exec "$MUT"
need_exec "$CONCOLIC"
need_exec "$CONCRETE"
need_file "$SEEDS/valid"
need_file "$SEEDS/malformed"
need_file "$COLLECTOR"
command -v python3 >/dev/null || fail "missing python3"
command -v sha256sum >/dev/null || fail "missing sha256sum"
command -v timeout >/dev/null || fail "missing timeout"

if [[ -e "$RUN_DIR" ]]; then
  if [[ -n "$(find "$RUN_DIR" -mindepth 1 -print -quit 2>/dev/null || true)" ]]; then
    fail "refusing to overwrite populated run directory: $RUN_DIR"
  fi
fi
mkdir -p "$RUN_DIR"

log() { printf '[eval-xz] %s\n' "$*"; }

git_rev() {
  local path="$1"
  if git -C "$path" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "$path" rev-parse HEAD
  else
    printf 'unknown\n'
  fi
}

write_manifest() {
  local mode="$1" mode_dir="$2" afl_exit="$3" started="$4" stopped="$5"
  {
    printf 'target=xz\n'
    printf 'mode=%s\n' "$mode"
    printf 'created_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'started_utc=%s\n' "$started"
    printf 'stopped_utc=%s\n' "$stopped"
    printf 'afl_exit_status=%s\n' "$afl_exit"
    printf 'root=%s\n' "$ROOT"
    printf 'superproject_commit=%s\n' "$(git_rev "$ROOT")"
    printf 'aflplusplus_commit=%s\n' "$(git_rev "$AFLPP")"
    printf 'symsan_commit=%s\n' "$(git_rev "$ROOT/symsan")"
    printf 'concolic=%s\n' "$CONCOLIC"
    printf 'concrete=%s\n' "$CONCRETE"
    printf 'seeds=%s\n' "$SEEDS"
    printf 'fuzz_seconds=%s\n' "$FUZZ_SECONDS"
    printf 'fuzz_timeout_ms=%s\n' "$FUZZ_TIMEOUT"
    printf 'taint_max_len=%s\n' "$TAINT_MAX_LEN"
    printf 'run_dir=%s\n' "$mode_dir"
    printf 'host=%s\n' "$(uname -n)"
    printf 'kernel=%s\n' "$(uname -r)"
    printf 'clang18=%s\n' "$(clang-18 --version 2>/dev/null | head -1 || true)"
    printf 'seed_sha256:\n'
    sha256sum "$SEEDS"/*
    printf 'binary_sha256:\n'
    sha256sum "$CONCOLIC" "$CONCRETE"
  } > "$mode_dir/manifest.env"
}

smoke_binary() {
  local bin="$1" seed="$2" label="$3"
  local rc=0
  timeout --preserve-status -s KILL 5 "$bin" "$seed" >/dev/null 2>&1 || rc=$?
  # exit 0 = valid stream, 1 = decode failure, 2 = IO/arg error; allow 0/1 for seeds
  if (( rc == 124 || rc == 137 || rc == 2 )); then
    fail "smoke failed for $label ($bin $seed) rc=$rc"
  fi
  log "smoke ok: $label rc=$rc"
}

run_smoke() {
  log "smoke concolic/concrete against valid/malformed seeds"
  smoke_binary "$CONCOLIC" "$SEEDS/valid" "concolic/valid"
  smoke_binary "$CONCOLIC" "$SEEDS/malformed" "concolic/malformed"
  smoke_binary "$CONCRETE" "$SEEDS/valid" "concrete/valid"
  smoke_binary "$CONCRETE" "$SEEDS/malformed" "concrete/malformed"
}

collect_metrics() {
  local mode="$1" mode_dir="$2" afl_exit="$3"
  python3 "$COLLECTOR" \
    --stats "$mode_dir/afl/default/fuzzer_stats" \
    --log "$mode_dir/afl-fuzz.log" \
    --output "$mode_dir/metrics.json" \
    --mode "$mode" \
    --run-dir "$mode_dir" \
    --afl-exit-status "$afl_exit" \
    || true
  if [[ -f "$mode_dir/metrics.json" ]]; then
    python3 - "$mode_dir/metrics.json" "$RUN_DIR/pilot-summary.jsonl" <<'PY'
import json, sys
path, out = sys.argv[1], sys.argv[2]
row = json.load(open(path, encoding="utf-8"))
with open(out, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(row, sort_keys=True) + "\n")
print(json.dumps({
    "mode": row.get("mode"),
    "complete": row.get("complete"),
    "execs_done": (row.get("afl") or {}).get("execs_done"),
    "afl_execution_throughput": row.get("afl_execution_throughput_per_sec"),
    "test_units": row.get("test_units"),
    "test_throughput": row.get("test_throughput_per_sec"),
    "primary_metric": row.get("primary_throughput_metric"),
    "screened": (row.get("pcbt") or {}).get("screened"),
    "admitted": (row.get("pcbt") or {}).get("admitted"),
    "vetoed": (row.get("pcbt") or {}).get("vetoed"),
    "selfcheck_fail": (row.get("pcbt") or {}).get("selfcheck_fail"),
    "admitted_vs_execs_delta": row.get("admitted_vs_execs_delta"),
    "problems": row.get("problems"),
}, sort_keys=True))
PY
  fi
}

run_mode() {
  local mode="$1"
  local mode_dir="$RUN_DIR/$mode"
  local out="$mode_dir/afl"
  local logf="$mode_dir/afl-fuzz.log"
  mkdir -p "$out/default"
  local started stopped
  started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  local -a env_vars=(
    AFL_SKIP_BIN_CHECK=1
    AFL_DISABLE_TRIM=1
    AFL_NO_UI=1
    AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1
  )
  local target="$CONCRETE"
  case "$mode" in
    afl)
      target="$CONCRETE"
      ;;
    noscreen)
      target="$CONCOLIC"
      env_vars+=(
        AFL_CUSTOM_MUTATOR_LIBRARY="$MUT"
        SYMAFL_CONCOLIC_TARGET="$CONCOLIC"
        SYMAFL_CONCRETE_TARGET="$CONCRETE"
        SYMAFL_NO_SCREEN=1
        TAINT_OPTIONS="taint_file=$out/default/.cur_input:taint_max_len=$TAINT_MAX_LEN:exit_on_memerror=false"
      )
      ;;
    pcbt)
      target="$CONCOLIC"
      env_vars+=(
        AFL_CUSTOM_MUTATOR_LIBRARY="$MUT"
        SYMAFL_CONCOLIC_TARGET="$CONCOLIC"
        SYMAFL_CONCRETE_TARGET="$CONCRETE"
        TAINT_OPTIONS="taint_file=$out/default/.cur_input:taint_max_len=$TAINT_MAX_LEN:exit_on_memerror=false"
      )
      if [[ -n "${SYMAFL_RCNT_LIMIT+x}" ]]; then
        env_vars+=("SYMAFL_RCNT_LIMIT=$SYMAFL_RCNT_LIMIT")
      fi
      ;;
    *) fail "unknown mode: $mode" ;;
  esac

  log "start mode=$mode seconds=$FUZZ_SECONDS target=$target out=$out"
  set +e
  env "${env_vars[@]}" \
    timeout --preserve-status -s INT "$FUZZ_SECONDS" \
    "$AFLPP/afl-fuzz" -i "$SEEDS" -o "$out" -m none -t "${FUZZ_TIMEOUT}+" -- "$target" @@ \
    >"$logf" 2>&1
  local afl_exit=$?
  set -e
  stopped="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  write_manifest "$mode" "$mode_dir" "$afl_exit" "$started" "$stopped"
  collect_metrics "$mode" "$mode_dir" "$afl_exit"
  log "finished mode=$mode afl_exit=$afl_exit"
}

run_smoke
if (( SMOKE_ONLY )); then
  log "smoke-only complete; run dir $RUN_DIR"
  exit 0
fi

for mode in "${MODES[@]}"; do
  run_mode "$mode"
done

log "pilot complete under $RUN_DIR"
if [[ -f "$RUN_DIR/pilot-summary.jsonl" ]]; then
  log "summary:"
  cat "$RUN_DIR/pilot-summary.jsonl"
fi
