---
document_type: contract
decision_status: accepted
implementation_status: implemented
normative_scope: current
last_verified: 2026-07-17
implementation_schema: telysta-project-session.v1
implementation_path: crates/telysta-storage/src/session.rs
implementation_constant: PROJECT_SESSION_SCHEMA
---

# Project Session and Desktop Commands v1

- 状态：`Implemented baseline / Remaining scope paused for R1`
- 起始日期：2026-07-14
- 工作包：`PLT-002.1`、`PLT-002.3`
- 实现：`crates/telysta-storage/src/session.rs`、`apps/desktop/src-tauri/src/main.rs`

## 1. 目的与边界

`ProjectSession` 是已打开正式项目的版本化、派生读模型。它服务于
Tauri 前端，但不进入 `project.json`，也不替代 `ProjectHistory`、
`LanguageState` 或 `StateTransaction` 的权威性。

它明确返回：项目/运行/语言 ID、规范化项目路径、history SHA-256、引擎与
seed、当前语言状态的分域语义 hash、语料统计、派生索引状态和恢复状态。
UI 不能据此直接改写 `LanguageState`。

## 2. 运行时不变量

1. `ProjectRuntime` 只能打开包含权威 `project.json` 的现有目录；
2. 同一进程内，规范化路径和项目 ID 都只能有一个活动会话；
3. 跨进程互斥仍由 `ProjectStore` 的文件 lease 负责；
4. `commit_history` 只接受完整、可 replay 的 `ProjectHistory`，并使用
   `save_if_current` 的 history SHA-256 进行乐观并发检查；
5. 不存在接受前端拼装 `LanguageState` 的写入命令；
6. `create_from_genesis` 仅接受恰含一个 `Genesis` 事件的历史，并且尚未
   暴露给 Tauri，直到 Genesis 编译器能够生成完整祖语状态。

## 3. v1 桌面命令

所有成功响应都由 `telysta-engine-api.v1` 的 `CommandResponse` 包装，实际
会话载荷有独立 schema `telysta-project-session.v1`。

| 命令 | 输入 | 输出 | 说明 |
|---|---|---|---|
| `open_project` | `projectRoot` | `ProjectSession` | 验证、加载并登记一个既有正式项目 |
| `get_project_session` | `projectId` | `ProjectSession` | 获取当前进程中已打开项目的派生读模型 |
| `refresh_project` | `projectId` | `ProjectSession` | 从权威文件重载并重新校验；v1 无内存脏状态 |
| `close_project` | `projectId` | `ProjectSession` | 注销本地会话，不删除或修改项目文件 |

错误通过结构化 `ProjectRuntimeError` 返回，至少区分：无效路径、项目缺失、
重复打开、项目 ID 冲突、未知会话、run/project 身份不匹配、陈旧写入和底层
存储错误。

## 4. 暂不暴露的命令

`create_project`、`commit_history` 和任意 state-edit 命令暂不对 UI 开放。
原因不是功能缺失，而是现阶段不存在能满足 `LanguageState` 硬约束的 Genesis
编译器。暴露一个“空项目”或让前端发送半成品语言状态，会重新引入已明确
禁止的假状态与双重真相。

`GEN-001.1` 已完成输入合同，但这不授权立即开放创建命令。创建路径只有在 G0B、
G1、相应 Accepted ADR 与 WS-1 Genesis 纵切闭合后，才能接受
`LanguageBlueprint v2` 并由 Rust application service 调用编译器和
`StateTransaction`。后续演化提交同样必须由应用服务持有 expected-history hash，
不得让 UI 组装完整 history。

## 5. 验证

当前存储层测试覆盖：有效项目打开/关闭、重复打开拒绝、会话摘要与 semantic
hash、完整 history 提交、陈旧 revision 冲突、非 Genesis 创建拒绝，以及既有
校验和、恢复、迁移、索引与写 lease 场景。

验证命令：

```powershell
cargo fmt --all --check
cargo test -p telysta-storage --locked
cargo test -p telysta-desktop --locked
cargo clippy --workspace --locked -- -D warnings
```

## 6. 已知限制和路线交接

- 前端当前使用路径输入；文件夹选择器在明确权限模型后接入；
- 项目工作区仅展示结构化会话摘要，不显示完整语言状态；
- Demo checkpoint 仍是技术 Spike，不能作为项目存储或项目恢复；
- `LanguageBlueprint v2` 合同已完成，但内置 feature capability 仍为 `planned`；当前先并行关闭 G0A/G0B，再由 R1 和 WS-1 为 `ProjectRuntime::create_from_genesis` 建立 application、Genesis 与音系/语法纵切；
- `SpeechCommunity` 不再是本合同之后的直接 Next，它属于 G3B 关闭后的 WS-2；
- `PLT-002.2/002.4/002.5` 的路径选择权限、命令级端到端测试和 Demo 清退归入 R1，不得绕过其 Job/API/staging 合同单独扩展桌面命令。
