---
document_type: roadmap
decision_status: not-applicable
implementation_status: in-progress
normative_scope: current
last_verified: 2026-07-19
owner: unassigned
reviewers: []
---

# Telysta Diachron Engine 项目路线图

- 状态：`Active planning baseline / pending reviewed subject`
- 基线日期：2026-07-12
- 最近路线修订：2026-07-19
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

## 2. 当前核心判断

项目已经拥有较丰富的领域模型和单元测试，但仍是研究原型。产品化前必须解决以下基础问题：

1. 历史重建目前不能完整恢复 DAG、类型学和保护集合。
2. 注词、复合、替换与部分类型学变化没有进入统一事件链。
3. 运行共享全局配置和固定快照目录，无法保证并发与多项目隔离。
4. Flat、Epoch 和 Branch 存在不同的演化实现，行为会逐渐分叉。
5. 一些模块只有独立实现和测试，没有进入主流程。
6. 规则缺少统一规范、版本、冲突分析和质量准入机制。

因此，在基础一致性完成前，不把“新增更多规则”或“完整桌面 UI”作为首要目标。

## 3. 架构原则

### 3.1 单一事实来源

- 待 ADR 接受后，`OperationContext` 是一次语义操作的模型/数据/规则/RNG 锁；`JobRecord/Attempt` 独立保存执行、日志、取消和恢复状态，不能混入语言语义哈希。
- `StateTransaction` 是修改 Rust 权威语言/项目聚合并提交 typed event/ChangeSet 的唯一入口。
- UI 不直接从全局目录推断当前运行数据。

### 3.2 可复现

同一引擎版本、项目、配置和 seed 必须产生相同：

- 词典状态哈希；
- 类型学状态哈希；
- DAG 哈希；
- 事件序列哈希。

时间戳、日志路径等非语义字段不进入语义哈希。

### 3.3 可回放

任意原生项目必须能够由锁定的 Genesis/Imported boundary 加后续 typed events/ChangeSets 恢复权威语义状态；snapshot/keyframe 只是可删除缓存。回放结果应与当时在线状态语义相等，而不仅是词形相同。

### 3.4 本地优先

项目默认保存在用户设备。LLM 是可关闭的辅助层，符号演化核心不依赖网络服务。

### 3.5 Rust 生产核心与 Python 研究桥接

Rust 是正式产品中语言状态、规则执行、历史模拟和项目存储的唯一权威实现。Python 保留为旧引擎基线、数据分析和语言学研究环境，但不进入最终桌面产品的必需运行时，也不得成为第二个项目状态写入者。

允许进行大规模重构，包括重建领域对象、目录、存储和执行路径；重构必须由黄金场景、领域不变量和迁移测试约束，禁止把现有缺陷逐行翻译到 Rust。正式决策见 [ADR-006](./adr/ADR-006-rust-native-core-python-research-bridge.md)。

## 4. 目标架构

```text
Tauri 2 + Svelte/TypeScript
  ├─ Project Workspace
  ├─ Epoch / Rule / Lexicon / DAG / Sentence / Quality Labs
  └─ Versioned Commands / Events
          │
Rust Application Service
  ├─ Project / Operation / Job / Cancel / Export
  ├─ Query / Explain / Compare
  └─ Rust Simulation Core
      ├─ Model / Time / RNG / StateTransaction
      ├─ Rules / Phonology / Grammar / Diachrony
      ├─ Family / Contact / Quality / Provenance
      └─ Storage / Migration
          │
Project Storage
  ├─ Versioned authoritative project/event artifact (`project.json` in v1)
  ├─ ProjectManifest / RunLedger / durable Job journal（ADR-011 Proposed；Accepted 前不实施）
  ├─ Rebuildable SQLite state and event index
  ├─ Versioned YAML rule packs
  └─ JSON/CSV/Markdown export

Python Research Lab
  ├─ Legacy reference adapter
  ├─ Dataset and statistical experiments
  └─ Golden scenario comparison
```

桌面和生产核心的正式决策见 [ADR-006](./adr/ADR-006-rust-native-core-python-research-bridge.md)。[ADR-004](./adr/ADR-004-tauri-python-sidecar.md) 已被替代，仅保留历史记录。

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

状态：`R0A/R0B evidence preparation in progress；work packages Planned pending assignment；G0A blocked；G0B not evaluated`

目标：在重构前建立可验证的现状基线。

交付物：

- 可重复安装的开发环境和 CI；
- 5 至 10 个黄金场景；
- 语义状态哈希工具；
- 模块可达性与去留清单；
- 当前持久化格式的回放失败测试；
- Tauri 最小技术验证，不包含正式 UI。

完成标准：

- 测试可在全新环境一条命令运行；
- 相同 seed 连续运行三次的语义哈希一致；
- 黄金场景覆盖 Flat、Epoch、Branch、语法化、复合和借词；
- 已知历史回放缺陷由失败测试稳定复现。

### Phase B：Rust 地基与架构验证

状态：`Partially complete / domain implementation waits for G1 + unevaluated G0B；platform work waits for blocked G0A`

目标：建立 Rust 权威核心，并用最小纵切验证状态、操作和回放合同，而不是先迁移全部旧功能或把 ADR-005 的长期研究主张当作 WS-1 前置。

交付物：

- Rust workspace、Tauri shell 和版本化 command/event API；
- 稳定 ID、`TimeModel`、`ProjectManifest/RunLedger/OperationContext`、独立 `JobRecord/Attempt` 和版本化 `RngTree`；
- `LanguageState v3`、共享 FeatureRegistry、typed ChangeEvent、`StateTransaction`、快照和原子持久化；
- 只能由祖语编译器签发的 `GenesisArtifact` 项目创建边界；
- 旧项目只读适配器和迁移 manifest；
- application service、持久化 Job、版本化桌面 API，以及一个不写正式语言状态的取消/恢复 Spike；
- 一个祖语微型纵切的结构、存储和查询地基；两社区、接触和重建后移到 WS-2/Family。

完成标准：

- 同版本、同输入的 Rust 结果跨进程一致；
- 每类状态变化可完整回放；
- 两个并行项目互不污染；
- Tauri 可以直接运行、取消和恢复 Rust 任务；
- 对应本阶段的 Accepted ADR、GateEvidence 与专家评审没有阻断缺口；ADR-005 的长期阶段证据分别在后续 G2/G4/G5 兑现。

### Phase C：可审计祖语编译器

状态：`Planned`

目标：完成第一个真正可信的产品纵切，而不是迁移旧随机造词器。

交付物：

- `LanguageBlueprint`、`LanguageState v3` 和多候选生成；
- 音系、韵律、音系配列、词根派生家族和 Grammar IR；
- `ProtoLanguageCompiler` 与 `GenesisQualityGate`；
- 词典、音系表、核心范式、构式清单和来源报告。
- 最小双向 Grammar/Meaning IR、版本化 TaskPack、IGT、`ProofCarryingUtterance` 和 typed `ExpressionGap`；
- CanonSeed、独立 evaluator 与最小作者闭环。

完成标准：

- 创世硬约束错误为零；
- 基础词不再全部独立随机；
- 用户锁定、经验先验、审美偏好和研究假说可区分并解释；
- 外部语言学阶段评审没有阻断性模型问题。

### Phase D：语言家族与真实演化

状态：`Planned`

目标：先以 WS-2 完成创新—变体—传播—常规化，再从可使用语言产生可回放、可重建的历史分支和接触层。

交付物：

- `ChangeProcess`、创新、采用、社会与词汇扩散；
- `SpeechCommunity`、`PopulationVariationState`、人口迁徙、网络、声望、L1/L2 和使用领域；
- 音系重组、类推、语法化、语义变化和正字法历史；
- 迁徙、分裂、接触、借词、结构扩散和标准化；
- 同源集、规则音对应和祖语重建挑战。

完成标准：

- 两个分支产生稳定但不同的规律对应；
- 例外、借词层和不规则形式具有可追溯来源；
- 社区参数通过过程影响扩散，不直接覆盖语言结构；
- 家族纵切通过第二次外部专家评审。

### Phase E：声明式规则平台

状态：`Planned`

目标：围绕稳定的 Rust 状态和 ChangeProcess IR 建设用户可插拔规则。

交付物：

- 版本化 RulePack、RuleSpec 和 Rust Rule Compiler；
- validate、dry-run、apply、explain 生命周期；
- 冲突、振荡、不可达与影响范围分析；
- 内置规则包和用户规则 SDK。

完成标准见 [规则系统与语言质量计划](./RULE_QUALITY_PLAN.md)。WASM 扩展后置，首版不提供任意代码插件。

### Phase F：Tauri 创作者工作台

状态：`Planned`

目标：围绕已经稳定的 Rust API 完成可安装、可保存、可取消的本地工作流。低保真任务研究从 R0B 开始，项目/Job 壳从 R1 开始，WS-1 提供候选与最小作者闭环，R3 提供 Meaning Workbench、Scene Lab 与 Canon Guardian；本阶段不再作为等到所有核心完成后才启动的单次横向工程。

首批功能：

- 新建、打开、保存、迁移和导出项目；
- 比较祖语候选并锁定 Blueprint；
- 运行、观察、取消和恢复历史模拟；
- 查看词典、语法、时间线、家族、同源集和来源解释；
- Quick、Expert 和 Research 三种视图共享同一状态模型。

完成标准：

- 干净环境无需 Python 即可完成核心流程；
- 取消或崩溃不会损坏项目；
- Windows 安装包通过真实用户任务验证；
- Streamlit 停止功能开发，并在等价能力确认后删除。

### Phase G：语法、文学能力与 Quality Lab

状态：`Planned`

目标：通过真实语料任务证明语言能用于叙事、对话、论证和多语体创作。

交付物：

- 完整 Grammar/Discourse IR、构式、范式和实现器；
- CommunicationNeedEngine、typed SyntheticUsage/Observation、语域和文学任务集；
- AuthorCanonCorpus、Onomasticon、Meaning Workbench、Scene Lab、ProofCarryingUtterance、LanguageCapabilityCertificate 与 ProductUsabilityEvidence；
- 多维 Quality Lab、专家审计包和版本化评审 rubric。

完成标准：

- readiness 由语义、构式、语域、生产力和边际收益共同判断，不使用单一词数；
- 黄金场景覆盖创世、变化、分支、接触和文学任务；
- 所有指标可下钻到规则、实体、构式或事件；
- 外部盲评没有严重结构错误。

### Phase H：创作、翻译、发音与发布

状态：`Planned`

目标：将成熟语言用于实际创作，并输出可验证的文本和语音。

交付物：R3 先交付 Authoring Studio Alpha、受控 Meaning/Scene 解析、IGT 与 deterministic `PronunciationPlan v1`；R6 扩展高级篇章、文学任务和 Language Bible；R7 的 `SpeechRenderPlan / PhoneticPlan v2` 只增加协同发音、表演/音频映射、确定性语音预览与可选神经语音，神经语音不作为 1.0 发布门。

完成标准：R3 的文本、gloss、音系形式与 v1 发音计划来自同一分析；R6 的复杂叙事不静默丢失语义；R7 再证明渲染层覆盖 v1 计划且不反向改变语言结构。

清理与整合贯穿 Phase A–H，不再作为独立等待阶段。每个 Rust 领域能力成为权威路径后，按[代码与模块清理计划](./CLEANUP_PLAN.md)迁移调用并删除对应旧生产实现。

### 发布切片

| 发布 | 可验证结果 | 对应阶段 |
|---|---|---|
| 0.2 Deterministic Baseline | 旧引擎黄金场景、分域哈希和已知缺陷报告 | A |
| 0.3 Platform Baseline | G0A/G1、application/JobStore、版本化 API/query、取消/恢复与存储基准 | A–B–F |
| 0.4 Executable Language Preview | WS-1 多候选 Genesis、双向语法、Orthography/IGT、结构 ChangeSet 与 explain；不得称 Alpha/canon-safe | B–C–F–G |
| 0.5 Canon-first Alpha | AuthorCanonCorpus、命名、Scene Lab、生产性构词、Canon impact、release/export 与创作者验证 | C–E–F–G |
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

完成日期：2026-07-12

- 实现 `telysta.legacy-state.v1` 只读规范化适配器；
- 统一创世整数 ID 为稳定字符串，并拒绝空 ID、重复规范 ID 和 key/entity 不一致；
- 对词典、DAG、类型学、事件和完整状态生成 SHA-256 分域哈希；
- 实现 `legacy-rng-tree-v1`，主演化、Epoch、Branch、Mock LLM 和演示路径使用独立派生流；
- 建立 genesis、flat_10、epoch_injection、branch、mock_llm 五个版本化黄金场景；
- 同 seed 三次、不同进程、不同测试顺序和先运行其他 seed 的确定性门通过；
- 基线报告记录规模、词类、音段/音节、同音、DAG、规则应用和硬错误；
- 该工作包验收快照：513 项测试通过。

### A-003：历史回放特征测试 ✅

完成日期：2026-07-13

- 新增在线状态与回放状态的特征测试矩阵；
- 验证音变词形、手工注词和软删除的标量回放行为；
- 以 8 项严格 `xfail` 固定完整状态、DAG、Swadesh 保护集、类型学、事件字段、借词、化石、复合和 Epoch 注词缺陷；
- 建立 [Legacy 事件覆盖账本](./LEGACY_EVENT_COVERAGE.md)，明确每个事件的写入、持久化、reducer 与 Rust 合同；
- 不在本工作包中修补旧存储；
- 该工作包验收快照：516 项测试通过，8 项已登记 `xfail`。

### A-004：模块清单 ✅

完成日期：2026-07-13

- 新增 `scripts/module_inventory.py`，通过 Python AST 生成可重复的生产可达性与测试引用报告；
- 审计得到 87 个 `app` 模块：65 个从 CLI/Streamlit 入口静态可达，57 个被测试直接引用，22 个不在生产静态路径；
- 新增 [模块迁移矩阵](./MODULE_MIGRATION_MATRIX.md)，为每个能力组记录 Rust 目标、分类和最晚决策门；
- 静态不可达模块只进入审查，仍需通过数据/动态注册/迁移删除门；
- 该工作包验收快照：519 项测试通过，8 项已登记 `xfail`。

### A-005：Rust Core Shell Spike ✅

完成日期：2026-07-13

- 创建 `telysta-core` 与 Tauri desktop workspace，桌面壳直接链接 Rust crate；
- 定义 `telysta-engine-api.v1` 的 response/event envelope；
- 实现 `engine_info`、`run_demo`、`engine://progress`、`cancel_run` 与 `recover_pending_runs`；
- 以双 checkpoint 槽位验证最小 demo 崩溃恢复边界，`cargo check -p telysta-desktop` 在 Windows 通过，运行时声明不需要 Python；
- Rust 核心 6 项测试覆盖确定性、进度、取消、恢复和 API 版本；详见 [Rust Desktop Shell Spike](./RUST_DESKTOP_SPIKE.md)；
- Spike 不迁移正式语言模型，也不直接承载完整 UI。

### B-001：Foundation Model ✅

完成日期：2026-07-13

- 以 `telysta-entity-id.v1` 实现稳定、类型化实体 ID、确定性派生和显式 legacy ID map；
- 以 `telysta-time-model.v1` 实现年份、精确世代坐标、半开区间、无浮点采用曲线、并发关系与依赖排序；
- 对 ID、时间、采用曲线和日程的 Rust deserialization 执行同一套不变量，拒绝无效 schema；
- 核心测试覆盖所有上述合同；详见 [Foundation Model v1](./FOUNDATION_MODEL_V1.md)；
- 不使用 demo checkpoint 或 Python `EngineHotState` 作为正式模型的基类。

### B-001.1：Foundation Repair ✅

完成日期：2026-07-13

- `LegacyIdMap` 的构造与反序列化统一执行 source schema、canonical key 和 target kind 校验；
- `TimeReference`、`VersionedTimeRange` 与 `ChangeSchedule` 均绑定 `TimeModel` schema，拒绝混用时间模型；
- demo run 使用显式幂等 ID，重复恢复不会重复启动 worker；
- desktop checkpoint 增加 checksum、临时文件替换和双槽恢复，Tauri CSP 不再关闭；
- CI 固定 Rust 1.77.2、使用 lockfile，并验证 workspace、desktop 链接与 Clippy。

复审修正：最后一项只描述 CI 命令意图，不能再表述为已证明的 MSRV。真实 MSRV
必须由兼容的 locked dependency graph 和 Windows/Linux 精确工具链运行共同证明。
COR-07 的本地修正选择 1.88.0：Windows exact gate 已通过，Linux workflow 已准备，
但 reviewed subject 上的远端运行与 provenance 尚不存在，因此 B-001.1 的该项仍在
重新验证中。原 1.77.2 记录只保留为历史，不再是当前兼容声明。

### B-002：Canonical LanguageState Schema ✅

完成日期：2026-07-13

- 为音系、韵律、词汇/义项、形态、构式、语体、书写、类型学、家族位置和 provenance 定义 `telysta-language-state.v1`；
- 将状态分为可序列化核心、派生统计和非语义运行元数据，并以 canonical JSON 重新校验后输出；
- 状态强制 evidence class、类型学证据、实体类型、跨域引用和 provenance 覆盖；
- 事件、社区、家族图和接触执行器保留给后续纵切，不以复刻 Python 数据结构或旧输出缺陷为目标；详见 [Canonical LanguageState v1](./LANGUAGE_STATE_V1.md)。

### DAT-001：最小数据治理与 Manifest ✅

完成日期：2026-07-13

- 定义 `telysta-data-manifest.v1`、`DataReference` 和 `DataRegistry`，记录来源、版本、许可证、citation、覆盖、限制与可选 payload hash；
- 为 `LanguageState` evidence 加入数据记录引用；
- 提交并测试 PHOIBLE 2.0、Concepticon 3.4.0 和 Grambank 1.0.3 的版本化 manifest，明确抽样与语义限制；
- 不下载或伪造固定 payload；项目或发布使用真实数据前必须锁定 payload hash；详见 [Data Governance v1](./DATA_GOVERNANCE_V1.md)。

### B-003：确定性合同 ✅

完成日期：2026-07-13

- 实现 `telysta-semantic-hash.v1` 的 full 与 11 个语义域 hash，派生统计不参与 hash；
- 实现 `telysta-rng-tree.v1`，以 root seed 和稳定路径的 SHA-256 counter stream 提供独立随机流；
- 测试同路径重现、无关路径隔离、合法范围和词汇变化的分域 hash 定位；
- 详见 [Determinism Contract v1](./DETERMINISM_CONTRACT_V1.md)。

### B-004：项目运行与事务合同 ✅

完成日期：2026-07-13

- 该工作包曾定义带 payload hash 的 v1 `ProjectDataLock`、`RunContext` 与 RulePack lock；其长期身份边界由 ADR-011 重新决策，不把历史完成项当作现行目标架构；
- 定义版本化 `Genesis` / `StateRevision` 事件、连续 sequence、provenance 顺序验证和可回放 `ProjectHistory`；
- `StateTransaction` 成为 Rust 项目历史的正式写入入口；完整的领域 delta 和原子存储仍留给后续工作包；
- 详见 [Project Runtime and Transactions v1](./PROJECT_RUNTIME_V1.md)。

### B-005：时间模型精确绑定与 provenance 时间完整性 ✅

完成日期：2026-07-13

- `TimeModel`、时间引用、范围与日程升级为指纹绑定，拒绝同 schema 下的跨模型混用；
- `LanguageState` 升级为 v2，旧时间数据只允许经显式源模型迁移；
- 项目回放验证 provenance 的 `createdAt` 与其事件的 `occurredAt` 精确相等；
- 详见 [Time Model v2 Migration](./TIME_MODEL_V2_MIGRATION.md)。

### FND-008：原子项目存储与迁移 ✅

完成日期：2026-07-14

- `telysta-storage` 将校验和保护的 `project.json` 设为唯一权威项目文件；SQLite 仅是可重建状态/事件索引；
- 正常加载只接受当前项目格式；旧的独立 history 必须经显式、版本化迁移器升级，源文件会先归档；
- 覆盖中断恢复、checksum 篡改、迁移和派生索引重建测试；详见 [Project Storage v1](./PROJECT_STORAGE_V1.md)。

### FND-008.1：存储完整性与并发收口 ⚠ Reopened by 2026-07-19 review

完成日期：2026-07-14

- SQLite 索引必须逐事件与权威 history 对照；元数据未变但行被篡改时也会重建；
- 全部写入与迁移路径使用进程内/跨进程写 lease；`save_if_current` 以 history hash 拒绝陈旧编辑器覆盖；
- 迁移 journal 使发布中断可续跑，重复迁移器注册不再污染 registry。

复审发现剩余阻断：create 的存在性检查不在同一 lease 内；`commit_history` 未验证
候选是当前 history 的前缀扩展；archive/journal 和 SQLite projection 存在完整性/
TOCTOU 缺口。当前关闭包为 `R0A-09 Current v1 Authority Repair`；修复前不得向
Tauri 暴露 create/commit。

### PLT-002：桌面项目持久化契约 ← Paused；剩余范围归入 R1

- `PLT-002.1` 已完成：`ProjectSession` 提供版本化会话摘要、语义 hash、恢复与索引状态；
- `PLT-002.3` 已完成最小安全命令：`open_project`、`get_project_session`、`refresh_project`、`close_project`；
- `create_project` 与写入命令刻意延后到 Genesis 编译器：禁止 UI 伪造空 `LanguageState`；
- 后续完成 `PLT-002.2/002.4/002.5`：路径服务、端到端命令测试、Demo 降级与用户可操作的冲突/迁移恢复界面。

### GEN-001：LanguageBlueprint v1 ← Superseded

完成日期：2026-07-14

- v1 已证明基础意图合同可行，但 `Map<FeatureId, ...>` 无法保存同一 feature 的多个知识来源；
- v1 没有权威 FeatureRegistry，不能在协议层拒绝未知 feature 和错误值域；
- v1 只作为显式迁移源保留，详见 [LanguageBlueprint v1](./LANGUAGE_BLUEPRINT_V1.md)。

### GEN-001.1：LanguageBlueprint 合同修复 ← Completed

完成日期：2026-07-14

- v2 分离 `IntentId` 与 `FeatureId`，同一 feature 可保留多个独立、可解释的意图；
- 提供显式 v1 → v2 迁移与迁移审计 hash，普通入口拒绝 v1；
- 建立 12 项最小音系/韵律 FeatureRegistry，校验值域、控制、依赖和不兼容项；
- 验证报告区分“结构有效”和“当前编译器可实现”，并返回注册表版本/hash 与结构化诊断；
- Tauri 命令和桌面示例改用 v2；当前能力均为 `planned`，因此尚不开放项目创建；
- 详见 [LanguageBlueprint v2](./LANGUAGE_BLUEPRINT_V2.md)。

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
