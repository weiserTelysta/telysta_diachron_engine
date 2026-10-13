---
document_type: roadmap
decision_status: not-applicable
implementation_status: in-progress
normative_scope: current
last_verified: 2026-10-12
owner: unassigned
reviewers: []
---

# Telysta Diachron Engine 项目路线图

- 状态：`Active planning baseline / pending reviewed subject`
- 基线日期：2026-07-12
- 最近路线修订：2026-10-12
- 适用范围：引擎、桌面客户端、规则系统、项目存储与质量体系
- 维护方式：每个阶段结束时更新状态和证据，不以功能数量代替完成度

## 1. 产品目标

Telysta Diachron Engine 的目标不是一次性随机生成词表，而是成为面向世界观创作者的本地优先语言历史工作台。用户应当能够：

- 创建祖语并配置音系、类型学、文化环境和演化倾向；
- 推进纪元，观察词汇、音系、形态、句法与语义的历时变化；
- 在任意时代建立分支语言，并保持可追溯的共同祖先；
- 编辑、验证和试运行规则包；
- 追踪每个现代形式的来源、规则和历史事件；
- 比较时代、分支和规则方案；
- 将项目保存为可迁移、可升级、可审计的本地文件。
- 从零开始创建语言，或把小说中已有的姓名、词语与台词作为 canon 锚点补全语言；
- 用真实场景验证表达、分析、IGT、发音与历史解释，并在不能表达时明确返回缺口；
- 锁定已发表文本，规则与历史变更必须先显示对 canon 的影响。

首要 0.5 用户是已经拥有姓名、称号、词语或短场景，希望把零散 canon 扩充为一门可实际使用且可审计语言的严肃世界观作者。构造语言爱好者是 Expert 工作流用户；专业语言学家首先作为评审者、研究模式用户和高级规则作者。首个核心结果是一个可审计、可持续扩充的单语言 Story Language Kit；两个历史分支、接触和重建属于后续 Language Family Forge，不是首发价值证明。

完整目标架构、模块工作包、依赖关系和跨阶段质量门见[专业语言模拟器实施总计划](./LANGUAGE_SIMULATOR_PLAN.md)；当前关键路径、详细 WBS、Stop/Go 与执行队列见[产品开发执行计划](./PRODUCT_DEVELOPMENT_PLAN.md)。

2026-10-12 用户范围补充：R2 随语言导出可阅读说明，STORY-10 验证后在 R3
形成性构建提供受限本地读音；正式视觉采用 Rosé Pine。详细依赖与验收统一见
[执行计划第 1.3 节](./PRODUCT_DEVELOPMENT_PLAN.md#13-2026-10-12-用户目标落实与路线复审)。

R0B 当前已有可离线复现的真实 Concepticon 研究切片和 Meaning scope/commitment
评审向量；执行状态与下一轮统一见 [WORK_LOG](./WORK_LOG.md)。它们不表示
生产语言生成、数据 adapter 或 G0B 已完成。

## 2. 当前核心判断

Python 研究原型保留以下已登记缺陷；Rust 当前能力见[当前架构](./architecture/CURRENT.md)。
这些历史缺陷不代表同名 Rust 实现必然存在相同问题：

1. 历史重建目前不能完整恢复 DAG、类型学和保护集合。
2. 注词、复合、替换与部分类型学变化没有进入统一事件链。
3. 运行共享全局配置和固定快照目录，无法保证并发与多项目隔离。
4. Flat、Epoch 和 Branch 存在不同的演化实现，行为会逐渐分叉。
5. 一些模块只有独立实现和测试，没有进入主流程。
6. 规则缺少统一规范、版本、冲突分析和质量准入机制。

因此，在基础一致性完成前，不把“新增更多规则”或“完整桌面 UI”作为首要目标。

## 3. 架构原则

唯一生产权威、确定性、回放和本地优先约束见 [AGENTS.md](../AGENTS.md)与
[ADR-006](./adr/ADR-006-rust-native-core-python-research-bridge.md)。

### 3.1 单一事实来源

遵循上述合同；此处不重复维护架构正文。

### 3.2 可复现

遵循上述合同；此处不重复维护架构正文。

### 3.3 可回放

遵循上述合同；此处不重复维护架构正文。

### 3.4 本地优先

遵循上述合同；此处不重复维护架构正文。

### 3.5 Rust 生产核心与 Python 研究桥接

遵循上述合同；此处不重复维护架构正文。

## 4. 目标架构

实际实现见[当前架构](./architecture/CURRENT.md)，目标依赖与作者流程见
[目标架构](./architecture/TARGET.md)，安全切换见[迁移地图](./architecture/MIGRATION.md)。

## 5. 分阶段路线

### 5.0 交付策略：能力地图之外，按端到端里程碑执行

下列 Phase A–H 保留为长期能力地图；实际提交和 stop/go 顺序由 R0A/R0B–R7 交付里程碑约束。里程碑优先于按领域横向铺开，任何领域深化都必须回到同一条可运行产品纵切：

| 里程碑 | 必须证明的结果 | 主要映射阶段 |
|---|---|---|
| R0A 计划/平台合同修复 | 首发 wedge、ADR 拓扑、Project/Run/Job、Gate 证据和 clean baseline | A–B–F |
| R0B WS-1 领域证据 | Grammar/Meaning、Canon/TaskPack、execution manifest/runner contract、evaluator、模型/数据证据与 Meaning Workbench | C–F–G |
| R1 平台收口 | application service、Project/Operation/Run ledger shell、JobStore/journal、版本化 API/query、staging、取消/恢复和存储基准 | A–B–F |
| R2 / WS-1 可执行微型语言 | Blueprint → 多候选 Genesis → 最小双向语法/任务 → Orthography/IGT round trip → ChangeSet → history/seal/create/reopen → replay/explain | B–C–F–G |
| R3 Story Language Kit | Canon-first、Onomasticon、生产性构词、Scene Lab、Canon impact、RulePack v1 | C–E–F–G |
| R3B WS-2 模型就绪 | SpeechCommunity/Variation/Process ADR、ExperimentRunner、参数辨识与 storage Go/No-Go | D–G |
| R4 / WS-2 Mechanistic Change v1 | innovation、competing variants、typed usage observation、传播失败、常规化、替代模型与消融 | D–G |
| R5 Language Family Forge | 分支、dialect linkage、迁徙、接触、借词适应、规律对应和重建 | D–E–F |
| R6 Production Conlang | R3 后并行单语言篇章/文学轨；R5 后集成历史、审计与 Language Bible | F–G–H |
| R7 Core Release + Optional Trains | core 安装迁移/恢复；Speech、LLM、Extension 分列发布 | H |

WS-1 不等待所有领域模型完成。其主轮廓固定为一个小型音系与韵律系统、一个名词范式、一个动词范式、三类核心构式、30–50 个锁定概念、3–5 个候选、最小 CanonSeed、一套规则化 Orthography v0 和一条 typed sound change；另有一个结构非同构的紧凑对照 fixture，防止 IR 被单一类型锁死。它必须包含 Meaning Workbench、四类 TaskPack、Linguistic Execution Manifest、双向语义与拼写 probes、由同一分析图投影的 IGT、独立 evaluator、Tauri 创建/查看和 typed `ExpressionGap`。R2 的 canon impact 仅为 CanonSeed compatibility preview，不创建 AuthorCanonCorpus/CanonRelease；这一阶段只证明“可执行语言与可审计结构变换”，不得宣称产品易用或真实传播。

执行门不可跳级：G0A 关闭后允许 R1 平台 walking skeleton 与 R0B 并行；只有 G1 与 G0B 同时关闭后才进入 WS-1 权威 schema 和生产纵切。G3 与 G3B 同时关闭后才进入 WS-2。fixture、反例与不写正式状态的测试材料可提前准备。

Story Language Kit 必须先于 WS-2：它提供可执行 Grammar、真实作者任务和 scenario templates，但 AuthorCanonCorpus 不自动成为人口频率。WS-2 只能在锁定 TheoryProfile、抽样单位和 observation model 后产生 `SyntheticUsageObservation`，或使用明确许可/抽样的 external empirical observation。通过新旧变体共存、成功/失败/稳定变体对照、参数恢复和常规化后，产品才可称 Mechanistic Change Simulator v1。

数据治理、科学验证、产品任务验证、性能预算和旧路径清理贯穿每个里程碑，不允许推迟到最终发布阶段。正式 schema 仍必须遵守 ADR stop condition：子 ADR 未接受时只能制作 fixture、原型和评审材料，不能改变持久化语义。

### Phase A：产品化基线

建立 clean-checkout、确定性基线、黄金场景与可信验证证据；当前受 G0A 阻断。

### Phase B：Rust 地基与架构验证

复用现有 Rust 地基，经 G0A 后建设 R1 应用/任务外壳；v3 与 Genesis 等待 G1 + G0B。

### Phase C：可审计祖语编译器

R2 编译、生成、分析、保存一门微型语言，导出说明并解释一次结构变化。

### Phase D：语言家族与真实演化

R4 验证创新、变体与传播机制，R5 再交付分支、接触及重建；不得提前声明真实传播。

### Phase E：声明式规则平台

R3 提供声明式作者规则的校验、dry-run 和 canon impact；R4 另行绑定过程模型。

### Phase F：Tauri 创作者工作台

R0B 先验证作者流程；R3 集成 Rosé Pine 工作台、场景、检查与导出。

### Phase G：语法、文学能力与 Quality Lab

R3 证明命名/对白/短场景可持续扩充；R6 验证高级篇章、文学任务与完整语言手册。

### Phase H：创作、翻译、发音与发布

基础说明从 R2 开始，STORY-10 后的受限读音在 R3 形成性构建先行；R7 完成发布加固及可选语音。

### 发布切片

| 发布 | 可验证结果 | 对应阶段 |
|---|---|---|
| 0.2 Deterministic Baseline | 旧引擎黄金场景、分域哈希和已知缺陷报告 | A |
| 0.3 Platform Baseline | G0A/G1、application/JobStore、版本化 API/query、取消/恢复与存储基准 | A–B–F |
| 0.4 Executable Language Preview | WS-1 多候选 Genesis、双向语法、Orthography/IGT、结构 ChangeSet、explain 与同版本最小语言说明；不得称 Alpha/canon-safe | B–C–F–G |
| 0.5 Canon-first Alpha | AuthorCanonCorpus、命名、Scene Lab、生产性构词、Canon impact、release/export、基础试听/WAV 与创作者验证 | C–E–F–G |
| 0.6 Mechanistic Change Simulator v1 | WS-2 变体、传播失败/成功/稳定、参数恢复、常规化与消融 | D–G |
| 0.7 Language Family Forge | 两分支、接触、借词适应、规律对应和重建挑战 | D–E–F |
| 0.8 Production Conlang Beta | 多语体、复杂场景、文学任务、Quality Lab 和专家审计 | F–G–H |
| 1.0 Core Authoring Release | Canon-safe 创作、完整历史、IGT、Language Bible、安装迁移和恢复；不依赖 neural voice/LLM/plugin | F–H |

## 6. 下一步工作包

当前从 R0A 平台/仓库决策与 R0B 领域/产品证据并行继续；后续实现严格按下列 Next/Blocked 状态推进：

### A-001：开发环境与 CI ⚠ Reopened by 2026-07-19 review

完成日期：2026-07-12

完成证据：

- 支持 Python 3.10–3.14，默认开发版本为 3.13；
- 使用 Poetry 2.4.1 application mode 和完整 `poetry.lock`；
- `scripts/check.py` 统一运行编译、Ruff 正确性检查和 pytest；
- 本地基线为 474 项测试全部通过；
- CI 验证 Linux 3.10/3.12/3.14 与 Windows 3.13；
- Windows、macOS 和 Linux 安装流程记录于 `docs/DEVELOPMENT_SETUP.md`。

复审修正：原完成记录保留为历史，但不再作为当前关闭证据。pytest 可在
`--collect-only` 下零执行成功；Gate 失败可能保留旧 passed；声明的 Rust 1.77.2
与 lock graph/实际 1.96 evidence 不一致，Linux desktop job 也未证明 Tauri 原生依赖。
COR-05 已在当前工作树完成 hermetic runner 与 fail-closed evidence 的本地实现检查点：
33 项定向测试通过并证明 `collected=33, executed=33`，hostile addopts 下的最终完整门
实际执行 588 项，结果为 `580 passed, 8 xfailed`。但这不是通过性 GateEvidence；独立
复核、clean subject 与受信远端 provenance 仍未完成。单 verifier lease 及锁竞争负例
已经形成后续本地实现候选。COR-07 已将 locked graph、workspace、toolchain、generator 与 CI 的
候选 MSRV 统一到 1.88.0，Windows exact gate 本地通过；Linux/fresh-checkout CI 与
provenance 仍待远端。当前关闭包仍为
`R0A-08 Verification Trust Repair`，状态保持 `In progress`。

### A-002：黄金场景与状态哈希 ✅

历史实现与限制见[当前架构](./architecture/CURRENT.md)、
[模块迁移矩阵](./MODULE_MIGRATION_MATRIX.md)及对应合同；此标题不代表当前 Gate 已通过。

### A-003：历史回放特征测试 ✅

历史实现与限制见[当前架构](./architecture/CURRENT.md)、
[模块迁移矩阵](./MODULE_MIGRATION_MATRIX.md)及对应合同；此标题不代表当前 Gate 已通过。

### A-004：模块清单 ✅

历史实现与限制见[当前架构](./architecture/CURRENT.md)、
[模块迁移矩阵](./MODULE_MIGRATION_MATRIX.md)及对应合同；此标题不代表当前 Gate 已通过。

### A-005：Rust Core Shell Spike ✅

历史实现与限制见[当前架构](./architecture/CURRENT.md)、
[模块迁移矩阵](./MODULE_MIGRATION_MATRIX.md)及对应合同；此标题不代表当前 Gate 已通过。

### B-001：Foundation Model ✅

历史实现与限制见[当前架构](./architecture/CURRENT.md)、
[模块迁移矩阵](./MODULE_MIGRATION_MATRIX.md)及对应合同；此标题不代表当前 Gate 已通过。

### B-001.1：Foundation Repair ✅

历史实现与限制见[当前架构](./architecture/CURRENT.md)、
[模块迁移矩阵](./MODULE_MIGRATION_MATRIX.md)及对应合同；此标题不代表当前 Gate 已通过。

### B-002：Canonical LanguageState Schema ✅

历史实现与限制见[当前架构](./architecture/CURRENT.md)、
[模块迁移矩阵](./MODULE_MIGRATION_MATRIX.md)及对应合同；此标题不代表当前 Gate 已通过。

### DAT-001：最小数据治理与 Manifest ✅

历史实现与限制见[当前架构](./architecture/CURRENT.md)、
[模块迁移矩阵](./MODULE_MIGRATION_MATRIX.md)及对应合同；此标题不代表当前 Gate 已通过。

### B-003：确定性合同 ✅

历史实现与限制见[当前架构](./architecture/CURRENT.md)、
[模块迁移矩阵](./MODULE_MIGRATION_MATRIX.md)及对应合同；此标题不代表当前 Gate 已通过。

### B-004：项目运行与事务合同 ✅

历史实现与限制见[当前架构](./architecture/CURRENT.md)、
[模块迁移矩阵](./MODULE_MIGRATION_MATRIX.md)及对应合同；此标题不代表当前 Gate 已通过。

### B-005：时间模型精确绑定与 provenance 时间完整性 ✅

历史实现与限制见[当前架构](./architecture/CURRENT.md)、
[模块迁移矩阵](./MODULE_MIGRATION_MATRIX.md)及对应合同；此标题不代表当前 Gate 已通过。

### FND-008：原子项目存储与迁移 ✅

历史实现与限制见[当前架构](./architecture/CURRENT.md)、
[模块迁移矩阵](./MODULE_MIGRATION_MATRIX.md)及对应合同；此标题不代表当前 Gate 已通过。

### FND-008.1：存储完整性与并发收口 ⚠ Reopened by 2026-07-19 review

存储完整性已重开，修复归属 R0A-09；以[存储合同](./PROJECT_STORAGE_V1.md)、
[审计台账](./AUDIT_DEFECT_LEDGER_2026-07-18.md)和实际故障测试验收。

### PLT-002：桌面项目持久化契约 ← Paused；剩余范围归入 R1

等待对应 Gate；启动条件见[执行计划](./PRODUCT_DEVELOPMENT_PLAN.md#22-当前执行队列)。

### GEN-001：LanguageBlueprint v1 ← Superseded

历史实现与限制见[当前架构](./architecture/CURRENT.md)、
[模块迁移矩阵](./MODULE_MIGRATION_MATRIX.md)及对应合同；此标题不代表当前 Gate 已通过。

### GEN-001.1：LanguageBlueprint 合同修复 ← Completed

历史实现与限制见[当前架构](./architecture/CURRENT.md)、
[模块迁移矩阵](./MODULE_MIGRATION_MATRIX.md)及对应合同；此标题不代表当前 Gate 已通过。

### R0A-EXEC：平台决策与仓库基线 ← Next

- 冻结首发 Story Language Kit wedge、1.0 范围、非目标和允许声明；
- 修复 ADR 依赖图，并先接受 ProjectManifest/RunLedger/Operation/Job、RNG、application/staging/query/dependency bundle 与 storage authority 中影响持久化/回放的决定；R0A-03 [平台合同包](./PLATFORM_CONTRACT_PACK_V1.md)、[ADR-012](./adr/ADR-012-project-package-commit-authority.md) 与 R0A-04 [ADR-013](./adr/ADR-013-rng-compatibility-and-distribution-versioning.md) 的评审材料及 RNG known-answer 已就绪，但仍为 Proposed；
- ADR-011 的 schema 草案、四条序列 fixture、负例、责任矩阵和迁移自审已经就绪；当前等待具名 code owner、独立架构 reviewer 与 migration reviewer 批准，仍不得实施持久化身份；
- 已将 [G0A GateEvidence](./G0A_GATE_EVIDENCE_2026-07-17.json) 强制迁移为 v3 候选；当前决策为 `blocked`；ADR-011/012/013 独立批准、clean-checkout、具名 owner/reviewer、完整 DeliveryReadiness、Windows/Linux provenance 与 R0A-05/07/08/09/10 terminal evidence 仍未完成；
- 已提供 [G0A 独立评审与 Clean Baseline 交接](./governance/G0A_REVIEW_AND_BASELINE_HANDOFF.md)和可执行 worktree 清单；它冻结待审对象哈希、区分 subject/attestation，并拦截瞬态产物与危险文件操作，但不替代人工批准或 Git 提交；
- 继续补齐 owner/reviewer、容量、估算、WIP 与 timebox；
- Proposed G0A policy v2 已精确要求 `R0A-01`、`R0A-02-ADR011`、`R0A-03`、`R0A-04`、`R0A-05`、`R0A-06`、`R0A-07`、`R0A-08`、`R0A-09`、`R0A-10`，并机器验证 R0A-07 的完整 DeliveryReadiness；旧 policy 下的 passed 不满足当前启动门，v2 仍待独立接受；
- COR-05 已完成 hermetic test runner、fail-closed GateEvidence、单 verifier lease 与
  锁竞争恶意负例的本地实现检查点，但仍待独立复核、clean subject 和受信远端复验；
  GateEvidence 为权威源，STATUS 发生输出撕裂时必须被重写或删除后重建；
- COR-07 已完成 1.88.0 MSRV 与 Windows gate 的本地实现候选；继续取得 Linux/
  fresh-checkout CI 和受信 provenance。旧 software pass 不再证明 MSRV；
- 完成 `R0A-09`：在不改变 v1 schema/hash/replay 的范围内修复
  create-if-absent、append-only history、archive/journal 复验和 index as-of binding；
- 完成 `R0A-10`：冻结 raw legacy replay/非法 golden/RNG 与 query-mutation 证据，
  将 Python CLI/Streamlit 明确隔离为 Legacy Lab；
- 审查并纳入当前 Rust/Tauri/CI/合同/fixture，形成 clean-checkout 证据；
- 关闭 G0A 后，R1 平台 walking skeleton 可与 R0B 并行。

### R0B-EVIDENCE：WS-1 领域与产品证据 ← Parallel Next

- 当前 R0B evidence preparation 为 `in progress`，具体工作包在 owner/reviewer/capacity 分配前仍为 `Planned`；G0B=`not evaluated` 且没有通过性 GateEvidence；
- 按 `ADR-008 → ADR-014 → ADR-009 → ADR-010 → ADR-007 umbrella` 接受领域决定，或在对应节点接受 ADR Index 所定义的显式 replacement ADR，冻结 Meaning/Grammar/Lexical Class/Realization/Task/Canon/evaluator 的边界；ADR-014/replacement 必须补齐稳定 `OrthographicForm/SpellingRealization` 身份键、owner、semantic hash、migration/replay、保守拼写与独立拼写改革语义；其内部顺序固定为 `R0B-01A-D ADR draft → R0B-04B-D review vectors → R0B-01A Accepted → R0B-04B frozen pack`，避免 ADR 与 fixture 循环；ADR-009 的跨 Gate 前置是 ADR-011，ADR-010 的跨 Gate 前置是 ADR-011/012/013；
- 冻结主 profile、结构非同构对照、Capability Matrix、四类 evaluator pack、CorpusRole、Orthography/IGT/PCU hostile fixtures、数据 execution slice，以及不自称通过结果的 Linguistic Execution Manifest/adapter contract；拼写 round trip 以 typed WordForm/analysis occurrence + OrthographyRevision（或 ADR 接受的等价 identity）为键，不以裸音系串为键；G0B 只验 contract/harness/registry 与当下可执行命令，G-LANG/G-CHANGE 的真实 Rust adapter 在 G2 才成为硬门；
- 先执行无领域 schema 依赖的 `R0B-06P`，制作 `FormativeJourney.r0b` 的 `Brief → Meaning Workbench → Candidate Audition → Scene/History Preview → Export` 低保真原型，并用目标作者真实 canon 验证；原型不得写正式状态；待 R0B-01/02 完成后，再由 R0B-06 把发现编译为正式产品 evidence contract；
- 固定 Genesis TheoryProfile、ODD/TRACE、ModelEvidence 与 parameter recovery/identifiability 模板；
- 关闭 G0B 后仍须等待 G1，二者共同放行 WS-1。

详细顺序、工作包和 Stop/Go 见[产品开发执行计划](./PRODUCT_DEVELOPMENT_PLAN.md)；2026-07-18 审计问题到现有 WBS/Gate 的修正映射见[审计修正执行计划](./AUDIT_CORRECTION_PLAN_2026-07-18.md)。其中已纠正“领域历史先于 v3/ChangeSet”的倒置依赖。G0A 关闭前，平台侧只允许合同、fixture 与不写正式状态的准备；G0A 关闭后可实现 R1 fake-operation 平台纵切。G0B 关闭前，领域侧仍只允许文档、fixture、数据锁、低保真原型和不写正式语言状态的研究实验。

### GEN-001.2：Domain Model Hardening ← Blocked by G1 + G0B

- 将下一持久化领域模型明确为 `telysta-language-state.v3`，不与现有 v2 时间迁移版本混淆；
- Blueprint、LanguageState、Genesis 编译器和 UI 共用 ADR-008 的 RegistryBundle/typed FeatureValue 合同；
- 在 Orthography authority ADR Accepted 后，补齐音段特征、异音与分布、音系配列/韵律、形态形式/异形/范式、typed constructions、语义角色、Orthography v0 与同图 IGT projection；音变不得静默重写拼写；
- 用 ADR-009 的原子 ChangeSet 取代生产历史中的完整状态替换，并定义 deterministic reducer；
- 引入 ADR-010 的 `GenesisArtifact` capability，锁定 Blueprint、Registry、数据、规则、RNG、能力和质量报告；
- 以 [ADR-007](./adr/ADR-007-language-state-v3-change-event-ir.md) 为 umbrella 做一致性评审，并按 [ADR-008](./adr/ADR-008-registry-bundle-domain-registries.md) → [ADR-014](./adr/ADR-014-meaning-grammar-lexical-identity-realization-authority.md) → [ADR-009](./adr/ADR-009-atomic-change-set-and-usage-observations.md) → [ADR-010](./adr/ADR-010-genesis-artifact-trust-boundary.md) → ADR-007 最终接受的依赖顺序收口；全部 Accepted 后才按 WS-1 最小端到端纵切修改 Rust schema 与迁移。

完成标准：v2 fixture 与迁移基线冻结；ADR-007～010、ADR-014 或 ADR Index 所定义的 Accepted replacement ADR，以及所有影响持久化/回放的依赖决定均已接受；WS-1 v3 能表达最小祖语、双向核心语法和一个 typed structural change；项目创建无法绕过 compiler capability、independent evaluator 和 Genesis hard-error gate；Tauri 能创建、重开、生成/分析文本并解释该纵切；专家阶段评审没有阻断性表达缺口。

### GEN-002：SpeechCommunity v1 ← Queued for WS-2 after Story Language Kit

- WS-2 v1 定义单一社区的人口、cohort/network、声望、语域、识字、标准化、L1/L2 与 lect 关联；迁徙、多社区和接触扩展留给 R5；
- 社群参数只能影响传播、采用和交际需求，不能直接覆盖音系或类型学 feature；
- 与 Blueprint、OperationContext 和未来 ChangeProcess 使用同一证据与 basis-points 合同。

### EVO-009：PopulationVariationState v1 ← Queued after GEN-002 in WS-2

- 以 `(community, lect)` 表达新旧变体、条件分布、过程阶段、残留与失败结果；
- UsageObservation 使用不可变语料锁，频率和统计不成为第二权威状态；
- 只有常规化后的 ValidatedChangeSet 才能修改 LanguageStructureState。

### GEN/EVO/FAM-001：祖语—分支—接触纵切 ← Split by WS-1 / WS-2 / Family

- WS-1 只完成 Blueprint、Genesis、双向 Grammar、一个 structural ChangeSet 与 replay/explain；
- WS-2 完成 innovation、competing variants、成功/失败传播、常规化与结构提交；
- Family 阶段再加入两个分支、一次 contact layer、借词适应、规律对应与重建；
- 各阶段以结构化状态、TaskPack、规则/过程解释和反例验证，禁止沿用旧逐词随机流程。

## 7. 暂不执行

在 G1 + G0B 和 WS-1 前置决定完成前，继续停止：

- LanguageState v3 持久化语义、正式 ChangeSet/reducer 和项目创建入口；
- SpeechCommunity、PopulationVariation 和家族/接触正式 schema；
- 大规模增加音变和语法化规则；
- 全量外部数据导入；
- 正式 UI 视觉精修；
- TTS、LLM 自动写状态和任意代码插件；
- 删除 Python legacy 模块；
- 把全部 Python 代码逐行翻译为 Rust；
- 搬运所有 Streamlit 页面；
- 增加云同步或多人协作；
- 承诺移动端支持；
- 根据主观判断批量删除实验模块。

这不限制领域级大规模重构；当黄金场景、目标 schema、迁移方案和验收门齐备时，可以整体替换旧领域实现。

## 8. 路线图更新规则

每个工作包完成时必须记录：

- 对应提交或 PR；
- 新增或更新的测试；
- 数据格式是否变化；
- 性能和语义哈希是否变化；
- 是否产生新的 ADR；
- 未完成项和已知限制。
