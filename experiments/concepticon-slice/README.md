# Concepticon 小型研究切片

研究问题：词义对齐引用能否定位到**真实发布记录**，并保留源词表、映射判断、
定义和可重复的转换链？本切片回答数据定位问题，不生成词汇或生产语言状态。

`slice.json` 保留 Swadesh-1955-100 的 12 个开发条目、对应的 12 个 concept sets
和一个 source-list 记录。所有列值原样保留；JSON 排序与选取顺序见 `lock.json`。
这些英文标签是引导词，不要求架空语言按同样方式切分词义。它们没有提供
谓词论元、量化/否定作用域、词类、文化范畴或语用承诺的完整模型。

## 来源、署名与许可

数据：List, Johann Mattis; Tjuka, Annika; Blum, Frederic; Kučerová, Alžběta;
Barrientos Ugarte, Carlos; Rzymski, Christoph; Greenhill, Simon; Forkel, Robert
(2025). *CLLD Concepticon 3.4.0 as CLDF dataset*, v3.4.0.
[固定发布 DOI](https://doi.org/10.5281/zenodo.14923561)，
[官方数据说明](https://concepticon.clld.org/download)。

数据许可为 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)；以发布
ZIP 内 LICENSE、CLDF metadata 和发布记录核对。仓库 MIT 不覆盖这些派生数据。
本项目的改动是选取、重排及附加研究元数据，没有改写原始行值；不暗示原作者认可。

源词表的 Source 是 `Swadesh1955`，发布物 `cldf/sources.bib` 对应：Swadesh,
Morris (1955), “Towards greater accuracy in lexicostatistic dating”,
*International Journal of American Linguistics* 21(2), 121–137；本切片所保留的
词表记录给出 pages 133–137。没有阅读原论文，不据此认定概念普遍稳定或支持年代估计。

ZIP SHA-256：`a385f04140540582222d6a57f596d38b28e4f5a39c02a828d9223f9cb540fc6e`。
嵌入 metadata 的 `prov:wasDerivedFrom` 仍记载 v3.3.0 / v3.3.0-26-gad44e5e0，
与发布版本字段不同；锁中如实保存，不猜测或静默改名。锁标识的是实际发布字节。

## 离线复现与边界

无需网络或新依赖，检查仓库内产物与引用闭包：

```bash
.venv/bin/python -I scripts/concepticon_slice.py
```

从固定 DOI 的 ZIP 本地副本完整复现（12.5 MB 原包不进入仓库或产品）：

```bash
.venv/bin/python -I scripts/concepticon_slice.py --archive target/research/concepticon-cldf-v3.4.0.zip
.venv/bin/python -I -m pytest tests/core/test_concepticon_slice.py -q
```

脚本只读输入，核对 archive、metadata、LICENSE、bibliography、三个源表和
transform 的锁，重算选择并比较输出字节。`resolve_reference` 只查询已校验
研究切片中的 dataset/table/record；未知或切片外记录报错。它不证明切片外记录
不存在，也不使 Rust `DataRegistry` 获得生产成员校验能力。

拒绝源表重复 ID、重复 ZIP 成员、外来词表关系、缺映射、`0/<NA>` 占位映射及
需要显式 replacement 选择的集合。仅核对这三张表的选取闭包；不是完整 CLDF
验证器，不核对全部关系网、retired 表或 bibliography 引用的语义。
checksum 不是签名；同时替换锁和数据仍需独立来源复核，不能获得信任授权。

抽样是开发者有目的地选择**源词表条目**，映射目标为 concept sets；没有采样
语言或 doculect，不估计跨语言频率。一个英语引导的历史词表有明显覆盖局限。
该材料只用于 development，不能作为 sealed audit、真实作者研究或自然性证据。
所有格式均为版本化研究产物；无 RNG、状态迁移、事件回放或生产 writer 变更。
