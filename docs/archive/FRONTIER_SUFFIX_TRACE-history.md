> **Historical:** The accepted suffix design is recorded in
> `../decisions/0003-frontier-anchored-suffix.md`; current runtime behavior is
> defined in `../RUNTIME_PROTOCOL.md`.

# Frontier-Anchored Suffix Tracing：研讨结论与实现状态

## 背景与问题

SymAFL v2 的 PCBT 会在 AFL++ custom mutator 的 `afl_custom_post_process` 中筛选变异候选。对被放行的候选，`PCBT::CheckInput` 已经准确确定：

- 该输入沿现有 PCBT 所走的路径前缀；
- 该路径上的 frontier 父节点；
- 输入将在该父节点走向的、尚未探索的二叉方向；
- 对应 frontier 的 symbolic branch 深度。

当前实现将该冗余拆为三种明确传输模式。初始 corpus bootstrap 使用
`pipe-full` 并把完整事件直接插入树；bootstrap 完成后，已命中 frontier 的候选
默认使用 `shm-suffix`。child 从程序入口完整 concolic 执行，但只在定长共享内存
中追加 frontier 后的条件事件。只有该输入获得 AFL coverage gain，mutator 才消费
SHM 后缀并直接插入树；若缓冲区溢出，则以 `pipe-suffix` 重跑同一输入，而非回退到
完整 trace。

这在深树下存在明确冗余：筛选阶段已经证明并记录了接入位置，但 trace replay 仍重复传输、读取和匹配整个已知前缀。

## 提议：Frontier-Anchored Suffix Tracing

对具有明确 PCBT frontier 的 admitted candidate，在 coverage-gaining replay 时：

1. traced child 仍从程序入口完整执行 DFSan/concolic tracking；不跳过任何 taint propagation、AST/label DAG 构造或实际程序执行。
2. traced child 不再向 pipe 报告 frontier 父节点之前（含父节点）的普通 symbolic-condition event。
3. mutator 将 frontier 父节点的 symbolic depth `k` 写入共享控制块，供 traced child 读取。
4. traced child 以与 PCBT 相同的口径计数 symbolic condition；前 `k` 个不写 pipe，随后只报告该新方向下的 **suffix**。
5. mutator 使用筛选阶段已保存的 frontier parent/direction，直接植入 suffix，而不再从 PCBT root 重放和匹配前缀。

该机制命名为：

> **Frontier-anchored suffix tracing / frontier-anchored incremental insertion**

## 理论前提与等价性

### PCBT 前缀同构不变式

基于 PCBT 的筛选正确性依赖如下前提：对于同一个候选输入，筛选时在 PCBT 上判定的 symbolic-path prefix，必须与后续 concolic replay 中实际经历的 symbolic-path prefix 严格一致。

设完整 replay trace 为：

\[
T(x) = E_1, E_2, \ldots, E_k, E_{k+1}, \ldots, E_m
\]

其中每个 `E_i = (cid_i, label_i, result_i)`；筛选命中深度为 `k` 的 frontier 父节点 `N`，并得到该输入的未探索方向 `d`：

```text
N.child[d] == nullptr
```

前缀同构要求：

1. `E_1 ... E_k` 逐项对应 root 到 `N` 的既有 PCBT 路径；
2. `E_k.cid == N.cid`；
3. `E_k.result == d`；
4. symbolic event 的计数口径完全一致：仅计入 mutator 会植入 PCBT 的条件事件，即 `cond_type` 且 `label != 0` 且 `label != kInitializingLabel`；
5. 对筛选经过的每个节点，已存 predicate 对候选输入的求值方向与 replay 中实际条件结果一致。

### 等价性结论

在此前提下：

```text
完整插入：
root --匹配 E1..Ek--> N.child[d] --植入 E(k+1)..Em-->

后缀插入：
直接从 N.child[d] --植入 E(k+1)..Em-->
```

二者生成的新 PCBT 节点、父子关系、`cid`、方向和 predicate 均相同。区别仅是完整插入额外承担了与已知前缀长度 `k` 成正比的事件序列化、pipe 传输、事件解码和树路径匹配成本。

因此，在 PCBT 前缀同构不变式下，suffix insertion 是完整 insertion 的**语义保持优化**，而非近似或启发式策略。

## 实现契约

PCBT 的路径前缀同构不变式是 suffix 的正确性依据，而非运行时需要重复验证的猜测。实现不发送 anchor，不建立内容 hash/ticket 校验协议，也不在接收端回放前缀。coverage-gaining 输入沿用 `post_process` 已保存的 frontier parent、direction 和 depth。

`pipe-full` 只用于 bootstrap；后验 full 对照应使用专门的测试夹具或独立运行，
不能把稳态候选切换为 full pipe。这样可以保持一个关键资源契约：pipe 上的事件
总会被消费并插入 PCBT，而不会为非 gaining 候选做无效序列化。

### pipe 的进程职责

在单核模型中有三个进程：`afl-fuzz`、目标 forkserver 和该轮 concolic child。
child 写事件；目标 forkserver 不读事件 pipe。真正的读取者是 `afl-fuzz` 父进程：
它以 `select()` 共同等待目标状态 fd 和 event pipe，并把所有当前可读字节 drain 到
`sym_trace_buf`，读到 `EAGAIN` 后回到等待。它不会在 drain 时解码或插树；child
结束后的 mutator 回调才会解码并 `InsertTrace`/`InsertSuffix`。因此 pipe 满时 child
阻塞，`afl-fuzz` 被调度后排空 pipe，随后 child 可继续执行，不存在“等 child 结束
才读 pipe”的环形等待。

## 三种传输模式

| 模式 | 使用场景 | 事件通道 | 消费逻辑 |
|---|---|---|---|
| `pipe-full` | 初始 corpus bootstrap | pipe，完整条件序列 | `post_run` 立即 `InsertTrace` |
| `shm-suffix` | bootstrap 后默认 | 定长 SHM，depth `k` 后的条件序列 | `queue_new_entry` 在 coverage gain 时 `InsertSuffix` |
| `pipe-suffix` | `shm-suffix` 溢出且确认 gain | pipe，depth `k` 后的条件序列 | 同一 forkserver 重跑后 `InsertSuffix` |

`shm-suffix` 在 `post_process` 放行已有 frontier 的候选时，把该节点的 depth 写入
共享控制块并置 `armed`；child 仍完整进行 DFSan label/AST 构造。缓冲区不够时，
runtime 置 overflow 后停止向事件数组追加，不会部分插入。AFL 确认 gain 后才会触发
`pipe-suffix` 重放；无 coverage gain 的候选直接丢弃 SHM 数据。

控制块由 mutator 在 forkserver 启动前创建，因此动态 depth 不依赖
`TAINT_OPTIONS` 的重新解析。初始 corpus、无明确 frontier 的输入强制走
`pipe-full`；SHM overflow 的安全回退是 `pipe-suffix`。该实现不在热路径额外校验
前缀，继续以 PCBT 前缀同构不变式为正确性前提。

## 关键边界：terminal edge

新方向可能在 frontier 父节点之后立即正常结束，没有任何后续 symbolic condition：

```text
E1 ... Ek
```

此时 suffix 为空。现有 `Node *child[2]` 仅以 `nullptr` 表示“未探索”，无法表达“已探索但该方向是 symbolic terminal”。若不处理，后续相同方向会持续被视为 frontier。

实现前或实现过程中需要将 edge 语义扩展为三态：

```text
Unexplored  : 未探索
NextNode    : 指向后继 symbolic branch 节点
Terminal    : 已探索，但无后继 symbolic branch
```

筛选只将 `Unexplored` 视为 frontier；`Terminal` 必须视作已经探索。

## 当前代码关联

| 组件 | 当前职责 | 后续改动方向 |
|---|---|---|
| `symsan/driver/aflpp/pcbt.cpp` | `CheckInput` 返回 frontier `Node*` / direction；`InsertTrace` 从 root 插入完整 trace | 已加入 node depth、terminal edge 和直接接入的 `InsertSuffix` |
| `symsan/driver/aflpp/symsan.cpp` | 保存 `last_node`/`last_dir` 并处理 gain replay | 强制 bootstrap `pipe-full`，默认 `shm-suffix`，overflow 后 `pipe-suffix` |
| `symsan/runtime/dfsan/dfsan.h` | forkserver child 的共享控制协议 | 定义 `OFF`、`FULL_STREAM`、`SUFFIX_SHM` 与 `SUFFIX_PIPE` |
| `symsan/runtime/dfsan/dfsan_flags.inc` | 定义 `TAINT_OPTIONS` 参数 | 已加入 suffix depth 与 single-pass SHM 参数 |
| `symsan/backend/solver_common.cpp` | `__taint_send_cond` 是条件事件的公共发送出口 | 已按 PCBT symbolic-event 口径计数；可写 pipe suffix 或 single-pass 共享数组 |

## 配置与验证策略

默认策略是 bootstrap `pipe-full`、稳态 `shm-suffix`、overflow `pipe-suffix`。
三种模式不提供稳态环境变量覆盖：`SYMAFL_TRACE_MODE` 即使存在也会被忽略并给出
警告。否则 pipe 会在尚未知道是否 coverage gain 时收集事件，破坏其“必然消费”
的资源约束。后验 full 对照应通过独立测试夹具完成。

在没有明确 frontier 的场景必须使用 `pipe-full`：初始 corpus bootstrap、PCBT 为空
以及 opaque predicate 的保守放行。

`SYMAFL_SINGLE_PASS_CAPACITY` 可设定事件容量，默认 `1048576`。容量耗尽只触发
该输入的 pipe-suffix replay，不丢弃 coverage-gaining path。

## 下一步任务

### 1. 已完成的实现

- `Node::depth`、terminal edge 与 `InsertSuffix` 已落地；空 suffix 标记对应 edge 为 `Terminal`。
- `queue_new_entry` 在 suffix 模式复用 `post_process` 保存的 frontier，正常时消费 SHM，溢出时以 pipe-suffix 重放。
- runtime 仅抑制已知前缀的条件事件导出；DFSan 执行、label union 和 predicate 构造不变。
- `shm-suffix` 已落地为共享 union table + 共享事件控制块；toy forkserver 中
  `skip=5/events=5` 的 gain 直接插入，树统计与 full/suffix 对照一致。
- 容量设为 `1` 时已验证 overflow 会回退 pipe-suffix replay，不污染 PCBT。

### 2. 后续测试与性能验证

1. **PCBT 单元/定向测试**：同一完整 event 序列分别走 `InsertTrace` 和 `InsertSuffix`，比较树拓扑、node 数、深度、`cid` 和可筛选结果；覆盖非空后缀与 terminal 后缀。
2. **后验 full 对照**：对同一 gaining input 以 `full` 重放，比较最终 PCBT 拓扑与 single-pass 结果；用于调试和论文验证。
3. **xz rich corpus 串行评测**：在相同语料、相同 `FUZZ_SECONDS`、相同 CPU 条件下采集默认策略的 replay 数、event 数、pipe bytes、nodes/depth、coverage、exec/s 和 RSS。传输替代方案应在独立实验分支中实现，不能以生产路径环境变量覆盖。

## 预期收益与边界

suffix 降低的是 coverage-gaining replay 的前缀事件报告与 PCBT 增量维护成本；single-pass 进一步消除正常 coverage-gaining case 的第二次 concolic execution 和 pipe 传输。二者都不会消除 `CheckInput` 在每个 mutation 上逐谓词走深路径的成本；后者仍需由此前讨论的 prefix invalidation cache 等机制优化。

两项优化互补：

- **pipe-suffix**：SHM overflow 时避免完整事件传输和 `InsertTrace` 前缀匹配；
- **shm-suffix**：消除正常 gaining input 的第二次 concolic execution，直接消费 forkserver child 的 suffix；
- **prefix invalidation cache**：减少候选筛选阶段的 predicate 重算。
