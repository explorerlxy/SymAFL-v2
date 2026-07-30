// SymAFL v2 smoke-test target: magic-byte parser with symbolic branches.
// PCBT requires two target builds. Build the concolic target with SymSan plus
// AFL's runtime and the init shim, then build the normal concrete target:
//   clang-18 -c tests/afl_init_shim.c -o /tmp/afl-init-shim.o
//   KO_CC=clang-18 KO_CXX=clang++-18 KO_USE_FASTGEN=1 \
//   $SYMSAN/build/bin/ko-clang -O1 -fno-sanitize-link-runtime \
//     -fsanitize-coverage=trace-pc-guard tests/toy.c \
//     $AFLPP/afl-compiler-rt.o /tmp/afl-init-shim.o -o tests/toy
//   $AFLPP/afl-clang-fast -O1 tests/toy.c -o tests/toy-afl
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
  if (argc < 2) { fprintf(stderr, "usage: %s <file>\n", argv[0]); return 1; }
  FILE *f = fopen(argv[1], "rb");
  if (!f) return 1;
  unsigned char buf[64];
  size_t n = fread(buf, 1, sizeof(buf), f);
  fclose(f);
  if (n < 4) return 0;

  if (buf[0] == 'S') {
    if (buf[1] == 'Y') {
      if (buf[2] == 'M') {
        if (buf[3] == 'A') {
          if (n >= 8 && buf[4] == 'F' && buf[5] == 'L') {
            // deep state: arithmetic guard
            unsigned v = buf[6] * 256u + buf[7];
            if (v > 50000) {
              // simulated bug: deliberate crash for crash-path testing
              volatile int *p = NULL;
              *p = 1;
            }
          }
        }
      }
    }
  }
  if (n >= 6 && buf[0] == 'R' && buf[1] == 'S' && buf[2] == 'A' &&
      buf[3] == 'N') {
    // second magic-word family: multiplication guard (harder for havoc)
    unsigned a = buf[4], b = buf[5];
    if (a * b == 0xBEEF) {
      abort();
    }
  }
  return 0;
}
