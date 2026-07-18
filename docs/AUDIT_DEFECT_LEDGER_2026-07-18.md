---
document_type: evidence
decision_status: not-applicable
implementation_status: in-progress
normative_scope: current
last_verified: 2026-07-18
source_revision: fa7468b68ba60984ad7c416560dccb8f19a60aa7
owner: unassigned
reviewers: []
---

# Telysta 审计缺陷控制台账（2026-07-18）

## 1. 作用与权威边界

本文把[语言学与架构审计](./LINGUISTIC_AND_ARCHITECTURE_AUDIT_2026-07-18.md)中的 P0/P1 缺陷绑定到修正工作包、ADR、planning fixture、目标 Gate 和关闭证据。Planning fixture 只有在 reviewed subject merge、内容 hash/reviewer 登记和该 bundle 的 evidence protocol 完成后才成为 frozen/immutable 基线。本文不是 GateEvidence，不批准 ADR，也不把 planning-only fixture 描述为已实现能力。

当前状态：

- G0A = `blocked`；
- R0B evidence preparation = `in progress`，但具体工作包在 owner/reviewer/capacity 分配前仍为 `Planned`；G0B = `not evaluated`，当前尚无 G0B GateEvidence；
- R1 = `blocked by G0A`；
- WS-1 = `blocked by G1 + G0B`；
- [ADR-014](./adr/ADR-014-meaning-grammar-lexical-identity-realization-authority.md)已形成 `Proposed` 草案，但 owner/reviewer 未分配；
- fixture 合同只检查 planning 预期的结构与内部一致性，不代表预期已冻结或 Rust target 已实现。

责任缩写：

| 缩写 | 责任 | 当前值 |
|---|---|---|
| DO | Domain owner | `unassigned` |
| AR | Architecture reviewer | `unassigned` |
| LR | Linguistics reviewer | `unassigned` |
| MR | Migration reviewer | `unassigned` |
| DR | Data/research reviewer | `unassigned` |

缺少真实 owner、独立 reviewer、容量和 timebox 的包不得进入 `Ready`。本台账不会虚构这些值。

## 2. 状态定义

| 状态 | 含义 |
|---|---|
| Open | 已确认问题，尚未形成完整合同或 fixture |
| Contract drafted | Proposed ADR/合同已形成，仍待独立评审 |
| Fixture drafted + contract-tested | planning-only fixture 的 ID、输入与期望已有合同测试，但尚未 reviewed merge |
| Fixture frozen | fixture 已进入 reviewed subject、登记内容 hash 与 reviewer，并满足 bundle-specific evidence protocol；后续变化触发显式版本或 Gate 过期 |
| Partial | 只有部分合同/fixture，仍有未冻结验收 |
| Blocked by Gate | 证据准备可继续，但生产实现受 Gate 阻断 |
| Closed | Accepted 决定、目标实现、迁移/replay/科学证据与 reviewer attestation 全部就绪 |

“当前测试通过”不能直接把缺陷改为 Closed。

## 3. P0 缺陷

| ID | 问题 | 修正工作包 / ADR | 当前证据 | Target Gate | Owner / reviewer | 状态 |
|---|---|---|---|---|---|---|
| P0-01A | G0A 证据基线不能支持平台放行声明 | COR-00/01、R0A-05/06 | G0A handoff、GateEvidence v2、台账 | G0A | unassigned / AR+MR | Blocked by Gate |
| P0-01B | 累计证据不能支持“产品完成”声明 | R0B-03/04/06/07、WS-1、R3、R6 claim ladder | Capability/TaskPack/Product/Expert evidence 均尚未闭合 | claim-specific G0B → G2 → G3 → G6 | unassigned / AR+LR+DR | Open / cumulative |
| P0-02 | Lexeme/Sense/WordForm/Morpheme/Paradigm/Construction 无统一身份 | R0B-01A、COR-L01/03、ARC-21、ADR-014 | LEX-N01、MOR-N01/02、HOM-N01 | G0B + G2 | unassigned / AR+LR+MR | Contract drafted + Fixture drafted + contract-tested |
| P0-03 | 权威写入、事件和历史无法完整解释变化 | ADR-009/011/012、ARC-12/13/22/23 | EVT-N01、LEGACY-REPLAY-004..008 | G0A + G0B + G1 + G2 | unassigned / AR+MR | Partial / Blocked by Gate |
| P0-04 | 音系不变量不足，非法词形可成为结果 | COR-L02/08、ARC-22 | PH-N01..06、PH-P01 | G0B + G2 | unassigned / LR+AR | Fixture drafted + contract-tested / Blocked by Gate |
| P0-05 | Meaning → sentence 不保持意义 | COR-L04/05/07、ADR-014 | SEM-N01/02、VAL-N01/02、QRY-N01 | G0B + G2 | unassigned / LR | Contract drafted + Fixture drafted + contract-tested |
| P0-06 | 经验数据被误作机制或事实 | COR-L05A、R0B-05/07 | DATA-N01、理论/数据责任矩阵 | G0B + G4 | unassigned / DR+LR | Partial |
| P0-07 | 类推、语法化、同音处理作用于错误对象 | ADR-014、COR-L03、WS2 | EVT-N01、GRA-N01、ANA-N01、HOM-N01/02 | G0B + G4 | unassigned / LR+DR | Fixture drafted + contract-tested / mechanism deferred |
| P0-08 | 确定性与 provenance 仍有旁路 | ADR-013、ARC-11/14/21 | DET-N01、LEGACY-REPLAY-004..008 | G0A + G1 + G2 | unassigned / AR+MR | Partial / Blocked by Gate |
| P0-09 | Genesis 信任边界未封印 | ADR-010、ARC-24/25 | CAP-N01；Genesis tamper matrix 尚待 WS1 fixture | G0B + G2 | unassigned / AR+LR | Contract drafted / Partial |
| P0-10 | 环境、气候或奇幻族群被写成直接因果 | COR-L05A、R0B-07、WS2 TheoryProfile | DATA-N01；causal-basis probe 尚待模型合同 | G0B + G4 | unassigned / DR+LR | Partial |
| P0-11 | realization/analysis/query 会修改语言状态 | ADR-014、COR-L04、ARC-10 | QRY-N01 | G0B + G1 + G2 | unassigned / AR+LR | Contract drafted + Fixture drafted + contract-tested |
| P0-12 | “音变”把不同机制压成逐词彩票 | COR-L02、ARC-22、WS2 | PH-N05、HOM-N02、EVT-N01 | G2 + G4 | unassigned / LR+DR | Fixture drafted + contract-tested / mechanism deferred |

## 4. P1 缺陷

| ID | 问题 | 修正工作包 | 当前证据 | Target Gate | Owner / reviewer | 状态 |
|---|---|---|---|---|---|---|
| P1-01 | 音段特征与音系层级过薄 | COR-L02、ARC-21 | PH-N01..06、PH-P01 | G0B + G2 | unassigned / LR | Fixture drafted + contract-tested |
| P1-02 | 历时与共时规则混用 | COR-L02、ARC-22、WS2 | EVT-N01、PH-N05 | G2 + G4 | unassigned / LR | Partial |
| P1-03 | 形态类型被单轴化 | COR-L03/06 | Profile A/B、MOR-N01/02 | G0B + G2 | unassigned / LR | Fixture drafted + contract-tested |
| P1-04 | 词类完整性判断英语中心 | COR-L03/06、ADR-014 | CAT-N01 | G0B + G2 | unassigned / LR | Contract drafted + Fixture drafted + contract-tested |
| P1-05 | 词汇生成退化为一概念一随机词 | COR-L03/04、R3 lexical family | LEX-N01、DATA-N01 | G2 + G3 | unassigned / LR | Partial |
| P1-06 | 语义关系无类型或方向不清 | COR-L04、ADR-014 | SEM-N01 | G0B + G2 | unassigned / LR | Contract drafted + Fixture drafted + contract-tested |
| P1-07 | 配价与对齐模型过窄 | COR-L05 | VAL-N01/02 | G0B + G2 | unassigned / LR | Fixture drafted + contract-tested |
| P1-08 | 形态实现不可逆 | COR-L03/04 | MOR-N01/02 | G0B + G2 | unassigned / LR | Fixture drafted + contract-tested |
| P1-09 | 生成查询有副作用 | COR-L04、ARC-10 | QRY-N01 | G1 + G2 | unassigned / AR+LR | Fixture drafted + contract-tested / Blocked by Gate |
| P1-10 | 社会变化与传播缺位 | WS2 | GRA-N01、ANA-N01、HOM-N02 | G4 | unassigned / LR+DR | Deferred |
| P1-11 | flat/epoch/branch 管线不等价 | ARC-10/22/23 | DET-N01、QRY-N01、legacy replay bundle | G1 + G2 | unassigned / AR+MR | Partial |
| P1-12 | Rust application/client 边界未落地 | ARC-10 | dependency-direction 与 IPC fixture 尚待 R1 | G1 | unassigned / AR | Blocked by G0A |
| P1-13 | authoritative input schema 过宽 | ARC-11/21 | CAP-N01、LEGACY-REPLAY-004 | G1 + G2 | unassigned / AR+MR | Partial |
| P1-14 | evaluator 验证实现而非语言能力 | COR-L07、R0B-04/07 | 24-case bundle；sealed TaskPack 尚待冻结 | G0B + G2 | unassigned / LR+DR | Partial |
| P1-15 | provenance 覆盖不完整 | ARC-21/22/23 | MOR-N02、LEGACY-REPLAY-005..008 | G2 | unassigned / AR+MR | Partial |
| P1-16 | DataReference 只证明标签存在 | COR-L05A、R0B-05 | DATA-N01 | G0B | unassigned / DR+AR | Fixture drafted + contract-tested / payload slice pending |
| P1-17 | Tauri API 仍是 spike 边界 | ARC-10/11/14、COR-L09 | QRY-N01、CAP-N01；IPC fixture 待 R1 | G1 + G2 | unassigned / AR | Blocked by G0A |
| P1-18 | SoundChange IR 无法表达核心历时过程 | COR-L02、ARC-22、WS2 | PH-N05、EVT-N01 | G2 + G4 | unassigned / LR+AR | Partial |

## 5. 已起草并通过结构合同测试的 planning fixture

以下文件当前仍属于未合并的 planning evidence。合同测试能够检查封闭字段、ID、typed 表示和
source wire/envelope hash，但不能阻止 fixture 与测试在同一个脏工作树中被同时改写；
因此在 reviewed subject merge、内容 hash、reviewer 和 bundle-specific evidence
requirements 完成前，状态不是 `Fixture frozen`。

### 5.1 Linguistic regression

- 路径：`tests/fixtures/linguistic_regression_cases_v1.json`
- schema：`telysta-linguistic-regression-cases.v1`
- 状态：`planning_only_not_a_production_persistence_format`
- case 数：24
- runner 状态：`future_not_bound`；当前未执行语言学 target；
- case 同时记录 assumption class、contract kind、claim scope 和
  single-fault/batch/evidence-bundle/metamorphic mode；真实绑定前仍须提供 versioned
  adapter schema、合法 baseline 和 runner-generated diagnostics；
- DET-N01 的重复十六进制 locks 明确标为 fixture sentinel；在真实 Registry/Data/Rule/
  Meaning/Grammar/EntityId/Theory/compiler payload hash 绑定前不得作为确定性证据；
- ID：
  - phonology：PH-N01..06、PH-P01；
  - capability/category/identity：CAP-N01、CAT-N01、LEX-N01；
  - homophony/morphology：HOM-N01/02、MOR-N01/02；
  - meaning/valency：SEM-N01/02、VAL-N01/02；
  - purity/determinism/data/event：QRY-N01、DET-N01、DATA-N01、EVT-N01；
  - delayed mechanism：GRA-N01、ANA-N01。

### 5.2 Legacy replay migration

- 路径：`tests/fixtures/legacy_replay_migration_cases_v1.json`
- schema：`telysta-legacy-replay-migration-cases.v1`
- 状态：`legacy_reference_not_a_production_persistence_format`
- case 数：8（LEGACY-REPLAY-001..008）
- LEGACY-REPLAY-001..007 是当前 source test contract 的 synthetic minimal producer-wire vector；004 的固定 timestamp 也是 fixture 输入，不是历史源测试真实输出；008 只是 absence claim，尚无封闭运行目录证明。
- planning integrity 使用 LF-normalized producer-wire SHA-256 与 Python-bound canonical source-envelope SHA-256；它们不是跨语言 semantic hash，也不是原始归档 hash。
- 旧 writer 的原始文件使用平台原生换行；合同测试调用真实 `KeyframeManager` 验证 synthetic keyframe/event batch，并验证 `DeltaEvent.to_dict()`。正式迁移 Gate 前仍须保存未归一化原始字节、原始 SHA-256、source revision、命令、环境、seed/clock 和完整目录 manifest。
- 所有成功导入只允许产生唯一 `LegacyHistoryBoundary` + `ImportedCheckpoint` payload；旧 event 不得被提升为 v3 ChangeSet。Rust target 路径当前明确标为 `planned_not_implemented`。

### 5.3 Executable contract

- 路径：`tests/core/test_audit_correction_fixture_contract.py`
- 当前只验证 planning fixture 的封闭性、ID、typed representation、关键语义、synthetic producer wire/envelope integrity、当前 legacy writer 格式和退役链；
- 不创建 production loader，不修改 Python legacy 行为，不退役 strict-xfail。

## 6. 缺陷关闭规则

任一条目改为 Closed 前必须同时具备：

1. 对应 ADR/合同已由具名独立 reviewer 接受；
2. Rust target contract、unit/property/replay/migration/hostile 测试按风险通过；
3. fixture 由 Rust 目标测试消费，不能复制第二份期望；
4. semantic hash、migration loss 和 provenance 影响已记录；
5. Capability Matrix、UI 文案和允许产品声明同步；
6. GateEvidence 显示对应 Gate 通过；
7. legacy 缺陷遵循 `strict xfail → Rust target → migration matrix/loss report → reviewer → retirement`；
8. 关闭证据包含提交、测试、reviewer attestation 和剩余限制。

禁止用下列方式关闭：

- 只修示例输出或字符串；
- 把 hard error 降为 warning；
- 添加猜测默认值；
- 将 strict xfail 改为 broad skip；
- 由 generator 自己的评分证明自然性；
- 由本台账文字代替 GateEvidence。

## 7. 执行记录

### 2026-07-18 / Wave 0–1 preparation

- `scripts/g0a_handoff.py --check --json`：退出码 `0`，基线为 commit `fa7468b68ba60984ad7c416560dccb8f19a60aa7` / tree `27e410f2da95ecc68481f1a261c48fe632c96d1d`；
- live 工作树分类：143 条原始记录、141 条 subject candidate、2 条 attestation-only、0 条 transient、0 条 manual-review、0 条 missing-review-target；
- handoff 只达到 `subjectReadyForStagingReview=true`；`cleanSubjectReadyForVerification=false`、`independentApprovalRecorded=false`；
- `scripts/g0a_handoff.py --check --require-clean-subject --json`：退出码 `1`，因此 G0A 继续为 `blocked`；
- live fingerprint 不写入本 subject 文件，避免台账修改自身造成自引用漂移；应在形成只读 subject commit 后由 GateEvidence 记录；
- ADR-014：Proposed 草案已创建；
- linguistic regression fixture：已创建；
- legacy replay migration fixture：已创建；
- fixture contract tests：已创建；本轮定向运行
  `.\.venv\Scripts\python.exe -m pytest tests\core\test_audit_correction_fixture_contract.py -q`
  得到 `8 passed`。这是当前 fingerprint 上的 targeted local check，不是 Gate 放行证据；
- `.\.venv\Scripts\python.exe -m pytest tests\storage\test_history_replay_features.py -q -rxX`
  在当前工作树得到 `3 passed, 8 xfailed`，与 declared strict-xfail 对应；该本地运行
  尚未绑定 reviewed subject commit、run ID 或原始目录 archive，因此不作为 migration
  execution evidence；
- 真实 owner/reviewer/capacity/timebox：仍未分配；
- R1/v3/Genesis 生产实现：未启动。
