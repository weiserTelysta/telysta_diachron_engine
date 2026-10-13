---
document_type: adr
decision_status: proposed
implementation_status: not-started
normative_scope: target
last_verified: 2026-10-12
owner: unassigned
reviewers: []
---

# ADR-014：Meaning–Grammar–Lexical Identity/Class–Realization Authority

## 1. 状态与放行边界

- 状态：`Proposed`
- 日期：2026-07-18
- 决策范围：Meaning、Grammar、Lexeme/Sense/WordForm/Morpheme/Paradigm/Construction 身份、language-internal lexical class、正字法、双向 realization/analysis、query purity、迁移、provenance、semantic hash 与 replay
- 已接受前置：ADR-006
- 接受前必须闭合：ADR-008、ADR-011、R0B-01 Meaning/Task Contract
- 跨合同发布/RNG 依赖：ADR-012 唯一拥有 `ProjectAuthorityHash` 与单发布点；ADR-013 唯一拥有 RNG compatibility contract
- 下游消费者：ADR-009、ADR-010、ADR-012、ADR-007 umbrella
- 产生工作包：R0B-01A-D/01A、R0B-04B-D/04B、COR-L01/04

本文是评审草案，不是生产 schema，也不授权实现 `LanguageState v3`、正式 reducer、Genesis 创建入口或新的权威 writer。只有本 ADR，或在 ADR Index 中具名登记、标为 `Accepted`、显式 `supersedes/replaces ADR-014` 且附逐条覆盖矩阵与同等独立评审的替代 ADR，被接受并且 G0B 关闭、G1 已通过后，相关持久化实现才可进入 WS-1。

计划依赖为：

```text
ADR-006
├─ ADR-008 RegistryBundle
├─ ADR-011 Operation/Run identity
└─ R0B-01 Meaning/Task Contract
         ↓
       ADR-014
         ↓
       ADR-009 typed ChangeSet
         ↓
       ADR-010 Genesis trust
         ↓
       ADR-007 umbrella final acceptance
```

ADR-008 决定 typed feature/value，ADR-011 决定 Operation/Run/Job 身份；它们都不代替本 ADR 的语言实体与 realization 决定。Capability Matrix 与 TaskPack 是接受证据，不是领域身份来源。

## 2. 用户与研究问题

Telysta 必须回答：

1. 一个“词”、一个义项、一个词形、一个词素、一个范式格位和一个构式各自是什么身份；
2. 从场景意义到句子，再从句子回到许可意义时，哪一层是权威；
3. 零实现、同形、同音、多义、融合、异形、缺陷范式和合法歧义如何存在，而不被字符串修复或随机 fallback 抹掉；
4. realization、analysis、evaluation 和 UI 查询如何保持只读；
5. v2 中无法恢复的顺序、意义和历史如何诚实迁移，而不是被推测为已知语言事实。

当前 Rust v2 和 Python legacy 都不能完整回答这些问题。若先写 v3 schema 或继续叠加规则，错误身份会被固化到 semantic hash、迁移和 replay 中。

## 3. 假设分类

| 假设 | 分类 | 本 ADR 的处理 |
|---|---|---|
| 权威实体必须有稳定、typed、可验证的身份 | Hard constraint | 闭合 ID kind、引用完整性和 constructor validation |
| 有序词素实现不能由 set 承载 | Hard constraint | ordered occurrence |
| query 不能改变语言 revision、history head 或 semantic hash | Hard constraint | Command/Query 分离 |
| 无法表达时不得伪造成功 | Hard constraint | typed `ExpressionGap` |
| `analyse(realize(M))` 在支持范围内应包含等价读法 | Software capability contract | 独立 equivalence oracle 与 contrastive foils |
| 某类词类、范式或对齐在语言中常见 | Empirical prior | 版本化数据与覆盖诊断，不设普遍必选项 |
| 频率、功能负载或加工压力影响某种结构 | Research hypothesis | 后续 `TheoryProfile`，不进入本 ADR 的确定性规则 |
| 用户偏好优雅、寒冷感、古老感或某类音形 | Creative preference | 候选约束/排序，不改变身份与语言学真值 |

## 4. 决策

### 4.1 权威 aggregate、writer 与 hash 边界

Rust 生产核心使用相互引用但不互相替代的权威 aggregate。这里的“Meaning Authority”不表示把每次场景或句意写入 `LanguageState`：

`LanguageState` 只有三个互斥的语义物化入口：

1. 新项目由 application service 从 `VerifiedGenesisArtifact` 物化 Genesis root；
2. 旧项目由 Rust application migration service 调用版本锁定的 importer，在全部 hard
   migration item 解决并取得不可反序列化的
   `ValidatedLegacyRootMaterialization` capability 后，物化唯一
   `LegacyHistoryBoundary` 与其 `ImportedCheckpoint` payload；
3. 任一 root 之后只允许 validated ChangeSet 经 reducer + `StateTransaction` 改变状态。

前两项只创建 root，不能用来绕过后续 ChangeSet。Storage adapter 只负责经授权对象的
物理原子发布；它只能消费 application service 产生的对应 root capability 或完整提交
组合，不拥有 LanguageState、root、effect 或 provenance 的语义构造权。下表中语言内部
实体的 ChangeSet 路径描述 root 之后的唯一修改路径。

| 对象 | 权威 aggregate | 唯一生产写入路径 | 完整性边界 |
|---|---|---|---|
| `SceneFacts`、`InteractionContext`、`CommunicativeIntent`、`PropositionGraph`、`PragmaticCommitments`、`LanguageSpecificObligations` | versioned TaskPack、已确认的 Operation input 或 AuthorCanon artifact | application command 在对应 artifact 合同内创建；query 只读 | 各自 content/request/canon hash；不进入 `StateSemanticHash` |
| language-internal `SenseMeaning`、`PredicateFrame` 与 typed semantic relation | `LanguageState.MeaningInventory` | validated ChangeSet + reducer + `StateTransaction` | `StateSemanticHash` |
| language-internal category、Construction、selection、agreement、linearization、morphology 与 morphophonology | `LanguageState.GrammarInventory` / Morphology inventory | validated ChangeSet + reducer + `StateTransaction` | `StateSemanticHash` |
| Lexeme、Sense、WordForm、Morpheme、Paradigm、ordered occurrence 与 state-level etymological references | `LanguageState` 的 Lexicon/Morphology/Meaning inventories | validated ChangeSet + reducer + `StateTransaction` | `StateSemanticHash` |
| 正字法 policy、grapheme inventory、WordForm spelling base/variant 与 OrthographyRevision | `LanguageState.OrthographyInventory`；细节见 §4.4A | validated root/ChangeSet；查询不得物化缺失 base | `StateSemanticHash` |
| realization、analysis、IGT、trace 与 candidate ranking | revision-bound `ProofCarryingUtterance` / analysis artifact | pure query service；不能取得 state writer capability | artifact content hash；不进入 `StateSemanticHash` 或 `HistoryHeadHash` |
| ComparativeConcept、Concepticon/CLICS 对齐与 typological gloss | versioned external alignment/data artifact | data import/curation boundary | data/alignment lock；不是 language-internal meaning |

源语言句子、英文 gloss、ComparativeConcept、Concepticon ID、LLM 提案、UI 标签和审美描述都不是 language-internal Meaning Authority。它们只能作为带 provenance 的输入、对齐或候选。作者接受一个 utterance 只改变 AuthorCanon；只有另行确认的结构意义编辑才能通过 ChangeSet 改变 `LanguageState`。

### 4.2 Meaning 分层

最小权威流程固定为：

```text
SceneFacts + InteractionContext
→ CommunicativeIntent + PragmaticCommitments
→ PropositionGraph + Reference + Scope
→ LanguageSpecificObligations
→ PredicateFrame + Construction selection
→ grammatical and lexical realization
```

- `SceneFacts` 描述任务中已确认的事实，不由目标句子的生成结果反向改写；
- `InteractionContext` 保存 speaker、addressee、deixis、speech act、register 和可访问指称；
- `CommunicativeIntent` 与 `PragmaticCommitments` 分离，避免把暗示或礼貌策略伪装成命题真值；
- `PropositionGraph` 使用 typed event、entity、role、reference、polarity、scope 和关系；
- `LanguageSpecificObligations` 记录目标语言强制要求但输入尚未确定的信息；
- 未满足义务必须要求用户确认、返回合法歧义或产生 typed gap，不能猜测。

ComparativeConcept 只用于跨语言对齐。多个 Lexeme 可以对齐同一 comparative concept；一个 Lexeme 可以拥有多个 Sense。对齐不得直接成为目标语言的 POS、格、时体或语义真值。

### 4.3 身份与所有权

目标 v3 至少使用以下关系：

```text
Lexeme ─owns──────────────→ Sense
Sense ─owns───────────────→ zero or more PredicateFrame
WordForm ─realizes────────→ Lexeme + FeatureBundle + ParadigmCell
Paradigm ─contains────────→ ParadigmCell
Morpheme ─owns────────────→ Allomorph
MorphologyInventory ─owns─→ RealizationUnit
MorphOccurrence ─ordered-in→ WordForm / Construction realization plan
Construction ─binds───────→ MeaningPattern + typed slots
GrammarInventory ─owns────→ LexicalClassDefinition
Lexeme / Sense ─assigned──→ LexicalClassDefinition
SurfaceForm ─derived-from─→ analysis graph + phonological representation
```

具体决定：

- `LexemeId` 在规则音变、普通屈折实现和身份保持的形式变化中保持稳定；lexical replacement、错误合并后的拆分或独立借词创建新 LexemeId；
- `SenseId` 表示一个 language-internal 义项，且恰有一个 owner Lexeme；相同或重叠的意义只能通过 typed relation/ComparativeConcept 对齐，不能让多个 Lexeme 共用同一个 Sense 实体。新增多义或 sense split 创建新 SenseId；identity-preserving 的显式属性修订保留 ID，并由 typed effect 记录；
- `PredicateFrameId` 表示一个 Sense 所拥有的 typed valency/frame 身份，保存角色、selection、编码义务和适用条件。Construction 只引用 Frame 并声明 role-to-slot mapping，不拥有 Frame。Frame 的 identity-preserving 修订使用 `PredicateFrameRevised`；frame split、独立 lexicalization 或重分析创建新 Frame ID，并以 typed `FrameAlternation` / source edge 连接旧新 Frame；
- `WordFormId` 表示一个 Lexeme 在一个规范化 FeatureBundle/ParadigmCell 下的词形身份。规则表面变化、条件 allomorph 选择或正字法变化不自动更换 WordFormId；新增 cell/bundle 或产生独立重分析的 grammatical word form 才按 typed effect 创建新身份；
- `MorphemeId` 表示抽象功能/意义贡献，不等于 IPA 字符串。形式磨损可保留 MorphemeId；重分析或新的构式化单位创建新 ID；
- `AllomorphId` 恰由一个 Morpheme 拥有，并保存 typed condition、适用层级和 provenance；不能只由相同表面字符串推断所有权；
- `RealizationUnitId` 表示 MorphologyInventory 中可被 ordered occurrence 引用的 typed exponent specification，而不是一次 surface token。普通音系输出变化保留 ID；贡献集合、variant kind 或分析所有权发生重分析时创建新 ID，并保留 typed source edge；
- `ParadigmCell` 由 language-internal feature bundle 和适用条件定义，不由英语标签或表格位置定义；
- `ConstructionId` 表示意义—槽位—形式配对。重分析产生新 ConstructionId，并保留来源边；普通版本化属性修订使用 typed effect；
- `LexicalClassDefinition` 由 language-specific `GrammarInventory` 拥有；它引用 ADR-008 `RegistryBundle` 中的 feature/value 定义而不复制定义。Lexeme 可以拥有多个 assignment，且 assignment 可以受 Sense、Construction、lect 或 typed grammatical environment 条件约束，不能压成一个普遍单值 `word_class`；历时有效性由 revision/ChangeSet history 表达，不把 current revision 反写成 assignment condition；
- `SurfaceForm`、IGT、候选排序和解析 forest 是 revision-bound projection，不独立获得权威语言身份。

实体是否“延续同一身份”必须由有限 typed effect 决定，不能由 IPA 字符串相等、gloss 相等或实现代码的对象复用隐式决定。

#### 4.3.1 Entity ID schema 决定

当前 `telysta-entity-id.v1` 的 kind 目录保持冻结，不在原 parser 中静默加入新 kind。LanguageState v3 使用并锁定 `telysta-entity-id.v2`：

- v2 保留 v1 的文本语法和全部既有 kind，并增加至少 `word-form`、`allomorph`、`realization-unit`、`paradigm`、`paradigm-cell`、`predicate-frame` 与 `lexical-class`；
- v1 项目中已存在的 EntityId 在迁移后保持逐字节稳定，不因 schema 升级、显示名、gloss、IPA、拼写或 map 排序而重新派生；
- 新 v3 ID 只能由 project-stable namespace、typed owner 和非显示性 stable key 派生；每一 kind 的 stable-key contract 必须进入 wire contract 与 migration fixture；
- `FeatureBundle` 是针对锁定 RegistryBundle 规范化的值，不是 EntityId；
- `MorphOccurrenceId`、analysis node 和 trace node 是 owner-scoped local ID，不进入全局 EntityKind；其局部唯一性、顺序和引用仍由 constructor、hash 与 replay 校验；
- v1 parser 继续拒绝 v2-only kind；v2 envelope 必须显式声明并锁定 entity-ID schema，loader 不得根据字符串内容猜版本。

具体 Rust enum 和 wire 字段仍在实施切片中完成，但实现不得改变上述兼容、派生和迁移语义。

### 4.4 有序 realization 与复杂形态边界

`Lexeme.morpheme_ids`、`Construction.morpheme_ids` 或等价字段不得使用 set 表达顺序。目标模型使用 ordered `MorphOccurrence`：

- occurrence 有 owner-scoped local ID、稳定顺序、`RealizationUnit` 引用、typed contribution、边界和可选 surface span；
- 同一 Morpheme 可重复出现；
- zero realization 保留语法贡献但没有 surface span；
- syncretism 保留不同 WordForm/ParadigmCell/analysis 身份，但允许它们共享同一 realization plan 或 SurfaceForm；
- homophony 允许不同 WordForm/analysis 共享同一表面字符串；
- compound 保存 ordered parent、角色和 morpheme boundary，不按 IPA 字符串切半；
- fusion、portmanteau、allomorphy、reduplication、不连续实现和 defectiveness 必须有明确 capability 状态；未实现时返回 typed gap，不得 silent no-op。

`RealizationUnit` 是闭合、版本化的 exponent union，而不是 Allomorph 的别名：

每个 union value 都有共同的 `RealizationUnitId`、inventory owner、provenance
与 variant tag；下列代码块只展开 variant payload：

```text
RealizationUnit =
  AllomorphicExponent {
    allomorph_id,
    one morpheme contribution,
    ordered form parts
  }
  | FusedExponent {
      two or more typed morpheme/feature contributions,
      ordered form parts
    }
  | ZeroExponent {
      one or more typed morpheme/feature contributions,
      no surface span
    }
  | capability-gated future variant
```

Allomorph 始终只有一个 owner Morpheme；fusion 不伪装成被任意一个 Morpheme 单独拥有的 Allomorph。不同环境选择同一 Morpheme 的不同 Allomorph 不改变 WordForm 身份。新增 variant 会改变持久化和 replay 语义，必须通过显式 schema migration；不能用自由字符串扩展。

WS-1 最低支持 ordered morphology、zero 和 syncretism。其他机制可以为 `planned`，但目标身份结构不能迫使未来靠字符串补丁实现。

#### 4.4A 正字法身份与投影（新增 Proposed 决定）

用户问题是：两个同音词能否保留不同拼写，音变后能否保留古老拼写，词典、
句子、IGT 与语言文档是否能引用同一份拼写依据。当前 v2 没有这些能力。
本节及 [review vectors](../../tests/fixtures/orthography_review_vectors_v1.json)
均可随评审修订，不是 frozen fixture 或生产 wire schema。

拟选择 **typed WordForm/occurrence 身份 + 显式 orthographic base**：

| 对象 | 身份与 owner | 写入及 hash |
|---|---|---|
| OrthographyInventory | LanguageState 拥有；包含字素、normalization/边界策略、拼写规则和基底引用 | Genesis/legacy root 或 validated ChangeSet；进入 StateSemanticHash |
| OrthographicForm | WordForm-scoped stable local key；同一 WordForm 可以有具名 canonical/variant form | 显式物化的有序 grapheme/base 或有锁的形态拼写推导；进入 StateSemanticHash |
| OrthographyRevision | 提交前分配的 revision identity，不能从 post-state hash 派生 | 内容、引用和 provenance 进入相应 state/hash；历史由 ADR-009/012 发布 |
| SpellingRealization | query artifact；键含 typed analysis/occurrence、language revision、OrthographyRevision 与相关 locks | 纯查询、独立 content hash；不进入 StateSemanticHash |
| IGT / SpellingAnalysisForest | 同一 analysis graph 的 revision-bound 投影 | 纯查询、独立 content hash；不得产生第二份词素/意义真相 |

`OrthographicForm` 的 local key 不由显示字符串、IPA、排序、candidate hash
或 post-state hash 导出。拼写修订保留其身份；新增独立 variant 创建新的 key。
WordForm 身份不因换字体、Unicode 表示或拼写改革改变。这里不增加生产
`EntityKind`；若评审选择全局 OrthographicFormId，须同时修改 EntityId 合同、
迁移向量与覆盖清单，不能悄悄扩展 parser。

orthographic base 保存显式 grapheme identity/顺序/边界，或引用版本锁定的
morpheme spelling base 和 typed realization plan；它不是当下发音的显示缓存。
Genesis 或显式新增词形命令可以使用 typed phonology + owner/lexical context
编译初始 base；query 不能为缺失 base 自行创建 state entity。最小 WS-1 先
覆盖固定 TaskPack 的 word forms，不据此宣称能处理任意文字系统或新词。

`SoundChange` 只改变 typed phonological effect，不重建上述 base。更新读音
后 `spell` 仍按旧 base/revision 输出保守拼写；选择更贴近新读音的拼写必须有
独立 `OrthographicChange`、author/provenance、影响清单和 replay。productive
拼写也必须从锁定 base/形态结构推导，不能藏一个“当前 phonology → 字符串”
查询，让声音变化在未提交拼写改革时静默改写文字。拼写改革只改变正字法
相关 state/history；不能因此伪造 phonological change 或新 WordForm 身份。

保守拼写的反向路径必须先解析到当前 language revision 许可的 typed
WordForm/occurrence analysis，再引用其当前 phonology 与 morphophonological
realization plan。旧 base 不是旧发音的权威缓存。音段删除或合流后，旧拼写
仍须回到该词形的新读音；同音异写可保留不同词形，不能靠字母逐一反推音段。
音变使旧 revision 的 PCU/IGT 过期，即使 OrthographyRevision 没有变化。

Unicode 与 span 拟定边界：

- 以 NFC 比较/规范化允许的书写表示，同时保留 AuthorCanon/导入来源原始
  字节；不会因 canonical equivalence 合并两个 lexical identities。
- 不默认 NFKC、大小写折叠或去变音符号；兼容字符合并必须由具名、版本化
  policy 决定并列出冲突。normalization 不是正字法改革，更不是音变。
- Unicode data version、normalizer、segmenter/tailoring 与策略都锁定。研究
  参照为 [UAX #15 rev58 / Unicode 18](https://www.unicode.org/reports/tr15/tr15-58.html)
  与 [UAX #29 rev49](https://www.unicode.org/reports/tr29/tr29-49.html)；不因此
  宣称当前 Python/Rust 已实现 Unicode 18。生产版本需在依赖审查时明确选择。
- Unicode grapheme cluster 不是语言学 grapheme、phoneme 或 morpheme；如
  一个 digraph 可有两个 clusters。字素表和 typed segmentation 另行定义。
- artifact span 使用明确 source artifact + normalization revision + UTF-8
  byte interval；raw→canonical alignment 单独保存。Webview 的 UTF-16 offset
  不能直接当 byte span；zero contribution 使用显式 anchor/empty span。
- 分别 NFC 的形素片段拼接后未必仍为 NFC，最终书写 artifact 按锁定 policy
  规范化，并保存跨片段合成/组合符重排的多对多 alignment。两个 contribution
  可以指向同一 canonical byte span；原始 occurrence 顺序与身份仍保留。
  Unicode 合成不构成形态 fusion，重排组合符也不能重排 MorphOccurrence。
  参照 [UAX #15 §1.4](https://www.unicode.org/reports/tr15/tr15-58.html#Concatenation)。

`parse(spell(A,O),O)` 必须包含等价 typed analysis，并排除锁定的 forbidden
reading。不同同音词不能只靠 phoneme string 选择拼写；同形/合流可以返回多
分析，但每项必须由 Grammar/Lexicon 许可，预算不足显式返回 incomplete/gap，
不能用“返回全部分析”或静默截断冒充成功。缺失 mapping 返回 typed gap，
禁止 raw IPA fallback。正向和反向都绑定同一 revision、orthography、registry
与 Unicode policy；变更这些输入使旧 PCU/IGT 证据过期。

IGT 的写词行、形素分段、gloss 与翻译从同一分析图投影。zero、syncretism、
fusion 允许贡献和 span 非双射；glossing 标记不是目标语言新增的文字、词素
或意义。规则来源参照 [Leipzig Glossing Rules](https://www.eva.mpg.de/lingua/resources/glossing-rules.php)，
不把规范展示当作真实分析已通过的证明。缺失映射的 v2/legacy 输入只能产生
`NeedsResolution`/`ArchiveOnly` 或 non-executable `OrthographyUnavailable`；
不能从 IPA、字形外观或英语 gloss 推断未保存的正字法身份和历史。

替代方案仍供 reviewer 比较：仅 phonology-keyed projection 会丢同音异写与
保守拼写；每次音变自动重拼写会混淆两个过程；全部只存 display string 会
丢失字素/边界与 typed analysis 关联。显式 base 的成本是维护拼写来源、
形态推导和迁移缺口；若选择更轻的替代，须逐项通过同等反例。

### 4.5 Language-internal categories

语言完整性以功能能力而不是英语 POS 清单判断：

- language-internal category 与 comparative concept 分开；
- 没有独立 pronoun 类但由 demonstrative、agreement、zero anaphora 或构式完成指称，不构成自动失败；
- 没有独立 adjective 类但由 stative predicate、relative/participial construction 或名词性策略完成修饰，不构成自动失败；
- UI 可以展示跨语言辅助标签，但持久化状态必须引用目标语言自己的 category/Construction/feature；
- Capability Matrix 是 supported/planned/rejected 的唯一产品展示来源。

### 4.6 双向 realization/analysis

生成和分析共享同一 Grammar/Lexicon authority：

```text
realize(revision, meaning, context, options)
  -> Candidate<ProofCarryingUtterance> | ExpressionGap

analyze(revision, surface, context, options)
  -> AnalysisForest<MeaningCandidate> | AnalysisGap
```

`ProofCarryingUtterance` 至少引用：

- language/revision/lect；
- Meaning 与 InteractionContext hash；
- Grammar、Lexicon、Registry 和 Capability locks；
- Construction、PredicateFrame、Lexeme、Sense、WordForm、MorphOccurrence；
- morphophonology、prosody、orthography/phonological form、IGT 与 trace；
- known ambiguity、typed gaps 和非权威 ranking diagnostics。

在冻结 Capability Matrix 与 TaskPack 范围内：

- `analyze(realize(M))` 必须包含经独立 equivalence checker 确认的等价读法；
- contrastive foils 和 forbidden readings 必须被拒绝；
- 合法歧义可以保留并逐项报告；
- ancestor、opposite、英语 gloss、随机造词和丢弃论元都不是合法 fallback；
- gradient ranker 只能排序已通过 hard validation 的候选。

partial realization 只有在调用者显式请求且结果同时列出未满足 obligations 时才允许；它不能获得“完整表达成功”的能力声明。

评审用 [Meaning vectors](../../tests/fixtures/meaning_review_vectors_v1.json)仍是
mutable planning notation：分别攻击否定/量化 scope、承诺状态、speech act 与
显式报告内容/来源。有限 scene 的不同真值可见证非等价；相同真值不证明一般
等价。捕获规避的 alpha relation 是有限支持域的保守检查，不是完整意义判定器。
中性 `Ask(Report(r,p))` 不承诺 p 的例子不定义所有语言 evidential 的承诺性质。
当前没有 production adapter 或表达成功证据；永远返回 gap、reject-all 或把所有
读法加入 forest 的实现均不能通过 declared supported profile 的完整表达验收。

### 4.7 Command/Query 分离

`realize`、`analyze`、`explain`、`evaluate`、projection query 和 UI preview 是纯 query：

- 不得调用 `StateTransaction`；
- 不得新增 Lexeme、Morpheme、Construction、portmanteau 或 grammar rule；
- 不得标记实体死亡或“学习”分析；
- 不得改变 revision、history head、event count 或 semantic hash；
- cache、index、parse forest 和 candidate list 必须可删除重建。

若用户接受新词、新构式、重分析、作者例外或 grammar repair，application service 必须创建显式 Command/Operation，产生 Proposed/Validated ChangeSet，并经过 expected-history-hash 与 StateTransaction 提交。

Query 可以使用确定性搜索；若 evaluator 或候选抽样需要随机性，必须使用独立、版本化、进入证据的 `RngTree` path，不得使用全局随机源，也不得复用 compiler 私有流。

### 4.8 Event kind 与变化对象

以下效果不得编码为 `SoundChange`：

- MorphophonologicalChange；
- Reanalysis / ConstructionChange；
- AnalogicalChange / ParadigmRestructuring；
- SemanticChange / LexicalReplacement；
- Borrowing；
- OrthographicChange；
- AuthorialOverride。

ADR-009 的有限 effect IR 至少必须能分别表达 `SenseIntroduced/Shifted/Retired`、`PredicateFrameIntroduced/Revised/Split`、`FrameAlternationChanged`、`LexicalClassAssignmentChanged`、`WordFormRealizationChanged`、`AllomorphIntroduced/ConditionChanged`、`ParadigmRestructured` 与 `ConstructionReanalyzed`。effect 名称可在 wire schema 中调整，但不得用一个无类型 `EntityUpdated` 或完整状态替换掩盖这些身份和 owner 语义。

同音不是必须修复的 hard error。类推必须引用范式、构式或可检验 schema；语法化必须引用源构式、桥接语境、旧新分析及后续采用模型。WS-1 只冻结对象和负例，真实传播机制留给 WS-2。

### 4.9 Provenance

每个权威实体、每个 identity-preserving revision 和每个 identity-changing effect 必须
使用以下互斥的 origin 联合类型之一，不能把 Genesis 或 legacy root 伪装成 ChangeSet：

```text
StateProvenanceOrigin =
  GenesisOrigin {
    operation_id,
    genesis_origin_id,
    dependency_bundle_hash
  }
  | LegacyImportOrigin {
      operation_id,
      legacy_history_boundary_id,
      importer_lock,
      dependency_bundle_hash
    }
  | ChangeOrigin {
      operation_id,
      change_set_id,
      effect_id
    }
```

`GenesisOriginId` 必须在 candidate 编译前由 Genesis Operation 稳定分配，且不得依赖
candidate、post state、`StateSemanticHash` 或 artifact content hash。
`LegacyHistoryBoundaryId` 同样必须在 state migration 前预分配而不能使用 checkpoint
content address；`ChangeSetId`/`EffectId` 遵循 ADR-009 的 reduction 前分配合同。三种
origin 的身份与引用必须在对应物化/reduction 前确定。它们共享可适用的
author/compiler/migration/process、typed source entity/多父来源、Registry、RulePack、
DataSlice、TheoryProfile、RNG locks 与 evidence/creative basis。pre revision/hash 可进入
相应操作或 effect provenance；post revision/hash 只在物化结果、ChangeSet envelope 或
history node 计算后记录，不能反向写入参与同一 post hash 的 state provenance。

`GenesisOrigin` 只有在 candidate 被封印为 `VerifiedGenesisArtifact` 并由 application
service 消费时才成为权威。artifact content hash 只允许进入下游 Genesis history
root、OperationRecord 或 ProjectManifest 对象图，不得写回该 artifact 所包含 state 的
provenance。`LegacyImportOrigin` 只能来自 `ValidatedLegacyRootMaterialization`，且永远
不取得或冒充 `VerifiedGenesisArtifact`；root 之后的任何修订只能使用 `ChangeOrigin`。

复合、借词、colexification 和重分析可能有多父 provenance。模型不得用单一 `source_id` 强行丢失来源角色或顺序。

### 4.10 Semantic hash

v3 `HashCoverageManifest` 必须逐字段说明 included/excluded、所属 hash 和理由，并分离三个非循环权威 hash：

1. `StateSemanticHash`：当前 `LanguageState` 规范状态的 hash；
2. `HistoryHeadHash`：Genesis/Legacy root 与 parent-linked committed ChangeSet 序列的 head hash；
3. `ProjectAuthorityHash`：由 ADR-012 唯一定义和发布的项目组合 hash；本 ADR 只要求它消费 `StateSemanticHash`/`HistoryHeadHash` 且保持无环，不重定义其完整字段集。

固定计算方向为：

```text
pre StateSemanticHash + expected HistoryHeadHash
→ validated ChangeSet
→ reducer
→ post StateSemanticHash
→ ChangeSetContentHash
→ next HistoryHeadHash
→ construct complete candidate manifest/object references without authority_hash
→ ADR-012 ProjectAuthorityHash
→ fill and validate authority_hash
→ atomic manifest publish exactly once
```

ChangeSet 可以保存 pre/post `StateSemanticHash`，但 committed ChangeSet envelope 和完整历史不得进入 `StateSemanticHash`；否则会形成 post-hash 自引用。相同当前状态和不同历史允许拥有相同 `StateSemanticHash`，但必须拥有不同 `HistoryHeadHash`。

state-level provenance 可以引用在 reduction 前已确定的
ChangeSetId/EffectId（event projection identity）、OperationId 和 typed source edge；
这些身份不得从 post-state 或 `ChangeSetContentHash` 派生。如果
`ChangeSetContentHash` 依赖 post `StateSemanticHash`，该 content hash 只能进入
history node，不能反向写入同一个 post state。任何 provenance link 的计算顺序必须在
HashCoverageManifest 中证明无环。

至少进入相关 domain/full `StateSemanticHash`：

- 稳定身份、owner 与 typed references；
- Sense、PredicateFrame、Construction 与 language-internal category；
- FeatureBundle、ParadigmCell、RealizationUnit 与 ordered MorphOccurrence；
- 权威 underlying/phonological representation；
- OrthographyInventory 的 policy、grapheme/base、mapping 与 lexical variant
  身份/引用；不包含 SpellingRealization/IGT 的派生查询内容或其 post hash；
- accepted lexical/grammar/language-internal meaning 的当前结果；
- 解释这些字段所必需的 schema、EntityId schema、RegistryBundle lock 与 state-level provenance references。

Rule/Data/Theory/RNG/TaskPack/evaluator locks 默认进入 `GenesisArtifactEnvelope` / `VerifiedGenesisArtifact`、Operation、ChangeSet、dependency bundle 或 history hash，而不因为曾参与一次操作就自动进入 `StateSemanticHash`。若某个当前 state entity 的解释确实依赖外部 payload，state 保存其 versioned typed reference/hash；`HashCoverageManifest` 必须逐项说明该引用为何属于 state。

不得进入 `StateSemanticHash`：

- committed ChangeSet envelope、history node 或 RunLedger；
- Job/Attempt/worker/heartbeat；
- Task/Operation/Canon 中的实例 Meaning；
- UI selection、窗口和编辑器布局；
- cache、projection、parse forest 和 candidate ordering；
- 可重建 statistics；
- 未接受的 LLM/author proposal。

查询、TaskPack、Canon、realization evidence 和其他派生/外部工件仍必须拥有自己的 content hash，并绑定所读取的 state revision、Meaning request、Registry、Grammar、Rule/Data locks；“不进入 StateSemanticHash”不等于“不需要完整性”。

hash 算法、覆盖或规范排序改变必须版本化并记录 baseline 变化。不同 schema 的原始 hash 不要求相等；迁移必须提供 source/target `StateSemanticHash`、source/target history hash 与 field mapping/loss report。

### 4.11 v2/legacy 迁移

- WS1-01 只做 v2 state-only shape migration；不得迁移或合成未知历史；
- v2 set 无法证明词素顺序时，迁移器不得按 ID、IPA 或当前迭代顺序猜测；
- 无约束 `semantic_frame` 只有在精确、版本化 mapping 存在时才能转换，否则产生 typed unresolved/loss item；
- 缺失 Sense、PredicateFrame、category 或 provenance 时，迁移停止或生成需作者确认的 non-executable artifact；
- 明确的 `MigrationResolutionMap` 可以记录经评审的人为消歧；没有 resolution 的结果只能是 `ArchiveOnly` 或 `NeedsResolution`，不能进入可执行 WS-1 状态；
- v2 完整状态历史进入 ADR-009 唯一 persisted kind `LegacyHistoryBoundary`。该 boundary 内含一个 imported checkpoint、source archive ref/hash、loss report、migration resolution ref、迁移器版本和 provenance discontinuity；`ImportedCheckpoint` 只是 boundary payload，不是第二种 replay root；
- 不从 state diff 推断 SoundChange、Analogy、Grammaticalization、Borrowing 或 community history。
- 缺失 orthographic base/mapping/variant identity 时，不用现有 IPA 自动补齐；
  产生具名 unresolved item，经评审 resolution 后才可物化可执行状态。

迁移结果在 unresolved hard item 清零前不得取得任何 root materialization capability；
全部解决并通过 state-only migration validation 后，只能取得独立的
`ValidatedLegacyRootMaterialization`。它永远不得取得 `VerifiedGenesisArtifact`，
也不能授权 root 之后绕过 ChangeSet 的状态写入。

### 4.12 Capability、UI 与 LLM

- `supported`：compiler、realizer、analyzer、validator 和 evaluator 都有当前证据；
- `planned`：schema/设计允许但当前不能执行，UI 显示不可用；
- `rejected`：当前产品范围明确不支持，返回 typed gap；
- LLM 可以把自然语言解析为 Meaning/Rule/Authoring proposal，但不能创建权威实体、validated capability 或提交 ChangeSet；
- Webview 不能提交 LanguageState、Grammar、history 或自称 verified 的 realization artifact。

## 5. 最小目标类型草图

以下只用于评审关系，不是生产 wire schema：

```text
LanguageStructureState
├─ MeaningInventory
│  ├─ Sense
│  ├─ PredicateFrame
│  └─ typed semantic relations
├─ GrammarInventory
│  ├─ LanguageInternalCategory
│  ├─ Construction
│  └─ selection / agreement / linearization
├─ Lexicon
│  ├─ Lexeme
│  ├─ WordForm
│  └─ Etymon / provenance links
├─ Morphology
│  ├─ Morpheme / RealizationUnit
│  ├─ Paradigm / ParadigmCell
│  └─ ordered MorphOccurrence
└─ OrthographyInventory
   ├─ Grapheme / normalization and boundary policy
   ├─ OrthographicForm / locked spelling base and variants
   └─ OrthographyRevision / typed mapping rules
```

具体 Rust 类型、ID 编码和 wire schema 只有在本 ADR 与 ADR-007/008/009 的依赖图接受后才可冻结。

## 6. 明确拒绝的替代方案

| 方案 | 拒绝理由 |
|---|---|
| 以 IPA 字符串和 gloss 作为跨域主键 | 同音、多义、零实现、融合和历时连续性不可表达 |
| 一个 `LexicalEntity` 同时承担 lexeme/sense/form/history | 身份变化、意义保持和 provenance 无法区分 |
| 使用 set 保存 morpheme IDs | 顺序、重复、零和不连续实现不可回放 |
| realization 时动态学习词素/构式 | query 修改权威状态，结果依赖调用顺序 |
| 不能表达时选择 ancestor/opposite 或随机造词 | 产生貌似成功但意义错误的句子 |
| 自动消解所有同音 | 把合法状态误作 hard error，并伪造形态变化 |
| 从 v2 state diff 推断真实历史事件 | 不可辨识；伪造机制 provenance |
| generator 使用自己的自然度总分自证 | 无独立 oracle，无法定位过生成或错误接受 |

## 7. 后果

正面后果：

- 生成、分析、IGT、词典、历史和 UI 使用同一身份与 Grammar authority；
- 可以明确表达同音、多义、零、syncretism、缺口和合法歧义；
- Query/Command、provenance、migration 和 semantic hash 有可测试边界；
- 后续历时变化作用于正确的语言学对象，而不是字符串。

成本：

- v3 schema、迁移器、reducer、realizer/analyzer 和 evaluator 必须联合设计；
- v2/legacy 中部分顺序、意义和历史只能报告损失，不能自动恢复；
- WS-1 必须缩小到两个 profile 和冻结 TaskPack，不能同时实现全部形态/语义机制。

## 8. 不在本 ADR 中决定

- 最终 Meaning formalism 或 parser algorithm；
- 完整语法 feature 目录；
- MaxEnt、neural 或其他候选 ranker；
- 全部 fusion/allomorphy/reduplication/defectiveness 实现；
- SpeechCommunity、扩散、接触和真实语法化模型；
- 文学成熟度、诗律和 TTS；
- 插件执行边界。

这些能力不得通过自由字符串提前进入权威状态。

## 9. 接受条件

本 ADR 只有同时满足以下条件才能标记 `Accepted`：

1. 具名 domain owner、architecture reviewer、linguistics reviewer 和 migration reviewer 已记录；作者和 owner 均不占任一 independent reviewer 槽位；
2. 与 ADR-007/008/009/010/011/012/013 的依赖无环，identity、writer、Genesis root、project publish、RNG 和 replay 责任不重叠；
3. 两个结构非同构 profile 能由同一关系模型表达，而不是只替换标签；
4. `tests/fixtures/linguistic_regression_cases_v1.json` 的全部 positive/negative/purity/determinism case 经过评审；
5. `tests/fixtures/legacy_replay_migration_cases_v1.json` 映射全部 8 个 strict-xfail，且没有伪造历史；
6. Capability Matrix 明确 WS-1 的 supported/planned/rejected；
7. Meaning、Grammar、Lexical/Morphological、Realization、HashCoverage 和 migration 合同均有唯一 owner；
8. `telysta-entity-id.v2` 的 kind/stable-key/migration 合同、state-only migration mapping、state-level provenance ID 顺序和 `StateSemanticHash` coverage/非循环测试向量均已冻结；`HistoryHeadHash` 与 `ProjectAuthorityHash` 向量分别由下游 ADR-009 与跨 Gate ADR-012 验收，不作为本 ADR 的循环接受前置；
9. ADR review-evidence manifest 已绑定本决定、fixture subject hash 和 reviewer attestation；它只用于接受 ADR，不冒充最终 G0B GateEvidence；
10. ADR 接受后，最终 G0B GateEvidence 再引用 Accepted ADR 与 R0B-01～07 的完整证据；本 ADR 仍不单独授权实现，生产 v3 继续等待 G1 + G0B。
11. R0B-04B-D 的正字法/IGT/PCU planning vectors 已独立审阅，身份、base、
    normalization、同音异写、非双射 span、hash/迁移和保守拼写决定闭合。
    R0B-04B 的 frozen hostile pack 必须在 ADR Accepted 后重写、绑定版本与
    reviewer；不能要求生产 runner 先通过再接受本 ADR，形成依赖循环。

## 10. 实施顺序

1. 冻结回归与迁移 fixture；
2. 接受本 ADR，或接受 ADR Index 所定义的显式 replacement ADR；
3. 冻结 Meaning/Grammar/phonology/lexicon/valency 合同与 Capability Matrix；
4. G1 + G0B 后实现 minimal State v3 与 state-only migration；
5. 实现 in-memory Meaning/Grammar/realize/analyze 纵切；
6. 实现 typed ChangeSet/reducer，再接 append-only history；
7. 由 VerifiedGenesisArtifact 创建生产 GenesisRoot；
8. 完成 Tauri proof-carrying 纵切和独立 evaluator；
9. G2 通过后才扩展 R3 authoring 与清理 legacy。
