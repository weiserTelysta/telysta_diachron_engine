---
document_type: research
decision_status: not-applicable
implementation_status: verified
normative_scope: current
last_verified: 2026-07-18
source_revision: fa7468b68ba60984ad7c416560dccb8f19a60aa7
owner: unassigned
reviewers: []
---

# Telysta 语言学与架构审计（2026-07-18）

## 1. 结论

Telysta 的目标定义和长期方向是正确的：Rust 作为唯一生产权威、版本化状态与随机流、可回放事件、可追溯证据、Tauri 薄客户端、LLM 只提案不提交，这些原则能够支撑一个专业语言模拟器。

但当前成果还不能被称为“已生成一门可使用的语言”，也不能被称为“已实现可靠的历时语言模拟”。当前 Rust 成果是产品化地基和最小状态/存储 spike；Python 成果是 legacy 基线与研究原型。后者已经暴露出系统性的语言学错误，前者尚未具备足够的领域表达力来替代它。

本次审计的核心判断是：

1. `g → gg`、缺少某些词类、句子主要是 IPA 拼接只是表层症状。
2. 还存在频率数据误用、语法化伪机制、类推对象错误、词汇语义静默丢失、形态类型单轴演化、同音词强制修复、历史规则被重新用作共时规则、生成过程修改语法状态等更严重的问题。
3. 其中相当一部分确实由架构促成：实体职责混合、字符串优先、写入点分散、验证边界过宽、事件类型过载、重复管线和验收目标过弱。
4. 在 G0A/G0B 与跨域实现合同关闭前继续增加规则数量，只会扩大不可回放和不可证伪的行为面。
5. 正确路径不是把更多“看起来像语言”的规则堆到 Python 中，而是先冻结 Meaning/Grammar/Realization 权威，再以 Rust 完成一个小而完整、双向可验证的语言纵切。

审计开始时工作树有 73 个已修改或未跟踪条目，因此本文只记录当前可观察事实，不把该工作树视为 clean-checkout 基线，也不授权 LanguageState v3 或生产生成器实现。

## 2. 审计口径

### 2.1 四类声明

| 类别 | 含义 | 产品中的处理方式 |
|---|---|---|
| 硬约束 | 软件或已声明能力绝不能违反的条件 | schema、validator、transaction 和测试必须拒绝违反项 |
| 经验先验 | 数据显示常见，但不是普遍律 | 版本化 `PriorPack`，记录数据、抽样、置信区间和限制 |
| 研究假设 | 对机制的可竞争解释 | 版本化 `TheoryProfile`，可替换、可消融、可比较 |
| 创作偏好 | 用户希望的听感、风格、文学或世界观效果 | 只参与候选筛选/排序，不伪装成语言学因果律 |

“自然”“优雅”“寒冷感”“像托尔金”都不是硬约束。类型学频率也不能单独证明某个生成结果正确。

### 2.2 严重度

| 级别 | 定义 |
|---|---|
| P0 | 会让权威状态、意义、回放或产品声明不可信；进入生产领域实现前必须解决 |
| P1 | 会系统性降低语言可用性、类型学覆盖或科学解释力；WS-1/R2 前必须关闭 |
| P2 | 影响文学、语音、编辑体验或规模；在核心语言可执行后处理 |

### 2.3 当前与目标的边界

- 下文指出的 Python 问题是 legacy/research 实现缺陷，不等于 Rust 已经生产化了这些行为。
- 下文指出的 Rust v2 表达限制是已知的 target gap；只要它仍被严格限制为 spike，就不是已交付能力的回归。
- 一旦用这些结构承载正式 Genesis、语言变化或用户 canon，它们就会变成 P0 数据迁移风险。

## 3. 架构如何放大语言学错误

当前最危险的失效链是：

```text
IPA/词类/语义字符串 + 职责混合的可变对象
        ↓
多个 engine、branch、LLM、realizer 直接修改状态
        ↓
校验器允许空词形、无核词形，或把结构错误降为 warning
        ↓
语法化、同音修复、形态变化被记成 SOUND_CHANGE，
或 Rust v2 只保存一份完整替换状态
        ↓
测试只断言“非空”“不同”“能回放”
        ↓
错误获得合法历史、稳定 hash 和看似通过的测试
```

`/go/ → /g/ → /gg/` 正是这条链的实例：无最后音节核保护的元音删除产生 `/g/`，过宽 validator 接受无核形式，同音消解再用字符串自连接生成 `/gg/`，最后把形态策略记录成 `SOUND_CHANGE`。

因此，修复某一个输出字符串不够。必须同时修复领域身份、写入权限、验证时机、事件语义和验收任务。

## 4. P0 问题台账

### P0-01：当前证据基线不能支持产品完成声明

**证据**

- [STATUS.md](./STATUS.md) 将 G0A 标为 blocked；G0B 也未关闭。
- ADR-007 至 ADR-013 的关键决策仍有 Proposed 或独立审批缺口。
- 当前工作树不是 clean checkout；审计开始时有 73 个状态条目。
- Rust `LanguageState` v2 与 Tauri demo 已实现地基能力，但 `VerifiedGenesisArtifact`、生产 Genesis compiler、Meaning/Grammar 纵切尚未实现。

**影响**

当前只能声称“具备可验证地基和研究原型”，不能声称“已经生成语言”或“已经模拟真实变化”。

**解决**

先关闭 G0A；并在 G0B 冻结 Meaning/Grammar/Realization 权威、能力矩阵、TaskPack 和真实数据切片。任何新功能必须引用对应 GateEvidence。

**验收**

- fresh checkout 可复现 Python/Rust/docs 全门；
- ADR owner、reviewer、依赖和接受状态无歧义；
- UI、README 和 demo 不把 `planned` 能力显示为 supported；
- 产品声明只来自版本化证据。

### P0-02：词位、词义、词形、词素、范式与历时阶段没有统一身份合同

**证据**

- Python `LexicalEntity` 同时承载 concept、POS、当前 IPA、历史 IPA、词频、词类、语法化阶段、语义 primes 和存亡状态。
- Rust v2 已分出 `Lexeme`、`Sense`、`Morpheme`，但 `Morpheme` 只有 gloss；`Lexeme.morpheme_ids` 和 `Construction.morpheme_ids` 是 `BTreeSet`，无法表示词素顺序、重复、零实现或不连续实现。
- `ProvenanceLedger` 当前每个实体只保留一项 provenance，不能表达多来源、借入、混成和连续多事件词源。

**影响**

同一个对象既是词典条目又是表层词形和历史阶段，导致：

- 音变、语义变化、词汇替换和语法化互相覆盖；
- 类推找不到范式格位，只能退化成“音系相似词传播”；
- compounding 只能剪贴 IPA；
- 不可能可靠生成 IGT、分析词形或回溯 etymon；
- schema 一旦持久化，之后分拆会引发大规模迁移。

**解决**

在实现前新增并接受 Meaning/Grammar/Realization ADR，至少定义：

```text
Lexeme ──owns──> Sense
Lexeme ──participates-in──> Paradigm / Construction
WordForm ──realizes──> Lexeme + FeatureBundle
Morph/MorphemeOccurrence ──ordered-in──> WordForm
SurfaceForm ──derived-from──> MorphologicalRepresentation
Etymon/ChangeEvent ──derives──> entity or form
```

顺序和重复必须用有序 occurrence 序列表示，不能用集合。零实现、融合、异形态、同形异义、缺陷范式和不连续形态必须有显式表示或明确列为不支持。

**验收**

- 同一词位的多词形和多词义不会复制或覆盖身份；
- 两个词位可表达同一 comparative concept；一个词位可有多个 sense；
- 复合词能够保留父词素顺序、边界和来源；
- `lexeme + feature bundle ↔ analysis ↔ surface` 在支持域内双向往返；
- schema 迁移、semantic hash 和 replay 语义由 Accepted ADR 决定。

### P0-03：权威写入和事件语义仍不足以解释“发生了什么”

**证据**

- Python `EvolutionEngine`、branch、grammaticalization 和 LLM orchestration 仍有直接字段修改。
- `grammaticalization_stage`、`word_class`、`typology.morpheme_table`、`semantic_primes` 和 `semantic_era_log` 可在完整事件提交之外变化。
- Python `DeltaEventType.SOUND_CHANGE` 被用于同音叠词、加缀和语法化结果。
- 当前 8 项 strict xfail 已固定回放缺陷：snapshot loader 忽略 DAG、Swadesh 保护集和 typology；event decoder 丢失 parent/source/edge/concept；compound 双亲来源和 epoch injection 无法从事件日志恢复。
- Rust v2 `StateRevision` 保存一份完整替换状态和自由文本 reason；它能回放“结果状态”，但不能证明音变、重分析、类推、借词或语义变化的机制。
- `ProjectRuntime::commit_history` 接收整份 `ProjectHistory`；当前只把新 history 的 project/run ID 与 session 比较，再检查可回放性和 expected history hash。它没有比较当前历史前缀、genesis、完整 `RunContext`、parent head 或 seed/data/rule locks；保留同一 project/run ID 的调用者可提交另一段可回放历史。

**影响**

可回放不等于可解释。两次完全不同的语言学操作可产生同一最终状态；中间因果、规则环境、输入对象和证据会丢失。未来开放写命令后，整历史替换还可能形成合法但改写了既有 lineage 的提交。

**解决**

- Rust 成为唯一写入者，所有变化经过 `Proposal → validator → typed ChangeSet → reducer → StateTransaction`。
- 至少区分 SoundChange、MorphophonologicalChange、Reanalysis、AnalogicalChange、SemanticChange、LexicalReplacement、Borrowing、ConstructionChange、OrthographicChange 和 AuthorialOverride。
- 事件记录对象 ID、前后结构、typed environment、rule/data/theory 版本、RngTree 路径、证据、失败/未采用理由和 replay contract。
- `commit_history` 在正式写 API 前改为 `baseHistoryHash + OperationId + typed ChangeSet`，只发布 application service/reducer 构造的后继 head；要求 genesis、完整 `RunContext` 和历史前缀不变。

**验收**

- 每个 semantic-hash 字段都有唯一 reducer 写路径；
- mutation coverage 测试能检测绕过 transaction 的写入；
- 同一输入锁、RNG 路径和规则包产生相同 ChangeSet/hash；
- 任意替换 genesis、换 seed/data/rule lock、删改/换序事件或提交非前缀 history 都会被拒绝；
- 查询和句子生成不改变语言 semantic hash。

### P0-04：音系不变量不足，非法词形能成为权威结果

**证据**

- `WellFormednessValidator._is_legal([])` 返回合法。
- 无元音序列被当作“空核音节”，但空核本身不被拒绝。
- 任意单辅音 onset/coda 默认通过；未知 token 可穿过 tokenizer。
- `MidVowelDropOperator` 无“至少保留一个可许可音节核”后置条件。
- `BasicLexiconGenerator` 生成后不执行最终 validator。
- Python Genesis 主路径直接写入随机 CV/CVC/CVCV/CCVC 词形；validator 主要出现在报告侧，legacy 黄金 fixture 仍接受每个样本 22–31 个 phonotactically illegal alive forms。
- borrowing 可引入未在目标 inventory 中的符号，并使用 `uuid.uuid4()`。
- native insert rule 的 compiler/backend 数据通路不完整，可能静默 no-op。
- 当前 syllabifier 会在 `/anta/` 一类序列中把同一个 intervocalic consonant 同时分给前一 coda 和后一 onset；`default_phonotactics.json` 又声明最大 onset 为 2，却列出不可达的 `str/spr/skr`。
- Rust v2 只验证 lexeme phoneme 序列非空和引用存在，不验证可音节化、音系配列或韵律结构；同时把所有音节核硬限制为 `SegmentClass::Vowel`，又排除了可作核的音节辅音等类型。

**影响**

系统既会接受不应存在于当前语言描述中的词形，也会错误拒绝真实语言可有的结构。字符串表面看似 IPA 并不等于音系上有效。

**解决**

建立分层音系合同：

1. `Segment/FeatureBundle`：CLTS/PHOIBLE 对齐的版本化特征，不以字符串等值代替特征匹配。
2. `Inventory`：音位、音位变体、对立和组合限制。
3. `ProsodicRepresentation`：mora、syllable、foot、stress、tone、边界和核许可类。
4. `PhonotacticGrammar`：硬约束先拒绝不可能状态；概率模型只对合法候选排序。
5. `SoundChangeIR`：typed target/environment/effect、适用域、例外来源和后置条件。
6. 每条变化先生成 proposal，应用后重新音节化和验证，再原子提交。

MaxEnt 音系配列可作为可替换的梯度模型，不能取代 inventory membership、音节化和最小核等硬验证。

**验收**

- unknown segment、空表层、无许可核、越界 cluster、悬空 suprasegmental 均产生 typed error；
- 支持音节辅音的 profile 能通过，不支持它的 profile 明确拒绝；
- 每个 segment occurrence 恰好属于一个 prosodic position；`/anta/` 等边界 fixture 不重复分配 token；
- delete/insert/metathesis/assimilation/lengthening 每类都有 unit、property 和 negative fixture；
- `/go/` 的末元音删除若导致无核形式，必须被阻断、修复或以明确理论 profile 许可；
- 生成、借词、复合、形态音系和音变共享同一最终 validator；任意 seed 的 Genesis hard errors 均为 0。

### P0-05：意义到句子的实现不能保持意义

**证据**

- demo 仍明确展示“纯 IPA 拼接，无形态变化”的 `SentenceAssembler`。
- CSG 只支持少量关系；没有可靠表示 scope、quantification、modality、negation、information structure、coreference、speech act 和 pragmatic commitment。
- `LexicalizationLayer` 在缺少词汇时会静默使用语义图中的 ancestor concept。当前无类型 `relations` 把 `BAD→GOOD`、`SMALL→BIG`、`BELOW→ABOVE`、`NEAR→FAR` 等对立/逆向关系也当成 ancestor，因而可直接反转真值条件。
- ancestor 返回 `set` 后直接迭代；多候选后备会受 Python hash seed 影响，同一输入可跨进程选择不同词项。
- `MorphologicalPlanner` 只取第一个 agent/patient；ergative-absolutive 路径仍给 subject 规划 NOM，角色系统未区分 S/A/P。
- 同一 planner 把 `I` 和 `we` 等路径映射到同一 `1SG` marker，进一步说明人称/数和词义没有形成 typed obligation。
- analytic 路径会把所有 grammaticalized function word 加到句子中，而不是由语义/构式需求选择。
- CSG 和 morphology 的 errors 被转成 warning 后仍继续生成。
- 验收测试主要断言句子非空、不同或可生成，未证明意义守恒。

**影响**

输出“像句子”但不能证明表达了输入意义。静默降级比显式失败更危险，因为用户会把错误翻译写入 canon。

**解决**

冻结一条完整、唯一的实现管线：

```text
SceneFacts + InteractionContext
→ CommunicativeIntent + PragmaticCommitments
→ typed Proposition/Scope Graph
→ language-specific obligations
→ predicate frame + construction selection
→ syntactic representation
→ lexeme + feature bundle
→ ordered morphology
→ morphophonology
→ phonology/prosody
→ orthography + IPA + IGT + trace
```

缺失能力必须返回 typed `ExpressionGap`，禁止临时随机造词、静默替换概念或丢弃论元。生成器与分析器使用同一 grammar authority。语义关系必须区分 entailment、is-a、part-of、antonym、spatial inverse、association 等；只有被 grammar/lexicalization contract 明确许可的 coercion 才能进入候选。

**验收**

- reference、predication、modification、deixis、negation、question、possession 至少各有正反任务；
- scope、角色、指称和 pragmatic commitment 在实现轨迹中可核对；
- `BAD` 不得实现为 `GOOD`，`BELOW` 不得实现为 `ABOVE`；候选排序跨 `PYTHONHASHSEED` 稳定；
- `generate → analyze` 恢复许可的抽象结构；歧义以候选集呈现；
- 同一任务在两个非同构语言 fixture 中都可表达，而非依赖英语词类和 SVO；
- 无法表达时返回可定位的 `ExpressionGap`，不返回貌似成功的句子。

### P0-06：经验数据被当成了机制或事实

**证据**

- `BasicLexiconGenerator` 使用 Swadesh/概念表中的 `true_freq_rank`，再固定分配 45% function / 55% content 权重。
- 语法化用英文 concept 名、frequency rank 和 `len(ipa_history)` 作为侵蚀阶段并直接触发。
- “功能词每个时代侵蚀”“高频词免于常规音变”“随机特征翻转形成 suppletion”等行为缺少可审计数据和适用域。
- `semantic_compounds.json` 中英语中心的复合和隐喻可被误读为普遍词汇化路径。
- morphology 的 analytic/agglutinative/fusional 被压成单轴阶段并按固定 Markov 循环漂移。

**影响**

系统会把数据标签、传统描述术语和研究假设变成伪自然定律；输出虽可重复，却没有科学可解释性。

**解决**

- 概念表只用于 elicitation/对齐；使用频率必须来自带语言、体裁、时期、token/type 单位的 corpus observation。
- type frequency、token frequency、语境频率、词汇扩散和保守效应分别建模。
- 类型学使用多维 feature profile；Grambank/WALS 只提供带谱系和地域控制的分布先验。
- 语法化 pathway 记录 source construction、bridging context、semantic/pragmatic inference、reanalysis、coexistence、formal change 和 adoption，不用“时代计数器”代替机制。
- 所有 pathway、compound association 和 typological association 必须带 provenance、版本和 limitations。

**验收**

- Concepticon/Swadesh 序号不再进入 usage frequency；
- 数据 manifest 锁定精确 payload、transform、license、sampling unit 和 hash；
- 任一 prior 可关闭并做 sensitivity/ablation；
- empirical association 不会自动成为跨语言硬约束；
- fixture 能显示高频导致弱化、保守或无显著效应的不同 profile，而不是单一方向。

### P0-07：类推、语法化和同音处理的语言学对象错误

**证据**

- `AnalogyPropagator` 按词形位置的音系特征相似度传播形态模式，而不是依据范式、构式、词族或可生产 schema。
- `GrammaticalizationOperator` 随意选择第一个 verb/word 作为 host，删除末 token，直接跳到 stage 3。
- `HomophoneResolver` 把同音当作必须消除的问题，采用 IPA 叠词、固定后缀、词汇死亡等策略，并把结果记为 sound change。
- `FossilPrefixExtractor` 假设死亡词会自动留下首音节前缀。
- compounding 把父词形按 Python 字符位置切成两半再拼接。

**影响**

这些不是“粗糙但近似”的同一机制，而是在错误对象上实现了不同机制。继续调参无法修正其语言学含义。

**解决**

- 类推：以 `ParadigmCell`、construction、schema productivity、base selection、token/type frequency 和社会采用为对象。
- 语法化：以 construction token 和重分析事件为对象，允许共存、层叠、更新、未完成和逆向/非典型候选。
- 同音：默认合法；只把有证据的 functional-load/lexical-competition 效应作为概率因素，不运行全局“消歧修复器”。
- 化石：必须来自已记录的 resegmentation/reanalysis 和传播证据。
- 复合：拼接 ordered morpheme occurrences，再经过边界敏感的 morphophonology；blend 是独立、可选、带来源的 word-formation process。

**验收**

- 没有 paradigm/construction 关系时不能声称发生 morphology analogy；
- 同音词可长期共存；是否受抑制由可替换 theory profile 决定；
- grammaticalization 事件能指出源构式、桥接语境、旧新分析和共存期；
- compound/blend 不会切断 IPA combining mark、多字符 segment 或 morpheme identity；
- 所有结果经过相同的表层验证和 event reducer。

### P0-08：确定性和 provenance 边界仍有旁路

**证据**

- Python borrowing 使用 `uuid.uuid4()`，不来自版本化 `RngTree`。
- 多条 Python 路径共享或重新派生 `random.Random` 的方式并不等价；flat、epoch、branch 的调用顺序不同。
- LLM sanitizer 只过滤“像 IPA 的字符”，不依据目标 inventory、phonotactics、morphology 和 canon validation；LLM 还可直接提出 compound IPA。
- Python 使用全局 snapshot/event 目录，项目隔离与 provenance 不完整。

**影响**

相同 seed 不必然产生相同结果；外部模型或调用顺序可改变权威状态；结果可能无法说明来自哪条数据、规则或随机流。

**解决**

- 所有 ID、抽样和 tie-break 都从版本化 `RngTree` path 或确定性 ID 派生。
- 外部模型只返回 versioned proposal DTO；Rust compiler/validator 重新解析并给出 candidate hash。
- 每项数据、规则、theory、模型输出、作者选择和 migration 都进入 provenance/lock。
- 项目文件、缓存、日志和临时产物都 project-scoped；临时产物不进入 semantic hash。

**验收**

- 仓库检查拒绝未登记的 RNG/UUID/time source；
- 调整无关模块执行顺序不改变既定 RNG path 的 known answer；
- LLM 关闭时核心能力仍完整；同一已锁定 proposal 可离线重放；
- sanitizer 不能把非法输出“清洗”为合法权威数据；
- project A 的运行不能读写 project B 的权威目录。

### P0-09：Genesis 信任边界尚未封印

**证据**

- Rust `ProjectRuntime::create_from_genesis` 只要求输入是一段可回放、首事件为 Genesis 的 history。
- 当前没有要求该 Genesis 来自 Blueprint + RegistryBundle + TheoryProfile + locked data/RNG 的确定性 compiler，也没有 evaluator seal。
- 从磁盘或 IPC 反序列化的对象与进程内已经验证的 capability 尚无不可混淆边界。

**影响**

任何“内部一致”的手工状态都可能被包装成 Genesis。这样只能证明 schema 可读，不能证明它满足用户 Blueprint、语言学 hard invariants 或生成质量门。

**解决**

- `telysta-application` 只接受进程内能力类型 `VerifiedGenesisArtifact` 创建正式项目。
- artifact 必须包含 Blueprint/compiler/evaluator/rule/data/theory/RNG locks、candidate semantic hash 和验证报告。
- 从磁盘、插件、IPC 或 LLM 得到的序列化 artifact 一律重新完整验证，不能反序列化为“已验证”能力。
- storage 的低层 arbitrary-history constructor 只保留 migration/test 权限，不暴露成产品 use case。

**验收**

- 手写 Genesis、篡改 candidate、换 compiler/data/RNG lock 或删除验证记录均失败；
- 同一锁定输入编译出同一 artifact/hash；
- `planned` compiler 不能产生 seal；
- 只有 accepted evaluator policy 的 hard errors 为 0 时才能创建项目。

### P0-10：环境和奇幻“种族”被写成直接语言因果

**证据**

- `app/domain/language/evolution_profile.py` 给 forest/tundra/desert/mountain 硬编码侵蚀位置和语法化倍率。
- 同一文件给 elven/orcish/dwarvish 硬编码特定音变倍率和语法化产物偏好。
- `BranchLanguage.evolve_one_era()` 把这些 multiplier 直接乘入逐词音变概率。

**影响**

这把未经充分控制的环境关联和创作标签伪装成因果机制，也会形成奇幻族群本质主义。它违反“经验先验、研究假设、创作偏好不可混用”的项目原则。

**解决**

- “优雅、冷峻、北方感、精灵、兽人”等只进入 `PreferenceProfile`，用于对已合法候选做可解释排序。
- 环境可影响词汇需求、交流媒介、迁徙、接触网络和使用场景；不能直接决定音变。
- 气候—音系等关联只能作为 opt-in、版本化 `TheoryProfile`，需要控制谱系、地域、接触和抽样偏差并显示不确定性。
- 用户若选择风格模板，UI 必须标注“创作预设”，不得标注“语言学规律”。

**验收**

- 关闭 creative preference 不改变 hard validity；
- race/environment 标签不能直接出现在 sound-change probability 的生产 reducer 中；
- 所有相关性模型可消融并报告效应区间；
- 相同环境允许产生多个结构不同的有效候选，不形成一对一映射。

### P0-11：读取/实现操作会改变语言状态

**证据**

- Python `MorphologicalPlanner` 在句子生成时累计 morpheme co-occurrence，并可能向 `typology.morpheme_table` 注册 portmanteau。
- `PortmanteauRegistry` 达到阈值后会生成融合体并把来源 morpheme 标死。
- 对应测试把“重复调用 planner 后语法发生变化”固化为成功路径。
- haplology/fusion 又使用 IPA 字符首尾和切片，而不是 typed segment/morpheme boundary。

**影响**

用户只要预览、刷新、重复翻译或比较两个候选，就可能改变之后的语法和历史。结果依赖 UI 查询次数，破坏确定性、审计和 canon safety。

**解决**

- `realize/analyze/preview/evaluate` 全部是纯查询，只消费 immutable state 和 request。
- corpus token observation 单独版本化；不能藏在 planner 的内部计数器。
- fusion、reanalysis 和 convention adoption 只能由 simulation/authoring command 提出 typed ChangeSet。
- application 层明确区分 Query 与 Command，依赖测试禁止 query 获得 writer capability。

**验收**

- 同一请求重复 1 次或 100 次，LanguageState semantic hash、history head 和后续候选不变；
- UI refresh/cancel/retry 不产生领域事件；
- observation ingestion 与 change adoption 是两个可分别重放的操作；
- fusion 能指出 source construction、morpheme occurrences、频率证据和采用事件。

### P0-12：当前“音变”把不同机制压成逐词彩票

**证据**

- Python engine 对每个词、每条 operator 独立抽样，而没有区分 innovation、token variation、lexical diffusion、community adoption 和 conventionalization。
- `ErosionModel` 使用未校准阈值并规定高频功能词持续侵蚀。
- `IrregularScarManager` 把高频词排除于规则音变，再随机翻转特征，声称可近似 `go/went` 一类 suppletion。
- 相近删除规则的 guard 不一致：final-vowel drop 有 stress/coda/nucleus 防护，mid-vowel drop 没有。

**影响**

规则音变、词汇扩散、类推、异干、词汇替换和偶发变化失去可区分对象。调高或调低概率不会让模型获得历史语言学含义。

**解决**

- `TheoryProfile` 明确选择 regular、lexically diffusing、class-conditioned、construction-conditioned 或 sporadic process。
- regular change 在一次 adoption 后对全部 typed environment 实例应用；词汇扩散记录扩散曲线和已采用集合。
- suppletion 只来自已记录的异干继承、词汇替换、接触或范式重组，不由随机 phone flip 生成。
- innovation、variant token、speaker/community adoption、conventionalization 和 later analogy 分成不同事件层。

**验收**

- 同一 change proposal 能报告适用集合、未应用原因、adoption 状态和 token correspondence；
- regular 与 lexical-diffusion fixture 产生可区分的历史；
- 随机特征翻转不能被标记为 suppletion；
- 频率先验关闭后，音系 hard environment 和 replay 仍保持正确。

## 5. P1 领域问题台账

| ID | 问题 | 当前表现 | 修正方向与最低验收 |
|---|---|---|---|
| P1-01 | 音段特征与音系层级过薄 | Python `dict[str,bool]`、Rust `ipa + SegmentClass`；缺少 feature geometry、allophony、tone/foot/boundary | RegistryBundle 定义值域、层级和查询；规则只能匹配 typed feature/environment；CLTS/PHOIBLE 是数据对齐，不是完整理论 |
| P1-02 | 历时与共时规则混用 | `SurfacePhonologyApplier` 调用 `apply_all()`，忽略 `era_start`，可把所有历史变化再次施加于每个生成 token | 分开 DiachronicChange 与 SynchronicAlternation；表层规则有边界、层级和 era/state scope；重复生成不改变词典底层形式 |
| P1-03 | 形态类型被单轴化 | analytic→agglutinative→fusional 作为 0/1/2 状态和循环漂移 | 按 synthesis、fusion、exponence、allomorphy、head/dependent marking 等多维表示；变化作用于具体 construction/paradigm |
| P1-04 | 词类完整性判断英语中心 | legacy 检查 `pron.`、`v.`；POS normalization 又改为 `pronoun`、`verb` | 从“必须有名词/动词/代词”改为功能能力；language-internal categories 与 comparative concepts 分开 |
| P1-05 | 词汇生成是一概念一随机词 | 每个概念独立 `_ipa_generate()`；renewal/domain injection 继续随机造词 | 支持 colexification、derivation、compounding、borrowing、periphrasis、zero 和 lexical gap；所有 coinage 带 strategy/provenance |
| P1-06 | 语义关系无类型或方向不清 | semantic graph 的 relation 可表示 opposition/association；ancestor fallback 丢意义 | 使用 typed semantic relation、scope 和 lexicalization strategy；CLICS 只作有方向不确定的 empirical prior |
| P1-07 | 配价和对齐模型过窄 | 只取一个 agent/patient；没有 S/A/P、experiencer、stimulus、recipient 等 | 用 predicate-specific valency frame；以 ValPaL task 做多类谓词、编码和 alternation 验收 |
| P1-08 | 形态实现不可逆 | 直接 IPA 后缀、portmanteau lookup 和表层拼接；无 analyzer/IGT | ordered morphology + morphophonology；零、融合、syncretism、allomorphy 可追踪；UniMorph 式范式任务与往返 |
| P1-09 | 生成查询有副作用 | portmanteau/grammar registry 可能在 realization 时学习或标死源 morpheme | Query 与 Command 分离；realizer 纯函数；学习/重分析只能提交显式 ChangeSet |
| P1-10 | 社会变化和传播缺位 | era 级全语言随机改变；“地区/气候”可能被当作直接原因 | 后续 WS-2 定义 SpeechCommunity、variant、token observation、network/contact、prestige/adoption；环境只能是有证据或创作条件 |
| P1-11 | 分支管线不等价 | flat、epoch、branch 绕过不同 validator、homophone、snapshot 和 RNG 路径 | 一个 application/simulation service；branch 只是输入 state/lineage 不同；共享同一 reducer、validator、event 和 evaluator |
| P1-12 | Rust client/application 边界未落地 | Tauri `main.rs` 直接依赖 `telysta-core` 和 `ProjectRuntime`，同时持有 demo engine 和项目 runtime | G0A 后先建 `telysta-application`；desktop 只使用 versioned command/query DTO，不编排 transaction |
| P1-13 | Rust schema 对 authoritative input 过宽 | Serde 默认可忽略未知字段；部分字段用自由字符串；down-level reader 有静默丢字段风险 | 对权威 envelope 采用严格 schema/unknown-field policy；FeatureRegistry 校验值域；compatibility/migration fixture 覆盖前后版本 |
| P1-14 | 评估器验证了实现而非语言能力 | 大量测试只检查长度、非空、差异和确定性；generator/evaluator 共享假设 | 独立 TaskPack；development/candidate/sealed/external 分组；meaning preservation、negative fixtures、held-out 和专家审计分开 |
| P1-15 | provenance 覆盖不完整 | Rust v2 要求部分实体有来源，但 prosody、register、orthography、typology assertion 等领域缺少等价的逐变化 provenance | effect coverage matrix 覆盖所有 semantic-hash 字段；每个变更能定位 event/evidence/author/rule，不允许靠整状态 replacement 无痕改变 |
| P1-16 | DataReference 只证明标签存在 | project lock 要求 dataset payload hash，但单条 reference 主要校验 dataset ID 和非空 table/record 字符串，不验证真实 payload 中的 record/field | payload-aware registry 校验 table/record/field、transform、sampling unit 和 transformed hash；负例拒绝虚构 record |
| P1-17 | Tauri API 仍是 spike 边界 | demo/project/blueprint 使用不同 error 形态；webview 字符串直接转项目路径；一个全局 mutex 串行 runtime | versioned response/error envelope、request ID、retryability、cursor/head binding；文件选择 capability；按项目隔离并发 |
| P1-18 | SoundChange IR 无法表达核心历时过程 | 当前 IR 只有 change/delete/insert、相邻环境和边界 flag；无 syllable/mora/stress/tone/morpheme boundary/stratum/inventory split；`feeding_mode=False` 仍把前规则输出交给后规则 | typed prosodic/morphological environment；simultaneous/cascade/stratal/opaque 模式；inventory-changing effect；chain shift、phonemicization、feeding/counterfeeding 黄金场景 |

## 6. 不能再沿用的推断

以下命题不得作为实现规则：

- “缺少独立代词/形容词类，所以语言不完整。”
- “两个词同音，所以系统必须主动消除其中一个。”
- “Swadesh 或 Concepticon 顺序就是使用频率。”
- “高频词总是更容易侵蚀”或“高频词总是免受规则音变。”
- “分析语、黏着语、屈折语是同一条必经演化链。”
- “IPA history 较长等于发生了语法化。”
- “音系相似词会自动继承同一个屈折范式。”
- “寒冷、山区、尚武、优雅等标签会直接造成某类音系或语法。”
- “固定 seed 或测试通过就证明语言自然、历史真实或文学可用。”
- “LLM 输出听起来好，所以可以成为 authoritative state。”

## 7. 理论与数据依据

这些来源用于约束建模方法，不用于宣称某一种理论是唯一真理。

| 证据 | 可支持的产品决策 | 不得据此推出 |
|---|---|---|
| Hayes & Wilson, [A Maximum Entropy Model of Phonotactics and Phonotactic Learning](https://www.brucehayes.org/papers/HayesAndWilsonPhonotactics2008.pdf) | 合法性可同时有 categorical constraints 与 gradient ranking；特征与非局部层级需要显式表示 | 一个分数就是跨语言“自然度”；概率模型可替代硬验证 |
| Bybee, [Word Frequency and Context of Use in Lexical Diffusion](https://www.unm.edu/~jbybee/downloads/Bybee2002WordFreq.pdf) 与 [Frequency of Use and the Organization of Language](https://doi.org/10.1093/acprof:oso/9780195301571.001.0001) | token/type/context frequency 对弱化、保守、生产性和扩散可有不同作用 | 概念表序号可充当 corpus frequency；高频只产生一个方向的变化 |
| Blevins & Wedel, [Inhibited Sound Change](https://julietteblevins.ws.gc.cuny.edu/files/2013/04/BlevinsWedel2009.pdf) | 在有限、有证据的环境中，lexical competition/functional load 可成为音变抑制的概率因素 | 所有 homophony 都是错误；需要全局叠词、加缀或词汇死亡 |
| Hopper & Traugott, [Mechanisms: Reanalysis and Analogy](https://www.cambridge.org/core/services/aop-cambridge-core/content/view/139D3443309AF1F9DA012BF72322DA57/9781139165525c3_p39-70_CBO.pdf/mechanisms-reanalysis-and-analogy.pdf) 与 [The hypothesis of unidirectionality](https://doi.org/10.1017/CBO9781139165525.006) | 语法化要建模语用推理、重分析、类推、形式变化和共存；方向性是可检验倾向 | 英文 concept + 侵蚀次数能直接触发固定阶段；路径无例外且必然完成 |
| Albright, [The Identification of Bases in Morphological Paradigms](https://www.mit.edu/~albright/papers/AlbrightDiss.html) | 类推以范式、base、predictability 和概率规则为对象 | 任意音系相似的两个词就是类推关系 |
| Haspelmath, [How to compare major word-classes](https://doi.org/10.5281/zenodo.3678496) 与 [Comparative concepts and descriptive categories](https://doi.org/10.5281/zenodo.1158392) | 跨语言比较概念与语言内部类别必须分离 | 英语式 noun/verb/adjective/pronoun 是每种语言的固定本体 |
| [Concepticon](https://concepticon.clld.org/about) 与 [CLICS](https://clics.clld.org/) | 概念对齐、colexification 和语义关联可作 empirical prior | 概念必须一对一词汇化；关联边等于有方向因果变化 |
| [ValPaL](https://valpal.info/) | 以谓词为中心测试语义角色、句法编码、配价类与 alternation | agent-patient、SVO、NOM/ACC 可覆盖所有谓词和语言 |
| McCarthy et al., [UniMorph 3.0](https://aclanthology.org/2020.lrec-1.483/) | 用 lexeme + feature bundle + form 表达范式并做跨语言数据验证 | 每种语言都必须实例化同一组范畴；形态关系永远是一对一函数 |
| Beesley, [Arabic Morphology Using Only Finite-State Operations](https://aclanthology.org/anthology-files/anthology-files/pdf/W/W98/W98-1007.pdf) | analyzer/generator 与 morphophonology 可用双向有限状态实现并覆盖部分非拼接形态 | 全部语义、句法和历史变化都是 FST 问题 |
| Ranta, [Grammatical Framework](https://doi.org/10.1017/S0956796803004738) 与 Copestake et al., [Minimal Recursion Semantics](https://www.cl.cam.ac.uk/~aac10/papers/newmrs.pdf) | 抽象结构与具体实现分离；typed parsing/linearization 和 scope underspecification 可作为实现参考 | 直接引入某一 formalism 就自动获得全部自然语言覆盖 |
| Skirgård et al., [Grambank](https://doi.org/10.1126/sciadv.adg6175) | 用带谱系/地域控制的多维语法数据建立可校准 prior | 高频类型是硬普遍律；地域关联就是环境因果 |
| Hartmann et al., [Investigating environmental effects on phonology using diachronic models](https://doi.org/10.1017/ehs.2023.33) | 环境—音系因果主张需要历时重建、谱系/地域/借用控制和因果模型；单一 Bantu 样本未支持其所检验的湿度—声调主张 | 环境永远没有作用；一次阴性结果可推广到所有语言、环境和音系变量 |
| Labov, [Transmission and Diffusion](https://doi.org/10.1353/lan.2007.0082) 与 Sharma & Dodsworth, [Language Variation and Social Networks](https://doi.org/10.1146/annurev-linguistics-011619-030524) | 区分创新、代际传递、成人扩散、社群网络、身份与采用过程 | 一个 era 随机数或地理标签足以模拟社会语言变化 |
| [CLTS](https://clts.clld.org/)、[PHOIBLE](https://phoible.org/inventories)、[WALS](https://wals.info/) | 标准化音段/类型数据和跨语言抽样可提供数据先验与验证样本 | 数据库收录即代表普遍可行或因果机制 |
| [Leipzig Glossing Rules](https://www.eva.mpg.de/lingua/pdf/Glossing-Rules.pdf) | 为可审计 IGT 输出提供展示约定 | gloss 标签本身就是语言内部语法分析 |

### 7.1 理论在架构中的正确位置

```text
hard invariants
  inventory/reference/schema/replay/meaning preservation
        ↓ reject invalid

versioned empirical PriorPack
  PHOIBLE/WALS/Grambank/CLICS/ValPaL/corpus observations
        ↓ rank/calibrate

versioned TheoryProfile
  MaxEnt phonotactics / usage-based change / paradigm analogy /
  lexical competition / social diffusion
        ↓ generate competing explanations

creative PreferenceProfile
  sound symbolism / aesthetic / cultural and literary goals
        ↓ select among already valid candidates
```

这四层不能倒置：偏好不能使非法状态合法，统计常见不能成为硬律，研究模型不能隐藏在常量里。

## 8. 推荐的目标领域架构

### 8.1 权威状态

```text
LanguageState
├─ PhonologicalSystem
│  ├─ SegmentRegistry / Contrast
│  ├─ ProsodicRepresentation
│  ├─ PhonotacticGrammar
│  └─ SynchronicAlternation
├─ Lexicon
│  ├─ Lexeme / Sense / Etymon
│  ├─ WordForm / Allomorph
│  └─ LexicalizationStrategy
├─ Morphology
│  ├─ Morpheme / ordered occurrence
│  ├─ Paradigm / FeatureBundle
│  └─ Morphophonology
├─ Grammar
│  ├─ PredicateFrame / Valency
│  ├─ Construction / InformationStructure
│  └─ Agreement / Alignment / Linearization
├─ SemanticsPragmatics
│  ├─ Proposition / Scope / Reference
│  └─ Commitments / Discourse
├─ Orthography / PronunciationPlan
├─ CommunityState（WS-2 后）
└─ ProvenanceGraph
```

### 8.2 命令与查询

```text
Tauri / CLI
  → versioned command/query DTO
  → telysta-application
      → compiler / authoring / simulation / evaluation services
      → telysta-core reducers and validators
      → telysta-storage atomic commit
```

realization、analysis、preview 和 evaluation 默认是纯查询。只有显式 author/simulate/adopt/commit 命令可产生 ChangeSet。

### 8.3 变化闭环

```text
Observation / author intent / scheduled experiment
→ ProposedChange
→ typed environment match
→ candidate variants
→ population or author selection
→ postcondition validation
→ Atomic ChangeSet
→ commit + provenance + semantic hash
→ replay + impact analysis
```

一条音变不能直接创建语法化，一次句子生成不能直接发明历史，一次 LLM 提案不能直接修改状态。

## 9. 建议的执行顺序

### Step 0：把本审计纳入 G0B 缺陷台账

- 给 P0/P1 项分配 owner、reviewer、target gate 和证据路径。
- 把 legacy 缺陷做成 negative fixtures，不为保持旧输出而移植到 Rust。
- 不在当前 dirty tree 中做大规模移动或删除。

### Step 1：新增 ADR-014（提案，不在本审计中代为接受）

建议题目：`Meaning–Grammar–Lexical Class–Realization Authority`。

必须决定：

- Lexeme/Sense/WordForm/Morpheme/Paradigm/Construction 的身份与所有权；
- semantic task、language-specific category 和 comparative concept 的边界；
- ordered realization、zero/fusion/syncretism/allomorphy 的表示；
- generate/analyze/IGT/trace 的权威关系；
- typed ExpressionGap、ambiguity 和 partial support；
- event/replay/migration/semantic hash 影响。

### Step 2：冻结三份 G0B 合同

1. `LINGUISTIC_REALIZATION_MODEL_V1.md`
2. `LEXICAL_CLASS_REFERENCE_AND_VALENCY_V1.md`
3. `WS1_LINGUISTIC_TASKPACK_V1.md`

Capability Matrix 以功能而不是英语词类计数，至少包含 reference、predication、modification、deixis、negation、question、possession。

### Step 3：建立两个非同构 fixture

至少包括：

- Profile A：无必需独立主语代词，属性概念不要求独立 adjective class；
- Profile B：不同于 A 的 alignment、order、head/dependent marking 和 morphological strategy。

两个 profile 必须通过同一语义任务，但产生不同结构；不能只是 SVO/SOV 换序。

### Step 4：先实现 Rust WS-1 纵切，再实现历时变化

纵切必须同时交付：

- 一个小 inventory/prosody/phonotactics；
- 可分析的 lexicon/paradigm/construction；
- 一段意义保持的文本；
- orthography、IPA、IGT 和 provenance trace；
- generate/analyze roundtrip；
- 一个 typed structural change 的完整 event/replay。

在它通过 G2 前，不扩展大批音变、家族、接触或 agent population。

### Step 5：WS-2 再引入机制性传播

按 innovation → variation → adoption → diffusion/transmission → regularization 建模。先做小规模可识别实验、parameter recovery、sensitivity 和 ablation，再扩大社群与家族规模。

## 10. 进入生产领域实现前的 Stop/Go

### Stop

出现以下任一情况即停止并补 ADR/合同：

- 新实体改变 persisted identity，但没有 migration；
- 新变化只能记录成自由文本或通用 `SOUND_CHANGE`；
- realizer、LLM 或 evaluator 能直接修改 authority state；
- validator 只给 warning 但仍提交违反 hard invariant 的结果；
- 数据只锁元数据而未锁精确 payload/transform；
- 测试只证明“有输出”而不证明 meaning/analysis/replay；
- 新规则依赖 IPA/grapheme 字符串匹配而已有 typed feature；
- UI 把 planned compiler capability 当成可用。

### Go

只有在以下条件同时满足时才进入 WS-1 生产实现：

- G0A 与 G0B 均关闭；
- ADR-007 至 ADR-014 的依赖和状态一致；
- clean-checkout 全门可复现；
- authority/migration/replay/semantic-hash 均有唯一合同；
- 两个非同构 fixture 和 TaskPack 已冻结；
- 数据 payload、license、sampling unit 和 limitation 可审计；
- negative fixtures 已覆盖本审计 P0 根因。

## 11. 针对现有三个表面症状的最终处置

| 症状 | 不应采用 | 应采用 |
|---|---|---|
| 缺少词类 | 增加固定 pronoun/verb/adjective 配额 | 检查语言是否能完成 reference/predication/modification 等功能；类别由该语言构式诊断定义 |
| `g → gg` | 特判字符串 `g`、禁止所有 geminate、继续全局同音修复 | 修复末核保护、post-change syllabification、同音默认合法、typed reduplication/morphology event、negative replay fixture |
| 句子是 IPA 拼接 | 再增加随机模板或让 LLM润色 IPA | 建立 typed meaning → construction → morphology → morphophonology → surface 的双向管线，输出 orthography/IPA/IGT/trace |

## 12. 审计完成标准

本文只完成“问题发现、根因归类、理论支撑和修正验收定义”。它没有：

- 接受任何 Proposed ADR；
- 修改 LanguageState、event replay 或 writer；
- 宣称当前语言生成质量已经提高；
- 授权清理 legacy 模块；
- 把某一理论升格为产品硬律。

下一份应产生的决策材料是 ADR-014 草案和 G0B 三份合同；下一份可执行代码应在 Gate 关闭后，以 Rust WS-1 小纵切为单位提交。

## 13. 本次验证记录

| 命令 | 结果 | 正确解释 |
|---|---|---|
| `.\.venv\Scripts\python.exe scripts\docs_check.py` | PASS | 新文档元数据、索引和本地链接满足当前文档治理检查 |
| `.\.venv\Scripts\python.exe scripts\check.py` | FAIL：compile/lint/docs 通过；测试为 552 passed、8 xfailed、1 failed | 唯一 failure 是 G0A `worktreeInventorySha256` 与当前 dirty tree 不一致；这是 GateEvidence 正确失效，不能刷新证据来掩盖工作树变更 |
| `cargo fmt --all --check` | PASS | 当前 Rust 格式门通过 |
| `cargo test --workspace --locked` | PASS：62 tests | 当前 Rust 地基合同和 spike 测试通过；不证明 WS-1 语言能力存在 |
| `cargo clippy --workspace --all-targets --locked -- -D warnings` | PASS | 当前 Rust lint 门通过 |

8 个 strict xfail 是已登记迁移缺陷，不应改成 broad skip，也不能被“其余测试通过”抵消。G0A 仍为 blocked。

## 14. 代码证据索引

行号以本文 `source_revision` 及审计时工作树为准；后续代码移动应保留 issue ID 或迁移映射。

| 问题 | 主要证据锚点 |
|---|---|
| P0-02 领域身份/有序形态 | `app/domain/lexicon/models.py:20-46`；`crates/telysta-core/src/state.rs:131-183,233-247` |
| P0-03 直接写入/整状态历史 | `app/engine/evolution.py:316-350`；`app/llm/orchestrator.py:157-170`；`crates/telysta-core/src/project.rs:348-421,625-680`；`crates/telysta-storage/src/session.rs:389-426` |
| P0-04 Genesis/音系合法性 | `app/domain/phonology/validator.py:132-215`；`app/domain/phonology/operators/mid_vowel_drop.py:29-53`；`app/domain/lexicon/generator.py:33-58,120-155`；`tests/fixtures/golden/legacy_v1.json:16-60` |
| P0-05 意义守恒 | `data/semantic_primes/primes.json:51-70`；`app/domain/syntax/semantic_graph.py:29-94`；`app/domain/syntax/lexicalization.py:54-66`；`app/domain/syntax/pipeline.py:82-120`；`app/domain/syntax/morphological_planner.py:67-127` |
| P0-06 频率/类型先验误用 | `app/domain/lexicon/generator.py:75-110`；`app/domain/lexicon/grammaticalization_operator.py:97-106`；`app/domain/lexicon/typology_drift.py:43-58,154-208` |
| P0-07 同音/类推/语法化对象 | `app/domain/lexicon/homophone_resolver.py:49-66,143-180`；`app/domain/lexicon/analogy.py:12-78`；`app/domain/lexicon/grammaticalization_operator.py:138-170,223-257`；`app/engine/vocabulary.py:230-298` |
| P0-08 确定性/LLM | `app/domain/lexicon/borrowing.py:197-215`；`app/llm/orchestrator.py:157-170`；`app/engine/vocabulary.py:131-187` |
| P0-09 Genesis seal | `crates/telysta-storage/src/session.rs:313-353`；`docs/adr/ADR-010-genesis-artifact-trust-boundary.md` |
| P0-10 环境/奇幻标签因果 | `app/domain/language/evolution_profile.py:36-81`；`app/domain/language/branch.py:119-145` |
| P0-11 query mutation | `app/domain/syntax/morphological_planner.py:242-309`；`app/domain/morphology/portmanteau.py:72-134`；`tests/syntax/test_morphological_planner.py:240-266` |
| P0-12 逐词彩票 | `app/domain/phonology/erosion.py:4-70`；`app/domain/lexicon/irregular.py:12-62`；`app/engine/evolution.py:274-314` |
| P1-02 共时/历时混用 | `app/domain/syntax/surface_phonology.py:10-48`；`app/domain/phonology/operators/registry.py:49-65` |
| P1-12 application boundary | `apps/desktop/src-tauri/src/main.rs:13-18,57-64,149-192` |
| P1-13/15/16 Rust schema、来源和数据 | `crates/telysta-core/src/state.rs:358-440`；`crates/telysta-core/src/data.rs:99-104,238-246`；`crates/telysta-core/src/project.rs:566-580` |
| P1-18 SoundChange IR | `app/domain/phonology/ir.py:9-30`；`app/domain/phonology/rule_compiler.py:74-93`；`app/domain/phonology/conflict_resolver.py:48-98` |
| Python replay 缺陷 | `app/domain/storage/history.py:34-87`；`tests/storage/test_history_replay_features.py:132-296` |
