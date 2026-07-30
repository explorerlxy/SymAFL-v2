# SymAFL v2

SymAFL v2 在 AFL++ 上增加 PCBT（Path-Constraint Binary Tree）候选筛选。系统在
PCBT 阶段执行带 SymSan/DFSan 跟踪的 concolic target；树达到饱和条件后，请求
AFL++ 切换到独立的 concrete target，并以保留的 queue 在新的 coverage universe
中重新 bootstrap。当前热路径不包含约束求解，也不使用 Jigsaw JIT。

## 当前执行模型

1. AFL++ 生成候选输入。
2. custom mutator 在 `afl_custom_post_process` 中用 PCBT 谓词解释器筛选候选。
3. 被放行候选在 concolic forkserver child 中完整执行 DFSan 跟踪。
4. 初始 corpus 用完整 pipe trace 建树；稳态用 frontier-anchored SHM suffix；仅当
   SHM 溢出且该输入产生 coverage gain 时，才以 pipe suffix 重放。
5. PCBT 饱和后，mutator 设置 phase-switch 请求；AFL++ 在调度边界切换 concrete
   forkserver，并重建 coverage 派生状态。

详细契约见：

- [文档索引](docs/README.md)
- [系统架构](docs/ARCHITECTURE.md)
- [运行时协议](docs/RUNTIME_PROTOCOL.md)
- [PCBT 与谓词语义](docs/PCBT.md)
- [配置参考](docs/CONFIGURATION.md)
- [验证矩阵](docs/VERIFICATION.md)
- [当前状态与已知缺口](docs/STATUS.md)
- [浏览器同步：文档摘要](docs/SYNC_DOCS.md) / [关键代码摘要](docs/SYNC_CODE.md)

## 仓库结构

```text
SymAFL-v2/
├── AFLplusplus/                # AFL++ v4.31c 分支；受限的 drain / phase-switch 集成
├── symsan/                     # SymSan 分支；mutator、PCBT、谓词解释器、DFSan runtime
├── scripts/                    # 构建、冒烟、评测入口
├── tests/                      # toy、pipe stress、forkserver 与模式回归
├── docs/                       # 架构、协议、验证、状态、决策记录
├── README.md                   # 用户入口
└── AGENTS.md                   # 仓库级操作约束；细节委托给 docs/
```

## 构建

```bash
git clone --recurse-submodules git@github.com:explorerlxy/SymAFL-v2.git
cd SymAFL-v2
git submodule update --init --recursive
scripts/build-all.sh
```

基线环境为 Ubuntu 24.04 与 LLVM/Clang 18。依赖清单应以构建脚本和 CI 为准；
SymSan 继承的构建依赖不等于当前 PCBT 热路径的运行时依赖。

## 本地验证

```bash
python3 tests/trace_check.py direct
python3 tests/trace_check.py afl
python3 tests/pcbt_pipe_check.py
python3 tests/pcbt_toy_modes_check.py
scripts/run-fuzz.sh pcbt
```

所有 fuzz 输出放在 `/tmp` 的专用目录中。不要把 corpus、fuzz 输出、二进制、core、
凭据或环境秘密提交到仓库。

## 重要边界

- PCBT 阶段要求显式设置 `SYMAFL_CONCOLIC_TARGET` 和
  `SYMAFL_CONCRETE_TARGET`。
- `SYMAFL_TRACE_MODE` 不控制生产传输路径；生命周期固定选择三种模式。
- `InsertSuffix` 依赖调用方已经证明 frontier 前缀同构，不在函数内重放前缀。
- 当前已审阅 mutator 只把条件事件插入 PCBT；不要把 memerr 路径绑定描述为已实现
  功能，除非相应代码和回归已落地。
