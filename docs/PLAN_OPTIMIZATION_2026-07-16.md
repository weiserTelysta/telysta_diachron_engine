---
document_type: legacy
decision_status: not-applicable
implementation_status: historical
normative_scope: historical
last_verified: 2026-10-16
source_revision: 9ff7e5e8cb820afde281a2c47a74d35e95c1e995
---

# Telysta 计划优化记录

- 历史日期：2026-07-16；依据为 [路线严格评审](./RESEARCH_ROUTE_REVIEW_2026-07-14.md)
  与 2026-07-15 工程/语言学/产品联合复审。
- 本文只保留修订理由、后续纠正和合并去向，不接受任何持久化 schema、writer、
  replay 或插件决定。当前 WBS、依赖、Ready 条件与执行队列只在
  [产品开发执行计划](./PRODUCT_DEVELOPMENT_PLAN.md)维护；Gate 只从版本化证据读取。
- 合并前全文保存在源提交 `9ff7e5e8cb820afde281a2c47a74d35e95c1e995` 的同一路径。
  本次未移动或删除历史合同、schema、fixture，也不新增第四份计划。

## 1. 结论

2026-07-16 修订的关键理由是拆开三个问题：平台能否承载任务、WS-1 能否表示
并验证语言、后续传播模型是否有经验支持。不能让 SpeechCommunity/Variation
阻塞 R1/R2，也不能把结构变换当成真实社会传播。Rust 单一权威与领域实现 Hold
保留；文档、fixture、数据锁及非权威研究不因 Hold 一并停止。
当前并行边界集中在[执行计划 §3](./PRODUCT_DEVELOPMENT_PLAN.md#3-关键路径与并行边界)。

## 2. 产品切入口

当时选定面向严肃叙事作者的 Canon-safe Story Language Kit，先以 R2 证明可执行
微型语言，再以 R3 证明持续创作；不以远期家族或文学愿景替代早期作者价值。
产品定义、1.0 范围和用户后续要求合并至
[执行计划 §1](./PRODUCT_DEVELOPMENT_PLAN.md#1-产品北极星)。

## 3. 修订后的决策门

阶段图与依赖只维护于[执行计划 §3](./PRODUCT_DEVELOPMENT_PLAN.md#3-关键路径与并行边界)；
完整 Gate 定义只维护于[能力地图 §10](./LANGUAGE_SIMULATOR_PLAN.md#10-跨阶段质量门)。
本文不再复制可漂移的阶段图、requirement 集合或通过条件。

### G0A：Platform Contract Ready

拆门理由是先接受进入 R1 所需的平台身份、权威存储、RNG 与应用边界，
而不是先冻结整个语言模型。对应[执行计划 §6](./PRODUCT_DEVELOPMENT_PLAN.md#6-r0a--r0b计划修复与领域证据)。

### G0B：WS-1 Domain Ready

领域接受、双 profile、Meaning/Grammar、TaskPack 与 evaluator 独立收口；
G0B 不能代替 G1，G1 也不能代替 G0B。对应[能力地图 G0B](./LANGUAGE_SIMULATOR_PLAN.md#g0bws-1-domain-ready)。

### G3B：WS-2 Model Ready

真实传播另需 model/observation/source typing、参数恢复与可辨识性，不能用架构
Spike 证明机制真实。对应[执行计划 §10](./PRODUCT_DEVELOPMENT_PLAN.md#10-r3b--r4ws-2-模型就绪与机制性变化-v1)。

## 4. 必须显式解决的 ADR 决策

原记录列出的身份/Run/Event、typed ChangeSet locus、Meaning/Grammar/Task authority、
TheoryProfile/ModelEvidence、聚合/replay 和离线 payload/ReplayCapability 问题，
由[ADR Index](./governance/ADR_INDEX.md)与[目标架构](./architecture/TARGET.md)分别维护
决定状态和边界；工作包文字不构成这些决定的答案。ADR-005 的架构可行性与模型
经验有效性仍须分开，不能由 Spike 自动接受后者。

## 5. 语言与科学验证修订

### 5.1 Meaning 分层

Scene/Context/Intent/Proposition/Obligations 与并行 Commitments 的分层、各层
等价/歧义/gap，以及 comparative concept 不等于语言内部范畴的要求，集中于
[能力地图 §5.9](./LANGUAGE_SIMULATOR_PLAN.md#59-meaning--grammar-ir)和 ADR-014。

### 5.2 分阶段语义与话语能力

G2/G3/G6 的表达范围与 typed gap 只在[执行计划 §8–12](./PRODUCT_DEVELOPMENT_PLAN.md#8-r2--ws-1可执行语言纵切)
维护；自然语言任务文案不能冒充已实现的意义表示。

### 5.3 Evaluator 与任务隔离

四类 TaskPack 与 sealed 可见性/失效边界见
[执行计划 §6](./PRODUCT_DEVELOPMENT_PLAN.md#6-r0a--r0b计划修复与领域证据)；negative
precision、禁读与歧义的验证见[§15](./PRODUCT_DEVELOPMENT_PLAN.md#15-验证矩阵)。

### 5.4 模型证据

恢复、可辨识性/equifinality、观测模型、校准/验证隔离、不确定性和替代模型的
要求集中于[执行计划 §10、§17](./PRODUCT_DEVELOPMENT_PLAN.md#17-数据模型与科学证据计划)；
S 曲线只作待解释模式，不是传播原因。

## 6. 产品与 UX 证据修订

能力证书与可用性证据分离、真实作者任务、Meaning Workbench、持续形成性研究
与预注册 benchmark 的要求已合并至[执行计划 §14、§16](./PRODUCT_DEVELOPMENT_PLAN.md#16-ux-与产品验证计划)。
团队固定练习或自动自测不能替代真实 canon 工作流与产品价值验证。

## 7. 工程顺序修订

本记录最初把 seal/create 放在 ChangeSet/history 之前；这一倒置已被当前 canonical
WBS 纠正。R2 内部门只在[执行计划 §8](./PRODUCT_DEVELOPMENT_PLAN.md#8-r2--ws-1可执行语言纵切)
维护；R1 的 fake artifact 不能冒充 WS-1 权威历史。

其余 R1 ledger/Job/query/headless runner、R3 语料来源、R4 前存储决策、R5 盲重建
观测与 scorer 隔离、R6 单语言/家族文学拆分和可选发布列车，分别由
[执行计划 §7–13、§18](./PRODUCT_DEVELOPMENT_PLAN.md#7-r1平台与仓库收口)承接，
不在历史记录重复维护工程顺序。

发音范围也已按用户后续要求修订：R3 必须提供受限本地试听，R2 随语言导出最小
说明；不沿用旧文中“语音只在 R7”的歧义。完整表现性语音仍在 R7，神经语音和
LLM 保持可选；范围见[执行计划 §1.3](./PRODUCT_DEVELOPMENT_PLAN.md#13-2026-10-12-用户目标落实与路线复审)。

## 8. Gate 证据与交付可行性

版本化 evidence、独立复核和过期规则只由[执行计划 §6、§21](./PRODUCT_DEVELOPMENT_PLAN.md#21-工作包执行模板)
及其链接的 policy/model 维护。滚动近程估算与远期范围估算的区分也已合并至 §21，
不从研究不确定性推导虚假发布日期。用户要求本地执行，旧远端条款不再是运行授权。

## 9. 当前允许与停止项

本文不保存“当前”状态。[执行计划 §22](./PRODUCT_DEVELOPMENT_PLAN.md#22-当前执行队列)
和生成 [STATUS](./STATUS.md) 是现行入口；历史允许项不授权正式 writer、领域持久化、
大批规则或正式视觉精修，legacy 删除仍须遵守迁移矩阵。

## 10. 下一次实现入口

历史建议的核心是平台与领域证据并行、G1 + G0B 后再进入 R2，不等待 R4/R5 来
验证 R1/R2，也不把作者结构变换称为真实传播。实际 Next 只从 §22、Gate 与真实
owner/capacity 决定，本文没有独立队列。
