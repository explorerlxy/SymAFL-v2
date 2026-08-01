# SymAFL v2 Critical Code Digest

This is the sole browser synchronization digest. Upload it with
[system.md](system.md), [evaluation.md](evaluation.md),
[status.md](status.md), and optional [next.md](next.md). It is a
source-faithful implementation artifact for browser-side analysis, not a second
system specification and not a substitute for the local worktree.

```text
Snapshot: superproject main 5eff0b8 (dirty)
AFLplusplus: main ef727c60875e17bac8400d0ec1025e6e856a21b8
symsan: v2-dev 193cfd74f0bcdc575236cbc39c2832ecf8bb790f (dirty)
Generated: 2026-08-01
Freshness: refreshed complete mutator, PCBT, and predicate excerpts after the PCBT storage refactor
Status document: docs/status.md is dirty and records the current verification matrix
```

## Reading contract

The excerpts below implement the components mapped in [status.md](status.md).
Each fenced block is copied verbatim from the declared inclusive range at the
recorded revision. Its provenance line supplies the full-file source-line count,
included-line count, and SHA-256 of the complete source file. There are no
ellipses, synthetic declarations, pseudocode replacements, reformatted lines,
or omitted bodies inside a source block.

Compact, tightly coupled implementations are included as complete files. Larger
AFL++ sources contribute only the complete functions and scheduler boundary that
own SymAFL integration. Dependencies not reproduced as source are named in the
introductory text rather than replaced with invented stubs.

## Status-driven source map

| Engineering realization in status.md | Primary excerpts |
|---|---|
| Required concolic/concrete targets and capture setup | trace ABI; complete custom mutator |
| PCBT screening and retry accounting | custom mutator; complete PCBT implementation |
| Bootstrap full trace and insertion | runtime writer; custom mutator; PCBT implementation |
| SHM frontier suffix and overflow replay | trace ABI; writer; mutator; PCBT implementation |
| Terminal edges and saturation | complete PCBT implementation |
| <=64-bit predicate conversion and evaluation | complete predicate header and implementation |
| Parent-side pipe drain | AFL++ trace-aware wait and drain function |
| Concrete phase switch and state reset | AFL++ PCBT state fields, switch function, scheduler call site |

The source order follows the data path:

```text
trace ABI -> runtime writer -> mutator setup/arming -> AFL++ parent drain
          -> mutator decode/insert -> PCBT screening -> predicate evaluation
          -> mutator phase request -> AFL++ scheduler switch
```

## 1. Shared trace-control ABI

The mutator and the concolic runtime share the label table and this control
block. mode and armed are synchronized with acquire/release operations in the
included writer and mutator code.

**Provenance:** `symsan/runtime/dfsan/dfsan.h:35-105`; source lines: 455; included: 71; revision: `193cfd74f0bcdc575236cbc39c2832ecf8bb790f`; SHA-256: `10d981fed060aabe466857912637e97911e45a873589c708cc185e0592f5a4b1`

```c
// Copy declarations from public sanitizer/dfsan_interface.h header here.
typedef uint32_t dfsan_label;

typedef union {
  uint64_t i;
  float f;
  double d;
} data;

struct dfsan_label_info {
  dfsan_label l1;
  dfsan_label l2;
  data op1;
  data op2;
  uint16_t op;
  uint16_t size; // FIXME: this limit the size of the operand to 65535 bits or bytes (in case of memcmp)
  uint32_t hash;
} __attribute__((aligned (8), packed));

// Shared trace-control protocol used by SymAFL's PCBT concolic phase.
// The custom mutator selects one transport for each forkserver child:
// full pipe during bootstrap, bounded SHM for normal suffix capture, or a
// suffix-only pipe replay after an SHM overflow. `skip_depth` is the number
// of symbolic condition events already represented by the PCBT prefix.
#define SYMAFL_SINGLE_PASS_MAGIC 0x53504331U  // "SPC1"
#define SYMAFL_SINGLE_PASS_VERSION 2U

#define SYMAFL_TRACE_OFF 0U
#define SYMAFL_TRACE_FULL_STREAM 1U
#define SYMAFL_TRACE_SUFFIX_SHM 2U
#define SYMAFL_TRACE_SUFFIX_PIPE 3U

struct symafl_single_pass_event {
  uint32_t cid;
  dfsan_label label;
  uint8_t result;
  uint8_t reserved[3];
};

struct symafl_single_pass_control {
  uint32_t magic;
  uint32_t version;
  uint32_t mode;
  uint32_t armed;
  uint32_t skip_depth;
  uint32_t event_capacity;
  uint32_t event_count;
  uint32_t overflow;
  uint32_t reserved;
  symafl_single_pass_event events[];
};

static inline size_t symafl_single_pass_size(size_t event_capacity) {
  return sizeof(symafl_single_pass_control) +
         event_capacity * sizeof(symafl_single_pass_event);
}

#ifndef PATH_MAX
# define PATH_MAX 4096
#endif
#define CONST_OFFSET 1
#define CONST_LABEL 0

static const size_t minimum_uniontable_size = 0x10000 * sizeof(dfsan_label_info); // 64K entries
static size_t uniontable_size = 0xc00000000; // FIXME

struct taint_file {
  char filename[PATH_MAX];
  int fd;
  off_t offset;
  dfsan_label offset_label;
```

## 2. Complete custom-mutator implementation

This compact file is included whole because my_mutator_t, initialization,
transport arming, decoder state, full/suffix insertion, replay, queue callbacks,
screening, saturation, and introspection all share state. It depends on the ABI
above, pcbt.hpp below, and AFL++ declarations in afl-fuzz.h.

**Provenance:** `symsan/driver/aflpp/symsan.cpp:1-664`; source lines: 664; included: 664; revision: `v2-dev 193cfd74f0bcdc575236cbc39c2832ecf8bb790f (dirty worktree)`; SHA-256: `59e1d977536ee702b89c763fb75976d7ffc20ec633fdfe5c1adfcaa708c4f057`

```cpp
/*
  SymAFL v2 custom mutator for AFL++: PCBT-guided seed screening.

  Based on the SymSan AFL++ driver
  (c) 2023 - 2024 by Chengyu Song <csong@ucr.edu>, Apache 2.0.

  v2 strips the solving chain (no TaskManager / Solver / custom mutations):
  AFL++ does traditional fuzzing only. The mutator
    (1) arms the SymSan forkserver target to capture symbolic branch-event
        streams for admitted candidates, then inserts coverage-gaining paths
        into a PCBT (path-constraint binary trie);
    (2) screens mutated candidates against the PCBT in
        afl_custom_post_process (Phase 2).
*/

#include "dfsan/dfsan.h"

#include "pcbt.hpp"

extern "C" {
#include "afl-fuzz.h"
}

#include <algorithm>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <vector>

#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/types.h>
#include <fcntl.h>

using namespace __dfsan;

#ifndef DEBUG
#define DEBUG 0
#endif

#if !DEBUG
#undef DEBUGF
#define DEBUGF(_str...) do { } while (0)
#endif

// Bootstrap always uses pipe-full so every initial path enters the tree.
// Steady state uses bounded SHM suffix capture. Pipe suffix is reserved for a
// confirmed coverage-gaining input whose SHM capture overflowed.

#undef alloc_printf
#define alloc_printf(_str...) ({ \
    char* _tmp; \
    s32 _len = snprintf(NULL, 0, _str); \
    if (_len < 0) FATAL("Whoa, snprintf() fails?!"); \
    _tmp = (char*)ck_alloc(_len + 1); \
    snprintf((char*)_tmp, _len + 1, _str); \
    _tmp; \
  })

struct my_mutator_t {
  my_mutator_t() = delete;
  explicit my_mutator_t(afl_state_t *afl) : afl(afl) {}

  ~my_mutator_t() {
    if (single_pass_control) {
      munmap(single_pass_control, single_pass_size);
    }
    if (single_pass_label_info) {
      munmap(single_pass_label_info, uniontable_size);
    }
    if (single_pass_trace_fd >= 0) close(single_pass_trace_fd);
    if (single_pass_union_fd >= 0) close(single_pass_union_fd);
    if (single_pass_trace_name) {
      shm_unlink(single_pass_trace_name);
      ck_free(single_pass_trace_name);
    }
    if (single_pass_union_name) {
      shm_unlink(single_pass_union_name);
      ck_free(single_pass_union_name);
    }
    if (full_stream_read_fd >= 0) close(full_stream_read_fd);
    if (full_stream_write_fd >= 0) close(full_stream_write_fd);
  }

  afl_state_t *afl;

  pcbt::Tree tree;
  std::unordered_set<std::string> traced_entries;
  bool bootstrap_done = false;

  // screening state (post_process)
  bool screening = true;
  uint8_t rlimit = 16;
  pcbt::NodeRef last_node = pcbt::kUnexplored;
  uint8_t last_dir = 0;
  bool last_gained = true;

  // Single-pass capture state. The target forkserver maps both regions once;
  // each admitted candidate arms the small control block for its own child.
  char *single_pass_union_name = nullptr;
  char *single_pass_trace_name = nullptr;
  int single_pass_union_fd = -1;
  int single_pass_trace_fd = -1;
  dfsan_label_info *single_pass_label_info = nullptr;
  symafl_single_pass_control *single_pass_control = nullptr;
  size_t single_pass_size = 0;
  bool single_pass_armed = false;
  int full_stream_read_fd = -1;
  int full_stream_write_fd = -1;

  // stats
  uint64_t traced_runs = 0;
  uint64_t failed_runs = 0;
  uint64_t trace_timeouts = 0;
  uint64_t memerr_events = 0;
  uint64_t screened = 0;
  uint64_t admitted = 0;
  uint64_t vetoed = 0;
  uint64_t vetoes_since_admit = 0;
  bool saturation_logged = false;
  // After inserting a trace, re-run CheckInput on the same bytes. A correct
  // insertion should close that path so CheckInput vetoes (returns false).
  // selfcheck_fail counts the opposite: CheckInput still admits the input.
  uint64_t selfcheck_fail = 0;
  uint64_t single_pass_captures = 0;
  uint64_t single_pass_overflows = 0;
};

// Shared union table owned by the target forkserver.
static dfsan_label_info *__dfsan_label_info;
static const size_t MAX_LABEL = uniontable_size / sizeof(dfsan_label_info);

dfsan_label_info *__dfsan::get_label_info(dfsan_label label) {
  if (unlikely(label >= MAX_LABEL)) {
    throw std::out_of_range("label too large " + std::to_string(label));
  }
  return &__dfsan_label_info[label];
}

static void init_forkserver_capture(my_mutator_t *data) {
  uint32_t capacity = 1U << 20;
  if (const char *value = getenv("SYMAFL_SINGLE_PASS_CAPACITY")) {
    char *end = nullptr;
    unsigned long long parsed = strtoull(value, &end, 10);
    if (end == value || *end != '\0' || parsed == 0 ||
        parsed > UINT32_MAX) {
      FATAL("Invalid SYMAFL_SINGLE_PASS_CAPACITY=%s", value);
    }
    capacity = (uint32_t)parsed;
  }

  data->single_pass_size = symafl_single_pass_size(capacity);
  data->single_pass_union_name =
      alloc_printf("/symafl-single-pass-union-%d", getpid());
  data->single_pass_trace_name =
      alloc_printf("/symafl-single-pass-events-%d", getpid());
  data->single_pass_union_fd = shm_open(data->single_pass_union_name,
      O_RDWR | O_CREAT | O_EXCL, S_IRUSR | S_IWUSR);
  if (data->single_pass_union_fd < 0 ||
      ftruncate(data->single_pass_union_fd, uniontable_size)) {
    PFATAL("Failed to create single-pass union table");
  }
  data->single_pass_label_info = (dfsan_label_info *)mmap(
      nullptr, uniontable_size, PROT_READ, MAP_SHARED,
      data->single_pass_union_fd, 0);
  if (data->single_pass_label_info == MAP_FAILED) {
    data->single_pass_label_info = nullptr;
    PFATAL("Failed to map single-pass union table");
  }

  data->single_pass_trace_fd = shm_open(data->single_pass_trace_name,
      O_RDWR | O_CREAT | O_EXCL, S_IRUSR | S_IWUSR);
  if (data->single_pass_trace_fd < 0 ||
      ftruncate(data->single_pass_trace_fd, data->single_pass_size)) {
    PFATAL("Failed to create single-pass event buffer");
  }
  data->single_pass_control = (symafl_single_pass_control *)mmap(
      nullptr, data->single_pass_size, PROT_READ | PROT_WRITE, MAP_SHARED,
      data->single_pass_trace_fd, 0);
  if (data->single_pass_control == MAP_FAILED) {
    data->single_pass_control = nullptr;
    PFATAL("Failed to map single-pass event buffer");
  }
  memset(data->single_pass_control, 0, data->single_pass_size);
  data->single_pass_control->magic = SYMAFL_SINGLE_PASS_MAGIC;
  data->single_pass_control->version = SYMAFL_SINGLE_PASS_VERSION;
  data->single_pass_control->event_capacity = capacity;

  int pipefd[2];
  if (pipe(pipefd)) PFATAL("Failed to create forkserver full-trace pipe");
  data->full_stream_read_fd = pipefd[0];
  data->full_stream_write_fd = pipefd[1];
  int flags = fcntl(data->full_stream_read_fd, F_GETFL);
  if (flags < 0 || fcntl(data->full_stream_read_fd, F_SETFL,
                         flags | O_NONBLOCK)) {
    PFATAL("Failed to configure forkserver full-trace pipe");
  }
  data->afl->fsrv.sym_trace_fd = data->full_stream_read_fd;

  const char *old_options = getenv("TAINT_OPTIONS");
  char *pipe_option = alloc_printf(":pipe_fd=%d", data->full_stream_write_fd);
  char *options = alloc_printf(
      "%s%sshm_name=%s:shm_size=%zu:single_pass_name=%s:single_pass_size=%zu"
      "%s",
      old_options ? old_options : "", old_options && *old_options ? ":" : "",
      data->single_pass_union_name, uniontable_size,
      data->single_pass_trace_name, data->single_pass_size,
      pipe_option ? pipe_option : "");
  if (setenv("TAINT_OPTIONS", options, 1)) {
    if (pipe_option) ck_free(pipe_option);
    ck_free(options);
    PFATAL("Failed to configure single-pass TAINT_OPTIONS");
  }
  if (pipe_option) ck_free(pipe_option);
  ck_free(options);
  __dfsan_label_info = data->single_pass_label_info;
  fprintf(stderr, "[pcbt] forkserver trace control enabled (capacity=%u)\n",
          capacity);
}

/// no splice input
extern "C" void afl_custom_splice_optout(my_mutator_t *data) {
  (void)(data);
}

extern "C" my_mutator_t *afl_custom_init(afl_state *afl, unsigned int seed) {
  (void)(seed);

  my_mutator_t *data = new my_mutator_t(afl);
  if (!data) {
    FATAL("afl_custom_init alloc");
    return NULL;
  }

  // PCBT has two distinct execution phases. The initial target must be the
  // concolic binary; after the tree is exhausted AFL++ restarts its
  // forkserver with the concrete binary and rebuilds coverage from the queue.
  const char *concolic = getenv("SYMAFL_CONCOLIC_TARGET");
  const char *concrete = getenv("SYMAFL_CONCRETE_TARGET");
  if (!concolic || !*concolic || !concrete || !*concrete) {
    FATAL("PCBT mode requires SYMAFL_CONCOLIC_TARGET and "
          "SYMAFL_CONCRETE_TARGET");
  }
  if (access(concolic, X_OK) || access(concrete, X_OK)) {
    PFATAL("PCBT target is not executable");
  }
  data->afl->pcbt_mode = 1;
  data->afl->pcbt_concrete_target = ck_strdup((u8 *)concrete);

  if (const char *mode = getenv("SYMAFL_TRACE_MODE")) {
    WARNF("SYMAFL_TRACE_MODE=%s is ignored: PCBT transport is selected "
          "by lifecycle (bootstrap=pipe-full, steady=shm-suffix, "
          "overflow+gain=pipe-suffix)\n", mode);
  }
  init_forkserver_capture(data);

  if (getenv("SYMAFL_NO_SCREEN")) {
    data->screening = false;
  }
  if (const char *rl = getenv("SYMAFL_RCNT_LIMIT")) {
    char *end = nullptr;
    unsigned long parsed = strtoul(rl, &end, 10);
    if (end == rl || *end != '\0' || parsed > UINT8_MAX) {
      FATAL("Invalid SYMAFL_RCNT_LIMIT=%s (expected 0..255)", rl);
    }
    data->rlimit = (uint8_t)parsed;
  }
  return data;
}

extern "C" void afl_custom_deinit(my_mutator_t *data) {
  const pcbt::Tree &t = data->tree;
  fprintf(stderr,
          "[pcbt] traces=%llu nodes=%llu pred_nodes=%llu depth=%llu conflicts=%llu "
          "opaque=%llu failed=%llu timeouts=%llu memerr=%llu screened=%llu "
          "admitted=%llu vetoed=%llu saturated=%llu "
          "selfcheck_fail=%llu single_pass=%llu single_pass_overflow=%llu "
          "admit_empty=%llu admit_opaque=%llu admit_frontier=%llu "
          "veto_terminal=%llu veto_rlimit=%llu\n",
          (unsigned long long)t.num_traces, (unsigned long long)t.num_nodes,
          (unsigned long long)t.num_pred_nodes(),
          (unsigned long long)t.max_depth,
          (unsigned long long)t.num_conflicts,
          (unsigned long long)t.num_opaque,
          (unsigned long long)data->failed_runs,
          (unsigned long long)data->trace_timeouts,
          (unsigned long long)data->memerr_events,
          (unsigned long long)data->screened,
          (unsigned long long)data->admitted,
          (unsigned long long)data->vetoed,
          (unsigned long long)(data->screening ? 0 : 1),
          (unsigned long long)data->selfcheck_fail,
          (unsigned long long)data->single_pass_captures,
          (unsigned long long)data->single_pass_overflows,
          (unsigned long long)t.check_admit_empty,
          (unsigned long long)t.check_admit_opaque,
          (unsigned long long)t.check_admit_frontier,
          (unsigned long long)t.check_veto_terminal,
          (unsigned long long)t.check_veto_rlimit);
  delete data;
}


static void disarm_capture(my_mutator_t *data) {
  symafl_single_pass_control *control = data->single_pass_control;
  __atomic_store_n(&control->armed, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&control->mode, SYMAFL_TRACE_OFF, __ATOMIC_RELEASE);
  data->single_pass_armed = false;
}

static void arm_full_capture(my_mutator_t *data) {
  symafl_single_pass_control *control = data->single_pass_control;
  __atomic_store_n(&control->event_count, 0, __ATOMIC_RELAXED);
  __atomic_store_n(&control->overflow, 0, __ATOMIC_RELAXED);
  __atomic_store_n(&control->armed, 0, __ATOMIC_RELAXED);
  __atomic_store_n(&control->mode, SYMAFL_TRACE_FULL_STREAM, __ATOMIC_RELEASE);
  __atomic_store_n(&control->armed, 1, __ATOMIC_RELEASE);
  data->single_pass_armed = true;
}

static void arm_suffix_capture(my_mutator_t *data, pcbt::NodeRef node,
                               uint8_t dir) {
  symafl_single_pass_control *control = data->single_pass_control;
  __atomic_store_n(&control->event_count, 0, __ATOMIC_RELAXED);
  __atomic_store_n(&control->overflow, 0, __ATOMIC_RELAXED);
  __atomic_store_n(&control->armed, 0, __ATOMIC_RELAXED);
  control->skip_depth = data->tree.depth(node);
  __atomic_store_n(&control->mode, SYMAFL_TRACE_SUFFIX_SHM, __ATOMIC_RELEASE);
  __atomic_store_n(&control->armed, 1, __ATOMIC_RELEASE);
  data->last_node = node;
  data->last_dir = dir;
  data->single_pass_armed = true;
}

static void arm_pipe_suffix_capture(my_mutator_t *data, pcbt::NodeRef node,
                                    uint8_t dir) {
  symafl_single_pass_control *control = data->single_pass_control;
  __atomic_store_n(&control->event_count, 0, __ATOMIC_RELAXED);
  __atomic_store_n(&control->overflow, 0, __ATOMIC_RELAXED);
  __atomic_store_n(&control->armed, 0, __ATOMIC_RELAXED);
  control->skip_depth = data->tree.depth(node);
  __atomic_store_n(&control->mode, SYMAFL_TRACE_SUFFIX_PIPE,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&control->armed, 1, __ATOMIC_RELEASE);
  data->last_node = node;
  data->last_dir = dir;
  data->single_pass_armed = true;
}

static bool decode_full_stream(const u8 *wire, size_t wire_size,
                               std::vector<pcbt::Event> *events) {
  size_t offset = 0;
  while (offset < wire_size) {
    if (wire_size - offset < sizeof(pipe_msg)) return false;
    pipe_msg msg;
    memcpy(&msg, wire + offset, sizeof(msg));
    offset += sizeof(msg);
    if (msg.msg_type == cond_type) {
      if (msg.label != 0 && msg.label != kInitializingLabel) {
        if (msg.label >= MAX_LABEL) return false;
        events->push_back({msg.id, msg.label, (uint8_t)(msg.result != 0)});
      }
      continue;
    }
    size_t trailer = 0;
    if (msg.msg_type == gep_type) {
      trailer = sizeof(gep_msg);
    } else if (msg.msg_type == memcmp_type && msg.flags) {
      trailer = sizeof(memcmp_msg) + (size_t)msg.result;
    } else if (msg.msg_type == gv_type) {
      trailer = (size_t)msg.result;
    }
    if (trailer > wire_size - offset) return false;
    offset += trailer;
  }
  return true;
}

static void selfcheck(my_mutator_t *data, const u8 *buf, size_t buf_size) {
  if (!buf || !buf_size) return;
  pcbt::NodeRef node = pcbt::kUnexplored;
  uint8_t dir = 0;
  // Fail when the just-inserted input is still admitted. Expected success is
  // CheckInput == false (path ends at a terminal edge). Remaining admits are
  // usually opaque predicates, concrete re-eval vs symbolic-path divergence,
  // or the short-input d=0 evaluation rule.
  if (data->tree.CheckInput(buf, (uint32_t)buf_size, &node, &dir,
                            data->rlimit)) {
    data->selfcheck_fail += 1;
  }
}

static bool decode_pipe_events(my_mutator_t *data,
                               std::vector<pcbt::Event> *events,
                               const char *fname) {
  afl_forkserver_t *fsrv = &data->afl->fsrv;
  if (decode_full_stream(fsrv->sym_trace_buf, fsrv->sym_trace_len, events)) {
    return true;
  }
  WARNF("invalid pipe trace for %s (%zu bytes)\n", fname,
        fsrv->sym_trace_len);
  data->failed_runs += 1;
  return false;
}

static bool insert_full_stream(my_mutator_t *data, const u8 *buf,
                               size_t buf_size, const char *fname) {
  std::vector<pcbt::Event> events;
  events.reserve(4096);
  if (!decode_pipe_events(data, &events, fname)) {
    disarm_capture(data);
    return false;
  }
  uint32_t created = data->tree.InsertTrace(events, __dfsan_label_info,
                                            MAX_LABEL);
  data->traced_runs += 1;
  fprintf(stderr, "[pcbt-trace] %s mode=full events=%zu created=%u\n",
          fname, events.size(), created);
  disarm_capture(data);
  // A run without any symbolic conditions cannot be represented by the
  // decision tree, so it has no meaningful PCBT self-check.
  if (!events.empty()) selfcheck(data, buf, buf_size);
  return true;
}

static bool insert_pipe_suffix_capture(my_mutator_t *data, const u8 *buf,
                                       size_t buf_size, const char *fname) {
  if (!data->single_pass_armed || data->last_node == pcbt::kUnexplored) {
    return false;
  }
  std::vector<pcbt::Event> events;
  events.reserve(4096);
  if (!decode_pipe_events(data, &events, fname)) {
    disarm_capture(data);
    return false;
  }
  uint32_t created = data->tree.InsertSuffix(data->last_node, data->last_dir,
      events, __dfsan_label_info, MAX_LABEL);
  fprintf(stderr,
          "[pcbt-trace] %s mode=pipe-suffix skip=%u events=%zu created=%u\n",
          fname, data->tree.depth(data->last_node), events.size(), created);
  disarm_capture(data);
  selfcheck(data, buf, buf_size);
  return true;
}

static bool insert_suffix_capture(my_mutator_t *data, const u8 *buf,
                                  size_t buf_size, const char *fname) {
  if (!data->single_pass_armed || data->last_node == pcbt::kUnexplored) {
    return false;
  }
  symafl_single_pass_control *control = data->single_pass_control;
  uint32_t count = __atomic_load_n(&control->event_count, __ATOMIC_ACQUIRE);
  bool overflow = __atomic_load_n(&control->overflow, __ATOMIC_ACQUIRE) ||
                  count > control->event_capacity;
  if (overflow) {
    data->single_pass_overflows += 1;
    WARNF("suffix capture overflow for %s; replaying through forkserver\n", fname);
    disarm_capture(data);
    return false;
  }
  std::vector<pcbt::Event> events;
  events.reserve(count);
  for (uint32_t i = 0; i < count; ++i) {
    const symafl_single_pass_event &event = control->events[i];
    if (event.label == 0 || event.label == kInitializingLabel ||
        event.label >= MAX_LABEL) {
      disarm_capture(data);
      return false;
    }
    events.push_back({event.cid, event.label, event.result});
  }
  uint32_t created = data->tree.InsertSuffix(data->last_node, data->last_dir,
      events, data->single_pass_label_info, MAX_LABEL);
  data->single_pass_captures += 1;
  fprintf(stderr,
          "[pcbt-trace] %s mode=suffix skip=%u events=%zu created=%u\n",
          fname, data->tree.depth(data->last_node), events.size(), created);
  disarm_capture(data);
  selfcheck(data, buf, buf_size);
  return true;
}

static bool replay_pipe_suffix(my_mutator_t *data, const u8 *buf,
                               size_t buf_size, const char *fname,
                               pcbt::NodeRef node, uint8_t dir) {
  arm_pipe_suffix_capture(data, node, dir);
  afl_fsrv_write_to_testcase(&data->afl->fsrv, const_cast<u8 *>(buf), buf_size);
  fsrv_run_result_t result = afl_fsrv_run_target(&data->afl->fsrv,
      data->afl->fsrv.exec_tmout, &data->afl->stop_soon);
  if (result != FSRV_RUN_OK) {
    WARNF("forkserver pipe-suffix replay failed for %s (%u)\n", fname,
          result);
    data->failed_runs += 1;
    disarm_capture(data);
    return false;
  }
  return insert_pipe_suffix_capture(data, buf, buf_size, fname);
}

static bool read_queue_file(const char *fname, std::vector<u8> *buf) {
  int fd = open(fname, O_RDONLY);
  struct stat st;
  if (fd < 0 || fstat(fd, &st) || st.st_size <= 0 || st.st_size > MAX_FILE) {
    if (fd >= 0) close(fd);
    return false;
  }
  buf->resize(st.st_size);
  ssize_t got = read(fd, buf->data(), buf->size());
  close(fd);
  return got == (ssize_t)buf->size();
}

extern "C" void afl_custom_post_run(my_mutator_t *data) {
  if (data->bootstrap_done || !data->single_pass_armed) return;
  uint32_t mode = __atomic_load_n(&data->single_pass_control->mode,
                                  __ATOMIC_ACQUIRE);
  if (mode == SYMAFL_TRACE_SUFFIX_SHM &&
      data->last_node != pcbt::kUnexplored) {
    (void)insert_suffix_capture(data, nullptr, 0, "bootstrap");
  } else if (mode == SYMAFL_TRACE_FULL_STREAM) {
    (void)insert_full_stream(data, nullptr, 0, "bootstrap");
  }
  data->last_node = pcbt::kUnexplored;
}

extern "C" u8 afl_custom_queue_get(my_mutator_t *data, const u8 *filename) {
  (void)filename;
  data->bootstrap_done = true;
  return 1;
}

extern "C" u8 afl_custom_queue_new_entry(my_mutator_t *data,
                                         const u8 *filename_new_queue,
                                         const u8 *filename_orig_queue) {
  (void)filename_orig_queue;
  if (!data->bootstrap_done || !data->single_pass_armed) return 0;
  const char *fname = (const char *)filename_new_queue;
  std::vector<u8> buf;
  if (!read_queue_file(fname, &buf)) {
    WARNF("cannot read coverage-gaining queue entry %s\n", fname);
    disarm_capture(data);
    return 0;
  }
  uint32_t mode = __atomic_load_n(&data->single_pass_control->mode,
                                  __ATOMIC_ACQUIRE);
  pcbt::NodeRef node = data->last_node;
  uint8_t dir = data->last_dir;
  bool inserted = mode == SYMAFL_TRACE_SUFFIX_SHM
      ? insert_suffix_capture(data, buf.data(), buf.size(), fname)
      : mode == SYMAFL_TRACE_SUFFIX_PIPE
            ? insert_pipe_suffix_capture(data, buf.data(), buf.size(), fname)
            : mode == SYMAFL_TRACE_FULL_STREAM
                  ? insert_full_stream(data, buf.data(), buf.size(), fname)
                  : false;
  if (!inserted && node != pcbt::kUnexplored) {
    (void)replay_pipe_suffix(data, buf.data(), buf.size(), fname, node, dir);
  }
  data->last_gained = true;
  data->traced_entries.insert(fname);
  return 0;
}

/// PCBT screening: veto mutated candidates that cannot reach an unexplored
/// frontier. Returning 0 with *out_buf=NULL tells AFL++ to skip executing
/// this candidate entirely.
extern "C" size_t afl_custom_post_process(my_mutator_t *data, u8 *buf,
                                          size_t buf_size, u8 **out_buf) {
  // rCnt bookkeeping for the previously admitted candidate
  if (data->last_node != pcbt::kUnexplored) {
    if (!data->last_gained) {
      uint8_t &count = data->tree.retry_count(data->last_node, data->last_dir);
      if (count != UINT8_MAX) count += 1;
    }
    if (data->single_pass_armed) {
      disarm_capture(data);
    }
    data->last_node = pcbt::kUnexplored;
  }

  if (!data->screening) {
    *out_buf = buf;
    return buf_size;
  }

  data->screened += 1;
  pcbt::NodeRef node = pcbt::kUnexplored;
  uint8_t dir = 0;
  if (data->tree.CheckInput(buf, (uint32_t)buf_size, &node, &dir,
                            data->rlimit)) {
    data->admitted += 1;
    data->vetoes_since_admit = 0;
    data->last_gained = false;
    // Dry-run corpus paths must all enter the tree, so bootstrap is always
    // pipe-full. Thereafter a candidate has an established frontier and uses
    // SHM. The pipe is reserved for data that is known to be consumed: the
    // bootstrap trace or an overflow replay after AFL++ confirms a gain.
    if (!data->bootstrap_done || node == pcbt::kUnexplored) {
      data->last_node = node;
      data->last_dir = dir;
      arm_full_capture(data);
    } else {
      arm_suffix_capture(data, node, dir);
    }
    *out_buf = buf;
    return buf_size;
  }

  data->vetoed += 1;
  ++data->vetoes_since_admit;
  // A saturated PCBT is a phase boundary, not a local screening fallback.
  // Let AFL++ perform the restart at its next scheduler boundary, where it
  // can safely replace the forkserver and rebuild its coverage state.
  if (data->tree.IsSaturated(data->rlimit)) {
    data->screening = false;
    data->afl->pcbt_switch_pending = 1;
    if (!data->saturation_logged) {
      data->saturation_logged = true;
      fprintf(stderr,
              "[pcbt] tree saturated after %llu vetoes; switching to concrete\n",
              (unsigned long long)data->vetoed);
    }
  }
  *out_buf = NULL;
  return 0;
}

extern "C" const char *afl_custom_introspection(my_mutator_t *data) {
  static char buf[768];
  const pcbt::Tree &t = data->tree;
  snprintf(buf, sizeof(buf),
           "traces=%llu nodes=%llu pred_nodes=%llu depth=%llu conflicts=%llu opaque=%llu "
           "failed=%llu timeouts=%llu memerr=%llu "
           "screened=%llu admitted=%llu vetoed=%llu saturated=%llu "
           "selfcheck_fail=%llu single_pass=%llu single_pass_overflow=%llu "
           "admit_empty=%llu admit_opaque=%llu admit_frontier=%llu "
           "veto_terminal=%llu veto_rlimit=%llu",
           (unsigned long long)t.num_traces, (unsigned long long)t.num_nodes,
           (unsigned long long)t.num_pred_nodes(),
           (unsigned long long)t.max_depth,
           (unsigned long long)t.num_conflicts,
           (unsigned long long)t.num_opaque,
           (unsigned long long)data->failed_runs,
           (unsigned long long)data->trace_timeouts,
           (unsigned long long)data->memerr_events,
           (unsigned long long)data->screened,
           (unsigned long long)data->admitted,
           (unsigned long long)data->vetoed,
           (unsigned long long)(data->screening ? 0 : 1),
           (unsigned long long)data->selfcheck_fail,
           (unsigned long long)data->single_pass_captures,
           (unsigned long long)data->single_pass_overflows,
           (unsigned long long)t.check_admit_empty,
           (unsigned long long)t.check_admit_opaque,
           (unsigned long long)t.check_admit_frontier,
           (unsigned long long)t.check_veto_terminal,
           (unsigned long long)t.check_veto_rlimit);
  return buf;
}
```

## 3. Complete PCBT representation and algorithms

The following header and source must be analyzed together. Nodes use compact
32-bit NodeRef child references: 0 is unexplored, 1 is the global terminal
node, and 2 is the virtual root. InsertSuffix deliberately retains its
caller-owned frontier-prefix invariant; CheckInput still chooses direction zero
when evaluation fails; saturation treats opaque predicates as unsaturated.

### pcbt.hpp

**Provenance:** `symsan/driver/aflpp/pcbt.hpp:1-90`; source lines: 90; included: 90; revision: `v2-dev 193cfd74f0bcdc575236cbc39c2832ecf8bb790f (dirty worktree)`; SHA-256: `28f2baa1e3b4b47651cf47ae0476ab92047a28d78c94b8c7dad5f0bef6798b54`

```cpp
// Path Constraint Binary Tree (PCBT) for SymAFL v2.
//
// A binary decision trie over symbolic-branch outcomes. Nodes live in a
// contiguous Tree-owned arena and refer to children by 32-bit NodeRef values:
// 0 is unexplored and 1 is the single global terminal node. The virtual root
// has no predicate; root.child[0] is the entry slot for the first condition.
#pragma once

#include <cstdint>
#include <vector>

#include "dfsan/dfsan.h"
#include "pred.hpp"

namespace pcbt {

using NodeRef = uint32_t;
constexpr NodeRef kUnexplored = 0;
constexpr NodeRef kTerminal = 1;
constexpr NodeRef kRoot = 2;

struct Node {
  uint32_t cid = 0;  // compile-time branch id
  Predicate pred;    // root view into Tree::pred_arena_
  NodeRef child[2] = {kUnexplored, kUnexplored};
  uint32_t depth = 0;                // root's children = 1
  uint8_t rCnt[2] = {0, 0};          // non-gaining admissions per direction
};

struct Event {
  uint32_t cid;
  uint32_t label;  // AST label in the *current* union table (per-run)
  uint8_t result;  // concrete branch outcome (0/1)
};

class Tree {
 public:
  Tree();

  // Insert one full branch-event path. The union table must still hold this
  // run's content. Returns the number of new topology nodes created.
  uint32_t InsertTrace(const std::vector<Event> &events,
                       const dfsan_label_info *table,
                       size_t table_labels);

  // Insert the suffix known to follow parent.child[direction]. The caller has
  // already established the PCBT prefix during screening, so this performs no
  // root replay or prefix matching. An empty suffix records the terminal node.
  uint32_t InsertSuffix(NodeRef parent, uint8_t direction,
                        const std::vector<Event> &events,
                        const dfsan_label_info *table, size_t table_labels);

  // Screen a candidate. On admission, *out_node / *out_dir identify an
  // unexplored frontier for retry bookkeeping and suffix skip depth. Terminal
  // edges are already explored and vetoed.
  bool CheckInput(const uint8_t *input, uint32_t len, NodeRef *out_node,
                  uint8_t *out_dir, uint8_t rlimit);

  bool IsSaturated(uint8_t rlimit) const;
  uint32_t depth(NodeRef ref) const { return node(ref).depth; }
  uint64_t num_pred_nodes() const { return pred_arena_.nodes.size(); }
  uint8_t &retry_count(NodeRef ref, uint8_t direction) {
    return node(ref).rCnt[direction];
  }

  // stats
  uint64_t num_nodes = 0;
  uint64_t num_traces = 0;
  uint64_t num_events = 0;
  uint64_t num_conflicts = 0;
  uint64_t num_opaque = 0;
  uint64_t max_depth = 0;
  uint64_t check_admit_empty = 0;
  uint64_t check_admit_opaque = 0;
  uint64_t check_admit_frontier = 0;
  uint64_t check_veto_terminal = 0;
  uint64_t check_veto_rlimit = 0;

 private:
  Node &node(NodeRef ref) { return nodes_[ref]; }
  const Node &node(NodeRef ref) const { return nodes_[ref]; }
  NodeRef append(Node &&node);
  bool IsSaturated(NodeRef ref, uint8_t rlimit) const;

  // Index 1 is a global terminal node; index 2 is the virtual root.
  std::vector<Node> nodes_;
  PredArena pred_arena_;
};

}  // namespace pcbt
```

### pcbt.cpp

**Provenance:** `symsan/driver/aflpp/pcbt.cpp:1-168`; source lines: 168; included: 168; revision: `v2-dev 193cfd74f0bcdc575236cbc39c2832ecf8bb790f (dirty worktree)`; SHA-256: `4ef3bb30a23c8bdeeee2d9ed7c9260428e89b520191793821f6d383d2d7a78ac`

```cpp
#include "pcbt.hpp"

namespace pcbt {

Tree::Tree() : nodes_(kRoot + 1) {
  pred_arena_.nodes.reserve(4096);
}

NodeRef Tree::append(Node &&new_node) {
  if (nodes_.size() == UINT32_MAX) return kUnexplored;
  nodes_.push_back(std::move(new_node));
  return (NodeRef)nodes_.size() - 1;
}

uint32_t Tree::InsertTrace(const std::vector<Event> &events,
                           const dfsan_label_info *table,
                           size_t table_labels) {
  if (events.empty()) return 0;
  num_traces += 1;
  num_events += events.size();

  NodeRef parent = kRoot;
  uint8_t dir = 0;
  uint64_t trace_depth = 0;
  size_t i = 0;
  for (; i < events.size(); ++i) {
    NodeRef next = node(parent).child[dir];
    if (next == kUnexplored) break;
    if (next == kTerminal || node(next).cid != events[i].cid) {
      num_conflicts += 1;
      return 0;
    }
    parent = next;
    dir = events[i].result ? 1 : 0;
    trace_depth += 1;
  }

  if (i == events.size()) {
    if (node(parent).child[dir] == kUnexplored) {
      node(parent).child[dir] = kTerminal;
    }
    return 0;
  }

  RunConverter conv(table, table_labels, &pred_arena_);
  uint32_t created = 0;
  for (; i < events.size(); ++i) {
    Node new_node;
    new_node.cid = events[i].cid;
    new_node.depth = parent == kRoot ? 1 : node(parent).depth + 1;
    new_node.pred = conv.conv(events[i].label);
    if (new_node.pred.opaque) num_opaque += 1;
    NodeRef next = append(std::move(new_node));
    if (next == kUnexplored) return created;
    node(parent).child[dir] = next;
    parent = next;
    dir = events[i].result ? 1 : 0;
    created += 1;
    trace_depth += 1;
  }

  node(parent).child[dir] = kTerminal;
  num_nodes += created;
  if (trace_depth > max_depth) max_depth = trace_depth;
  return created;
}

uint32_t Tree::InsertSuffix(NodeRef parent, uint8_t direction,
                            const std::vector<Event> &events,
                            const dfsan_label_info *table,
                            size_t table_labels) {
  if (parent < kRoot || parent >= nodes_.size() || direction > 1) return 0;
  num_traces += 1;
  num_events += events.size();

  if (events.empty()) {
    node(parent).child[direction] = kTerminal;
    return 0;
  }

  RunConverter conv(table, table_labels, &pred_arena_);
  uint32_t created = 0;
  uint8_t dir = direction;
  NodeRef cur = parent;
  for (const Event &event : events) {
    Node new_node;
    new_node.cid = event.cid;
    new_node.depth = node(cur).depth + 1;
    new_node.pred = conv.conv(event.label);
    if (new_node.pred.opaque) num_opaque += 1;
    NodeRef next = append(std::move(new_node));
    if (next == kUnexplored) return created;
    node(cur).child[dir] = next;
    cur = next;
    dir = event.result ? 1 : 0;
    created += 1;
  }

  node(cur).child[dir] = kTerminal;
  num_nodes += created;
  if (node(cur).depth > max_depth) max_depth = node(cur).depth;
  return created;
}

bool Tree::CheckInput(const uint8_t *input, uint32_t len, NodeRef *out_node,
                      uint8_t *out_dir, uint8_t rlimit) {
  NodeRef cur = node(kRoot).child[0];
  if (cur == kUnexplored) {
    *out_node = kUnexplored;
    *out_dir = 0;
    check_admit_empty += 1;
    return true;
  }

  while (true) {
    const Node &current = node(cur);
    if (current.pred.opaque) {
      *out_node = kUnexplored;
      *out_dir = 0;
      check_admit_opaque += 1;
      return true;
    }
    uint64_t v = 0;
    uint8_t dir = eval_predicate(pred_arena_, current.pred, input, len, &v)
                      ? (v ? 1 : 0)
                      : 0;
    NodeRef next = current.child[dir];
    if (next == kTerminal) {
      *out_node = kUnexplored;
      *out_dir = 0;
      check_veto_terminal += 1;
      return false;
    }
    if (next == kUnexplored) {
      *out_node = cur;
      *out_dir = dir;
      if (current.rCnt[dir] < rlimit) {
        check_admit_frontier += 1;
        return true;
      }
      check_veto_rlimit += 1;
      return false;
    }
    cur = next;
  }
}

bool Tree::IsSaturated(uint8_t rlimit) const {
  NodeRef entry = node(kRoot).child[0];
  return entry != kUnexplored && IsSaturated(entry, rlimit);
}

bool Tree::IsSaturated(NodeRef ref, uint8_t rlimit) const {
  const Node &current = node(ref);
  if (current.pred.opaque) return false;
  for (uint8_t direction = 0; direction != 2; ++direction) {
    NodeRef next = current.child[direction];
    if (next == kTerminal) continue;
    if (next == kUnexplored) {
      if (current.rCnt[direction] < rlimit) return false;
      continue;
    }
    if (!IsSaturated(next, rlimit)) return false;
  }
  return true;
}

}  // namespace pcbt
```

## 4. Complete predicate representation, conversion, and interpreter

The Tree owns one shared predicate arena. RunConverter keeps a per-traced-run
label memo and rolls back a failed root conversion without poisoning later
roots. The interpreter starts at the requested root and uses an iterative
post-order sparse evaluation scratch, so unrelated arena prefixes are not
evaluated.

### pred.hpp

**Provenance:** `symsan/driver/aflpp/pred.hpp:1-95`; source lines: 95; included: 95; revision: `v2-dev 193cfd74f0bcdc575236cbc39c2832ecf8bb790f (dirty worktree)`; SHA-256: `6d1e3204190af9912b4106279ad19c8f60ce936dc9be1200ae44d747f87e9b45`

```cpp
// Self-contained branch predicates for SymAFL v2 PCBT screening.
//
// Tree owns one PredArena for its lifetime. RunConverter converts one traced
// run into that shared post-order PNode array and memoizes only that run's
// union-table labels. A Predicate is a root index into the tree arena, so
// nodes do not retain a per-trace shared_ptr or duplicate expression views.
//
// Integer bit-vector ops only; FP/string/gep subtrees are marked opaque —
// screening treats an opaque node as "cannot decide -> admit".
//
// eval_predicate() interprets a predicate against a concrete input with
// SMT-LIB bit-vector corner semantics (div-by-zero rules, shift>=width,
// exact-width masking).
#pragma once

#include <cstdint>
#include <unordered_map>
#include <vector>

#include "dfsan/dfsan.h"

namespace pcbt {

enum class PKind : uint8_t {
  Opaque = 0,
  Read,   // input bytes: value=byte offset, nbytes=bits/8 (little-endian)
  Const,  // value=constant (masked to bits)
  Add, Sub, Mul, UDiv, SDiv, URem, SRem, Neg,
  Not, And, Or, Xor, Shl, LShr, AShr,
  Equal, Distinct, Ult, Ule, Ugt, Uge, Slt, Sle, Sgt, Sge,
  ZExt, SExt, Extract, Concat,
};

struct PNode {
  uint64_t value;      // Const: value; Read: byte offset; Extract: bit offset
  uint32_t a;          // left/only child index (UINT32_MAX = none)
  uint32_t b;          // right child index (UINT32_MAX = none)
  uint8_t bits;        // result width in bits; for comparisons: operand width
  PKind kind;
};

struct PredArena {
  std::vector<PNode> nodes;  // post-order by label (children before parents)
};

struct Predicate {
  uint32_t root = 0;
  bool opaque = false;
  // input-read set of this predicate: sorted unique (offset, nbytes) pairs
  std::vector<std::pair<uint32_t, uint32_t>> reads;

  bool reads_range(uint32_t lo, uint32_t hi) const {
    for (auto &r : reads) {
      uint32_t rlo = r.first, rhi = r.first + r.second - 1;
      if (rlo <= hi && lo <= rhi) return true;
    }
    return false;
  }
};

// Converts one traced run into the Tree-owned arena. Create once per trace;
// call conv() per branch label. A failed root conversion does not make later
// labels opaque.
class RunConverter {
 public:
  RunConverter(const dfsan_label_info *table, size_t table_labels,
               PredArena *arena);
  // Convert the subtree at `label`; returns a Predicate view into the
  // shared arena (possibly marked opaque).
  Predicate conv(uint32_t label);
 private:
  const dfsan_label_info *table_;
  size_t table_labels_;
  PredArena *arena_;
  size_t run_start_;
  std::unordered_map<uint32_t, uint32_t> label_map_;  // label -> arena index
  std::vector<uint32_t> inserted_labels_;

  uint32_t convert(uint32_t label, size_t depth);
  uint32_t convert_op(const dfsan_label_info *info, uint32_t op,
                      uint32_t op_lo, size_t depth);
  uint32_t add(PKind kind, uint16_t bits, uint32_t a, uint32_t b,
               uint64_t value = 0);
  uint32_t add_const(uint64_t value, uint16_t bits);
  uint32_t conv_child(uint32_t label, uint64_t cval, uint16_t cbits,
                      size_t depth);
};

// Evaluate only the root-reachable DAG against a concrete input. Returns false
// on undefined evaluation (read past input end); on success sets *out to the
// root value (0/1 for comparison roots).
bool eval_predicate(const PredArena &arena, const Predicate &pred,
                    const uint8_t *input, uint32_t len, uint64_t *out);

}  // namespace pcbt
```

### pred.cpp

**Provenance:** `symsan/driver/aflpp/pred.cpp:1-350`; source lines: 350; included: 350; revision: `v2-dev 193cfd74f0bcdc575236cbc39c2832ecf8bb790f (dirty worktree)`; SHA-256: `f9a93cade71c1d57abb0ff1fa61e7c3d85d15bef621e7e4c66ff6da7b656f6e8`

```cpp
#include "pred.hpp"

#include <algorithm>
#include <unordered_map>
#include <unordered_set>

using namespace __dfsan;

namespace pcbt {

namespace {
constexpr uint32_t kNoChild = UINT32_MAX;
constexpr uint32_t kInvalidNode = UINT32_MAX;
constexpr size_t kMaxArenaNodes = 2'000'000;  // per traced run
constexpr size_t kMaxDepth = 256;  // recursion cap -> opaque

struct EvalFrame {
  uint32_t node;
  bool expanded;
};

struct EvalScratch {
  std::unordered_map<uint32_t, uint64_t> values;
  std::vector<EvalFrame> stack;

  void Reset() {
    values.clear();
    stack.clear();
  }
};
}  // namespace

RunConverter::RunConverter(const dfsan_label_info *table, size_t table_labels,
                           PredArena *arena)
    : table_(table), table_labels_(table_labels), arena_(arena),
      run_start_(arena->nodes.size()) {}

uint32_t RunConverter::add(PKind kind, uint16_t bits, uint32_t a, uint32_t b,
                           uint64_t value) {
  if (bits == 0 || bits > 64 ||
      arena_->nodes.size() - run_start_ >= kMaxArenaNodes ||
      arena_->nodes.size() >= kInvalidNode) {
    return kInvalidNode;
  }
  arena_->nodes.push_back({value, a, b, (uint8_t)bits, kind});
  return (uint32_t)arena_->nodes.size() - 1;
}

uint32_t RunConverter::add_const(uint64_t value, uint16_t bits) {
  return add(PKind::Const, bits, kNoChild, kNoChild, value);
}

uint32_t RunConverter::conv_child(uint32_t label, uint64_t cval,
                                  uint16_t cbits, size_t depth) {
  if (label == 0) return add_const(cval, cbits);
  return convert(label, depth + 1);
}

uint32_t RunConverter::convert(uint32_t label, size_t depth) {
  if (depth > kMaxDepth || label >= table_labels_ ||
      label == kInitializingLabel) {
    return kInvalidNode;
  }
  auto it = label_map_.find(label);
  if (it != label_map_.end()) return it->second;

  const size_t nodes_checkpoint = arena_->nodes.size();
  const size_t labels_checkpoint = inserted_labels_.size();
  const dfsan_label_info *info = &table_[label];
  uint32_t op = info->op;
  uint32_t op_lo = op & 0xff;
  uint32_t idx;

  if (op == 0) {
    // raw input byte: offset in op1, input id in op2 (multi-input unused)
    idx = add(PKind::Read, 8, kNoChild, kNoChild, info->op1.i);
  } else if (op_lo == Load) {
    // uload: consecutive input bytes fused into one read
    if (info->l1 == 0 || info->l1 >= table_labels_ || info->l2 == 0 ||
        info->l2 > 8) {
      idx = kInvalidNode;
    } else {
      idx = add(PKind::Read, (uint16_t)(info->l2 * 8), kNoChild, kNoChild,
                table_[info->l1].op1.i);
    }
  } else {
    idx = convert_op(info, op, op_lo, depth);
  }

  if (idx == kInvalidNode) {
    arena_->nodes.resize(nodes_checkpoint);
    while (inserted_labels_.size() > labels_checkpoint) {
      label_map_.erase(inserted_labels_.back());
      inserted_labels_.pop_back();
    }
    return kInvalidNode;
  }
  label_map_.emplace(label, idx);
  inserted_labels_.push_back(label);
  return idx;
}

uint32_t RunConverter::convert_op(const dfsan_label_info *info, uint32_t op,
                                  uint32_t op_lo, size_t depth) {
  uint16_t size = info->size;
  // The local evaluator intentionally supports one machine word. Wider
  // bit-vectors must be conservatively admitted instead of being truncated.
  if (size == 0 || size > 64) return kInvalidNode;
  PKind kind;
  bool unary = false, binary = false;

  switch (op_lo) {
    case Add: kind = PKind::Add; binary = true; break;
    case Sub: kind = PKind::Sub; binary = true; break;
    case Mul: kind = PKind::Mul; binary = true; break;
    case UDiv: kind = PKind::UDiv; binary = true; break;
    case SDiv: kind = PKind::SDiv; binary = true; break;
    case URem: kind = PKind::URem; binary = true; break;
    case SRem: kind = PKind::SRem; binary = true; break;
    case Shl: kind = PKind::Shl; binary = true; break;
    case LShr: kind = PKind::LShr; binary = true; break;
    case AShr: kind = PKind::AShr; binary = true; break;
    case And: kind = PKind::And; binary = true; break;
    case Or: kind = PKind::Or; binary = true; break;
    case Xor: kind = PKind::Xor; binary = true; break;
    case Neg: kind = PKind::Neg; unary = true; break;
    case Not: kind = PKind::Not; unary = true; break;
    case ZExt: kind = PKind::ZExt; unary = true; break;
    case SExt: kind = PKind::SExt; unary = true; break;
    default: break;
  }

  if (op == __dfsan::Extract || op_lo == Trunc) {
    uint64_t off = (op == __dfsan::Extract) ? info->op2.i : 0;
    uint32_t a = conv_child(info->l1, info->op1.i, 64, depth);
    return a == kInvalidNode ? kInvalidNode
                             : add(PKind::Extract, size, a, kNoChild, off);
  }
  if (op == __dfsan::Concat) {
    if (info->l1 == 0 && info->l2 == 0) return kInvalidNode;
    uint16_t cbits1 = size, cbits2 = size;
    if (info->l1 == 0 && info->l2 != 0 && info->l2 < table_labels_) {
      if (table_[info->l2].size > size) return kInvalidNode;
      cbits1 = (uint16_t)(size - table_[info->l2].size);
    }
    if (info->l2 == 0 && info->l1 != 0 && info->l1 < table_labels_) {
      if (table_[info->l1].size > size) return kInvalidNode;
      cbits2 = (uint16_t)(size - table_[info->l1].size);
    }
    uint32_t a = conv_child(info->l1, info->op1.i, cbits1, depth);
    uint32_t b = conv_child(info->l2, info->op2.i, cbits2, depth);
    return a == kInvalidNode || b == kInvalidNode
               ? kInvalidNode : add(PKind::Concat, size, a, b);
  }
  if (op_lo == ICmp) {
    uint32_t p = op >> 8;
    switch (p) {
      case bveq: kind = PKind::Equal; break;
      case bvneq: kind = PKind::Distinct; break;
      case bvugt: kind = PKind::Ugt; break;
      case bvuge: kind = PKind::Uge; break;
      case bvult: kind = PKind::Ult; break;
      case bvule: kind = PKind::Ule; break;
      case bvsgt: kind = PKind::Sgt; break;
      case bvsge: kind = PKind::Sge; break;
      case bvslt: kind = PKind::Slt; break;
      case bvsle: kind = PKind::Sle; break;
      default: return kInvalidNode;
    }
    uint32_t a = conv_child(info->l1, info->op1.i, size, depth);
    uint32_t b = conv_child(info->l2, info->op2.i, size, depth);
    return a == kInvalidNode || b == kInvalidNode
               ? kInvalidNode : add(kind, size, a, b);
  }
  if (unary) {
    uint32_t a = conv_child(info->l1, info->op1.i, size, depth);
    return a == kInvalidNode ? kInvalidNode : add(kind, size, a, kNoChild);
  }
  if (binary) {
    uint32_t a = conv_child(info->l1, info->op1.i, size, depth);
    uint32_t b = conv_child(info->l2, info->op2.i, size, depth);
    return a == kInvalidNode || b == kInvalidNode
               ? kInvalidNode : add(kind, size, a, b);
  }

  // FP ops, string ops, Arg/Free, fmemcmp, GEP artifacts, ... : unsupported
  return kInvalidNode;
}

Predicate RunConverter::conv(uint32_t label) {
  Predicate pred;
  if (label == 0 || label >= table_labels_) {
    pred.opaque = true;
    return pred;
  }

  pred.root = convert(label, 0);
  if (pred.root == kInvalidNode) {
    pred.root = 0;
    pred.opaque = true;
    return pred;
  }

  std::unordered_set<uint32_t> seen;
  std::vector<uint32_t> stack = {pred.root};
  while (!stack.empty()) {
    uint32_t i = stack.back();
    stack.pop_back();
    if (!seen.insert(i).second) continue;
    const PNode &nd = arena_->nodes[i];
    if (nd.kind == PKind::Read)
      pred.reads.emplace_back((uint32_t)nd.value, nd.bits / 8);
    if (nd.a != kNoChild) stack.push_back(nd.a);
    if (nd.b != kNoChild) stack.push_back(nd.b);
  }
  std::sort(pred.reads.begin(), pred.reads.end());
  pred.reads.erase(std::unique(pred.reads.begin(), pred.reads.end()),
                   pred.reads.end());
  return pred;
}

namespace {
inline uint64_t mask_bits(uint64_t v, uint16_t bits) {
  return bits >= 64 ? v : (v & ((1ull << bits) - 1));
}
inline int64_t sext_bits(uint64_t v, uint16_t bits) {
  if (bits >= 64) return (int64_t)v;
  uint64_t m = 1ull << (bits - 1);
  return (int64_t)((v ^ m) - m);
}
}  // namespace

bool eval_predicate(const PredArena &arena, const Predicate &pred,
                    const uint8_t *input, uint32_t len, uint64_t *out) {
  if (pred.opaque || pred.root >= arena.nodes.size()) return false;
  const auto &nodes = arena.nodes;
  static thread_local EvalScratch scratch;
  scratch.Reset();
  scratch.stack.push_back({pred.root, false});

  while (!scratch.stack.empty()) {
    EvalFrame frame = scratch.stack.back();
    scratch.stack.pop_back();
    if (scratch.values.find(frame.node) != scratch.values.end()) continue;
    if (frame.node >= nodes.size()) return false;
    const PNode &nd = nodes[frame.node];
    if (!frame.expanded) {
      scratch.stack.push_back({frame.node, true});
      if (nd.b != kNoChild) scratch.stack.push_back({nd.b, false});
      if (nd.a != kNoChild) scratch.stack.push_back({nd.a, false});
      continue;
    }

    uint64_t a = 0, b = 0;
    if (nd.a != kNoChild) {
      auto it = scratch.values.find(nd.a);
      if (it == scratch.values.end()) return false;
      a = it->second;
    }
    if (nd.b != kNoChild) {
      auto it = scratch.values.find(nd.b);
      if (it == scratch.values.end()) return false;
      b = it->second;
    }
    uint16_t bits = nd.bits;
    uint64_t v;
    switch (nd.kind) {
      case PKind::Opaque: return false;
      case PKind::Read: {
        uint32_t nbytes = nd.bits / 8;
        if (nd.bits == 0 || nd.bits % 8 != 0 || nbytes > 8 ||
            nd.value + nbytes > len) return false;
        v = 0;
        for (uint32_t k = 0; k < nbytes; k++)
          v |= (uint64_t)input[nd.value + k] << (8 * k);
        break;
      }
      case PKind::Const: v = mask_bits(nd.value, bits); break;
      case PKind::Add: v = mask_bits(a + b, bits); break;
      case PKind::Sub: v = mask_bits(a - b, bits); break;
      case PKind::Mul: v = mask_bits(a * b, bits); break;
      case PKind::UDiv:
        v = (b == 0) ? mask_bits(~0ull, bits) : mask_bits(a / b, bits);
        break;
      case PKind::SDiv: {
        int64_t sa = sext_bits(a, bits), sb = sext_bits(b, bits);
        if (sb == 0) {
          v = mask_bits(sa < 0 ? 1 : (uint64_t)-1, bits);
        } else if (sb == -1) {
          v = mask_bits(0 - a, bits);
        } else {
          v = mask_bits((uint64_t)(sa / sb), bits);
        }
        break;
      }
      case PKind::URem: v = (b == 0) ? a : mask_bits(a % b, bits); break;
      case PKind::SRem: {
        int64_t sa = sext_bits(a, bits), sb = sext_bits(b, bits);
        if (sb == 0) {
          v = a;
        } else if (sb == -1) {
          v = 0;
        } else {
          v = mask_bits((uint64_t)(sa % sb), bits);
        }
        break;
      }
      case PKind::Neg: v = mask_bits(0 - a, bits); break;
      case PKind::Not: v = mask_bits(~a, bits); break;
      case PKind::And: v = mask_bits(a & b, bits); break;
      case PKind::Or: v = mask_bits(a | b, bits); break;
      case PKind::Xor: v = mask_bits(a ^ b, bits); break;
      case PKind::Shl: v = (b >= bits) ? 0 : mask_bits(a << b, bits); break;
      case PKind::LShr: v = (b >= bits) ? 0 : (mask_bits(a, bits) >> b); break;
      case PKind::AShr:
        v = b >= bits ? (sext_bits(a, bits) < 0 ? mask_bits(~0ull, bits) : 0)
                      : mask_bits((uint64_t)(sext_bits(a, bits) >> b), bits);
        break;
      case PKind::ZExt: v = mask_bits(a, bits); break;
      case PKind::SExt:
        v = mask_bits((uint64_t)sext_bits(a, nodes[nd.a].bits), bits);
        break;
      case PKind::Extract:
        v = nd.value >= 64 ? 0 : mask_bits(a >> nd.value, bits);
        break;
      case PKind::Concat: {
        uint16_t lo_bits = nodes[nd.b].bits;
        if (lo_bits >= 64) return false;
        v = mask_bits((a << lo_bits) | b, bits);
        break;
      }
      case PKind::Equal: v = (mask_bits(a, bits) == mask_bits(b, bits)); break;
      case PKind::Distinct: v = (mask_bits(a, bits) != mask_bits(b, bits)); break;
      case PKind::Ult: v = (mask_bits(a, bits) < mask_bits(b, bits)); break;
      case PKind::Ule: v = (mask_bits(a, bits) <= mask_bits(b, bits)); break;
      case PKind::Ugt: v = (mask_bits(a, bits) > mask_bits(b, bits)); break;
      case PKind::Uge: v = (mask_bits(a, bits) >= mask_bits(b, bits)); break;
      case PKind::Slt: v = (sext_bits(a, bits) < sext_bits(b, bits)); break;
      case PKind::Sle: v = (sext_bits(a, bits) <= sext_bits(b, bits)); break;
      case PKind::Sgt: v = (sext_bits(a, bits) > sext_bits(b, bits)); break;
      case PKind::Sge: v = (sext_bits(a, bits) >= sext_bits(b, bits)); break;
      default: return false;
    }
    scratch.values.emplace(frame.node, v);
  }
  *out = scratch.values.find(pred.root)->second;
  return true;
}

}  // namespace pcbt
```

sed: -e expression #1, char 6: missing command
## 5. Complete runtime condition-event writer

The runtime receives the control block configured by the mutator. The writer
shows that suffix modes suppress export only: the child still executes DFSan
propagation and constructs labels. solver_common.h, sanitizer runtime helpers,
and flag definitions are external dependencies of this included file.

**Provenance:** `symsan/backend/solver_common.cpp:1-174`; source lines: 174; included: 174; revision: `193cfd74f0bcdc575236cbc39c2832ecf8bb790f`; SHA-256: `37a41b73aa67ca36dd4483eae3612841ce5386f69abd51311b87458942e6ba4e`

```cpp
/*
  Common code shared between fastgen and thoroupy solvers.

   ------------------------------------------------

   Written by Chengyu Song <csong@cs.ucr.edu> and
              Ju Chen <jchen757@ucr.edu>

   Copyright 2021-2025 UC Riverside. All rights reserved.

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at:

     http://www.apache.org/licenses/LICENSE-2.0

 */

#include "solver_common.h"

#include <fcntl.h>
#include <string.h>
#include <sys/mman.h>

//===----------------------------------------------------------------------===//
// Shared Global State
//===----------------------------------------------------------------------===//

uint32_t __instance_id;
uint32_t __session_id;
int __pipe_fd;
int __control_pipe_fd;
static uint64_t __taint_symbolic_depth;
static symafl_single_pass_control *__single_pass;

void InitializeSinglePassCapture() {
  if (internal_strcmp(flags().single_pass_name, "") == 0) return;
  if (flags().single_pass_size < sizeof(symafl_single_pass_control)) {
    Printf("FATAL: invalid single-pass capture size %zu\n",
           flags().single_pass_size);
    Die();
  }

  int fd = shm_open(flags().single_pass_name, O_RDWR, S_IRUSR | S_IWUSR);
  if (fd == -1) {
    Printf("FATAL: cannot open single-pass capture buffer\n");
    Die();
  }
  uptr mapped = internal_mmap(nullptr, flags().single_pass_size,
                              PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
  internal_close(fd);
  int err;
  if (internal_iserror(mapped, &err)) {
    Printf("FATAL: cannot map single-pass capture buffer: %s\n",
           strerror(err));
    Die();
  }
  __single_pass = reinterpret_cast<symafl_single_pass_control *>(mapped);
  if (__single_pass->magic != SYMAFL_SINGLE_PASS_MAGIC ||
      __single_pass->version != SYMAFL_SINGLE_PASS_VERSION ||
      symafl_single_pass_size(__single_pass->event_capacity) >
          flags().single_pass_size) {
    Printf("FATAL: invalid single-pass capture header\n");
    Die();
  }
}

bool IsTraceStreamEnabled() {
  if (__pipe_fd < 0) return false;
  if (!__single_pass) return true;
  uint32_t mode = __atomic_load_n(&__single_pass->mode, __ATOMIC_ACQUIRE);
  return mode == SYMAFL_TRACE_FULL_STREAM ||
         mode == SYMAFL_TRACE_SUFFIX_PIPE;
}

//===----------------------------------------------------------------------===//
// Shared Helper Functions
//===----------------------------------------------------------------------===//

void __taint_send_cond(dfsan_label label, uint8_t result,
                       uint8_t add_nested, uint8_t loop_flag,
                       uint32_t cid, void *addr) {

  // AFL's SymAFL extension selects one of four per-child modes through the
  // shared control block. FULL_STREAM writes bootstrap events to the pipe;
  // SUFFIX_SHM writes the normal post-frontier suffix to bounded shared memory;
  // SUFFIX_PIPE is the overflow-replay fallback and writes that suffix to pipe.
  // Standalone launcher/direct tracing has no single-pass control block.
  // Preserve its established pipe semantics: a configured pipe is a full
  // event stream. The control block is only present for forkserver runs,
  // where the mutator explicitly selects OFF, FULL_STREAM, SUFFIX_SHM, or
  // SUFFIX_PIPE.
  uint32_t trace_mode = __single_pass
      ? __atomic_load_n(&__single_pass->mode, __ATOMIC_ACQUIRE)
      : (__pipe_fd >= 0 ? SYMAFL_TRACE_FULL_STREAM : SYMAFL_TRACE_OFF);
  if (trace_mode == SYMAFL_TRACE_SUFFIX_SHM &&
      __atomic_load_n(&__single_pass->armed, __ATOMIC_ACQUIRE)) {
    if (label == 0 || label == kInitializingLabel) return;
    if (++__taint_symbolic_depth <= __single_pass->skip_depth) return;
    // Once the bounded suffix buffer has overflowed, this child must not
    // touch the event array again. The mutator will discard the partial
    // suffix and replay this coverage-gaining input through pipe-suffix.
    if (__atomic_load_n(&__single_pass->overflow, __ATOMIC_ACQUIRE)) return;
    uint32_t index = __atomic_fetch_add(&__single_pass->event_count, 1,
                                        __ATOMIC_RELAXED);
    if (index >= __single_pass->event_capacity) {
      __atomic_store_n(&__single_pass->overflow, 1, __ATOMIC_RELEASE);
      return;
    }
    __single_pass->events[index] = {cid, label, result, {0, 0, 0}};
    return;
  }

  if (trace_mode != SYMAFL_TRACE_FULL_STREAM &&
      trace_mode != SYMAFL_TRACE_SUFFIX_PIPE) {
    return;
  }

  if (__pipe_fd < 0) return;

  // Pipe suffix replay keeps concolic execution and AST construction intact;
  // it only suppresses already-known PCBT prefix condition events. The
  // forkserver cannot reparse TAINT_OPTIONS for every child, so use the shared
  // skip depth in that case. The flag remains for standalone launcher tracing.
  int skip_depth = flags().trace_skip_depth;
  if (trace_mode == SYMAFL_TRACE_SUFFIX_PIPE) {
    skip_depth = static_cast<int>(__single_pass->skip_depth);
  }
  if (skip_depth >= 0) {
    if (label == 0 || label == kInitializingLabel) return;
    if (++__taint_symbolic_depth <=
        static_cast<uint64_t>(skip_depth)) {
      return;
    }
  }

  uint16_t flags = 0;
  if (add_nested) flags |= F_ADD_CONS;

  // set the loop flags according to branching results
  switch (loop_flag) {
    case TrueBranchLoopExit:
      flags |= result ? F_LOOP_EXIT : F_LOOP_LATCH;
      break;
    case TrueBranchLoopLatch:
      flags |= result ? F_LOOP_LATCH : F_LOOP_EXIT;
      break;
    case FalseBranchLoopExit:
      flags |= result ? F_LOOP_LATCH : F_LOOP_EXIT;
      break;
    case FalseBranchLoopLatch:
      flags |= result ? F_LOOP_EXIT : F_LOOP_LATCH;
      break;
    default:
      // No loop flag or unrecognized flag, do nothing
      break;
  }

  // send info
  pipe_msg msg = {
    .msg_type = cond_type,
    .flags = flags,
    .instance_id = __instance_id,
    .addr = (uptr)addr,
    .context = __taint_trace_callstack,
    .id = cid,
    .label = label,
    .result = result
  };

  if (internal_write(__pipe_fd, &msg, sizeof(msg)) < 0) {
    Die();
  }
}
```

## 6. AFL++ parent pipe-drain lifecycle

This is the complete trace-aware drain and wait function. Its external state
fields are declared in AFLplusplus/include/forkserver.h; the mutator assigns
fsrv.sym_trace_fd during initialization. AFL++ accumulates raw bytes only; the
mutator's decode_full_stream is the semantic consumer.

**Provenance:** `AFLplusplus/src/afl-forkserver.c:394-482`; source lines: 2292; included: 89; revision: `ef727c60875e17bac8400d0ec1025e6e856a21b8`; SHA-256: `7665e4220d55bb7ed142cfc63f0e923d3a22dbf0d57e13a5041188f61d362f7e`

```c
/* Drain the optional SymAFL event pipe without interpreting its frames. This
   runs in the afl-fuzz parent while it waits on the target forkserver; the
   custom mutator owns framing. AFL only prevents a long full trace from
   blocking the forkserver child on a full pipe. */
static void drain_sym_trace(afl_forkserver_t *fsrv) {

  if (fsrv->sym_trace_fd < 0) return;
  u8 buffer[0x10000];
  while (1) {

    ssize_t got = read(fsrv->sym_trace_fd, buffer, sizeof(buffer));
    if (got <= 0) {

      if (got < 0 && errno != EAGAIN && errno != EWOULDBLOCK) {

        WARNF("SymAFL event pipe read failed: %s", strerror(errno));

      }
      return;

    }

    size_t needed = fsrv->sym_trace_len + (size_t)got;
    if (needed > fsrv->sym_trace_cap) {

      size_t capacity = fsrv->sym_trace_cap ? fsrv->sym_trace_cap : 0x10000;
      while (capacity < needed) capacity *= 2;
      fsrv->sym_trace_buf = ck_realloc(fsrv->sym_trace_buf, capacity);
      if (!fsrv->sym_trace_buf) { PFATAL("SymAFL trace buffer alloc"); }
      fsrv->sym_trace_cap = capacity;

    }

    memcpy(fsrv->sym_trace_buf + fsrv->sym_trace_len, buffer, (size_t)got);
    fsrv->sym_trace_len += (size_t)got;

  }

}

/* Like read_s32_timed(), while the afl-fuzz parent also continuously drains
   the optional SymAFL full-trace pipe. */
static u32 __attribute__((hot)) read_s32_timed_with_trace(
    afl_forkserver_t *fsrv, s32 *buf, u32 timeout_ms,
    volatile u8 *stop_soon_p) {

  u64 start = get_cur_time();
  while (1) {

    u64 now = get_cur_time();
    if (now - start > timeout_ms) return timeout_ms + 1;
    u32 remaining = timeout_ms - (u32)(now - start);
    fd_set readfds;
    FD_ZERO(&readfds);
    FD_SET(fsrv->fsrv_st_fd, &readfds);
    int max_fd = fsrv->fsrv_st_fd;
    if (fsrv->sym_trace_fd >= 0) {

      FD_SET(fsrv->sym_trace_fd, &readfds);
      if (fsrv->sym_trace_fd > max_fd) max_fd = fsrv->sym_trace_fd;

    }
    struct timeval wait = {.tv_sec = remaining / 1000,
                           .tv_usec = (remaining % 1000) * 1000};
    int ready = select(max_fd + 1, &readfds, NULL, NULL, &wait);
    if (ready < 0) {

      if (errno == EINTR && !*stop_soon_p) continue;
      return 0;

    }
    if (ready == 0) return timeout_ms + 1;
    if (fsrv->sym_trace_fd >= 0 && FD_ISSET(fsrv->sym_trace_fd, &readfds)) {
      drain_sym_trace(fsrv);
    }
    if (FD_ISSET(fsrv->fsrv_st_fd, &readfds)) {

      ssize_t len_read = read(fsrv->fsrv_st_fd, buf, 4);
      if (len_read != 4) return 0;
      drain_sym_trace(fsrv);
      // AFL++ reserves zero for forkserver communication failure. A child
      // completing within the same millisecond is still a valid execution.
      u32 elapsed = (u32)(get_cur_time() - start);
      return elapsed ? elapsed : 1;

    }

  }

```

## 7. AFL++ concrete-phase switch

The following state fields are the mutator-to-scheduler handoff. The switch
function is complete: it retargets the forkserver, handles map-size growth,
resets coverage-derived state, preserves queue files, recalibrates them, and
culls the concrete bitmap.

### State fields

**Provenance:** `AFLplusplus/include/afl-fuzz.h:597-612`; source lines: 1464; included: 16; revision: `ef727c60875e17bac8400d0ec1025e6e856a21b8`; SHA-256: `4599d47504d0d052bef4764af8cbf4edc77dca1567249933fb5d95dcc191fc04`

```c
      shmem_testcase_mode,              /* If sharedmem testcases are used  */
      expand_havoc,                /* perform expensive havoc after no find */
      cycle_schedules,                  /* cycle power schedules?           */
      old_seed_selection,               /* use vanilla afl seed selection   */
      reinit_table,                     /* reinit the queue weight table    */
      pcbt_mode,                        /* SymAFL PCBT concolic phase       */
      pcbt_switch_pending,              /* restart with concrete target     */
      pcbt_concrete_active;             /* concrete phase is live           */

  u8 *virgin_bits,                      /* Regions yet untouched by fuzzing */
      *virgin_tmout,                    /* Bits we haven't seen in tmouts   */
      *virgin_crash;                    /* Bits we haven't seen in crashes  */

  u8 *pcbt_concrete_target;             /* concrete forkserver executable   */

  double *alias_probability;            /* alias weighted probabilities     */
```

### switch_pcbt_to_concrete

**Provenance:** `AFLplusplus/src/afl-fuzz.c:546-659`; source lines: 3780; included: 114; revision: `ef727c60875e17bac8400d0ec1025e6e856a21b8`; SHA-256: `6510ea1d20993cdfba8af4d3333064242ad910c409bf2a2a5bb293b91dce9a04`

```c
/* PCBT starts on the concolic build, whose edge IDs intentionally do not
   describe the concrete build. Once the mutator proves the tree saturated,
   replace the forkserver only at this scheduler boundary. The current queue
   remains useful input, but every coverage-derived property is rebuilt. */
static void switch_pcbt_to_concrete(afl_state_t *afl) {

  if (!afl->pcbt_switch_pending) return;
  if (!afl->pcbt_mode || !afl->pcbt_concrete_target) {

    FATAL("PCBT requested a concrete switch without a concrete target");

  }
  if (afl->fsrv.qemu_mode || afl->fsrv.frida_mode || afl->fsrv.cs_mode ||
      afl->unicorn_mode) {

    FATAL("PCBT concrete fallback supports native forkserver targets only");

  }

  ACTF("PCBT saturated; restarting forkserver with concrete target %s",
       afl->pcbt_concrete_target);

  afl->pcbt_switch_pending = 0;
  afl->pcbt_concrete_active = 1;
  afl_fsrv_kill(&afl->fsrv);

  ck_free(afl->fsrv.target_path);
  afl->fsrv.target_path = ck_strdup(afl->pcbt_concrete_target);
  ck_free(afl->argv[0]);
  afl->argv[0] = ck_strdup(afl->pcbt_concrete_target);

  // Start once to learn the concrete target's requested map size. The two
  // builds may have different edge counts; the map is therefore resized when
  // needed before the fresh concrete coverage universe is initialized.
  u32 map_size = afl->fsrv.map_size;
  afl_fsrv_start(&afl->fsrv, afl->argv, &afl->stop_soon,
                 afl->afl_env.afl_debug_child);
  if (afl->fsrv.real_map_size > map_size) {

    u32 new_map_size = afl->fsrv.real_map_size;
    afl_fsrv_kill(&afl->fsrv);
    afl->virgin_bits = ck_realloc(afl->virgin_bits, new_map_size);
    afl->virgin_tmout = ck_realloc(afl->virgin_tmout, new_map_size);
    afl->virgin_crash = ck_realloc(afl->virgin_crash, new_map_size);
    afl->var_bytes = ck_realloc(afl->var_bytes, new_map_size);
    afl->top_rated = ck_realloc(afl->top_rated,
                                new_map_size * sizeof(void *));
    afl->clean_trace = ck_realloc(afl->clean_trace, new_map_size);
    afl->clean_trace_custom = ck_realloc(afl->clean_trace_custom,
                                         new_map_size);
    afl->first_trace = ck_realloc(afl->first_trace, new_map_size);
    afl->map_tmp_buf = ck_realloc(afl->map_tmp_buf, new_map_size);
    afl_shm_deinit(&afl->shm);
    afl->fsrv.map_size = new_map_size;
    afl->fsrv.trace_bits =
        afl_shm_init(&afl->shm, new_map_size, afl->non_instrumented_mode);
    map_size = new_map_size;
    afl_fsrv_start(&afl->fsrv, afl->argv, &afl->stop_soon,
                   afl->afl_env.afl_debug_child);

  }

  memset(afl->virgin_bits, 0xff, map_size);
  memset(afl->virgin_tmout, 0xff, map_size);
  memset(afl->virgin_crash, 0xff, map_size);
  memset(afl->var_bytes, 0, map_size);
  memset(afl->top_rated, 0, map_size * sizeof(void *));
  memset(afl->clean_trace, 0, map_size);
  memset(afl->clean_trace_custom, 0, map_size);
  memset(afl->first_trace, 0, map_size);

  afl->total_bitmap_size = 0;
  afl->total_bitmap_entries = 0;
  afl->queued_with_cov = 0;
  afl->queued_variable = 0;
  afl->var_byte_count = 0;
  afl->queued_favored = 0;
  afl->pending_favored = 0;
  afl->pending_not_fuzzed = 0;
  afl->smallest_favored = -1;
  afl->score_changed = 1;
  afl->reinit_table = 1;

  for (u32 i = 0; i < afl->queued_items; ++i) {

    struct queue_entry *q = afl->queue_buf[i];
    if (!q) continue;
    ck_free(q->trace_mini);
    q->trace_mini = NULL;
    q->tc_ref = 0;
    q->exec_cksum = 0;
    q->exec_us = 0;
    q->bitmap_size = 0;
    q->handicap = 0;
    q->cal_failed = 0;
    q->has_new_cov = false;
    q->var_behavior = false;
    q->favored = false;
    q->was_fuzzed = false;
    q->fuzz_level = 0;
    if (!q->disabled) ++afl->pending_not_fuzzed;

  }

  // This is the concrete bootstrap: retain all discovered queue files, but
  // calibrate each one against the fresh bitmap before ordinary AFL resumes.
  afl->queue_cur = NULL;
  afl->current_entry = 0;
  perform_dry_run(afl);
  cull_queue(afl);
  OKF("Concrete forkserver ready; bootstrapped %u retained queue entries",
      afl->queued_items);

}
```

### Scheduler boundary

**Provenance:** `AFLplusplus/src/afl-fuzz.c:3167-3167`; source lines: 3780; included: 1; revision: `ef727c60875e17bac8400d0ec1025e6e856a21b8`; SHA-256: `6510ea1d20993cdfba8af4d3333064242ad910c409bf2a2a5bb293b91dce9a04`

```c
    switch_pcbt_to_concrete(afl);
```

## Verification and non-implementation boundaries

This excerpt refresh adds no new evidence beyond the PCBT-structure matrix
recorded in [status.md](status.md): the SymSan build, direct/AFL trace checks,
long pipe drain, three transport modes, and the PCBT-to-concrete smoke.
Use [evaluation.md](evaluation.md) for experiment design and required focused
regressions.

The following boundaries are intentionally not represented as active
implementation excerpts:

- Memerr/UCSan finding binding is planned only. The mutator decoder maintains
  frame alignment for selected non-condition messages but inserts condition
  events only.
- Timeout and memerr counters are declared in my_mutator_t, but the current
  recorded implementation paths do not increment them.
- Jigsaw is retained under symsan/solvers/jigsaw/ but is not part of the PCBT
  hot path; the included pred.cpp interpreter is the active evaluator.
- Short-input direction selection and the caller-owned suffix precondition
  remain engineering gaps with the evidence labels recorded in [status.md](status.md).

## Regeneration rule

Never hand-patch code inside an excerpt. When an included source file, selected
range, submodule revision, or summarized code risk changes, regenerate the
affected complete block from the local snapshot; update its provenance, the
snapshot header, and only the source-map/freshness text made stale by that
change. Leave unchanged blocks byte-for-byte intact.
