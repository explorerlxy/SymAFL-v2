// Microbenchmark for the PCBT predicate interpreter (pred.cpp).
// Measures ns/eval and ns/op for synthetic predicates of varying sizes,
// and simulated tree walks of varying path lengths. No fuzzer involved —
// this isolates the interpreter's true cost.
#include <chrono>
#include <cstdio>
#include <cstring>
#include <vector>

#include "pred.hpp"

using namespace pcbt;

// Build a synthetic predicate: a chain of `n` arithmetic/bit ops over
// input-byte reads and inline constants, ending in a comparison.
static PredicatePtr make_pred(size_t n, uint16_t bits = 32) {
  auto p = std::make_shared<Predicate>();
  p->nodes.reserve(n + 3);
  // v0 = Read(0)
  p->nodes.push_back({PKind::Read, 8, UINT32_MAX, UINT32_MAX, 0, 1});
  size_t cur = 0;
  static const PKind ops[] = {PKind::Add, PKind::Xor, PKind::And,
                              PKind::Or,  PKind::Mul, PKind::Sub};
  for (size_t i = 1; i <= n; i++) {
    // const_i
    p->nodes.push_back({PKind::Const, bits, UINT32_MAX, UINT32_MAX,
                        0x9e3779b9u * (uint32_t)i, 0});
    size_t c = p->nodes.size() - 1;
    // widen cur to `bits` if needed
    if (p->nodes[cur].bits != bits) {
      p->nodes.push_back({PKind::ZExt, bits, (uint32_t)cur, UINT32_MAX, 0, 0});
      cur = p->nodes.size() - 1;
    }
    p->nodes.push_back({ops[i % 6], bits, (uint32_t)cur, (uint32_t)c, 0, 0});
    cur = p->nodes.size() - 1;
    // every 8 ops, fold in another input byte
    if (i % 8 == 0) {
      p->nodes.push_back({PKind::Read, 8, UINT32_MAX, UINT32_MAX,
                          (uint64_t)(i / 8), 1});
      size_t r = p->nodes.size() - 1;
      p->nodes.push_back({PKind::ZExt, bits, (uint32_t)r, UINT32_MAX, 0, 0});
      r = p->nodes.size() - 1;
      p->nodes.push_back({PKind::Xor, bits, (uint32_t)cur, (uint32_t)r, 0, 0});
      cur = p->nodes.size() - 1;
    }
  }
  // final: cur != 0  (comparison root, like a real branch condition)
  p->nodes.push_back({PKind::Const, bits, UINT32_MAX, UINT32_MAX, 0, 0});
  size_t z = p->nodes.size() - 1;
  p->nodes.push_back({PKind::Distinct, bits, (uint32_t)cur, (uint32_t)z, 0, 0});
  return p;
}

template <typename F>
static double bench(F &&f, int iters) {
  auto t0 = std::chrono::steady_clock::now();
  for (int i = 0; i < iters; i++) f();
  auto t1 = std::chrono::steady_clock::now();
  return std::chrono::duration<double, std::nano>(t1 - t0).count() / iters;
}

int main() {
  uint8_t input[64];
  memset(input, 0xA5, sizeof(input));

  printf("== single predicate eval, varying AST size ==\n");
  for (size_t n : {10UL, 50UL, 200UL}) {
    auto p = make_pred(n);
    uint64_t out, sink = 0;
    double ns2 = bench([&] {
      eval_predicate(*p, input, sizeof(input), &out);
      sink += out;
    }, 200000);
    printf("nodes=%5zu  %8.1f ns/eval  (%5.2f ns/op)  [sink=%llu]\n",
           p->nodes.size(), ns2, ns2 / p->nodes.size(),
           (unsigned long long)sink);
  }

  printf("== tree walk: K predicates of ~50 nodes along a path ==\n");
  std::vector<PredicatePtr> chain;
  for (int i = 0; i < 1000; i++) chain.push_back(make_pred(20));
  for (size_t k : {10UL, 100UL, 1000UL}) {
    uint64_t out, acc = 0;
    double ns = bench([&] {
      acc = 0;
      for (size_t i = 0; i < k; i++) {
        if (!eval_predicate(*chain[i], input, sizeof(input), &out)) break;
        acc += out;
      }
    }, 20000);
    printf("path_len=%4zu  %9.1f ns/candidate  (%5.2f M candidates/s)\n", k, ns,
           1e3 / ns);
    if (acc == 12345) printf("!");
  }
  return 0;
}
