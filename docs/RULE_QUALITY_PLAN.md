# 规则系统与语言质量计划

- 状态：`Proposed domain plan；R3/R4 split adopted by main plans`
- 基线日期：2026-07-12
- 目标：从“不断添加规则类”升级为可验证、可组合、可解释的语言演化规则平台

> **路线状态说明（2026-07-16）：** R3 的作者结构转换与 R4 的 ChangeProcess 规则分层；任何生产规则都须使用 typed ChangeSet、锁定的 Registry/TheoryProfile/evidence、RngTree 与 StateTransaction，并以三份主计划和 Accepted ADR 为准。

## 1. 规则系统目标

每条规则必须能够回答：

- 它在什么时代、语言画像和上下文中适用？
- 它修改哪一种状态？
- 哪些条件会触发、阻止或修复它？
- 它与其他规则冲突时按什么顺序执行？
- 它为什么改变了这个词或类型学状态？
- 它是否可复现、可回放、可迁移？

## 2. 统一生命周期

```text
RuleSpec
  → Parse
  → Compile
  → Validate
  → Conflict Analysis
  → Dry Run
  → ProposedChangeSet + Canon Impact + Explanation
  → domain validation and explicit author/process decision
  → Apply through StateTransaction
  → committed typed ChangeSet / events / explanation
```

规则不得直接绕过事务原地修改生产状态。

## 3. RuleSpec 最小结构

```yaml
schema_version: 1
id: phonology.final_vowel_drop
version: 1
domain: phonology
enabled: true

trigger:
  time_range: {model: telysta-time-model.v2, start: 100, end: 300}
  lect_ids: [lect.proto]

target:
  natural_class: {syllabic: true}
  position: word_final

conditions:
  all:
    - not_stressed
    - preserves_nucleus
    - legal_output

operation:
  type: delete

application:
  mode: authorial_structural
  evidence_class: creative_preference
  process_binding: none

effects:
  state: lexicon
  emit_event: true

examples:
  positive:
    - {input: kata, output: kat}
  negative:
    - {input: ta, stress: final, output: ta}
```

最终 schema 应通过 JSON Schema 或等价机制验证，并独立于具体执行后端。

上例只表示 R3 的作者批准结构变换。R4 的过程规则必须另行引用 `TheoryProfileId`、typed process state、observation model、参数/先验、distribution version 与稳定 `RngTree` path；不得给一条结构规则增加自由 `probability` 字段，就把它包装成社会传播。

## 4. 规则包结构

```text
rules/
├── phonology/
├── morphology/
├── grammaticalization/
├── semantics/
├── syntax/
├── borrowing/
└── repair/
```

内置规则包只收录达到准入标准的规则。研究性规则进入 `experimental` 包，默认关闭。

## 5. 规则准入标准

每条默认规则至少具备：

- 正例与反例；
- 固定 seed 的确定性测试；
- 前置条件和阻断条件测试；
- 输出不变量测试；
- 与相邻规则的组合顺序测试；
- 事件与解释内容测试；
- 历史回放一致性测试；
- 适用语言画像说明。

音系规则还必须证明：

- 输出可被 inventory 正确 tokenize；
- 保持或经过 repair 恢复音系合法性；
- 不会无意清空所有音节核；
- backend parity 在适用范围内成立。

词汇和形态规则还必须证明：

- 不破坏核心概念保护；
- 不产生非法 DAG 环；
- morpheme table、stage 和 feature presence 同步；
- 词长、复合深度和派生数量受物理上限控制。

## 6. 冲突与解释

规则编译阶段应检测：

- 同一 target/context 的覆盖；
- 删除规则与后续 change 规则的不可达关系；
- 互为逆操作导致的振荡；
- repair 规则再次触发原规则的循环；
- 同一状态字段的未声明写冲突。

每次应用至少记录：

- rule ID 和版本；
- 输入和输出；
- 命中的条件；
- 对 authorial rule 记录批准与 canon impact；对 process rule 记录 TheoryProfile、参数/先验、observation、distribution version、RngTree path/counter 与抽样结果；
- repair 或 rollback；
- 受影响的实体和 DAG 边。

## 7. 创作偏好与过程理论分离

质量评价不能假设所有语言都应趋向同一种平均形态。项目可以声明创作目标画像，例如：

```yaml
morphosyntax: agglutinative
word_order: SOV
phonotactics: moderate
sound_impression: restrained
register_goal: ritual_formal
```

这些字段是可解释的 `CreativePreference`，只能影响候选比较或作者提案，不能直接成为变化率。接触、侵蚀、语法化或词汇替换属于锁定 `TheoryProfile` 的研究模型参数，必须通过 Observation/ChangeProcess 影响结果。质量系统分别检查硬约束、与创作目标的匹配、模型适用域和自身历史一致性，而不是简单奖励某一种类型学。

## 8. 质量维度

| 维度 | 示例指标 |
|---|---|
| 音系合法性 | 非法音节率、未知音素率、修复失败率 |
| 音变自然性 | 环境条件覆盖、无条件突变比例、规则振荡 |
| 词汇健康度 | 核心词存活率、词长分布、更新率、词汇真空 |
| 同音控制 | 同音密度、消歧成功率、过度附加率 |
| 形态一致性 | domain state 与词缀、feature presence 的一致性 |
| 意义/语法能力 | required meaning、under/over-generation、forbidden reading、歧义与 ExpressionGap 正确性 |
| 历时连续性 | 可追溯现代词比例、断裂 DAG 节点数 |
| 分支质量 | 共同继承比例、差异度、独立创新比例 |
| 类型学合理性 | 硬冲突数量、罕见组合警告 |
| 可解释性 | 有完整规则链的变化比例 |

Quality Lab 展示多维结果和异常，不把所有维度压缩成一个无法解释的总分。

## 9. 黄金场景

至少维护以下场景：

1. 最小音变：少量词、单条规则，用于精确断言。
2. 规则组合：删除、同化、repair 顺序。
3. 语法化：内容词到 clitic/affix/particle。
4. 接触与借词：跨 inventory 适配和 DAG 来源。
5. Epoch：注词、复合、替换与类型学漂移。
6. Branch：共同祖先、独立随机流和差异度。
7. 长周期：检测词汇灭绝、同音爆炸和形态失控。
8. 回放：在线状态与锁定 Genesis/Imported boundary + committed typed ChangeSet 重建的全语义 hash 相等；snapshot/keyframe 删除后仍成立。

黄金场景记录规范化输入、引擎版本、规则包版本和预期语义哈希。

黄金哈希只保证同版本确定性，不能单独证明语言学质量。每个领域还必须运行多 seed 性质测试和统计诊断，检查硬约束、分布漂移、异常 seed、谱系对应与语料覆盖；模型版本有意改变输出时，必须提供语义 diff 和变更理由，而不是盲目更新快照。

## 10. 实施顺序

1. R0B 冻结 typed environment/effect、证据分类、Capability Matrix、Canon impact 与 evaluator 反例；
2. G1 + G0B 后，在 WS-1 用一条 feature-based structural change 验证 ProposedChangeSet、reducer、rollback、replay 与 explain；
3. R3 交付 `Structural/Authoring RulePack v1`：validate、conflict、dry-run、canon impact、显式批准、commit；
4. 冻结现有 Python 规则为 legacy research vectors，选择代表性规则迁移为测试向量，不机械复刻旧缺陷；
5. G3B 接受 SpeechCommunity/Variation/ChangeProcess、TheoryProfile、Observation 与 RNG 绑定；
6. R4 交付 `Process RulePack v1`，覆盖成功、失败、停滞、逆转、残留和常规化；
7. 每代规则分别建立 adversarial evaluator、Quality Lab 与 GateEvidence；达到准入标准后再扩展数量；
8. SDK/WASM 只在稳定 RuleSpec 和插件边界 ADR 之后进入可选列车。

## 11. 完成标准

- 默认规则全部来自版本化规则包；
- 生产 Rule Compiler 和规则执行器由 Rust 权威核心提供；
- 规则不直接绕过 StateTransaction 修改状态；
- 用户规则可以在不运行完整演化的情况下验证和 dry-run；
- 每个变化可以追溯到具体规则版本；
- 黄金场景覆盖所有默认规则的主要组合；
- Quality Lab 能定位异常时代、规则和实体。
