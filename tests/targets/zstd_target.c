// SymAFL v2 zstd target: decompress a zstd frame from a file (argv[1]).
// Based on benchmarks/realworld/harness/zstd_harness.c (v1), switched from
// stdin to file input so it uses the proven taint_file path.
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include <zstd.h>

#define MAX_INPUT_SIZE (32u * 1024u * 1024u)
#define MAX_OUTPUT_SIZE (128u * 1024u * 1024u)

int main(int argc, char **argv) {
  if (argc < 2) { fprintf(stderr, "usage: %s <file>\n", argv[0]); return 2; }
  FILE *f = fopen(argv[1], "rb");
  if (!f) return 2;
  fseek(f, 0, SEEK_END);
  long sz = ftell(f);
  fseek(f, 0, SEEK_SET);
  if (sz <= 0 || (unsigned long)sz > MAX_INPUT_SIZE) { fclose(f); return 2; }
  uint8_t *input = (uint8_t *)malloc((size_t)sz);
  if (!input) { fclose(f); return 2; }
  size_t input_size = fread(input, 1, (size_t)sz, f);
  fclose(f);
  if (input_size == 0) { free(input); return 2; }

  unsigned long long content_size = ZSTD_getFrameContentSize(input, input_size);
  if (content_size == ZSTD_CONTENTSIZE_ERROR ||
      content_size == ZSTD_CONTENTSIZE_UNKNOWN ||
      content_size > MAX_OUTPUT_SIZE) {
    free(input);
    return 1;
  }

  uint8_t *output = (uint8_t *)malloc((size_t)content_size + 1);
  if (!output) { free(input); return 2; }

  size_t produced = ZSTD_decompress(output, (size_t)content_size, input,
                                    input_size);
  int rc = ZSTD_isError(produced) ? 1 : 0;
  free(output);
  free(input);
  return rc;
}
