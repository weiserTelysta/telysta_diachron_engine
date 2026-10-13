---
document_type: contract
decision_status: accepted
implementation_status: implemented
normative_scope: current
last_verified: 2026-10-12
implementation_schema: telysta-data-manifest.v1
implementation_path: crates/telysta-core/src/data.rs
implementation_constant: DATA_MANIFEST_SCHEMA
---

# Data Governance v1

- 状态：`Accepted`
- 完成日期：2026-07-13
- 对应工作：`DAT-001`
- 实现：`crates/telysta-core/src/data.rs`、`data/manifests/`

外部语言学数据只能作为带来源、版本和限制的证据输入；不得把数据库中的语言、特征或词表直接复制成“自然语言模板”。

## Manifest 合同

每个 `telysta-data-manifest.v1` 记录：

- 稳定 `data-set` ID、标题和版本；
- 许可证、citation、固定 HTTPS URI 与数据格式；
- 内容 SHA-256（本地已下载 payload 必填）；
- 抽样单位、覆盖说明和记录数；
- 至少一条明确 limitation。

`DataRegistry` 拒绝重复 dataset ID 和指向未知 dataset 的 `DataReference`。
`DataReference` 使用 dataset、table 和 record ID 形成可审计的外部记录定位；
当前元数据 registry **不检查 table/record 是否真实存在**。这一验证属于后续
payload adapter/execution slice，不能把 `validate_reference` 成功当作记录已验证。
`LanguageState` 的 evidence 可以保存这些引用。

`DataManifest::verify_payload_checksum(bytes)` 要求非空的 pinned content hash，
并核对原始字节 SHA-256；换行、空白和 JSON 等价重排也会改变该锁。无 hash 的
catalog manifest 仍可作为元数据加载，但不能通过此载荷校验。该纯查询不写
状态、不改变 v1 schema/identity/hash/replay，也不增加依赖。已用 SHA-256 已知
答案及缺锁/变更/空载荷负例验证。

checksum 成功只说明字节匹配，不说明来源可信、许可可分发、schema/引用完整、
抽样有效或语言学结论正确；不签发可绕过后续领域校验的 capability。

## 初始清单

| Manifest | 用途 | 关键限制 |
|---|---|---|
| `phoible-2.0.json` | 音位库存与特征的经验先验 | inventory 是来源特定 doculect；不得按 ISO/Glottocode 粗暴合并。 |
| `concepticon-3.4.0.json` | 概念/义项对齐与语义关系 | gloss 是便利标签，不等同完整语义定义。 |
| `grambank-1.0.3.json` | 语法特征的经验先验 | 覆盖不完整，特征值不构成确定性因果规则。 |

三个文件均是版本化 manifest，不包含下载的数据 payload，`contentSha256` 因而为空。发布构建或可复现实验一旦使用本地 payload，必须把 manifest 复制为项目级锁定版本，并写入 payload hash、精确引用和抽样/过滤 manifest。

## 使用规则

1. `HardConstraint`、`EmpiricalPrior` 和 `ResearchHypothesis` 必须有 citation；
2. 类型学断言至少需要一个 evidence record；
3. 从 manifest 抽取的数据记录通过 `DataReference` 连接到 evidence；
4. 缺失、偏差、来源冲突和不确定性保留为数据本身的 metadata；
5. 创作偏好可以没有外部数据引用，但不得宣称为经验结论。

本合同验收时曾把少量固定 payload 直接指向“祖语—分支—接触”纵切；该执行顺序现已拆分。当前 G0B 只为 WS-1 选择人工审查、可复现的小型 execution slice，并在项目 manifest 中锁定 hash、许可证、抽样与转换；传播和家族/接触数据分别后置到 G3B/WS-2 与 R5。全量导入仍不是当前 Next。

## R0B-05 研究执行切片

[Concepticon 研究切片](../experiments/concepticon-slice/README.md)已锁定 v3.4.0
原始 ZIP、metadata、许可、bibliography、三个 CSV 表、转换脚本与输出 hash。
离线重现 12 个源词表条目、对应 concept sets 及源词表记录，并在研究切片内
检查 dataset/table/record 成员与映射闭包；原始列值保留，不做 Unicode 归一化。

该版本化研究产物不是项目级 DataManifest 或 Meaning IR；Python 不写正式状态，
Rust registry 仍不验证真实记录成员。完整 CLDF、生产 adapter 与 G0B 接受仍待完成。
抽样单位、来源差异、署名许可及限制只在切片 README/lock 维护，不复制进本合同。
