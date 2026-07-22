---
document_type: capability-plan
decision_status: not-applicable
implementation_status: in-progress
normative_scope: target
last_verified: 2026-07-19
owner: unassigned
reviewers: []
---

# Telysta 专业语言模拟器实施总计划

- 状态：`Accepted capability map；R0A/R0B/R3B gate graph 于 2026-07-16 修订`
- 技术架构：Rust 原生生产核心已经 `Accepted`，见 [ADR-006](./adr/ADR-006-rust-native-core-python-research-bridge.md)
- 语言学架构：社区驱动模拟仍为分阶段 `Proposed`，不是 WS-1 前置；其局部机制须由后续 ADR 与 G2/G3/G4/G5 证据接受、替代或否决，见 [ADR-005](./adr/ADR-005-community-driven-language-simulation.md)
- 基线日期：2026-07-12；最近路线修订：2026-07-19
- 当前工作包：`R0A-08 verification trust + R0A-09 current v1 authority + R0A-10 legacy evidence containment + R0B WS-1 领域证据；GEN-001.2 implementation blocked`
- 目标：将现有研究原型逐步演进为可复现、可审计、可实际创作并可扩展至语言家族的语言历史模拟器

## 1. 文档职责

本文维护长期能力地图、领域边界、跨阶段依赖和 Gate 语义，不是当前执行 WBS、
工作包状态或队列的权威来源：

- [项目路线图](./ROADMAP.md)只汇总阶段状态、发布切片和当前 Next；
- 本文记录目标系统、长期能力、领域边界与跨阶段完成标准；
- [产品开发执行计划](./PRODUCT_DEVELOPMENT_PLAN.md)是工作包 ID、依赖、R2A–R2F 映射、当前状态、Stop/Go、执行队列与 capacity 的唯一 canonical WBS；
- [规则系统与语言质量计划](./RULE_QUALITY_PLAN.md)记录 RuleSpec 和质量指标细节；
- [代码与模块清理计划](./CLEANUP_PLAN.md)规定模块删除和合并流程；
- Accepted ADR 与已接受领域合同决定不可变语义、身份、writer、migration 和 replay；
- 版本化 Gate policy 决定 requirement 与接受谓词，GateEvidence 是实际 Gate decision 的唯一机器事实。

本文若重复列出 WBS 顺序，只构成便于阅读的镜像。镜像与 canonical WBS 不一致时，
相关工作立即停止并同步修订，不得选择对当前实现最方便的一份。任何新功能必须归属
长期能力地图与 canonical WBS；无法归属的功能先进入研究清单，不直接加入主流程。

### 1.1 交付方式

模块工作包描述“系统最终需要什么”，但提交顺序采用 walking skeleton：先冻结产品/科学合同和 clean baseline，再让 Blueprint、最小真实数据、RegistryBundle、LanguageState v3、双向 Grammar/Meaning IR、GenesisArtifact、TaskPack、一个结构 ChangeSet、项目存储和 Tauri 作者闭环形成端到端路径。语言可使用后才扩大真实传播、家族与文学规模。

里程碑顺序为：

1. R0A 产品/平台合同、ADR 拓扑、仓库基线与 GateEvidence；
2. R0B Meaning/Grammar、TaskPack、Canon、数据、evaluator 与低保真产品验证；
3. R1 application service、Project/Operation/Run ledger shell、持久化 Job、版本化 API/query 与恢复外壳；
4. R2 / WS-1 可执行微型语言与可审计结构变换；
5. R3 Story Language Kit、Canon-first、Meaning Workbench、Scene Lab 与生产性扩充；
6. R3B SpeechCommunity/Variation/ChangeProcess、实验与长历史存储合同；
7. R4 / WS-2 创新、变体、传播失败、常规化与消融；
8. R5 家族、接触、规律对应与重建；
9. R6 单语言高级篇章/文学能力与家族后续集成；
10. R7 Core Release，以及彼此独立的 Speech、Research、LLM/Extension 可选列车。

WS-1 的验收对象不是独立模块数量，而是一次真实流程：用户输入 Blueprint 或 CanonSeed，Rust 编译多个 candidate，经独立 evaluator 后封存 GenesisArtifact；项目创建并重开；同一 Grammar IR 生成并分析一段短文本、输出 IGT；应用一个 typed structural change；随后从 UI 查看状态、语义 hash、事件、CanonSeed compatibility/impact preview 和来源解释。R2 不创建 AuthorCanonCorpus/CanonRelease；该 change 只证明事务与回放，不证明真实传播。

## 2. 产品完成定义

Telysta 的最终产品不是随机造词器，而是本地优先的语言历史模拟和创作工作台。完成后的系统应能：

1. 根据明确的审美、类型学和社会历史约束编译一门内部一致的祖语；
2. 模拟使用、创新、社会扩散、音系重组、语法化、语义变化和类推；
3. 通过迁徙、隔离、接触、征服和标准化产生可追溯的语言家族；
4. 根据交际任务和语料缺口扩充词汇与构式，而不是固定次数注词；
5. 生成词典、参考语法、形态范式、词源、同源词表和逐词分析语料；
6. 支持用户声明式规则包，并在启用前完成校验、冲突分析和 dry-run；
7. 对每个结果提供来源、规则版本、置信度和历史解释；
8. 从 `SceneFacts → InteractionContext → CommunicativeIntent → PropositionGraph → LanguageSpecificObligations → Grammar Realization` 的分层表示生成文本，并行记录 `PragmaticCommitments`；源文本缺失而目标语言强制表达的信息必须形成可解决义务；
9. 输出正字法、音位、窄式语音表示和可验证的语音；
10. 通过确定性、类型学、历时对应、语料覆盖和专家评审质量门。
11. 支持 Language-first 与 Canon-first，共用同一 Blueprint 和正式状态；
12. 将姓名、台词和作品片段保存为版本化 CanonCorpus，变更必须先报告影响；
13. 无法表达时返回 typed ExpressionGap，禁止随机 fallback 或静默丢失意义；
14. 由未参与开发的创作者只使用工作台和导出文档完成新场景、新名字与修订任务。

“语言学家找不到任何争议”不是可验证目标。产品目标是：不出现基础结构矛盾，所有罕见或争议性结果均有证据、模型来源或明确的创作选择，并且能够完整复现和审计。

## 3. 当前基线与主要缺口

截至基线日期，已确认：

- 相同 seed 的两次 Epoch 运行会产生不同状态哈希、词数和类型学；
- 207 个创世词中有 30 个不满足项目自身音系合法性约束；
- 创世词形按概念独立随机产生，没有词根家族与构词历史；
- 主流程只有四个启用的音系算子，长期变化以磨损为主；
- 环境和审美 profile 没有接入主演化流程与 UI，部分字段没有生产调用；
- 扩充由固定领域词表和预写复合规则驱动，没有语言规模停止条件；
- 实测现代词汇约三分之二为名词，语义与语体覆盖严重不均衡；
- CSG 定义的多数关系没有进入规划器，不能支撑一般翻译和复杂叙事；
- Branch、Epoch 和 Flat 仍有不同的演化路径；
- 历史回放不能恢复完整 DAG、类型学和保护状态；
- 用户目前只能选择 seed、三个音素预设、LLM 与 Epoch 模式。

这些问题决定了实现顺序：先修状态和确定性，再建设新的语言模型；不能在不可信地基上继续堆规则和 UI。

## 4. 目标系统

```text
WorldModel
└── SpeechCommunity
    ├── demography / settlement / mobility
    ├── social network / prestige / L1-L2 ratio
    ├── contact / literacy / institutions
    └── CommunicationNeeds
            │
LanguageBlueprint
├── aesthetic preferences
├── typological constraints and priors
├── phonology / prosody / morphology / syntax
├── semantics / pragmatics / registers
└── orthography policy
            │
ProtoLanguageCompiler
├── coherent feature sampling
├── phonotactic grammar
├── root and derivation families
├── construction inventory
└── GenesisQualityGate
            │
HistoricalSimulation
├── InnovationGenerator
├── AdoptionAndDiffusion
├── SoundSystemRestructuring
├── GrammaticalizationAndReanalysis
├── SemanticsAndLexicalization
├── AnalogyAndRepair
├── ContactAndBorrowing
└── FamilyGraph
            │
LanguageState + ProvenanceLedger
            │
QualityLab / AuthoringStudio / Translation / Speech
```

所有状态修改必须通过 `StateTransaction`，所有随机选择必须来自版本化 `OperationContext` 所锁定的 `RngTree` 路径合同，所有变化必须生成版本化事件和解释。Job/Attempt 只描述执行，不得成为语言历史的语义身份。

生产系统的技术边界为：

```text
Svelte/TypeScript → Tauri commands/events → Rust Application Service
                                             │
                                             ▼
                                    Rust Simulation Core
                                  model / rules / simulation
                                  quality / storage / migration

Python Research Lab → datasets / experiments / reference vectors
                     不直接写正式 LanguageState
```

Rust 是正式项目状态和模拟结果的唯一事实来源。Python 旧引擎用于 A 阶段建立行为基线，之后只保留研究、数据处理和对照用途；最终桌面产品不依赖 Python sidecar。

## 5. 核心领域对象

### 5.1 Project、Operation、Job 与 RngTree

目标边界由 Proposed [ADR-011](./adr/ADR-011-project-manifest-run-ledger-job-identity.md) 决定，Accepted 前不能实施，也不能继续把语义输入、执行状态和文件路径混入一个 `RunContext`：

- `ProjectManifest` 保存项目身份、权威 history heads、schema 与 migration metadata；
- `RunLedger` 保存不可变 `OperationRecord`；每次 Genesis、Authoring、Simulation、Migration、Retcon 或 Import 都有稳定 `OperationId`；
- `OperationContext` 锁定 base history hash、引擎、模型、registry、规则、数据、TaskPack 与 RNG；
- `JobStore` 保存 `JobId`、`AttemptId`、progress、journal、checkpoint、cancel/crash/restart/resume 状态；
- `ChangeSet` 引用 `OperationId`，而不是 `JobId`；Job/Attempt 不进入 LanguageState semantic hash；
- restart 创建新 Attempt 并保持 OperationSpec 不变；resume 仅在全部输入、RNG frontier 与 checkpoint schema 均锁定时允许；
- 提交以 `OperationId + expected_history_hash` 幂等，staging result 未提交前不改变权威历史。

随机流按稳定路径派生，例如：

```text
root seed
├── genesis.phonology
├── genesis.lexicon
├── era.0042.sound_change
├── branch.northern.contact
└── llm.mock.proposals
```

增加一个新模块不能改变其他模块已经存在的随机序列。

### 5.2 TimeModel

历史时间不能继续由无量纲“轮次”代替。`TimeModel` 至少包含：

- 绝对或项目相对年份、世代长度和模拟步长；
- 变化的开始、持续、采用、竞争、稳定和终止区间；
- 迁徙、分裂、接触、征服、识字和标准化事件时间；
- 社区之间的接触强度和随时间变化的传播通道；
- 同时发生的变化及其依赖、阻断和重排序关系。

所有 `ChangeProcess` 和 `LanguageFamilyGraph` 事件必须引用版本化时间坐标；UI 可以显示“纪元”，但纪元只是 TimeModel 的视图，不是计算真值。

### 5.3 LanguageState

待 ADR 接受的目标边界为：

```text
ProjectWorldState
├── LanguageStructureState
│   ├── Phonology / Prosody / Morphology
│   ├── Construction / Meaning / Lexicon
│   ├── Pragmatics / Register / Orthography
│   └── structural provenance
├── SpeechCommunityState
├── PopulationVariationState
├── LanguageFamilyGraph
├── immutable CorpusLocks
└── ProjectModelLocks
```

`LanguageStructureState` 是某一 lect 在某时点已经常规化的结构快照。变体采用率、临时过程、token 语料、运行 Job、UI 选择和可重建统计不得混入其中。结构、变体、语料和历史仍由同一 Rust 权威与事务边界管理，但身份、hash、聚合与 replay 语义必须由 ADR 明确，不能由实现自行猜测。

### 5.4 LanguageBlueprint

每个用户特征具有以下控制级别：

- `locked`：模拟不得改变；
- `preferred`：作为有强度的先验；
- `emergent`：由历史产生；
- `hypothetical`：争议性研究假说，默认关闭并显示低置信度。

审美、自然环境、社会结构和谱系继承必须分层，禁止把“寒冷”“精灵”等标签直接编码为确定性语法或音变规律。

### 5.5 SpeechCommunity

至少包括人口、聚落、网络密度、迁徙、成人二语比例、接触、威望、识字、标准化和语体分层。第一版使用群体级参数，不立即模拟每个说话人；只有研究证明必要时才引入 agent-based speaker simulation。

### 5.6 ChangeProcess

变化不再等同于“规则对每个词随机执行”，而是：

`ChangeProcess` 必须是可重放的状态图，而不是强制线性流水线。它至少表达 innovation、竞争/共存、采用或拒绝、社会与词汇扩散、停滞、逆转、残留、重组、类推/修复、常规化和消融；不同阶段可重叠或失败。每个过程记录来源群体、typed environment/effect、持续时间、观察模型、采用轨迹、词汇扩散策略、社会评价、参数锁、终态和失败原因。

### 5.7 LanguageFamilyGraph

分支由迁徙或分离事件产生，记录分离年代、创始群体、联系强度、接触语言和独立随机流。借词、仿译、结构扩散和方言平整均作为显式事件，不通过直接覆盖子语言状态实现。

### 5.8 TheoryProfile 与 ModelEvidence

每次 Genesis 和 SimulationRun 锁定明确的 TheoryProfile：模型、参数、先验、适用域、证据类别、已知失败、版本和 semantic hash。改变模型只能创建新 run 或实验分支，不得重新解释既有历史。

正式模型版本还应绑定 `ExperimentSpec` 与 `ModelEvidenceBundle`，区分 verification、calibration、held-out validation、sensitivity 和 ablation，并以 ODD/TRACE 记录模型生命周期。

### 5.9 Meaning / Grammar IR

Meaning 不以源语言句子或一份扁平 `semantic_frame` 为权威。最低层级为：

```text
SceneFacts
→ InteractionContext
→ CommunicativeIntent
→ PropositionGraph
→ LanguageSpecificObligations
→ Grammar Realization

PragmaticCommitments 作为可追踪并行层
```

`SceneFacts` 保存实体、事件、时间、地点和世界关系；`InteractionContext` 保存 speaker/addressee、deictic center、common ground、discourse referents、社会关系与 genre；`CommunicativeIntent` 保存 speech act 与信息/社会目标；`PropositionGraph` 保存 predicate、typed roles、polarity、quantification/scope、时体和 modality；`PragmaticCommitments` 区分 asserted、presupposed、implicated 与 accommodated；`LanguageSpecificObligations` 保存目标语言必须解析的区分。每层分别定义 equivalence、允许歧义和 typed gap。

Grammar IR 必须由生成与分析共享，最小表达上述有限子集、selection、agreement、linearization 与 morphology realization。不支持的 scope、modality 或 pragmatics 必须返回 typed `ExpressionGap`，不得静默近似。

解析索引、FST、搜索表和缓存由 grammar hash + compiler version 派生，不进入权威状态。

### 5.10 TaskPack 与 ProofCarryingUtterance

TaskCase 保存 scene facts、speaker/addressee、deictic anchor、speech act、scope graph、required meaning、optional nuance、forbidden reading、commitment status、discourse pre/postcondition、register/genre 与 equivalence policy。每个正式输出携带意义、构式、词素、gloss、音系、正字法、时代/方言、允许歧义与来源，形成可验证的 `ProofCarryingUtterance`。

### 5.10A Orthography 与 IGT Projection Authority

正字法不是 IPA 展示别名，也不要求与音系双射。其权威拆分会改变持久化实体含义，
因此在 ADR-014 修订或 replacement ADR Accepted 前不得实现 WS1-04A。推荐决策是：
LanguageStructureState 拥有版本化字素表、Unicode normalization、边界策略、
typed phonology↔orthography mapping 与词汇化拼写 override；CanonSeed spelling
保持带来源和锁定策略的输入约束，作者接受后才成为相应 Canon/lexical authority。
WordForm 身份不得由显示拼写字符串推导，拼写也不得只以裸 `PhonologicalForm` 为键。
ADR 必须选择稳定 `OrthographicForm/SpellingRealization`：优先以 typed
WordForm/analysis occurrence + OrthographyRevision 为键；若选择独立 orthographic
base，必须给出等价的 identity/hash/replay 语义。上述 authoritative identity、
mapping、policy 和 override 进入 StateSemanticHash；拼写候选、analysis forest 与
IGT 是绑定 language revision 和输入 Meaning 的纯查询工件，不进入该 hash。

软件硬约束是确定性投影、显式歧义、segment/morpheme/construction 可追踪性和
query purity，而不是强迫每种文字系统一一对应。`SoundChange` 只改变其 typed
phonological effect，不得静默改写拼写；保守拼写持续存在，直到独立、可审计且可回放
的 `OrthographicChange` 被提交。v2 migration 缺少 mapping 时必须产生显式
`OrthographyUnavailable`/typed gap，禁止猜测。ADR 必须冻结 lexical spelling、
保守拼写、拼写改革和 WordForm 的 migration/hash/replay 语义。

`parse(spell(A, O), O)` 必须包含与 typed analysis `A` 等价的分析，同时拒绝锁定的
forbidden analysis；其中 `O` 是 OrthographyRevision。对 `parse(S, O)` 返回的每个
许可分析，`spell(A', O)` 只能产生许可的 canonical/variant spelling。malformed
spelling、同音异写、未映射音段、字素冲突、normalization 差异、analysis precision
和 ambiguity budget 必须通过 hostile cases，禁止“任何输入返回全部分析”的万能
analyzer，也禁止回退到 raw IPA。IGT 必须从同一分析图投影 orthographic line、morpheme segmentation、
versioned gloss vocabulary 与 translation，并对 zero、syncretism、fusion 等非双射
结构保存 span/contribution 对齐，不能手工维护第二份分析。

### 5.11 CanonCorpus 与 Onomasticon

CanonSeed 保存已有姓名、词语、拼写和台词锚点；`AuthorCanonCorpus` 保存作者批准的正式文本与发布版本。任何规则、语法、词义或历史变化必须先执行 canon impact。Onomasticon 将人名、地名、族名、王号、本名/外名/旧名建模为有词素、时代、lect、命名传统和词源的对象，而不是随机合法字符串；完整 SpeechCommunity 关联在 WS-2 建立。

语料必须带 `CorpusRole`：`AuthorCanonCorpus` 只用于兼容性与回归；`EvaluationTaskCorpus` 只用于任务与审计；`SyntheticUsageCorpus` 必须锁定 TheoryProfile、场景分布、抽样单位、seed 和生成过程；`EmpiricalReferenceCorpus` 只用于 prior、calibration 与 held-out validation。Canon 可产生需求或场景 seed，但不能自动变成人口使用频率；同一 slice 不得同时调参和验证同一声明。

### 5.12 语言能力、产品可用性与创作评价

`LanguageCapabilityCertificate` 锁定 language revision、era、lect、Meaning/Grammar、TaskPack/evaluator packs、Canon、数据/模型锁、支持能力、typed gaps 和已知限制。影响语义或评价边界的变更会使证书过期；能力层级使用 `LC0–LC6`，其中 `LC1` 仅称“可执行微型语言”。

`ProductUsabilityEvidenceBundle` 另行锁定 app build、平台、locale、无障碍配置、persona、招募条件、任务协议、完成/耗时/错误/求助/恢复指标，以及用户是否理解 gap、canon impact 和 provenance。`CreativeEvaluationRecord` 保存作者与盲评者的审美、文学和声音判断。三者不得互相替代，也不得压缩成单一“自然度”分数。

`ReleaseClaimManifest` 将 build、manifest phase、candidate/effective channel、
`claimsEffective`、GateEvidence hash、Capability Matrix、supported/planned/refused
能力、允许/禁止声明、已知限制与过期条件投影到应用、README 和导出。它是只读发布
工件，不进入 LanguageState 或历史，也不能成为第二权威 writer。用于产生 Gate 证据
的 candidate manifest 不生效产品声明；Gate 通过后另行生成引用 candidate/evidence
hash 的 immutable effective manifest，禁止原地升级。

## 6. 工作流与工作包

### PLT：Rust 平台与迁移边界

| ID | 工作 | 主要输出 | 完成标准 |
|---|---|---|---|
| PLT-001 | Rust workspace | core、application、storage、Tauri crate 边界 | 依赖方向由自动检查约束 |
| PLT-002 | Tauri command/event API | 版本化 request、response、progress、cancel | UI 不直接访问领域状态或数据库 |
| PLT-003 | Python Research Bridge | 数据、提案和黄金向量交换协议 | Python 不能写正式项目状态 |
| PLT-004 | Legacy Adapter | 旧快照读取、规范化报告和缺陷标记 | 不把旧 schema 冻结为新领域模型 |
| PLT-005 | Cross-platform Build | Windows 优先，随后 macOS/Linux | 正式构建无 Python 运行时依赖 |
| PLT-006 | Application Service / Persistent Job | use-case service、JobStore/lease/journal/cursor、staging、submit/query/cancel/restart/resume、dependency bundle | Tauri 不直接编排事务；遗漏事件可补投；长任务不会留下半提交状态；离线项目可审计/重验 |
| PLT-007 | Headless Experiment Runner | versioned ExperimentSpec、batch runner、raw artifact index | 与桌面共用 application/query 边界；不形成第二状态 writer |

历史 PLT-001/002 Spike 已证明 Rust/Tauri 技术方向；正式 R1 只能在 G0A 后推进，且不得冻结 LanguageState v3 或 WS-1 领域对象。ADR-005 是分阶段研究背景，不是平台或 WS-1 的单一接受前置。

### AGT：Agent 治理与项目能力

| ID | 工作 | 主要输出 | 完成标准 |
|---|---|---|---|
| AGT-001 | Project Agent Contract | 根级 `AGENTS.md`、权威边界和停止条件 | Agent 不需要重新推断生产真值与测试入口 |
| AGT-002 | Skill Supply Chain | allowlist、来源/commit/许可证/权限审查 | 未审查网络 Skill 不执行 |
| AGT-003 | Linguistic Architecture Review | 领域审查 Skill 与结构化风险报告 | 核心模型缺口在编码前暴露 |
| AGT-004 | Rust Domain Guardian | schema、事件、迁移、事务审查 | 权威写入和 replay 不变量不可绕过 |
| AGT-005 | Simulation Validation | 确定性、多 seed、敏感性、独立验证报告 | 测试通过不再被误报为科学有效 |

### FND：确定性、状态与存储

| ID | 工作 | 主要输出 | 完成标准 |
|---|---|---|---|
| FND-001 | 规范化实体 ID | 全部 ID 使用稳定字符串 | 快照无混合 key，旧 ID 可迁移 |
| FND-002 | Canonical State Schema | 版本化 LanguageState schema | schema 可验证，非语义字段明确 |
| FND-003 | Semantic State Hasher | 词典、DAG、类型学、事件分域哈希 | 同状态稳定，同语义变化必改变 |
| FND-004 | RngTree | 路径派生的独立随机流 | 添加无关模块不影响已有结果 |
| FND-005 | Project/Operation/Run/Job Identity | ADR-011 的 ProjectManifest、RunLedger、OperationContext/RunSpec、Job/Attempt | 语义操作与执行状态分离；restart/resume/commit 规则可迁移、可回放 |
| FND-006 | StateTransaction | 唯一状态修改入口 | 不再存在绕过事务的生产写入 |
| FND-007 | 完整事件 schema | 词汇、DAG、类型学、语法和接触事件 | 在线状态可由事件重放 |
| FND-008 | 原子持久化和迁移 | 原子写、校验、格式版本 | 中断不会留下可误读项目 |
| FND-009 | 统一单时代核心 | Flat/Epoch/Branch 共用演化服务 | 三种模式无重复业务循环 |
| FND-010 | TimeModel | 年份、世代、区间、采用曲线和同时变化 | 所有历史过程引用统一时间坐标 |

依赖关系：`PLT-001 → FND-001/FND-004/FND-010 → G0A/Accepted ADR-011 → FND-005/PLT-006/FND-008`；`G1 + G0B → LanguageState v3 对应的 FND-002/FND-006/FND-007/FND-009 slice`。平台 ledger/Job walking skeleton 不冻结 LanguageState v3，但任何持久化身份实现都必须等待对应 ADR Accepted。

### DAT：经验数据与版本治理

| ID | 工作 | 主要输出 | 完成标准 |
|---|---|---|---|
| DAT-001 | 数据源清单 | PHOIBLE、WALS/Grambank、CLICS、Lexibank/Concepticon、CLDF | 版本、许可证、用途与限制完整 |
| DAT-002 | Feature Registry | 统一音系、语法、语义 feature ID | 内部不再使用无约束字符串 |
| DAT-003 | Empirical Priors | 按谱系/区域控制的统计先验 | 与硬约束和用户审美严格区分 |
| DAT-004 | CLDF 互操作 | Wordlist/StructureDataset 导入导出 | 示例数据可往返验证 |
| DAT-005 | Calibration / Identifiability Protocol | 留出集、谱系/区域分层、缺失值、parameter recovery、equifinality、敏感性与消融 | 先验经过校准且不被表述为因果定律；模型参数在目标观测下是否可辨识有证据 |
| DAT-006 | Corpus Role / Observation Contract | author canon、evaluation task、synthetic usage、empirical reference 与 typed observation | 语料用途、抽样、split、transform、license、hash 不可互换；无自证循环 |

数据不能直接变成“自然语言模板”；必须记录采样偏差、缺失值和置信度。

### GEN：祖语蓝图与编译器

| ID | 工作 | 主要输出 | 完成标准 |
|---|---|---|---|
| GEN-001 | LanguageBlueprint | locked/preferred/emergent 模型 | UI 与引擎共用 schema |
| GEN-001.2 | Domain Model Hardening | LanguageState v3、typed FeatureRegistry、ChangeEvent、GenesisArtifact | 状态能表达祖语与变化，创建边界不可绕过 |
| GEN-002 | SpeechCommunity v1 | 群体级社会语言学参数 | 参数影响路径可解释 |
| GEN-003 | 音系编译器 | inventory、allophony、prosody、phonotactics | 100% 创世词通过合法性检查 |
| GEN-004 | 词根与派生家族 | Root/Lexeme/Sense/Derivation graph | 基础词不再全部独立随机 |
| GEN-005 | 祖语语法编译器 | coherent typology + constructions | 所有范式和构式通过约束检查 |
| GEN-006 | 创世质量门 | 完整 GenesisQualityReport | 硬错误阻止模拟启动 |
| GEN-007 | Preference Compiler | 感知目标、结构偏好、多候选 Pareto 采样和解释 | “优雅/冷峻”等偏好不直接变成伪语言规律 |
| GEN-008 | Candidate Lifecycle | CandidateSet、Unverified/VerifiedGenesisArtifact、过期与重验 | 未经独立验证或锁已改变的候选不能创建项目 |

### EVO：历时变化核心

| ID | 工作 | 主要输出 | 完成标准 |
|---|---|---|---|
| EVO-001 | ChangeProcess State Graph | 创新、共存/竞争、采用/拒绝、扩散、停滞/逆转、重组、常规化/消融 | 变化可重叠、失败并保留残留；过程与结构提交分离 |
| EVO-001A | Surface Variation / Perception | typed variant realization、allophony、perception 与 token observation | 音变、借词适应和 observation 不以底层音位串直接代替表面证据 |
| EVO-002 | 规则音变与词汇扩散 | regular/frequency/class/sporadic 模式 | 同源词形成可测对应 |
| EVO-003 | 音系重组 | merger、split、chain shift、phonemicization | inventory 会随历史改变 |
| EVO-004 | 类推与范式整平 | analogy、leveling、irregularization | 例外具有明确来源 |
| EVO-005 | 形态音系 | 边界、异形、融合、重音互动 | 词形和音变使用同一分析 |
| EVO-006 | 语法化与重新分析 | 构式驱动路径 | 类型学状态由具体历史推导 |
| EVO-007 | 语义变化 | polysemy、metaphor、metonymy、narrowing 等 | 新义项保留来源和方向 |
| EVO-008 | 正字法历史 | 拼写标准、保守拼写、改革 | 拼写与发音可以历史分离 |
| EVO-009 | PopulationVariationState | `(community, lect)` 新旧变体、条件分布、UsageObservation | 传播中变体与已常规化结构分离，成功/失败均可回放 |

### FAM：迁徙、分支与接触

| ID | 工作 | 主要输出 | 完成标准 |
|---|---|---|---|
| FAM-001 | MigrationEvent | 迁徙、创始人口和目的地 | 可从任意历史状态建立分支 |
| FAM-002 | FamilyGraph | 祖先、分支、方言连续体 | 家族关系可回放和比较 |
| FAM-003 | ContactEngine | 借词、仿译、结构扩散 | 借入形式符合当时双方音系 |
| FAM-004 | 社会扩散与等语线 | 地域/阶层采用差异 | 分支差异与隔离强度相关 |
| FAM-005 | 标准化与方言平整 | 威望语、书面语和教育事件 | 标准化不抹除历史来源 |

### GRM：语法与构式系统

| ID | 工作 | 主要输出 | 完成标准 |
|---|---|---|---|
| GRM-001 | Grammar Feature Model | 对齐、标记、TAM、语态、从句、信息结构 | 不再只依赖宏观 morph type |
| GRM-002 | Construction Inventory | 简单句到复杂篇章的构式 | 每个构式声明语义和形式槽位 |
| GRM-003 | Paradigm Engine | 屈折、异形、融合、零标记、缺陷范式 | 范式覆盖和同形可诊断 |
| GRM-004 | Constraint Solver | 依赖、冲突、罕见组合提示 | 硬错误与软警告分离 |
| GRM-005 | Semantic/Discourse IR | 指代、事件、时体、情态、信息结构 | 可表达复杂叙事而非只支持 SVO |
| GRM-006 | Realizer | IR → construction → morphology → order | 不静默丢失核心语义角色 |
| GRM-007 | Interlinear Gloss | 文本、词素切分、versioned gloss vocabulary、翻译 | IGT 从 realizer/analyzer 同一图投影；zero/syncretism/fusion 的非双射 span/contribution 可追踪，不手写第二分析 |
| GRM-008 | Bidirectional Analyzer | surface/morphology/construction → Meaning IR | `analyse(realize(M))` 至少包含一个与 M 等价的读法 |
| GRM-009 | Proof-Carrying Utterance | 意义、构式、词素、gloss、音系、语体、来源 | 无法结清意义或结构义务的输出不能进入 Canon |

### LEX：语义、扩充与文学能力

| ID | 工作 | 主要输出 | 完成标准 |
|---|---|---|---|
| LEX-001 | LexiconSenseGraph | lexeme、sense、relation、register | 多义、同义和语体可表达 |
| LEX-002 | CommunicationNeedEngine | 领域、场景、语义框架需求 | 扩词由缺口驱动 |
| LEX-003 | WordFormationStrategies | 派生、复合、转类、重叠、借词、创新 | 每个新词有形成策略和来源 |
| LEX-004 | Synthetic Usage / Observation | 锁定场景分布、sampling unit、TheoryProfile 的 token/collocation/construction observation | 频率来自显式模拟或经验 observation；不得从 AuthorCanon 自动推断 |
| LEX-005 | Register/Genre Model | 口语、正式、宗教、诗歌、古语、方言 | 同一概念可按语体选择形式 |
| LEX-006 | Literary Task Suite | 叙事、对话、论证、诗歌、史诗任务 | 无临时随机 fallback 完成目标任务 |
| LEX-007 | Readiness Model | 词汇家族、义项、构式、覆盖率多维报告 | 不用单一词数判断完成 |
| LEX-008 | TaskPack / ExpressionGap | versioned scene tasks、禁止读法、缺口与 lexical debt | 不能表达时明确失败，扩充由真实任务触发 |
| LEX-009 | CanonCorpus / Onomasticon | 发布文本、姓名系统、旧名/外名与影响索引 | 规则变更不能静默破坏已发布形式 |

### RUL：可插拔规则平台

| ID | 工作 | 主要输出 | 完成标准 |
|---|---|---|---|
| RUL-001 | Rule Pack Manifest | ID、版本、引擎范围、作者、许可证 | 项目固定规则包版本 |
| RUL-002 | RuleSpec schemas | phonology、morphology、grammar、semantic、contact | 数据规则无任意代码执行 |
| RUL-003 | Rule Compiler | RuleSpec → stable IR | schema 与执行后端解耦 |
| RUL-004 | Conflict Analyzer | 写冲突、振荡、不可达、循环 repair | 高风险冲突阻止激活 |
| RUL-005 | Dry-run and Explain | 影响范围、示例、状态 diff | 启用前可预览结果 |
| RUL-006 | Rule SDK | 模板、测试工具、打包、文档 | 用户可独立制作规则包 |
| RUL-007 | Sandboxed Extension | 受限 WASM 高级插件，后置任务 | 无任意文件、网络和状态写权限 |

普通用户扩展以声明式 Rule Pack 为主；任意 Python 插件不进入产品安全边界。

### QLT：验证、基准与专家审计

| ID | 工作 | 主要输出 | 完成标准 |
|---|---|---|---|
| QLT-001 | Hard Invariants | 音系、DAG、范式、语义角色、回放约束 | 违反即失败 |
| QLT-002 | Typological Diagnostics | 频率、依赖、罕见度、数据覆盖 | 罕见与错误明确区分 |
| QLT-003 | Diachronic Diagnostics | 对应规律、借词层、路径完整性 | 每个现代形式可追溯 |
| QLT-004 | Golden Scenarios | 最小、标准、长周期、分支、接触、文学 | CI 稳定复现语义哈希 |
| QLT-005 | Reconstruction Challenge | 从子语言反推祖语和对应 | 可量化家族历史规律性 |
| QLT-006 | Expert Audit Package | 语法、词典、IGT、对应表、规则账本 | 专家无需读源码即可审计 |
| QLT-007 | Blind Expert Review | 外部语言学家按 rubric 评估 | 严重结构问题归零后再发布 |
| QLT-008 | Multi-seed Diagnostics | 性质测试、统计分布、异常 seed 和语义 diff | 不以单个黄金哈希代替模型质量 |
| QLT-009 | ModelEvidence / ODD-TRACE | verification、calibration、held-out、敏感性、消融 | 每个模型声明都公开适用域和已知失败 |
| QLT-010 | Independent Evaluator / LanguageCapabilityCertificate | Development、CandidateSelection、SealedAudit、ExternalElicitation packs；反例、缺陷注入、版本锁与能力证书 | 生成器不能用私有启发式自我认证；欠生成、过生成、禁读接受、歧义与 gap 分项报告；变更后自动过期 |
| QLT-011 | GateEvidenceManifest | claim、证据种类、锁、协议、阈值、结果、review/waiver、过期条件 | 软件、语言能力、科学模型、产品可用性和专家/创作证据不可互相替代 |

### APP：桌面产品

| ID | 工作 | 主要输出 | 完成标准 |
|---|---|---|---|
| APP-000 | Continuous Product Discovery | primary persona/JTBD、形成性访谈、确认性任务、可用性原型和非目标 | 首发严肃叙事作者完成真实 canon 任务；conlanger 验证 expert disclosure，语言学家验证审计信息；参与者与实现者角色分离 |
| APP-001 | Rust Core Shell Spike | engine_info/run/progress/cancel/crash recovery | Tauri 直接调用 Rust 且无 Python 依赖 |
| APP-002 | Project Workspace | 新建、打开、保存、迁移、导出 | 中断不损坏项目 |
| APP-003 | Quick Mode | 审美、社区、复杂度和历史向导 | 非专家可生成一致祖语 |
| APP-004 | Expert Mode | feature、构式、规则、历史编辑器 | 专家可见约束与罕见度 |
| APP-005 | Research Mode | 批量运行、参数扫描、对照和统计 | 可导出可复现实验 manifest |
| APP-006 | Timeline/Family/DAG | 历史、分支、借词层和规则解释 | 任意结果可导航到来源 |
| APP-007 | Rule Studio | 编辑、校验、dry-run、打包 | 无效规则不能启用 |
| APP-008 | Quality Lab | 多维质量报告与异常定位 | 分数可下钻到规则和实体 |
| APP-009 | Authoring Studio | 翻译、IGT、词典、语法和语料 | 可用于实际创作 |
| APP-010 | Meaning Workbench / Scene Lab / Canon Guardian | scene facts、interaction、scope/obligation、候选话语、作者决定与 canon impact | 作者能在不编辑 JSON/形式语义的情况下发现并解决歧义或义务，安全扩充语言 |

### SPH：翻译、发音与语音

| ID | 工作 | 主要输出 | 完成标准 |
|---|---|---|---|
| SPH-001 | Source Semantic Parser | 源文本 → Discourse IR，LLM 可选 | 歧义可显示和人工修正 |
| SPH-002 | Orthographic Realizer | 形态结果 → 正字法 | 拼写规则版本化 |
| SPH-003 | PronunciationPlan v1 | morphology → phonology → typed allophony → utterance prosody → phones | R3 提供确定性、可审计发音计划；不承诺自然音频 |
| SPH-003A | SpeechRenderPlan / PhoneticPlan v2 | tempo、coarticulation、actor guidance、音频/TTS 映射 | R7 在 v1 上扩展渲染，不反向定义语言结构 |
| SPH-004 | Deterministic TTS | 自定义音素映射与 WAV 输出 | 所有目标音素有定义输出 |
| SPH-005 | Neural Speech Option | 音系特征条件化语音 | 与确定性发音分开标注质量 |

TTS 不能早于稳定的音系、韵律、形态音系和正字法模型。

## 7. 阶段依赖

```text
R0A platform/repository/identity decisions → G0A → R1 / G1
       │                                      Application / Job / query / storage
       └──────────────┐
                      │
R0B WS-1 domain/evidence decisions → G0B
                      │
                  G1 + G0B
                      ↓
R2 / G2 WS-1：Meaning/Grammar → Genesis → create/reopen → structural change
                      ↓
R3 / G3 Story Kit：Canon → Meaning Workbench/Scene Lab → safe growth
          ├──────────→ single-language advanced discourse/literature lane
          └──────────→ R3B / G3B WS-2 model/experiment/storage readiness
                                   ↓
                              G3 + G3B
                                   ↓
R4 / G4 Mechanistic Change：variation → propagation/failure → conventionalization
                                   ↓
R5 / G5 Family：branch/contact → correspondence → reconstruction
                                   ↓
R6 / G6 family integration / expert audit / publish-grade Language Bible

R7 / G7 Core Release；Speech、Research、LLM/Extension 为独立可选列车

贯穿泳道：DAT + QLT + UX + I18N + PERF + CLEANUP
RulePack：R3 Structural/Authoring rules → R4 Process rules → SDK/optional sandbox
```

- G0A 关闭后允许 `PLT-006` 用假确定性任务实现 application、Project/Operation/Run ledger 与 Job walking skeleton，并与 R0B 并行；任何持久化身份、resume 或 replay 语义必须先由 Accepted ADR 决定；
- 只有 G1 与 G0B 同时关闭，才实现 LanguageState v3、Genesis、正式 reducer 和项目创建；
- `GEN-001.2` 被拆为 R0B 决策与 WS-1 小纵切；`GEN-002` 后移到 R3B/R4，必须晚于可执行语言和 Story Kit；
- 只有 G3 与 G3B 同时关闭，才实现 SpeechCommunity、Variation、UsageObservation 和 ChangeProcess 的生产 schema；
- `RUL-001/002` 可在 R0/R1 设计；R3 只交付已稳定结构 effect 的 authoring rules，R4 才交付受 TheoryProfile/RngTree/ChangeProcess 约束的 process rules；
- Quality、数据、UX 与科学证据是每个 Gate 的贯穿交付，不是发布前补测；
- R3 交付确定性 `PronunciationPlan v1`；R7 的语音渲染/TTS 不参与定义语言结构、历史或使用性是否正确；
- R3 后的单语言文学能力不等待 R5；只有家族史集成、重建审计和全量 Language Bible 依赖 R5。

### 7.1 R2 内部门（canonical WBS 镜像）

本节镜像[产品开发执行计划 §8](./PRODUCT_DEVELOPMENT_PLAN.md#8-r2--ws-1可执行语言纵切)；
工作包 ID、依赖和状态以该执行计划为唯一 canonical WBS。

WS-1 不以一个大 PR 一次通过，按以下可停止、可回滚的内部门推进：

1. `R2A`：复用 R1 已验证的 ProjectManifest/RunLedger shell，完成 Registry、State、
   Meaning/Grammar 的 in-memory typed language；不得重新定义 Project/Operation/Run/Job；
2. `R2B`：candidate compiler + independent evaluator，隔离 CandidateSelection、
   sealed 和 negative evidence；
3. `R2C`：typed structural ChangeSet + atomic reducer，先在内存中验证 precondition、
   effect ordering、rollback 和 replay；
4. `R2D`：append-only domain history + Genesis seal/create/reopen + dependency
   bundle/ReplayCapability；只有 R2B 与 R2C 均通过后才能物化生产 Genesis root；
5. `R2E`：Meaning Workbench + authoring round trip + typed gaps；
6. `R2F`：Tauri vertical slice、cancel/crash/reopen、query projection 与 GateEvidence 收口。

R2B 与 R2C 可以并行准备，但同一时刻最多一个包改变 schema、writer 或 replay。
R2D 同时依赖 R2B 与 R2C，不得把 seal/create 提前到 typed ChangeSet 和 history
boundary 之前。任一门失败都回到该 slice 的合同或实现，不允许以空状态、自由字符串
语义、完整状态替换或 UI fallback 跨越后续门。

产品主流程固定为：

```text
创建世界、语言目标或 CanonSeed
→ 生成、验证并比较多个祖语候选
→ 用 TaskPack 证明最小表达/分析并创建项目
→ 在 Meaning Workbench 中检查 scene、指称、scope、语用义务与允许歧义
→ 在 Scene Lab 中扩充词族、构式、名字与 Canon
→ 建立社区、变体、地图和时间事件
→ 模拟传播、失败、常规化、分支与接触
→ 检查来源、同源集、规则对应、Canon 影响和质量诊断
→ dry-run 用户规则并继续演化
→ 导出词典、语法、IGT、谱系、能力/可用性证据和可选语音
```

Quick、Expert 和 Research 是同一状态与命令模型的不同视图，不能形成三套业务流程。

## 8. 已完成基线：A-002 详细任务

- 完成日期：2026-07-12
- 实现位置：`app/core/rng.py`、`app/domain/storage/canonical.py`、`app/engine/golden.py`
- 黄金 manifest：`tests/fixtures/golden/legacy_v1.json`
- 执行入口：`scripts/baseline_report.py`
- 验证证据：513 项测试通过；五个场景同 seed 三次、跨进程、顺序隔离和跨 seed 隔离通过
- 已知结果：seed 888 的 genesis 仍有 22 个音系非法形式；Epoch 边界事件和 Branch 事件仍不完整，转入 A-003 固定为失败特征测试

### A-003 完成证据

- 完成日期：2026-07-13
- 特征矩阵：`tests/storage/test_history_replay_features.py`
- 事件账本：`docs/LEGACY_EVENT_COVERAGE.md`
- 当前通过：音变词形/时代、手工注词、软删除
- 严格 `xfail`：完整状态/DAG、Swadesh、类型学、辅助事件字段、借词、化石、复合和 Epoch 注词
- 验证证据：516 项通过，8 项已登记 `xfail`；`xfail(strict=True)` 防止缺陷被静默掩盖
- 决策：不在 Python 旧存储中进行全面修复；这些失败场景转为 Rust `StateTransaction`、事件 schema 和 reducer 的验收样本

### A-004 完成证据

- 完成日期：2026-07-13
- 可重复报告：`scripts/module_inventory.py`
- 测试：`tests/core/test_module_inventory.py`
- 静态事实：87 个 `app` 模块；65 个从 CLI/Streamlit 可达；57 个被测试引用；22 个不在生产静态路径
- 迁移决策：[模块迁移矩阵](./MODULE_MIGRATION_MATRIX.md)
- 决策：不删除任何模块；所有静态不可达结果仍受动态引用、数据依赖和迁移门约束
- 验证证据：519 项通过，8 项已登记 `xfail`

### A002-01：Canonical ID Policy

- 统一 `word_id`、node ID、rule ID、branch ID 为字符串；
- 定义命名空间与稳定生成方式；
- 为旧数字 ID 提供读取迁移；
- 禁止哈希依赖对象插入顺序。

完成标准：现有快照可规范化，JSON key 不再混合整数和字符串。

### A002-02：Semantic Snapshot Schema

- 明确哪些字段决定语言语义；
- 排除 timestamp、绝对路径、日志和耗时；
- 规范集合、映射、浮点数和枚举序列化；
- schema 带版本。

A-002 的 schema 是 `legacy canonical adapter`，用于固定旧引擎观察结果和定位差异，不等同于 Rust 新核心的最终 `LanguageState`。新 schema 必须在 TimeModel 和 ADR-005 Spike 后单独决策。

完成标准：同一状态跨进程序列化字节一致。

### A002-03：分域状态哈希

输出：

- lexicon hash；
- DAG hash；
- typology/grammar hash；
- event hash；
- full semantic hash。

完成标准：报告能够定位差异来自哪个领域。

### A002-04：RngTree 最小实现

- 根 seed 只保存一次；
- 通过稳定路径派生随机流；
- 禁止生产代码调用模块级 `random` 或无 seed `Random()`；
- NumPy RNG 使用对应派生 seed。

本任务在 Python 旧引擎中只实现满足基线所需的最小兼容层；永久算法、路径规范和版本承诺在 Rust `FND-004` 中实现。不得为追求旧输出相等而冻结不合理的 `seed + era` 方案。

完成标准：静态扫描和测试都能阻止未受控随机源。

### A002-05：黄金场景 v1

至少建立：

1. 创世最小场景；
2. Flat 10 era；
3. Epoch 注词与复合；
4. Branch 分叉；
5. Mock LLM 开启；
6. 同 seed 三次运行；
7. 不同 seed 差异检查。

黄金 fixture 记录输入、引擎版本、规则版本和分域哈希，不直接保存易碎的全部输出文本。

### A002-06：确定性门

必须满足：

- 同配置、同 seed 连续三次 full semantic hash 相同；
- 不同进程结果相同；
- 测试顺序不影响结果；
- 先运行其他 seed 不影响目标 seed；
- 关闭或开启无关日志不影响结果；
- 添加不消费现有随机流的新模块不改变旧结果。

### A002-07：基线报告

每个黄金场景输出：

- 存活/死亡词；
- 词类和语义域分布；
- 平均音段和音节；
- 同音密度；
- 语法化和词素数量；
- DAG 连通度；
- 类型学状态；
- 规则应用统计；
- 硬约束错误。

这些指标用于观察变化，不在 A-002 中强行修改语言学行为。

## 9. 优化策略

### 9.1 允许大规模重构，但按领域切换

- 先用适配器让旧模型产生新 schema；
- 可以整体重建 Rust 领域对象、存储格式和执行路径，不要求保持 Python 类结构；
- 新核心通过黄金场景和领域不变量后，以领域纵切为单位切换权威调用；
- 一个 PR 可以覆盖一个完整领域纵切，但不得混入无关领域和无证据删除；
- 行为变化与文件移动、格式化分开提交；
- 旧格式必须有显式迁移或正式放弃记录。

双轨只用于迁移期对照。一个 Rust 领域实现成为权威后，应停止该领域的生产双写并进入旧实现删除流程，避免长期维护 Python/Rust 两套核心。

### 9.2 正确性优先于性能

优化顺序：

1. 语义正确；
2. 可复现；
3. 可解释；
4. Rust 类型和事务边界能够表达不变量；
5. 通过基准；
6. profiling；
7. 对 Rust 热路径进行数据布局、并行和算法优化。

不得为了速度跳过事务、验证和来源记录。

### 9.3 分离四类知识

| 类型 | 行为 |
|---|---|
| Hard constraint | 违反即拒绝 |
| Empirical prior | 改变概率并显示数据覆盖 |
| Research hypothesis | 默认关闭，显示置信度和来源 |
| Creative preference | 用户审美，不宣称为自然规律 |

### 9.4 以语义 diff 代替脆弱快照

测试优先比较规范化状态和领域哈希。只有协议、导出格式和 UI 文案需要完整文本快照。

### 9.5 规则数据化，执行器最小化

通用变化由 RuleSpec 表达；只有 RuleSpec 无法表达且证明具有复用价值的算法才进入可信代码插件。

### 9.6 指标必须可下钻

不提供无法解释的“自然度 87 分”。每个质量指标必须能定位到语言状态、构式、词条、规则或历史事件。

## 10. 跨阶段质量门

每个 Gate 都绑定固定 fixture、TaskPack、反例、失败阈值、证据包和重新验证条件。以下编号与 [产品开发执行计划](./PRODUCT_DEVELOPMENT_PLAN.md)一致。

### 10.1 GateEvidenceManifest

每次 Gate 决策必须生成版本化 `GateEvidenceManifest`，至少记录：

- `gate_id`、`claim_ids`、source commit/build 与决策时间；
- schema、grammar、TaskPack/evaluator、data、model、rule 与 RNG locks；
- protocol、fixture、sampling、预注册阈值与 raw artifact references；
- 结果、已知失败、severity、waiver/rationale 和允许的产品声明；
- owner、reviewer、专业角色、独立性/利益冲突；
- `expires_when`、revalidation triggers 与失败后的 rollback/next action。

证据种类分为 `SoftwareVerificationEvidence`、`LinguisticCapabilityEvidence`、`ScientificModelEvidence`、`ProductUsabilityEvidence` 和 `ExpertOrCreativeReviewEvidence`。任一类都不能替代另一类；manifest 是 CI/发布工件，不进入 LanguageState，也不形成新的权威 writer。

### G0A：Platform Contract Ready

G0A 的 requirement 与接受谓词必须由版本化 Gate policy 机器定义。下一版 policy
的 required requirement 集合必须精确等于 `R0A-01`、`R0A-02-ADR011`、`R0A-03`、`R0A-04`、`R0A-05`、
`R0A-06`、`R0A-07`、`R0A-08`、`R0A-09`、`R0A-10`。其中 R0A-07 必须机器
验证 owner、独立 reviewer、capacity、estimate、WIP 与 timebox；R0A-08/09/10
必须使用各自的 terminal acceptance predicate 和 provenance。policy 缺项、文档与
policy 集合不一致或 evidence 使用旧 policy 时，G0A 一律保持 `blocked`。

- 首发 Story Language Kit、primary persona/JTBD、1.0 范围、非目标、假设分类和允许声明已冻结为可证伪产品假设；这不是价值已获验证，R0B 失败会使 G0A 相关声明过期并触发重开；
- ADR 依赖图无环；ProjectManifest/RunLedger/Operation/Job、RngTree、application、staging、query、dependency bundle 与 storage authority 的持久化/回放决定已 Accepted 或被 Accepted 决定明确替代；
- GateEvidence schema、owner/reviewer、容量、估算、WIP 与 timebox 已登记；
- 关键源码、CI、合同与 fixture 进入可审查版本基线，clean checkout 可复现 Rust/Python 门；
- 同 seed 语义哈希稳定、未受控 RNG 为零，旧缺陷只作为显式迁移/反例证据。

G0A 只允许进入不冻结 LanguageState v3 的 R1 平台纵切；它不证明 WS-1 领域模型正确。

### G0B：WS-1 Domain Ready

- ADR-007/008/009/010 与 Meaning/Grammar/Task/Canon/evaluator 的持久化和 replay 决定已 Accepted 或被明确替代；
- WS-1 Capability Matrix 明确 supported/planned/rejected，且一个主 profile 与一个结构非同构对照 fixture 可表达；
- Meaning 六层、equivalence/ambiguity/obligation、四类 evaluator pack、CorpusRole 与证书边界可执行；
- Linguistic Execution Contract 在 G0B 锁定 manifest schema、runner harness、adapter schema/registry、case-to-Gate 映射、当前可执行的 G0B 命令和 evidence 输出；尚未允许实现的 G2 adapter 可登记 `future`，但不计入通过能力；
- Orthography/IGT/PCU review vectors 先攻击 Proposed authority ADR；ADR Accepted 后再冻结 version/hash/reviewer 和 adapter plan，避免 ADR 接受条件与 fixture authority 循环；覆盖 normalization、未映射、同音异写、拼写冲突/歧义、禁 IPA fallback、正/负 typed-analysis round trip、非双射 IGT span、PCU integrity 及音变不静默重拼写；
- 真实小数据切片锁定精确 payload、hash、许可证、sampling unit、split 与 transform；
- Meaning Workbench 原型由目标叙事作者用真实 canon 验证；形成性研究与确认性任务分离；原型发现必须经正式 Meaning/Canon contract 编译和复核，不能单独充当 G0B 通过证据；
- Genesis TheoryProfile、ModelEvidence/ODD-TRACE 与 parameter recovery/identifiability 方案已登记。

G0B 不以 SpeechCommunity、Variation 或 ChangeProcess 为前置；这些属于 G3B。

### G1：Platform Ready

- Rust application service 是 Tauri/CLI 的唯一 use-case 边界；
- ProjectManifest、OperationSpec/RunSpec 与 append-only RunLedger 的假任务纵切可原子声明、放弃和提交；v1 LegacyHistoryBoundary migration fixture 可停止、可回滚且不伪造 provenance；
- Job 可持久化 submit/query/cancel/interrupted/restart/resume；Job/Attempt 不进入语义 hash，重复请求与 commit 幂等；
- worker lease、event journal/cursor、staging/GC 与 crash/reopen 可恢复；遗漏事件可通过 query projection 补齐；
- staging result 只能通过 `OperationId + StateTransaction + expected_history_hash` 原子提交；
- 并行项目隔离、迁移、故障注入和 crash/reopen 通过；
- versioned command/event/query/error DTO 与 capability manifest 可恢复遗漏事件；
- dependency bundle 与 ReplayCapability 能区分 Native/Legacy/ArchiveOnly，断网仍可审计；
- 项目打开、回放、内存、写入、取消和长任务恢复满足登记了测量环境/方法的预算。

### G2：Executable Language

- 多候选 Genesis、独立 evaluator、VerifiedGenesisArtifact、create/reopen 与锁过期闭环通过；
- 每个 candidate 锁定最小 Genesis TheoryProfile、数据、registry、规则、compiler 和 RNG；任一语义锁变化都会触发重验；
- typed phonology、最小名词/动词范式、Meaning/Grammar IR 和三类核心构式联合工作；
- Orthography v0、Unicode 策略、spelling analysis 和 IGT projection 与同一分析图联合工作；禁止 raw IPA fallback；
- `analyse(realize(M))` 至少包含等价读法，非法读法和 forbidden reading 被拒绝；
- G-LANG/G-CHANGE adapter 已从 `future` 切换为真实 Rust 命令并生成锁定输入/结果 evidence；仅有 fixture 或 sentinel 不算能力；
- `parse(spell(A, O), O)` 至少包含等价 typed analysis 并拒绝 forbidden analysis；对 `parse(S, O)` 返回的每个许可分析，`spell(A', O)` 只产生许可 spelling；normalization、同音异写、malformed/未映射项、precision 和拼写歧义上限通过；
- Development、CandidateSelection、SealedAudit 与 adversarial negative 任务分离；sealed pack 不参与候选排序；
- evaluator 分别报告 hard pass、under-generation、over-generation、forbidden-reading acceptance、ambiguity、gap correctness 与 construction coverage；
- 所有 WS-1 TaskCase 产生 Proof-Carrying Utterance，不能表达时返回 typed ExpressionGap；主 profile 与结构非同构对照均通过相应边界；
- 一个 feature-based structural ChangeSet 原子提交、失败回滚、回放和解释通过；
- 生成 `LanguageCapabilityCertificate`；其中 `G-LANG` 只声明可执行、可分析的微型语言，`G-CHANGE` 只声明可审计的作者结构变换；两者均不得声明真实社会传播或产品易用。

### G3：Story Language Kit / Creator Usability

- Canon-first、Onomasticon、生产性形态/词族、Meaning Workbench、Minimal InteractionContext、Scene Lab 和 Canon impact 完整；
- 名称、2–3 话轮对白、短叙事和仪式/誓言任务保留 speaker/addressee、deixis、speech act、基本照应、引语来源、register/politeness 和 context pre/postcondition，无 silent fallback；
- Structural/Authoring RulePack v1 仅对已稳定结构 effect 提供 validate/dry-run/canon impact；用户批准后事务提交，已发布 Canon 不被静默改写；
- 未参与开发的目标叙事作者不编辑 JSON/形式语义即可发现并解决一种真实歧义或义务，完成新场景、恢复错误并安全扩充语言；
- `CanonAlphaJourney.g3` 与 ReleaseClaimManifest 已预注册；确认性样本与形成性样本隔离，安全硬门和比例门在观察结果前冻结；
- 词典、语法、IGT、正字法、音节/重音、`PronunciationPlan v1` 和来源来自同一分析；R7 只增加音频渲染；
- 生成独立的 `ProductUsabilityEvidenceBundle` 与 `CreativeEvaluationRecord`，不能用 LanguageCapabilityCertificate 代替。

### G3B：WS-2 Model Contract Ready

- SpeechCommunity/lect、Variation aggregate、ChangeProcess state graph、typed UsageObservation 和 `ChangeLocus` ADR 已 Accepted；
- 稳定结构变体属于 LanguageStructureState 还是 Variation aggregate 已决定；WS-1 结构 locus 与 WS-2 社区 locus 边界无歧义；
- AuthorCanon、evaluation task、synthetic usage 与 empirical reference 明确分离，observation 标注 simulated/empirical 与 sampling process；
- long-history benchmark 与 segmented-event storage Go/No-Go 已完成；
- internal ExperimentRunner、parameter recovery、identifiability/equifinality、calibration/held-out split 和 acceptance predicates 就绪；
- surface variation/perception 能为音变和借词适应提供 typed evidence，而不是直接对底层 IPA/grapheme 串做替换。

### G4：Mechanistic Change Simulator v1 / G-SIM

- 创新、新旧变体共存、UsageObservation、传播/失败、常规化和结构提交分层；
- 同一创新至少有成功 run、失败对照和残留/逆转可表示路径；
- 只有常规化后的 ValidatedChangeSet 能修改结构，失败创新仍可审计；
- 同 seed replay、多 seed 分布、替代 TheoryProfile、parameter recovery、identifiability/equifinality、uncertainty coverage、calibration/held-out、敏感性和消融通过；
- 结果可下钻到 observation、assumption、process、effect 和 entity。

### G5：Family History

- 谱系 DAG、dialect linkage、迁徙、限时接触和借词适应可回放；
- 两个分支形成可测的规律对应，inventory、形态、构式和词义历史同步；
- 重建挑战能区分同源、借词、残留和偶然相似，并报告不确定性；
- counterfactual fork 使用稳定锁和独立 RngTree 路径，不受调度顺序影响。

### G6：Production Conlang

- 多句叙事、对白、论证、反事实、引语、多语体和一类受约束诗体通过；
- 形式约束不能以非法词形、意义丢失或无来源随机古语达成；
- 外部作者任务、language relay、Canon 回归和无障碍核心任务达到预注册阈值；
- 高级篇章能力可在 G3 后以单语言 lane 先行；家族史集成、盲重建审计与完整 Language Bible 等待 G5；
- Language Bible、词典、语法、IGT、名字册、历史、证据和限制来自同一版本状态。

### G7：Core Expert Release

- Expert Audit Package、ModelEvidenceBundle、数据/规则/模型锁和许可证清单完整；
- 外部盲评没有严重结构错误，已知争议、失败、适用域和非目标公开；
- clean machine 安装、旧项目迁移、备份恢复、取消/崩溃和跨平台支持通过；
- Core Release 不依赖 neural voice、LLM 或 plugin；Speech、Research、LLM/Extension 各有自己的能力声明和发布门；
- 语音仅在 deterministic pronunciation/render plan 成立后发布；LLM/TTS/插件结果不写权威状态；
- 发布声明逐项映射到已通过的 TaskPack、Gate 和证据工件。

G0B、G2、G3B、G4、G5 和 G7 各进行一次相应专业角色的阶段外部评审。发现阻断性抽象错误时允许回到前一 Gate 大规模重构，不以已投入代码量为继续执行理由。

## 11. 风险与控制

| 风险 | 控制 |
|---|---|
| 范围过大 | 每阶段由质量门限制，不并行铺开全部功能 |
| 规则数量掩盖模型缺陷 | G0B–G2 前冻结大规模规则扩充；R3 authoring rules 与 R4 process rules 分代 |
| 经验数据被当作因果 | priors、hypotheses、preferences 分层 |
| 插件执行任意代码 | 普通插件仅声明式，WASM 后置且沙箱化 |
| UI 复制不稳定 API | EngineTransport 和 schema 先版本化 |
| 文学规模导致词汇爆炸 | 使用 lexeme family、sense、coverage 和需求队列 |
| LLM 污染符号真值 | LLM 只提议和解析，事务验证器最终裁决 |
| TTS 掩盖错误发音 | R3 确定性 PronunciationPlan 先于 R7 音频渲染与神经语音 |
| Canon/语料自证模型 | CorpusRole、sampling/split lock、sealed evaluator 与 held-out validation 隔离 |
| 参数不可辨识却宣称机制 | parameter recovery、equifinality、替代模型与 uncertainty coverage 作为 G4 前置证据 |
| Rust 重构失控 | 领域纵切、迁移 manifest、限时双轨和 stop/go gate |
| 机械翻译旧缺陷 | 以目标不变量和缺陷清单裁决，不以逐输出相等为唯一目标 |
| Python/Rust 双核心长期共存 | Rust 成为权威后停止生产双写，Python 只留研究边界 |
| 性能优化过早 | Rust 方向已确定，但局部优化仍由 profiling 和预算触发 |

## 12. 计划维护

本文不得独立改变工作包 ID、R2A–R2F 映射、当前状态或执行顺序。任何 canonical
WBS 变化先修改 `PRODUCT_DEVELOPMENT_PLAN.md`，并在同一变更中更新本文镜像。
`scripts/docs_check.py` 必须检查 R2 镜像、G0A policy requirement 集合、ADR 状态和
capability/release claim 的一致性；动态 Gate 状态、测试数量、subject hash 和运行
环境不得手写复制到本文。

每个工作包进入开发前必须补充：

- owner；
- reviewer 及所需专业角色；
- effort range、容量假设、WIP limit 与 timebox；
- 输入和输出 schema；
- 依赖；
- 不变量；
- 测试与黄金场景；
- 数据迁移影响；
- 性能预算；
- 文档更新位置；
- GateEvidence 类型、证据路径、阈值、允许声明与过期条件。

完成后记录提交或 PR、测试数量、语义哈希变化、迁移结果和已知限制。任何改变核心模拟理论、持久化身份或 replay 语义的决定必须先新增或替代 ADR；没有 owner、容量、证据责任与降范围规则的工作包不得进入 Ready。
