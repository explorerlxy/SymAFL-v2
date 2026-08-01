// Focused PCBT predicate-conversion regression.
#include <cassert>
#include <cstdint>
#include <vector>

#include "pred.hpp"

using namespace __dfsan;
using namespace pcbt;

static void set_raw(dfsan_label_info *table, uint32_t label, uint32_t offset) {
  table[label].op = 0;
  table[label].size = 8;
  table[label].op1.i = offset;
}

int main() {
  // A 1024-deep integer expression must convert without recursive depth
  // failure, and still evaluate to its concrete branch result.
  std::vector<dfsan_label_info> deep(1027);
  set_raw(deep.data(), 1, 0);
  for (uint32_t i = 2; i != 1026; ++i) {
    deep[i].l1 = i - 1;
    deep[i].op = Add;
    deep[i].size = 8;
    deep[i].op2.i = 1;
  }
  deep[1026].l1 = 1025;
  deep[1026].op = (bveq << 8) | ICmp;
  deep[1026].size = 8;
  deep[1026].op2.i = 6;
  PredArena arena;
  RunConverter deep_converter(deep.data(), deep.size(), &arena);
  Predicate deep_pred = deep_converter.conv(1026);
  assert(!deep_pred.opaque);
  uint8_t input[] = {6};
  uint64_t value = 0;
  assert(eval_predicate(arena, deep_pred, input, sizeof(input), &value));
  assert(value == 1);

  // fmemcmp is total for the scalar byte range represented in its label and
  // only accepted when compared directly with zero.
  std::vector<dfsan_label_info> memcmp(4);
  set_raw(memcmp.data(), 1, 0);
  memcmp[2].l1 = 1;
  memcmp[2].l2 = 4;
  memcmp[2].op = Load;
  memcmp[2].size = 32;
  memcmp[3].l1 = 2;
  memcmp[3].op = fmemcmp;
  memcmp[3].size = 4;
  memcmp[3].op2.i = 0x44332211U;
  std::vector<dfsan_label_info> memcmp_root(5);
  // Keep the first four entries and add the comparison root.
  for (uint32_t i = 0; i != 4; ++i) memcmp_root[i] = memcmp[i];
  memcmp_root[4].l1 = 3;
  memcmp_root[4].op = (bveq << 8) | ICmp;
  memcmp_root[4].size = 32;
  PredArena memcmp_arena;
  RunConverter memcmp_converter(memcmp_root.data(), memcmp_root.size(),
                                 &memcmp_arena);
  Predicate memcmp_pred = memcmp_converter.conv(4);
  assert(!memcmp_pred.opaque);
  uint8_t magic[] = {0x11, 0x22, 0x33, 0x44};
  assert(eval_predicate(memcmp_arena, memcmp_pred, magic, sizeof(magic),
                        &value));
  assert(value == 1);
  magic[0] = 0x10;
  assert(eval_predicate(memcmp_arena, memcmp_pred, magic, sizeof(magic),
                        &value));
  assert(value == 0);

  // Comparing a memcmp result with a nonzero integer is not defined by C's
  // sign-only result contract and must remain an explicit unsupported case.
  memcmp_root[4].op2.i = 1;
  PredArena rejected_arena;
  RunConverter rejected_converter(memcmp_root.data(), memcmp_root.size(),
                                  &rejected_arena);
  Predicate rejected = rejected_converter.conv(4);
  assert(rejected.opaque);
  assert(rejected.error == PredError::UnsupportedOp);
  return 0;
}
