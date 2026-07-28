# SymAFL v2 — PCBT-Guided Seed Screening on SymSan/Jigsaw

SymAFL v2：在传统 fuzzer（AFL++）基础上增加 PCBT（路径约束二叉树）种子筛选。
变异候选在执行前先对照路径约束树判定"能否到达未探索分支"，只执行有趣候选；
PCBT 耗尽前，所有被执行的候选都是 concolic execution（SymSan 高效路径约束收集）。
系统不含约束求解；Jigsaw 仅作为谓词→原生函数的 JIT 求值库。

## 仓库结构

| 子模块 | 来源 | 说明 |
|---|---|---|
| `AFLplusplus/` | 上游官方 @ v4.31c | 零补丁；筛选经 custom mutator `post_process` 否决实现 |
| `symsan/` | explorerlxy/SymAFL-Symsan @ v2-dev | 开发主战场：剥离求解链 + PCBT 核心 + JIT 筛选 |

## 构建

```bash
git clone --recurse-submodules <this-repo>
cd SymAFL-v2
scripts/build-all.sh        # aflpp -> symsan
```

依赖（Ubuntu 24.04）：`clang-18 libc++-18-dev libc++abi-18-dev libunwind-18-dev
libz3-dev libprotobuf-dev protobuf-compiler libgoogle-perftools-dev
libboost-container-dev python3-dev zlib1g-dev cmake`

## 设计文档

见 `docs/DESIGN_V2.md`（技术方案 as-planned / as-built）。
