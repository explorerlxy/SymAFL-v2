// Microbenchmark for the PCBT predicate interpreter (pred.cpp).
// Measures root-reachable evaluation rather than a full arena-prefix scan.
#include <chrono>
#include <cstdio>
#include <cstring>
#include <vector>

#include "pred.hpp"

using namespace pcbt;

namespace {
constexpr uint32_t kNoChild = UINT32_MAX;

struct SyntheticPredicate {
  PredArena arena;
  Predicate pred;
};

static uint32_t add(SyntheticPredicate *pred, PKind kind, uint8_t bits,
                    uint32_t a = kNoChild, uint32_t b = kNoChild,
                    uint64_t value = 0) {
  pred->arena.nodes.push_back({value, a, b, bits, kind});
  return (uint32_t)pred->arena.nodes.size() - 1;
}

static SyntheticPredicate make_pred(size_t n, uint8_t bits = 32) {
  SyntheticPredicate pred;
  pred.arena.nodes.reserve(n * 3 + 3);
  uint32_t cur = add(&pred, PKind::Read, 8, kNoChild, kNoChild, 0);
  static const PKind ops[] = {PKind::Add, PKind::Xor, PKind::And,
                              PKind::Or, PKind::Mul, PKind::Sub};
  for (size_t i = 1; i <= n; i++) {
    uint32_t c = add(&pred, PKind::Const, bits, kNoChild, kNoChild,
                     0x9e3779b9u * (uint32_t)i);
    if (pred.arena.nodes[cur].bits != bits) {
      cur = add(&pred, PKind::ZExt, bits, cur);
    }
    cur = add(&pred, ops[i % 6], bits, cur, c);
    if (i % 8 == 0) {
      uint32_t r = add(&pred, PKind::Read, 8, kNoChild, kNoChild, i / 8);
      r = add(&pred, PKind::ZExt, bits, r);
      cur = add(&pred, PKind::Xor, bits, cur, r);
    }
  }
  uint32_t zero = add(&pred, PKind::Const, bits);
  pred.pred.root = add(&pred, PKind::Distinct, bits, cur, zero);
  return pred;
}

template <typename F>
static double bench(F &&f, int iters) {
  auto t0 = std::chrono::steady_clock::now();
  for (int i = 0; i < iters; i++) f();
  auto t1 = std::chrono::steady_clock::now();
  return std::chrono::duration<double, std::nano>(t1 - t0).count() / iters;
}
}  // namespace

int main() {
  uint8_t input[64];
  memset(input, 0xA5, sizeof(input));

  printf("== single predicate eval, varying AST size ==\n");
  for (size_t n : {10UL, 50UL, 200UL}) {
    auto pred = make_pred(n);
    uint64_t out, sink = 0;
    double ns = bench([&] {
      eval_predicate(pred.arena, pred.pred, input, sizeof(input), &out);
      sink += out;
    }, 200000);
    printf("nodes=%5zu  %8.1f ns/eval  (%5.2f ns/op)  [sink=%llu]\n",
           pred.arena.nodes.size(), ns, ns / pred.arena.nodes.size(),
           (unsigned long long)sink);
  }

  printf("== tree walk: K predicates of ~50 nodes along a path ==\n");
  std::vector<SyntheticPredicate> chain;
  for (int i = 0; i < 1000; i++) chain.push_back(make_pred(20));
  for (size_t k : {10UL, 100UL, 1000UL}) {
    uint64_t out, acc = 0;
    double ns = bench([&] {
      acc = 0;
      for (size_t i = 0; i < k; i++) {
        if (!eval_predicate(chain[i].arena, chain[i].pred, input,
                            sizeof(input), &out)) break;
        acc += out;
      }
    }, 20000);
    printf("path_len=%4zu  %9.1f ns/candidate  (%5.2f M candidates/s)\n", k,
           ns, 1e3 / ns);
    if (acc == 12345) printf("!");
  }
  return 0;
}
