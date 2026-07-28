# SymAFL v2 技术方案：基于 SymSan 高效收集的 PCBT 筛选 fuzzer

## Context（背景、动机与模型澄清）

**SymAFL 的核心贡献**：在传统 fuzzer（AFL++）基础上增加 PCBT（路径约束二叉树）筛选——变异候选在执行前先对照路径约束树判定"能否到达未探索分支"，只执行有趣候选。**在 PCBT 耗尽前，fuzzer 只进行 concolic execution**：每个通过筛选的候选都做一次带符号追踪的执行，其路径约束表达式序列用于增量维护 PCBT 和 JIT 筛选函数。系统不含约束求解。

**为什么换底座**：v1 用 SymCC(2021) 收集路径约束，效率太慢。SymSan（USENIX Sec'22）是已知最快的约束收集器（比 SymCC 快 62× 的符号状态管理），且其仓库已 vendored Jigsaw 的 JIT 代码（可作谓词→原生函数的求值引擎）。v2 的目标：**用 SymSan 的高效收集能力实现 SymAFL 的既定功能**。

**与 SymSan 原版协作模式的本质区别**（用户澄清，这是方案设计的出发点）：

| | SymSan 原版（双线并行） | SymAFL v2（本方案） |
|---|---|---|
| AFL++ 执行什么 | 全程 concrete（普通 AFL 二进制） | **全程 concolic**（SymSan 追踪二进制） |
| SymSan 追踪二进制 | 侧线：每种子 fork+exec 一次，收约束→求解→喂种子 | **就是 afl-fuzz 的 forkserver 目标本身** |
| 约束收集的触发 | 按种子定期同步 | 每次执行都在追踪；事件消费按覆盖增益门控 |
| 求解器 | I2S→Jigsaw→Z3 | **无**（Jigsaw 仅作谓词 JIT 求值库） |
| 筛选 | 无 | post_process 否决（AFL++ 官方钩子，零补丁） |

**已核实的关键事实**（代码/文档级）：

1. AFL++ custom mutator 的 `post_process` 可否决执行（返回 NULL/0 则候选不执行），对所有变异生效；`fuzz`/`fuzz_count` 均为 optional——mutator 只实现 `init`/`post_process`/`queue_get`/`queue_new_entry` 合法（AFL++ v4.31c `docs/custom_mutators.md`）。
2. SymSan 每次追踪运行是全新进程，事件流 = **从程序入口开始的完整符号分支决策序列**（`backend/fastgen.cpp:112-137`：label≠0 的每个条件分支按执行序发 `pipe_msg{cid,label,result}`；具体分支不发）。分歧点检测的 InsertTrace 成立，v1 的 `__insert_depth` SHM 不需要。
3. SymSan 原版需编译**两个**二进制（普通 fuzzing + ko-clang 追踪版，`driver/aflpp/README.md`）；本方案只需**一个**（追踪版 + 补 AFL coverage/forkserver）。
4. 宿主 Ubuntu 24.04.4 + clang-18.1.8（README 基线 LLVM 18）可直建；缺 `libprotobuf-dev protobuf-compiler libgoogle-perftools-dev libboost-container-dev python3-dev`。
5. SymSan 原版驱动无 forkserver、无 AFL coverage 注入追踪二进制——这两点是本方案必须新做的集成工作（见下"集成难点"）。

**用户已拍板**：RSan 角色 = UCSan 替代（v1 分支保留）；仓库形态 = 新建 superproject + submodules；系统范围 = 传统 fuzzer + PCBT 筛选，无求解器。

## 目标系统架构（单二进制、全程 concolic）

```
目标构建（一次）：ko-clang (DFSan 符号追踪)
                + -fsanitize-coverage=trace-pc-guard   ← 补 AFL 覆盖
                + AFL++ SanitizerCoveragePCGUARD.so    ← 补 forkserver（LD_PRELOAD）

┌─ afl-fuzz（官方 v4.31c，零补丁；env 设 TAINT_OPTIONS 使能标签追踪）─┐
│  queue → havoc 变异 → post_process ─┐                              │
│  ┌─ symsan mutator .so（在 afl-fuzz 进程内）◄┘                     │
│  │  PCBT.CheckInput(候选) → JIT 谓词逐节点求值（µs）               │
│  │    → 到达 frontier → 放行（记录 admitting 节点）                │
│  │    → 否则 → 否决执行（返回 0）；admitting 节点 rCnt++           │
│  └──────────────────────────────────┘                             │
│  放行候选 → forkserver 执行（concolic：DFSan 标签全程追踪，        │
│             事件不发 pipe——pipe_fd=-1 短路，零序列化）             │
└─────────────────────────────────────────────────────────────────────┘
        │ queue_new_entry（覆盖增益）或 queue_get（首次选中，bootstrap）
        ▼
  追踪重跑（复用既有 launcher：fork+exec+pipe+SHM AST 表）
        → 符号分支事件流（从根开始）→ PCBT.InsertTrace（分歧点检测）
        → UCSan memerr 事件 → 漏洞↔路径绑定
```

**执行语义（与 v1 契约一一对应）**：
- **每个被执行的候选都是 concolic run**：forkserver 子进程在 `TAINT_OPTIONS=taint_file=<@@路径>` 环境下，DFSan 拦截器对每次运行的输入文件做标签追踪（concolic 本体）；不发事件（pipe_fd=-1 时 `__send*` 短路，`fastgen.cpp` 既有逻辑），因此 non-gaining run 零序列化开销——对应 v1 "no-gain 只付 tracking"。
- **覆盖增益的候选**：launcher 重跑一次（开事件），事件流喂 InsertTrace——对应 v1 "gaining 候选带 dump 重放"。重跑与首跑同二进制同输入，确定性目标下路径一致；InsertTrace 前可比对两次 bitmap 做 replay 校验（v1 契约，作为正确性护栏）。
- **bootstrap**：初始种子/新 queue 条目首次被选中（`queue_get`/`queue_new_entry`）时 launcher 追踪一次并 InsertTrace——每个 queue 条目的真实路径都进树。
- **non-gaining 候选**：admitting 节点 rCnt++（筛选时已知，无需 trace）。
- **PCBT 耗尽**（root 饱和）：`post_process` 转为全放行（退化为纯 AFL 继续 fuzz），日志标记。v1 无 fallback；此处选择 passthrough 作为最简策略，后续可改。

**两个集成难点（本方案特有的新工作，Phase 0/1 必须验证）**：
1. **AFL coverage + forkserver 注入 SymSan 二进制**：ko-clang 构建时加 `-fsanitize-coverage=trace-pc-guard`，fuzz 时 `AFL_PRELOAD=SanitizerCoveragePCGUARD.so`（AFL++ 官方为 sancov 二进制提供 forkserver 的标准机制）。DFSan 与 sancov 均为 IR 级插桩，预期可共存，但 DFSan runtime 的 preinit 初始化（固定地址布局）与 PCGUARD.so 的 ctor 顺序需实测。
2. **forkserver 模式下的输入标签**：原版是 exec-per-seed，`InitializeTaintFile` 按启动时输入文件大小预分配 label；forkserver 下进程常驻、输入文件内容每轮重写。需要小补丁：初始化时按 `AFL max_len`（如 1MB）预建输入字节 label（1M×32B=32MB，COW 分摊，~10 LoC），或拦截器内惰性建 label。

## 仓库与代码布局

新 superproject：`/media/hahafish/Data/ForUbuntu/SymAFL-v2`（GitHub 新建 `explorerlxy/SymAFL-v2`）：

```
SymAFL-v2/
├── AFLplusplus/          # submodule: 上游官方 @ v4.31c（零补丁）
├── symsan/               # submodule: explorerlxy/SymAFL-Symsan（v2-dev 分支，开发主战场）
│   ├── runtime/dfsan/dfsan_custom.cpp  # 【改】forkserver 输入标签预分配/惰性化（~10-30 LoC）
│   ├── driver/aflpp/
│   │   ├── symsan.cpp          # 【改】剥离 fuzz/fuzz_count/TaskManager/solver 链（-400 行）；
│   │   │                       #      保留 init/launcher；新增 post_process/queue_get/queue_new_entry
│   │   ├── pcbt.hpp/.cpp       # 【新】PCBT 核心（~600-800 LoC）
│   │   └── screen_jit.*        # 【新】谓词 JIT 求值封装（~200 LoC，复用 solvers/jigsaw/jit.cc）
│   └── solvers/jigsaw/         # 【保留】仅 jit.cc codegen 作库；gd.cc/rgd.cc 不链接
├── docs/
└── scripts/                    # 构建/目标编译/运行/评测脚本（仿 v1 scripts/ 风格）
```

- `explorerlxy/SymAFL-Jigsaw` 独立 fork 仅作参考，不进 submodules。
- 本地 `papers/repos/SymSan` 是无 git 历史的 tarball 快照；Phase 0 经 gh-proxy 重新克隆 fork，核对 HEAD=f225218 作为基线。
- NTFS 注意：各 submodule 设 `core.filemode false`；fuzz 输出目录必须在 ext4（/tmp）。
- 运行配置固定 `AFL_DISABLE_TRIM=1`（trim 会改动已追踪条目的内容，使树中对应路径失效；SymSan README 对同类问题也如此建议）。

## PCBT 核心设计（新代码，全部在 symsan 仓库 driver/aflpp/ 内）

**数据来源**（全部既有）：launcher 追踪重跑产生 `pipe_msg{cond, cid, label, result}` 事件流（从根开始、执行序、仅符号分支）；`RGDAstParser::get_root_expr(label)` 从共享 AST 表还原谓词 `rgd::AstNode`。

**树节点**：`{cid, direction, 谓词AstNode, 编译后fn+关系符, 左右子, rCnt, expCnt}`。谓词语义 = "创建该节点的那次 trace 上观察到的分支条件"（与 v1 相同的近似语义：同一 cid 在不同路径前缀下表达式可能不同——具体折叠所致；replay 监控兜底）。

**InsertTrace(事件流)**：从根沿 `(cid,result)` 走树；首个不匹配处插入剩余事件链。谓词去重复用 Jigsaw `fCache` 归一化哈希思路（常量/输入字节参数化 + Merkle 哈希）。

**CheckInput(候选)**：从根逐节点：候选字节装入参数数组 → JIT 函数 → C++ 侧按关系符得布尔 → 走向子节点。缺失子节点方向 = frontier → 放行并记录 admitting 节点。rCnt 低值剪枝语义沿用 v1（参考 `AFLplusplus/src/PathConTree.cpp` 算法逻辑）。

**谓词 JIT 求值封装**（`screen_jit.*`）：复用 `solvers/jigsaw/jit.cc` 的 `codegen()`（AstNode→LLVM IR→ORC 原生函数），C++ 侧按关系符判定布尔（**不涉及梯度下降**）。
- **语义红线**：`jit.cc:160-214` 除零 hack（`select(c==0,1,c)`）与 Z3 位向量语义（`bvudiv x 0 = 2^w−1` 等）不一致，必须按 Z3 语义重写；移位 ≥ 位宽、精确位宽掩码同按 SMT-LIB 语义。上线后抽样用 Z3 交叉验证（Z3 仅作离线验证器）。
- 冷节点先走 ~100 LoC AstNode 解释器兜底，查询超阈值再 JIT——长尾节点收不回 35µs-0.6ms 的 ORC 编译成本。

**UCSan 漏洞绑定**：memerr 事件随追踪重跑的事件流到达，记录其在 PCBT 中的路径位置 → "漏洞↔路径"报告。不做求解式漏洞输入生成。

## 实施阶段

### Phase 0 — 底座与单二进制冒烟（1–1.5 天）
1. 创建 `SymAFL-v2` superproject + 两个 submodule（symsan 经 gh-proxy 克隆核对 HEAD=f225218，推 `v2-dev`）。
2. 装依赖；构建 AFL++ v4.31c（`PERFORMANCE=1 NO_NYX=1 source-only`）与 SymSan（clang-18）。
3. **关键验证 A**：玩具目标用 ko-clang + `-fsanitize-coverage=trace-pc-guard` 构建，afl-fuzz + `AFL_PRELOAD=SanitizerCoveragePCGUARD.so` 跑 2 分钟——forkserver 握手成功、覆盖增长、DFSan runtime 不炸。
4. **关键验证 B**：同二进制设 `TAINT_OPTIONS=taint_file=...`，确认 forkserver 每轮运行输入被正常打标签（必要时打上"预分配 max_len label"补丁）。
- **通过标准**：单一二进制同时胜任 AFL forkserver 目标与 launcher 追踪目标。

### Phase 1 — 剥离求解 + PCBT 构建（1–2 天）
1. 剥离 `symsan.cpp` 的 fuzz/fuzz_count/solver 链（mutator 仅剩 init + launcher + queue 钩子），确认纯 AFL + 空 mutator 正常。
2. 实现 `pcbt.*`；`queue_get`（首次）/`queue_new_entry` → launcher 追踪 → InsertTrace。统计节点数/树深/插入耗时。
- **通过标准**：玩具 + 1 真实目标跑 10 分钟，树持续增长、无崩溃；抽查插入路径与事件流一致。

### Phase 2 — 筛选上线（2–3 天）
1. `screen_jit.*`（ORC 复用 + Z3 语义修正 + 解释器兜底）+ CheckInput。
2. `afl_custom_post_process` 放行/否决 + 统计导出（introspection）。
3. 正确性：抽样 admitted 候选 launcher 重放，验证到达预测 frontier（replay 契约 + bitmap 比对）；JIT vs Z3 抽样交叉验证。
- **通过标准**：replay 一致率 ≥99%；筛选延迟均值 <100µs/候选；覆盖 ≥ baseline 95%。

### Phase 3 — 对比评测（2–3 天）
- 配置：① AFL++ 纯灰盒（普通二进制）② 本方案筛选关（单 concolic 二进制空筛，量底座开销）③ 本方案筛选开。可选 ④ SymAFL v1 既有数据作代际参照。
- 目标：v1 六目标中可 ko-clang 编译者（libxml2、openjpeg、xz 等逐个验证）+ 2–3 个 FuzzBench 目标。
- 指标：concolic execs/s（有效吞吐）、筛选吞吐与否决率、覆盖-时间曲线、UCSan 内存错误数。
- 消融：筛选开/关；JIT vs 解释器。

### Phase 4 — 漏洞绑定演示与论文素材（1–2 天）
UCSan memerr + PCBT 路径前缀 → 报告样例；MDPI 图表数据整理。

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| DFSan + sancov + PCGUARD.so 三者不兼容（preinit/ctor 顺序、固定地址布局冲突） | Phase 0 关键验证 A 先行；备选：链接 `afl-compiler-rt.o` + 手写 `__AFL_INIT` ctor；最差情况退回"launcher exec-per-candidate"（慢但语义不变） |
| forkserver 常驻进程的标签空间/AST 表跨轮污染 | 关键验证 B；预分配 max_len label 补丁；子进程 COW 语义保证每轮独立（已分析成立，实测确认） |
| 目标非确定 → 首跑与重跑路径分叉，树污染 | 评测目标限定确定性；replay bitmap 校验，不一致丢弃不插入（v1 契约） |
| 谓词语义近似（同 cid 不同 run 表达式不同）误杀 | replay 监控；rCnt 保守阈值；高误杀 cid 降级恒放行 |
| ORC 编译延迟拖慢冷路径 | 解释器兜底 + 惰性编译（设计已含） |
| concolic 全程执行的底噪（DFSan tracking 2-9× native）使绝对吞吐低于纯 AFL | 这正是论文要量化的 trade-off：筛选否决率 × 单执行成本 = 收益公式；Phase 3 配置②单独量化 |
| 剥离求解后 parser/TaskManager 残留依赖 | Phase 1 编译期逐点清理；parser 只保留 `get_root_expr` |
| 树无限增长 | 节点上限 + rCnt 剪枝；超限停止插入只筛选（告警） |

## 交付物

1. `SymAFL-v2` superproject（两个 submodule + 构建/运行脚本）。
2. symsan fork `v2-dev` 分支：求解剥离 + forkserver 标签补丁 + `pcbt.*` + `screen_jit.*` + `symsan.cpp` 改造。
3. 评测数据与图表（`results/`）。
4. 设计文档（as-built 版，替代旧头脑风暴文档）。
