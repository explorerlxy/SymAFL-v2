// Local-only PCBT pipe-drain regression target. A 64 KiB input takes one
// symbolic branch per byte, producing more than 2 MiB of condition records.
// That exceeds a Linux pipe buffer and deadlocks unless AFL++ drains the trace
// pipe while its forkserver child is still running.
#include <stdint.h>
#include <stdio.h>

int main(int argc, char **argv) {
  if (argc != 2) return 1;

  FILE *f = fopen(argv[1], "rb");
  if (!f) return 1;
  unsigned char buf[65536];
  size_t n = fread(buf, 1, sizeof(buf), f);
  fclose(f);

  volatile uint32_t total = 0;
  for (size_t i = 0; i < n; ++i) {
    volatile unsigned char value = buf[i];
    if ((value ^ (unsigned char)i) & 1) {
      total += value;
    } else {
      total ^= value;
    }
  }
  return (int)(total & 0);
}
