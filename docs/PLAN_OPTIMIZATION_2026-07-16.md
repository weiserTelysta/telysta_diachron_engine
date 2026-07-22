# Telysta 计划优化记录

- 状态：`Planning change record merged into the three authoritative plans / no persisted-schema decision`
- 日期：2026-07-16
- 依据：[路线严格评审](./RESEARCH_ROUTE_REVIEW_2026-07-14.md)、2026-07-15 工程/语言学/产品联合复审
- 影响范围：[项目路线图](./ROADMAP.md)、[专业语言模拟器实施总计划](./LANGUAGE_SIMULATOR_PLAN.md)、[产品开发执行计划](./PRODUCT_DEVELOPMENT_PLAN.md)

本文记录执行顺序和证据门的修订，不替代 Accepted ADR。涉及项目身份、Run/Event 归属、LanguageState v3、ChangeSet locus、聚合边界、回放或插件执行的条目仍必须先由 ADR 决定。

本文是 2026-07-16 的历史计划优化记录，不是当前执行 WBS 或 Gate 状态源。工作包
ID、依赖、R2A–R2F 映射、Stop/Go 和当前队列以
[产品开发执行计划](./PRODUCT_DEVELOPMENT_PLAN.md)为唯一 canonical WBS；Gate
requirement 与 decision 分别以版本化 policy 和 GateEvidence 为机器事实。若本文的
历史顺序与当前执行计划不同，不得据本文启动实现。

## 1. 结论

项目继续采用 `Conditional Go + Domain Implementation Hold`：Rust 单一权威、Tauri 薄客户端、确定性 RngTree、事务回放、typed IR、独立 evaluator、Canon impact 和 ODD/TRACE 方向保留；原计划不得按单一 G0 串行执行。这里的 Hold 只冻结尚未由 Accepted ADR 和对应 Gate 放行的持久化领域语义，不冻结文档、fixture、数据锁、UX 原型、研究实验，也不冻结 G0A 关闭后的 R1 平台 walking skeleton。

当前首先要证明两个不同问题：

1. 平台能否安全承载未来任务，而不提前冻结语言学模型；
2. WS-1 的语言、语义、任务和作者闭环是否具备足够明确的领域合同。

SpeechCommunity、PopulationVariation 和真实传播模型属于第三个、更晚的决策门，不能阻塞 application/Job 平台，也不能在其 ADR 接受前进入生产 schema。

## 2. 产品切入口

首发价值切入口固定为：

> 面向严肃世界观作者的 Canon-safe、可审计 Story Language Kit。

R2 先证明一个可执行微型语言，R3 证明作者可以持续使用和扩充。语言变化模拟器是 R4 的第二能力层；语言家族是 R5 的第三能力层。最终愿景仍是可审计的语言历史模拟器，但不得用远期家族目标替代早期产品价值验证。

R0B 产品研究必须使用目标作者自己的姓名、台词和场景，比较其现有表格、Wiki、词典/音变工具工作流，并定义转向条件。完成团队提供的固定任务只能证明操作可行，不能证明产品价值。

## 3. 修订后的决策门

```text
R0A planning repair + repository baseline
        ↓
G0A Platform Contract Ready
        ↓
R1 application / JobStore / API / staging / query / benchmark
        ↓
G1 Platform Ready

R0B WS-1 domain evidence ───────────────────────────────┐
        ↓                                                │
G0B WS-1 Domain Ready                                    │
        └────────────────────────────────────────────────┘
                         ↓
R2A–R2F executable-language vertical slice
                         ↓
G2 Executable Language
                         ↓
R3 Story Language Kit + continuous product validation
                         ↓
G3 Creator Capability

R3B WS-2 model decision + storage/experiment readiness
        ↓
G3B WS-2 Model Ready
        ↓
R4 Mechanistic Change Simulator v1
        ↓
R5 Family / Contact / Blind Reconstruction

R3 后可并行：single-language discourse/literary track
R5 后集成：family-history literary track
R7 core：release hardening
R7 optional trains：speech / neural voice / LLM / extension preview
```

### G0A：Platform Contract Ready

本节只保留 Gate 设计理由，不维护当前 required requirement 集合或状态；当前集合、
接受谓词和 decision 以版本化 policy、canonical WBS 和 GateEvidence 为准。

只包含进入 R1 所需条件：

- 当前 Rust/Tauri/CI/合同/fixture 进入 clean-checkout 基线；
- Project、Operation/Run、Job、事件归属、staging 与 authoritative/derived storage 中影响持久化身份、回放和权威写入的决定已 Accepted；
- application 依赖方向、versioned request/query/error/event、Job journal/cursor 和权限边界可评审；
- RNG 与既有历史兼容策略明确；
- 产品首发切入口作为可证伪假设、允许声明和平台支持范围明确；R0B 产品证据失败会触发 G0A 相关声明重验，而不是把首发 wedge 当成已经验证的市场事实。

### G0B：WS-1 Domain Ready

只包含进入正式 WS-1 schema/实现所需条件：

- Registry、LanguageState v3、Meaning/Grammar、GenesisArtifact、TaskPack、Canon 和 evaluator 边界无阻断未决项；
- WS-1 支持/计划/拒绝能力矩阵冻结；
- 两个结构上非同构的对照轮廓能够由同一 IR 表达；
- 数据 execution slice、四类 TaskPack、缺陷注入、Canon fixture 和 Meaning Workbench 原型可复现；
- 所有影响持久化身份、回放或创建信任边界的 ADR 已 Accepted。

### G3B：WS-2 Model Ready

只包含真实传播实现的前置条件：

- SpeechCommunity、lect、Variation aggregate、UsageObservation 和 ChangeProcess 的身份/hash/replay ADR 已 Accepted；
- ChangeProcess 使用 process graph，而不是唯一线性阶段；
- AuthorCanon、TaskFixture、SyntheticUsage 和 ExternalEmpiricalObservation 不可互换；
- headless ExperimentRunner、参数恢复/可辨识性协议和存储规模决策已就绪；
- 模型声明、适用域、失败模式和 ODD/TRACE 证据模板已锁定。

## 4. 必须显式解决的 ADR 决策

R0A/R0B 不预先给出下列持久化答案，但必须为其建立独立决策记录，不能继续隐含在工作包描述中：

1. `ProjectManifest / RunLedger / OperationId / RunId / JobId / AttemptId` 的身份与迁移；Authoring/Retcon 由 OperationKind 和 provenance 表达；
2. ChangeSet 的 typed locus：WS-1 结构 lect 与 WS-2 community-conditioned locus；
3. Meaning/Grammar/Task certification 的权威边界；
4. TheoryProfile、ModelEvidence、参数、校准与验证工件；
5. LanguageStructure、Variation、UsageCorpus、Canon、Job 和派生索引的聚合/回放边界；
6. 离线重验所需 registry/rule/data/TaskPack/evaluator payload 保存和 `ReplayCapability`。

ADR-005 还必须把“架构边界可接受”与“经验模型已获得验证”分开。Spike 可以证明表示与实现可行，不能证明某个社会语言学机制真实。

## 5. 语言与科学验证修订

### 5.1 Meaning 分层

```text
SceneFacts
→ InteractionContext
→ CommunicativeIntent
→ PropositionGraph
→ LanguageSpecificObligations
→ Grammar Realization

PragmaticCommitments 作为可追踪并行层
```

每层分别定义 equivalence、允许歧义、scope/commitment 和 typed gap。`ComparativeConcept ↔ LanguageInternalCategory ↔ Lexeme/ConstructionMeaning` 只作为带 provenance 的跨语言词汇/范畴对齐，不是整个 Task meaning pipeline；比较概念不得直接成为所有候选语言的时体、格、词类或语义真值。

### 5.2 分阶段语义与话语能力

- G2：事件、角色、指称、否定、最小量化/辖域、时体和疑问；
- G3：指示、基本照应、言语行为、共同知识、信息结构和 register；
- G6：模态/反事实、预设、嵌套引语、跨句时间、篇章关系和 viewpoint。

未实现能力必须返回 typed gap。TaskCase 文案不能伪装成已经实现的语义表示。

### 5.3 Evaluator 与任务隔离

```text
DevelopmentPack
CandidateSelectionPack
SealedAuditPack
ExternalElicitationPack
```

最终 evaluator 同时检查 coverage、negative precision、semantic false acceptance、歧义分布和未覆盖规则。任何被开发者查看并用于调试的 sealed pack 立即失去 held-out 身份。

### 5.4 模型证据

G4 前除 replay、multi-seed、sensitivity 和 ablation 外，还必须有：

- synthetic parameter recovery；
- identifiability/equifinality 检查；
- observation model 与校准目标；
- calibration/validation 数据隔离；
- uncertainty coverage 或明确的不可识别报告；
- 替代 TheoryProfile 与无该机制对照。

S 曲线只能作为可比较的输出模式，不能充当传播原因。

## 6. 产品与 UX 证据修订

`LanguageCapabilityCertificate` 与 `ProductUsabilityEvidence` 分开：

- 前者锁定语言 revision、lect、Grammar、TaskPack、Canon、evaluator、数据/模型和限制；
- 后者锁定用户群、真实任务、使用情境、UI build、平台/辅助技术、成功率、误完成、耗时、恢复、信心和满意度。

R0B 原型和 WS-1 必须提供 `Meaning Workbench v0`：作者可以用场景模板和 obligation 卡片确认角色、时体、指称、语气与目标语言强制信息；自然语言或 LLM 只产生提案，typed Meaning 才是权威输入。

人本研究不是 R0B 后永久冻结。每个 R 阶段至少有一次形成性研究，Gate 前有一次预注册 benchmark；无障碍参与者从 R0B 开始进入关键任务。

## 7. 工程顺序修订

- R1 在 ADR-011 Accepted 后先建立 Project/Operation/Run ledger shell，再将 Persistent Job 拆为 JobStore、worker lease、event journal/cursor、result staging/GC 和 restart/resume contract；
- R1 增加 query projection、dependency bundle/replay capability 和通用 headless ExperimentRunner；
- 当前 canonical R2 顺序为 `R2A in-memory typed language`
  → `R2B candidate compiler / independent evaluator`
  → `R2C typed ChangeSet / atomic reducer`
  → `R2D append-only history / seal / create / reopen / ReplayCapability`
  → `R2E Meaning Workbench / authoring round trip`
  → `R2F Tauri vertical slice`；本记录原先把 seal/create 提前到
  ChangeSet/history 之前，该顺序已被当前执行计划修正；
- R3 增加最小 InteractionContext/Discourse 和 corpus source typing；R3 RulePack 的直接应用标为 authorial structural transform，不宣称社会传播；
- R4 前完成 storage scale decision；R5 的 storage 工作只作复验；
- R3 交付 deterministic PronunciationPlan v1；最小 surface variation 与 production/perception mapping 在 R3B 完成，先于 R4/R5 音位化和借词；R7 只增加 SpeechRenderPlan/TTS；
- R5 的重建挑战只向 reconstructor 暴露后代观测，ground truth 由独立 scorer 保管；
- R6 单语言篇章/文学能力不再被 R5 家族工程整体阻塞；只有家族文学集成依赖 R5；
- release hardening 不依赖神经语音、LLM 或插件预览。

## 8. Gate 证据与交付可行性

每个 Gate 生成版本化 `GateEvidenceManifest`：

```text
gate/schema version
claims and non-claims
fixture / TaskPack / data / model hashes
environment and support matrix
metrics and pass/fail predicates
reviewers and independence
severity rubric and adjudication
waivers and expiry
results, known failures and next blocker
```

Gate 通过必须能由该 manifest 重演和复核，不能只依赖会议结论。

只对当前 rolling wave（R0A、R0B、R1、R2）做交付估算。工作包进入 Ready 前必须具备 owner、reviewer、S/M/L 或三点估算、实际专业容量、WIP 上限、timebox 和超限降范围规则。R3–R7 只保留范围级估算，避免在研究不确定性尚未降低时制造虚假日期。

## 9. 当前允许与停止项

现在允许：

- repository baseline、合同/ADR 修订、fixture、数据锁、Meaning/Task/Canon 反例；
- Product Evidence、Meaning Workbench 和不可提交正式状态的 UX prototype；
- application/Job/query/experiment 的假确定性任务设计与合同测试；
- 不写生产状态的 Python 数据/模型实验。

继续停止：

- LanguageState v3、RunLedger 和 ChangeSet 的正式持久化实现，直到对应 ADR Accepted；
- SpeechCommunity/Variation 正式 schema；
- 大批生产规则、全量数据导入、正式 UI 视觉精修；
- 神经 TTS、权威 LLM、任意代码插件；
- 未经迁移矩阵和等价任务验证的 legacy 删除。

## 10. 下一次实现入口

以下是 2026-07-16 时点的历史建议，不表示当前工作包已经 Ready。当前 Next 必须由
canonical WBS、GateEvidence 和 owner/capacity 记录联合决定。

1. 关闭 G0A，进入 R1 平台 walking skeleton；
2. 并行完成 G0B 的 WS-1 领域证据；
3. G1 与 G0B 均关闭后，按 R2A–R2F 逐门实施；
4. 不等待 R4/R5 的社会传播和家族模型来验证 R1/R2；
5. 不允许 R1/R2 的结构变换被产品文案描述为真实语言传播。
