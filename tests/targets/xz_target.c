// SymAFL v2 xz target: decode an .xz stream from a file (argv[1]).
// Based on benchmarks/realworld/harness/xz_harness.c (v1), switched from
// stdin to file input so it uses the proven taint_file path.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include <lzma.h>

#define MAX_INPUT_SIZE (32u * 1024u * 1024u)
#define MAX_OUTPUT_TOTAL (128u * 1024u * 1024u)
#define OUT_CHUNK (128u * 1024u)

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

  uint8_t *output = (uint8_t *)malloc(OUT_CHUNK);
  lzma_stream stream = LZMA_STREAM_INIT;
  lzma_ret init_ret = lzma_stream_decoder(&stream, UINT64_MAX, 0);
  if (!output || init_ret != LZMA_OK) {
    free(output);
    free(input);
    lzma_end(&stream);
    return 2;
  }

  stream.next_in = input;
  stream.avail_in = input_size;
  stream.next_out = output;
  stream.avail_out = OUT_CHUNK;

  size_t total = 0;
  lzma_ret ret = LZMA_OK;
  while (ret == LZMA_OK) {
    size_t before = OUT_CHUNK - stream.avail_out;
    ret = lzma_code(&stream, LZMA_FINISH);
    size_t produced = OUT_CHUNK - stream.avail_out;
    total += (produced - before);
    stream.next_out = output;
    stream.avail_out = OUT_CHUNK;
    if (total > MAX_OUTPUT_TOTAL) { ret = LZMA_DATA_ERROR; break; }
  }

  free(output);
  free(input);
  lzma_end(&stream);
  return (ret == LZMA_STREAM_END) ? 0 : 1;
}
