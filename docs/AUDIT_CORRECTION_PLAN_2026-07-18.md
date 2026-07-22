---
document_type: plan
decision_status: not-applicable
implementation_status: in-progress
normative_scope: current
last_verified: 2026-07-19
source_revision: 599f50d3b952178bcb841afa86edd3886cef1024
owner: unassigned
reviewers: []
---

# Telysta 审计修正执行计划（2026-07-18）

## 1. 文档角色与当前结论

本文把[语言学与架构审计](./LINGUISTIC_AND_ARCHITECTURE_AUDIT_2026-07-18.md)中的 P0/P1 问题映射到现有工作包、质量门、迁移证据和验收任务。它是修正覆盖层，不是第四份主计划，也不自行接受任何 ADR。

权威关系保持不变：

- `AGENTS.md`、Accepted ADR 和已接受领域合同决定不可逆语义；
- [产品开发执行计划](./PRODUCT_DEVELOPMENT_PLAN.md)仍是 WBS、依赖、Stop/Go 和当前队列的执行权威；
- [路线图](./ROADMAP.md)维护阶段状态；
- [专业语言模拟器实施总计划](./LANGUAGE_SIMULATOR_PLAN.md)维护长期能力地图；
- [当前状态](./STATUS.md)和 GateEvidence 决定是否已经放行，计划文字不能代替 Gate 证据。

当前判断：

- G0A = `blocked`；
- 2026-07-19 对 `599f50d3b952178bcb841afa86edd3886cef1024` 的执行后复审重新打开了
  Gate/CI、当前 Rust v1 authority writer、migration archive/index 与 legacy
  evidence 边界；现有 GateEvidence 中的成功运行不得解释为 MSRV、fresh checkout
  或不可伪造人工评审已经成立；
- R0B evidence preparation = `in progress`，但具体工作包在 owner/reviewer/capacity 分配前仍为 `Planned`；G0B = `not evaluated`，当前尚无 G0B GateEvidence；
- R1 = `blocked by G0A`；
- WS-1 = `blocked by G1 + G0B`；
- 当前可以并行修正文档、ADR、fixture、数据锁和不写权威状态的研究实验；
- 当前不得实现生产 `LanguageState v3`、正式 reducer、Genesis 创建入口、大批生产规则或 Python/Rust 双写；
- 第一段 Rust 领域代码只能在 `G1 + G0B` 关闭后，以一个完整 WS-1 纵切进入。

## 2. 修正目标与允许声明

修正工作的近期目标不是“生成一门 Tolkien 级完整语言”，而是到 G2 交付一个可证伪的最小结果：

> 对两个结构非同构的微型语言轮廓，系统能够从结构化意义生成合法表达，再分析回等价意义；每个词形、词素、构式、规则和历史结果均可追溯、可迁移、可回放；无法表达时返回 typed gap，而不是静默丢义、随机造词或拼接 IPA。

G2 只允许声明“可执行微型语言与一次可审计结构变化”。真实社会传播、完整语言演化、语言家族、文学成熟度和史诗级表达仍须由 R3–R6 的独立证据支持。

所有假设继续分为四类：

| 类别 | 在修正中的处理 |
|---|---|
| 硬约束 | schema、constructor、validator、transaction 和测试直接拒绝违反项 |
| 经验先验 | 版本化数据、抽样单位、转换、置信和限制进入 `PriorPack` |
| 研究假设 | 进入可替换 `TheoryProfile`，接受敏感性、消融和不可辨识性检验 |
| 创作偏好 | 只参与候选约束或排序，不伪装成语言学因果规律 |

## 3. 已识别并在当前 WBS 修正的依赖错误

审计时的旧 WBS 曾把 `WS1-01A Language History + Ledger Integration` 放在 `WS1-01 RegistryBundle + State v3` 之前，同时又要求前者集成 typed ChangeSet；当前
`PRODUCT_DEVELOPMENT_PLAN.md` 已修正为 `WS1-01 → WS1-09 → WS1-01A`。真实
ChangeSet/reducer 必须先有最小 v3 aggregate；R1 只能用 deterministic fake artifact
验证平台生命周期。后续变更不得重新引入该倒置。

修正后的关键链为：

```text
现在
├─ COR-00 / COR-01 / COR-02A：缺陷台账、clean baseline、平台 ADR ─→ G0A
└─ COR-02B / COR-L00…L07：领域 ADR、反例、双 profile、TaskPack ─→ G0B

G0A
└─ ARC-10…ARC-14：application / ledger shell / staging / job ───→ G1

G1 + G0B（G0B 已包含 WS-1 所需 Accepted ADR）
└─ ARC-20 v2 冻结与迁移边界
   └─ ARC-21 最小 LanguageState v3
      ├─ COR-L08（依据 COR-L02…L07）→ ARC-22 typed ChangeSet / reducer
      │                  └─ ARC-23 append-only 领域历史 ─┐
      └─ COR-L07/L08 → ARC-24 Genesis compiler/evaluator ┴─→ ARC-25 seal/create/reopen → G2

G2 → R3 canon-safe authoring 与 legacy 逐域清理
G3 + G3B → WS-2 机制性变化 → G4
```

`ARC-23` 的实现可以与 Genesis 评价器后半段交错集成，但它的验收必须同时依赖 v3 与 validated ChangeSet，不能再由平台账本壳或完整状态替换冒充。此阶段只允许 Legacy/test root；生产 GenesisRoot 只能由 ARC-25 的 `VerifiedGenesisArtifact` 构造和原子发布。

## 4. Wave 0：立即执行的治理与基线修正

本 Wave 不写新的生产语言状态。

| ID | 映射 | 交付物 | Go 条件 | 规模 |
|---|---|---|---|---|
| COR-00 缺陷控制台账 | R0A-07、审计 P0/P1 | `问题 → 类别 → 当前证据 → ADR/schema → owner/reviewer → fixture → target gate → 关闭证据` 唯一台账；区分 Python legacy defect 与 Rust target gap | 每个 P0/P1 有唯一关闭判据；禁止只修输出字符串 | S |
| COR-01 G0A clean baseline | R0A-05/06 | 经逐项审查的 subject commit、fresh-checkout 运行、GateEvidence v2 输入 | R0A-05 的 clean baseline 可复核；本包不能单独宣称 G0A passed | M |
| COR-02A G0A 平台 ADR 收口 | R0A-02/03/04 | 独立评审并接受 ADR-011/012/013；固定 G0A 所需 platform/storage/RNG 依赖 | owner 不兼任独立 reviewer；仅 G0A/R1 范围内影响身份、回放和写入的决定已 Accepted | M |
| COR-02B G0B 领域 ADR 收口 | R0B-01/03/04 | 校正并独立评审 ADR-008 → ADR-014 → ADR-009 → ADR-010 → ADR-007；ADR-009 以前置 ADR-011 为界，ADR-010 以前置 ADR-011/012/013 为界 | 五个领域节点由指定 ADR 或 ADR Index 规则下的 Accepted replacement 按无环顺序闭合；不把 G0B 接受工作伪装成 G0A 前置 | M |
| COR-03 回归 fixture 起草与合同测试 | R0B-03/04、A-003 | 本文第 8、9 节的 planning-only fixture ID、输入、期望结果/错误和证据路径 | reviewed subject merge 前状态仅为 drafted + contract-tested；合并、登记 hash/reviewer 并满足 bundle evidence protocol 后才可称 frozen | M |
| COR-04 交付治理 | R0A-07 | owner、architecture/domain/migration reviewer、容量、S/M/L、WIP、timebox、降范围规则 | 缺任一字段的工作包不得进入 Ready | S |
| COR-05 Gate runner 与失败落盘修复 | R0A-05/06、审计 P0 | hermetic subprocess environment、实际执行计数、失败 run 原子落盘、旧 passed 降级 | `PYTEST_ADDOPTS=--collect-only`、插件/路径注入和中途失败均不能产生或保留 passed；evidence 为 blocked 时，STATUS 必须匹配或被删除后重建 | M |
| COR-06 Gate policy 与 attestation 生命周期 | R0A-06/07 | milestone attestation、普通后续提交规则、DeliveryReadinessEvidence、身份/时间/URI 验证与受信 provenance | 普通 R1 提交不被旧 milestone 永久阻断；capacity/estimate/WIP/timebox 不能靠手填 status 绕过；若不能兼容 v2 则先版本化 v3 | M |
| COR-07 MSRV 与跨平台 CI 复真 | A-001、B-001.1、R0A-05 | 真实 MSRV 决定、兼容 lock graph、精确工具链 gate、Linux Tauri prerequisites、Windows/Linux fresh-checkout | 声明的最低版本在两平台运行完整门；GateEvidence 绑定精确工具链和 CI provenance | M |
| COR-08 当前 v1 authority writer 修复 | B-004、FND-008/008.1、审计 P0 | lease 内 `create_if_absent`、无副作用 ProjectId 冲突、append-only history commit、限制 unconditional save | 双进程创建不能覆盖；任意截断/fork/rewrite 被拒绝；合法前缀扩展仍可保存；不改变 v1 schema | M |
| COR-09 当前 v1 migration/index 修复 | FND-008/008.1、R1-07 | archive 重读/hash 校验、清 journal 前复验、index authority-token/retry | 同名损坏/缺失 archive 和 save/query race 被 fault-injection 检出；当前热修不伪造新 journal 语义 | M |
| COR-10 Legacy evidence 与产品边界 | A-002/003、PLT-003/004 | raw replay/golden failure archive、failure fingerprint、Legacy Lab 入口/输出隔离、RNG/Mock LLM/golden workspace characterization | Python 不写 Rust project；8 个缺陷可独立复现；非法语言输出只作 negative evidence；不在 Python 建第二套修复核心 | M |

### 4.1 2026-07-19 复审后的前置链

这些包修复已经存在的基础实现和验证器，不授权 R1、v3、Genesis 或新的生产 writer。
当前 v1 热修只允许收紧已接受不变量；若修复需要改变持久化字段、实体意义、journal
schema、history identity 或 replay 语义，立即停止并先修订/接受对应 ADR。

```text
COR-05 hermetic gate + failure persistence
→ COR-07 honest MSRV / cross-platform CI
→ COR-06 Gate policy / milestone lifecycle
                         ┐
ADR-011/012/013 review ──┼→ COR-08 v1 writer safety → COR-09 archive/index
                         │
COR-10 legacy evidence ──┘
→ clean subject + independent review
→ regenerate blocked/passed evidence from the exact subject
→ re-evaluate G0A
```

`COR-08` 的最小修复不新增 schema：存在性检查与写入必须在同一 lease 内，提交候选必须
包含当前 history 的字节等价前缀。`COR-09` 的当前 journal 修复从内容寻址文件名重算并
验证 source hash；显式增加 source checksum、migrator identity/version 属于后续版本化
schema/ADR 工作，不得偷偷塞入 v1。

### 4.2 新增工作包的实施合同

#### COR-05：Gate runner 与失败落盘

- 唯一 Python test runner 必须净化 `PYTEST_ADDOPTS`、`PYTEST_PLUGINS`、注入式
  `PYTHONPATH`/coverage 配置，并证明 `collected > 0`、`executed > 0`、exit code 为零；
- `scripts/check.py`、完整 gate 与 targeted pytest 必须共用该 runner，不能保留直接
  pytest 旁路；
- 开始复验时旧 passed 必须先失效；preflight、command、final docs check 或异常失败都
  必须原子写入 blocked/failure run，再返回非零；
- evidence 是源，STATUS 是可重建派生物；写入采用同目录临时文件、flush/fsync 和
  replace；
- 必测 hostile cases：`--collect-only`、`-k nonexistent`、旧 passed + 中途失败、
  evidence 写成但 STATUS 写失败、subject/lock 改变。
- v2 只有在本次 attempt 能诚实捕获完整 environment、subject 和 lock hash 时才追加
  formal `verificationRun`；捕获不完整时仍必须把 decision 和软件明细落为 blocked，但
  不得复制历史环境或伪造 formal run。需要表达 partial attempt 的 schema 演进属于 COR-06。

2026-07-19 本地实施检查点：

- hermetic runner、非零 collected/executed 守卫、复验前 blocked checkpoint、失败明细保留
  及 evidence-first 输出恢复已经实现；这只是当前工作树上的实现结果，不是 GateEvidence；
- `python -I scripts/pytest_runner.py tests/core/test_pytest_runner.py
  tests/core/test_gate_evidence_generator.py -q` 得到 `33 passed`，runner 报告
  `collected=33, executed=33`；
- hostile `PYTEST_ADDOPTS=--collect-only` 的最终完整 `scripts/check.py` 检查实际执行
  `588` 项，得到 `580 passed, 8 xfailed`，没有退化为 collect-only；
- Windows 上精确 1.88.0 的 `cargo fmt --all --check`、`cargo test --workspace --locked`
  （62 项）、`cargo clippy --workspace --all-targets --locked -- -D warnings`、desktop
  locked build 与 `node --check` 已通过；这是 COR-07 的本地实现候选，不是 Linux、
  fresh-checkout 或跨平台 attestation；
- 已建立覆盖整个验证与发布窗口的跨进程单 verifier lease，并以锁竞争负例证明第二个
  publisher 不得修改 evidence/STATUS；两个文件仍不存在通用文件系统意义上的事务性
  crash 原子性。当前合同因此以 GateEvidence 为唯一权威，撕裂时 STATUS 必须被重写或
  删除并由 evidence 重建；
- Proposed G0A policy v2、GateEvidence v3、十项 requirement、完整 DeliveryReadiness
  结构与 v2→v3 强制降级已经形成本地实现候选；当前持久化候选明确为 `blocked`，没有
  继承旧 pass、reviewer 或远端 provenance；
- COR-05 仍等待独立复核、clean subject 与最终全门证据，不能单独标记 Closed；G0A 保持
  `blocked`，R0A-08 还必须取得 COR-07 的 Linux/fresh-checkout CI 与受信 provenance。

#### COR-06：Gate policy 与人类治理

- 已确认 pass 条件与 reviewer 意义改变，因而创建 Proposed GateEvidence v3 与 policy
  v2；v2→v3 强制降为 blocked 并清除旧 pass/review；
- 普通后续代码提交只验证历史 milestone 内部完整性；只有受保护合同/fixture/lock
  改变才触发重审，`require-current-subject` 仅用于 gate/release workflow；
- 新增结构化 DeliveryReadinessEvidence，覆盖 owner、independent reviewer、capacity、
  estimate、WIP、UTC timebox、降范围规则、有效期和审批引用；
- reviewer evidence 必须启用 URI/UTC 语义校验，并绑定签名 statement 或受信 provider
  的 account/review/subject/decision；自由字符串不能满足 pass；
- Agent 可以实现 schema/validator，但不得虚构人员、容量、日期或批准。

#### COR-07：MSRV 与 CI

- 先以当前 lock graph 的真实最低要求验证候选 MSRV；若选择提升，统一
  `Cargo.toml`、`rust-toolchain.toml`、CI 和 evidence；若坚持 1.77.2，另做受审查的
  dependency downgrade/re-lock；
- generator 必须调用并记录精确工具链，不接受“更高版本也通过”代替 MSRV；
- Ubuntu desktop job 安装 Tauri 原生依赖；Windows/Linux 都运行 locked
  fmt/test/clippy 和 desktop build/check；
- Python CI 先采用无缓存可靠安装顺序，Poetry cache 优化不得阻塞正确性；
- 旧 Rust verificationRuns 全部失效，最终 evidence 记录 workflow run/check identity
  和 artifact digest。

2026-07-19 COR-07 本地实现候选：

- `cargo metadata --locked` 显示 locked graph 的最高依赖 `rust-version` 为 1.88.0；
  选择提升当前 MSRV，而不是把 Tauri 依赖图降级到未经评审的旧版本；
- workspace `rust-version`、`rust-toolchain.toml`、generator 的当前协议/validator 和
  CI 已统一到精确 1.88.0；Cargo resolver 使用 MSRV-compatible fallback，
  v1 schema 的 1.77.2 继续作为历史迁移输入保留；
- Windows 上 exact-1.88.0 fmt、62 项 workspace tests、Clippy `-D warnings`、desktop
  locked build 和 JavaScript syntax check 已通过；
- 新增 10 项工具链/CI 合同负例，拒绝较新 Rust/Cargo 冒充 MSRV、
  workspace/toolchain 漂移、缺失/损坏 toolchain 的旧 pass 残留、job-level context
  越界、平台矩阵缺口与过早 Poetry cache；与 COR-05 runner/evidence 测试合并后为
  `43 passed, collected=43, executed=43`；
- 最终 exact-1.88.0 GateEvidence 本地验证实际执行完整 Python 套件 `598` 项，得到
  `590 passed, 8 xfailed`，随后 9 个登记协议全部直接通过；decision 仍因治理与远端
  证据阻断保持 `blocked`；
- Linux job 已按 Tauri 官方 Debian/Ubuntu 前置安装原生包并使用相同 locked commands，
  但本地修改尚未形成 reviewed clean subject，也没有远端 run/check identity 或 artifact
  digest。因此 COR-07/P1-19 只能标为 locally mitigated，不能 Closed；
- 本地合同测试会拒绝当前 workflow 使用过的 job-level context 越界；另以 MIT 许可的
  `actionlint 1.7.12` 对当前 workflow 通过一次性复核，Windows amd64 release archive
  SHA-256 为 `6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9`。
  它尚未纳入必需门，GitHub 服务端解析与真实调度仍是远端验收的一部分；
- Windows/Linux provenance 如何进入 GateEvidence 的正式语义属于 COR-06/v3；在该决定
  前不向 v2 填造 provider、run ID 或 artifact digest。
- v2 的 `rustVersionMeetsWorkspace` 当前 validator 由“版本不低于”收紧为“Rust 与
  Cargo 都精确等于 workspace MSRV”；schema 的版本字符串约束保持向后可表达历史 run，
  当前旧 run 因协议/fingerprint 改变全部失效。该 policy amendment 不增加跨平台
  provenance；若以后需要独立 exact-match 字段，由 v3 版本化。

#### COR-08：当前 v1 writer

- 在 core 增加 `candidate.validate_extension_of(base)`：context 相同、旧事件逐项完全
  相同、只能追加合法尾部；等长完全相同可以幂等，其余截断/重排/fork/rewrite 拒绝；
- storage 提供 lease 内 `create_if_absent` 和 `append_if_current`；公共 unconditional
  replacement 降为迁移/恢复私有实现；
- create 同时拒绝现有 authority、recovery artifact 或 pending migration；失败不得在
  磁盘留下新项目，ProjectId 冲突在写入前处理；
- runtime 的 expected hash 同时匹配打开 session 和 lease 内权威文件；
- 必测同进程/跨进程/路径别名双创建，以及截断、旧事件修改、重排、fork、外部 run、
  合法多事件追加和幂等重复。

#### COR-09：当前 v1 migration 与 projection

- archive 存在时重读并验证内容 hash 与 `<sha256>.source.json` 文件名；拒绝越出
  migrations 目录的链接/重解析；
- completed target 清 journal 前，archive、source schema、唯一 migrator、重演 target
  hash 和当前 target 必须闭合；任何证据缺失都保留材料并返回人工恢复错误；
- index publish 绑定读取时 authority hash；重建前取得 lease 并重读 authority，查询
  返回 `as_of_history_sha256`，竞争时有限重试或 `projection_stale`；
- 必测 archive 缺失/损坏/链接、各 crash point、多 reader + writer、SQLite 删除/损坏；
  任何失败不得改变 authority bytes。

#### COR-10：Legacy evidence

- 冻结被测 commit、环境、命令、seed/clock、原始未归一化字节、目录 manifest、
  SHA-256 和准确 failure fingerprint；
- 记录 8 个 replay loss、22–31 个非法 golden、RNG 顺序敏感性、query mutation、
  `uuid4` 借词 ID、Mock LLM 实际 disabled 和非空 workspace 污染；
- Python 只修测试工具、入口警告、输出隔离、Mock/golden characterization 和未受控
  随机源守卫；不修旧音系、语义 fallback、形态 query、DAG/replay 或新增语言模型；
- README/CLI/Streamlit 统一标为 Legacy/Research Lab，输出不得落入 Rust project root；
  对应 Rust replacement 与 migration reviewer 关闭前不得删除模块或 xfail。

G0A 的实际执行顺序：

1. 先为 COR-05～10 与 COR-02A/04 分配 owner、独立 reviewer、容量、WIP 和 timebox；未分配前保持 `Planned`。
2. 将 COR-05/07 的本地实现检查点经独立复核与 clean subject 收口，并在 Windows/Linux
   远端门产生受信运行证据；旧 GateEvidence 继续保持 blocked，不在修复中手工改成 passed。
3. 评审 Gate milestone 生命周期和 DeliveryReadinessEvidence；若需要改变 manifest 含义，先版本化 schema，再实施 COR-06。
4. 由具名 owner、独立架构 reviewer 和 migration reviewer 处理 ADR-011/012/013；随后按当前/目标语义边界实施 COR-08/09。
5. 并行完成 COR-10 的原始证据冻结和 Python 产品边界，不修复 Python 语言模型。
6. 使用 `scripts/g0a_handoff.py --check --json` 审查工作树，不以 `git add -A` 代替判断；语义修改、fixture/baseline、移动/删除必须分成不同提交。
7. 创建 clean subject commit，并运行 `scripts/g0a_handoff.py --check --require-clean-subject`。
8. 在 Windows 与 Linux fresh checkout 使用精确声明工具链运行完整门；Gate evidence job 聚合受信运行身份与 artifact hash。
9. 将 GateEvidence/STATUS 作为独立 attestation 提交，并重新评估 G0A；失败必须将磁盘状态原子保持为 blocked。

不得为了让当前脏工作树通过而刷新 inventory hash。GateEvidence 因输入改变而失效是正确行为。

计划中的评审顺序为：COR-02A 平台侧先闭合 ADR-011，再闭合依赖它的 ADR-012；ADR-013 可并行评审，但必须先冻结 wire representation 与 known-answer。COR-02B 领域侧按 `ADR-008 Registry → ADR-014 Identity/Realization → ADR-009 ChangeSet → ADR-010 Genesis → ADR-007 umbrella` 收口；各节点允许 ADR Index 规则下的 Accepted replacement。ADR-009 的跨 Gate 前置是 ADR-011，ADR-010 的跨 Gate 前置是 ADR-011/012/013。G0B 证据准备不以完整 G0A clean-baseline 证明为前置，但相关平台 ADR 未 Accepted 时不得接受对应领域 ADR；ADR-014 必须先消除 ChangeSet 所作用对象的跨域身份歧义，ADR-009/010 才能最终接受。若 ADR 正文显示不同依赖，立即停止并先修正依赖图。

## 5. Wave 1：G0B 领域修正包

这些包现在可以起草、评审和 fixture 化，但在 G1 + G0B 前不得成为生产 v3 writer。

| ID | 对应现有包 | 主要交付物 | 最低验收 | 规模 |
|---|---|---|---|---|
| COR-L00 缺陷反例化 | R0B-03/04 | P0/P1、fixture、Gate、owner/reviewer 映射 | 所有 legacy 缺陷都有 Rust negative/migration target；不复制 Python 缺陷 | S |
| COR-L01 ADR-014 | R0A-02、R0B-01、R0B-01A-D/01A、R0B-04B-D | Meaning–Grammar–Lexical Class–Realization–Orthography 权威决定 | 先起草 ADR，再用 review vectors 攻击，随后才 Accepted；冻结稳定 `OrthographicForm/SpellingRealization` 身份、所有权、ordered occurrence、query purity、migration/hash/replay；裸 IPA/音系串不作为拼写身份键；Accepted 前不实现持久化语义 | M |
| COR-L02 类型化音系合同 | R0B-03、WS1-01/04/09 | Segment/Feature、韵律、音系配列、typed SoundChange IR | unknown/empty/no licensed nucleus/illegal cluster/unanchored suprasegmental 均 typed reject | M |
| COR-L03 词汇—形态身份合同 | R0B-01/03、WS1-01/03/04 | Lexeme、Sense、WordForm、Morpheme、Paradigm、Construction、SurfaceForm | 序列不用 set；同音、多义、零实现和 syncretism 可表达、可分析 | M |
| COR-L04 双向实现合同 | R0B-01/04/04B-D/04B、WS1-02/03/04A/08 | Meaning → realization → analysis、typed analysis ↔ orthography、同图 IGT、trace、typed gap | `analyse(realize(M))` 与 `parse(spell(A, O), O)` 包含等价分析且拒绝 forbidden analysis；同音异写、precision/ambiguity、非双射 IGT span 通过；query 不改 hash | L |
| COR-L05 配价与对齐合同 | R0B-01/03/04 | PredicateFrame、S/A/P、语义角色、编码与 alternation | 覆盖不及物、及物、心理/感知、三价转移、处所；不将英语 subject/NOM 普遍化 | M |
| COR-L05A Evidence/Data Execution Slice | R0B-05/07 | 精确 payload/hash/license/sampling unit/transform、数据到 Registry/PriorPack/TaskCase 的可执行小切片 | payload-aware reference 通过；概念表、类型频率和 usage frequency 不可互换 | M |
| COR-L06 双 profile fixture | R0B-03/04/05、WS1-04/06 | 两个结构非同构的微型语言 specification | 相同任务由不同构式/形态机制完成，不能只换词序或标签 | L |
| COR-L07 独立 evaluator | R0B-04/07、WS1-06 | 四类 TaskPack、缺陷注入、sealed audit、分项报告 | 不导入 compiler 私有评分；无 writer、无未受控 RNG；能检出人工缺陷 | M |

ADR-014 至少必须决定：

- `Lexeme → Sense → PredicateFrame` 的身份与所有权；
- `WordForm → Lexeme + FeatureBundle`、`Paradigm → ParadigmCell`；
- ordered `MorphOccurrence` 与 zero、syncretism、fusion、allomorphy、defectiveness 的身份边界；
- `Construction` 如何绑定意义、typed slots、selection、linearization 和 realization；
- `generate/analyze/IGT/trace` 的权威输出与歧义语义；
- `ExpressionGap`、silent fallback、query purity、provenance、semantic hash 和 replay；
- v2 无法恢复的历史如何进入 `LegacyHistoryBoundary + loss report`，而不是伪造事件。

### 5.1 两个非同构验证轮廓

Profile A：

- 主宾对齐；
- VSO、头初；
- 谓词头标记，独立主语代词可省；
- 属性概念使用状态谓词/关系式修饰；
- possession 标记在 possessed head。

Profile B：

- 作格—绝对格；
- SOV、头末；
- dependent ERG/ABS 与后置词；
- 无强制谓词一致；
- 独立修饰构式；
- possessor dependent marking。

两者是验证 fixture 和创作 specification，不是类型学普遍组合。它们必须完成相同的 reference、predication、modification、deixis、negation、question、possession，以及不及物、及物、感知/心理、三价转移和处所任务。

### 5.2 理论与数据责任

理论或数据库只能支持相应的有限决定，不能升级成普遍硬律：

| 依据 | 在计划中的合法用途 | 禁止推断 |
|---|---|---|
| CLTS / PHOIBLE | 音段、特征与 inventory 数据对齐 | 数据库存在某组合不等于每个候选都合理 |
| Hayes–Wilson 类 MaxEnt 音系配列 | hard validator 之后的可选梯度排序参考 | 高分不能救活 hard-invalid form |
| Haspelmath 的比较概念区分 | language-internal category 与 comparative concept 分离 | 不强制每种语言有英语式 pronoun/adjective POS |
| UniMorph / finite-state morphology | Lexeme + FeatureBundle + WordForm 以及双向形态边界 | 表格标签不自动证明真实语言范式 |
| GF / MRS | 抽象意义、实现与分析分层的工程参考 | 不把某一形式语义框架当唯一语言理论 |
| ValPaL | predicate-specific valency、编码与 alternation 任务 | 不把 agent/patient 二分当全部论元结构 |
| Hopper–Traugott / Albright / Blevins–Wedel | 约束语法化、范式类推、同音/functional-load 的负例与 WS-2 假设 | 不将统计关联变成确定性修复规则 |

Concepticon/CLICS 只提供概念锚点与可能的 colexification 先验，不提供 silent fallback 的方向；Grambank/WALS 只做覆盖检查，不生成硬类型包。所有数据必须经过 R0B-05 的版本、license、抽样单位、转换和 payload hash 锁。

### 5.3 初始 G0B/G2 工程阈值

以下只适用于已冻结 Capability Matrix 与当前版本 TaskPack，是首个纵切的硬软件验收，不是“人类语言普遍律”：

- 两个 profile 的 supported hard tasks：100%；
- forbidden-reading acceptance：0；
- hard phonological errors：0；
- supported task roundtrip：100% 包含经独立 equivalence checker 确认的等价分析，并通过 contrastive foils；
- 对所有声明为 `planned` 或 `rejected` 的冻结负例，typed gap 分类正确率：100%；
- query 导致的 semantic-hash mutation：0；
- 锁定输入、版本、数据、规则和 RNG 时跨进程结果一致；
- ambiguity、under-generation、over-generation 分别报告，不压成单一“自然度”分数。

TaskPack 按 `Development / CandidateSelection / SealedAudit / ExternalElicitation` 分组。SealedAudit 一旦被参与同轮 compiler/candidate 调参的人员查看，就失去该轮 sealed 证据资格，且不得反馈给同轮候选排序；按审计协议隔离的独立 reviewer 可以检查并留下 attestation。

Evaluator 若需要抽样或缺陷注入，必须使用独立、版本化且进入证据的 evaluator `RngTree` path；不得复用 compiler 私有随机流，也不得使用未受控随机源。

## 6. Wave 2：G0A 后的 R1 平台修正

R1 只使用 deterministic fake operation，验证产品生命周期而不冻结 LanguageState v3。

| ID | 对应现有包 | 交付物 | Go 条件 |
|---|---|---|---|
| ARC-10 Application Boundary | R1-01 | `telysta-application`；desktop 只调用 versioned command/query | dependency-direction CI；desktop 无 storage writer/transaction 编排；core 无 Tauri/async |
| ARC-11 Strict Wire & Capability | R1-03/06 | closed tagged DTO、schema version、`Untrusted<T> → Validated<T>`、idempotency、稳定 seed wire | unknown field/wrong union/hash tamper 全部拒绝；普通 serde 不能伪造 validated capability |
| ARC-12 Append-only Ledger Shell | R1-01A | Project/Operation/Run ledger、parent hash/sequence、LegacyHistoryBoundary；只运行 fake task | 不可换序、删改或覆盖；Job/Attempt 不进入 language semantic hash |
| ARC-13 Single-Publish Package | R1-04/05 | immutable object + 单一 manifest 发布点、lease、recovery、GC | 每个 crash point 只暴露完整前态或后态；缺失/篡改对象拒载 |
| ARC-14 Job/Staging/Dependency | R1-02A～E、R1-09/10 | Job journal、staging、Restart/Resume locks、DependencyBundle/ReplayCapability | stale staging 不可提交；缺 RNG frontier 只能 Restart；缺 payload 不得从 URI/latest 猜测 |

G1 的证据必须覆盖 unit、schema compatibility、fault injection、migration corpus、cross-process、IPC 和 benchmark。G1 只允许声明“平台 walking skeleton 完成”，不允许声明“已经生成语言”。

## 7. Wave 3：G1 + G0B 后的 Rust WS-1 纵切

| ID | 依赖 | 交付物 | 最低验收 |
|---|---|---|---|
| ARC-20 v2 Freeze & Migration Boundary | G1、G0B（其中已包含 Accepted ADR-009） | v2 bytes/schema/hash/golden corpus、source archive、loss fixture | 同一 source bytes 产生相同 target hash/loss report；不从 state diff 伪造历史；G0B 前只可在 COR-03 中准备 planning evidence |
| ARC-21 Minimal State v3 + Provenance | ARC-20、Accepted ADR-007/008/014 | strict aggregate、RegistryBundle、typed values、ordered occurrences、ProvenanceGraph、ExecutableDataSliceRef | hostile deserialize、悬空引用、错误值域和无序序列拒绝；每个 Genesis entity 可追溯 |
| COR-L08 Executable Linguistic Slice | ARC-21、COR-L02/03/04/05/05A/06/07、R0B-04B | in-memory Meaning/Grammar、phonology、morphology、stable orthographic realization、realize/analyze/parse/spell roundtrip、IGT/explain | 两个 profile 完成本计划阈值；同音异写与保守拼写可保持；音变不静默重拼写；零 silent fallback；尚不绕过 Genesis seal 创建项目 |
| ARC-22 Typed ChangeSet + Reducer | ARC-21、COR-L08、Accepted ADR-009 | `Proposal → ValidatedChangeSet` capability、typed effect/environment/lock、atomic reducer | 多 effect 全成全败；wrong locus/stale base/tampered lock 拒绝；online=replay hash |
| ARC-23 Append-only Domain History | ARC-22、ARC-13 | history node、Legacy/test root + parent-linked committed ChangeSet | 非前缀、换序、删改、同 Operation 异结果拒绝；删除 projection 后可完整 replay；不得构造生产 GenesisRoot |
| ARC-24 Genesis Compile/Evaluate | ARC-21、COR-L07/08 | deterministic CandidateSet、独立 evaluator、hard-error report | compiler 与 evaluator 不共享私有评分；缺依赖或 planned capability 不能 seal |
| ARC-25 Genesis Seal + Atomic Create | ARC-23/24、Accepted ADR-010 | 私有 `VerifiedGenesisArtifact`、生产 GenesisRoot materialization、原子 create/reopen/import-reverify | 只有 VerifiedGenesisArtifact 能创建生产 GenesisRoot；客户端不能提交 State/history/“verified JSON”；逐项篡改失败；崩溃不留半项目 |
| COR-L09 Tauri Proof-Carrying Slice | ARC-25、COR-L08 | Blueprint → candidates → create/reopen → realize/analyze → change diff/why | 不编辑 JSON 完成全链；取消/崩溃/重试无第二 writer；能力矩阵与 UI 同源 |

WS-1 的首个 typed structural-transform 验证候选是末元音删除，最终是否采用仍由音系合同和 fixture 评审决定：

- `/kano/ → /kan/`：仅当目标 profile 的音系配列许可 `/kan/` 时通过；
- `/go/ → /g/`：若目标 profile 要求许可核，按该验证 fixture 的 proposal policy 原子失败或要求显式 repair；
- 系统不得让 `/g/` 先成为权威词形，再通过同音“修复”产生 `/gg/`。

这里验证的是 reducer/validator 的原子性，不推出“真实音变遇到非法结果必然整体停止”的语言学普遍律；后续 TheoryProfile 可显式提出 blocking、repair、reanalysis 或异质采用模型，但不能静默制造非法权威状态。

<a id="8-必须冻结的语言学回归-fixture"></a>
<a id="linguistic-regression-fixtures-v1"></a>

## 8. 必须起草、合同测试并在 reviewed merge 后冻结的语言学回归 fixture

本 v1 bundle 仍是 `future_not_bound` 的 planning evidence。每个 case 同时记录四类
`assumptionClass`、工程/数据/领域 `contractKind` 和 claim scope，避免把软件不变量、
数据语义或 profile 选择误写成语言学普遍律。绑定真实 runner 前必须先冻结 versioned
adapter schema，并证明 negative case 的 baseline 合法；case 必须明确区分
single-fault、batch diagnostic、insufficient-evidence bundle 或 metamorphic contract。
SEM-N01/EVT-N01 是显式 batch coverage，不冒充单故障；GRA-N01/ANA-N01 是证据充足性
bundle。DET-N01 的 planning locks 是显式 sentinel，真实 payload 绑定前不构成确定性
证据。Planning contract test 只检查这些声明和输入结构，不执行未来 Rust runner。

| Fixture ID | 必须证明 |
|---|---|
| PH-N01 | unknown segment 被拒绝 |
| PH-N02 | 空词形被拒绝 |
| PH-N03 | vowel-nucleus profile 中 `/g/` 因无许可核被拒绝 |
| PH-N04 | `/anta/` 的同一 segment occurrence 不得同时占前一 coda 和后一 onset |
| PH-N05 | `/go/ → /g/` 违反核约束时 ChangeSet 原子失败 |
| PH-N06 | max-onset 与许可 cluster 自相矛盾的数据被拒绝 |
| PH-P01 | profile 明确许可 syllabic consonant 时，对应正例通过，不把“元音核”写成普遍律 |
| CAP-N01 | `planned/rejected` 能力，尤其未实现的 insert rule，返回 typed error 而非 silent no-op |
| CAT-N01 | 未设独立 pronoun/adjective 词类但相关功能已由构式实现时，不得判语言“不完整” |
| LEX-N01 | 多个 Lexeme 可共享 comparative concept；单一 Lexeme 可拥有多个 Sense |
| HOM-N01 | 两个 Lexeme 可同音并长期共存，不自动叠词、加缀或标死 |
| HOM-N02 | 音变产生同音本身不是 hard failure |
| MOR-N01 | zero 与 syncretism 返回合法多分析，而非丢失 morpheme/feature |
| MOR-N02 | compound 保留 ordered parents、角色和 morpheme boundary，不按 IPA 字符串切半 |
| SEM-N01 | BAD 不得后备实现成 GOOD；BELOW 不得实现成 ABOVE |
| SEM-N02 | I 与 we 不得坍缩为同一 feature bundle |
| VAL-N01 | 作格 profile 中 `A → ERG`、`S/P → ABS` |
| VAL-N02 | experiencer/stimulus 与 donor/theme/recipient 不得丢失 |
| QRY-N01 | realize/analyze/evaluate 前后 semantic hash 不变 |
| DET-N01 | 锁定输入和 RNG 时跨进程结果稳定；语义字段变化必须改变 StateSemanticHash，非语义字段变化不得改变它，禁止恒定 hash 假实现 |
| DATA-N01 | Concepticon/Swadesh 序号不得被解释为 token/usage frequency |
| EVT-N01 | grammaticalization、analogy、analogical homophone repair 不得编码为 SoundChange；其他同音回避机制必须先类型化，不能从“同音”标签推断事件种类 |
| GRA-N01 | 无源构式、桥接语境和旧新分析时，不得仅凭 gloss/频率/侵蚀次数声称语法化 |
| ANA-N01 | 无共享范式/构式时，不得仅凭音形相似声称类推 |

类型化音系必须把 categorical validator 与可选 gradient ranker 分开；梯度高分不能救活违反硬约束的候选。Genesis、借词、复合、形态音系和变化必须共享同一最终 validator。

### 8.1 Orthography / IGT / PCU 扩展包（尚未起草）

当前 24-case v1 不覆盖正字法权威与同图 IGT，不能用于接受新增 authority。执行顺序
必须是 `R0B-01A-D Proposed ADR → R0B-04B-D review vectors → R0B-01A Accepted
ADR → R0B-04B reviewed/frozen fixture → G2 real adapter evidence`。review vectors
可以随 Proposed ADR 修订，不是 frozen evidence；ADR 接受后的 fixture 必须重新登记
schema/version、content hash、reviewer 和 expected diagnostics。

| Planned vector | 必须证明 |
|---|---|
| ORT-N01 | 未映射 typed analysis 返回诊断，不回退 raw IPA |
| ORT-N02 | NFC/NFD、非法字素和边界冲突不会产生静默不同结果 |
| ORT-N03 | 同音但词汇化/保守拼写不同的 WordForm 可保持不同 `SpellingRealization` |
| ORT-N04 | 万能 analyzer 因 forbidden analysis、precision 或 ambiguity budget 失败 |
| ORT-P01 | `parse(spell(A, O), O)` 保留等价 typed analysis，许可 variant 可稳定往返 |
| IGT-N01 | zero、syncretism、fusion 的 span/contribution 从同一分析图投影 |
| PCU-N01 | 手改 orthographic/gloss line 会使 ProofCarryingUtterance integrity 失败 |
| CHG-N01 | `SoundChange` 不静默改写 spelling；只有独立 `OrthographicChange` 可重拼写 |

## 9. Legacy replay 缺陷迁移

现有 replay 特征测试的 8 个独立 strict-xfail 在 planning draft 中编号为
`LEGACY-REPLAY-001..008`；只有 reviewed subject merge、hash/reviewer 登记以及
fixture evidence protocol 要求的 source revision、test run、environment、timestamp
和 result fingerprint 完成后，这组 ID 才进入 frozen 状态：

当前 001..007 只是 synthetic minimal producer-wire vector，008 只是未附运行目录的
absence claim；它们锁定迁移问题和 forbidden inference，不声称是历史运行的 raw
execution archive。正式 migration Gate 仍须补齐不可变 source bytes/目录 manifest、
raw SHA-256、source revision、命令、环境、seed/clock 与 run fingerprint。

| ID | 缺陷 | Rust 目标 |
|---|---|---|
| LEGACY-REPLAY-001 | 完整状态/DAG 未恢复 | 删除派生 snapshot 后 full semantic hash 相同 |
| LEGACY-REPLAY-002 | protection set 丢失 | 经 ADR 决定其属于 operation/model policy 还是权威状态；禁止猜测 |
| LEGACY-REPLAY-003 | typology snapshot 丢失 | typed assertion 可迁移；derived diagnostic 重算 |
| LEGACY-REPLAY-004 | decoder 丢字段 | strict typed decode；必需字段缺失和未知字段均拒绝 |
| LEGACY-REPLAY-005 | borrowing parent 丢失 | 单父 lineage effect、存在性、edge type、provenance 和无环验证 |
| LEGACY-REPLAY-006 | fossil parent 丢失 | 独立 fossil lineage effect，不与 borrowing 共用宽松事件 |
| LEGACY-REPLAY-007 | compound 双父丢失 | 双父基数、顺序/角色与 lineage 可回放 |
| LEGACY-REPLAY-008 | Epoch 注词无事件 | 进入 `LegacyHistoryBoundary + loss report`；不得伪造历史事件 |

每个 xfail 的唯一退役链：

```text
Python strict xfail
→ Rust migration / negative fixture
→ Rust target contract passing
→ migration matrix + source hash + loss report
→ migration reviewer 批准
→ 删除旧 xfail
```

禁止改成 broad skip、添加猜测默认值、放宽断言或合成不存在的历史事件。

旧 Python writer 使用平台原生换行，因此 Windows 与类 Unix 主机上同一 JSON
payload 的原始文件字节不同。Planning fixture 对 producer wire 采用 LF 归一化后
的 payload hash，并通过真实 `KeyframeManager` 写入路径验证当前平台产物；正式迁移
归档仍必须保留原始 source bytes、原始 SHA-256、平台/换行元数据，不得用归一化文件
替换原档。

## 10. 验证矩阵

| 层级 | 必需证据 |
|---|---|
| Unit | constructor、不变量、typed target/environment/effect、父节点基数、Registry 值域和 capability |
| Property | 合法小状态序列满足原子性、序列化往返和 online/replay 等价；失败 effect 不改变 head/hash/event count |
| Replay | 删除 snapshot/index/projection 后，由 Genesis 或 LegacyBoundary + events 重建全 hash 与分域 hash |
| Migration | 同 source bytes 得到同 target hash/loss report；原 bytes 归档；未知版本拒绝；crash 恢复到完整前态或后态 |
| Semantic hash | map/JSON 顺序不影响 hash；权威字段改变相应 hash；Job/Attempt/cache/projection 不改变 language hash |
| Hostile input | unknown schema/field/feature、planned capability、ID kind 错误、重复 ID、悬空引用、cycle、hash/head/RNG lock 篡改均拒绝且不 panic |
| Evaluator | false acceptance/false rejection、forbidden reading、under/over-generation、ambiguity、gap correctness 和 construction coverage 分项报告 |
| Scientific | verification、calibration、held-out validation、sensitivity、ablation、parameter recovery、identifiability 分开 |
| UI/E2E | Webview 不能提交 State/Genesis JSON；cancel/crash/retry 不产生半项目或第二 writer |

在引入 `proptest`、`quickcheck` 或其他新依赖前，先用受限生成器证明 property 范围，再按仓库依赖、license 和 advisory 流程评审。

另建立 `HashCoverageManifest`：逐字段记录 included/excluded、理由、hash 版本和影响域。v2/v3 迁移比较映射与 loss report，不要求不同 schema 的原始 hash 字符串相等。

## 11. 推迟到 WS-2 的机制

WS-1 只建立可承载下列过程的身份、接口和反例，不提前伪实现：

- frequency-conditioned lexical diffusion；
- 语法化的桥接语境、重分析、共存、采用与常规化；
- 范式类推的生产力和社会传播；
- functional load 对音变的概率影响；
- innovation、variation、adoption、diffusion/transmission；
- SpeechCommunity、接触、威望、网络传播；
- complex chain shift、phonemic split/merger、feeding/counterfeeding 的机制比较；
- 历时语义变化、lexical replacement 与词汇竞争；
- 借词/接触变体的采用与传播；
- suppletion、irregularization 的形成过程；其共时表示可在 R3 合同允许时实现，但不能提前伪造形成历史。

WS-2 必须将“规则适用”“个体变体”“群体采用”“结构常规化”拆成不同事件与状态。环境、气候、奇幻族群和审美只可经有证据的交际/社会变量或创作偏好进入候选，不得成为直接音系/语法因果律。

## 12. 清理与大型重构放行条件

大型重构是允许的，但必须以迁移和纵切证据为边界，而不是按文件数量推进。

任何 legacy 模块、fixture 或 xfail 只有同时满足以下条件才可删除：

- [模块迁移矩阵](./MODULE_MIGRATION_MATRIX.md)已有 Rust replacement 或明确废弃决定；
- replacement contract 和对应 negative fixture 已通过；
- 旧项目 migration fixture、source archive、loss report 可审计；
- production、dynamic registration、data-driven entry 均确认无调用；
- Python 不再是 writer，且不存在临时双写；
- semantic-hash/golden 变化已由 reviewer 批准；
- clean checkout 全门通过；
- Capability Matrix、文档和用户声明同步；
- 删除/移动使用独立提交，不与语义修改混合。

清理顺序遵循[代码与模块清理计划](./CLEANUP_PLAN.md)：

```text
冻结 legacy 行为与缺陷
→ Rust replacement contract
→ migration / negative / replay evidence
→ 切断生产入口
→ 观察一个发布窗口
→ 独立删除提交
```

不得因为静态不可达直接删除；不得把 Python 保留为回滚 writer。回滚依靠 source archive、migration journal、版本化 reader 和提交回退。

## 13. WIP、职责与 Stop 条件

在具名 owner 与真实容量尚未回写 R0A-07 前，下列数值是 proposed initial WIP，不是已经批准的 Gate 条件；经责任人接受后才成为该 delivery wave 的硬上限：

- 全仓最多两个进行中包：一个平台/仓库包，一个只读领域证据包；
- 同时最多一个包涉及 schema、identity、writer、replay 或 semantic hash；
- owner 不得兼任独立 reviewer；
- 没有真实容量、估算、timebox 和降范围规则的包不得 Ready；
- 纵切超时就缩小同一纵切，不通过开启第二个领域“追进度”。

任一情形触发 Stop：

- persisted identity、writer、replay 或 plugin boundary 改变但无 Accepted ADR；
- client、LLM、storage 或普通 serde 能自行授予 validated capability；
- 用多个可变文件顺序替换冒充原子提交；
- v3 接受通用 JSON Patch 或完整状态 replacement；
- metadata-only `DataReference` 进入 compiler；
- provenance 只能表达单一父来源；
- query、realizer 或 evaluator 产生 ChangeSet；
- validator 把 hard error 降为 warning；
- 使用 IPA/词类字符串代替已有 typed feature 或 identity；
- 第二 profile 只能通过复制标签完成；
- 迁移需要猜测未知历史；
- 测试只断言“有输出”“不相同”或单一 golden hash。

## 14. 下一批实际执行队列

2026-07-18 已完成 planning preparation：

- 建立[缺陷控制台账](./AUDIT_DEFECT_LEDGER_2026-07-18.md)；
- 创建 ADR-014 Proposed 草案；
- 起草 24 个 linguistic regression case 与 8 个 legacy migration case，并通过 planning-only contract tests；它们尚未 reviewed merge，legacy execution evidence 也未附着，因此不称 frozen；
- 增加 planning-only fixture contract tests；
- 修正 ADR-008 → ADR-014 → ADR-009 → ADR-010 → ADR-007 的依赖。

在没有人为越权接受 ADR 或伪造 Gate 之前，下一批按以下顺序推进：

1. 为 COR-00～10、COR-02B 与 COR-L00～L07 填写具名 owner、独立 reviewer、容量和 timebox。
2. 复核并收口 COR-05 → 为 COR-07 取得 Linux/fresh-checkout CI 证据 → COR-06，使测试执行、工具链和 Gate 生命周期本身先可信；当前 COR-05/07 仅达到本地实现检查点。
3. 独立评审 ADR-011/012/013；随后完成 COR-08/09 的 v1 writer、archive 和 index 修复，并执行并发/故障注入测试。
4. 完成 COR-10：冻结 8 个 replay 缺陷、非法 golden、RNG 顺序敏感性与 query mutation 的原始证据；将 Python 入口明确为 Legacy Lab。
5. 逐项审查 subject candidates，形成 Windows/Linux 可复核的 clean subject；不使用 `git add -A`，不进行大规模移动或删除。
6. 独立评审 ADR-014 和对应 fixture；冻结 Meaning/Grammar/Realization、typed phonology、lexical identity/morphology、valency四份 G0B 合同。
7. 冻结两个非同构 profile、Capability Matrix、四类 TaskPack、runner adapter 和真实数据小切片；`DATA-N01` 在 G0B 执行，21 个语言生成 case 在 G2 执行，`GRA-N01/ANA-N01` 在 G4 执行。
8. 重新生成 GateEvidence 并关闭 G0A 后，仅启动 ARC-10～14 的 fake-operation 平台纵切。
9. 关闭 G1 + G0B 后，再启动 ARC-20/21 与 COR-L08；随后以 ARC-22/23/24/25 完成 ChangeSet、历史、Genesis seal 和原子创建。
10. G2 通过后才进入 canon-safe authoring、逐域 legacy 清理和 R3；G3 + G3B 后才进入 WS-2。

下一段生产领域代码仍然不是“更多音变规则”，而是 Gate 放行后的 Rust 最小 v3 纵切。
