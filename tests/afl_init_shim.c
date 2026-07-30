// Start AFL's sanitizer-coverage forkserver after SymSan runtime setup.
extern void __afl_auto_init(void);

__attribute__((constructor(101))) static void v2_afl_init(void) {
  __afl_auto_init();
}
