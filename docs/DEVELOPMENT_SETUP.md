---
document_type: runbook
decision_status: not-applicable
implementation_status: implemented
normative_scope: current
last_verified: 2026-10-16
---

# 开发环境与质量检查

> 本文记录本地质量入口。Python 命令维护旧引擎基线、黄金场景和跨仓库文档检查；
> Rust workspace 与 Tauri 使用独立的 Rust 质量门。正式产品方向见
> [ADR-006](./adr/ADR-006-rust-native-core-python-research-bridge.md)，完整强制命令以
> 仓库根目录 [AGENTS.md](../AGENTS.md) 为准。运行与验证均在本地，GitHub 只保存代码。

- 状态：`Current local quality runbook`
- 基线日期：2026-07-12；最后核验：2026-10-16
- 默认开发版本：Python 3.13
- 支持范围：Python 3.10–3.14

2026-10-16 用户明确关闭远端执行。旧 CI 工作流保留为
[历史参考](./archive/ci-workflow-2026-10-16.yml)，已移出 `.github/workflows/`；
没有 push、PR、定时或手动远端执行入口。后续新增活跃 workflow 会使本地检查失败。
Git push 只保存阶段代码，不把旧远端 CI 要求当作继续执行的授权。

## 1. Windows 环境

安装 Python 3.13 后，在 PowerShell 中执行：

```powershell
py -3.13 -m venv .venv
uvx --from poetry==2.4.1 poetry sync --no-interaction
```

Poetry 必须运行在与项目 `.venv` 分离的工具环境中；也可以使用固定到 2.4.1 的
`pipx` 安装。不要把 Poetry 自身安装进项目 `.venv`，否则环境不再与 `poetry.lock`
描述的运行/开发依赖集合相等。

进入虚拟环境不是必需的，可以始终通过 `.venv` 中的 Python 执行命令。若希望激活：

```powershell
.\.venv\Scripts\Activate.ps1
```

## 2. macOS 与 Linux 环境

```bash
python3.13 -m venv .venv
uvx --from poetry==2.4.1 poetry sync --no-interaction
```

## 3. Rust 与 Tauri 工具链

当前 workspace 的 MSRV 与精确验证工具链均为 Rust `1.88.0`：

```text
Cargo.toml [workspace.package].rust-version = 1.88.0
rust-toolchain.toml channel = 1.88.0
```

当前 `Cargo.lock` 中经 Tauri 进入 workspace 的 `time`、`plist`、`darling` 和
`serde_with` 等依赖声明的最高 `rust-version` 为 1.88.0。metadata 只确定候选下限；
必须使用精确 1.88.0 完成 locked build/test/clippy 才构成 MSRV 实现检查。依赖图改变时
必须重新计算并验证，不能把这一版本当成永久不变的产品规律。
`.cargo/config.toml` 的 `incompatible-rust-versions = "fallback"` 约束以后重新解析依赖时
优先选择兼容版本，但它不替代已提交 lock graph 的精确工具链验证。

所有平台先安装精确工具链：

```text
rustup toolchain install 1.88.0 --profile minimal --component rustfmt,clippy
```

Windows 还需要 Microsoft C++ Build Tools 与 WebView2 开发/运行环境。Debian/Ubuntu
开发机使用 [Tauri v2 官方前置要求](https://v2.tauri.app/start/prerequisites/)
列出的原生依赖：

```bash
sudo apt update
sudo apt install -y \
  libwebkit2gtk-4.1-dev \
  build-essential \
  curl \
  wget \
  file \
  libxdo-dev \
  libssl-dev \
  libayatana-appindicator3-dev \
  librsvg2-dev
```

这些包只说明 Debian/Ubuntu 的构建前置；`ubuntu-24.04` 通过不能推导所有 Linux
发行版、macOS、安装包或运行时兼容性已经得到证明。

## 4. 一键质量检查

Windows：

```powershell
.\.venv\Scripts\python.exe -I scripts/check.py
```

macOS/Linux：

```bash
.venv/bin/python -I scripts/check.py
```

该脚本依次执行：

1. Python 语法编译；
2. Ruff 正确性级静态检查；
3. 文档链接、索引、Gate、schema 和 desktop command 一致性检查；
4. 完整 pytest 测试套件。

pytest 使用系统为当前进程分配的独立临时目录；不得在共享工作树中固定一个 basetemp，
以免连续运行或并发 agent 互相删除目录。测试缓存插件在该总门禁中关闭。任一步失败都会
返回非零退出码。本地开发和独立本地复查使用同一个脚本。

需要刷新 G0A 证据时，不手工编辑测试数量或工作区计数。执行：

```powershell
.\.venv\Scripts\python.exe -I scripts/generate_gate_evidence.py --verify
```

当前应审查的 G0A 合同指针是 Proposed
[G0A policy v2](./G0A_POLICY_V2.json) 及其
[schema](./G0A_POLICY_V2.schema.json)，以及 Proposed
[GateEvidence v3 model](./governance/GATE_EVIDENCE_MODEL_V3.md) 和
[manifest schema](./GATE_EVIDENCE_MANIFEST_V3.schema.json)。生成器与测试已有本地
迁移实现候选，不等于这些治理合同已被独立接受；现有 GateEvidence/STATUS 尚未形成
有效 v3 attestation，G0A 必须保持 `blocked`。

准备独立评审与 clean subject 前，先运行：

```powershell
.\.venv\Scripts\python.exe -I scripts/g0a_handoff.py --check --json
```

它会列出全部 subject candidate、两份 attestation-only 生成文件、待审合同哈希以及被拒绝的
缓存/构建产物。提交 subject 后追加 `--require-clean-subject`；该检查成功只证明 worktree
边界满足交接条件，不表示 ADR 已接受或 G0A 已通过。完整职责与提交顺序见
[G0A 独立评审与 Clean Baseline 交接](./governance/G0A_REVIEW_AND_BASELINE_HANDOFF.md)。

该命令必须由仓库 `.venv` 的解释器启动。它先生成排除自身输出的 worktree fingerprint，
将**全部**旧 `SoftwareVerificationEvidence` 标记为未运行，再依次执行 Python/docs、
Rustfmt、Rust test、Clippy、desktop locked build 和 JavaScript 检查。所有登记协议，包括定向测试，
都必须直接执行才能恢复 `pass`，不得依赖手工声明的父门禁覆盖关系。

全部通过后才创建带 UTC 开始/结束时间的 `verificationRuns`，记录真实 Python 可执行路径、
已安装分发集合摘要、Python/Rust/Cargo/Node 版本、锁文件摘要和实际命令。验证前会拒绝与
`poetry.lock` 不一致的 `.venv`，并要求本次正式验证使用 workspace 锁定的精确
Rust 1.88.0 工具链。Windows/Linux 本地 MSRV 检查使用同一版本；本地较新
工具链不伪装成 MSRV 证明。任一命令
失败会清除当前成功标记，尚未执行的后续协议继续保持 `not_run_for_fingerprint`。

GateEvidence 的 `subjectCommit`/`subjectTree` 指向被验证提交；证据和 STATUS
只在后续 attestation 范围内发布。旧 Proposed policy v2/v3 model 中的远端
provenance 条款与当前用户要求不再一致，须另行评审本地证据替代合同；不得为
满足旧条款启动远端任务。现有生成器继续 fail closed，普通本地检查通过不能
签发 G0A pass，也不能把历史 v1/v2 pass 当作当前证据。

Unix 上 `.venv/bin/python` 常是软链接。启动子进程时保留 launcher 路径，
不能先 `resolve()` 到系统 Python，否则丢失 `pyvenv.cfg` 与锁定依赖环境。
preflight 同时检查 `.venv` prefix 与解释器目标，证据记录实际 launcher。
命令参数使用平台路径；证据中的历史 Windows protocol 文本不直接充当 Unix argv。

## 5. 单独运行

```powershell
.\.venv\Scripts\python.exe -I scripts/docs_check.py
.\.venv\Scripts\python.exe -I scripts\pytest_runner.py tests -q
.\.venv\Scripts\python.exe -m ruff check app ui tests main.py streamlit_app.py
.\.venv\Scripts\python.exe -m compileall -q app ui tests main.py streamlit_app.py
cargo +1.88.0 fmt --all --check
cargo +1.88.0 test --workspace --locked
cargo +1.88.0 clippy --workspace --all-targets --locked -- -D warnings
cargo +1.88.0 build -p telysta-desktop --locked
node --check apps/desktop/web/app.js
node --test apps/desktop/tests/app.test.cjs
node --check experiments/meaning-workbench/app.js
node --test experiments/meaning-workbench/app.test.cjs
```

2026-07-19 的 Windows 本地实现检查点中，精确 1.88.0 workspace tests 为
`62 passed`，fmt、Clippy `-D warnings`、desktop locked build 与 `node --check`
均通过。该记录不是当前 GateEvidence，也不关闭 R0A-08 或 G0A。
后续在本地 fresh checkout 复验精确版本；附加 stable 工具链只检查向前兼容，
不能替代 1.88.0 证明。不同操作系统的本地结果仍须分别记录，不从 Linux 推导 Windows。

本轮实际执行断点统一记录在 [WORK_LOG](./WORK_LOG.md)，不在多个文档复制
动态测试数量。可选浏览器自测及独立工具环境见
[作者流程原型说明](../experiments/meaning-workbench/README.md)。

## 6. 依赖管理

- `pyproject.toml` 是直接依赖和工具配置来源；
- `poetry.lock` 必须提交，用于锁定完整依赖图；
- 添加或升级依赖后必须重新运行一键检查；
- 本地锁定环境使用 Poetry 2.4.1，升级 Poetry 需要独立提交；
- 不在 `pyproject.toml` 中固定个人镜像源。需要镜像时使用本机 Poetry/pip 配置；
- 当前项目使用 Poetry application mode，不构建或安装根 Python 包。

更新锁文件：

```powershell
uvx --from poetry==2.4.1 poetry lock
uvx --from poetry==2.4.1 poetry sync --no-interaction
```

## 7. Python 支持策略

- 3.13 是旧引擎基线、研究桥接和迁移期对照的默认版本；
- 在本地分别验证最低版本 3.10、中间版本 3.12 和最高版本 3.14；
- Windows + Python 3.13 的本地结果单独记录，不用 Linux 代替；
- 新 Python 次版本先本地验证，再扩大 `requires-python` 范围；
- Python 3.10 使用已锁定的 `tomli` 开发依赖，3.11+ 使用标准库 `tomllib`。

## 8. 静态检查策略

当前 Ruff 只启用影响正确性的规则：语法错误、无效控制流和未定义名称。更广泛的导入排序、风格和格式统一将在清理阶段独立进行，避免一次产生大量与行为修改混杂的差异。

任何新增代码仍应保持一致格式；该限制不表示项目接受长期风格漂移。

## 9. 可选 LLM 的 API key 预留

仓库根目录 [`.env.example`](../.env.example) 为未来 Telysta Proposal Assistant
预留版本标记、provider/base URL/model 与空的 `TELYSTA_LLM_API_KEY`。
开发时可复制为 `.env.local`；该本地文件及其他 `.env.*` 已由 Git 忽略，只有
空值模板允许提交。不要把开发工具自身的登录凭据放进本项目。

这只是配置入口草案：当前 desktop 和 Python baseline **都不读取它**，复制或
填入 key 不会启用联网、切换 legacy backend 或增加后台 agent。默认
`TELYSTA_LLM_ENABLED=false`；没有配置 key 也不应阻碍未来离线生成、保存、语言
手册或基础试听。正式适配仍按 R7-LLM-01 的 Proposal Escrow 与 Rust 验证边界实施。

桌面产品的目标是通过 Rust 凭据服务保存到操作系统凭据库；项目文件、历史、
导出、日志和 webview 查询 DTO 只能持有非敏感配置/凭据引用，不能包含 key。
这沿用 ADR-004 的凭据原则与 ADR-006 的 Rust 权威，不引入当前未实现的
keyring 依赖或命令。网络调用须由用户明确启用和请求，具有限额、取消与超时；
不因存有 key 自动执行 agent 循环。

LLM 仅解析创作意图、提出待审方案或解释已验证结果。音系/语法编译、历史
归约、正确性判定和基础读音不依赖 LLM；提案不得直接提交状态或补造历史机制。
