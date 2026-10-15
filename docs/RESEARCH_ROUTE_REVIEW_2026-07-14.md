---
document_type: research
decision_status: not-applicable
implementation_status: in-progress
normative_scope: historical
last_verified: 2026-10-12
---

# Telysta 语言生成与历时模拟路线严格评审

- 状态：Research Review / historical planning evidence
- 日期：2026-07-14
- 评审对象：产品目标、语言生成逻辑、历时模拟方法、科学验证路线、Rust/Tauri 架构与 UI/UX
- 当前快照：HEAD fa7468b；工作树包含尚未纳入版本基线的大量 Rust、Tauri、CI 与合同文件
- 总体判定：Conditional Go — 保留技术底座，修改语言模型与科学验证路线
- 处置：`Accepted as planning evidence`；第 13–14 节原始阶段/Go 建议由 [产品开发执行计划](./PRODUCT_DEVELOPMENT_PLAN.md) 的 R0A/R0B–R7 与 G0A/G0B/G3B 顺序取代

本文是研究评审，不是新的持久化架构决策。凡涉及实体身份、LanguageState v3 语义、事件回放或新插件边界的建议，恢复实现前必须由现有 ADR 修订或新 ADR 决定。

研究结论、证据与 Conditional Go 判定保留不变；执行层已采纳“先证明语言可执行和可创作，再声明真实传播”的更严格次序：WS-1 只证明结构事务，Story Language Kit 前置，变体传播归入后续 WS-2。当前状态、工作包和 Gate 以执行计划为准。

下文出现的单一 `G0`、旧 Current/Next 或 Implementation Hold 均是 2026-07-14 评审快照，不是现行执行门；不得据此绕过 G0A/G0B、Accepted ADR 或 G3B。

## 1. 结论先行

Telysta 的目标有条件可实现，但需要把产品承诺说准确。

可以实现并值得追求的目标是：

> 一个本地优先、确定性、可审计、可配置理论假设，能够生成内部一致的架空语言并模拟多种有证据支持的历史路径的创作与研究平台。

目前不能科学承诺的目标是：

> 精确复现自然语言唯一真实的产生与演化机制，或保证专业语言学家几乎无法提出争议。

语言变化的启动、个体差异、社会传播、习得、频率和身份作用仍没有统一模型。正确的专业定位不是掩盖争议，而是让每种理论配置都版本化、可比较、可消融、可证伪，并公开其适用范围。

因此，本次路线判定为：

| 对象 | 判定 | 理由 |
|---|---|---|
| 产品愿景 | 有条件通过 | “可审计的语言历史模拟器”可行；“唯一真实演化”不可承诺 |
| Rust 单一生产权威 | 保留 | 有利于不变量、回放、迁移、并发和发布边界 |
| Tauri 本地客户端 | 保留 | 符合本地优先、长任务、项目文件和可恢复工作流 |
| Python 研究桥 | 保留 | 适合数据清洗、统计实验和旧基线，不应写正式状态 |
| 当前 Python 生成器 | 产品路线否决 | 固定音节模板、独立造词、逐词概率规则和 IPA 拼句不能证明语言成立 |
| RegistryBundle / GenesisArtifact / ChangeSet | 保留并修订 | 方向正确，但尚缺变体层、理论配置、跨域实现要求和完整候选生命周期 |
| LanguageState v3 直接开工 | 暂停 | ADR-008/009/010 仍为 Proposed，且缺少关键科学对象 |
| UI 视觉精修 | 暂停；允许低保真研究 | 应先验证主任务、信息层级和能力边界 |

最重要的架构结论是：不需要推翻 Rust、Tauri、RngTree、StateTransaction 和事件审计；需要重构的是 Genesis 编译与语言变化的核心抽象。

## 2. 产品承诺分级

以下分级用于防止把工程完成误报为科学完成。

| 承诺 | 可行性 | 允许的产品表述 |
|---|---|---|
| 同版本、同输入、同 seed 可复现 | 高 | 确定性保证 |
| 生成一个无硬结构矛盾的小型语言 | 高，但当前未实现 | 通过 Genesis hard gate |
| 生成可用于核心交际任务的架空语言 | 中高 | 必须有双向语法和任务语料证据 |
| 生成可追溯的语言家族与接触层 | 中 | 必须有变体、扩散、重组和重建测试 |
| 生成具有文学表达能力的语言 | 中低、需人机协作 | 只能声明具体任务覆盖，不能只报词数 |
| 经验校准的人类语言演化研究平台 | 中低、长期研究 | 必须公开 TheoryProfile、校准域和不确定性 |
| 自动复现自然语言真实产生机制 | 不可验证 | 禁止承诺 |
| 专业语言学家找不到争议 | 不可验证 | 改为阶段外部评审和已知限制公开 |

## 3. 严格审核标准

### 3.1 成熟度等级

每项能力单独评级，不计算一个总“自然度分数”。

本节 R0–R4 仅是本次研究快照的能力成熟度代码，不是后续路线图的 R0–R7 里程碑。

| 等级 | 含义 |
|---|---|
| R0 | 缺失，或只有名称 |
| R1 | 有合同、文档或研究原型 |
| R2 | 权威路径已实现并通过局部验证 |
| R3 | 通过多 seed、反例、对照、回放和 held-out 验证 |
| R4 | 外部复核、复现实验和真实用户任务均通过 |

R2 证明软件按定义工作；R3 才开始支持模型有效性；R4 才支持产品级专业声明。

### 3.2 十一道审核门

| 门 | 严格通过条件 |
|---|---|
| A. 声明纪律 | 硬约束、经验先验、研究假说、创作偏好分离；每个结论说明证据边界 |
| B. 权威与可复现 | Rust 单一写入、版本锁、RngTree、事务、迁移、跨进程 replay 全部成立 |
| C. 共时结构完整性 | 音系、韵律、形态、构式、语义、语用、词汇和正字法可共同验证 |
| D. 生成与分析 | 同一 Grammar IR 支持生成和分析；核心意义在 round trip 中不静默丢失 |
| E. Genesis 一致性 | 跨域约束求解、多候选、用例 probes、回溯修复和可解释 Pareto 选择 |
| F. 历时机制 | 区分创新、变体共存、传播、常规化、结构重分析、类推和修复 |
| G. 谱系与接触 | 继承图、社群网络、限时接触边、波状扩散和借词整合均可表达 |
| H. 数据有效性 | 精确版本、payload hash、许可证、doculect、谱系/区域抽样和转换记录完整 |
| I. 科学可证伪性 | 有零模型、旧基线、消融、全局敏感性、不确定性和 held-out 检验 |
| J. 可审计结果 | 每个形式、规则、构式、事件、警告和失败都能下钻到来源 |
| K. 产品与 UX | 核心任务可完成；能力诚实；错误可恢复；无障碍、国际化和长任务可用 |

### 3.3 一票否决项

出现以下任一情况，不得声称达到专业语言模拟质量：

- 独立抽取若干类型学特征后直接拼成“自然语言”；
- 有 typed feature 可用时仍依赖 IPA 或字素字符串匹配；
- 只能生成表面句，不能恢复其结构和核心意义；
- 规则一触发就瞬间替换整个语言，没有竞争变体；
- 把完整状态替换描述为已知的音变、类推或语法化；
- 把数据库相关性、环境标签或审美偏好表述为因果规律；
- LLM 能直接提交词典、规则、历史或 LanguageState；
- 使用一个不透明自然度总分掩盖实体级失败；
- 没有锁定模型、数据、规则、RNG 路径与转换过程；
- UI 把 planned 能力呈现为可用；
- 只用单个黄金 hash 或测试数量证明语言学正确。

## 4. 当前项目评定

### 4.1 2026-07-14 实测基线

本次只运行只读验证，没有修改核心实现：

- cargo test --workspace --locked：59 passed；
- cargo clippy --workspace --all-targets --locked -- -D warnings：通过；
- Python scripts/check.py：519 passed，8 个登记明确迁移目标的 strict xfail；
- 当前 Git 基线仍未包含大量新增 Rust、Tauri、CI、合同和 fixture；按当时术语，历史单一 G0 的 repository 条件仍未关闭，现行对应条件已拆入 G0A。

这些结果证明当前工程检查稳定，不证明 Genesis、语法或变化模型科学有效。

### 4.2 分项成熟度

| 维度 | 计划 | 权威实现 | 严格判定 |
|---|---:|---:|---|
| 声明与证据分类 | R2 | R2 | 方向正确；尚未接入真实固定数据与 TheoryProfile |
| 确定性、事务、存储 | R3 | R2–R3 | 当前最强部分；仍需 clean checkout 基线 |
| LanguageState 表达力 | R2 | R1 | v2 是最小骨架，FeatureAssertion 与 semantic frame 仍为字符串 |
| Genesis 编译 | R2 | R0 | 没有生产 ProtoLanguageCompiler 或 GenesisArtifact |
| 双向语法与实际使用 | R2 | R0 | 旧句子生成只是 IPA 词串 |
| 历时变化 | R2 | R0 | Rust 仍以完整 StateRevision 为主；Python 是非权威研究原型 |
| 变体、传播与常规化 | R1 | R0 | 当前最大语言学架构缺口 |
| 家族、波状扩散与接触 | R2 | R0 | 有计划，无权威纵切 |
| 数据治理 | R2 | R1 | 有 manifest 合同，但没有执行级 payload lock 和抽样协议 |
| 科学验证 | R2 | R0–R1 | 有黄金场景愿景，无正式 ODD/TRACE、held-out、敏感性和消融协议 |
| 产品 UI/UX | R2 | R0–R1 | 当前是技术 Spike，不是可用创作工作台 |

### 4.3 代码与文档证据

当前实现与目标之间的关键差距不是推测：

- LanguageState 仍为 v2；FeatureAssertion.value、Construction.semantic_frame 是无约束字符串；
- Phoneme、ProsodyState、Morpheme 和 Construction 只具备最小字段；
- 项目历史仍用 Genesis / StateRevision 保存完整状态，而不是 typed linguistic effects；
- 内置 Blueprint 注册表的 12 个音系能力全部明确为 Planned；
- Tauri 只开放正式项目的打开/刷新/关闭和 Blueprint 校验，创建被刻意禁止；
- Python Genesis 固定从 CV/CVC/CVCV/CCVC 中抽样，概念之间独立造词；
- Python 主演化只注册四个硬编码音系算子；
- 旧句法 assembler 明确不做一致、形态变化或组合语义；
- 三个数据 manifest 的 contentSha256 与 recordCount 均为空。

因此，当前产品还没有“生成了一门语言”。它已经有可信工程地基和一个被正确隔离的旧研究基线。

可复核证据索引：

| 结论 | 仓库证据 |
|---|---|
| LanguageState 仍为 v2，核心字段表达力有限 | `crates/telysta-core/src/state.rs`：`LANGUAGE_STATE_SCHEMA_VERSION`、`FeatureAssertion`、`Construction` |
| 历史仍以完整状态修订为主 | `crates/telysta-core/src/project.rs`：`LanguageEventPayload::StateRevision` |
| Blueprint 能力诚实标记为 planned | `crates/telysta-core/src/blueprint.rs`：内置 registry 与 capability tests |
| Tauri 尚未开放正式 Genesis 创建 | `apps/desktop/src-tauri/src/main.rs`：project commands 与 Blueprint validation |
| Python 造词使用固定音节模板 | `app/domain/lexicon/generator.py`：`CV/CVC/CVCV/CCVC` templates |
| Python 演化只有少量硬编码算子 | `app/engine/evolution.py`：默认 operation registry |
| 旧句子生成不做一致或组合语义 | `app/domain/syntax/assembler.py` |
| 数据尚未形成执行锁 | `data/manifests/*.json`：空 `contentSha256` / `recordCount` |

## 5. 现有路线中正确且应保留的部分

### 5.1 Rust / Python / Tauri 权威边界

ADR-006 的方向正确：

- Rust 管正式状态、规则、模拟、历史和存储；
- Python 做研究、统计、数据处理和对照；
- Tauri/Webview 只调用版本化 Rust 命令；
- LLM 只解析、解释或提议。

Rust 的价值不只是性能，而是收紧状态不变量、取消、并发、迁移和插件边界。没有理由回退为 Python sidecar 双核心。

### 5.2 RegistryBundle

Blueprint、LanguageState、RuleSpec 和 UI 使用同一特征合同是必要条件。ADR-008 应保留分域 registry，但接受前还应明确：

- feature 的 domain、scope、value、dependency 和 incompatibility；
- realization requirements，即某特征要由哪些范式、构式或音系对象实现；
- cross-domain constraints；
- evidence coverage 和缺失说明；
- compiler capability；
- 离线 payload 的精确组成与 bundle hash；
- 旧项目如何重验和迁移。

注册表只能定义可表达性，不能把类型学数据库变成一套普遍语法。

### 5.3 GenesisArtifact

正式项目只能来自编译与完整重验后的产物，这个信任边界正确。Genesis gate 还必须证明“可使用”，而不只是“没有悬空引用”。

建议将候选生命周期显式分为：

~~~text
UnverifiedCandidate
→ locally validated candidate
→ usage probes
→ candidate comparison
→ user selection
→ VerifiedGenesisArtifact
→ atomic project creation
~~~

来自磁盘或 IPC 的任何候选都必须重新验证；内存私有构造器不是持久化信任机制。

### 5.4 ChangeSet 与 UsageCorpus 分离

ADR-009 对结构状态、使用观察和派生统计的区分正确。ChangeSet 适合提交原子结构变化，但不能承担变化发生前的全部过程。必须补充“竞争变体尚未成为结构”的表示。

### 5.5 可复现底座仍需科学化

当前底座能证明工程确定性，尚不能单独证明模型可信：

- v2 的 `StateRevision` 记录变化后的完整状态，能回放结果，却不能验证哪条规则、哪个环境、哪个社群与哪次重分析造成了变化；
- `RngTree` 的路径隔离方向正确，但还应锁定 RNG 算法、分布变换版本与决策级路径，增加 known-answer tests、统计质量说明和 counter 溢出处理；
- 已提交历史应重放 typed effects，而不是重新抽样；RNG 用于重跑编译或实验，不能在 replay 中重新决定事实；
- 数据引用验证不能只检查 dataset ID，还必须在锁定 payload 中检查 table、record、field、type 与 citation；
- Tauri 在加入文件导入、RulePack、预览内容或插件前，应从通用 capability 收窄到窗口、命令与路径级最小权限。

这些是现有架构的加固项，不构成改回 Python 或引入第二权威核心的理由。counter-based RNG 可作为未来替代或对照路线，但是否替换当前实现应先形成可迁移、可回放的正式决策。[Random123](https://doi.org/10.1145/2063384.2063405)说明了 key/counter 独立流的工程基础；它不能替 Telysta 自动完成模型验证。

## 6. 必须增加的核心抽象

### 6.1 TheoryProfile

每次 Genesis 和历史模拟都必须锁定一套版本化 TheoryProfile：

~~~text
TheoryProfile
├── phonotactic model
├── morphology realization model
├── grammar/semantic model
├── learner or transmission model
├── diffusion model
├── analogy and repair model
├── contact model
├── parameters and priors
├── evidence class and applicability
└── version / semantic hash / limitations
~~~

它不表示“真理”，而表示本次实验采用的可复现理论组合。不同模型必须可并行比较和消融。

### 6.2 PopulationVariationState

自然变化通常不是“命中规则后整门语言瞬间改变”，而是：

~~~text
innovation
→ old/new variants coexist
→ lexical, social, regional and register distributions diverge
→ propagation succeeds, stalls, reverses or dies
→ conventionalization
→ structural reanalysis
→ ChangeSet
~~~

建议区分：

| 对象 | 责任 |
|---|---|
| LanguageStructureState | 已经常规化的音系、语法、词汇和构式 |
| PopulationVariationState | 正在竞争的变体、条件分布、采用率和社群差异 |
| UsageCorpus | 版本化 utterance/token/construction 观察 |
| ChangeProcessState | 过程阶段、模型、参数、证据和停止条件 |
| HistoryLedger | 观察、推断、失败、常规化和最终结构事件 |

这不是引入第二个生产写入者。它们仍由 Rust 和 StateTransaction 管理。但其持久化身份、hash 与 replay 语义必须先由 ADR 决定，不能藏在临时缓存中。

### 6.3 最小双向 Grammar IR

Grammar/Discourse IR 不能整体推迟到 M4。M1 就必须拥有一个很小但真实的双向核心：

- typed semantic frames 与 arguments；
- three core constructions；
- nominal and verbal paradigm；
- agreement/linearization/selection；
- generate(meaning)；
- parse(utterance)；
- intended meaning 必须出现在分析集合中，核心角色不得丢失；
- 可生成符合 Leipzig 规范的 IGT。

解析可能有歧义，因此 round trip 检查的是语义等价与目标读法可恢复，不要求只有一个分析。

### 6.4 四条执行管线必须分离

~~~text
immutable raw CLDF payload
→ versioned transform
→ empirical PriorPack

Blueprint + TheoryProfile + RegistryBundle
→ Rust constraint compiler
→ CandidatePortfolio
→ independent evaluator
→ VerifiedGenesisArtifact

Verified LanguageState + TheoryProfile + RunContext
→ Proposal / ProposedChangeSet
→ verifier + reducer
→ committed event log

ExperimentSpec
→ batch runner
→ calibration / sensitivity / ablation / corroboration
→ ModelEvidenceBundle
~~~

Genesis 解决初始系统的一致性，历时模拟解决时间、群体和变化机制；二者不能混成一个“随机演化直到像语言”的循环。生成器与评价器可共享硬不变量，但评价器必须有独立指标、数据分区和失败条件，不能让编译器用自己的启发式证明自己自然。PriorPack 必须可替换、可关闭，数据库频率不能偷偷变成硬规则。

## 7. 推荐的 Genesis 生成逻辑

顺序式“先音系、再词汇、再语法”可以作为模块边界，不能成为不可回退的一次性流水线。推荐改为跨域约束求解：

~~~text
Blueprint + TheoryProfile + RegistryBundle + locked data
    ↓
resolve capabilities and classify every assumption
    ↓
sample family/area-aware priors and generate several system skeletons
    ↓
jointly compile phonology/prosody, morphology, constructions and meanings
    ↓
build roots, lexeme families, senses, paradigms and realizations
    ↓
generate diagnostic usage corpus
    ↓
analyse generated forms and expose cross-domain conflicts
    ↓
backtrack, repair or reject
    ↓
produce a Pareto candidate set with entity-level explanations
    ↓
user selects a candidate
    ↓
seal VerifiedGenesisArtifact
~~~

### 7.1 音系

推荐分层：

~~~text
underlying segments
→ syllabification and prosody
→ morphophonology
→ surface phonemes
→ allophonic realization
→ phonetic plan
~~~

这是研究分层，不能把图当成适用于所有 profile 的唯一执行次序。当前候选
阶段合同统一见 [ADR-014 §4.6.1](./adr/ADR-014-meaning-grammar-lexical-identity-realization-authority.md#461-发音计划的候选边界)：
区分供规则读取的结构韵律与话语韵律，明确依赖、失效/重算与有限次序。

- 有序上下文规则可以使用有限状态关系；
- phonotactic hard constraints 与梯度偏好分开；
- MaxEnt 可作为一个可替换 PhonotacticModel，不是自然度真理；
- inventory 不是独立音素抽样结果，必须检查对立、系列、分布、边界和韵律互动；
- 同一 IPA 形式可能有不同底层分析，字符串不能替代音系对象。

### 7.2 形态

第一版应使用 typed realization，而不是让随机模型自由发明：

- concatenation、zero exponence、syncretism；
- fusion、portmanteau、reduplication；
- stem alternation、suppletion、defectiveness；
- conditioned allomorphy 与 morphophonology；
- paradigm slots、inflection classes、derivation families。

每个形式必须能回到词素、特征束、范式位置和来源。

### 7.3 句法、语义与语用

应吸收 Grammar Matrix 的工程原则，而不必复制其全部 HPSG：

- typed feature structures；
- declarative constraints；
- language-specific modules；
- generation 与 parsing 共用一套语法；
- 用未参与开发的语言现象和反例 testsuite 检查过生成。

文学能力还需要逐步加入 discourse referents、scope、coreference、information structure、quotation、ellipsis、register 和 pragmatic inference。它们不能用词汇数量代替。

### 7.4 Iterated learning

迭代学习只能作为默认关闭的 Research TheoryProfile。实验表明文化传递能产生可学习结构，但后续工作也表明结构来自可压缩性与表达性的共同压力。

必须固定 learner prior、bottleneck、teacher count、communication task 和 stopping rule，并至少做：

- 无传递对照；
- 单代与多代对照；
- 单教师与多教师对照；
- 不同表达压力对照；
- 关闭表达压力时检查是否退化为形式合并。

不能把任何涌现结构自动解释为自然语言普遍规律。

## 8. 推荐的历时变化逻辑

### 8.1 三类音变 profile

首个严谨版本至少区分：

1. categorical regular change；
2. lexically diffusing change；
3. socially diffusing variation。

S 曲线是结果形状，不是传播原因。模型必须说明选择、网络、年龄、身份、频率或接触等机制，并允许变化失败、残留、逆转与竞争。

### 8.2 结构变化的提交边界

~~~text
InnovationProposal
→ Variant introduced in a typed environment
→ Usage/Propagation observations
→ model-specific competition
→ Conventionalization decision
→ reanalysis / analogy / repair
→ atomic ChangeSet
→ LanguageStructureState
~~~

ChangeSet 只提交已达到模型定义的结构影响。没有成功传播的创新也必须留下可审计研究记录，但不能伪装成 LanguageState 变化。

### 8.3 语法化与构式变化

语法化不能是 typology flag 随机翻转。它必须从已有 lexeme/construction 和使用上下文出发，同时记录：

- form and meaning changes；
- host-class expansion；
- frequency and register evidence；
- phonological reduction；
- morphosyntactic reanalysis；
- analogy and competing constructions；
- pathway evidence and exceptions。

TheoryProfile 应允许构式化、频率驱动或其他假说，并能关闭其中任一机制。

### 8.4 谱系、波状扩散与接触

纯树不足以表示方言连续体和重叠创新。推荐：

~~~text
Genealogy DAG
+ Community network
+ time-bounded contact edges
+ innovation diffusion regions
~~~

借词事件必须保存 donor community、source lexeme/sense、contact time、perception mapping、phonotactic repair、morphological integration、register/domain 和 adoption history，不能只复制字符串。

## 9. 数据与统计路线

### 9.1 当前 manifest 的阻断问题

现有 manifest 只能作为 catalog，不能作为可复现实验输入：

- PHOIBLE 标为 2.0，但 URI 10.5281/zenodo.2562766 是概念 DOI；CLDF 2.0.1 的精确版本 DOI 是 10.5281/zenodo.2677911；
- Grambank 标为 1.0.3，但 URI 10.5281/zenodo.7740139 是概念 DOI；1.0.3 的精确版本 DOI 是 10.5281/zenodo.7844558；
- Concepticon 3.4.0 的 CLDF DOI 10.5281/zenodo.14923561 与版本相符；
- 2026-10-12 独立 AI 实证复审补充：上述 Concepticon 发布物是 CLDF Wordlist，
  不是普通 JSON；catalog 已纠正 format。PHOIBLE 网站声明 CC-BY-SA-3.0，
  [CLDF 2.0.1 发布 API](https://zenodo.org/api/records/2677911) 声明 cc-by-3.0，
  这是来源冲突，尚未查归档内许可；不能据 API 较宽声明直接放宽适用许可。
  当前 PHOIBLE catalog 保留网站标签并记录未决来源，执行 lock 前必须解决。
- 三者的 contentSha256 与 recordCount 均为空；
- 尚无项目级样本选择、过滤、转换、feature 映射和输出 hash。

恢复实现后，任何进入 compiler/calibration 的数据切片都必须锁定：

- exact version DOI；
- 原始 payload SHA-256；
- license and distribution decision；
- source IDs，以及适用时的 doculect IDs；概念/映射切片记录 concept set、
  source list 与转换谱系等对应单位；
- sampling manifest；
- transformation code/version/hash；
- transformed payload hash；
- missingness and exclusion report；
- limitations and intended use。

PHOIBLE 的 CC-BY-SA 许可还需要明确衍生数据与发布物的分发决策。

### 9.2 各数据源的正确用途

| 资源 | 可以支持 | 不能证明 |
|---|---|---|
| PHOIBLE | 来源特定 inventory 与 segment feature 观察 | 随机拼出的 inventory 就是自然音系 |
| CLTS | 音标规范化和跨资源映射 | 某一语言唯一正确的音位分析 |
| Grambank | 语法特征分布、谱系与区域约束 | 共现关系是因果规律 |
| Concepticon | 概念 ID、词表任务和 gloss 对齐 | 人类意义空间只有一种切分 |
| CLICS | colexification 与语义关联候选 | 某语义变化的方向与原因 |
| WOLD | 借词实例、来源和可借性观察 | 普适固定借词概率 |
| Glottolog | 稳定 languoid ID、分类与来源 | 分类永远不变或没有争议 |

语言结构观察应保留来源/doculect 单位，控制 family 与 area，报告缺失值，避免
大语系重复加权，并按主张选择 family-held-out 与 area-held-out 验证。
2026-10-12 复审收窄原“所有 prior”表述：Concepticon 等概念/映射数据须按
concept set、source list 与转换谱系声明单位；标签语言不是目标 doculect。
其表结构依据为[官方 v3.4.0 元数据](https://raw.githubusercontent.com/concepticon/concepticon-cldf/v3.4.0/cldf/Wordlist-metadata.json)，
不据 metadata extent 冒充本轮实际重计记录数。

## 10. 科学验证路线

### 10.1 建立 ODD + TRACE 模型档案

每个 TheoryProfile 应提供一个可随版本发布的模型档案：

- Purpose and intended use；
- entities, state variables and scales；
- process overview and scheduling；
- design concepts and submodels；
- initialization and input data；
- parameterization and calibration；
- software verification；
- sensitivity and uncertainty；
- validation results；
- applicability domain and known failures。

ODD 负责让模拟模型可描述、可复现；TRACE 负责记录设计、实现、测试、校准、分析与适用性。ADR 和单元测试不能替代它们。

建议把上述材料做成三个版本化工件，而不是散落在文档和 CI 日志中：

| 工件 | 内容 |
|---|---|
| TheoryProfile / ModelProfile | 机制、调度、参数、先验、适用域、已知失败和 semantic hash |
| ExperimentSpec | 校准/验证数据分区、seed/replicate、对照、指标、阈值和预注册预期 |
| ModelEvidenceBundle | ODD、TRACE、数据锁、测试、回放、校准、敏感性、消融、held-out 与专家异议 |

固定术语也必须分开：**verification** 是代码是否正确实现已声明模型；**calibration** 是用校准数据确定参数；**validation/corroboration** 是在未参与调参的数据或模式上检验适用性；**sensitivity** 是结论对参数和结构假设的依赖；**ablation** 是关闭机制后检查预先声明的贡献。测试通过只能支持 verification。

### 10.2 八层验证

| 层 | 必须回答的问题 |
|---|---|
| V0 软件验证 | 代码是否按合同运行，事务、回放、迁移和 RNG 是否正确？ |
| V1 硬不变量 | 是否存在非法形式、断裂范式、丢失角色、悬空来源？ |
| V2 内部充分性 | 生成和分析能否完成核心交际任务？ |
| V3 经验校准 | 多 seed 分布是否落在目标数据的可接受域？ |
| V4 泛化 | family-held-out、area-held-out 和未见现象是否通过？ |
| V5 因果辨识 | 消融某机制后，相关预测是否消失？替代模型是否同样解释结果？ |
| V6 历史重建 | 能否从子语言区分同源、借词、残留和偶然相似？ |
| V7 人与产品 | 专家盲审和真实用户任务是否成功？ |

### 10.3 强制对照

每个主要模型至少与以下基线比较：

- 无约束随机生成；
- 只有硬约束、没有经验先验；
- 独立类型学特征采样；
- Python legacy；
- 关闭 social diffusion；
- 关闭 frequency；
- 关闭 analogy/repair；
- 另一个可解释同一现象的 TheoryProfile。

敏感性分析必须探索联合参数空间，不能只逐项改变一个参数。应同时报告 output uncertainty 和 input sensitivity。

高维参数可先用 Morris/elementary effects 筛查，再对重要参数使用 Sobol 或其他全局方法；昂贵模型使用 surrogate 时，surrogate 自身也必须验证。校准不能只追逐单个 inventory 大小，而应以多层模式共同约束 inventory、phonotactics、范式、构式任务、规则对应、扩散、谱系和接触；这与 [pattern-oriented modelling](https://doi.org/10.1126/science.1116681) 用多个尺度模式排除等效错误机制的原则一致。

### 10.4 必备反例

首批反例至少覆盖：

- 非局部和谐、词素边界与音节边界；
- feeding、bleeding、counterfeeding；
- merger、split、phonemicization 与 inventory 同步；
- zero、syncretism、portmanteau、suppletion、defective paradigm；
- analyse(realize(analysis)) 语义等价；
- negation/quantifier scope、valency alternation、reference tracking；
- 创新传播失败、残留、逆转和多曲线形状；
- 高频领先与高频保守由不同模型产生；
- 两社群共享部分而非全部创新；
- 接触创新跨越树边，借词经过目标音系和形态整合。

## 11. UI/UX 路线

### 11.1 当前界面判定

当前静态页面是合格的 Tauri 技术 Spike，不是产品 UI：

- 需要手输项目目录；
- Blueprint 以原始 JSON 编辑；
- 结果主要是 hash 和对象计数；
- 没有创建、候选比较、历史运行、变化解释或实际语言使用任务；
- 没有 Quick / Expert / Research 产品工作流证据。

不应现在做大规模视觉精修，但应该立即做低保真任务原型和用户研究。

### 11.2 推荐主流程

~~~text
Home / recent projects
→ define creative and research intent
→ capability and assumption review
→ generate and compare candidates
→ inspect failures and trade-offs
→ select and seal Genesis
→ create communities and timeline
→ dry-run / run / cancel / resume simulation
→ inspect forms, rules, events and provenance
→ test communication and literary tasks
→ export grammar, dictionary, IGT, family and experiment manifest
~~~

Quick、Expert 和 Research 必须共享同一 Blueprint、命令和 LanguageState：

- Quick：用任务和感知语言描述偏好，但显示它们被编译成了什么假设；
- Expert：编辑 typed features、constructions、rules 和 conflicts；
- Research：批量 seed、参数扫描、对照、敏感性和导出 manifest。

模式切换不能复制状态或产生三套业务逻辑。

### 11.3 关键交互

- Candidate Compare：并排比较硬错误、偏好权衡、实现缺口、例词和例句；
- Conflict Resolver：显示锁定冲突、依赖链和可选修复，不静默改用户选择；
- Timeline：显示 planned/running/cancelled/failed/recoverable，允许取消与恢复；
- Provenance Inspector：从词形或句子下钻到分析、规则、事件、数据与 TheoryProfile；
- Quality Lab：以具体失败为入口，不以总分为入口；
- Rule Studio：validate → conflict analysis → dry-run → impact diff → apply；
- Branch/Compare：比较两个候选、时代、分支或模型，不丢失来源；
- Export Preview：文本、IGT、IPA、正字法和语音来自同一分析。

Blueprint 参数不能只是 slider 或 JSON 字段。每项至少展示通俗说明、专业定义、值域、默认值、假设类别、能力状态、影响预览、冲突、来源与 Reset。完整生成不得随连续输入反复触发，应区分低成本预览与显式 Apply。

冲突诊断应返回最小冲突集合、每条约束来源、不可共存原因和若干最小修复方案；硬约束不能静默放松。长任务应持久化为锁定请求的 Job，明确 `Queued → Running → CancelRequested → Cancelled/Failed/Completed`，取消只在安全点生效，并保证不会留下半提交项目。只有存在确定性 checkpoint 才显示 Resume，否则应显示从锁定请求 Restart。

### 11.4 认识论诚实

每个用户可见控制和结果都应带可识别类别：

- Locked hard constraint；
- Empirical prior and coverage；
- Research hypothesis and confidence；
- Creative preference；
- Planned or unavailable capability；
- Simulated observation；
- Inferred explanation；
- User-authored intervention。

不能只用颜色编码；用户必须能查看解释和来源。

### 11.5 可用性与无障碍门

- 以 WCAG 2.2 AA 为最低桌面 Webview 目标；
- 完整键盘路径、可见焦点、正确名称/角色/状态与状态消息；
- 目标尺寸、对比度、缩放/reflow、减少动画、非颜色提示；
- 中英文界面与可扩展本地化，不把英文技术词硬编码进 schema；
- IPA 与组合附加符号字体 fallback、复制和搜索正确；
- 错误信息包含问题、位置、原因、后果和下一步；
- 长任务必须有进度、取消、恢复、后台状态和崩溃恢复；
- 危险变更提供 dry-run、影响范围、确认和可恢复分支。

UI locale、生成语言、正字法和语料语言必须是四个不同概念；界面资源化与 bidi isolation 不能改变项目中的 IPA、正字法或 hash。架空文字规范化应有显式策略，不能未经领域判断统一使用兼容等价规范化。

渐进披露应用于信息层级，不应用于隐藏限制。Quick 模式可以少显示参数，但不能隐藏系统替用户作出的科学假设。

### 11.6 用户研究

至少覆盖以下参与者：

- 严谨的世界观创作者 / conlanger；
- 语言学专家或研究型用户；
- 需要词典、例句、翻译和发音的实际创作者；
- 键盘、低视力和屏幕阅读器用户；这不是前三类用户的可选替代组。

核心任务包括：创建祖语、解决冲突、比较候选、运行并取消演化、重启后恢复或确定性重跑、解释一个现代形式、添加规则并 dry-run、完成一段 IGT、导出可复现实验，以及仅用键盘/屏幕阅读器完成关键路径。中英文切换不得改变 IPA、正字法、状态或 hash。

测量任务完成率、严重错误、恢复成功率、耗时、证据类别理解、重复实验成功率、解释可找到率和无障碍问题。满意度只能作为补充。

## 12. 对现有 ADR 与计划的修改建议

### 12.1 ADR-008

接受前补充：

- bundle 精确包含哪些离线 payload；
- cross-domain realization requirements；
- compiler 与 model capability；
- exact hash 输入；
- registry 与 empirical prior 的边界；
- 旧项目无法取得锁定 payload 时的行为。

### 12.2 ADR-009

接受前补充：

- provisional variation 与 committed structure 的两阶段语义；
- PopulationVariationState / ChangeProcessState 的身份、版本、hash 和 replay；
- immutable UsageCorpus snapshot；
- effect dependencies、precondition 和 reducer migration；
- 失败创新与未常规化过程如何审计；
- v2 ImportedCheckpoint 的机制断裂如何在 UI 显示。

### 12.3 ADR-010

接受前补充：

- UnverifiedCandidate 与 VerifiedGenesisArtifact 的类型边界；
- CandidateSet/CandidateId 和多候选选择；
- compiler/data/registry 版本变化后的重新验证与过期规则；
- 失败、取消、重启和原子创建；
- Genesis usage probes 与 hard/soft gate 的组成；
- generator 与 independent evaluator 的边界，避免生成逻辑自我认证。

### 12.4 新 ADR 或 umbrella 修订

以下任一选择都会影响持久化语义，必须正式决策：

- TheoryProfile 是否为项目锁；
- PopulationVariationState 是独立聚合还是 LanguageState v3 子域；
- Grammar IR 的双向语义和等价判定；
- 模拟的 ODD/TRACE 文档如何与模型版本绑定。

此外应增加科学模型 ADR，明确 ModelProfile、ExperimentSpec、ModelEvidenceBundle、数据分区、参数分布、replicate、指标、敏感性、消融和适用域。它不改变 Rust 单一权威，但决定什么条件下一个模型版本可以被产品声明为“已验证”。

### 12.5 路线图冲突

ROADMAP 的 M1 描述是一个最小社区和一个 ChangeSet；旧 Phase B 描述仍包含两社区和一次接触。应明确：

- M1 的 typed sound change 只是结构、事务、回放纵切，不得宣称真实传播；
- 若 M1 要声称“最小真实变化”，则必须加入竞争变体、UsageObservation、创新失败对照和最小双向 Grammar IR；
- 两社区、分支和接触属于后续 M3，除非只做明确标注的架构 Spike。

## 13. 推荐执行顺序

### R0：继续保持实现暂停，冻结科学合同

完成以下文档决策后才恢复 v3 持久化实现：

1. 接受本审核门和产品承诺边界；
2. 修订 ADR-008/009/010；
3. 决定 TheoryProfile、PopulationVariationState 和双向 Grammar IR；
4. 建立 ODD/TRACE、校准、敏感性、消融和 held-out 模板；
5. 确定 M1 的精确能力声明和反例 testsuite；
6. 修正数据 catalog 的精确版本与执行锁策略。
7. 决定 RNG 算法保留或替换、分布版本与回放兼容策略。

### R1：M0 收口

- 把 Rust/Tauri/CI/合同/fixture 纳入可审查版本基线；
- clean checkout 运行完整门；
- ADR 获得代码所有者与语言学评审；
- 固定一个最小真实数据切片及其完整 hash/抽样/许可记录。

### R2：修订后的 M1 最小纵切

~~~text
Blueprint
→ RegistryBundle + TheoryProfile
→ several Genesis candidates
→ minimal bidirectional Grammar IR and usage probes
→ VerifiedGenesisArtifact
→ create / reopen project
→ introduce one competing variant
→ one failed propagation control
→ one conventionalized typed ChangeSet
→ replay and explain in Tauri
~~~

范围必须保持小：少量音系与韵律、一个名词范式、一个动词范式、三类核心构式、20–40 个锁定概念、一个社区模型和一个 typed sound process。

### R3：共时语言内核

先让语言能稳定分析和表达核心意义，再扩大规则数量：

- phonology/prosody；
- morphology and paradigms；
- constructions and compositional semantics；
- lexical families and senses；
- usage probes and IGT；
- register and minimal discourse。

### R4：可切换历时模型

分别实现并消融 categorical change、lexical diffusion、social diffusion、analogy、constructionalization、grammaticalization 和 semantic shift。每个模型独立版本、参数、证据与适用域。

### R5：家族、接触与重建

加入分支、dialect linkage、migration、contact、borrowing、regular correspondence 和 reconstruction challenge。

### R6：Creator Workbench 与文学任务

在权威纵切稳定后实现完整 Quick/Expert/Research 工作台，用叙事、对话、论证、反事实、引语、多语体和 IGT 验证语言可用性。

TTS 继续后置，必须建立在同一 morphology → phonology → allophony → prosody → phonetic plan 分析上。

## 14. Stop / Go 决策

### 当前允许继续

- 论文与数据源核验；
- ADR 修订；
- ODD/TRACE 和验证 protocol；
- 数据抽样与许可证研究；
- 低保真 UI 任务原型和用户访谈；
- 不改变权威 schema 的实验性 Python 模型。

### 当前停止

- LanguageState v3 持久化语义实现；
- 新生产 ChangeSet/reducer；
- SpeechCommunity 正式 schema；
- 大规模规则扩充；
- 全量外部数据导入；
- 把当前静态 Webview 打磨成正式产品；
- 删除 Python legacy 模块；
- TTS、LLM 自动写状态或任意代码插件。

### 恢复实现的 Go 条件

- ADR-008/009/010 已接受或明确替代；
- TheoryProfile、变体层和双向 Grammar IR 有正式边界；
- M1 有固定数据、反例、对照和能力声明；
- 历史 G0 的 clean-checkout 条件可复现（现行归入 G0A）；
- 语言学和架构评审未发现阻断性表示缺口。

## 15. 参考依据与对本项目的含义

### 语言生成、变化与语法

- [Yu 2023, The Actuation Problem](https://doi.org/10.1146/annurev-linguistics-031120-101336)：语言变化启动需要个体与群体多层因素，综合个体模型仍缺失；支持 TheoryProfile 而非唯一模型。
- [Blythe & Croft 2012, S-Curves and the Mechanisms of Propagation](https://doi.org/10.1353/lan.2012.0027)：S 曲线需要具体传播与选择机制；曲线本身不是解释。
- [Blythe & Croft 2021, How individuals change language](https://doi.org/10.1371/journal.pone.0252582)：部分历史数据更支持终身渐进调整与网络效应，而不是只靠儿童习得错误。
- [Bybee 2006, From Usage to Grammar](https://doi.org/10.1353/lan.2006.0186)：频率影响表征、类别与变化，但不提供一个普适常数。
- [Kaplan & Kay 1994, Regular Models of Phonological Rule Systems](https://aclanthology.org/J94-3001/)：有序上下文音系规则可用 regular relations 统一生成与识别。
- [Hayes & Wilson 2008, A Maximum Entropy Model of Phonotactics](https://doi.org/10.1162/ling.2008.39.3.379)：加权约束可表示 categorical 与 gradient phonotactics；应作为可替换模型。
- [Traugott 2014, Toward a constructional framework for research on language change](https://doi.org/10.1075/cogls.1.1.01tra)：历史变化应同时跟踪形式与意义，并考虑 schema、类推和渐进重分析。
- [Bender, Flickinger & Oepen 2002, Grammar Matrix](https://aclanthology.org/W02-1502/) 与 [Bender et al. 2010](https://aclanthology.org/P10-4001/)：类型化、模块化、可定制 precision grammar 是可行工程路线，但只是 starter grammar。
- [Kirby, Cornish & Smith 2008](https://doi.org/10.1073/pnas.0707835105)：文化传递可产生更可学和更结构化的人工语言。
- [Kirby et al. 2015](https://doi.org/10.1016/j.cognition.2015.03.016)：结构来自可压缩性与表达性的权衡，不能只优化学习压缩。
- [Leipzig Glossing Rules](https://www.eva.mpg.de/lingua/resources/glossing-rules.php)：为专家可审计 IGT 提供通行约定。

### 数据与互操作

- [PHOIBLE FAQ](https://phoible.org/faq)：inventory 是来源特定 doculect，存在同语言多 inventory 与采样问题。
- [CLTS](https://clts.clld.org/)：为不同音标和数据集提供标准化 catalog 与映射。
- [Grambank 论文](https://doi.org/10.1126/sciadv.adg6175)：语法多样性受谱系和地理制约，语言样本不是独立同分布数据点。
- [Concepticon](https://concepticon.clld.org/)：核心价值是概念列表映射判断，不是用短 gloss 替代完整语义。
- [CLICS](https://www.nature.com/articles/s41597-019-0341-x)：支持可复现 colexification 分析，但同步关联不能自动给出变化方向。
- [WOLD](https://wold.clld.org/)：提供专家整理的借词、donor 和来源信息，样本范围必须公开。
- [CLDF](https://cldf.clld.org/)：通过标准数据格式把数据库与分析工具解耦，支持验证和复用。
- [FAIR Principles](https://doi.org/10.1038/sdata.2016.18)：数据应可发现、可访问、可互操作、可复用；版本、元数据和机器可读性不可省略。

### 模拟科学与产品

- [ODD 2020](https://www.jasss.org/23/2/7.html)：用标准结构描述模拟目的、实体、调度、初始化、输入和子模型，提升复现与评审能力。
- [TRACE 2014](https://doi.org/10.1016/j.ecolmodel.2014.01.018)：模型质量需要贯穿设计、实现、测试、校准、分析和适用性，而不是发布前一次验证。
- [Sargent 2013, Verification and validation of simulation models](https://doi.org/10.1057/jos.2012.20)：概念模型有效性、实现验证、数据有效性与运行有效性必须分别建立证据。
- [Grimm et al. 2005, Pattern-oriented modeling](https://doi.org/10.1126/science.1116681)：用跨尺度多模式约束模型，降低多套错误机制拟合同一结果的风险。
- [Saltelli et al., sensitivity analysis review](https://arxiv.org/abs/1711.11359)：逐项局部变化不足以支撑复杂模型，应区分不确定性和敏感性并探索联合空间。
- [W3C PROV-DM](https://www.w3.org/TR/prov-dm/)：可用 Entity、Activity、Agent 与 derivation 组织 Blueprint、产物、规则、数据和事件的解释链。
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/)：为键盘、焦点、状态消息、错误帮助、目标尺寸、对比度和完整流程提供正式无障碍门。
- [Progressive Disclosure for algorithmic transparency](https://doi.org/10.1145/3374218)：分层披露可帮助用户建立系统心智模型；对 Telysta 的含义是逐层展示复杂性，而非隐藏假设。

## 16. 最终评语

现有计划已经避开了几个最危险的方向：没有把 LLM 设为真值、没有继续承诺 Python 双核心、没有把自然度压成单分数，也没有允许 Webview 拼装正式状态。这些是值得保留的成果。

但如果不补充 TheoryProfile、PopulationVariationState、最小双向 Grammar IR 和正式科学验证生命周期，项目很可能最终成为：

> 一个工程上可靠、规则可回放、界面可操作，但语言变化仍过于机械的高级规则执行器。

补完这些边界后，Telysta 才有机会成为专业语言学家愿意认真评审、创作者愿意长期使用的语言历史实验与创作平台。

## 17. 2026-10-12 路线复审补充

本节为本轮研究记录；上文保留原始评审背景。当前执行范围只以
[产品计划](./PRODUCT_DEVELOPMENT_PLAN.md#13-2026-10-12-用户目标落实与路线复审)为准。

### 研究与实践依据

| 来源 | 本轮已核对范围 | 对 Telysta 的含义与限制 |
|---|---|---|
| [Moscoso Del Prado Martin & Salhan 2026](https://aclanthology.org/2026.scil-main.14/)，DOI 10.18653/v1/2026.scil-main.14 | 论文元数据与摘要；全文方法尚待复核 | 随机历时模型可复现部分频率统计；加入频率/库存稳定假设影响拟合。属于 research hypothesis，不能仅因统计拟合就认定历史机制真实；列入 G4 对照模型候选 |
| [McGahay 2025](https://www.isca-archive.org/interspeech_2025/mcgahay25_interspeech.html) | 官方摘要 | 感知混淆优化提供元音系统变化的局部模型候选；不是所有音系、语法或社会变化的普遍原因 |
| [Unicode 18 UAX #15 rev58](https://www.unicode.org/reports/tr15/tr15-58.html)、[UAX #29 rev49](https://www.unicode.org/reports/tr29/tr29-49.html) | 官方规范相关章节 | normalization、文本 cluster 与语言 grapheme 分开；版本锁定、source/span 对齐进入正字法评审；不宣称当前运行库已支持 Unicode 18 |
| [Rubino et al. 2024](https://aclanthology.org/2024.findings-naacl.215/) | 官方摘要 | 历史词形归一与现代化可区分；支持单独设计保守拼写与显式改革，不把历史文本模型当造语正确性证明 |
| [Lexibank](https://lexibank.clld.org/)与 [CLDF 1.3](https://cldf.clld.org/) | 官方数据入口与格式说明 | 采用稳定概念/语言/音段引用、独立数据与转换锁；采样单位及版本逐项固定，不从网站当前版本自动替换项目锁 |
| [Leipzig Glossing Rules](https://www.eva.mpg.de/lingua/resources/glossing-rules.php) | 规则与分析边界 | IGT 是分析的展示；同图投影且支持非一对一实现。规范本身不证明分析正确 |
| [eSpeak NG](https://github.com/espeak-ng/espeak-ng/blob/master/docs/index.md)及 [GPL-3.0 许可](https://github.com/espeak-ng/espeak-ng/blob/master/COPYING) | 文档入口、音素输入和许可证 | 可作本地语音研究参考；尚未决定分发，不能直接加入 MIT 客户端。先定义 typed pronunciation adapter 与受限试听覆盖，独立评估音质与许可 |
| [Rosé Pine palette](https://rosepinetheme.com/palette/)与 [WCAG 2.2](https://www.w3.org/TR/WCAG22/) | 官方配色与无障碍标准 | 色彩是作者 creative preference；逐组合核验对比度、焦点、键盘和中文/IPA 显示，不能把主题名当成可访问性证明 |

上述资料截至 2026-10-12 检索；未下载和锁定论文数据，不形成生产数据依赖。
新规则进入默认包前仍需正/反例、组合顺序、replay 与独立评价。

2026-10-14 再核对官方 UAX #15 rev58，仍为 Unicode 18.0.0；本机 Python
`unicodedata.unidata_version` 为 15.1.0。新增有限正字法 oracle 不执行 normalization，
不拿运行库版本差异冒充 Unicode 18 conformance。上述标准参照与具体实现锁继续分开。

2026-10-15 发音前置复核：[KlattGrid 官方说明](https://www.fon.hum.uva.nl/praat/manual/KlattGrid.html)
明确分开声源、滤波及两者交互的时变参数；这里只读网页说明，没有运行 Praat、
复制实现或分发依赖。它说明渲染参数需要独立合同，不证明语言音系或任何默认
声学值正确。[Yan et al. 2021](https://arxiv.org/abs/2107.11628v1) 本轮只读官方摘要，
用七种语言的 ASR 研究语言特定 phone–phoneme 映射；不是造语/TTS 的正确性证明，
不采用其模型或数据。[Kaplan & Kay 1994](https://aclanthology.org/J94-3001/) 重新
核对元数据，没有在本轮重读全文；规则系统仍是候选方法，不能替代阶段依赖合同。
新增规则示例均为人工 profile 偏好；当前音系引用检查不验证 phones 或音频。

### 本地资料库

已盘点 `references/` 的文件种类；本轮抽读 Sindarin 教程的版权/目录页、
《律史前月读教程》文本、Laloxv15 手册前七个 PDF 页及《浅谈手语基本语序研究
方法》前六页，未宣称已通读全部教材。印欧语入门的前九页无法
提取文本，需渲染/OCR 后再审阅。资料内容有自然语言教材、架空语言设定、
民间译本及与本项目无关的系统排障笔记，不可整体当成同质语言学证据。

施婉萍《浅谈手语基本语序研究方法》（2018，DOI
[10.12677/ml.2018.61013](https://doi.org/10.12677/ml.2018.61013)；本地 PDF
第 1–6 页）讨论采样定义、形态/空间/角色转换对表面语序研究的影响。本地
第 2 页标注 CC BY 4.0，DOI 网页本轮未能访问。它提示 TaskPack 需控制角色、
语境与诱导任务，不能仅用 SOV/SVO 标签代替 grammar capability；不会把论文
对手语的分析直接移植成有声架空语言规则，也不宣称当前产品支持手语。

Laloxv15 手册的构词、分类借词和语法说明用来观察作者如何组织规则与示例；
其中学习难度和普适性的自述不作为经验结论。当前仅记录阅读，不抽取词表、
字体或成体系的规则进入生成器；分发许可尚未核实。

- 自然语言教材：用于设计结构边界和反例，优先核对原书、页码与版本。
- 人造语言教程：用于学习发音说明、范式、练习和词典组织；游戏设定与
  推测语法归 creative preference/research hypothesis，不升级为经验先验。
- 词典与字体：先记来源、hash 与许可，再决定是否允许抽取或分发；
  不把已有作品词汇直接作为生成器默认词表。
- 语言说明验收：读者能够据导出说明读出支持的形式、构造新句子，追溯
  词源及一条变化，并知道未支持的表达；不靠篇幅或词数证明语言可用。

### 规划评审决定

保留 Rust 唯一权威、Tauri 客户端和 WS-1 最小纵切。优先修复当前存储边界，
同时准备双向语法与作者任务的评审材料。基础文档随 R2 交付；基础试听在
STORY-10 验证后先行，完整表现性语音后置。此处没有接受任何 ADR 或 Gate。
