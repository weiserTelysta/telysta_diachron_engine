---
document_type: product-plan
decision_status: not-applicable
implementation_status: in-progress
normative_scope: current
last_verified: 2026-07-18
owner: unassigned
reviewers: []
---

# Telysta 产品开发执行计划

- 状态：`Active planning baseline / Domain Implementation Hold`
- 最近修订：2026-07-18
- 适用范围：产品定义、Rust 核心、Tauri 工作台、语言生成、历时模拟、验证、数据、迁移与发布
- 当前阶段：`R0A 计划/决策修复 + R0B WS-1 领域证据`
- 当前阻断：G0A 为 `blocked`；R0B evidence preparation 正在进行，但具体工作包在 owner/reviewer/capacity 分配前仍为 `Planned`，G0B=`not evaluated` 且没有通过性 GateEvidence；当前仓库未形成 clean-checkout 基线；ADR-007～014 均未完成所需接受流程，ADR-014 已形成 Proposed 草案但 owner/reviewer 未分配；Project/Operation/Run/Job、Meaning/Grammar/Lexical Class/Realization、TheoryProfile、ChangeSet locus、聚合与 replay 边界尚未闭合。ADR-005 是分阶段研究背景，不是 WS-1 前置

本文把 [项目路线图](./ROADMAP.md)、[专业语言模拟器实施总计划](./LANGUAGE_SIMULATOR_PLAN.md)、[路线严格评审](./RESEARCH_ROUTE_REVIEW_2026-07-14.md) 与 [计划优化记录](./PLAN_OPTIMIZATION_2026-07-16.md) 转换为可执行的关键路径和工作包。[审计修正执行计划](./AUDIT_CORRECTION_PLAN_2026-07-18.md)把 2026-07-18 的语言学/架构缺陷映射回本文工作包、Gate 与验收证据，不形成第二套 WBS。它们都不替代 Accepted ADR，也不直接决定持久化实体身份、事件回放或插件边界。

权威边界按职责解释：仓库 `AGENTS.md`、Accepted ADR 与已接受领域合同决定不可变语义；本文决定当前执行顺序、WBS 与 Stop/Go；`ROADMAP.md` 汇总阶段状态和 Next；`LANGUAGE_SIMULATOR_PLAN.md` 维护长期能力地图。三份主计划若不一致，先停止相关工作并同步修订，不选择对实现最方便的一份。若本文建议会改变持久化实体意义、回放语义、权威写入者或插件执行边界，必须先新增或修订 ADR。

## 1. 产品北极星

Telysta 不以“一键生成 Tolkien 级语言”为可验证承诺。产品目标是：

> 帮助严肃世界观创作者从世界设定或已有名字、词语和台词出发，编译一个可表达、可分析、可演化、可追溯的语言系统；作者能够持续扩充它，而不破坏已经发表的 canon。

首发价值切入口固定为 **Canon-safe、可审计的 Story Language Kit**：R2 证明一个可执行微型语言，R3 证明真实作者能够持续使用和扩充。R4 的机制性变化模拟与 R5 的语言家族是后续价值层，不能替代 R0–R3 的产品价值验证。

代码负责：

- 结构一致性、确定性、回放、迁移与影响分析；
- 音系、形态、构式、意义和正字法的联合实现；
- 多候选编译、任务验证、历时推演与来源解释；
- 暴露表达缺口、冲突、歧义、模型限制和证据范围。

作者负责：

- 审美方向、文化意义、叙事目的和文学判断；
- 候选选择、canon、允许的歧义和显式创作破格；
- 对模型提案、LLM 提案和历史候选作最终决定。

### 1.1 两种创作入口

两个入口必须编译到同一 `LanguageBlueprint`、命令和权威状态，不能形成双 schema：

1. **Language-first**：从交际、结构与审美目标生成语言，让语言反向启发世界；
2. **Canon-first**：导入已有姓名、称号、词语、拼写和台词，把它们作为可解释约束，生成若干兼容方案。

世界设定只产生交际、词汇、语体、命名和接触需求。气候、种族、性格或审美标签不得直接作为音系和语法的因果律。

### 1.2 1.0 完成定义

1.0 不是“支持所有人类语言结构”，而是一个能力边界公开、以口语型架空语言为首版范围的 Production Conlang 工作台。手语和多模态语言在引入 modality abstraction 前属于公开非目标。它至少应能：

- 生成并封存一个内部一致的祖语和可追溯的后继语言；
- 处理名字、短对话、叙事段落、引语、条件/反事实、仪式文本和一类受约束诗体；
- 用同一分析产生文本、形态切分、IGT、音位/语音计划和来源解释；
- 从现代形式回溯祖形、规则、类推、借词、社群过程和作者干预；
- 对既有 `CanonCorpus` 执行影响分析，禁止规则变化静默破坏已发表形式；
- 在不能表达目标意义时返回 typed `ExpressionGap`，不得临时随机造词或丢失意义；
- 导出 Language Bible：发音、语法、词典、名字册、历史、IGT 语料、使用证明和已知限制；
- 由未参与开发的创作者完成新场景和命名任务，并通过外部语言学审计。

神经 TTS、任意代码插件、完整自动文学翻译、个体级大规模 agent simulation 与“普适自然度”均不是 1.0 硬门。

## 2. 产品声明阶梯

任何阶段只能使用已经被证据支持的声明：

| 阶段 | 允许声明 | 禁止声明 |
|---|---|---|
| R0–R1 | 已建立合同、平台和可复现地基 | 已生成语言、已模拟变化 |
| R2 / WS-1 | 可生成、分析和审计一个可执行微型语言；可回放一次结构变换 | 已模拟真实传播；已达到完整创作语言 |
| R3 | 可用于规定的命名、对白与短场景；可安全持续扩充 | 可翻译任意文学文本 |
| R4 / WS-2 | 已具备 Mechanistic Change Simulator v1：创新—变体—传播—常规化闭环 | 模型代表唯一真实语言变化机制 |
| R5 | 可生成受支持的分支、接触层和规律对应 | 支持所有历史过程或全部类型学 |
| R6 | 通过版本化文学任务与外部创作者验证 | 自动达到 Tolkien 的艺术成就 |
| R7 | 在公开适用域内提供语音、研究与发布能力 | TTS 或 LLM 输出证明语言学正确 |

测试通过证明实现满足对应测试，不自动证明自然性、历史真实性或文学质量。

## 3. 关键路径与并行边界

### 3.1 关键路径

```text
R0A 计划/ADR/仓库修复 → G0A Platform Contract Ready
→ R1 application / JobStore / API / staging / query / benchmark → G1

R0B WS-1 domain evidence → G0B WS-1 Domain Ready
G1 + G0B
→ R2A–R2F executable-language vertical slice → G2
→ R3 Story Language Kit + continuous product validation → G3

R3B WS-2 model decision + experiment/storage readiness → G3B
→ R4 Mechanistic Change Simulator v1 → G4
→ R5 family/contact/blind reconstruction → G5

R3 后可并行 single-language discourse/literary track；R5 后集成 family history
→ R6 Production Conlang → G6
→ R7 core release hardening；speech/LLM/plugin 作为独立可选发布列车
```

### 3.2 可以并行的工作

- R0A repository/ADR/platform contract 与 R0B TaskPack/反例/数据锁/低保真 UX 可并行；
- G0A 关闭后，R1 application/job 外壳可以使用假的确定性任务验证，不等待 G0B 或 v3 语言实现；
- UI 信息架构和任务测试可使用不可提交权威状态的 prototype；
- Python 可以进行模型研究和数据转换，但不能写正式项目；
- evaluator 的 fixture 与缺陷注入测试可以先于生成器实现。

### 3.3 不得并行铺开的工作

- ADR 未接受前，不实现 v3 持久化意义、正式 reducer 或创建入口；
- Grammar/Change IR 未稳定前，不开放 RulePack SDK；
- 可执行语言未通过 WS-1 前，不扩展大批历时规则；
- 生产性共时语言未通过 R3 前，不扩大家族、接触和个体模拟；
- deterministic PronunciationPlan 未正确前，不加入语音渲染或神经 TTS；
- 正式 API 未稳定前，不大规模精修 Webview。

## 4. 目标执行架构

近期不进行技术栈翻转。Rust 是唯一生产权威；Python 是研究桥；Tauri 是薄客户端。

```text
Tauri / future CLI
        ↓ versioned request/query DTO
telysta-application
├── ProjectService
├── GenesisService
├── AuthoringService
├── SimulationService
├── EvaluationService
├── ExportService
└── JobManager
        ↓
telysta-core + telysta-storage
        ↓
later, only after stable boundaries:
telysta-compiler / telysta-simulation / telysta-evaluation
```

近期只计划新增 `telysta-application`。不得为了“架构漂亮”立即拆出大量 crate；先建立 application 边界、依赖方向、版本化 DTO 和 Job 生命周期，待编译/模拟/评价接口稳定后再拆 crate。

### 4.1 四条管线

```text
immutable data payload
→ versioned transform
→ empirical PriorPack

Blueprint + TheoryProfile + RegistryBundle
→ deterministic compiler
→ CandidateSet
→ independent evaluator
→ VerifiedGenesisArtifact

LanguageState + OperationContext/RunSpec + TheoryProfile
→ Proposal / ProposedChangeSet
→ validator + reducer
→ committed history

ExperimentSpec
→ batch runner
→ calibration / sensitivity / ablation / held-out
→ ModelEvidenceBundle
```

生成器和评价器可以共享公开 Grammar/Language 查询能力及硬不变量，但 evaluator 不得调用生成器私有评分函数自我认证。

## 5. 里程碑总表

| 里程碑 | 产品结果 | 主要 Gate | 当前状态 |
|---|---|---|---|
| R0A 计划/平台合同修复 | 产品切入口、ADR 依赖、Project/Run/Job、仓库与平台证据可评审 | G0A Platform Contract Ready | In progress |
| R0B WS-1 领域证据 | Meaning/Grammar、TaskPack、Canon、数据、evaluator 与 UX 原型可评审 | G0B WS-1 Domain Ready | evidence preparation in progress；work packages Planned；G0B not evaluated |
| R1 平台收口 | application service、Project/Operation/Run ledger shell、持久化 Job、稳定 API、staging、query 与存储预算 | G1 Platform | Blocked by G0A |
| R2 / WS-1 可执行语言纵切 | 一段真实文本、一个 Genesis、一次结构变换可生成/分析/保存/解释 | G2 Executable Language | Blocked by G1 + G0B |
| R3 Story Language Kit | 语言可用于命名、对白和短场景，并可 canon-safe 扩充 | G3 Creator Usability | Blocked by R2 |
| R3B WS-2 模型就绪 | 社群/变体/观察/过程 ADR、实验与存储前置完成 | G3B WS-2 Model Ready | Blocked by R3 |
| R4 / WS-2 机制性变化 v1 | 创新、共存、传播失败、常规化和 ChangeSet 完整闭环 | G4 Mechanistic Change | Blocked by G3B |
| R5 Language Family Forge | 分支、接触、借词、规律对应和重建可用 | G5 Family History | Blocked by R4 |
| R6 Production Conlang | 单语言篇章/文学轨与家族历史集成、审计和发布包通过 | G6 Production Artlang | Single-language track after R3; integration by R5 |
| R7 Core Release + Optional Trains | 安装迁移与长期维护完成；speech/LLM/plugin 分列发布 | G7 Expert Release | Blocked by R6；可选列车不阻塞 core |

## 6. R0A / R0B：计划修复与领域证据

R0A/R0B 只允许文档、fixture、数据锁、低保真原型和不写正式状态的研究实验。R0A 关闭后可以进入不依赖 v3 的 R1 平台实现；R0B 必须在正式 WS-1 schema 和生成器实现前关闭。

| ID | 工作包 | 依赖 | 交付物 | 验收与 Go 条件 |
|---|---|---|---|---|
| R0A-01 | Product Constitution / Wedge | 路线评审 | 首发 Story Language Kit、用户类型、入口、1.0/非目标、允许声明 | 产品、架构和语言学评审无阻断歧义；家族目标不替代首发验证 |
| R0A-02 | ADR Dependency Repair | R0A-01 | 拆分 ADR-005 的架构/经验验证；评审 ADR-011 Project/Operation/Run/Job；补 Meaning/Grammar/Task、TheoryProfile/聚合决策记录 | 无循环前置；所有持久化/回放决定有唯一 ADR owner |
| R0A-03 | Platform Contract Pack | R0A-02 | [application、JobStore/journal/cursor、staging、query、dependency bundle、ReplayCapability 边界](./PLATFORM_CONTRACT_PACK_V1.md)；[ADR-012 单发布点](./adr/ADR-012-project-package-commit-authority.md) | 评审材料已就绪；ADR-011/012 Accepted 后，R1 可用假任务实现而不冻结 v3；无第二权威事实源 |
| R0A-04 | RNG Decision Record | 确定性合同 | [ADR-013](./adr/ADR-013-rng-compatibility-and-distribution-versioning.md)：保留算法、distribution 版本、known-answer、溢出与 replay 策略 | 评审材料与 Rust known-answer 已就绪；独立批准前不改变持久化；既有历史解释不变 |
| R0A-05 | G0A Repository Baseline | 当前工作树 | 审查并纳入 Rust/Tauri/CI/合同/fixture；固定 clean-checkout 证据 | Python/Rust 全门可复现；无误纳临时产物或未登记语义漂移 |
| R0A-06 | GateEvidenceManifest v2 | R0A-01/02 | subject/attestation 分离、claims、hashes、环境运行记录、阈值、reviewer、severity、waiver、结果 | 证据提交无自引用；Gate pass/fail 可 fresh-checkout 复核，不依赖会议印象 |
| R0A-07 | Rolling-wave Delivery Pack | R0A-01 | R0A/R0B/R1/R2 owner、reviewer、三点或 S/M/L 估算、容量、WIP、timebox | 无 owner/容量/降范围规则的包不得 Ready |
| R0B-01 | Meaning/Task Contract | R0A-01 | SceneFacts → InteractionContext → CommunicativeIntent → PropositionGraph → LanguageSpecificObligations → Grammar Realization，PragmaticCommitments 并行；ComparativeConcept 仅作跨语言锚点 | 各层等价、歧义、scope、commitment 与 typed gap 有 provenance；不依赖中英文或英语范畴相等 |
| R0B-01A | Meaning–Grammar–Lexical Identity–Realization Authority ADR | R0A-02、R0B-01 | ADR-014：Lexeme/Sense/WordForm/Morpheme/Paradigm/Construction 身份与所有权、ordered occurrence、双向实现、query purity、migration/hash/replay | ADR-014 Accepted，或 ADR Index 所定义的 replacement ADR Accepted；zero/syncretism/同音/多义/typed gap 的语义无歧义；不以完整状态替换掩盖效果 |
| R0B-02 | Canon/Corpus/Author Contract | R0A-01、R0B-01 | CanonSeed、AuthorCanon、TaskFixture、SyntheticUsage、ExternalEmpiricalObservation、AuthorialException | corpus 来源不可互换；作者选择不伪装经验规律；修改触发重验 |
| R0B-03 | Capability Matrix | R0A-02、R0B-01/01A | WS-1 支持/计划/拒绝的音系、形态、构式、意义、话语与历史能力 | UI/compiler 同源；两个结构非同构轮廓均可表达 |
| R0B-04 | Four-way TaskPack v1 | R0B-01/03 | Development、CandidateSelection、SealedAudit、ExternalElicitation；正/负例与缺陷注入 | 参与同轮 compiler/candidate 调参者打开 sealed pack 即失去该轮 sealed 证据资格；隔离的独立 reviewer 可按审计协议检查；required/forbidden/equivalence 可执行 |
| R0B-05 | Data Execution Slice | 数据治理合同 | 精确 DOI、payload SHA、license、sampling unit、transform 与输出 hash | payload-aware validation 和真实小切片可复现 |
| R0B-06 | Product Evidence + Meaning Workbench | R0A-01、R0B-01/02 | 真实作者工作流/替代基线；`Brief → Meaning obligations → Candidates → Scene/History → Export` 原型 | 作者用自己的 canon，不编辑 JSON/形式语义即可确认 5–10 个意图；记录转向条件 |
| R0B-07 | Scientific Model Template | 路线评审 | ODD/TRACE、ExperimentSpec、ModelEvidenceBundle、parameter recovery/identifiability 模板 | verification/calibration/validation/sensitivity/ablation/identifiability 分开 |

G0B 的 ADR 关闭顺序固定为
`ADR-008 → ADR-014 → ADR-009 → ADR-010 → ADR-007 umbrella`；各节点允许 ADR
Index 规则下的 Accepted replacement。ADR-009 的跨 Gate 前置是 ADR-011，ADR-010
的跨 Gate 前置是 ADR-011/012/013；R0B 证据准备不以完整 G0A clean-baseline 证明为
前置，但相关平台 ADR 未 Accepted 时不得接受对应领域 ADR。G0B 只有在上述决定、
R0B-01～07 验收和独立领域证据全部进入对应
GateEvidence 后才能标记为 `passed`；“evidence preparation in progress”不是 Gate 决定。

### R0A/R0B Stop 条件

- 任一新概念会改变持久化身份但没有 ADR；
- Meaning IR 仍以自由字符串或源语言句子充当权威；
- Canon、任务、审美或文化需求被塞进 LanguageState 成为第二语义来源；
- UX prototype 暴露 planned 能力如同已支持；
- 数据切片无法锁定精确 payload 与转换；
- 只有当前开发者的脏工作树能够通过验证，clean checkout 不能复现。
- ADR 接受条件依赖只有 R4/R5 才能完成的经验结果，却又被作为 R1/R2 架构前置；
- Canon/Task/simulated usage 被当作外部经验观察或 held-out 证据；
- 工作包没有 owner、容量、估算、阈值或失败后的降范围规则。

## 7. R1：平台与仓库收口

| ID | 工作包 | 依赖 | 交付物 | 验收与 Go 条件 |
|---|---|---|---|---|
| R1-01 | `telysta-application` | G0A | application-service crate 与禁止反向依赖规则 | desktop 不直接编排领域事务；core 不依赖 Tauri/async |
| R1-01A | Project/Operation/Run Ledger Shell | R1-01、Accepted ADR-011 | versioned ProjectManifest、OperationSpec/Context、RunSpec、RunLedger、v1 LegacyHistoryBoundary migration fixture | 假确定性任务可声明/运行/放弃/提交而不冻结 LanguageState v3；manifest/history/ledger 原子性可故障注入 |
| R1-02A | JobStore v1 | R1-01A、R0A-03 | versioned JobRecord/Attempt、idempotency key、input locks、状态事务 | Job 不依赖 Webview 生命周期；不进入 language semantic hash；不能藏入可删除的派生索引 |
| R1-02B | Worker Lease | R1-02A | owner、heartbeat、stale claim、cancel race、process termination recovery | 强制终止真实进程后可确定性认领或失败，不出现双 worker |
| R1-02C | Job Event Journal | R1-02A/B | 单调 sequence、`list_job_events(after)`、event retention | Tauri emit 只作通知；遗漏事件可由 cursor 补取 |
| R1-02D | Result Staging / GC | R1-02A/C | staged artifact、expected history hash、TTL/quota/GC、冲突保留 | 长任务不持有写锁；旧结果不能覆盖新历史；失败结果可审计 |
| R1-02E | Restart/Resume Contract | R1-02A–D | restartable/resumable 判定、checkpoint schema 与锁 | 未锁定 RNG cursor/输入/版本时只能 Restart，不能假 Resume |
| R1-03 | Versioned Desktop API | R1-01/02C | request/response/event/error DTO、request ID、retryability、cursor | Webview 不接收完整可写 LanguageState；contract/schema drift fixture 通过 |
| R1-04 | Staging/Commit Boundary | R1-02D | application commit use case、expected-history-hash 提交 | 只经 StateTransaction 提交；并发变更不会被旧结果覆盖 |
| R1-05 | Storage Baseline Benchmark | R0A-05 | full-history 写入、打开、回放、内存、故障注入基准 | 记录 R2 预算；`project.json` 足够与否由数据而非假设决定 |
| R1-06 | Tauri Capability Review | R1-03 | 按窗口、命令、路径的最小权限计划和 PathBroker | 引入文件导入/RulePack 前没有通用远程或写权限 |
| R1-07 | Query Projection Contract | R1-03/05 | cursor pagination、history-hash binding、rebuild/version/stale semantics | 不向 Webview 发送完整状态；派生 projection 可删除重建 |
| R1-08 | Headless Experiment Harness v0 | R1-02A–E | 锁定输入、replicate、对照、manifest、取消/重启的假任务 runner | G4 的实验能力不再依赖 R7 UI；相同 manifest 可重演 |
| R1-09 | Dependency Bundle / ReplayCapability | R0A-03、R1-05 | content-addressed registry/rule/data/TaskPack payload；Native/Legacy/ArchiveOnly | 离线重验不只依赖 URI；不支持执行时仍可只读审计 |
| R1-10 | Verification Infrastructure | R1-01–09 | dependency-direction、schema compatibility、fault injection、migration corpus、IPC E2E、benchmark protocol | G1 验收不依赖散落的手工测试 |

最小 Job 状态：

```text
Queued → Running → CancelRequested → Cancelled | Failed | Completed
crash: Running → Interrupted → Restartable | Resumable
```

只有 checkpoint 锁定全部输入、模型、数据、RNG cursor 和恢复 schema 时才显示 Resume；否则只能从锁定请求 Restart。

## 8. R2 / WS-1：可执行语言纵切

WS-1 的验收叙事固定为：**one paragraph, one history**。它证明语言结构和软件闭环，不宣称真实社会传播。

| ID | 工作包 | 依赖 | 交付物 | 验收与 Go 条件 |
|---|---|---|---|---|
| WS1-00 | Minimal Genesis TheoryProfile | G1、G0B、R0B-05/07 | Genesis 的模型/先验/参数、适用域、版本、semantic hash 与 ModelLock | 每个 candidate 锁定 profile；profile 或证据版本变化使验证过期 |
| WS1-01 | RegistryBundle + State v3 | G1、G0B、R1-01A、Accepted ADR-007/008/014 | typed FeatureValue、跨域实现要求、v3 新类型、v2 state-only checkpoint migration；不迁移或合成历史 | hostile deserialization、引用、不变量、migration、semantic hash 通过；R1 账本壳不被误当成领域历史 |
| WS1-02 | Minimal Meaning IR | R0B-01/04、WS1-01 | 六层 Meaning 的有限子集；event/roles/reference/polarity、最小 quantifier/scope、tense/aspect、question、number、possession/modification 与 pragmatic commitments | meaning 不以字符串或比较概念直接承载；等价、欠/强制区分、commitment 和 obligation 可测试；未支持项返回 typed gap |
| WS1-02A | InteractionContext + Meaning Workbench v0 | WS1-02、R0B-06 | scene template、speaker/addressee、deixis、speech act、obligation cards、ambiguity confirmation | 非专家不编辑 JSON/形式语义即可确认 5–10 个真实意图 |
| WS1-03 | Minimal Grammar IR | WS1-02 | typed slots、selection、agreement、linearization、morphology realization、parse/realize | `analyse(realize(M))` 包含等价读法；非法形式被拒绝 |
| WS1-04 | Phonology/Morphology Slice | WS1-01/03 | typed inventory/prosody/phonotactics；主轮廓的名词/动词范式、zero/syncretism；结构非同构对照 fixture | 所有表面形式可回到 segment、morpheme、slot 和 meaning；同一 IR 不只会换标签复制单一类型 |
| WS1-05 | Genesis Candidate Compiler | WS1-00/01/02/03/04、R0A-04、R0B-05 | 3–5 个 deterministic candidates、trace、locks、Pareto diagnostics | 同输入跨进程一致；无生成器私有总自然度分数 |
| WS1-06 | Independent Evaluator | R0B-04/07、WS1-03/04 | 四类 TaskPack、hard/negative probes、缺陷注入、coverage、false acceptance、ambiguity report | evaluator 检出人工缺陷和过生成；sealed audit 不参与候选选择 |
| WS1-09 | Typed Structural ChangeSet | WS1-01/04、Accepted ADR-009 | `LanguageStructure { language_id, lect_id }` locus、一条 feature-based sound rule、Proposed/Validated ChangeSet、atomic reducer | 不需要伪造 community；pre/post hash、失败回滚和 effect ordering 通过；先在内存验证 reducer，不依赖尚未建立的领域 ledger |
| WS1-01A | Language History + Ledger Integration | WS1-01/09、R1-01A、Accepted ADR-009 | Authoring/StructuralChange Operation、history node、validated ChangeSet 与 LegacyHistoryBoundary 集成；只允许 Legacy/test root | 多次 Authoring/Structural Operation 可回放；ChangeSet 引用 OperationId；不得在 seal 前构造生产 GenesisRoot；Job/Attempt 不进入语义 hash |
| WS1-07 | Genesis Trust Boundary | WS1-01A、WS1-05/06、R1-04、Accepted ADR-010 | CandidateSet、Unverified/Verified artifact、revalidation、生产 GenesisRoot materialization、seal/create/reopen | 磁盘/IPC 候选重新验证；只有 VerifiedGenesisArtifact 能原子创建生产 GenesisRoot；客户端无法伪造创建 |
| WS1-08 | Minimal Authoring Loop | WS1-02A/03/07 | scene → confirmed Meaning → utterance candidates → analysis/IGT/broad phonological form/explain → author accept | 5–10 句真实场景零随机 fallback；输出 ProofCarryingUtterance |
| WS1-10 | Tauri Vertical Slice | G1、WS1-01A、WS1-05–09 | Blueprint 表单、候选比较、create/reopen、句子检查、变化 diff、Why inspector | 不编辑 JSON 完成纵切；取消或崩溃不产生半项目 |

### R2 内部门与 WS-1 固定范围

R2 不等到最终 G2 才首次集成，按以下内部门交付可运行工件：

1. R2A：复用 R1 已验证的 RunLedger shell，完成 Registry、State、Meaning/Grammar 的 in-memory typed language；
2. R2B：candidate compiler + independent evaluator；
3. R2C：typed structural ChangeSet + atomic reducer；
4. R2D：append-only domain history + seal/create/reopen + dependency bundle/replay capability；
5. R2E：Meaning Workbench + authoring round trip；
6. R2F：Tauri vertical slice、cancel/crash/reopen 和 query projection。

- 30–50 个锁定概念只作为 fixture 容量，不是语言丰富度指标；
- 三类核心构式和七类交际 probes；
- 一个小型音系/韵律系统；
- 主轮廓的一个名词范式和一个动词范式，以及一个结构非同构的对照 fixture；
- 一个 typed 结构音变；
- 一个 CanonSeed 名字/词语集合；
- 一段短文本的正字法、音节/重音、宽式 IPA、IGT、分析与来源；WS-1 只锁定 `PhonologicalForm`，R3 交付 deterministic `PronunciationPlan v1`，R3B 增加 surface variation/perception，R7 只交付渲染级 v2。

### WS-1 Go 条件

- G0B/G1、ADR、Registry、Grammar、Genesis、evaluator、storage、Tauri 全闭环；
- 所有 hard TaskCase 通过，未支持能力返回 typed gap；
- 删除快照后可由 Genesis + ChangeSet 重建同一语义状态；
- 外部语言学评审没有阻断性表示缺口；
- 产品文案只称“可执行微型语言/可审计结构变换”。

## 9. R3：Story Language Kit

R3 先证明单语言可持续使用，再扩大真实历时和家族规模。

| ID | 工作包 | 依赖 | 交付物 | 验收与 Go 条件 |
|---|---|---|---|---|
| STORY-01 | CanonCorpus/Release | R0B-02、WS1 | CanonCommit、发布快照、影响索引、retcon/branch | 规则变化列出受影响姓名、句子、词源和诗行；不静默迁移 |
| STORY-02 | Onomasticon v1 | WS1、STORY-01 | 人名、地名、族名、王号、本名/外名/旧名及命名构式 | 名字有词素、时代、lect、命名传统、语体和词源；完整 community 关联在 WS-2 建立 |
| STORY-03 | Productive Morphology | WS1 | inflection classes、allomorphy、fusion、portmanteau、reduplication、defectiveness、derivation | 未见词根与 feature bundle 能生成/分析；缺口显式 |
| STORY-04 | Lexical Families/Senses | STORY-03 | root family、sense、colexification/derivation、collocation、register | 新概念不默认独立造根；每个扩充有任务和来源 |
| STORY-05 | Scene Lab + Minimal Discourse | R0B-04、WS1-02A、STORY-01/03/04 | 场景、deixis、基本照应/信息结构、言语行为、Meaning obligations、candidate utterances、Lexical Debt Queue | 固定对白与短叙事不靠词汇堆叠；零 silent fallback |
| STORY-05A | Corpus Source Typing | R0B-02、STORY-01/05 | AuthorCanon、TaskFixture、SyntheticUsage、ExternalEmpiricalObservation 的身份和允许用途 | Canon 只产生需求/场景，未经模型不得冒充人口频率 |
| STORY-06 | Canon-first Reconciliation | R0B-02、STORY-02/05 | 导入已有名称/台词、冲突集、兼容方案和历史解释提案 | 不自动为所有例外编造历史；用户可保留显式创作异常 |
| STORY-07 | Creative/Aesthetic Profile | WS1、STORY-05 | pairwise candidate audition、声音/节奏/文字偏好及解释 | 偏好不成为经验规律；相同语义内容用于候选比较 |
| STORY-08 | Structural RulePack v1 | WS1-09、稳定 Grammar/Change IR | 声明式 validate → conflicts → dry-run → impact → authorial structural transform → explain | 无任意代码；R3 变换不在 UI 中伪装为社群传播历史 |
| STORY-09 | Creator Workbench Alpha | R1、STORY-01–08 | Forge / Write / Inspect / Quality 核心工作流 | 目标叙事作者完成候选和短场景；expert 能追踪现代形式；中英文状态不变 |
| STORY-10 | Deterministic PronunciationPlan v1 | WS1-04、STORY-03/05 | morphology → phonology → typed allophony → utterance prosody → phones | 同一分析与锁跨进程结果一致；覆盖音段、边界、重音/声调；只承诺发音计划，不承诺音频自然性 |

R3 不要求庞大词典。完成度由 TaskPack 覆盖、生产力、意义保真、canon 稳定性和第二人使用决定。

## 10. R3B / R4：WS-2 模型就绪与机制性变化 v1

| ID | 工作包 | 依赖 | 交付物 | 验收与 Go 条件 |
|---|---|---|---|---|
| R3B-01 | WS-2 Decision Pack | G3、R0B-07 | SpeechCommunity/lect、Variation、UsageObservation、ChangeProcess、locus/aggregate/replay ADR | 架构边界与经验有效性分开；无 Proposed 决定进入生产 schema |
| R3B-02 | Storage Scale Decision | R1-05、R3 现实 fixture | full rewrite/replay/memory/UsageCorpus benchmark；必要时单独 storage ADR | 在 WS2-01 前决定是否 segmented events；snapshot/index 仍只作派生 |
| R3B-03 | Experiment Readiness | R1-08、R0B-07 | parameter recovery、identifiability/equifinality、calibration/validation split、acceptance predicates | G4 不靠人工看图或 S 曲线宣告通过 |
| R3B-04 | Surface Variation / Perception v1 | STORY-10、STORY-05 | surface distributions、production/perception mapping、phonologization candidates | 能解释音位化和借词修复；不提前实现 TTS |
| WS2-00 | SpeechCommunity / Lect v1 | G3B | 单一社区的人口、cohort/network、声望、语域、L1/L2 与 lect 关联 | 社区参数只影响 observation/propagation/need；不能直接覆盖语言结构 |
| WS2-01 | Variation Aggregate | WS2-00、Accepted ADR | `(community, lect)` 变体、条件分布、过程阶段和结果状态 | 变体不混入已常规化 LanguageState；身份/hash/replay 明确 |
| WS2-02 | UsageObservation Lock | R0B-02/07、WS2-01 | immutable typed corpus snapshot、sampling unit、observation model、frequency derivation | simulated/author/empirical 来源不可互换；统计不是第二权威状态 |
| WS2-03 | ChangeProcess Graph v1 | WS2-01/02 | 可并发/循环/停滞的 innovation、coexistence、diffusion、social indexing、reanalysis、analogy、conventionalization transitions | 成功、失败、逆转、长期稳定变体和残留均可表示；阶段不是唯一线性链 |
| WS2-04 | Diachronic TheoryProfiles | WS1-00、R0B-07、WS2-03 | 扩展基础 TheoryProfile：categorical、lexical diffusion、social diffusion 可替换模型 | 每模型有适用域、参数锁、ODD 和可关闭机制；不重新定义基础 ModelLock |
| WS2-05 | Conventionalization Commit | WS1-09、WS2-03/04 | provisional overlay、validated ChangeSet、process/event causation | 未传播创新不修改结构；常规化原子提交且可回放 |
| WS2-06 | Minimal Experiment | R3B-03、WS2-04/05 | 成功/失败、稳定变体、关闭扩散、替代模型、参数恢复与相同随机流比较 | 同 seed 可复现；关键参数可恢复或明确不可辨识；不以 S 曲线充当原因 |
| WS2-07 | History UI | R1、WS2-01–06 | process timeline、variant view、cancel/restart、Why/Why-not | UI 区分 observation、inference、simulation 和 user intervention |

只有 WS2-06 通过后，产品才可称“Mechanistic Change Simulator v1”；它仍不代表唯一真实变化机制。

## 11. R5：Language Family Forge

| ID | 工作包 | 依赖 | 交付物 | 验收与 Go 条件 |
|---|---|---|---|---|
| R5-FAM-01 | Community/Lect Mapping | WS2、ADR | 多社区—多 lect 映射、迁徙、隔离、使用领域 | 不把 community IDs 永久嵌入单个 LanguageState 身份 |
| R5-FAM-02 | Genealogy + Contact Graph | R5-FAM-01 | genealogy DAG、dialect linkage、time-bounded contact edges | 继承与接触来源分开，跨树创新可表达 |
| R5-FAM-03 | Sound/Inventory History | STORY-10、R3B-04、WS2、R5-FAM-02 | merger、split、phonemicization、allophony、ordered change | inventory、词形、异音和对应联合更新 |
| R5-FAM-04A | Analogy / Paradigm Repair | R3、WS2 | leveling、extension、irregularization、residual classes | 每过程引用范式、使用与证据；可独立消融 |
| R5-FAM-04B | Grammar / Construction Change | R3、WS2 | bridging contexts、constructionalization、grammaticalization、reanalysis | source construction、共存、扩展和残留可回放 |
| R5-FAM-04C | Semantic Change | R3、WS2 | polysemy、semantic map、metaphor/metonymy、narrowing/broadening | 新旧义和使用域共存；不随机翻转 typology flag |
| R5-FAM-05 | Contact Transfer | R5-FAM-02/03/04 | lexical borrowing、calque、structural diffusion、agentivity、perception/repair、register/adoption | transfer type 明确；借词不当同源词，结构接触不复用字符串复制语义 |
| R5-FAM-06 | Blind Correspondence/Reconstruction | R5-FAM-03–05 | 后代观测包、隐藏 truth、cognate/correspondence/loan challenge、独立 scorer | reconstructor 看不到 ledger/祖语/标签；报告多解和校准不确定性 |
| R5-FAM-07 | Counterfactual Fork | R1、R5-FAM-01–06 | 从锁定历史点比较不同迁徙、接触或模型 | 分支有稳定 ID/locks；比较不受调度顺序 RNG 影响 |
| R5-FAM-08 | Storage Scale Recheck | R3B-02、现实长历史 fixture | family/contact 长历史复验与预算回归 | 只复验既定架构；不把首次 storage 决策拖到风险发生后 |

## 12. R6：Production Conlang 与文学工作台

| ID | 工作包 | 依赖 | 交付物 | 验收与 Go 条件 |
|---|---|---|---|---|
| LIT-01 | Advanced Discourse IR | R3 | quantification/scope、modality/counterfactual、presupposition、long-range reference、complex information structure、nested quotation、ellipsis、viewpoint、register | 多句人物、时间、承诺和话语来源不丢失；在 R3 最小话语能力上扩展；单语言轨不等待家族工程 |
| LIT-01F | Family-history Literary Integration | LIT-01、R5 | 多时期/lect 文本、archaism、contact/register history | 文学形式引用真实 family/contact history，不阻塞单语言 LIT-01 |
| LIT-02 | Literary TaskPack | LIT-01 | 叙事、对白、演说、祷祈/誓言、诗歌、史诗片段 fixture | required meaning、允许省略、禁止读法和人工评审分开 |
| LIT-03 | LiteraryTradition | STORY-02/07、LIT-01 | meter、rhyme、alliteration、parallelism、formulae、archaism | 形式约束不能用非法词形或意义丢失凑齐 |
| LIT-04 | Adversarial Quality Lab | R0B-07、R3–R5 | gap、歧义、范式、同音、来源、历史和任务失败诊断 | 所有指标可下钻；不输出单一自然度分数 |
| LIT-05 | Language Relay Test | LIT-01–04 | 外部用户只凭导出语法/词典分析新文本 | 第二人能解释预期事件并发现真实歧义 |
| LIT-06 | Creator Validation | LIT-01–04 | 独立作者新写场景、10 个名字和修订诗句 | 不需要编辑 JSON 或临时绕过规则；记录任务成功与认知负担 |
| LIT-07 | Expert Audit | LIT-04/05/06 | 预注册 scope、severity rubric、跨专长 reviewer、盲审/裁决、grammar/dictionary/IGT/event/data/model locks | 支持域内无阻断错误；分歧、一致性和异议公开，不外推为普适自然性 |
| LIT-08 | Publish/Language Bible | LIT-01–07 | 版本化参考语法、词典、名字册、历史、corpus、LanguageCapability/ProductUsability/Creative/Expert 证据索引 | 所有导出来自同一状态和分析；重新导出稳定 |

## 13. R7：Core Release 与可选发布列车

| ID | 工作包 | 依赖 | 交付物 | 验收与 Go 条件 |
|---|---|---|---|---|
| R7-SPH-01 | SpeechRenderPlan / PhoneticPlan v2 | G6、STORY-10、R3B-04 | tempo、coarticulation、actor guidance、音频/TTS 映射 | 在 v1 上提升表现精度；不首次定义音变机制或反向改变 LanguageState |
| R7-SPH-02 | Actor Pack | R7-SPH-01、G6 | 音节、重音、慢/常速、最小对立、台词指导 | 人类表演者可按文档复现；音频不掩盖缺失音 |
| R7-SPH-03 | Deterministic Speech Preview | R7-SPH-01 | 可重复的本地发音预览 | 明确标为 pronunciation aid，不宣称自然人声真值 |
| R7-SPH-04 | Optional Neural Voice | R7-SPH-01–03 | 版本化外部模型结果与限制 | 不参与语言正确性；模型、输入、许可和结果锁定 |
| R7-RES-01 | Research UI / Scale-up | R1-08、R4/R5 | 参数扫描 UI、队列管理、大规模 replicates、发布级 evidence bundle | 复用既有 headless runner；不成为 G4 前置能力的首次实现 |
| R7-LLM-01 | Proposal Escrow | 稳定 Meaning/Rule IR | LLM 只提议 scene/meaning/rule/explanation | schema/domain/impact/user confirmation 后才能 commit |
| R7-EXT-01 | Plugin Boundary ADR | 稳定 RulePack、明确需求 | WASM/WIT capability、资源限制、provenance | 未有 ADR 和沙箱验证前不执行第三方代码 |
| R7-REL-01 | Core Release Hardening | G6、R1-09、必需发布工件 | installer、migration、backup/recovery、license、support matrix、diagnostic export | clean machine、旧项目、取消/崩溃、无障碍和升级测试通过；不依赖 neural voice、LLM 或 plugin preview |

`R7-SPH-*`、`R7-LLM-01`、`R7-EXT-01` 分别属于 Speech Pack、Proposal Assistant 和 Extension Preview 发布列车。除发布承诺明确包含某列车外，它们不得阻塞 1.0 core authoring release。

## 14. LanguageCapabilityCertificate、产品证据与任务阶梯

以下数量是初始工程预算，不是语言学普遍定律；pilot 后可以调整，但语义硬门不能降格为软分数。

| 等级 | 证明内容 | 初始验收预算 |
|---|---|---|
| LC0 语义合同 | Scene/Interaction/Intent/Proposition/Obligation、等价、歧义、canon 规则 | 所有合同和反例已冻结 |
| LC1 可执行微型语言 | 最小语义对立、未见组合、IGT、音系和回析 | 30 个核心 TaskCase + 10 个 sealed 组合，hard requirement 100% |
| LC2 生产性核心 | 多领域表达、新词根范式、派生和构式组合 | 版本化任务集；至少 30% 组合不参与生成器调试 |
| LC3 场景与文化 | 叙事、对话、指令、谈判、仪式、三种语体、名字系统 | 固定短场景、InteractionContext 和 CanonCorpus 回归通过 |
| LC4 历史语言 | 祖语、两个分支、接触、三个时期文本、盲重建 | 对应/借词/旧文分析、hidden-truth scorer 和来源通过 |
| LC5 文学语言 | 叙事、演说、祷誓、诗歌、史诗片段 | 意义、文体和形式分别验证；人工审美单独评议 |
| LC6 创作者发布 | 独立作者和读者能使用与审计 | 新场景、新名字、诗句修订、relay 与专家任务通过 |

`LanguageCapabilityCertificate` 必须锁定：language/revision、era、lect、Meaning/Grammar、TaskPack role、CanonCorpus、evaluator、数据/模型、支持能力、typed gaps 和已知限制。任何影响这些语义的变更都会使证书过期并触发重新验证。

`ProductUsabilityEvidence` 独立锁定 app build、平台/locale、辅助技术、persona、招募条件、任务、完成率、误完成、耗时、求助、恢复、信心、满意度和研究限制。`CreativeEvaluationRecord` 单独保存作者/读者的审美与文学判断。三类证据不得互相替代，也不得压缩成一个自然度或可用性总分。

### 14.1 TaskCase 最小结构

```text
scene facts
speaker / addressee / social context
deictic anchor / common ground / discourse referents
speech act / interaction goal
required propositions and distinctions
quantification / scope / temporal-modal relations
asserted / presupposed / implicated / accommodated commitments
optional nuances
forbidden readings / contrastive foils
discourse precondition / postcondition
register / genre
equivalence policy
```

### 14.2 ProofCarryingUtterance

正式输出至少携带：意义与意图、构式推导、词素切分/gloss、音系与正字法、语体/体裁、允许歧义、时代/方言、历史来源和 provenance。无法结清结构账或意义账的输出不能进入 CanonCorpus。

## 15. 验证矩阵

| 风险 | 必需验证 |
|---|---|
| 非法状态进入权威路径 | constructor、hostile deserialization、schema/domain invariant |
| 随机漂移 | RngTree path isolation、known-answer、跨进程、多线程稳定归并 |
| reducer 部分提交 | property tests、effect ordering、rollback、pre/post hash |
| 回放失真 | 删除 snapshot 后 Genesis + events 深度重建 |
| 迁移伪造历史 | v2 checkpoint migration、source archive、显式机制断裂 |
| 语法自我欺骗 | round trip、contrastive foils、negative parse、独立 semantic validator |
| 生成器自我评分 | evaluator dependency boundary、defect injection、held-out tasks |
| 模型过拟合 | family/area-held-out、替代模型、全局 sensitivity、ablation |
| 参数不可辨识 | synthetic parameter recovery、equifinality/profile analysis、uncertainty coverage、明确不可识别报告 |
| evaluator 任务泄漏 | pack role、首次可见版本、sealed audit expiry、external elicitation |
| Canon/模拟语料自证 | CorpusRole、sampling/observation lock、calibration/validation split |
| UI 绕过领域边界 | API contract、Tauri E2E、无直接 state JSON 写入 |
| 长任务破坏项目 | idempotency、cancel race、crash/restart、expected history conflict |
| Job/Operation 身份混淆 | Project/Run/Job ADR、RunLedger migration、attempt 与 semantic operation 分离 |
| 离线重验失效 | dependency payload bundle、compiler/reducer compatibility、ReplayCapability |
| Canon 漂移 | impact index、published fixture、retcon/branch regression |
| 文学任务词语拼盘 | required meaning、forbidden readings、无 silent fallback |
| 数据引用虚假 | payload/table/record/field/citation validation |
| 外部可用性不足 | creator task、language relay、expert blind audit、accessibility task |

每个高风险领域至少按需要包含 unit、property、replay、migration、scientific validation 和 UI task tests。不得用广泛 skip；预期失败只能 strict xfail，并写明迁移目标。

## 16. UX 与产品验证计划

### 16.1 信息架构

```text
Forge    language brief / canon seed / candidates
Write    scene / Meaning Workbench / utterance / canon
History  process / variants / epochs / branches / contact
Inspect  dictionary / grammar / paradigms / etymology / Why
Lab      quality / experiments / data-model locks
Publish  Language Bible / IGT / actor and audit packs
```

Guided/Expert 是同一任务中的渐进披露；Research 是 Lab 工作区。切换不改变字段值、命令语义、默认模型或能力真实性。

### 16.2 第一轮固定任务

1. 不编辑 JSON，从真实项目简报或已有 canon 创建候选；
2. 导入已有名字并解决最小冲突；
3. 用相同名字、台词和诗句比较候选；
4. 在 Meaning Workbench 中识别并解决一种真实歧义或目标语言义务；
5. 生成短场景、识别 ExpressionGap，并接受一项最小扩充加入 CanonCorpus；
6. 从现代词追踪到祖形和每个事件；
7. dry-run 一条规则并理解 Canon 影响；
8. 取消长任务，重启后恢复或确定性重跑；
9. 只用键盘完成关键路径；
10. 切换中英文，IPA、正字法、state/hash 不变化。

第一轮以已拥有姓名、台词或短场景的目标叙事作者验证首发 wedge；conlanger 验证 Expert 渐进披露，语言学家验证审计材料，三者不互相冒充主要用户。R0 同时记录用户当前表格、Wiki、词典和音变工具基线以及继续使用意愿。形成性研究与 Gate benchmark 使用不同参与者；每个 R 阶段持续迭代，不在 R0 后永久冻结用户理解。

正式 UI 视觉系统只有在 R0B-06 任务路径通过且 R1 API 稳定后启动。目标至少为 WCAG 2.2 AA；自动扫描不能替代键盘、屏幕阅读器、高对比和 200% 缩放测试，无障碍参与者从 R0B 开始进入关键任务。

## 17. 数据、模型与科学证据计划

- catalog manifest 可以没有 payload hash，但任何进入 compiler、calibration 或项目的数据必须形成 execution lock；
- PHOIBLE、Grambank 等资源按 doculect/source 使用，保留 family/area 和 missingness；
- exact DOI、payload hash、license、sampling、transform 和 transformed hash 全部锁定；
- registry definition、empirical PriorPack、Research TheoryProfile 与 Creative Preference 分离；
- 校准集与验证集按 family/area/phenomenon 预先分区；
- AuthorCanon、TaskFixture、SyntheticUsage 与 ExternalEmpiricalObservation 具有不可互换的 CorpusRole；同一 slice 不得既调参又验证同一声明；
- 模型版本发布时生成 ModelEvidenceBundle，链接 ODD、TRACE、数据锁、observation model、测试、回放、参数恢复、可辨识性、校准、敏感性、消融、held-out 和专家异议；
- 测试通过只属于 verification；不能替代 empirical validation。

## 18. 性能与存储门

初始工程预算用于发现回归，不是永久 SLA。每项测量必须记录机器等级、OS/build、fixture 规模、冷/热启动、重复次数、p50/p95 和峰值内存：

- UI 短命令 p95 < 100 ms；
- cancel acknowledgement < 250 ms；
- WS-1 的 3–5 candidates / 50 concepts p95 < 2 s；
- WS-1 project open/reopen < 500 ms；
- UI 主线程不执行超过 50 ms 的领域计算；
- replay、candidate batch、UsageCorpus 分别记录峰值内存。

“当前 full-history `project.json` 对 WS-1 足够”只是待 R1-05 验证的工程假设。R3B-02 必须在 WS-2/长历史前用现实 fixture 测量完整重写、启动回放和内存；若不满足预算，再通过单独 ADR 决定 immutable checksummed event segments、manifest head、derived SQLite 和 rebuildable snapshots。不得让 snapshot 或 SQLite index 成为第二权威事实源。

## 19. 迁移与清理路线

1. 冻结 v2 schema、fixture、hash 和真实导入样本；
2. 先增加 application/job，不改变持久化语言语义；
3. v3 使用新类型，不在 v2 struct 上无边界追加字段；
4. v2 历史只迁移为 `ImportedCheckpoint/LegacyStateBoundary`，不从 state diff 推断机制；
5. Registry → phonology/prosody → morphology/grammar → event/reducer 逐域切换；
6. Rust 纵切成为权威后，停止对应 Python 生产路径；
7. Python 保留数据分析、研究模型与黄金对照；
8. production Job 替代 demo worker 后再删除 DemoEngine；
9. Streamlit 只有在 Tauri 等价任务通过后删除；
10. 文件移动、格式化、语义行为、schema migration 和大规模删除分开提交。

删除仍受 [CLEANUP_PLAN](./CLEANUP_PLAN.md) 与迁移矩阵约束。静态不可达不是删除证据。

## 20. 风险登记

| 风险 | 早期信号 | 控制 | 阻断门 |
|---|---|---|---|
| Grammar IR 范围爆炸 | WS-1 开始实现完整 HPSG/所有类型学 | 严格有限双向子集；第二对照轮廓揭露偏置 | WS1-02/03 |
| 生成器自我认证或过生成 | evaluator 复用私有评分、只测目标读法存在 | 四类 TaskPack、negative precision、缺陷注入、sealed audit | WS1-06 |
| “可用”出现太晚 | 只有状态/hash，没有真实句子 | WS1 minimal authoring loop；R3 Scene Lab | WS1-08 |
| 文化刻板因果 | 世界标签直接改变语法/音系 | 只形成 communication/lexicon/register need | R0A-01/R0B-01 |
| Canon 被随机重生成破坏 | 更新后姓名/台词漂移 | stable ID、Canon release、impact、branch/retcon | STORY-01 |
| 规则扩充掩盖模型缺陷 | 规则数增加，反例仍失败 | IR/TaskPack/WS1 先行 | WS1 Gate |
| 社会模拟参数不可辨识 | 多组参数产生相同曲线 | 群体 variation、参数恢复、equifinality、替代 TheoryProfile | R3B-03/WS2-06 |
| 事件日志爆炸 | 每 token 一事件、full JSON 重写变慢 | UsageCorpus 分离、过程级 ChangeSet、R3B storage decision | R3B-02 |
| Canon 自证传播 | 作者台词直接变成人口频率 | CorpusRole、synthetic sampling、observation model | R0B-02/WS2-02 |
| Project/Job 二次迁移 | 一个项目只有一个 run、JobId 被当历史身份 | Project/Run/Job ADR + RunLedger migration | R0A-02/WS1-01A |
| LLM 污染真值 | 自由文本直接进入状态 | Proposal Escrow + schema/domain/user decision | R7-LLM-01 |
| TTS 掩盖错误分析 | 好听音频先于 phonetic plan | R7-SPH-01 硬前置 | R7 Speech Gate |
| UI 复制领域逻辑 | webview 自建 Blueprint/State | versioned API、shared capability registry | R1-03 |
| 双核心长期共存 | Python/Rust 都写项目 | 领域切换后停止 Python production | 每阶段 cleanup |
| 数据关联变因果 | 频率直接成为硬规则 | prior/hypothesis/preferences 分层 | R0B-05/07 |
| 计划因并行失控 | 多领域同时半完成 | 关键路径、WIP 限制、阶段 gate | 全阶段 |

## 21. 工作包执行模板

任何工作包进入 `In Progress` 前必须补齐：

1. 用户可见或研究问题；
2. owner 与 reviewer；
3. 实际专业容量、S/M/L 或三点估算、WIP、timebox 与超限降范围规则；
4. 范围和明确非目标；
5. Hard constraint / Empirical prior / Research hypothesis / Creative preference 分类；
6. authoritative schema、ADR、数据源和迁移影响；
7. 输入、输出、错误、命令和事件版本；
8. semantic hash、RNG path 和 replay 影响；
9. unit/property/replay/migration/scientific/UI tests；
10. 性能预算、取消安全点和并发策略；
11. fixture、golden scenario、TaskPack role 与 hostile cases；
12. 所需 GateEvidence kind、阈值、severity、waiver 和过期条件；
13. 文档、capability matrix 与用户文案更新；
14. rollback、cleanup 和停止双写计划；
15. 允许的产品声明和已知限制；
16. Stop/Go 决策人及证据位置。

工作包只能按 `Planned → Ready → In Progress → Review → Complete` 流转。依赖、ADR、数据或 fixture 未就绪时不得标为 Ready。Complete 必须记录提交/PR、测试、语义 hash/baseline 变化、迁移结果和剩余限制。

## 22. 当前执行队列

### 现在允许执行

第一批并行但有边界的队列：

| Lane | 立即工作 | 输出 |
|---|---|---|
| A Repository | R0A-05 G0A repository baseline | 使用 [G0A 交接清单](./governance/G0A_REVIEW_AND_BASELINE_HANDOFF.md)审查纳入范围，形成版本基线与 clean-checkout 证据 |
| B Platform Decisions | R0A-01～04/06/07 | 产品 wedge、ADR 依赖、Project/Run/Job、Gate/交付合同 |
| C WS-1 Domain Evidence | R0B-01～05/07 | Meaning/Grammar/Corpus/TaskPack/Capability、反例与数据锁 |
| D Product | R0B-06 | Product Evidence、Meaning Workbench 原型、失败/转向记录 |

Lane A/B 中进入 R1 所需的决定 Accepted 并关闭 G0A 后，可以实施 R1；R0B 与 R1 继续并行。只有 G1 与 G0B 同时关闭后才进入 WS-1 正式 schema、compiler、reducer 和创建入口。R3 期间可以准备 G3B；只有 G3 与 G3B 同时关闭后才进入 WS-2。

### 继续停止

- LanguageState v3 持久化实现和正式 reducer；
- SpeechCommunity/PopulationVariation 正式 schema；
- 大批生产规则；
- 全量外部数据导入；
- 正式 UI 视觉精修；
- TTS、权威 LLM、WASM/代码插件；
- 删除 Python legacy；
- 把 current demo worker 或 `project.json` 直接扩展成长期架构。

### 下一次实现启动门：G0A

恢复 R1 平台实现前必须同时满足：

- [当前 G0A GateEvidence](./G0A_GATE_EVIDENCE_2026-07-17.json) 的 `decision` 必须等于 `passed`，且不存在未登记 waiver；截至 2026-07-18 该值仍为 `blocked`；
- ADR 依赖图无环；Project/Operation/Run/Job、staging、query、dependency bundle 与 storage authority 中影响持久化身份、回放或权威写入的决定已经 Accepted；
- G0A clean checkout、RNG、平台 API/Job/Gate 合同可复现；
- `scripts/g0a_handoff.py --check --require-clean-subject` 证明不存在未提交的 subject candidate、瞬态产物、冲突或未经单独复核的删除/重命名；
- R0A/R1 owner、reviewer、容量、估算、WIP 和 timebox 已填写；
- 架构、产品和发布声明评审未发现会迫使 R1 产生第二权威或冻结 v3 的阻断缺口。

进入 R2 还必须额外满足 G1 + G0B：Meaning/Grammar、Registry/State v3 目标合同、TaskPack/Canon/evaluator、数据 execution slice、Meaning Workbench 和所有影响持久化/回放的 ADR 均已就绪。State v3 的生产实现属于 R2 纵切交付物，不得反向成为进入 R2 的既成实现前置。Variation/SpeechCommunity 不再是 R1/R2 前置，而是 G3B 前置。

## 23. 计划维护

- `ROADMAP.md` 只维护产品方向、里程碑状态、发布切片和当前 Next；
- `LANGUAGE_SIMULATOR_PLAN.md` 维护长期能力地图、领域工作包与跨阶段 Gate；
- 本文维护关键路径、详细执行 WBS、依赖、Stop/Go 和当前队列；
- ADR 维护不可逆的架构和持久化语义决策；
- 每个里程碑结束时更新状态、证据、基线、失败与下一阻断项；
- 任何能力声明变化必须同步 README、capability registry 和 UI；
- 不用测试数量、代码量、词数或规则数代替阶段完成度。
