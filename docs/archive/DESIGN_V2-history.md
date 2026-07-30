> **Historical:** This document mixes original planning and later as-built notes.
> Current normative behavior is defined in `../ARCHITECTURE.md`,
> `../RUNTIME_PROTOCOL.md`, `../PCBT.md`, and `../STATUS.md`.

# SymAFL v2 技术方案：基于 SymSan 高效收集的 PCBT 筛选 fuzzer

## As-built phase model（当前实现）

PCBT 不是无限期运行的单二进制模式。启动 PCBT 时必须显式提供本地构建的
`SYMAFL_CONCOLIC_TARGET` 与 `SYMAFL_CONCRETE_TARGET`：前者运行 SymSan
concolic phase，后者仅在 PCBT 饱和后运行传统 AFL++ phase。切换保留已发现的
queue 文件，但清空所有 coverage 派生状态、创建 concrete coverage universe，并
重新校准队列作为 bootstrap。

为保证单核多进程调度下不会发生 trace pipe 死锁，AFL++ 的 **afl-fuzz 父进程**
（而非目标中的 forkserver 进程）在 forkserver-control 等待循环中将 status fd 与
SymSan event pipe 一起 `select()`；每当被调度且 pipe 可读就立即 drain。若 child
因 pipe 满而阻塞，它让出 CPU 后 afl-fuzz 可立刻消费已有事件，无需等到 child
结束或 pipe 再次写满。该支持需要 AFL++ 中保持最小、受限的 SymAFL 补丁；PCBT
谓词与筛选本身仍在 custom mutator 中。

### 三种 concolic 事件传输模式

concolic 阶段中每一个被 PCBT 放行的候选都会执行 DFSan 跟踪，但不会无条件向
pipe 写事件。传输策略由 mutator 在每个 forkserver child 启动前写入共享控制块，
并由生命周期固定选择（不支持将稳态候选强制改为 pipe）：

| 模式 | 时机 | 通道与事件范围 | PCBT 消费 |
|---|---|---|---|
| `pipe-full` | 初始 corpus bootstrap | pipe 从第一个符号分支起报告完整事件 | child 结束后立即 `InsertTrace` |
| `shm-suffix` | bootstrap 后默认 | 定长 SHM 只追加 frontier 父节点深度 `k` 后的条件事件 | 仅 coverage gain 时 `InsertSuffix(parent, direction, suffix)` |
| `pipe-suffix` | SHM 溢出且确认 gain 时 | 同一 forkserver 对该输入重跑；pipe 仅报告第 `k+1` 个及之后的条件事件 | child 结束后 `InsertSuffix` |

`pipe-suffix` 与 `pipe-full` 均由 AFL++ 在等待 child 时并发 drain。SHM 溢出不会
丢弃该 gaining path：runtime 置 overflow 位后停止向事件数组追加；仅当 AFL++ 随后
确认 coverage gain，mutator 才执行 suffix-only pipe replay。三种模式都完整执行
DFSan 传播与 AST/label DAG 构造；它们只改变条件事件的导出和消费方式。这样 pipe
上的事件只出现在 bootstrap 或确认 gain 后的重放中，必然会被插入 PCBT。

#### pipe 调度与所有权边界

单核运行时涉及三个进程：`afl-fuzz`、常驻的目标 forkserver，以及每轮 fork 出的
concolic child。child 以固定大小的 `pipe_msg` 逐条阻塞写入内核 pipe：仍有容量时
继续写，满时内核阻塞该 child。目标 forkserver 不读取此 pipe。`afl-fuzz` 等待其
status fd 时同步监听 event pipe；一旦可读就连续读取到 `EAGAIN`，仅追加到
`sym_trace_buf`，不在此处解析或插树；pipe 暂空后回到 `select()`，把 CPU 让给
forkserver/child。child 结束并回报状态后，custom mutator 才解码缓冲区并执行
`InsertTrace` 或 `InsertSuffix`。因此“drain”与“消费并入树”是两个不同阶段。

## Context（背景、动机与模型澄清）

**SymAFL 的核心贡献**：在传统 fuzzer（AFL++）基础上增加 PCBT（路径约束二叉树）筛选——变异候选在执行前先对照路径约束树判定“能否到达未探索分支”，只执行有趣候选。**在 PCBT 耗尽前，fuzzer 只进行 concolic execution**：每个通过筛选的候选都做一次带符号追踪的执行，其路径约束表达式序列用于增量维护 PCBT 和本地位向量谓词解释器。系统不含约束求解。

**为什么换底座**：v1 用 SymCC(2021) 收集路径约束，效率太慢。SymSan（USENIX Sec'22）是已知最快的约束收集器（比 SymCC 快 62× 的符号状态管理），且其仓库已 vendored Jigsaw 的 JIT 代码（可作谓词→原生函数的求值引擎）。v2 的目标：**用 SymSan 的高效收集能力实现 SymAFL 的既定功能**。

**与 SymSan 原版协作模式的本质区别**（用户澄清，这是方案设计的出发点）：

| | SymSan 原版（双线并行） | SymAFL v2（本方案） |
|---|---|---|
| AFL++ 执行什么 | 全程 concrete（普通 AFL 二进制） | **PCBT 饱和前 concolic，饱和后 concrete** |
| SymSan 追踪二进制 | 侧线：每种子 fork+exec 一次，收约束→求解→喂种子 | **就是 afl-fuzz 的 forkserver 目标本身** |
| 约束收集的触发 | 按种子定期同步 | 每次执行都在追踪；事件消费按覆盖增益门控 |
| 求解器 | I2S→Jigsaw→Z3 | **无**（当前 PCBT 用本地解释器；Jigsaw 不在热路径） |
| 筛选 | 无 | post_process 否决；forkserver drain / phase switch 使用最小 AFL++ 补丁 |

**已核实的关键事实**（代码/文档级）：

1. AFL++ custom mutator 的 `post_process` 可否决执行（返回 NULL/0 则候选不执行），对所有变异生效；`fuzz`/`fuzz_count` 均为 optional——mutator 只实现 `init`/`post_process`/`queue_get`/`queue_new_entry` 合法（AFL++ v4.31c `docs/custom_mutators.md`）。
2. SymSan 每次追踪运行都是新的 child，并从程序入口完整执行 DFSan 传播和
   AST/label DAG 构造。`backend/fastgen.cpp` 对每个 `label≠0` 的条件调用
   `__taint_send_cond`；`backend/solver_common.cpp` 再依本轮控制块决定导出完整
   pipe 序列、`k` 后的 SHM suffix 或 `k` 后的 pipe suffix。具体分支不进入 PCBT
   序列。只有 `pipe-full` 才向接收端导出从根开始的完整序列并使用 `InsertTrace`；
   suffix 模式直接在已知 frontier 使用 `InsertSuffix`，不需要 v1 的
   `__insert_depth` SHM。
3. SymSan 原版使用普通 fuzzing 二进制与侧线 ko-clang 追踪二进制；本方案同样
   需要两个本地构建目标，但它们按**时间阶段**而非并行侧线使用：PCBT 饱和前使用
   ko-clang concolic target（附 AFL coverage/forkserver runtime），饱和后切换到普通
   AFL++ concrete target。两者的 queue 可复用，coverage bitmap 不可复用。
4. 宿主 Ubuntu 24.04.4 + clang-18.1.8（README 基线 LLVM 18）可直建；缺 `libprotobuf-dev protobuf-compiler libgoogle-perftools-dev libboost-container-dev python3-dev`。
5. SymSan 原版驱动无 forkserver、无 AFL coverage 注入追踪二进制——这两点是本方案必须新做的集成工作（见下"集成难点"）。

**用户已拍板**：RSan 角色 = UCSan 替代（v1 分支保留）；仓库形态 = 新建 superproject + submodules；系统范围 = 传统 fuzzer + PCBT 筛选，无求解器。

## 目标系统架构（双二进制、两阶段）

```
目标构建：concolic：ko-clang (DFSan 符号追踪)
                    + -fsanitize-coverage=trace-pc-guard
                    + afl-compiler-rt.o + afl_init_shim.c ← AFL 覆盖与 forkserver
          concrete：afl-clang-fast（普通 AFL++ 插桩）

┌─ afl-fuzz（v4.31c + SymAFL 调度补丁；env 设 TAINT_OPTIONS 使能标签追踪）─┐
│  queue → havoc 变异 → post_process ─┐                              │
│  ┌─ symsan mutator .so（在 afl-fuzz 进程内）◄┘                     │
│  │  PCBT.CheckInput(候选) → 位向量谓词解释器逐节点求值             │
│  │    → 到达 frontier → 放行（记录 admitting 节点）                │
│  │    → 否则 → 否决执行（返回 0）；admitting 节点 rCnt++           │
│  └──────────────────────────────────┘                             │
│  放行候选 → forkserver 执行（concolic：DFSan 标签全程追踪；       │
│             bootstrap=pipe-full，稳态=shm-suffix）                 │
└─────────────────────────────────────────────────────────────────────┘
        │ bootstrap 后 coverage gain
        ▼
  SHM suffix → PCBT.InsertSuffix
  SHM overflow → forkserver pipe-suffix replay → PCBT.InsertSuffix
  bootstrap pipe-full → PCBT.InsertTrace
```

**执行语义（与 v1 契约一一对应）**：
- **PCBT 阶段的每个被执行候选都是 concolic run**：forkserver 子进程在 `TAINT_OPTIONS=taint_file=<@@路径>` 环境下，DFSan 拦截器对每次运行的输入文件做标签追踪。bootstrap 的路径以 pipe-full 立即入树；稳态候选以 SHM 保存 frontier 后缀，若不产生 coverage gain 则在下一候选前丢弃该后缀，因而不承担 pipe 序列化。
- **覆盖增益的候选**：正常情况下直接消费同一次 child 执行留下的 SHM suffix 并 `InsertSuffix`，无需第二次 concolic execution。只有 SHM 溢出才以同一 forkserver 重跑，并由 pipe-suffix 输出第 `k+1` 个分支后的事件，再直接接入已记录的 frontier。
- **bootstrap**：初始 corpus 的每个执行强制为 pipe-full；事件在 `post_run` 被消费并 `InsertTrace`，从而让初始路径都进入树。之后 `queue_get` 标记 bootstrap 完成并启用默认 SHM suffix。
- **non-gaining 候选**：admitting 节点 rCnt++（筛选时已知，无需 trace）。
- **PCBT 耗尽**（所有可求值路径均为 terminal 或 rCnt 饱和）：请求 AFL++ 在调度边界停止 concolic forkserver、重启 concrete forkserver；保留当前 queue，重置 coverage bitmap 及其队列评分，并对 retained queue 重新 calibration/bootstrap，随后进入传统 AFL++。

**两个集成难点（本方案特有的新工作，Phase 0/1 必须验证）**：
1. **AFL coverage + forkserver 注入 SymSan 二进制**：ko-clang 构建时加 `-fsanitize-coverage=trace-pc-guard`，并链接 `afl-compiler-rt.o` 与 `afl_init_shim.c`；后者在 SymSan runtime 初始化后调用 `__afl_auto_init`。DFSan 与 sancov 均为 IR 级插桩，需用 toy 验证 runtime 初始化顺序、forkserver 握手和 coverage。
2. **forkserver 模式下的输入标签**：原版是 exec-per-seed，`InitializeTaintFile` 按启动时输入文件大小预分配 label；forkserver 下进程常驻、输入文件内容每轮重写。需要小补丁：初始化时按 `AFL max_len`（如 1MB）预建输入字节 label（1M×32B=32MB，COW 分摊，~10 LoC），或拦截器内惰性建 label。

## 仓库与代码布局

新 superproject：`/media/hahafish/Data/ForUbuntu/SymAFL-v2`（私有 GitHub 仓库 `explorerlxy/SymAFL-v2`）：

```
SymAFL-v2/
├── AFLplusplus/          # 私有 submodule: explorerlxy/SymAFL-AFLplusplus-v2（main；基于 v4.31c，含受限的 pipe-drain / phase-switch 改动）
├── symsan/               # 私有 submodule: explorerlxy/SymAFL-Symsan（v2-dev 分支，开发主战场）
│   ├── runtime/dfsan/dfsan_custom.cpp  # 【改】forkserver 输入标签预分配/惰性化（~10-30 LoC）
│   ├── driver/aflpp/
│   │   ├── symsan.cpp          # 【改】剥离 fuzz/fuzz_count/TaskManager/solver 链（-400 行）；
│   │   │                       #      保留 init 与 AFL++ 回调；新增 post_process/queue_get/queue_new_entry
│   │   ├── pcbt.hpp/.cpp       # 【新】PCBT 核心（~600-800 LoC）
│   │   └── pred.hpp/.cpp       # 谓词 AST 转换与 ≤64-bit SMT 位向量解释器
│   └── solvers/jigsaw/         # 保留依赖代码；当前 mutator 不链接求解/JIT 热路径
├── docs/
└── scripts/                    # 构建/目标编译/运行/评测脚本（仿 v1 scripts/ 风格）
```

- `explorerlxy/SymAFL-Jigsaw` 独立 fork 仅作参考，不进 submodules。
- 本地 `papers/repos/SymSan` 是无 git 历史的 tarball 快照；Phase 0 经 gh-proxy 重新克隆 fork，核对 HEAD=f225218 作为基线。
- NTFS 注意：各 submodule 设 `core.filemode false`；fuzz 输出目录必须在 ext4（/tmp）。
- 运行配置固定 `AFL_DISABLE_TRIM=1`（trim 会改动已追踪条目的内容，使树中对应路径失效；SymSan README 对同类问题也如此建议）。

## PCBT 核心设计（新代码，全部在 symsan 仓库 driver/aflpp/ 内）

**数据来源**：forkserver child 产生的 `pipe_msg{cond, cid, label, result}` 或等价的定长 SHM 条件事件。pipe-full 从根开始，两个 suffix 模式从已知 frontier 的第 `k+1` 个事件开始；谓词由共享 AST/union table 中的 label 还原。

**树节点**：`{cid, Predicate(arena, root, opaque), 左右子, terminal[2], rCnt[2], depth}`。每条 trace 的 label DAG 由 `RunConverter` 一次转换为共享的 `PredArena`，节点只保存其中的轻量视图；当前不编译原生函数。谓词语义 = "创建该节点的那次 trace 上观察到的分支条件"（与 v1 相同的近似语义：同一 cid 在不同路径前缀下表达式可能不同——具体折叠所致；replay 监控兜底）。

**InsertTrace(事件流)**：从根沿 `(cid,result)` 走树；首个缺失位置插入剩余事件链，已有节点的 `cid` 不一致则判为冲突并丢弃该非确定性 trace。单条 trace 内的共享由 label→arena-index memoization 保证；当前没有跨 trace 的 Jigsaw 函数缓存或谓词编译缓存。

**CheckInput(候选)**：从根逐节点：将候选字节交给本地位向量解释器 → 取得布尔结果 → 走向子节点。解释器支持 ≤64-bit 的常见整数/比较/位运算；不支持或过宽表达式标为 opaque 并保守放行。缺失子节点方向 = frontier → 放行并记录 admitting 节点。rCnt 低值剪枝语义沿用 v1（参考 `AFLplusplus/src/PathConTree.cpp` 算法逻辑）。

**谓词解释器**（`pred.*`）：`RunConverter` 将每次 trace 的 union-table label DAG 转为共享 AST arena；`eval_predicate()` 按 SMT-LIB 位向量语义解释 ≤64-bit 的整数表达式，包括除零和越宽移位。FP、字符串、GEP、过宽或过深表达式标为 opaque，由 `CheckInput` 保守放行。Jigsaw JIT 尚未接入；若后续接入，须用解释器和离线 Z3 做交叉验证后才可替代它。

**UCSan 漏洞绑定**：memerr 事件随追踪重跑的事件流到达，记录其在 PCBT 中的路径位置 → "漏洞↔路径"报告。不做求解式漏洞输入生成。

## 实施阶段

### Phase 0 — 底座与双目标冒烟（1–1.5 天）
1. 创建 `SymAFL-v2` superproject + 两个 submodule（symsan 经 gh-proxy 克隆核对 HEAD=f225218，推 `v2-dev`）。
2. 装依赖；构建 AFL++ v4.31c（`PERFORMANCE=1 NO_NYX=1 source-only`）与 SymSan（clang-18）。
3. **关键验证 A**：玩具 concolic target 用 ko-clang + `-fsanitize-coverage=trace-pc-guard` + `afl-compiler-rt.o` + init shim 构建，运行 afl-fuzz——forkserver 握手成功、覆盖增长、DFSan runtime 不炸。
4. **关键验证 B**：同二进制设 `TAINT_OPTIONS=taint_file=...`，确认 forkserver 每轮运行输入被正常打标签（必要时打上"预分配 max_len label"补丁）。
- **通过标准**：concolic target 可同时胜任 AFL forkserver 目标和 DFSan 追踪；concrete target 可在 phase switch 后以同一 queue 重新建立 coverage。

### Phase 1 — 剥离求解 + PCBT 构建（1–2 天）
1. 剥离 `symsan.cpp` 的 fuzz/fuzz_count/solver 链（mutator 仅剩 init 与 AFL++ 回调），确认纯 AFL + 空 mutator 正常。
2. 实现 `pcbt.*`；bootstrap 以 forkserver pipe-full 插入 `InsertTrace`，稳态以 queue_new_entry 消费 suffix。统计节点数/树深/插入耗时。
- **通过标准**：玩具 + 1 真实目标跑 10 分钟，树持续增长、无崩溃；抽查插入路径与事件流一致。

### Phase 2 — 筛选上线（2–3 天）
1. `pred.*` 位向量解释器 + CheckInput；JIT 仅作为后续可选优化。
2. `afl_custom_post_process` 放行/否决 + 统计导出（introspection）。
3. 正确性：抽样 admitted 候选在同一 forkserver 重放，验证到达预测 frontier（replay 契约 + bitmap 比对）；解释器 vs Z3 抽样交叉验证。
- **通过标准**：replay 一致率 ≥99%；筛选延迟均值 <100µs/候选；覆盖 ≥ baseline 95%。

### Phase 3 — 对比评测（2–3 天）
- 配置：① AFL++ 纯灰盒（concrete 二进制）② 本方案筛选关（concolic phase 保持 DFSan、但不 veto，量底座开销）③ 本方案筛选开。可选 ④ SymAFL v1 既有数据作代际参照。
- 目标：v1 六目标中可 ko-clang 编译者（libxml2、openjpeg、xz 等逐个验证）+ 2–3 个 FuzzBench 目标。
- 指标：concolic execs/s（有效吞吐）、筛选吞吐与否决率、覆盖-时间曲线、UCSan 内存错误数。
- 消融：筛选开/关；若将来接入 JIT，再与当前解释器比较。

### Phase 4 — 漏洞绑定演示与论文素材（1–2 天）
UCSan memerr + PCBT 路径前缀 → 报告样例；MDPI 图表数据整理。

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| DFSan + sancov + AFL runtime 不兼容（preinit/ctor 顺序、固定地址布局冲突） | Phase 0 关键验证 A 先行；使用 `afl-compiler-rt.o` + init shim，并以 toy 验证 forkserver、coverage 与 taint |
| forkserver 常驻进程的标签空间/AST 表跨轮污染 | 关键验证 B；预分配 max_len label 补丁；子进程 COW 语义保证每轮独立（已分析成立，实测确认） |
| 目标非确定 → 首跑与重跑路径分叉，树污染 | 评测目标限定确定性；replay bitmap 校验，不一致丢弃不插入（v1 契约） |
| 谓词语义近似（同 cid 不同 run 表达式不同）误杀 | replay 监控；rCnt 保守阈值；高误杀 cid 降级恒放行 |
| 深 PCBT 的逐节点解释成本过高 | 先量化解释器开销；后续可引入经交叉验证的 JIT 或前缀缓存 |
| concolic 全程执行的底噪（DFSan tracking 2-9× native）使绝对吞吐低于纯 AFL | 这正是论文要量化的 trade-off：筛选否决率 × 单执行成本 = 收益公式；Phase 3 配置②单独量化 |
| 剥离求解后 parser/TaskManager 残留依赖 | Phase 1 编译期逐点清理；parser 只保留 `get_root_expr` |
| 树无限增长 | 节点上限 + rCnt 剪枝；超限停止插入只筛选（告警） |

## 交付物

1. `SymAFL-v2` superproject（两个 submodule + 构建/运行脚本）。
2. symsan fork `v2-dev` 分支：求解剥离 + forkserver 标签补丁 + `pcbt.*` + `pred.*` + `symsan.cpp` 改造。
3. 评测数据与图表（`results/`）。
4. 设计文档（as-built 版，替代旧头脑风暴文档）。
