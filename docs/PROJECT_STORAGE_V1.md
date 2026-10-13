---
document_type: contract
decision_status: accepted
implementation_status: partial
normative_scope: current
last_verified: 2026-10-12
implementation_schema: telysta-project-file.v1
implementation_path: crates/telysta-storage/src/lib.rs
implementation_constant: PROJECT_FILE_SCHEMA
---

# Project Storage v1

- Status: `Accepted contract / implementation reopened`
- Completed: 2026-07-14 (`FND-008`, `FND-008.1`)
- Implementation: `crates/telysta-storage`

> **2026-10-12 local repair candidate:** `R0A-09` now checks creation under
> the publication lease, requires conditional commits to extend the existing
> history without changing its context, revalidates migration archives and
> regenerated targets before clearing journals, and holds the project lease
> across authoritative loading, index publication and event queries. Published
> snapshots now return directly to the runtime; recovery preserves foreign
> primary bytes and rejects linked archives. New
> regression tests reproduced the prior failures and pass with the repair.
> Independent review and cross-platform terminal evidence remain pending;
> this does not close G0A or expose create/commit to Tauri.

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

Every `create_if_absent`, `save`, `save_if_current`, `load`, `event_index_entries`,
`migrate`, and `recover_migration` operation
holds an exclusive project write lease. The lease combines an OS-released file
lock (`project.write.lock`) with an in-process path registry, so two desktop
windows in one process and two separate processes cannot mutate a project at
the same time.

`save_if_current(history, expected_history_sha256)` is the normal UI save path:
the command rejects a stale editor when the project history changed after it
was loaded. It also requires an unchanged `RunContext` and an exact current event
prefix; replay validity alone does not authorize truncation or a fork. An
identical retry is allowed. The core owns this rule through
`ProjectHistory::validate_extension_of`; runtime checks its opened session and
storage independently checks the current disk history under the lease.

**Behavior change, 2026-10-12:** plain `save` retains its Rust signature but
now allows only initial creation or an exactly identical retry. An identical
retry does not rewrite authority or the recovery copy. Replacement, truncation,
forks and even valid extensions require `save_if_current` with an expected hash;
the prior unconditional replacement behavior is deliberately removed. Normal
writes refuse any pending migration journal until explicit recovery completes.
The session creation path uses `create_if_absent`.
Creation checks the primary file, recovery copy and pending migration journal
while holding the same lease used for publication, including dangling links.
The runtime receives a snapshot of its own publication before the lease is
released; it does not reacquire the lease for a second load after committing.

`load` holds the lease while reading authority and checking/rebuilding the
index. `event_index_entries` keeps it through the SQLite query. Contention
returns `WriteLocked`; it must not publish or return an unbound projection.

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
path explicitly. Even when the target is already published, recovery verifies the archive
bytes against its content-addressed name, the source schema, the registered
transformation, and the regenerated target history hash before clearing the
journal. An existing archive with different bytes is rejected, never reused
or overwritten. Missing/corrupt archives leave the journal available for
diagnosis and do not change the primary file.

Recovery may publish over the exact archived source bytes or a missing primary;
an already matching target may complete the journal. Any different existing
primary, including another valid legacy document or damaged bytes, is preserved
for explicit resolution. The migration directory must be a physical directory
and its archive a regular file; symlinks and Windows reparse points are rejected.
These checks assume writers honor the project lease, and do not claim resistance
to malicious filesystem changes outside that coordination boundary.

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

The R0A-09 regression matrix additionally covers simultaneous creators,
recovery/journal preservation, duplicate runtime identities before publication,
truncated/forked histories and changed run inputs, missing/tampered archives
before and after target publication, source/target/registry mismatches, and a
real subprocess contending for the project lease. Further regressions cover
foreign/damaged primary preservation, linked archives/directories on Unix,
publication-bound snapshots, session revision checks, pending migration write
rejection and the removal of unconditional replacement. Schemas, event identities,
RNG answers and semantic hashing are unchanged.
