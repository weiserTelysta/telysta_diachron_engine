---
document_type: adr
decision_status: proposed
implementation_status: not-started
normative_scope: target
last_verified: 2026-07-18
owner: unassigned
reviewers: []
---

# ADR-013：RNG 兼容性与 Distribution 版本化

- 状态：`Proposed`
- 日期：2026-07-17
- 决策范围：`telysta-rng-tree.v1` 保留策略、bounded distribution、known-answer、counter overflow、checkpoint/replay
- 前置合同：[Determinism Contract v1](../DETERMINISM_CONTRACT_V1.md)
- Known-answer fixture：[`tests/fixtures/rng_known_answers_v1.json`](../../tests/fixtures/rng_known_answers_v1.json)

## 1. 问题

当前 Rust RNG 已稳定地按 seed/path 产生 SHA-256 counter stream，并用拒绝采样实现 `uniform`，但持久化只记录 `rngSchema`：bounded distribution 没有独立版本，缺少跨实现 known-answer，`next_u64` 在 `u64` counter 末端使用 wrapping add。若未来优化 sampler 或引入 resume checkpoint，可能在不改 schema 的情况下改变历史结果。

## 2. 假设分类

| 断言 | 分类 | 处理 |
|---|---|---|
| 已有 v1 seed/path 的输出不可静默改变 | Hard replay constraint | 冻结 byte-level known-answer |
| 所有采样分布都可由 tree schema 隐含 | Rejected assumption | distribution 独立版本化 |
| 单流会合理消耗接近 `2^64` 个 raw draw | Engineering impossibility for intended use, not a proof | 生产 execution policy 仍必须设硬预算并拒绝溢出 |
| 更“自然”的随机性会改善语言质量 | Research hypothesis | RNG 只保可复现；语言质量由模型/evaluator 证明 |

## 3. 提议决定

### 3.0 独立评审阻断：64-bit JSON wire 编码

当前 ADR-011 planning schema 和 Tauri demo command 仍把 `rootSeed`/`seed` 表示为 JSON
integer / Rust `u64`。大于 JavaScript `Number.MAX_SAFE_INTEGER` 的值无法在 Webview 中无损
往返；fixture 已覆盖 `u64::MAX`，因此这不是理论边界。

ADR-013 Accepted 前必须独立决定并测试 target wire 表示。当前推荐候选是规范化十进制
字符串：禁止符号、前导零和空白，范围限定为 `0..=u64::MAX`；Rust 领域内部仍使用
`u64`。在该决定批准并同步 ADR-011 schema、Tauri DTO、known-answer fixture 和迁移规则
前，当前整数 planning draft 只可用于评审，不得成为生产 wire 格式。

### 3.1 保留 v1 raw stream

保留 `telysta-rng-tree.v1` 的 key/path/raw-output 算法，不用新的第三方 PRNG 替换已有历史。以下 wire interpretation 冻结：

- path key：SHA-256(`telysta-rng-tree.v1` bytes, root seed LE u64, repeated segment length LE u32 + ASCII bytes)；
- raw draw：SHA-256(`telysta-rng-tree.v1` bytes, 32-byte key, counter LE u64) 的前 8 bytes 按 little-endian u64；
- path 语法：非空点分段，每段 1–64 bytes，只含 lowercase ASCII、数字、`-`、`_`；
- 新模块只能获得新稳定 path，不能移动或重用旧 path。

### 3.2 独立版本化 distribution

将当前 raw draw 解释命名为 `telysta-rng-next-u64.v1`，将当前 bounded rejection sampler 命名为 `telysta-rng-uniform-u64.v1`：

```text
accepted_upper = u64::MAX - (u64::MAX % upper_exclusive)
draw until value < accepted_upper
return value % upper_exclusive
```

这是对现有行为的记录，不是算法修改。未来 shuffle、weighted choice、normal/Poisson、Dirichlet 或浮点映射必须各有 schema/参数规范和 known-answer；不得只写“使用 RNG v1”。

### 3.3 兼容策略

- 现有 `telysta-run-context.v1` 中 `rngSchema == telysta-rng-tree.v1` 明确映射到上述两个 v1 distribution；这是 legacy compatibility table，不重写源文件；
- 新 `RunSpec` 必须显式保存 tree schema、root seed、run path root、distribution bundle/version 和 draw budget；
- loader 遇到未知 tree/distribution schema 返回 `ArchiveOnly` 或 `Unavailable`，不得用“最相近”实现；
- 只改变 distribution 时不改 raw tree；只改变 path/key/raw bytes 时必须新 tree schema；
- replay 选择由锁定 schema 决定，不由当前默认实现或 app 版本决定。

### 3.4 Counter overflow 与 resume

底层 v1 primitive 的实际 legacy 行为是 wrapping counter；该行为为了旧输出解释保留，但禁止生产 Run 绕回 counter 0。R1 必须在可持久化 execution cursor 外层实现：

- 声明且验证每个 stream 的最大 raw-draw budget；
- 在下一 draw 将越过预算或 counter 将 wrap 前返回稳定、不可重试的 `rng_stream_exhausted`；
- checkpoint 保存 tree/distribution schema、完整 path、next counter、budget、已消费 draw 和 checksum；
- 缺任一字段只能 Restart；Resume 不得改变 RunSpec、path 或 cursor；
- counter/budget 不进入 LanguageState semantic hash，但进入 Operation/Run lock、checkpoint 和 replay evidence。

如未来需要改变 primitive API 来消除 wrapping，实现必须保留 v1 replay adapter，并通过新 ADR 决定新 schema；不得直接修改 v1 known-answer。

## 4. Known-answer 与验证

`rng_known_answers_v1.json` 覆盖 seed `0`、`888`、`u64::MAX`，两个不同 path，raw draws、普通 bounded sampler 和高拒绝率 bounded sampler。`crates/telysta-core/tests/rng_known_answers.rs` 通过公共 Rust API 验证 fixture，防止重构、字节序、segment 编码或 sampler 边界静默漂移。

R1/WS-1 在 Accepted 后还必须增加：

- 跨进程/跨平台 fixture；
- path registry collision 与重复声明检查；
- draw-budget property tests 和边界故障注入；
- checkpoint restart/resume 等价测试；
- distribution bundle migration/unknown-version 负例；
- scheduler、并发和新增无关 stream 不改变既有 Run 的测试。

## 5. 后果与审批门

该决定不把 RNG 当成语言学自然度来源；它只保证同一已声明随机实验可重演。优点是既有输出不变、sampler 演化可审计、resume 不会伪确定；代价是每个新分布都要版本、fixture 和兼容表。

本文尚缺具名 code owner、independent determinism reviewer 和 independent migration
reviewer；作者和 owner 不得占任一 independent reviewer 槽位。因此本文仍为
Proposed，不授权修改 persisted RunContext、开始 RunSpec writer 或把 G0A 标记为通过。
