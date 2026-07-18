---
document_type: adr
decision_status: proposed
implementation_status: not-started
normative_scope: target
last_verified: 2026-07-18
owner: unassigned
reviewers: []
---

# ADR-010：GenesisArtifact 信任边界与项目创建

- 状态：`Proposed`
- 日期：2026-07-14
- 决策范围：祖语编译、Genesis 质量门、Tauri 创建命令、存储导入与离线重验
- 前置决策：ADR-006、ADR-008、ADR-009、ADR-011、ADR-012、ADR-013、ADR-014
- 设计上下文：ADR-007 umbrella；ADR-011 固定 ProjectManifest、Genesis Operation 与 Job 身份，ADR-012 拥有 `ProjectAuthorityHash` 和单发布点，ADR-013 固定被锁定的 RNG wire/path/distribution 语义，ADR-014 固定 Genesis 必须封印的语言实体与 realization authority；本 ADR 只决定可信创建与消费流程

## 1. 用户与研究问题

如何确保正式项目一定来自经过能力检查和语言学质量门的祖语编译，而不是由客户端或任意 JSON 绕过编译器拼装权威状态？

## 2. 假设分类

| 假设 | 分类 | 处理方式 |
|---|---|---|
| Genesis hard errors 非零时不得创建项目 | Hard constraint | `GenesisVerifier` / application-service gate |
| Rust 私有构造器能证明磁盘数据可信 | Unsupported security assumption | 所有反序列化输入重新验证 |
| 内容 hash 可以发现非预期变化 | Engineering guarantee | canonical hash 与锁验证 |
| 本地 artifact 必须使用数字签名 | Research/security option | 没有密钥模型前不作为 v1 承诺 |

## 3. 决策

`GenesisArtifactEnvelope` 是可序列化但始终不可信的内容 envelope；`VerifiedGenesisArtifact` 是编译或完整重验成功后才能取得的内存 capability。二者不得使用同一可反序列化 Rust 类型，也不能因为字段相同互相转换。

envelope 与 verified capability 至少共同锁定：

- LanguageState v3、`StateSemanticHash`、state schema、`telysta-entity-id.v2` 与 semantic-hash schema；
- Blueprint 文档与 hash；
- RegistryBundle schema/version/hash；
- ADR-014 Meaning/Grammar/Lexical/Realization contract bundle schema/version/hash；
- HashCoverageManifest schema/version/hash；
- Genesis TheoryProfile / ModelLock；
- data payload locks；
- RulePack locks；
- RNG schema/root seed/path contract；
- compiler、grammar compiler、realizer/analyzer 与 validator version/hash；
- Capability Matrix schema/version/hash；
- Development/CandidateSelection/SealedAudit TaskPack locks；
- independent evaluator schema/version/hash、evaluator RNG lock 与 attestation；
- candidate identity 与 candidate semantic hash；
- compiler capability report 与 typed gaps；
- GenesisQualityReport 及其 hard-error、forbidden-reading、under/over-generation、ambiguity 和 coverage 分项；
- provenance ledger；
- artifact schema 与 detached canonical content hash；digest 字段本身不进入被摘要 payload。

若某个锁的完整 payload 不内嵌 artifact，artifact 必须引用 dependency bundle 中可离线解析、content-addressed 的 payload；URI 或显示版本号不能代替内容 hash。

`ProtoLanguageCompiler` 只能返回未验证的 candidate/envelope，独立 evaluator 只能返回版本化
`EvaluatorReport` 与 attestation；二者都不能单独构造 `VerifiedGenesisArtifact`。所有绑定
按下列单向 hash DAG 计算，禁止“相互包含”：

```text
versioned dependency payload hashes
→ candidate payload hash
→ EvaluatorReport hash(candidate + exact TaskPack/evaluator/RNG locks)
→ GenesisQualityReport hash(candidate + evaluator reports)
→ artifact content hash(all preceding locks/reports; excludes its own digest field)
→ verified runtime capability
```

Rust application service 调用同一 crate 内唯一的
`GenesisVerifier::verify_and_seal`，在 `readyForCompilation=true`、所有 required
capability 为 `supported`、hard errors 和 forbidden-reading acceptance 为零，且上述
单向绑定全部验证时，才能通过私有构造器返回运行期 `VerifiedGenesisArtifact`。

私有构造器不是持久化信任机制。任何来自磁盘、导入包、IPC 或测试 fixture 的
`GenesisArtifactEnvelope` 都是不可信数据，必须由 application service 调用同一个
`GenesisVerifier::verify_and_seal`，针对 envelope 锁定的精确 schema、
Meaning/Grammar/Realization contract、Registry、TheoryProfile、数据、规则、RNG、
Capability Matrix、TaskPack、evaluator、HashCoverageManifest 和质量报告完整重验。
不得用当前默认 evaluator、当前 TaskPack 或“兼容最新版”替换被锁定依赖后继续声称是同一
artifact。

## 4. Tauri 与存储边界

- 正式 `create_project` 命令接收 Blueprint/用户选择和目标路径，由 Rust application service 调用 compiler；
- Webview 不能提交 LanguageState、ProjectHistory 或自称 VerifiedGenesisArtifact 的任意 JSON 创建项目；
- 若提供 artifact 导入，只能进入独立 `verify_and_import_genesis` 路径，并执行与本地编译等价的验证；
- application service 从 `VerifiedGenesisArtifact` 构造 ADR-011 定义的 ProjectManifest、Genesis OperationRecord、RunLedger 初始记录、Genesis root、不可变空 UsageCorpus root 和初始 `HistoryHeadHash`；客户端不能提供这些权威对象；
- storage 只接受 `VerifiedGenesisArtifact` capability 与 application service 已验证的项目组合，并在写入前再次核对 artifact、`StateSemanticHash`、`HistoryHeadHash`、operation、ledger 和 ADR-012 `ProjectAuthorityHash`；
- 创建消费 ADR-012 预先计算且排除自身字段的 `ProjectAuthorityHash`，使用不可变对象 + 单 manifest 原子发布，一次提交 Genesis root、OperationRecord、manifest head 与该 hash；失败不留下半项目或只有 ledger 没有 history 的分裂状态。

内容 hash 和历史 hash chain 用于完整性与可复现性。数字签名只有在定义签发者、密钥存储、撤销和离线验证模型后才能加入，不能用无密钥模型的“签名”制造虚假安全感。

## 5. 验收标准

- 具名 domain owner 与独立 architecture、linguistics、storage/migration reviewer 已登记；作者和 owner 不占 independent reviewer 槽位；
- hard errors 非零或 capability 不完整时无法构造 artifact；
- compiler、evaluator 或客户端中的任何一方都不能单独构造 verified capability；
- 普通反序列化只能得到 `GenesisArtifactEnvelope`，不能获得已验证 capability；
- 篡改 Blueprint、state、entity/hash schema、Meaning/Grammar/Realization contract、registry、TheoryProfile、data、rule、RNG、Capability Matrix、TaskPack、evaluator、HashCoverageManifest 或质量报告后导入失败；
- 缺失锁定 payload、使用不同 evaluator/TaskPack 重验或 dependency bundle 无法离线解析时导入失败；
- Tauri 无法绕过 Rust compiler/application service；
- 项目创建的 Genesis history、ProjectManifest 和 RunLedger 全成或全败；
- 创建后重开得到相同 artifact content hash、`StateSemanticHash`、`HistoryHeadHash` 和 `ProjectAuthorityHash`；
- artifact/evaluator/quality hash 按固定 DAG 计算，任何 digest 都不摘要自身或依赖下游 digest；
- fixture、迁移和离线导入均有显式验证路径；
- 不引入第二个生产状态写入者。

## 6. 后果

创建流程会比直接保存 ProjectHistory 更严格，也需要将编译、验证和存储组合成 application-service 用例。该复杂度是阻止空状态、伪造状态和不可复现项目进入正式历史所必需的。
