# TelystaLexisEngine — 开发文档

> 本文档为内部开发参考文档，记录项目目的、技术路线与阶段性目标。项目尚未完成，不对外发布。

---

## 一、项目概述与愿景

TelystaLexisEngine 是一个高度自动化的架空语言（Conlang）生成与历时演化系统，目标是为严肃的奇幻世界观提供具备真实历史深度的语言学基座。

系统摒弃传统"查表式"或"纯随机拼接"的造语方案，采用**神经符号混合架构（Neuro-Symbolic Architecture）**：

- **符号层（规则引擎）**：以 Python 严密的算法和数据结构为核心，负责音系生成、历时音变、形态演化与句法计算。所有语言学规则均可配置、可插拔、可单元测试。
- **神经层（LLM 渲染）**：在符号层的结构化计算完成后，由大语言模型（LLM）负责生成时代纪事、解释语义漂移、润色文化隐喻，并为演化"异常突变"提供合理化叙事。LLM **绝不干预**任何规则计算过程，但可通过受控回调机制向符号层提交提案。

最终产物不是静态字典，而是一个具备完整历史脉络、独立语法形态、自然语音输出与句法级翻译能力的动态语言演化系统。

---

## 〇、架构决策记录（ADR）

本节记录项目中尚未最终拍板的重大架构抉择。每条 ADR 包含选项分析与当前倾向，需在对应 Phase 启动前最终确认。

### ADR-001：计算核心的技术栈选择

**决策触发点**：Phase 1 的范例层批量计算、特征矩阵运算、DAG 遍历在纯 Python OOP 下存在严重性能瓶颈。

**三个选项**：

| 方案 | 优势 | 劣势 | 适用阶段 |
|---|---|---|---|
| **A. 纯 Python OOP** | 开发速度快，代码直观 | 范例层 O(N×K) 循环在词库超过 5000 词时卡顿；`dict`-based `Phoneme` 对象内存巨大 | Phase 0（当前）|
| **B. Data-Oriented Python（NumPy）** | 保持纯 Python 栈；批量矩阵运算可达 C 速度；特征位压缩为 `uint16` 后内存占用降低 10–50x | 复杂的 DAG 递归和 CSG 挂载在纯 NumPy 下依然痛苦 | Phase 1–2 热路径 |
| **C. Rust 核心 + Python 外壳（PyO3）** | 音素特征用 `bitflags`（8-16 bit 整型），十万次遍历仅几百 KB 内存；`fst` crate 原生支持 FST；DAG 图计算极高效；可编译为 Wasm | 需引入 Rust 工具链；团队学习曲线（但 Cursor/AI 辅助下 Borrow Checker 门槛大幅降低） | Phase 2+ 核心热路径 |

**当前倾向**：

- **Phase 0–1**：维持 Python OOP（当前实现），重点是打通逻辑闭环，不在性能上浪费时间
- **Phase 1 末尾**：将范例层批量计算迁移至 NumPy 矩阵（方案 B），音素特征从 `dict[str, bool]` 改为 `uint16` 位掩码
- **Phase 2+ 决策点**：若 NumPy 方案在 DAG 和 CSG 处理上出现明显瓶颈，启动 Rust 核心（方案 C），通过 PyO3 向 Python 层暴露接口，Python 仅负责 LLM 调用、配置读取和 Web 接口

**方案 C 的分工边界（若采用）**：

```
Rust 核心（计算热路径）          Python 外壳（胶水层）
─────────────────────────        ──────────────────────
PhonemeInventory（bitflags）     读取 YAML 配置
SoundChangeRule IR               调用 LLM API
Rule Compiler + Backend          提供 Web/CLI 接口
Hot State 词库（Vec<LexEntry>）  可视化与前端
DAG 词源图遍历                   用户交互逻辑
范例池批量计算
CSG → 形态规划器
```

### ADR-002：Rule Compiler 执行后端选型

**决策触发点**：Phase 1 规则集超过 ~30 条，或规则级联出现性能/正确性问题。

| 后端 | 实现路径 | 注意事项 |
|---|---|---|
| **Regex Backend**（当前） | Python `re` 模块，由 IR 动态生成正则字符串 | 避免 Lookbehind 污染 IR 设计；规则集 >30 条时需压测 |
| **FST Backend** | Python: `pynini` (OpenFST 绑定)；Rust: `fst` crate | IR 设计必须提前按 FST 的图语义构造，不能以"替换后端"为由偷懒 |
| **Python 原生 Backend** | 直接用 Python 列表迭代执行 IR | 最慢但最透明，适合调试和单元测试验证 |

**约束**：无论选择哪个后端，`SoundChangeRule` IR 对象不得改变（见 3.2 节）。

### ADR-003：语义基元树的来源

**决策触发点**：Phase 3 语义层启动前。

| 选项 | 说明 | 风险 |
|---|---|---|
| **自建最小语义图** | 手工定义 ~200 个语义基元节点和边 | 工作量大；覆盖面有限 |
| **引入 WordNet / BabelNet** | 成熟的语义关系图谱，图距离可直接量化 | 依赖外部资源；需处理授权和数据格式 |
| **LLM 即时推理** | 每次语义校验时询问 LLM | 不确定性高，违反"符号层不依赖 LLM"的铁律 |

**当前倾向**：Phase 3 初期使用自建最小语义图（覆盖斯瓦迪士列表概念 + 扩展至约 500 节点），为 ADR-002 中的图距校验提供支撑。后期考虑以 WordNet 作为可选扩展。

---

## 二、语言学设计规范

本节是引擎的理论基础。所有算法实现必须对标此处的语言学标准。

### 2.1 音系层（Phonology）

#### 2.1.1 音素清单（Phoneme Inventory）

引擎须维护一套**有限的音素清单**，而非无限随机采样。**音素清单的底层存储绝不能是 `List[str]`**——`["p", "t", "k"]` 只是换了外观的字母表，无法支持任何真正的音系运算。音素清单必须是 `List[Phoneme]`，每个音素携带完整的**二值特征矩阵（Binary Feature Matrix）**（详见 2.1.6 节与 3.1 节）。

清单的规模与风格由用户在 UI 参数中设定。典型预设：

| 风格预设 | 元音数量 | 辅音特征 | 听感 |
|---|---|---|---|
| 精灵语型 | 多（5–8 个） | 偏流音、无复辅音 | 空灵、柔和 |
| 兽人语型 | 少（3–4 个） | 偏爆破音、塞擦音 | 粗犷、沉重 |
| 外星语型 | 用户自定义 | 允许非人类发音限制 | 不可预测 |

#### 2.1.2 音位配列规则（Phonotactic Constraints）

音节结构**不是简单模板列表**，而是"结构模板 + 合法组合集"的双层系统。语言是**连续光谱（continuum）**，描述的不是"哪些音节能用"，而是"哪些常用 + 多常见"：

```
# 错误示范（错误假设所有 C 都可互换）
templates = ["CV", "CVC", "CCV"]

# 正确做法：分层约束
onset_clusters = ["p", "t", "k", "pr", "tr", "str", ...]  # 合法词首辅音丛
coda_set       = ["n", "ŋ", "t", "st", ...]               # 合法词尾辅音
```

复杂度档位**不是全局开关，而是位置敏感的**。同一语言可以同时存在"词首允许 CCV、词尾仅允许 VC"的情况：

| 档位 | 允许结构 | 说明 |
|---|---|---|
| 极简 | V, CV | 夏威夷语型，无辅音丛 |
| 标准 | CV, CVC, 简单复辅音 | 大多数自然语言 |
| 复杂 | CCVCC 等 | 允许词首词尾辅音丛 |
| 炼狱 | 无限制 | 完全忽略 CV 规则 |

音素选取须遵循**条件概率**而非均匀随机：/s/ 后更可能接 /t/ 而非 /b/，/k/ 后更可能接 /r/。

#### 2.1.3 音变规则（Phonological Processes）

| 规则类型 | 说明 | 示例 |
|---|---|---|
| 同化（Assimilation） | 相邻音趋同 | n → m / \_ p |
| 弱化（Lenition） | 发音向省力方向滑落 | p → b → v → ∅ |
| 强化（Fortition） | **重音音节**发音强化 | ∅ → p（词首重音） |
| 脱落（Elision） | 音素在特定位置消失 | 词尾元音脱落 |
| 腭化（Palatalization） | 辅音受后续前元音影响 | t + y → tʃ |
| 插音（Epenthesis） | 插入音素以修复非法结构 | /ktt/ → /kɪtt/ |

> **⚠️ 技术选型警示——正则引擎的上限**
>
> 当前使用 Python `re` 模块执行上下文敏感音变规则（如 `A → B / C_D`）。随着规则数量增长，级联和交叉重叠规则极易陷入**灾难性回溯**或顺序覆盖问题。
>
> **退路预留**：当规则集超过 ~30 条或出现性能瓶颈时，须将音变解析器迁移至**有限状态转换器（Finite State Transducers, FST）**。FST 是计算语言学处理形态和音系演变的标准算法模型，可保证线性时间复杂度且天然支持双向转换（G2P / P2G）。迁移路径：`re` → `pynini`（OpenFST Python 绑定）。

#### 2.1.4 音系合法性检查器（Phonological Well-Formedness Validator）

音变规则执行后**可能产生非法音系结构**（如 /ktt/），必须在每次音变后运行合法性校验：

```
校验流程：
  执行音变 → 校验器检测 → 合法 → 继续
                         → 非法 → 修复（Epenthesis）→ 二次校验
                                → 无法修复 → 回滚本条规则 + 记录日志
```

合法性校验规则由同一份音位配列配置文件驱动，确保生成时与演化后的约束标准完全一致。

#### 2.1.5 重音系统（Stress）

重音位置由语法基因参数指定（词首 / 倒数第二音节 / 规则可配置）。重音不仅影响听感，还直接参与磨损计算（见 2.5.2 节双变量磨损模型）。

#### 2.1.6 自然音类与特征束（Natural Classes & Feature Bundles）

这是音系引擎的理论核心，也是区分"字符串替换系统"与"真正音系计算引擎"的分水岭。

**为什么必须用特征矩阵？**

用字符串写浊化规则，必须逐一列举所有清辅音：

```
p→b / V_V,  t→d / V_V,  k→g / V_V,  s→z / V_V,  f→v / V_V ...
```

100 个音素就需要 100 条规则。用特征矩阵，整个自然音类只需一条规则：

```yaml
target: {voiced: false, consonantal: true}   # 所有清辅音
change: {voiced: true}                       # 对应浊化
environment: {before: {syllabic: true}, after: {syllabic: true}}
```

引擎自动发现"所有符合条件的音素"，执行整个**自然音类（Natural Class）**的统一变化。

**标准二值特征集（SPE 体系）**：

| 特征名 | 含义 | 典型 True | 典型 False |
|---|---|---|---|
| `syllabic` | 可作音节核 | 元音 | 辅音 |
| `consonantal` | 发音有强阻塞 | 大多数辅音 | 元音、半元音 |
| `voiced` | 声带振动 | b, d, g, z, v | p, t, k, s, f |
| `continuant` | 气流不完全中断 | 擦音、近音 | 塞音、鼻音 |
| `nasal` | 软腭下降、气流经鼻 | m, n, ŋ | 其余音 |
| `sonorant` | 共鸣音 | 元音、鼻音、流音 | 塞音、擦音 |
| `labial` | 双唇或唇齿 | p, b, m, f, v | — |
| `coronal` | 舌尖/舌叶 | t, d, n, s, z, ʃ | — |
| `dorsal` | 舌背 | k, g, ŋ, x | — |
| `high` | 舌位高 | i, u, k, g | a, e, o |
| `low` | 舌位低 | a | i, u |
| `back` | 舌位后 | u, o, k | i, e |
| `round` | 嘴唇圆化 | u, o, ø, y | i, e, a |

不同语言可使用该标准特征集的子集，并允许在配置中添加非标准特征（如为外星语定义 `{ "click": true }`）。

---

### 2.2 形态层（Morphology）

形态学决定词汇如何变化和组合。引擎须支持语言类型的**动态漂移**（类型学轮回 Typological Cycle）：

| 语言类型 | 特征 | 典型语言 |
|---|---|---|
| 孤立语（Isolating） | 零词缀，靠语序和虚词 | 现代汉语、越南语 |
| 黏着语（Agglutinative） | 词根 + 规律词缀，含元音和谐 | 日语、土耳其语 |
| 屈折语（Fusional） | 词缀与词根融合，边界模糊 | 拉丁语、俄语 |

三种类型是**演化阶段**，不是静态标签。轮回方向：孤立语 → 黏着语 → 屈折语 → 磨损崩塌 → 回到孤立语。

#### 屈折语的特征融卷算法（Feature Fusion）

黏着语的形态逻辑是"乐高式叠加"（词根 + 时态后缀 + 人称后缀），代码容易实现。但**屈折语**中一个词缀同时编码多个特征（如拉丁语 `-o` 单独表达第一人称/单数/现在时/主动语态的融合），这在算法上是本质性的挑战，不可等同于黏着语处理。

从黏着语磨损到屈折语在算法层意味着：

**阶段一：黏着语分析形式**
```
[词根: VID] + [人称: -o] + [时态: -ba] + [语态: -r]
每个词缀是独立的特征节点，可单独查表
```

**阶段二：磨损与融合（Feature Fusion 触发）**

当相邻词缀的音节因高频磨损而发生**合并**时，触发融合：

```python
@dataclass
class PortmanteauMorpheme:
    """融卷词缀：一个表面形式编码多个语法特征的融合包"""
    surface_form: str              # 表面形式，如 "-o"
    feature_bundle: dict[str, str] # 编码的特征包
    # {
    #   "person": "1st",
    #   "number": "singular",
    #   "tense":  "present",
    #   "voice":  "active"
    # }
```

融合规则：当两个相邻词缀 A + B 的合并形式 `AB` 与现有词缀清单中的其他形式发生冲突（同音），且合并形式的使用频率超过阈值时，将 A+B 注册为一个新的 `PortmanteauMorpheme`，原有分析式词缀标记 `is_dead=true`（软删除）。

**阶段三：不规则化锁定**

高频使用的融卷词缀被齐夫矩阵锁定，阻断进一步规则化。这产生了类似拉丁语的不透明屈折形态——从外部已看不出词根和词缀的边界。

---

### 2.3 句法层与生成管线（Syntax & Generation Pipeline）

#### 2.3.1 为什么不用 AST

自然语言的本质是**多义 + 概率 + 语境依赖**，经典 AST（抽象语法树）的根本前提——"语法是上下文无关的、结构是确定的"——在自然语言中不成立。强行用 AST 解析用户输入将陷入 PP Attachment 等无底洞歧义问题。

**决策**：放弃"解析（Parsing）"思路，改为**受控输入 + 生成（Generation）**思路。

#### 2.3.2 受控语义图（Controlled Semantic Graph, CSG）

CSG 是引擎的**语义 API 标准**，充当防波堤，将所有自然语言的混乱挡在核心引擎之外。用户或前端提交的是无歧义的逻辑关系结构，而非自然语言字符串：

```json
{
  "predicate": "SEE",
  "agent": { "ref": "I", "person": 1, "number": "sg" },
  "patient": { "ref": "MAN" },
  "instrument": { "ref": "TELESCOPE" },
  "tense": "PAST",
  "aspect": "PERFECTIVE",
  "modality": "ABILITY",
  "negation_scope": null,
  "subordinate": null
}
```

CSG 的核心优势：
- **无歧义**：彻底绕开 PP 挂靠、量词辖域等结构歧义
- **跨时代稳定**：同一份 CSG 输入，Era 0 输出孤立语句，Era 5 输出黏着语句，输入永远稳定，变化全在引擎内部
- **形态运算锚点**：引擎直接读取 `agent`/`patient` 标签，查询当前格位系统，决定词缀挂载，无需依存句法分析

CSG 表达能力须覆盖：

| 特性 | 字段 | 说明 |
|---|---|---|
| 时制 | `tense` | PAST / PRESENT / FUTURE / TENSELESS |
| 体貌 | `aspect` | PERFECTIVE / IMPERFECTIVE / HABITUAL |
| 情态 | `modality` | ABILITY / NECESSITY / POSSIBILITY / null |
| 否定辖域 | `negation_scope` | "predicate" / "agent" / null |
| 从句 | `subordinate` | 嵌套 CSG 对象 |

> **⚠️ CSG 并没有消灭歧义，只是把它推给了上游**
>
> CSG 是引擎的防波堤，但它本身不解决"谁来生成 CSG"的问题。自然语言的歧义是客观事实，把"消除歧义"推给前端或 LLM，如果 LLM 幻觉（如将 `instrument` 识别成 `patient`）会直接导致符号层输出荒谬的语法结果。

**CSG 输入来源的分级信任模型**：

| 输入来源 | 信任级别 | 处理方式 |
|---|---|---|
| UI 结构化表单（下拉框选主谓宾格） | **高信任** | 直接提交引擎，仅做 Schema 校验 |
| LLM 翻译的自然语言 | **低信任** | 须经过三步纠错协议 |
| 引擎内部生成（RAG 新词推演） | **高信任** | 直接使用 |

**自然语言 → CSG 三步纠错协议**（仅当 UI 提供 NL 输入功能时启用）：

```
① LLM 将自然语言翻译为 CSG JSON
         │
         ▼
② 结构校验器（无需 LLM，纯符号）
   ├─ Schema 合法性检查（字段完整、类型正确）
   ├─ 语义基元合法性（predicate/agent/patient 是否在已知概念表中）
   └─ 角色唯一性（同一实体不能同时是 agent 和 patient）
         │
    通过 → ③ 用户确认展示
    失败 → 返回错误 + 要求 LLM 修正（最多重试 2 次）
         │
③ 可视化展示（"引擎将理解为：我用望远镜看见了那个人"）
   → 用户点击确认 → 提交引擎
   → 用户点击修改 → 退回 ①
```

**核心原则**：对 LLM 生成的 CSG 永远执行用户确认步骤，不允许 LLM 输出直接进入计算层。

#### 2.3.3 五步生成管线

```
① 受控语义输入（CSG）
   [SEE, agent=I, patient=MAN, tense=PAST]
         │
         ▼
② 词汇化（Lexicalization）
   查询 Era N 存活词库，提取词干与音段
   SEE → /vɪd/ (v.)  |  I → /ɛg/ (pron.)  |  MAN → /mɪn/ (n.)
         │
         ▼
③ 句法与形态规划器（Syntactic & Morphological Planner）
   读取类型学参数（SOV / 主宾格 / 动词须变位）
   特征黑板（Feature Blackboard）：[Subject_Person:1st, Subject_Number:Sg]
   判定：/mɪn/ 为受事 → 附着宾格后缀 -o
   判定：/vɪd/ 过去时 → 附加时态标记 -ed
         │
         ▼
④ 线性化生成树（Generation Tree）
   [Pron-Nom: /ɛg/] + [Noun-Acc: /mɪno/] + [Verb-Past: /vɪded/]
   （此处 AST 仍保留，但角色是"生成"而非"解析"）
         │
         ▼
⑤ 表层音系输出（Surface Phonology）
   触发历时音变规则（d-e-d 清化）→ /ɛg/ /mɪno/ /vɪtet/
   → 合法性校验 → 输出
```

**特征黑板与一致性检查（Agreement）**：规划器维护一个包含当前句子特征的黑板，谓词处理时直接从黑板读取主语特征，若语法基因开启"动主一致性"则自动挂载对应人称后缀，彻底避免散乱的 `if-else` 链。

---

### 2.4 语义层（Semantics）

#### 2.4.1 语义基元网络

词义不由 LLM 随机捏造，而由**结构化语义基元（Semantic Primes）**驱动：

- 建立底层语义基元，通过逻辑运算确立核心含义
- 支持通过现有词根组合推断新词：`[WATER] + [EYE] → 眼泪`
- 用户未设定词义时，引擎通过语义运算推断，LLM 仅负责叙事包装

#### 2.4.2 语义漂移算子

| 算子 | 说明 | 示例 |
|---|---|---|
| 扩大（Broadening） | 词义适用范围变广 | dog（特定犬种 → 所有狗） |
| 缩小（Narrowing） | 词义变得极度具体 | meat（所有食物 → 仅指肉类） |
| 贬义化（Pejoration） | 含义由正面变负面 | silly（受祝福的 → 愚蠢的） |
| 褒义化（Amelioration） | 含义由负面变正面 | — |
| 隐喻漂移（Metaphor） | 在语义树相邻节点跳跃 | 太阳 → 白天 → 时间 |

#### 2.4.3 LLM 受控回调机制（Controlled Callback）

原架构"LLM 绝不干预计算"存在一个**结构性割裂**：LLM 在语义漂移阶段推演出的新词义（如 太阳→灵魂 的隐喻链），若仅以叙事文本形式存在，符号层的 CSG 翻译器将无法使用该新词义，导致系统语义与叙事脱节。

**关键问题——符号引擎如何判断"太阳→灵魂"合理而"石头→快乐"不合理？**

纯逻辑基元网络无法判断隐喻的文化合理性。如果校验规则太严，LLM 的精彩提案会被大量拒绝；如果太宽，校验毫无意义。必须用**可量化的标准**替代模糊的"合法性"。

**受控回调协议——三层校验标准**：

```
LLM 推演 → 以强 JSON Schema 返回结构化提案
  {
    "word_id": "sun_42",
    "shift_type": "METAPHOR",
    "from_prime": "CELESTIAL_BODY",
    "to_prime":   "SOUL",
    "chain":      ["CELESTIAL_BODY", "LIGHT", "LIFE_FORCE", "SOUL"]
  }
                │
                ▼
        符号引擎三层校验
        ┌──────────────────────────────────────────────────────┐
        │ 第一层（结构安全，硬校验，失败直接拒绝）:              │
        │  ① 语义环检测：chain 中不存在 A→...→A              │
        │  ② 无效语义基元：chain 中每个节点须在语义树中存在    │
        │  ③ 已死词冲突：to_prime 不能与 is_dead 词的语义相同  │
        │                                                      │
        │ 第二层（图距校验，软校验，超限降级为"叙事专用"）:    │
        │  ④ chain 跳数 ≤ MAX_HOP（默认 4，可配置）           │
        │     例：SUN→LIGHT→LIFE→SOUL（3 跳，通过）           │
        │         SUN→HAPPINESS（直接跳域，1 跳但跨域，拒绝）  │
        │  ⑤ 跨域检测：chain 中不超过 1 次语义域切换          │
        │     （域定义：自然现象/社会关系/抽象概念/物质/动作） │
        │                                                      │
        │ 第三层（文化一致性，统计软校验，可关闭）:             │
        │  ⑥ 检查该语言中已有的隐喻方向（已有先例 → 加权通过） │
        └──────────────────────────────────────────────────────┘
                │
  通过一二层 → 写入 LexicalEntity.semantic_primes（正式入库）
  通过一层但二层超限 → 标记 "lore_only: true"（仅用于叙事，不参与 CSG）
  一层失败 → 硬拒绝 + 记录 + 叙事仍然输出
```

`MAX_HOP` 和域定义是可配置参数，允许用户根据世界观需要调整隐喻的"跳跃距离"。

**铁律**：LLM 只负责"提议"，符号引擎负责"盖章入库"。`lore_only` 的提案可以出现在叙事文本中，但 CSG 词汇化步骤不会使用该词义。

---

### 2.5 历时演变机制（Diachronic Evolution）

所有演化机制实现为**可插拔算子（Evolution Operators）**，支持独立启用/禁用。

#### 2.5.1 五大演变机制

| 机制 | 说明 | 工程实现 |
|---|---|---|
| **音变（Sound Change）** | 规则性音素替换，按时代步进 | YAML 规则配置 + 执行引擎 |
| **类推（Analogy）** | 系统自我修复，使不规则趋于规则 | 形态规则对比与相似性传播 |
| **语法化（Grammaticalization）** | 实词 → 虚词 → 语法标记 | 高频词降级管线 |
| **重新分析（Reanalysis）** | 使用者误解结构导致新规则 | 结构边界重新切分 |
| **借用（Borrowing）** | 来自接触语言的外来词 | 单点热注入（Hot Injection） |

语法化演变链（内置预设路径）：

```
实词 → 附着词 → 词缀 → 消失
动词"去" → 助词"将要" → 将来时前缀 ga- → （磨损脱落）
```

#### 2.5.2 双变量磨损模型（Dual-Variable Erosion）

旧模型 `Erosion_Rate = f(Frequency)` 存在语音学缺陷：许多高频词若处于**重音（Stress）**位置，不仅不会磨损，反而会发生音素强化（Fortition）。

**新模型**：

```
Erosion_Rate = f(Frequency, Stress_Position)

具体规则：
  词尾非重音音节的高频词  → 急速磨损（如助词、后缀）
  词根重音音节的高频词    → 轻度磨损，可能发生强化
  低频词的任意音节        → 轻度磨损，倾向保持完整
```

这一模型同时解释了：为何助词（低重音、高频）最先消失，而核心词根（重音）能抵御磨损。

#### 2.5.3 规则冲突分类与消解

冲突消解中心须明确处理以下**四类冲突类型**：

| 冲突类型 | 描述 | 消解策略 |
|---|---|---|
| **优先级冲突** | 两条规则同时触发，互不兼容 | 按规则优先级字段排序，取最高优先级 |
| **覆盖冲突** | 规则 A 的输出触发规则 B，但顺序不同结果不同 | 严格按注册顺序单趟扫描（No Feeding/Bleeding 模式可配置） |
| **合法性冲突** | 规则执行后产生非法音系结构 | 触发合法性校验器，执行修复或回滚 |
| **语义冲突** | 音变导致词汇与另一词汇同音（同音词灾） | 触发同音词消解器（见 5.3 节） |

#### 2.5.4 范例混合模型（Exemplar Hybrid Model）

纯规则系统存在根本局限：音变太"干净"，变化均匀，产生不了真实语言的**渐变性、不均匀性和内部变体**。

引擎采用**规则 + 范例双层混合架构**：

| 层级 | 功能 | 工程实体 |
|---|---|---|
| 规则层（宏观） | 大规模、跨词汇的音变趋势 | Evolution Operators |
| 范例层（微观） | 词内部的概率性、不均匀变化 | `ipa_exemplars` 字段 |
| DAG 层（历史） | 记录所有演化路径 | DAG 节点与边 |

**组合爆炸风险**：

假设一个词经历 3 条概率性音变规则，每条产生"变/不变"2 种分支，则单词最多产生 $2^3 = 8$ 个变体。10,000 词的词库维护 `keep_top_k=5` 的范例池，每时代需执行约 $10000 \times 5 \times 3 = 150,000$ 次单独计算。**Python 纯 OOP 循环在此规模下每个时代将需要数分钟**，系统完全不可用。

**强制要求——范例层必须向量化**：

```python
# ❌ 禁止：Python 对象循环（OOP 路线）
for word in lexicon:
    for exemplar in word.ipa_exemplars:
        apply_sound_change(exemplar, rule)   # 每次调用 Python 对象方法

# ✅ 要求：NumPy 矩阵化批量运算（Data-Oriented 路线）
# 将整个词库的范例池表达为 2D 数组
# 行 = 范例实例  |  列 = [word_id, phoneme_feature_bits, weight, frequency]
exemplar_matrix: np.ndarray  # shape: (total_exemplars, feature_cols)

# 一次矩阵运算覆盖所有词所有范例
target_mask = (exemplar_matrix[:, voiced_col] == 0) & \
              (exemplar_matrix[:, consonantal_col] == 1)   # 自然音类
prob_vector  = compute_prob(exemplar_matrix[target_mask, weight_col],
                            exemplar_matrix[target_mask, freq_col])
change_mask  = np.random.random(target_mask.sum()) < prob_vector
exemplar_matrix[target_mask][change_mask, voiced_col] = 1  # 整批浊化
```

这意味着音素特征矩阵在范例层的存储须采用**紧凑的数值格式**（特征位压缩为整型位掩码），而非 Python `dict[str, bool]`。**Python OOP 的 `Phoneme` 类是设计文档层的概念接口，实际运行时的批量计算必须走 NumPy 数组路线，或在未来的 Rust 扩展中用 `bitflags` 处理。**

范例坍缩须在每个时代末批量执行（矩阵按 weight 排序 + 截断），不得在单词粒度上逐个调用：

```python
def batch_collapse_exemplars(matrix: np.ndarray, keep_top_k: int = 5) -> np.ndarray:
    # 按 word_id 分组，每组保留 weight 最高的 k 个范例
    ...
```

范例层的效果：同一条音变规则作用于一个词，部分范例变、部分不变，词的内部自然形成**变体（Variation）**，变体竞争后权重高者胜出，这正是真实语言演化的微观机制。

#### 2.5.5 不规则性（Irregularity）

**完全规则的语言是假语言**。基于齐夫矩阵，极高频词（如"我"、"是"、"去"）须被锁定，阻断其参与正常规则化演变，自然产生历史遗留的不规则变位（如 go/went）。不规则性是系统的目标，不是 bug。

---

## 三、系统架构

系统采用高内聚、低耦合的分层架构。

```
┌──────────────────────────────────────────────────────────────┐
│                      前端展示层 (UI Layer)                    │
│    参数仪表盘 | 时代字典 | DAG 词源树 | 发音按钮 | 时间轴      │
└────────────────────────────┬─────────────────────────────────┘
                             │ CSG + UI 参数包
┌────────────────────────────▼─────────────────────────────────┐
│                   核心引擎层 (Engine Layer)                   │
│  规则编译器 | 算子注册表 | 音变执行器 | 合法性校验器           │
│  冲突消解中心 | CSG 规划器 | 特征黑板 | 生成树线性化 | 范例坍缩器│
└──────┬────────────────┬───────────────────────────┬──────────┘
       │                │                           │
┌──────▼──────┐  ┌──────▼──────────────┐  ┌────────▼────────┐
│  领域模型层  │  │   数据存储与语义层   │  │   语音合成层    │
│  Phoneme     │  │  事件溯源 + 关键帧   │  │  IPA → TTS      │
│ PhonemeInv.  │  │  Neo4j DAG（后期）  │  │  eSpeak / SSML  │
│ LexicalEntity│  │  语义基元网络        │  │  G2P 正字法     │
│ ipa_exemplars│  │                     │  │                 │
└─────────────┘  └─────────────────────┘  └─────────────────┘
                             ↕ 受控回调协议
                    ┌────────────────────┐
                    │    LLM 渲染层       │
                    │  时代纪事 | 语义提案 │
                    │  （仅提议，不入库）  │
                    └────────────────────┘
```

### 3.1 领域模型层（Domain Layer）

#### Phoneme——音系计算的原子单位

这是整个引擎的最底层构件。`settings.py` 中目前的 `consonants = ["p", "t", "k"]` 是一个需要在 Phase 0 末尾偿还的技术债，必须在 Phase 1 开始前完成替换。

```python
@dataclass(frozen=True)  # 音素定义不可变
class Phoneme:
    symbol: str          # 表层 IPA 符号，仅用于显示和 TTS
    features: dict[str, bool]
    # 示例 —— /p/：
    # {
    #   "syllabic":     False,  # 不能作音节核
    #   "consonantal":  True,
    #   "voiced":       False,  # 清音
    #   "continuant":   False,  # 塞音（气流完全中断）
    #   "nasal":        False,
    #   "sonorant":     False,
    #   "labial":       True,   # 双唇音
    #   "coronal":      False,
    #   "dorsal":       False,
    # }

    def matches(self, feature_spec: dict[str, bool]) -> bool:
        """判断本音素是否属于某个自然音类（特征束）"""
        return all(self.features.get(f) == v for f, v in feature_spec.items())

    def apply_change(self, change_spec: dict[str, bool],
                     inventory: "PhonemeInventory") -> "Phoneme":
        """将特征变化映射到音素表中对应的音素（如 voiced=True → /b/）"""
        new_features = {**self.features, **change_spec}
        return inventory.find_by_features(new_features)
```

**音素库（PhonemeInventory）**：

```python
class PhonemeInventory:
    def __init__(self, phonemes: list[Phoneme]):
        self._phonemes = phonemes

    def get_natural_class(self, feature_spec: dict[str, bool]) -> list[Phoneme]:
        """返回符合特征束的所有音素（自然音类）"""
        return [p for p in self._phonemes if p.matches(feature_spec)]

    def find_by_features(self, features: dict[str, bool]) -> Phoneme | None:
        """按完整特征向量查找唯一音素"""
        candidates = [p for p in self._phonemes if p.features == features]
        return candidates[0] if candidates else None

    def find_by_symbol(self, symbol: str) -> Phoneme | None:
        return next((p for p in self._phonemes if p.symbol == symbol), None)
```

**内置预设库**（`data/phoneme_presets/` 目录下的 JSON 文件，每个预设定义一套完整的音素清单与特征矩阵）：

```
ipa_standard.json     # 完整 IPA 标准音素集
elven_light.json      # 精灵语预设（多元音、流音为主）
orcish_heavy.json     # 兽人语预设（爆破音、鼻音为主）
```

---

**词汇实体（LexicalEntity）**——当前已实现基础字段，后续按阶段扩展：

```python
@dataclass
class LexicalEntity:
    # --- Phase 0（已实现）---
    id: str
    concept: str             # 语义概念（如 "water"）
    pos: str                 # 词性（n./v./adj. 等）
    ipa_current: str         # 当前时代代表音（范例池权重最高者）
    ipa_history: List[str]   # 历代代表音快照
    frequency_weight: float  # 齐夫频率权重
    is_dead: bool = False    # 软删除标记

    # --- Phase 1（范例层）---
    ipa_exemplars: List[dict] = field(default_factory=list)
    # [{"form": "/taka/", "weight": 0.7}, {"form": "/taga/", "weight": 0.3}]
    stress_pattern: str = ""  # 重音位置（"initial" / "penultimate" 等）

    # --- Phase 2（生命周期）---
    era_born: int = 0
    source_language: str = ""   # 借词来源
    morpheme_type: str = "root" # root / prefix / suffix / clitic
    dag_parent_ids: List[str] = field(default_factory=list)

    # --- Phase 3（语义层）---
    semantic_primes: List[str] = field(default_factory=list)
    semantic_era_log: List[dict] = field(default_factory=list)
    # [{"era": 3, "shift": "METAPHOR", "from": "SUN", "to": "SOUL"}]
```

### 3.2 核心引擎层（Engine Layer）

#### 规则编译器（Rule Compiler）——特征规则到执行后端的桥梁

这是衔接"特征矩阵音系学"与底层执行引擎的关键组件。

> **⚠️ 设计告诫——IR 必须与执行后端完全解耦**
>
> 正则表达式（Regex）与有限状态转换器（FST）在本质上是**不同的计算范式**：Regex 是无状态的模式匹配，FST 是带权图上的自动机组合（Composition）运算，二者无法平滑映射。如果 Rule Compiler 的中间表示（IR）使用了正则特有的 Lookahead/Lookbehind 来处理 before/after 环境，则后期迁移 FST 时底层逻辑须**完全重写**，而非"只换后端"。
>
> **正确做法**：Rule Compiler 的 IR 必须是**后端不可知（Backend-Agnostic）**的。IR 只描述语言学语义（什么音素类在什么语境下变成什么），执行后端是可替换的插件。

**三层架构**：

```
┌─────────────────────────────────────────────────────────┐
│ 规则定义层（用户可见）：YAML 特征束规则                  │
│   target: {voiced:false, consonantal:true}              │
│   change: {voiced:true}                                 │
│   environment: {before:{syllabic:true}, after:...}      │
└────────────────────────┬────────────────────────────────┘
                         │  Rule Compiler（启动时运行一次）
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 中间表示层（IR）：SoundChangeRule 对象                   │
│   target_class:   List[Phoneme]  ← 已展开的自然音类     │
│   output_map:     dict[Phoneme, Phoneme]  ← 变化映射表  │
│   env_before:     List[Phoneme] | None                  │
│   env_after:      List[Phoneme] | None                  │
│   env_flags:      {word_initial, word_final, ...}       │
│   priority:       int                                   │
└────────────────────────┬────────────────────────────────┘
                         │  Backend Adapter（可替换）
                    ┌────┴────┐
                    ▼         ▼
          ┌──────────────┐  ┌──────────────────┐
          │ RegexBackend │  │  FSTBackend       │
          │ (Phase 1–2)  │  │ (pynini, Phase 3+)│
          └──────────────┘  └──────────────────┘
```

**IR（SoundChangeRule）定义**：

```python
@dataclass
class SoundChangeRule:
    name: str
    priority: int
    # 展开后的集合——不含任何正则或 FST 特定结构
    target_class: list[Phoneme]         # 符合 target 特征束的音素集合
    output_map: dict[str, str]          # symbol → symbol（音素符号到音素符号的映射）
    env_before: list[Phoneme] | None    # None 表示任意前环境
    env_after:  list[Phoneme] | None    # None 表示任意后环境
    env_flags: dict[str, bool]          # {"word_initial": False, "word_final": True, ...}
    op: Literal["change", "delete", "insert"]  # 操作类型
```

**后端可替换性验证标准**：任何 `Backend` 实现只接受 `SoundChangeRule` 对象，不接受 YAML 字典，不接受正则字符串。切换后端时 IR 对象**零修改**，这是唯一允许的"平滑迁移"定义。

**规则编译流程**：

```
YAML 规则文件
   ├─ 查询 PhonemeInventory → 展开 target 自然音类 [p, t, k, s, f, ...]
   ├─ 查询 PhonemeInventory → 展开 env_before/after 类 [a, e, i, o, u]
   ├─ 按 apply_change() 构建 output_map {p→b, t→d, k→g, ...}
   └─ 生成 SoundChangeRule IR 对象 → 传入当前 Backend Adapter
```

**同一份 YAML 在不同音素清单的语言中自动适配**：精灵语和兽人语的"所有清辅音"集合不同，但规则描述相同，IR 展开结果自动不同。

---

**其他引擎组件**：

- **算子注册表**：所有演化算子通过注册表管理，支持热启用/禁用，不修改调度逻辑
- **音变执行器**：按优先级顺序调用已编译规则，执行替换，输出 IPA 字符序列
- **合法性校验器**：每次音变后验证音系结构，触发插音修复或回滚
- **冲突消解中心**：按四类冲突类型分别处理（见 2.5.3 节）
- **CSG 规划器**：读取 CSG + 类型学参数，经五步管线输出当代语法句
- **特征黑板**：维护句子级特征状态，供一致性检查使用
- **范例坍缩器**：定期将范例池收缩至 top-k，防止内存爆炸

### 3.3 数据存储与语义层（Data Layer）

**计算层与持久层必须严格分离**：

Event Sourcing 解决了**存储爆炸**问题，但如果每次演化计算都需要从关键帧重放 Delta 日志来重建当前状态，计算复杂度将是 O(E × (K+D))（E 为时代数，K 为关键帧重建时间，D 为日志重放时间），同时 Python 对大规模对象的深拷贝极其缓慢。

**双层设计——计算热状态（Hot State）+ 事件溯源持久层**：

```
┌──────────────────────────────────────────────────────────┐
│               计算层（内存，常驻）                        │
│  Hot State: 当前时代的完整词表（dict[id → LexicalEntity]）│
│  ← 引擎的所有演化计算仅操作此对象，永远不重放日志         │
└────────────────────────┬─────────────────────────────────┘
                         │ 每次修改后写入事件
                         ▼
┌──────────────────────────────────────────────────────────┐
│               持久层（磁盘/DB，异步写入）                 │
│  Era 0  [FULL SNAPSHOT]                                  │
│  Era 1  [DELTA: word_42 /taka/→/taga/]                  │
│  Era 2  [DELTA: word_07 is_dead=true]                   │
│  Era 3  [DELTA: word_15 借词注入 /stɛːl/]               │
│  ...                                                     │
│  Era 10 [FULL SNAPSHOT]  ← 每 N 个时代保存关键帧          │
└──────────────────────────────────────────────────────────┘
```

**运行时规则**：
- **引擎计算**永远只读写 Hot State，不接触持久层
- **每次修改**（音变、死词标记、借词注入）写入 Delta 事件后立即更新 Hot State
- **历史查询**（"Era 3 的词库是什么？"）通过最近关键帧 + 重放日志完成，但这是只读的历史重建操作，不影响计算

这将同音词消解、类推传播等需要"全景视角"的操作的复杂度降回 O(词汇量)，因为 Hot State 始终是当前时代的完整词表。

词汇演化路径以**有向无环图（DAG）**记录：

```
原始词根 [ipa: /taka/]
    ├── Era 1 → 同化：/taka/ → /taga/（浊化）
    │       ├── Era 2 → 主支：/taga/ → /tag/（词尾元音脱落）
    │       └── Era 2 → 分支：森林精灵语 /taɣa/（摩擦化）
    └── Era 1 → 借词：兽人语借入 /tak/
```

### 3.4 语音合成层（TTS Layer）

- **唯一后端货币**：IPA 是引擎内部唯一计算标准，永远不对拼写字符串进行计算
- **G2P 正字法系统**：分离表面拼写（Orthography）与底层发音（IPA）。前端可展示奇幻拼写（/θ/ → `th`），引擎只操作 IPA
- **发音后端**（方案待最终确认）：
  - `eSpeak NG`：处理单音素与罕见音的精确合成
  - `Edge-TTS / Azure TTS + SSML`：处理长句韵律与语调

---

## 四、核心推演管线

```
[用户 UI 参数输入]
        │ 参数包（种子 / 音系偏好 / 语法基因 / 世界语言列表）
        ▼
┌─────────────────┐
│  阶段一：创世    │  音系初始化 + 词库生成 + 语法基因设定 + Era 0 快照（关键帧）
└────────┬────────┘
         │
         ▼
┌──────────────────────────┐
│  阶段二：历时音变与磨损   │  音变执行 → 合法性校验 → 同音词消解 → 不规则伤疤
│  （可循环多个时代）       │  Delta 日志记录 + 定期关键帧
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│  阶段三：语法化与形态演化 │  类型漂移 + 语法化降级 + 语序漂移 + 分支语言
│  （可循环多个时代）       │  RAG 新词推演 + 借词注入
└────────┬─────────────────┘
         │
         ▼
┌────────────────────────────────┐
│  阶段四：LLM 文化渲染（可关闭） │  时代纪事 + 语义漂移提案 → 受控回调入库
└────────┬───────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  输出：各时代字典 + 演化 DAG + 音频朗读  │
└─────────────────────────────────────────┘
```

### 阶段一：创世（Genesis）

1. 接收 UI 参数包（种子、音素偏好、音节复杂度、语法基因、是否开启 LLM、世界语言列表）
2. 按参数初始化音素清单与音位配列约束（双层系统）
3. 基于斯瓦迪士列表生成初代核心词根：初始化范例池（单一范例，weight=1.0），打上 POS 标签与齐夫频率权重
4. 确立语序基因与时态/体貌路线
5. 保存 Era 0 关键帧快照

### 阶段二：历时音变与物理磨损（Erosion）

1. 加载当前时代音变规则集，按优先级顺序执行，每条规则后触发合法性校验
2. 按双变量磨损模型（频率 × 重音位置）差异化施加磨损；范例层以概率方式应用音变
3. **同音词灾检测与多策略消解**（见 5.4 节）
4. **不规则伤疤**：锁定极高频词，阻断规则化
5. 用户可插入新词（含跨语言借词）或标记死词（基础词汇不可删除）
6. 记录 Delta 日志；每 N 个时代保存关键帧

### 阶段三：语法化与形态演化（Grammaticalization）

1. **类型漂移**：根据积累磨损程度，判断是否触发孤立语 ↔ 黏着语 ↔ 屈折语的转变
2. **语法化降级**：高频实词因发音极度磨损，降级为语法标志（前缀/后缀/助词）
3. **语序漂移**：当格位后缀磨损脱落时，触发语序固化
4. **新词推演（RAG 锚点）**：检索相关古词根，调用 LLM 推演新词汇，数量严格控制，专有名词≤总词量 5%
5. **分支语言**：在设定节点产生方言/分支，各自独立演化；分支间可产生跨语言借词

### 阶段四：文化渲染（LLM Lore Generation，可关闭）

- 引擎将本时代存活词表、规则突变快照以强 JSON Schema 传递给 LLM
- LLM 生成 ~100 字时代纪事，并以 JSON 格式返回语义漂移提案
- 符号引擎对提案进行合法性校验，通过则写入 `LexicalEntity`，否则仅保留叙事文本
- 关闭此阶段后引擎保持纯符号计算状态，输出完全确定性

---

## 五、特色工程学机制

### 5.1 可插拔演化算子（Pluggable Operators）

```python
evolution_pipeline.register(VoicingAssimilationOperator, enabled=True,  priority=10)
evolution_pipeline.register(FinalVowelDropOperator,      enabled=True,  priority=20)
evolution_pipeline.register(GrammaticalizationOperator,  enabled=False, priority=30)
```

每个算子包含：触发条件、作用域（全局 / 特定 POS / 特定音系环境）、优先级、回滚函数。新增算子不修改调度核心。

### 5.2 软删除与化石词根（Soft Delete）

演化淘汰的词汇打上 `is_dead: true`，在现代词典隐藏，但其残留音节可作为"化石前缀"继续存活于复合词中，模拟真实语言的历史层积。

### 5.3 单点热更新与跨语言借词（Hot Injection & Cross-Lingual Borrowing）

支持在特定时代注入借词：

```json
{
  "concept": "steel",
  "source_language": "古矮人语",
  "inject_at_era": 3,
  "ipa_injected": "/stɛːl/",
  "adaptation_rules": ["final_cluster_simplification"]
}
```

**跨语言借词**：用户可传入多个已生成的语言实例（如精灵语 + 兽人语），当两种语言处于同一世界时，引擎按设定的文化接触强度，允许本语言从接触语言中少量借词（数量受控），以体现真实的文化交流。借入词须经过语音适应规则（Phonological Adaptation），而非原样插入。

注入词仅从注入点开始参与后续磨损，无需回滚前期数据。

### 5.4 多策略同音词消解器（Homophone Resolution）

当词汇过度磨损导致同音词溢出阈值时，引擎触发消解器，按以下策略优先级依次尝试：

```yaml
homophone_resolution:
  strategies:
    - reduplication      # 重叠化（如 ta → tata）
    - affixation         # 添加区分性词缀
    - semantic_shift     # 语义分化（多义词分裂为两个独立词义）
    - borrowing          # 从接触语言借词替代
    - lexical_death      # 最后手段：频率较低者标记为 is_dead
```

消解策略的选择本身也受语法基因影响：黏着语型语言优先选择词缀策略，孤立语型优先选择借词或语义分化。

### 5.5 逆向词源引擎（Reverse Etymology）

为用户强行预设的现代核心词汇提供词源倒推。引擎在数据库中寻找发音相近的古词，调用 LLM 附会出合理词源叙事。若发音距离超过阈值、逻辑断裂无法自圆其说，系统记录"词源不明（Etymology Unknown）"，不强行编造。

### 5.6 受控语义回调（Controlled Semantic Callback）

详见 2.4.3 节。核心铁律：LLM 只提议，符号引擎盖章。任何未经校验的语义提案不得进入词汇库。

### 5.7 测试驱动的语言学（TDD for Linguistics）

新增每一条音变规则**必须先写测试**：

```python
def test_final_vowel_drop():
    rule = FinalVowelDropOperator()
    assert rule.apply("taka") == "tak"
    assert rule.apply("minu") == "min"
    assert rule.apply("kp") == "kp"  # 无元音，不触发
```

单元测试覆盖：规则本身、规则优先级顺序、合法性校验、范例坍缩、CSG 生成树输出。

---

## 六、用户输入参数规范（UI 参数包）

| 参数类别 | 参数项 | 说明 |
|---|---|---|
| 基础设定 | `seed` | 全局随机种子，0 表示自动生成 |
| 基础设定 | `is_llm` | 是否启用 LLM 渲染层 |
| 世界观背景 | `environment` | 地理环境（森林/冻土/沙漠等） |
| 世界观背景 | `race` | 种族（精灵/人类/兽人等） |
| 世界观背景 | `world_languages` | 同一世界中的其他语言列表（用于跨语言借词） |
| 音系偏好 | `phoneme_preset` | 音素风格预设，或自定义音素清单 |
| 音系偏好 | `phonotactic_complexity` | 音节复杂度档位（极简/标准/复杂/炼狱） |
| 音系偏好 | `ipa_preference` | 用户偏好的 IPA 音素集合 |
| 音系偏好 | `custom_base_lexicon` | 用户直接为基础词库设定的发音（可选，优先级最高） |
| 语法偏好 | `word_order` | 初始语序（SVO/SOV/VSO 等） |
| 语法偏好 | `tense_system` | 时态路线（印欧屈折式/孤立虚词式/无时态） |
| 语法偏好 | `morphological_type` | 初始语言类型（孤立语/黏着语/屈折语） |
| 演化控制 | `evolution_operators` | 本次启用的演化算子列表 |
| 演化控制 | `era_steps` | 演化时代总步数 |
| 演化控制 | `keyframe_interval` | 关键帧保存间隔（默认每 10 个时代） |
| 演化控制 | `branch_languages` | 分支语言设定（名称 + 分叉时代 + 环境偏差） |

---

## 七、分阶段开发目标

### Phase 0 — MVP 基础闭环 ✅ 已完成

**目标**：打通最小系统闭环，验证核心数据模型与存储流程。不引入 LLM、不引入分支语言、不引入范例层、不引入语法化。

- [x] `Poetry` 环境搭建与依赖锁定
- [x] 全局配置系统（`GlobalSettings` + `Configs`）
- [x] 基础词汇实体模型（`LexicalEntity`）
- [x] 斯瓦迪士列表 JSON 数据源（swadesh_207.json，含 207 词条）
- [x] 基础 IPA 音节生成（CV/CVCV 模板，均匀随机）⚠️ *技术债：当前使用 `List[str]`，Phase 0 末尾前必须替换为 `List[Phoneme]`*
- [x] swadesh_207.json 词频校准（`true_freq_rank` + `word_class`，基于 SUBTLEX-US 语料库估算）
- [x] 双轨 Zipf-Mandelbrot 频率模型（GCZ 虚词区 0.45 / LZ 实词区 0.55，`β` 偏移修正高频平台）
- [x] Era 0 快照 JSON 保存
- [x] **`Phoneme` 数据类与 `PhonemeInventory` 实现**（偿还上述技术债，Phase 0 的最后一步）
- [x] **内置音素预设 JSON 文件**（至少提供 `ipa_minimal.json`，含标准二值特征矩阵）
- [x] **将 `GlobalSettings.consonants/vowels` 迁移为 `PhonemeInventory` 对象**
- [x] 2–3 条硬编码音变规则（词尾元音脱落、清辅音浊化）及其单元测试
- [x] Era 0 → Era 2 基础演化流程（顺序执行，无冲突消解）
- [x] 10 个测试句简单组装（仅拼接，无形态变化）

> **Phase 0 退出标准**：`Phoneme` 类存在，且所有音变规则的目标/环境描述均以特征字典而非字面字符串表达。在此之前不得进入 Phase 1。

---

### Phase 1 — 规则编译器（IR 优先）+ 真实音系引擎 + 存储架构升级 ✅ 已完成

**目标**：引入后端不可知的规则编译器 IR；升级音系引擎为真实特征计算；完成存储双层架构。

> **⚠️ Phase 1 设计红线**：规则编译器的中间表示（`SoundChangeRule` IR）不得包含任何正则表达式或 FST 特定结构。任何 Backend（Regex/FST/原生 Python）只接受 IR 对象，不接受原始字符串。

**规则编译器——IR 优先（核心新增）**：
- [x] `SoundChangeRule` IR 数据类（后端不可知，见 3.2 节定义）
- [x] `RuleCompiler.compile()`: YAML → `SoundChangeRule` IR（含自然音类展开 + output_map 构建）
- [x] `Backend` 抽象接口（`apply(rule: SoundChangeRule, sequence: list[str]) -> list[str]`）
- [x] `RegexBackend`：将 IR 转为内存中的正则并执行（**不允许 IR 依赖正则特性**）
- [x] `NativeBackend`：纯 Python 列表迭代实现 IR，用于单元测试验证
- [x] `delete` / `insert` op 支持（脱落和插音）
- [x] 规则编译器核心测试：同一 IR 在 RegexBackend 和 NativeBackend 下输出一致

**音系引擎**：
- [x] 双层音位配列系统（结构模板 + onset_clusters / coda_set，基于特征束查询，非字符串枚举）
- [x] 条件概率音素选取（概率权重挂载在 `Phoneme` 对象上）
- [x] 音节复杂度四档（位置敏感）：CV / CVC / CVCV / CCVC，尾辅音偏向 sonorant 池
- [x] 风格预设体系（对应不同 `PhonemeInventory` 预设 JSON）
- [x] 可插拔算子注册表（接受 `SoundChangeRule` IR）
- [x] 音系合法性校验器（基于特征约束 + 插音修复 + 回滚）
- [x] 四类规则冲突消解中心

**存储架构——计算层/持久层分离**：
- [x] `EngineHotState` 类：内存中的当前时代完整词表，所有演化计算的唯一操作对象
- [x] Delta 日志写入（每次修改后异步写入，不阻塞计算）
- [x] Keyframe 关键帧机制（可配置间隔，Era N 的全量序列化）
- [x] 历史重建接口：从关键帧 + Delta 重建任意时代（只读，不影响 Hot State）

**范例层——NumPy 路线（禁止 OOP 循环）**：
- [x] `LexicalEntity` 新增 `ipa_exemplars` 字段（Python 接口层，供序列化）
- [x] `ExemplarMatrix`：将词库全部范例池打包为 NumPy `ndarray`，音素特征以 `uint16` 位掩码存储
- [x] 批量概率性音变（矩阵级运算，禁止 Python 逐词循环）
- [x] 批量坍缩器（`batch_collapse_exemplars`，keep_top_k=5，矩阵排序截断）
- [x] Phase 1 末尾性能基准测试：1000 词 × 5 范例 × 10 规则的单时代演化 < 1 秒（实测 ~0.1s）

**TDD**：
- [x] `tests/phonology/test_rule_ir.py`：IR 构建正确性
- [x] `tests/phonology/test_backend_parity.py`：RegexBackend vs NativeBackend 输出一致性
- [x] `tests/phonology/test_natural_class.py`：自然音类展开正确性
- [x] `tests/storage/test_hot_state.py`：Hot State + Delta + 关键帧重建一致性
- [x] `tests/exemplar/test_batch_compute.py`：NumPy 批量计算与 OOP 循环结果一致性（OOP 仅用于验证）

> **Phase 1 退出标准**：Rule Compiler 通过后端一致性测试；性能基准达标；Hot State 与持久层接口完全分离。✅ 全部满足。

---

### Phase 2 — 词汇生命周期与 DAG

> **Phase 2 启动前决策点**：根据 Phase 1 末尾性能基准，评估 ADR-001（计算核心技术栈）。若 NumPy 方案在 DAG 遍历和 Hot State 深拷贝上出现明显瓶颈，Phase 2 启动 Rust 核心（方案 C），通过 PyO3 向 Python 层暴露接口。

**目标**：实现词汇的完整历史追溯与生命周期管理。

- [x] `LexicalEntity` 扩展（`era_born`、`dag_parent_ids`、`source_language`、`morpheme_type`）
- [x] 软删除机制（`is_dead` 标签 + 化石前缀存活逻辑）
- [x] DAG 词源结构（初期 JSON 模拟邻接表，后期对接 Neo4j）
- [x] 单点热更新接口（含跨语言借词适应规则）
- [x] 多策略同音词消解器（5 策略优先级队列）
- [x] 不规则伤疤生成（高频词锁定机制）
- [x] 双变量磨损模型（频率 × 重音位置）
- [x] 用户词汇插入/删除接口（含基础词汇保护锁）
- [x] 跨语言借词接口（接收外部语言实例 → 音系适应 → 注入）

---

### Phase 3 — CSG 生成管线

**目标**：用受控语义图（CSG）替代 AST 解析方案，打通五步生成管线。

- [x] CSG Schema 设计与校验器（含语义环检测）
- [x] 词汇化层（Lexicalization）：CSG 语义基元 → Era N 存活词干映射
- [x] 语义基元网络（Semantic Primes）基础结构
- [x] 类型学参数矩阵（语序、时态/体貌路线、格位系统、一致性约束）
- [x] 特征黑板（Feature Blackboard）与 Agreement 合一检查
- [x] 句法与形态规划器（读取类型学参数，决定词缀挂载）
- [x] 生成树线性化（Generation Tree → 音素序列）
- [x] 表层音系输出（对生成序列再次触发音变规则）
- [x] 跨时代同句对比输出（同一 CSG，Era 0 vs Era 5 vs Era 10）
- [x] 分支语言独立演化管线（各分支维护独立参数矩阵）

---

### Phase 4 — 语法化与形态演化

**目标**：实现语言类型的动态漂移与真实语法演化。

- [x] `LexicalEntity` 语法化字段扩展（`word_class`, `grammaticalization_stage`, `grammaticalized_from_id`, `grammatical_function`）
- [x] `data/grammaticalization_pathways.yaml` 语义-功能路由配置（7 条预设路径，含类型学三分支）
- [ ] 语言类型漂移引擎（孤立语 ↔ 黏着语 ↔ 屈折语，含触发阈值配置）
- [ ] `GrammaticalizationOperator`：读取 `grammaticalization_pathways.yaml`，按触发条件（`true_freq_rank` + 磨损步数）将高频实词降级为虚词，产物形态由类型学参数决定
- [ ] 语法化演变链配置化（内置预设路径 + 用户自定义路径）
- [ ] 语序漂移触发条件（格位脱落率 → 语序固化判定）
- [ ] 汉藏路线：虚词/助词生成系统
- [ ] 印欧路线：后缀屈折磨损系统
- [ ] 类推传播（Analogy）：相似词群之间的形态模式扩散

---

### Phase 5 — LLM 渲染层集成

**目标**：引入 LLM，将语言学数据包装为世界观叙事，并建立受控回调通道。

- [ ] LLM 接口抽象层（支持多模型后端热切换，统一输入/输出 Schema）
- [ ] 强 JSON Schema 数据交接格式定义（引擎 → LLM）
- [ ] 时代纪事生成（~100 字历史叙事，封装为"神话/迁徙/技术革命"）
- [ ] 受控回调协议实现（LLM 语义提案 → 校验器 → 入库或拒绝）
- [ ] RAG 锚点新词推演（相关古词根检索 → LLM 推断新词义 → 校验）
- [ ] 逆向词源引擎（预设现代词 → 倒推词源，含放弃判定阈值）
- [ ] LLM 功能全局开关（纯符号模式须完全可用）

---

### Phase 6 — 语音合成与前端展示

**目标**：完成可展示、可朗读的完整交互系统。

- [ ] TTS 后端最终选型与集成（eSpeak NG 精确音素 + Edge-TTS 长句韵律）
- [ ] G2P 正字法系统（IPA ↔ 奇幻字符拼写映射，前端可自定义）
- [ ] 各时代字典前端展示（含发音按钮、词性、语义、词源链接）
- [ ] 词源演化树可视化（可交互 DAG，支持展开/折叠分支）
- [ ] 历史时期时间轴拖拽导航（跨时代状态重建）
- [ ] UI 参数配置仪表盘（CSG 输入表单 + 参数拖拽 + 实时预览）
- [ ] 多分支语言对比展示（同词根跨分支演化路径对比）

---

## 八、技术选型清单

| 技术/库 | 用途 | 状态 |
|---|---|---|
| Python 3.10+ | 胶水层与 LLM 接口（始终存在）| ✅ 已确定 |
| Poetry | 依赖管理与环境隔离 | ✅ 已确定 |
| NumPy | 范例层批量矩阵计算、特征位掩码运算 | 🔧 Phase 1 末引入 |
| `re`（标准库） | RegexBackend 实现（Phase 0–2，由 IR 驱动） | ✅ 当前使用 |
| `pynini`（OpenFST） | FSTBackend 实现（ADR-002 决策后引入） | 🔜 按需引入 |
| Rust + PyO3 | 计算核心热路径（ADR-001 Phase 2 决策点） | 🔜 待评估 |
| IPA 音素预设 JSON | 标准特征矩阵数据文件（`data/phoneme_presets/`） | 🔧 Phase 0 末完成 |
| JSON | 敏捷期 Delta 日志与关键帧存储 | ✅ 已确定 |
| Neo4j | 成熟期 DAG 词源图数据库 | 🔜 Phase 2+ |
| eSpeak NG | 精确 IPA 单音素合成 | 🔜 Phase 6 评估 |
| Edge-TTS / Azure TTS | 长句韵律与语调合成 | 🔜 Phase 6 评估 |
| Streamlit / Gradio | 开发期快速 UI | 🔜 Phase 6 MVP |
| 独立 Web UI 框架 | 发布期语言维基系统 | 🔜 待定 |
| LLM API（多后端） | 语义渲染与纪事生成 | 🔜 Phase 5 |

---

## 九、关键约束与设计原则

1. **LLM 不干预计算，但可受控提议**：LLM 的任何推演结果须经过符号引擎的合法性校验方可入库。未通过校验的提案仅用于叙事，不参与任何后续计算。

2. **IPA 是唯一后端货币**：引擎内部永远只对 IPA 字符串进行操作。G2P 映射和奇幻正字法只在前端展示层发生。

3. **种子保证确定性**：相同种子 + 相同参数包 + 相同算子集合 → 跨端输出绝对一致（范例层的概率性音变同样由种子控制的 RNG 驱动）。

4. **演化算子必须可插拔**：新增或禁用任意演化规则不得修改调度核心逻辑。

5. **基础词汇不可删除**：斯瓦迪士核心词汇在任何时代均不能硬删除，可标记 `is_dead` 但化石痕迹须保留。

6. **测试先行**：每新增一条音变规则，必须先在 `tests/` 中写明其基准词汇上的预期输出并通过。

7. **不追求完全规则**：完全规则的语言是假语言。引擎须主动引入不规则性、冗余与历史遗留异常。范例层的变体竞争机制是实现这一点的核心手段。

8. **Rule Compiler IR 后端不可知**：`SoundChangeRule` IR 不得包含任何正则或 FST 特定结构。Backend 是可替换插件，IR 是不变契约。从 RegexBackend 迁移至 FSTBackend 不得修改 YAML 规则文件，也不得修改 IR 数据类。

9. **CSG 是引擎的外部 API，且对 LLM 生成的 CSG 永远需要用户确认**：任何句子生成请求必须通过 CSG 结构体提交。LLM 翻译的自然语言 CSG 须经过三步纠错协议和用户确认，不允许直接进入计算层。

10. **音素是特征矩阵，不是字符串**：引擎内部以特征矩阵（Python 接口层用 `Phoneme` 对象，计算热路径用 `uint16` 位掩码）作为音系计算的原子单位。IPA 符号仅用于显示和 TTS，不参与任何音系逻辑运算。任何以字面字符串比较来判断音素类别的代码均视为架构违规。

11. **范例层批量运算禁止 Python OOP 循环**：范例池的音变计算必须走 NumPy 矩阵路线（或未来的 Rust 核心），不允许对 `Phoneme` 对象逐个 Python 方法调用。性能基准（Phase 1 末尾）是硬性退出标准。

12. **计算层永远操作 Hot State，持久层只做读写**：引擎的任何演化计算只读写内存中的 `EngineHotState`，Delta 日志是其副产物。计算不重放日志，历史查询不影响 Hot State。

13. **屈折语形态须通过 PortmanteauMorpheme 而非不规则词缀表**：从黏着语磨损到屈折语的算法路径必须实现 Feature Fusion（融卷算法），不得以"不规则词缀表手写例外"代替真正的特征融卷机制。

---

*文档版本：0.3 — 2026-04-06*
*对应代码版本：Phase 0 进行中*
