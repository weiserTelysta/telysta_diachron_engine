---
document_type: adr
decision_status: accepted
implementation_status: not-started
normative_scope: target
last_verified: 2026-10-16
owner: "ai:/root (execution coordinator)"
reviewers:
  - ai:/root/ai_architecture_acceptance
  - ai:/root/ai_migration_acceptance
  - ai:/root/ai_linguistic_provenance_acceptance
---

# ADR-013：RNG 兼容性与 Distribution 版本化

- 状态：`Accepted for AI-reviewed local development; production implementation remains staged`
- 日期：2026-07-17
- 决策范围：`telysta-rng-tree.v1` 保留策略、bounded distribution、known-answer、counter overflow、checkpoint/replay
- 前置合同：[Determinism Contract v1](../DETERMINISM_CONTRACT_V1.md)
- Known-answer fixture：[`tests/fixtures/rng_known_answers_v1.json`](../../tests/fixtures/rng_known_answers_v1.json)

2026-10-16 经三个独立 AI 会话接受为本地开发技术合同；执行模式、用户授权及
接受范围见 [Agent 操作模型 §3.1](../AGENT_OPERATING_MODEL.md#31-用户授权的-ai-本地开发审阅2026-10-16)。
这不是目标 writer、迁移器、语言学真实性或跨平台发布已验证的声明。

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

### 3.0 64-bit JSON wire 编码（Proposed 决定）

本轮前 ADR-011 planning schema 与当前 Tauri demo command 把 `rootSeed`/`seed`
表示为 JSON integer / Rust `u64`。Webview 的 Number 不能区分所有大整数，见
[ECMAScript Number.MAX_SAFE_INTEGER](https://tc39.es/ecma262/multipage/numbers-and-dates.html#sec-number.max_safe_integer)。
fixture 已覆盖 `u64::MAX`，不能继续把该 wire 问题留给客户端自行截断。

2026-10-14 Proposed 决定：target `rootSeed` 采用规范化 ASCII 十进制字符串，
仅 `"0"` 或无前导零的正数字符串，范围 `0..=18446744073709551615`；禁止符号、
空白、指数、小数、Unicode 数字与 JSON number。Rust 领域内部仍使用 `u64`，
验证后解析并要求 `parsed.to_string() == text`；Webview 不经 Number/parseInt 转换，
也不把 BigInt 直接放入 JSON。ADR-011 planning schema/records 已同步该字符串；
Python range oracle、Node ECMAScript grammar/JSON round trip 和 Rust parse 交叉检查，
设计已独立接受，但仍须未来 target DTO 绑定，不能宣称生产 wire 已升级。

现有 `RunContext v1`、demo command 与冻结 RNG known-answer 保留原格式和字节。
未来显式迁移从归档原文由 Rust 精确解出 legacy u64 后生成规范字符串，保存源
artifact/schema/hash 和转换记录；不得先走 JS Number，不重写源 archive，不改变
raw tree、distribution 或 legacy path。已丢失精度的外部 number 无法猜回原 seed，
必须拒绝并要求原始来源/显式解决，而不是补零。target 请求不隐式接收 legacy number；
legacy adapter 与正式 DTO 仍需按 R1/G0A 接受条件实施。

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

2026-10-14 Proposed planning slice：`rngLock.streamBudgets` 显式列出相对
stream path 与 `maxRawDraws`；同一锁中 path 唯一，Run 继承父预算。完整路径为
Run pathRoot + relativePath；未声明流拒绝执行。预算/计数采用
`0..=2^53-1` 的 JSON safe integer 子域，这只是有限执行策略，不改变 v1 raw
算法，也不替代 §3.0 的生产 DTO 绑定与实际测试。零预算有效，但第一 draw 即耗尽。

`telysta-rng-frontier-draft.v1` 列出全部已声明流（未用流为零计数）的完整 path、
distributionVersion、预算、consumedRawDraws 与 nextCounter；初始 counter 为零，
每次 raw draw（包括 sampler 丢弃值）计数一次，故两种计数必须相等且不越预算。
到达预算的 checkpoint 可验证，但下一 draw 必须 `rng_stream_exhausted`。
恢复器需要匹配此 frontier schema 及 RunSpec 锁，不能只接受一个不透明 hash。

planning frontier 摘要覆盖完整对象：UTF-8 JSON、对象键排序、无额外空白/末尾换行、
数组保留已声明顺序；这里的字段和值限定为本草案的 ASCII 字符串与 safe integers。
这不是通用 canonicalizer 或 StateSemanticHash。实际记录 fixture 的 frontier hash
可重算，其他重复十六进制仍是 format sentinel。当前 Python 检查验证 schema、
跨记录关系与负突变，尚无生产 cursor、恢复器或 restart/resume 执行证据。

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

本文已由独立 AI 完成 architecture/determinism、migration 与 provenance 设计接受；
作者未占 independent reviewer 槽位。尚未实现的 persisted RunContext/RunSpec 变更
仍须版本化、迁移和实际验证；本次接受不把旧 G0A 标记为通过。
