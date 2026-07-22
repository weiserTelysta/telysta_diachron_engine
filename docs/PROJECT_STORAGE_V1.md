---
document_type: contract
decision_status: accepted
implementation_status: partial
normative_scope: current
last_verified: 2026-07-19
implementation_schema: telysta-project-file.v1
implementation_path: crates/telysta-storage/src/lib.rs
implementation_constant: PROJECT_FILE_SCHEMA
---

# Project Storage v1

- Status: `Accepted contract / implementation reopened`
- Completed: 2026-07-14 (`FND-008`, `FND-008.1`)
- Implementation: `crates/telysta-storage`

> **2026-07-19 implementation review:** the v1 schema and sole-authority
> decision remain accepted, but implementation closure is reopened. Project
> creation checks existence before taking the write lease, arbitrary
> replay-valid history can replace the current history, migration recovery can
> clear its journal without revalidating the source archive, and derived-index
> publication/query has an authority-token race. These are tracked by
> `R0A-09`; create/commit must not be exposed to Tauri until the repair matrix
> passes.

## Authority boundary

`project.json` is the sole authoritative project artifact. It has schema
`telysta-project-file.v1` and contains:

```text
schemaVersion
historySha256
history: telysta-project-history.v1
```

`historySha256` is the SHA-256 hash of canonical serialized `ProjectHistory`.
Loading replays the full history and verifies the checksum. A file is not a
project merely because it is parseable JSON.

`project.sqlite` is a derived query index. It contains only project/run
metadata and event sequence, ID, timestamp, and event hash. It is rebuilt when
absent, stale, unreadable, or structurally different from the authoritative
history; it never participates in deciding language state. Loading compares all
indexed event rows and metadata to the current history before reporting the
index as fresh.

## Write coordination

Every `save`, `save_if_current`, `migrate`, and `recover_migration` operation
holds an exclusive project write lease. The lease combines an OS-released file
lock (`project.write.lock`) with an in-process path registry, so two desktop
windows in one process and two separate processes cannot mutate a project at
the same time.

`save_if_current(history, expected_history_sha256)` is the normal UI save path:
the command rejects a stale editor when the project history changed after it
was loaded. Plain `save` remains available for creating a project or an
intentional unconditional replacement.

## Commit and recovery

1. The complete replacement JSON is written to a unique temporary file and
   synced before publication.
2. Before replacing a valid current project, that byte-exact file is written to
   `project.last-valid.json`.
3. The primary file is then replaced. On platforms without rename-overwrite
   semantics, the recovery file permits restoration if the replacement step is
   interrupted.
4. On load, a malformed or incomplete primary file falls back only to a fully
   validated `project.last-valid.json`. It never loads an unchecked temp file or
   a stale SQLite record.

On Unix, the parent directory is synced after staged replacement. Windows uses
the same staged and recovery semantics; the standard library does not expose a
portable parent-directory sync primitive there.

This is recovery semantics, not a claim that multiple unrelated files form one
filesystem transaction. The only authoritative commit unit is `project.json`;
the SQLite index is safely disposable.

## Versioning and migration

Normal `ProjectStore::load()` accepts only `telysta-project-file.v1`. Any other
top-level `schemaVersion` returns `MigrationRequired`; no normal loading path
guesses field meanings or silently upgrades data.

`ProjectStore::migrate()` receives a `ProjectMigrationRegistry`. A migrator is a
versioned deterministic transformation from one named source schema to the
current project-file schema. Before an upgrade is written, the source bytes are
archived under `migrations/<sha256>.source.json`.

Before publishing the migrated file, storage also writes
`migration.journal.json`, containing the source schema/archive and expected
target history hash. If publication is interrupted, `migrate()` resumes from
that journal automatically; `recover_migration()` exposes the same recovery
path explicitly. A completed target is verified before the journal is cleared.

The initial built-in migrator is intentionally explicit:

```rust
let registry = ProjectMigrationRegistry::with_legacy_history_v1();
store.migrate(&registry)?;
```

It wraps a replay-valid standalone `telysta-project-history.v1` document in the
new checksum-protected project envelope. Future history/schema changes require
their own migrator and regression fixture; they must not be hidden behind serde
defaults.

## Acceptance coverage

`cargo test -p telysta-storage --locked` covers:

- save/load replay and SQLite indexing;
- checksum tampering rejection;
- primary-file corruption recovery from a prior validated copy;
- explicit legacy-history migration with source archive;
- interrupted-migration journal recovery;
- safe rebuilding of a missing derived index.
- rebuilding an index whose rows were changed while metadata remained intact;
- write-lease contention, stale-history save rejection, and duplicate migration
  registration safety.
