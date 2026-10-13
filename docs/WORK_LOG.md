---
document_type: runbook
decision_status: not-applicable
implementation_status: in-progress
normative_scope: current
last_verified: 2026-10-14
---

# 执行记录与恢复入口

本文只记录实际执行、验证和下一断点；工作包与启动门仍由
[执行计划](./PRODUCT_DEVELOPMENT_PLAN.md)决定，Gate 状态只读
[证据](./G0A_GATE_EVIDENCE_2026-07-17.json)。不得把本记录当成评审批准。

## 用户目标

本地客户端生成可使用的架空语言，解释音变历史、词源、语法与类型，支持句子
创作、基础读音和同版本语言文档。视觉采用 Rosé Pine；保证可读性、健壮性与
可访问性。每个阶段按评审、计划、执行、测试、复审循环推进。

## 当前循环：2026-10-12

- 起点：`9ff7e5e`；用户新增未跟踪的 `references/`，原样保留。
- 已核对：产品计划、路线图、能力地图、当前/目标/迁移架构、ADR 索引、存储
  与会话合同、审计台账、Python 和桌面入口。
- 评审结论：保留 Rust/Tauri 唯一权威与最小语言纵切；收敛重复进度描述；
  把基础读音和语言手册落实为有依赖的交付验收，而非无限后置的可选愿景。
- 环境已建立：Python 3.13.5 + Poetry 2.4.1 锁定虚拟环境、Rust 1.88.0、
  官方 Node 24.21.0。无 sudo，原生开发包解压在用户目录，链接系统运行库。
- `R0A-09 / COR-08/09` 进入本地复审：保持 v1 schema、身份和 replay 语义，
  已修复 lease 内 create-if-absent、core history extension、session/disk 双重
  revision 检查、publication snapshot、迁移 archive/primary/link 边界与 index
  authority。公开 save 保留签名但收紧为初始创建/相同重试，合同已明示行为变化。
  本地独立 AI 复审完成；正式 Gate 关闭与跨平台证据仍待完成。
- 桌面基线补齐 Linux RGBA 图标及 global command bridge；会话命令串行，
  不可编译的 Blueprint 明确提示。Node 处理函数测试已通过，不冒充 WebKit E2E。
- `R0A-10` 本地材料采集进入复审：`scripts/legacy_evidence.py` 逐项真实执行
  八个回放失败，保存原始字节、源码、JUnit、环境与 hash；五个黄金场景与原
  semantic hashes/hard errors 一致，未修复旧语言模型。旧 CLI/Streamlit 已
  标注研究边界。尚无 clean reviewed subject，不称正式冻结或 Gate closure。
- `R0B-06P` 初版位于 `experiments/meaning-workbench/`：Rosé Pine、canon
  输入、八项意图、两种方案概念、缺口提示和研究草稿导出；无权威状态或网络。
  已做浏览器自测，真实作者研究尚未采集，不计为 ProductUsabilityEvidence。
- 完整 evidence 刷新发现 `R0A-08` 的 Linux 验证遗漏：Python launcher 被
  `resolve()` 解到系统解释器，且定向 pytest 路径写死 Windows 分隔符。
  三个故障测试复现后修复；解释器还必须具有仓库 `.venv` 的 prefix，不能
  仅靠相同软链接目标冒充。前次失败已由生成器记录，未保留历史 pass。
- `R0B-01A-D/04B-D`：ADR-014 §4.4A 已提出 WordForm/occurrence + explicit
  orthographic base 决定，补齐 owner、hash、revision、normalization、迁移与
  保守拼写边界；22 个 mutable review vectors 在
  `tests/fixtures/orthography_review_vectors_v1.json`。仍 Proposed，reviewers
  为空；未写生产 schema、normalizer、realizer 或 analyzer。
- `R0B-05` 只新增 DataManifest 原始 payload checksum 验证，缺 hash 或字节不符
  均拒绝；不等于记录成员验证。Concepticon format 纠正为 CLDF Wordlist；
  PHOIBLE 的网站/CLDF 版本许可冲突已标注，尚未解决，不能仅补 hash 就放行。
- 用户要求已落实为三份专业 AGENT.md；新会话分别审查形式、实证与历时使用。
  已修订角色绑定/异拼写串读向量、真实材料意图关联、R2 手册与 R3 必需试听的
  验收链。生产手册、音频和真实作者研究仍未实现，不冒充规划已执行。
- G0A 仍 blocked；独立 ADR 接受、跨平台 attestation 和真实责任分配未完成。

### 本次续作：真实数据 → 意义反例

- `R0B-05` 研究切片完成并进入 Review：原包 DOI 14923561 的 MD5 与发布记录
  相符，SHA-256 `a385f04140540582222d6a57f596d38b28e4f5a39c02a828d9223f9cb540fc6e`。
  [切片](../experiments/concepticon-slice/README.md)保存 12 个定向源条目、12 个
  concept sets 和一个源词表记录；原字段逐列保持。离线重现、成员/映射验证
  与 15 项拒绝/完整性测试通过。独立复审发现并修复 `0/<NA>` 占位映射；真实
  数据与转换锁再次复查，无未解决 finding。不升级 Rust registry 的能力声明。
- `R0B-04` 轮换执行：独立审阅复现 SEM-N01 把 candidate 设为 required 后仍
  通过结构检查。补充 reading 定义、明确等价策略、identical/alias 阳性对照及
  矛盾突变回归；先见缺定义失败，再修正通过。新增四个 scope/commitment/report
  [review vectors](../tests/fixtures/meaning_review_vectors_v1.json)及有限模型见证，
  4/16 种关系赋值的 alpha 对照与捕获/角色/常量/域负例。仍属 mutable planning，
  不称 production IR、自然语言等价判定或 Rust round-trip 通过。
  复审继续发现预设条目丢失、问句 alternatives 非互补及 truth 标签未校验三个
  一致性缺口；补齐基线承诺、每个 polar issue 和标签检查及突变回归，独立重跑
  原反例全部拒绝，复查无遗留 finding。相关测试合计 32 passed。

## 独立 AI 审阅与复查

所有会话以 `fork_turns=none` 启动，自行读仓库，只读审查；修复由主维护会话完成。
不同方法不表示不同人类资历；未将本记录或会话名称写成 ADR/Gate 批准。

| 会话 | 范围 | 发现及复查 |
|---|---|---|
| `/root/architecture_review` | v1 storage/runtime/data/API | 复现写后 load 抢锁失败、pending migration 覆盖其他合法 legacy primary；后续确认 session hash 与 unconditional save 缺口。均修复并复查；创建/提交各 100 次真实锁竞争、迁移与剩余 authority probes 通过 |
| `/root/migration_review` | archive/journal、证据脚本、客户端边界 | 复现 archive 与 migrations 目录链接越界；修复后 unpublished/published/首次归档/恢复探针拒绝且保留字节。Windows reparse 仅源码复查。failure fingerprint 不认证缺陷机制的限制已写入合同 |
| `/root/linguistics_review` | 初轮领域/正字法/原型 | 人数冲突、试听前置漂移、保守拼写回析、跨贡献 NFC 对齐已修订并复查；22 个向量仍为 planning |
| `/root/linguistic_formal_round2` | [形式与反例指南](../.agents/reviewers/linguistic-formal/AGENT.md) | VAL-N02 角色名不能证明参与者绑定；R04/R20 可串入错误同音分析。增加绑定与 forbidden foil、每个拼写精确分析集，独立正反例复查通过 |
| `/root/linguistic_empirical_round2` | [跨语言实证指南](../.agents/reviewers/linguistic-empirical/AGENT.md) | Concepticon format 错误已纠正；doculect 一刀切已收窄；PHOIBLE 来源冲突准确披露但底层许可仍待解决 |
| `/root/linguistic_diachronic_round2` | [历时与作者指南](../.agents/reviewers/linguistic-diachronic/AGENT.md) | 原型真实 canon 与意图脱节、手册/试听未进入硬验收。现有人工关联、WS1-10/G2 导出与 STORY-10A/G3 试听已复查；受影响 R3 20 节点依赖检查无环 |
| `/root/concepticon_slice_review` | 实证指南；真实 ZIP、研究锁、转换与成员验证 | 核对 Zenodo、许可、全部 1+12+12 行，15 tests 与原包离线重现通过；占位映射反例已修复复查，无遗留 finding |
| `/root/meaning_scope_review` | 形式指南；Meaning oracle 与 scope/commitment | 原矛盾禁读被拒绝；新增向量复查的三个一致性缺口全部修复，原反例拒绝、17 项相关基线通过，无遗留 finding |

第二轮形式复查绑定的向量 SHA-256：

- linguistic regression：`f6710cd9384ef48755184e0fbafed84484d21c3e30e7e014d456027724d48945`；
- orthography review：`ba6303f2d6191d6c391fdaa9e2bdf9be57b0d2a4745080f08f5d07573076483c`。

本次续作的最终独立复查 hash：linguistic regression
`2d2e710f06e7064b35ba718a8f94aaed1aee9722e1d7c7487a8c0b2895a39bcf`；
Meaning review `21b90043217d5b7e2fb701d1ecf12c494260f235f15ae67aaaf789be37e69bf2`。

临时复现脚本在本机 `/tmp/telysta-independent-review-ipgm1xk0/`，不当作持久
发布证据。可长期复跑的回归在 Rust/Node 测试及 planning vectors 中；完整正式
attestation 仍需冻结 subject、记录责任/平台来源，并逐项满足对应接受条件。

## 恢复步骤

1. 阅读本文件与执行计划第 22 节，检查 `git status`、diff 和后台进程。
2. 运行相关完整门；本机 Rust 命令需要下述用户目录工具链与 pkg-config 路径。
3. 核对当前完整门结果与下述检查点。先完成下述平台草案复审和完整门，再进入
   production adapter binding plan，或准备有真实参与者的原型试用；在
   Accepted ADR/独立 Gate 证据具备前不实现 Proposed 持久化语义。
4. 继续可执行的 R0A 修复、R0B 评审材料与非权威作者原型；不虚构独立批准。

会话内持续执行已获用户授权。额度恢复后的自动调度尚未设置：当前 IDE 会话
没有通用计划任务工具；不能把本文件或后台 shell 当成模型自动唤醒机制。

## 本机验证环境

```bash
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
export PKG_CONFIG_PATH="$HOME/.local/share/telysta-tooling/native/usr/lib/x86_64-linux-gnu/pkgconfig"
```

标准开发机应按 DEVELOPMENT_SETUP 安装系统开发包；上面仅是当前无 sudo 环境
的适配，不作为其他发行版已验证的证明。日志在忽略目录 `target/`，最终完整
检查结果与下一断点在本轮结束前更新。GateEvidence 仍是唯一 Gate 状态来源。

## 2026-10-12 验证检查点

- Linux Rust 1.88.0 完整门：工作区 83 tests、fmt/clippy/desktop build 通过。
  其中 core/storage 80 项已由独立 AI 复跑（storage 30）。本机故障曾定位到 native 开发库与
  仓库缺失 PNG 图标，已解决。本地工作区不等于 fresh-checkout attestation。
- Node：桌面处理函数 7 项、作者原型逻辑 7 项通过。
- Python 完整门：646 passed / 8 strict xfailed；本次新增 24 项。完整复验
  已通过，最终 subject 以最新 GateEvidence 为准。归档测试 9 项、evidence generator 56 项通过。
  中间直接检查曾为 621 passed / 8 xfailed / 1 failed，
  唯一失败是修改 subject 后生成证据过期；现已由 evidence generator 刷新并
  完整复验通过，未修改断言或手工伪造 hash。最终记录以最新 GateEvidence 为准。
- Chromium 153 / Playwright 1.63.0：原型离线加载、Unicode/注入文本安全呈现、
  Markdown 下载、编辑失效、可见键盘焦点、390/720px 重排通过；截图已视觉
  复核，移动端字体增大后的复跑也通过。没有 Windows/WebKit E2E 声明。
  新增真实材料意图笔记后的离线填写、导出、失效与移动端重排复跑通过。
- Legacy 原始采集：`target/legacy-evidence/2026-10-12-local-03/`，8 个真实失败、
  5 个黄金场景、268 文件校验通过；这是当时源码的可校验快照，后续源码变更
  不改变这份历史材料。更早失败/试运行目录保留供诊断，不作最终证据。

## 续作断点：2026-10-14

- 上一完整验证是 646 Python passed / 8 strict xfailed、83 Rust、14 Node；之后
  的完整复验只以最新 GateEvidence 的 verificationRuns 和 subject 为准，不能
  把旧 fingerprint 当成本次证据。
- `/root/platform_adr_review` 的新上下文只读评审提出三个 P2 草案缺口：同一
  Operation 输入变体矛盾、rngLock 无法表达必需预算、manifest 替换后失败未闭合。
  本轮选定固定输入 Operation，Run 仅由 role/runKey 派生 stream root；补齐预算、
  完整 frontier 与跨记录校验；补充八个 pre/post publication planning states、
  目录持久化和 `commit_outcome_unknown` 协议。全部 ADR 仍 Proposed，未改生产身份、
  RNG raw stream、writer 或 replay。
  `/root/platform_contract_recheck` 发现无 Run Operation 的重复预算和 uncertain
  replace 判定漂移两项 planning 检查缺口；修复后原反例均拒绝，9 项定向基线
  通过，复查无遗留 finding。真实恢复器、writer、rootSeed wire 与 authority
  canonicalizer/KAT 仍待后续闭合，不能把这些检查计为生产能力。
- 验证器曾只把结构合法的外部声明当作可信条件；定向测试先复现未拒绝，再增加
  明确的 external trust unavailable 边界，57 项 generator tests 通过。账户同意、
  provider 与 terminal payload 受信验证尚未实现，不能签发 passed；没有绕过开关。
  `/root/gate_verifier_review` 会话未完成，不记为独立通过；本修复目前是主会话自审。
- 文档旧口径已修正：当前 GateEvidence 是 v3 blocked candidate，不是旧 v1/v2；
  Linux 本地检查也不等于 Windows/Linux 远端 attestation。
- 本地《普通语言学教程》为 337 页扫描本；已视觉核对封面、版权及 PDF 3–6 页
  目录/出版说明，文本提取为空，尚未精读正文。未把目录当作模型证据或复制进产品。
- 上述平台切片完整门已通过：652 Python passed / 8 strict xfailed，83 Rust，
  14 Node。进入下一轮当前只读桌面输入修复：独立审阅复现 JS 把
  `candidateCount:8.0000000000000001` 转为合法整数 8、将 9007199254740993 改值。
  前端改传原文，Rust 直接解析；同名命令兼容旧 typed 参数，恰一个非 null 输入。
  schema/hash 算法/持久化身份不变。Node 原反例先失败，再修复；新增 Rust 精确
  整数、原文/typed 同报告、小数/歧义输入负例。编辑使报告失效，迟到成功/错误
  不能显示为当前文本的结果。独立复查原数值反例、null/缺失/双传、旧调用兼容，
  并复跑 5 Rust / 9 Node；复审无遗留 finding。仍无真实 WebKit IPC 声明。
- Blueprint 修复完整门已通过：652 Python passed / 8 strict xfailed、85 Rust，
  桌面与原型 Node 合计 16 项。此后进入 rootSeed wire planning slice：目标协议
  使用规范 ASCII 十进制字符串，schema 闭合 u64 边界，Python/Node 独立整数
  oracle 与 Rust parse/canonical cross-check 已通过。当前生产 RunContext/demo、
  冻结 KAT 与 raw RNG 算法未改，源归档不得重写或先经 JS Number；目标 DTO 仍未实现。
  新增 Node wire 检查已接入 Linux CI。`/root/rng_wire_review` 独立分解范围正则为
  38 个连续不重叠整数区间，并用 104,296 个边界/格式案例跨语言比对；无 finding。
- 当前完整门入口继续为 `generate_gate_evidence.py --verify`，其输出与 STATUS
  是本次 subject/环境/结果的唯一机器记录。下一断点是 R0B production adapter
  binding plan 与 authority hash review decisions；受信外部 attestation 尚无实现，
  不把本地自测作为 Gate 批准。
- 本轮将源代码和评审材料准备为隔离本地分支 `codex/review-baseline-2026-10-14`，
  用独立检出执行完整门；不切换当前工作分支，不推送，不纳入用户 `references/`。
  精确 subject、环境与结果只读该候选的生成 GateEvidence/STATUS，不把本地候选
  称为正式 clean baseline acceptance、远端 attestation 或 G0A 通过。
  初始候选 `5b51d9add04b86ed3121b63b5a9800464c40d59b` 收录 74 个实现/评审文件；
  独立 venv 按 poetry.lock 的 48 个分发包及 wheel SHA-256 重新安装，不复制旧 venv。
  首次验证真实失败：verifier lease 把 linked worktree 的 `.git` 文件当作目录。
  新回归先复现失败，再改由 Git 定位当前检出的 metadata 锁；同一检出竞争仍拒绝
  且输出不变，58 项 generator tests 通过。`/root/checkout_lease_review` 在普通及
  linked 检出独立验证跨进程拒绝、带空格路径和正常/异常清理，无 finding。
  修复后 clean run 结果以候选分支最新 subject/生成证据为准；初次失败日志
  保留在候选 target 中。
