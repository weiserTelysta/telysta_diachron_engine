//! Durable project storage for the Telysta language simulator.
//!
//! `project.json` is the only authoritative on-disk representation. It wraps a
//! validated [`ProjectHistory`] with a checksum of its canonical JSON. The
//! SQLite file is deliberately derived: it accelerates event queries, but is
//! rebuilt whenever it is absent, corrupt, or stale. This prevents a partial
//! index write from becoming a second source of project truth.

pub mod session;

pub use session::{
    ProjectRuntime, ProjectRuntimeError, ProjectSession, ProjectSessionIndexStatus,
    ProjectSessionStatus, ProjectSessionSummary, PROJECT_SESSION_SCHEMA,
};

use std::{
    collections::{BTreeMap, BTreeSet},
    fmt,
    fs::{self, File, OpenOptions},
    io::Write,
    path::{Path, PathBuf},
    process,
    sync::{
        atomic::{AtomicU64, Ordering},
        Mutex, OnceLock,
    },
    time::{SystemTime, UNIX_EPOCH},
};

use fs2::FileExt;
use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Deserializer, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use telysta_core::project::{ProjectHistory, PROJECT_HISTORY_SCHEMA};

pub const PROJECT_FILE_SCHEMA: &str = "telysta-project-file.v1";
pub const PROJECT_INDEX_SCHEMA: &str = "telysta-project-index.v1";
pub const PROJECT_FILE_NAME: &str = "project.json";
pub const PROJECT_RECOVERY_FILE_NAME: &str = "project.last-valid.json";
pub const PROJECT_INDEX_FILE_NAME: &str = "project.sqlite";
pub const PROJECT_MIGRATION_DIR_NAME: &str = "migrations";
pub const PROJECT_WRITE_LOCK_FILE_NAME: &str = "project.write.lock";
pub const PROJECT_MIGRATION_JOURNAL_FILE_NAME: &str = "migration.journal.json";
pub const PROJECT_MIGRATION_JOURNAL_SCHEMA: &str = "telysta-project-migration-journal.v1";

static TEMPORARY_FILE_COUNTER: AtomicU64 = AtomicU64::new(0);
static PROCESS_WRITE_LEASES: OnceLock<Mutex<BTreeSet<PathBuf>>> = OnceLock::new();

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ProjectStorageError {
    Io {
        operation: String,
        path: PathBuf,
        message: String,
    },
    Serialization(String),
    Validation(String),
    MigrationRequired {
        found_schema: String,
        expected_schema: &'static str,
    },
    Migration(String),
    Index(String),
    WriteLocked {
        path: PathBuf,
    },
    WriteConflict {
        expected_history_sha256: String,
        actual_history_sha256: Option<String>,
    },
}

impl fmt::Display for ProjectStorageError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io {
                operation,
                path,
                message,
            } => write!(formatter, "cannot {operation} {}: {message}", path.display()),
            Self::Serialization(message) => write!(formatter, "invalid project JSON: {message}"),
            Self::Validation(message) => write!(formatter, "invalid project storage: {message}"),
            Self::MigrationRequired {
                found_schema,
                expected_schema,
            } => write!(
                formatter,
                "project format {found_schema:?} requires an explicit migration before it can be read as {expected_schema:?}"
            ),
            Self::Migration(message) => write!(formatter, "project migration failed: {message}"),
            Self::Index(message) => write!(formatter, "project index failed: {message}"),
            Self::WriteLocked { path } => write!(
                formatter,
                "project is already being modified by another process: {}",
                path.display()
            ),
            Self::WriteConflict {
                expected_history_sha256,
                actual_history_sha256,
            } => write!(
                formatter,
                "project changed before save: expected history SHA-256 {expected_history_sha256}, found {}",
                actual_history_sha256.as_deref().unwrap_or("no current project")
            ),
        }
    }
}

impl std::error::Error for ProjectStorageError {}

/// A checksum-protected file envelope. The nested history still carries its
/// own schema and replay validation; this outer version is the persistence
/// contract and changes when the file layout changes.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectFile {
    schema_version: String,
    history_sha256: String,
    history: ProjectHistory,
}

impl ProjectFile {
    pub fn new(history: ProjectHistory) -> Result<Self, ProjectStorageError> {
        let history_sha256 = canonical_history_sha256(&history)?;
        Ok(Self {
            schema_version: PROJECT_FILE_SCHEMA.to_owned(),
            history_sha256,
            history,
        })
    }

    pub fn schema_version(&self) -> &str {
        &self.schema_version
    }

    pub fn history_sha256(&self) -> &str {
        &self.history_sha256
    }

    pub fn history(&self) -> &ProjectHistory {
        &self.history
    }

    fn from_parts(
        schema_version: String,
        history_sha256: String,
        history: ProjectHistory,
    ) -> Result<Self, ProjectStorageError> {
        if schema_version != PROJECT_FILE_SCHEMA {
            return Err(ProjectStorageError::MigrationRequired {
                found_schema: schema_version,
                expected_schema: PROJECT_FILE_SCHEMA,
            });
        }
        ensure_sha256(&history_sha256, "project history SHA-256")?;
        let actual_sha256 = canonical_history_sha256(&history)?;
        if history_sha256 != actual_sha256 {
            return Err(ProjectStorageError::Validation(format!(
                "historySha256 {history_sha256} does not match canonical history digest {actual_sha256}"
            )));
        }
        Ok(Self {
            schema_version,
            history_sha256,
            history,
        })
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RawProjectFile {
    schema_version: String,
    history_sha256: String,
    history: ProjectHistory,
}

impl<'de> Deserialize<'de> for ProjectFile {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let raw = RawProjectFile::deserialize(deserializer)?;
        Self::from_parts(raw.schema_version, raw.history_sha256, raw.history)
            .map_err(serde::de::Error::custom)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum IndexStatus {
    Fresh,
    Rebuilt,
    Deferred { reason: String },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SaveOutcome {
    pub history_sha256: String,
    pub index_status: IndexStatus,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LoadedProject {
    pub history: ProjectHistory,
    pub history_sha256: String,
    pub index_status: IndexStatus,
    pub recovered_from_last_valid: bool,
}

impl LoadedProject {
    fn into_save_outcome(self) -> SaveOutcome {
        SaveOutcome {
            history_sha256: self.history_sha256,
            index_status: self.index_status,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EventIndexEntry {
    pub sequence: u64,
    pub event_id: String,
    pub occurred_at_year: i32,
    pub event_sha256: String,
}

/// A deterministic migration function. Migrations receive the raw JSON
/// document, rather than a partially deserialized project, so callers cannot
/// accidentally make normal loading infer an old format.
#[derive(Clone)]
pub struct ProjectMigration {
    source_schema: &'static str,
    target_schema: &'static str,
    transform: fn(Value) -> Result<ProjectFile, ProjectStorageError>,
}

impl ProjectMigration {
    pub const fn new(
        source_schema: &'static str,
        target_schema: &'static str,
        transform: fn(Value) -> Result<ProjectFile, ProjectStorageError>,
    ) -> Self {
        Self {
            source_schema,
            target_schema,
            transform,
        }
    }

    pub const fn source_schema(&self) -> &'static str {
        self.source_schema
    }

    pub const fn target_schema(&self) -> &'static str {
        self.target_schema
    }

    /// Wrap a validated pre-FND-008 `ProjectHistory` JSON document in the
    /// FND-008 envelope. This is intentionally opt-in through `migrate`.
    pub const fn legacy_history_v1() -> Self {
        Self::new(
            PROJECT_HISTORY_SCHEMA,
            PROJECT_FILE_SCHEMA,
            migrate_legacy_history_v1_document,
        )
    }
}

#[derive(Default)]
pub struct ProjectMigrationRegistry {
    migrations: BTreeMap<&'static str, ProjectMigration>,
}

impl ProjectMigrationRegistry {
    pub fn with_legacy_history_v1() -> Self {
        let mut registry = Self::default();
        registry
            .register(ProjectMigration::legacy_history_v1())
            .expect("built-in migration schemas are valid and unique");
        registry
    }

    pub fn register(&mut self, migration: ProjectMigration) -> Result<(), ProjectStorageError> {
        if migration.source_schema.trim().is_empty() || migration.target_schema.trim().is_empty() {
            return Err(ProjectStorageError::Migration(
                "migration source and target schemas must not be blank".to_owned(),
            ));
        }
        if migration.target_schema != PROJECT_FILE_SCHEMA {
            return Err(ProjectStorageError::Migration(format!(
                "migration target {:?} is not the current project-file schema {PROJECT_FILE_SCHEMA:?}",
                migration.target_schema
            )));
        }
        if self.migrations.contains_key(migration.source_schema) {
            return Err(ProjectStorageError::Migration(
                "migration registry contains duplicate source schemas".to_owned(),
            ));
        }
        self.migrations.insert(migration.source_schema, migration);
        Ok(())
    }

    fn find(&self, source_schema: &str) -> Option<&ProjectMigration> {
        self.migrations.get(source_schema)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MigrationOutcome {
    pub project: LoadedProject,
    pub source_schema: String,
    pub source_archive: Option<PathBuf>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct MigrationJournal {
    schema_version: String,
    source_schema: String,
    source_archive_file: String,
    target_history_sha256: String,
}

impl MigrationJournal {
    fn new(
        source_schema: String,
        source_archive_file: String,
        target_history_sha256: String,
    ) -> Result<Self, ProjectStorageError> {
        if source_schema.trim().is_empty() {
            return Err(ProjectStorageError::Migration(
                "migration journal source schema must not be blank".to_owned(),
            ));
        }
        if source_archive_file.trim().is_empty()
            || Path::new(&source_archive_file).file_name().is_none()
            || Path::new(&source_archive_file).components().count() != 1
        {
            return Err(ProjectStorageError::Migration(
                "migration journal source archive must be a single file name".to_owned(),
            ));
        }
        ensure_sha256(
            &target_history_sha256,
            "migration journal target history SHA-256",
        )?;
        Ok(Self {
            schema_version: PROJECT_MIGRATION_JOURNAL_SCHEMA.to_owned(),
            source_schema,
            source_archive_file,
            target_history_sha256,
        })
    }

    fn validate(&self) -> Result<(), ProjectStorageError> {
        if self.schema_version != PROJECT_MIGRATION_JOURNAL_SCHEMA {
            return Err(ProjectStorageError::Migration(format!(
                "unsupported migration-journal schema {:?}",
                self.schema_version
            )));
        }
        Self::new(
            self.source_schema.clone(),
            self.source_archive_file.clone(),
            self.target_history_sha256.clone(),
        )
        .map(|_| ())
    }
}

struct ProjectWriteLease {
    file: File,
    path: PathBuf,
}

impl Drop for ProjectWriteLease {
    fn drop(&mut self) {
        let _ = FileExt::unlock(&self.file);
        if let Some(leases) = PROCESS_WRITE_LEASES.get() {
            if let Ok(mut leases) = leases.lock() {
                leases.remove(&self.path);
            }
        }
    }
}

/// A project directory. Paths are fixed by the storage format; the caller only
/// selects the directory that owns the project.
#[derive(Debug, Clone)]
pub struct ProjectStore {
    root: PathBuf,
}

impl ProjectStore {
    pub fn open(root: impl Into<PathBuf>) -> Result<Self, ProjectStorageError> {
        let root = root.into();
        if root.as_os_str().is_empty() {
            return Err(ProjectStorageError::Validation(
                "project root must not be empty".to_owned(),
            ));
        }
        fs::create_dir_all(&root)
            .map_err(|error| io_error("create project directory", &root, error))?;
        Ok(Self { root })
    }

    pub fn root(&self) -> &Path {
        &self.root
    }

    pub fn project_path(&self) -> PathBuf {
        self.root.join(PROJECT_FILE_NAME)
    }

    pub fn recovery_path(&self) -> PathBuf {
        self.root.join(PROJECT_RECOVERY_FILE_NAME)
    }

    pub fn index_path(&self) -> PathBuf {
        self.root.join(PROJECT_INDEX_FILE_NAME)
    }

    pub fn migration_directory(&self) -> PathBuf {
        self.root.join(PROJECT_MIGRATION_DIR_NAME)
    }

    pub fn write_lock_path(&self) -> PathBuf {
        self.root.join(PROJECT_WRITE_LOCK_FILE_NAME)
    }

    pub fn migration_journal_path(&self) -> PathBuf {
        self.root.join(PROJECT_MIGRATION_JOURNAL_FILE_NAME)
    }

    fn acquire_write_lease(&self) -> Result<ProjectWriteLease, ProjectStorageError> {
        fs::create_dir_all(&self.root)
            .map_err(|error| io_error("create project directory", &self.root, error))?;
        let path = self.write_lock_path();
        let process_leases = PROCESS_WRITE_LEASES.get_or_init(|| Mutex::new(BTreeSet::new()));
        {
            let mut process_leases = process_leases.lock().map_err(|_| {
                ProjectStorageError::Validation("project write-lease mutex is poisoned".to_owned())
            })?;
            if !process_leases.insert(path.clone()) {
                return Err(ProjectStorageError::WriteLocked { path });
            }
        }
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(&path)
            .map_err(|error| {
                release_process_write_lease(&path);
                io_error("open project write lease", &path, error)
            })?;
        match FileExt::try_lock_exclusive(&file) {
            Ok(()) => Ok(ProjectWriteLease { file, path }),
            Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                release_process_write_lease(&path);
                Err(ProjectStorageError::WriteLocked { path })
            }
            Err(error) => {
                release_process_write_lease(&path);
                Err(io_error("acquire project write lease", &path, error))
            }
        }
    }

    /// Initialize a project or acknowledge an exact retry without rewriting it.
    /// Existing histories can change only through `save_if_current`.
    pub fn save(&self, history: ProjectHistory) -> Result<SaveOutcome, ProjectStorageError> {
        let _lease = self.acquire_write_lease()?;
        self.ensure_no_pending_migration()?;
        if path_metadata(&self.project_path())?.is_none() {
            return self
                .create_snapshot_unlocked(history)
                .map(LoadedProject::into_save_outcome);
        }
        let current = self.read_project_file(&self.project_path())?;
        if current.history() != &history {
            return Err(ProjectStorageError::Validation(
                "save without an expected hash cannot replace or extend an existing project; use save_if_current"
                    .to_owned(),
            ));
        }
        self.load_unlocked().map(LoadedProject::into_save_outcome)
    }

    /// Create under the same lease as publication, preserving recovery and
    /// migration artifacts if a project has already occupied this directory.
    pub fn create_if_absent(
        &self,
        history: ProjectHistory,
    ) -> Result<SaveOutcome, ProjectStorageError> {
        self.create_with_snapshot(history)
            .map(LoadedProject::into_save_outcome)
    }

    // Bind the runtime result to this publication while the lease is held.
    // Reacquiring a lease to load afterwards can fail after a successful write,
    // or observe a later writer's history instead of the caller's commit.
    pub(crate) fn create_with_snapshot(
        &self,
        history: ProjectHistory,
    ) -> Result<LoadedProject, ProjectStorageError> {
        let _lease = self.acquire_write_lease()?;
        self.create_snapshot_unlocked(history)
    }

    fn create_snapshot_unlocked(
        &self,
        history: ProjectHistory,
    ) -> Result<LoadedProject, ProjectStorageError> {
        for path in [
            self.project_path(),
            self.recovery_path(),
            self.migration_journal_path(),
        ] {
            if path_metadata(&path)?.is_some() {
                return Err(ProjectStorageError::Validation(format!(
                    "refusing to create a project over existing {}",
                    path.display()
                )));
            }
        }
        self.save_snapshot_unlocked(history, None)
    }

    /// Save only when the caller still holds the history revision it loaded.
    /// This is the optimistic-concurrency companion to the cross-process write
    /// lease used by every mutation entry point.
    pub fn save_if_current(
        &self,
        history: ProjectHistory,
        expected_history_sha256: &str,
    ) -> Result<SaveOutcome, ProjectStorageError> {
        self.save_if_current_with_snapshot(history, expected_history_sha256)
            .map(LoadedProject::into_save_outcome)
    }

    pub(crate) fn save_if_current_with_snapshot(
        &self,
        history: ProjectHistory,
        expected_history_sha256: &str,
    ) -> Result<LoadedProject, ProjectStorageError> {
        ensure_sha256(expected_history_sha256, "expected history SHA-256")?;
        let _lease = self.acquire_write_lease()?;
        self.save_snapshot_unlocked(history, Some(expected_history_sha256))
    }

    fn save_snapshot_unlocked(
        &self,
        history: ProjectHistory,
        expected_history_sha256: Option<&str>,
    ) -> Result<LoadedProject, ProjectStorageError> {
        self.ensure_no_pending_migration()?;
        if let Some(expected) = expected_history_sha256 {
            let project_path = self.project_path();
            let current = if project_path
                .try_exists()
                .map_err(|error| io_error("check current project", &project_path, error))?
            {
                Some(self.read_project_file(&project_path)?)
            } else {
                None
            };
            if current.as_ref().map(ProjectFile::history_sha256) != Some(expected) {
                return Err(ProjectStorageError::WriteConflict {
                    expected_history_sha256: expected.to_owned(),
                    actual_history_sha256: current.map(|file| file.history_sha256),
                });
            }
            let current = current.expect("matching history hash requires a current file");
            history
                .validate_extension_of(current.history())
                .map_err(|error| ProjectStorageError::Validation(error.to_string()))?;
        }
        let file = ProjectFile::new(history)?;
        let saved = self.write_project_file(&file, true)?;
        Ok(LoadedProject {
            history: file.history,
            history_sha256: saved.history_sha256,
            index_status: saved.index_status,
            recovered_from_last_valid: false,
        })
    }

    fn ensure_no_pending_migration(&self) -> Result<(), ProjectStorageError> {
        if path_metadata(&self.migration_journal_path())?.is_some() {
            return Err(ProjectStorageError::Migration(
                "a pending migration must be explicitly recovered before normal writes".to_owned(),
            ));
        }
        Ok(())
    }

    /// Load the authoritative file. A recovery copy is considered only when
    /// the primary file is corrupt or incomplete; an old schema is never
    /// silently treated as corruption or guessed into the current format.
    pub fn load(&self) -> Result<LoadedProject, ProjectStorageError> {
        let _lease = self.acquire_write_lease()?;
        self.load_unlocked()
    }

    // The lease must cover authoritative loading and derived-index publication.
    // Mutation paths already holding it use this helper to avoid re-entry.
    fn load_unlocked(&self) -> Result<LoadedProject, ProjectStorageError> {
        let (file, recovered_from_last_valid) = self.load_authoritative_file()?;
        let index_status = match self.index_is_current(&file) {
            Ok(true) => IndexStatus::Fresh,
            Ok(false) | Err(_) => match self.rebuild_index(&file) {
                Ok(()) => IndexStatus::Rebuilt,
                Err(error) => IndexStatus::Deferred {
                    reason: error.to_string(),
                },
            },
        };
        Ok(LoadedProject {
            history: file.history,
            history_sha256: file.history_sha256,
            index_status,
            recovered_from_last_valid,
        })
    }

    /// Explicitly migrate the document currently stored at `project.json`.
    /// The source bytes are archived before the upgraded file is committed.
    pub fn migrate(
        &self,
        registry: &ProjectMigrationRegistry,
    ) -> Result<MigrationOutcome, ProjectStorageError> {
        let _lease = self.acquire_write_lease()?;
        self.migrate_unlocked(registry)
    }

    /// Resume a migration that was interrupted after its source archive and
    /// journal were committed. No source format is ever guessed during this
    /// recovery; the same explicit registry is still required.
    pub fn recover_migration(
        &self,
        registry: &ProjectMigrationRegistry,
    ) -> Result<Option<MigrationOutcome>, ProjectStorageError> {
        let _lease = self.acquire_write_lease()?;
        if !self.migration_journal_path().exists() {
            return Ok(None);
        }
        self.migrate_unlocked(registry).map(Some)
    }

    fn migrate_unlocked(
        &self,
        registry: &ProjectMigrationRegistry,
    ) -> Result<MigrationOutcome, ProjectStorageError> {
        if let Some(journal) = self.read_migration_journal()? {
            let archive = self
                .migration_directory()
                .join(&journal.source_archive_file);
            self.validate_archive_path(&archive)?;
            let bytes = fs::read(&archive).map_err(|error| {
                io_error("read pending migration source archive", &archive, error)
            })?;
            self.validate_pending_migration(registry, &bytes, &journal)?;
            match self.read_project_file(&self.project_path()) {
                Ok(file) if file.history_sha256() == journal.target_history_sha256 => {
                    self.clear_migration_journal()?;
                    return Ok(MigrationOutcome {
                        project: self.load_unlocked()?,
                        source_schema: journal.source_schema,
                        source_archive: Some(
                            self.migration_directory().join(journal.source_archive_file),
                        ),
                    });
                }
                Ok(file) => {
                    return Err(ProjectStorageError::Migration(format!(
                        "pending migration targets {}, but current project has history SHA-256 {}",
                        journal.target_history_sha256,
                        file.history_sha256()
                    )));
                }
                Err(_) => {
                    // Only the exact archived source or an absent publication
                    // belongs to this interrupted migration. Another legacy
                    // document, unknown schema or damaged file is user data.
                    let path = self.project_path();
                    if path_metadata(&path)?.is_some() {
                        let primary = fs::read(&path).map_err(|error| {
                            io_error("check pending migration primary", &path, error)
                        })?;
                        if primary != bytes {
                            return Err(ProjectStorageError::Migration(
                                "current project differs from the pending migration source; preserving both for explicit resolution"
                                    .to_owned(),
                            ));
                        }
                    }
                    return self.migrate_source_bytes(registry, bytes, Some(journal));
                }
            }
        }

        let path = self.project_path();
        let bytes = fs::read(&path)
            .map_err(|error| io_error("read project for migration", &path, error))?;
        self.migrate_source_bytes(registry, bytes, None)
    }

    fn validate_pending_migration(
        &self,
        registry: &ProjectMigrationRegistry,
        bytes: &[u8],
        journal: &MigrationJournal,
    ) -> Result<(), ProjectStorageError> {
        if journal.source_archive_file != format!("{}.source.json", sha256_hex(bytes)) {
            return Err(ProjectStorageError::Migration(
                "migration source archive does not match its content-addressed name".to_owned(),
            ));
        }
        let document: Value = serde_json::from_slice(bytes)
            .map_err(|error| ProjectStorageError::Migration(error.to_string()))?;
        let schema = document_schema(&document)?;
        if schema != journal.source_schema {
            return Err(ProjectStorageError::Migration(
                "migration journal source schema does not match archived source".to_owned(),
            ));
        }
        let migration = registry
            .find(&schema)
            .ok_or(ProjectStorageError::MigrationRequired {
                found_schema: schema,
                expected_schema: PROJECT_FILE_SCHEMA,
            })?;
        let regenerated = (migration.transform)(document)?;
        if migration.target_schema != regenerated.schema_version()
            || regenerated.history_sha256() != journal.target_history_sha256
        {
            return Err(ProjectStorageError::Migration(
                "archived source does not regenerate the journal's target".to_owned(),
            ));
        }
        Ok(())
    }

    fn migrate_source_bytes(
        &self,
        registry: &ProjectMigrationRegistry,
        bytes: Vec<u8>,
        pending_journal: Option<MigrationJournal>,
    ) -> Result<MigrationOutcome, ProjectStorageError> {
        let document: Value = serde_json::from_slice(&bytes)
            .map_err(|error| ProjectStorageError::Serialization(error.to_string()))?;
        let source_schema = document_schema(&document)?;

        if source_schema == PROJECT_FILE_SCHEMA {
            return Ok(MigrationOutcome {
                project: self.load_unlocked()?,
                source_schema,
                source_archive: None,
            });
        }

        let migration = registry.find(&source_schema).ok_or_else(|| {
            ProjectStorageError::MigrationRequired {
                found_schema: source_schema.clone(),
                expected_schema: PROJECT_FILE_SCHEMA,
            }
        })?;
        let migrated = (migration.transform)(document)?;
        if migration.target_schema != migrated.schema_version() {
            return Err(ProjectStorageError::Migration(format!(
                "migration declared target {:?}, but produced {:?}",
                migration.target_schema,
                migrated.schema_version()
            )));
        }

        let archive = if let Some(journal) = pending_journal {
            if journal.source_schema != source_schema {
                return Err(ProjectStorageError::Migration(format!(
                    "migration journal source schema {:?} does not match archived source {:?}",
                    journal.source_schema, source_schema
                )));
            }
            if journal.target_history_sha256 != migrated.history_sha256() {
                return Err(ProjectStorageError::Migration(format!(
                    "migration journal target SHA-256 {} does not match regenerated target {}",
                    journal.target_history_sha256,
                    migrated.history_sha256()
                )));
            }
            self.migration_directory().join(journal.source_archive_file)
        } else {
            let archive = self.archive_migration_source(&bytes)?;
            let source_archive_file = archive
                .file_name()
                .and_then(|name| name.to_str())
                .ok_or_else(|| {
                    ProjectStorageError::Migration(
                        "migration archive file name is not valid UTF-8".to_owned(),
                    )
                })?
                .to_owned();
            let journal = MigrationJournal::new(
                source_schema.clone(),
                source_archive_file,
                migrated.history_sha256().to_owned(),
            )?;
            self.write_migration_journal(&journal)?;
            archive
        };
        self.write_project_file(&migrated, false)?;
        self.clear_migration_journal()?;
        Ok(MigrationOutcome {
            project: self.load_unlocked()?,
            source_schema,
            source_archive: Some(archive),
        })
    }

    /// Return the SQLite event index after ensuring it corresponds to the
    /// authoritative history. Consumers never query a stale index.
    pub fn event_index_entries(&self) -> Result<Vec<EventIndexEntry>, ProjectStorageError> {
        let _lease = self.acquire_write_lease()?;
        let loaded = self.load_unlocked()?;
        if let IndexStatus::Deferred { reason } = loaded.index_status {
            return Err(ProjectStorageError::Index(reason));
        }
        let path = self.index_path();
        let connection = Connection::open(&path)
            .map_err(|error| sqlite_error("open event index", &path, error))?;
        let mut statement = connection
            .prepare(
                "SELECT sequence, event_id, occurred_at_year, event_sha256 \
                 FROM project_events ORDER BY sequence ASC",
            )
            .map_err(|error| sqlite_error("prepare event-index query", &path, error))?;
        let rows = statement
            .query_map([], |row| {
                Ok(EventIndexEntry {
                    sequence: row.get(0)?,
                    event_id: row.get(1)?,
                    occurred_at_year: row.get(2)?,
                    event_sha256: row.get(3)?,
                })
            })
            .map_err(|error| sqlite_error("query event index", &path, error))?;
        rows.collect::<Result<Vec<_>, _>>()
            .map_err(|error| sqlite_error("read event index", &path, error))
    }

    fn load_authoritative_file(&self) -> Result<(ProjectFile, bool), ProjectStorageError> {
        let primary = self.project_path();
        match self.read_project_file(&primary) {
            Ok(file) => Ok((file, false)),
            Err(error @ ProjectStorageError::MigrationRequired { .. }) => Err(error),
            Err(primary_error) => {
                let recovery = self.recovery_path();
                if !recovery.exists() {
                    return Err(primary_error);
                }
                self.read_project_file(&recovery).map(|file| (file, true)).map_err(|recovery_error| {
                    ProjectStorageError::Validation(format!(
                        "primary project could not be read ({primary_error}); recovery copy could not be read ({recovery_error})"
                    ))
                })
            }
        }
    }

    fn read_project_file(&self, path: &Path) -> Result<ProjectFile, ProjectStorageError> {
        let bytes = fs::read(path).map_err(|error| io_error("read project", path, error))?;
        let document: Value = serde_json::from_slice(&bytes)
            .map_err(|error| ProjectStorageError::Serialization(error.to_string()))?;
        let schema = document_schema(&document)?;
        if schema != PROJECT_FILE_SCHEMA {
            return Err(ProjectStorageError::MigrationRequired {
                found_schema: schema,
                expected_schema: PROJECT_FILE_SCHEMA,
            });
        }
        serde_json::from_value(document)
            .map_err(|error| ProjectStorageError::Validation(error.to_string()))
    }

    fn write_project_file(
        &self,
        file: &ProjectFile,
        retain_previous: bool,
    ) -> Result<SaveOutcome, ProjectStorageError> {
        fs::create_dir_all(&self.root)
            .map_err(|error| io_error("create project directory", &self.root, error))?;
        let bytes = serde_json::to_vec_pretty(file)
            .map_err(|error| ProjectStorageError::Serialization(error.to_string()))?;
        let project_path = self.project_path();
        let recovery_path = self.recovery_path();
        if retain_previous && project_path.exists() && self.read_project_file(&project_path).is_ok()
        {
            let previous = fs::read(&project_path)
                .map_err(|error| io_error("read prior project", &project_path, error))?;
            write_replaceable_file(&recovery_path, &previous, None)?;
        }
        write_replaceable_file(
            &project_path,
            &bytes,
            if retain_previous && recovery_path.exists() {
                Some(recovery_path)
            } else {
                None
            },
        )?;

        let index_status = match self.rebuild_index(file) {
            Ok(()) => IndexStatus::Rebuilt,
            Err(error) => IndexStatus::Deferred {
                reason: error.to_string(),
            },
        };
        Ok(SaveOutcome {
            history_sha256: file.history_sha256.clone(),
            index_status,
        })
    }

    fn archive_migration_source(&self, bytes: &[u8]) -> Result<PathBuf, ProjectStorageError> {
        let directory = self.migration_directory();
        fs::create_dir_all(&directory)
            .map_err(|error| io_error("create migration archive directory", &directory, error))?;
        let path = directory.join(format!("{}.source.json", sha256_hex(bytes)));
        self.validate_archive_path(&path)?;
        if path_metadata(&path)?.is_none() {
            write_replaceable_file(&path, bytes, None)?;
        }
        let archived = fs::read(&path)
            .map_err(|error| io_error("verify migration source archive", &path, error))?;
        if archived != bytes {
            return Err(ProjectStorageError::Migration(
                "existing source archive does not match the migration input".to_owned(),
            ));
        }
        Ok(path)
    }

    fn validate_archive_path(&self, path: &Path) -> Result<(), ProjectStorageError> {
        let directory = self.migration_directory();
        let metadata = fs::symlink_metadata(&directory)
            .map_err(|error| io_error("inspect migration directory", &directory, error))?;
        if is_link_or_reparse_point(&metadata) || !metadata.is_dir() {
            return Err(ProjectStorageError::Migration(
                "migration directory must be a physical project-local directory".to_owned(),
            ));
        }
        if path.parent() != Some(directory.as_path()) {
            return Err(ProjectStorageError::Migration(
                "migration archive must be inside the migration directory".to_owned(),
            ));
        }
        if let Some(metadata) = path_metadata(path)? {
            if is_link_or_reparse_point(&metadata) || !metadata.is_file() {
                return Err(ProjectStorageError::Migration(
                    "migration archive must be a regular file, never a link or reparse point"
                        .to_owned(),
                ));
            }
        }
        Ok(())
    }

    fn read_migration_journal(&self) -> Result<Option<MigrationJournal>, ProjectStorageError> {
        let path = self.migration_journal_path();
        if !path.exists() {
            return Ok(None);
        }
        let bytes =
            fs::read(&path).map_err(|error| io_error("read migration journal", &path, error))?;
        let journal: MigrationJournal = serde_json::from_slice(&bytes)
            .map_err(|error| ProjectStorageError::Migration(error.to_string()))?;
        journal.validate()?;
        Ok(Some(journal))
    }

    fn write_migration_journal(
        &self,
        journal: &MigrationJournal,
    ) -> Result<(), ProjectStorageError> {
        journal.validate()?;
        let path = self.migration_journal_path();
        let bytes = serde_json::to_vec_pretty(journal)
            .map_err(|error| ProjectStorageError::Serialization(error.to_string()))?;
        write_replaceable_file(&path, &bytes, None)
    }

    fn clear_migration_journal(&self) -> Result<(), ProjectStorageError> {
        let path = self.migration_journal_path();
        if path.exists() {
            fs::remove_file(&path)
                .map_err(|error| io_error("clear migration journal", &path, error))?;
            sync_parent_directory(&path)?;
        }
        Ok(())
    }

    fn index_is_current(&self, file: &ProjectFile) -> Result<bool, ProjectStorageError> {
        let path = self.index_path();
        if !path.exists() {
            return Ok(false);
        }
        let connection = Connection::open(&path)
            .map_err(|error| sqlite_error("open event index", &path, error))?;
        let project_id = file.history().context().project_id().to_string();
        let run_id = file.history().context().run_id().to_string();
        let metadata = [
            ("index_schema", PROJECT_INDEX_SCHEMA),
            ("project_file_schema", PROJECT_FILE_SCHEMA),
            ("project_history_schema", PROJECT_HISTORY_SCHEMA),
            ("history_sha256", file.history_sha256()),
            ("project_id", project_id.as_str()),
            ("run_id", run_id.as_str()),
        ];
        for (key, expected) in metadata {
            let actual = connection
                .query_row(
                    "SELECT value FROM project_metadata WHERE key = ?1",
                    params![key],
                    |row| row.get::<_, String>(0),
                )
                .optional()
                .map_err(|error| sqlite_error("read event-index metadata", &path, error))?;
            if actual.as_deref() != Some(expected) {
                return Ok(false);
            }
        }

        let expected_entries = expected_event_index_entries(file)?;
        let mut statement = connection
            .prepare(
                "SELECT sequence, event_id, occurred_at_year, event_sha256 \
                 FROM project_events ORDER BY sequence ASC",
            )
            .map_err(|error| sqlite_error("prepare event-index validation", &path, error))?;
        let actual_entries = statement
            .query_map([], |row| {
                Ok(EventIndexEntry {
                    sequence: row.get(0)?,
                    event_id: row.get(1)?,
                    occurred_at_year: row.get(2)?,
                    event_sha256: row.get(3)?,
                })
            })
            .map_err(|error| sqlite_error("query event-index validation", &path, error))?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|error| sqlite_error("read event-index validation", &path, error))?;
        Ok(actual_entries == expected_entries)
    }

    fn rebuild_index(&self, file: &ProjectFile) -> Result<(), ProjectStorageError> {
        let index_path = self.index_path();
        let temporary_path = temporary_path_for(&index_path);
        let mut connection = Connection::open(&temporary_path).map_err(|error| {
            sqlite_error("create temporary event index", &temporary_path, error)
        })?;
        connection
            .execute_batch(
                "PRAGMA journal_mode = DELETE;
                 PRAGMA synchronous = FULL;
                 CREATE TABLE project_metadata (
                     key TEXT PRIMARY KEY NOT NULL,
                     value TEXT NOT NULL
                 ) STRICT;
                 CREATE TABLE project_events (
                     sequence INTEGER PRIMARY KEY NOT NULL CHECK(sequence > 0),
                     event_id TEXT UNIQUE NOT NULL,
                     occurred_at_year INTEGER NOT NULL,
                     event_sha256 TEXT NOT NULL
                 ) STRICT;",
            )
            .map_err(|error| sqlite_error("initialize event index", &temporary_path, error))?;
        let transaction = connection.transaction().map_err(|error| {
            sqlite_error("begin event-index transaction", &temporary_path, error)
        })?;
        let metadata = [
            ("index_schema", PROJECT_INDEX_SCHEMA.to_owned()),
            ("project_file_schema", PROJECT_FILE_SCHEMA.to_owned()),
            ("project_history_schema", PROJECT_HISTORY_SCHEMA.to_owned()),
            ("history_sha256", file.history_sha256().to_owned()),
            (
                "project_id",
                file.history().context().project_id().to_string(),
            ),
            ("run_id", file.history().context().run_id().to_string()),
        ];
        for (key, value) in metadata {
            transaction
                .execute(
                    "INSERT INTO project_metadata(key, value) VALUES (?1, ?2)",
                    params![key, value],
                )
                .map_err(|error| {
                    sqlite_error("write event-index metadata", &temporary_path, error)
                })?;
        }
        for event in expected_event_index_entries(file)? {
            transaction
                .execute(
                    "INSERT INTO project_events(sequence, event_id, occurred_at_year, event_sha256) \
                     VALUES (?1, ?2, ?3, ?4)",
                    params![
                        event.sequence,
                        event.event_id,
                        event.occurred_at_year,
                        event.event_sha256,
                    ],
                )
                .map_err(|error| sqlite_error("write event index", &temporary_path, error))?;
        }
        transaction
            .commit()
            .map_err(|error| sqlite_error("commit event index", &temporary_path, error))?;
        connection.close().map_err(|(_, error)| {
            sqlite_error("close temporary event index", &temporary_path, error)
        })?;
        replace_staged_file(&temporary_path, &index_path, None)
    }
}

fn migrate_legacy_history_v1_document(document: Value) -> Result<ProjectFile, ProjectStorageError> {
    let history: ProjectHistory = serde_json::from_value(document)
        .map_err(|error| ProjectStorageError::Migration(error.to_string()))?;
    ProjectFile::new(history)
}

fn canonical_history_sha256(history: &ProjectHistory) -> Result<String, ProjectStorageError> {
    history
        .replay()
        .map_err(|error| ProjectStorageError::Validation(error.to_string()))?;
    let bytes = serde_json::to_vec(history)
        .map_err(|error| ProjectStorageError::Serialization(error.to_string()))?;
    Ok(sha256_hex(&bytes))
}

fn expected_event_index_entries(
    file: &ProjectFile,
) -> Result<Vec<EventIndexEntry>, ProjectStorageError> {
    file.history()
        .events()
        .iter()
        .map(|event| {
            let event_json = serde_json::to_vec(event)
                .map_err(|error| ProjectStorageError::Serialization(error.to_string()))?;
            Ok(EventIndexEntry {
                sequence: event.sequence(),
                event_id: event.event_id().to_string(),
                occurred_at_year: event.occurred_at().year().0,
                event_sha256: sha256_hex(&event_json),
            })
        })
        .collect()
}

fn document_schema(document: &Value) -> Result<String, ProjectStorageError> {
    document
        .get("schemaVersion")
        .and_then(Value::as_str)
        .filter(|schema| !schema.trim().is_empty())
        .map(str::to_owned)
        .ok_or_else(|| {
            ProjectStorageError::Validation(
                "project document must contain a non-blank schemaVersion".to_owned(),
            )
        })
}

fn path_metadata(path: &Path) -> Result<Option<fs::Metadata>, ProjectStorageError> {
    match fs::symlink_metadata(path) {
        Ok(metadata) => Ok(Some(metadata)),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(None),
        Err(error) => Err(io_error("inspect project artifact", path, error)),
    }
}

fn is_link_or_reparse_point(metadata: &fs::Metadata) -> bool {
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x400;
        metadata.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0
    }
    #[cfg(not(windows))]
    {
        metadata.file_type().is_symlink()
    }
}

fn ensure_sha256(value: &str, label: &str) -> Result<(), ProjectStorageError> {
    if value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase())
    {
        Ok(())
    } else {
        Err(ProjectStorageError::Validation(format!(
            "{label} must be 64 lowercase hexadecimal characters"
        )))
    }
}

fn sha256_hex(bytes: &[u8]) -> String {
    Sha256::digest(bytes)
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

fn temporary_path_for(path: &Path) -> PathBuf {
    let name = path
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or("project");
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let counter = TEMPORARY_FILE_COUNTER.fetch_add(1, Ordering::Relaxed);
    path.with_file_name(format!(
        ".{name}.{}-{timestamp}-{counter}.tmp",
        process::id()
    ))
}

fn write_replaceable_file(
    destination: &Path,
    bytes: &[u8],
    recovery: Option<PathBuf>,
) -> Result<(), ProjectStorageError> {
    let temporary = temporary_path_for(destination);
    let write_result = (|| {
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temporary)
            .map_err(|error| io_error("create temporary project file", &temporary, error))?;
        file.write_all(bytes)
            .map_err(|error| io_error("write temporary project file", &temporary, error))?;
        file.sync_all()
            .map_err(|error| io_error("sync temporary project file", &temporary, error))?;
        Ok(())
    })();
    if let Err(error) = write_result {
        let _ = fs::remove_file(&temporary);
        return Err(error);
    }
    replace_staged_file(&temporary, destination, recovery)
}

fn replace_staged_file(
    temporary: &Path,
    destination: &Path,
    recovery: Option<PathBuf>,
) -> Result<(), ProjectStorageError> {
    match fs::rename(temporary, destination) {
        Ok(()) => sync_parent_directory(destination),
        Err(first_error) if destination.exists() => {
            // Windows does not guarantee rename-overwrite semantics. The prior
            // valid copy has already been committed to `recovery`, so a crash
            // between removal and rename is recoverable and never readable as
            // an unchecked project.
            fs::remove_file(destination)
                .map_err(|error| io_error("replace prior project file", destination, error))?;
            if let Err(second_error) = fs::rename(temporary, destination) {
                if let Some(recovery) = recovery {
                    if recovery.exists() {
                        let _ = fs::copy(&recovery, destination);
                    }
                }
                let _ = fs::remove_file(temporary);
                return Err(ProjectStorageError::Io {
                    operation: "replace staged project file".to_owned(),
                    path: destination.to_path_buf(),
                    message: format!(
                        "initial rename: {first_error}; replacement rename: {second_error}"
                    ),
                });
            }
            sync_parent_directory(destination)
        }
        Err(error) => Err(io_error("publish staged project file", destination, error)),
    }
}

fn io_error(operation: &str, path: &Path, error: std::io::Error) -> ProjectStorageError {
    ProjectStorageError::Io {
        operation: operation.to_owned(),
        path: path.to_path_buf(),
        message: error.to_string(),
    }
}

fn sqlite_error(operation: &str, path: &Path, error: rusqlite::Error) -> ProjectStorageError {
    ProjectStorageError::Index(format!("cannot {operation} {}: {error}", path.display()))
}

fn release_process_write_lease(path: &Path) {
    if let Some(leases) = PROCESS_WRITE_LEASES.get() {
        if let Ok(mut leases) = leases.lock() {
            leases.remove(path);
        }
    }
}

#[cfg(unix)]
fn sync_parent_directory(path: &Path) -> Result<(), ProjectStorageError> {
    let parent = path.parent().ok_or_else(|| {
        ProjectStorageError::Validation(format!(
            "project path {} has no parent directory",
            path.display()
        ))
    })?;
    let directory = File::open(parent)
        .map_err(|error| io_error("open project parent directory", parent, error))?;
    directory
        .sync_all()
        .map_err(|error| io_error("sync project parent directory", parent, error))
}

#[cfg(not(unix))]
fn sync_parent_directory(_path: &Path) -> Result<(), ProjectStorageError> {
    // Rust's standard library has no portable directory-sync primitive on
    // Windows. The staged replacement still has a validated recovery/journal
    // path, and platform-specific replacement can be strengthened later.
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::{
        collections::{BTreeMap, BTreeSet},
        env,
    };

    use rusqlite::Connection;
    use telysta_core::{
        identity::{EntityId, EntityKind},
        project::{ProjectDataLock, RunContext, RunContextParts, StateTransaction},
        state::{
            ConceptReference, ConstructionInventory, EvidenceClass, EvidenceRecord, FamilyPosition,
            LanguageState, LanguageStateParts, Lexeme, LexiconSenseGraph, MorphologyState,
            OrthographyState, Phoneme, PhonologyState, PragmaticsAndRegisters, ProsodyState,
            ProvenanceEntry, ProvenanceKind, ProvenanceLedger, RegisterDefinition, SegmentClass,
            Sense,
        },
        time::{SimYear, TimeModel},
    };

    use super::*;

    struct TempProject {
        path: PathBuf,
    }

    impl TempProject {
        fn new(label: &str) -> Self {
            let path = env::temp_dir().join(format!(
                "telysta-storage-{label}-{}-{}",
                process::id(),
                TEMPORARY_FILE_COUNTER.fetch_add(1, Ordering::Relaxed)
            ));
            fs::create_dir_all(&path).expect("create temporary project directory");
            Self { path }
        }
    }

    impl Drop for TempProject {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.path);
        }
    }

    fn id(kind: EntityKind, value: &str) -> EntityId {
        EntityId::new(kind, value).expect("valid test entity ID")
    }

    fn minimal_state() -> LanguageState {
        let time_model = TimeModel::new(SimYear(0), 25, 1).expect("valid time model");
        let timestamp = time_model.time_reference(SimYear(0));
        let evidence_id = id(EntityKind::Evidence, "fixture-preference");
        let event_id = id(EntityKind::Event, "genesis");
        let language_id = id(EntityKind::Language, "proto-fixture");
        let family_node_id = id(EntityKind::FamilyNode, "fixture-root");
        let community_id = id(EntityKind::SpeechCommunity, "fixture-community");
        let consonant_id = id(EntityKind::Phoneme, "p");
        let vowel_id = id(EntityKind::Phoneme, "a");
        let lexeme_id = id(EntityKind::Lexeme, "water");
        let sense_id = id(EntityKind::Sense, "water-liquid");
        let evidence_ids = BTreeSet::from([evidence_id.clone()]);

        let mut provenance_entries = BTreeMap::new();
        for entity_id in [
            language_id.clone(),
            family_node_id.clone(),
            consonant_id.clone(),
            vowel_id.clone(),
            lexeme_id.clone(),
            sense_id.clone(),
        ] {
            provenance_entries.insert(
                entity_id.clone(),
                ProvenanceEntry {
                    entity_id,
                    event_id: event_id.clone(),
                    kind: ProvenanceKind::Genesis,
                    created_at: timestamp.clone(),
                    evidence_ids: evidence_ids.clone(),
                },
            );
        }

        LanguageState::new(LanguageStateParts {
            language_id,
            as_of: timestamp,
            evidence: BTreeMap::from([(
                evidence_id.clone(),
                EvidenceRecord {
                    id: evidence_id,
                    class: EvidenceClass::CreativePreference,
                    note: "fixture only".to_owned(),
                    citation: None,
                    data_references: BTreeSet::new(),
                },
            )]),
            phonology: PhonologyState {
                phonemes: BTreeMap::from([
                    (
                        consonant_id.clone(),
                        Phoneme {
                            id: consonant_id.clone(),
                            ipa: "p".to_owned(),
                            class: SegmentClass::Consonant,
                            evidence_ids: evidence_ids.clone(),
                        },
                    ),
                    (
                        vowel_id.clone(),
                        Phoneme {
                            id: vowel_id.clone(),
                            ipa: "a".to_owned(),
                            class: SegmentClass::Vowel,
                            evidence_ids: evidence_ids.clone(),
                        },
                    ),
                ]),
            },
            prosody: ProsodyState {
                syllable_nuclei: BTreeSet::from([vowel_id.clone()]),
                max_syllable_moras: 2,
            },
            morphology: MorphologyState {
                morphemes: BTreeMap::new(),
            },
            constructions: ConstructionInventory {
                constructions: BTreeMap::new(),
            },
            lexicon: LexiconSenseGraph {
                lexemes: BTreeMap::from([(
                    lexeme_id.clone(),
                    Lexeme {
                        id: lexeme_id,
                        phoneme_sequence: vec![consonant_id, vowel_id],
                        morpheme_ids: BTreeSet::new(),
                        sense_ids: BTreeSet::from([sense_id.clone()]),
                        register: "neutral".to_owned(),
                    },
                )]),
                senses: BTreeMap::from([(
                    sense_id.clone(),
                    Sense {
                        id: sense_id,
                        concept: ConceptReference {
                            catalog: "fixture".to_owned(),
                            concept_id: "water".to_owned(),
                        },
                        related_sense_ids: BTreeSet::new(),
                        evidence_ids: evidence_ids.clone(),
                    },
                )]),
            },
            pragmatics: PragmaticsAndRegisters {
                default_register: "neutral".to_owned(),
                registers: BTreeMap::from([(
                    "neutral".to_owned(),
                    RegisterDefinition {
                        description: "default register".to_owned(),
                        formality_basis_points: 5_000,
                    },
                )]),
            },
            orthography: OrthographyState::Disabled,
            typology: BTreeMap::new(),
            family_position: FamilyPosition {
                node_id: family_node_id,
                parent_language_id: None,
                community_ids: BTreeSet::from([community_id]),
            },
            provenance: ProvenanceLedger {
                entries: provenance_entries,
            },
        })
        .expect("minimal state is valid")
    }

    fn history() -> ProjectHistory {
        let context = RunContext::new(RunContextParts {
            project_id: id(EntityKind::Project, "storage-fixture-project"),
            run_id: id(EntityKind::Run, "storage-fixture-run"),
            time_model: TimeModel::new(SimYear(0), 25, 1).expect("valid time model"),
            root_seed: 88,
            engine_version: "0.1.0-test".to_owned(),
            data_lock: ProjectDataLock::new(Vec::new()).expect("empty data lock"),
            rule_packs: BTreeMap::new(),
        })
        .expect("valid run context");
        StateTransaction::begin(context, id(EntityKind::Event, "genesis"), minimal_state())
            .expect("valid transaction")
            .history()
    }

    fn intentionally_rejected_migration(_: Value) -> Result<ProjectFile, ProjectStorageError> {
        Err(ProjectStorageError::Migration(
            "test migration must never replace the original registration".to_owned(),
        ))
    }

    fn revised_history(base: &ProjectHistory, label: &str) -> ProjectHistory {
        let mut transaction = base.replay().expect("replay fixture");
        transaction
            .revise_state(id(EntityKind::Event, label), minimal_state(), label)
            .expect("valid revision");
        transaction.history()
    }

    fn pending_migration(store: &ProjectStore, publish_target: bool) -> PathBuf {
        let source = serde_json::to_vec_pretty(&history()).expect("encode source");
        fs::write(store.project_path(), &source).expect("write source");
        let archive = store
            .archive_migration_source(&source)
            .expect("archive source");
        let target = ProjectFile::new(history()).expect("target file");
        let journal = MigrationJournal::new(
            PROJECT_HISTORY_SCHEMA.to_owned(),
            archive.file_name().unwrap().to_str().unwrap().to_owned(),
            target.history_sha256().to_owned(),
        )
        .expect("journal");
        store
            .write_migration_journal(&journal)
            .expect("write journal");
        if publish_target {
            store
                .write_project_file(&target, false)
                .expect("publish target");
        }
        archive
    }

    #[test]
    fn pending_migration_preserves_an_unrelated_or_damaged_primary() {
        let alternate = revised_history(&history(), "newer-legacy-data");
        for bytes in [
            serde_json::to_vec(&alternate).unwrap(),
            br#"{"schemaVersion":"unrecognized-project.v9","data":"preserve"}"#.to_vec(),
            b"damaged but potentially recoverable user data".to_vec(),
        ] {
            let temporary = TempProject::new("migration-primary-conflict");
            let store = ProjectStore::open(&temporary.path).unwrap();
            let archive = pending_migration(&store, false);
            let archived = fs::read(&archive).unwrap();
            let journal = fs::read(store.migration_journal_path()).unwrap();
            fs::write(store.project_path(), &bytes).unwrap();
            assert!(store
                .recover_migration(&ProjectMigrationRegistry::with_legacy_history_v1())
                .is_err());
            assert_eq!(fs::read(store.project_path()).unwrap(), bytes);
            assert_eq!(fs::read(store.migration_journal_path()).unwrap(), journal);
            assert_eq!(fs::read(archive).unwrap(), archived);
        }
    }

    #[test]
    fn pending_migration_resumes_its_exact_source_or_published_target() {
        for published in [false, true] {
            let temporary = TempProject::new("migration-matching-primary");
            let store = ProjectStore::open(&temporary.path).unwrap();
            let archive = pending_migration(&store, published);
            let result = store
                .recover_migration(&ProjectMigrationRegistry::with_legacy_history_v1())
                .unwrap()
                .unwrap();
            assert_eq!(result.project.history, history());
            assert_eq!(result.source_archive, Some(archive));
            assert!(!store.migration_journal_path().exists());
        }
    }

    #[test]
    fn published_snapshots_remain_bound_to_the_callers_commit() {
        let temporary = TempProject::new("publication-snapshot");
        let store = ProjectStore::open(&temporary.path).unwrap();
        let base = history();
        let created = store.create_with_snapshot(base.clone()).unwrap();
        let first = revised_history(&base, "first-writer");
        let committed = store
            .save_if_current_with_snapshot(first.clone(), &created.history_sha256)
            .unwrap();
        let second = revised_history(&first, "second-writer");
        store
            .save_if_current(second.clone(), &committed.history_sha256)
            .unwrap();
        let _lease = store.acquire_write_lease().unwrap();
        assert!(matches!(
            store.load(),
            Err(ProjectStorageError::WriteLocked { .. })
        ));
        assert_eq!(created.history, base);
        assert_eq!(committed.history, first);
        assert_ne!(created.history_sha256, committed.history_sha256);
        assert!(!created.recovered_from_last_valid);
        assert!(!committed.recovered_from_last_valid);
        assert_eq!(store.load_unlocked().unwrap().history, second);
    }

    #[test]
    fn save_without_expected_hash_cannot_replace_or_extend_existing_history() {
        let temporary = TempProject::new("save-authority");
        let store = ProjectStore::open(&temporary.path).unwrap();
        let base = history();
        let first = revised_history(&base, "first");
        let created = store.save(first.clone()).unwrap();
        let bytes = fs::read(store.project_path()).unwrap();
        for candidate in [base, revised_history(&first, "unconditional-append")] {
            assert!(store.save(candidate).is_err());
            assert_eq!(fs::read(store.project_path()).unwrap(), bytes);
            assert!(!store.recovery_path().exists());
        }
        let retry = store.save(first).unwrap();
        assert_eq!(retry.history_sha256, created.history_sha256);
        assert_eq!(fs::read(store.project_path()).unwrap(), bytes);
        assert!(!store.recovery_path().exists());
    }

    #[test]
    fn runtime_requires_its_open_revision_even_if_caller_knows_new_disk_hash() {
        let temporary = TempProject::new("session-authority");
        let store = ProjectStore::open(&temporary.path).unwrap();
        let base = history();
        store.create_if_absent(base.clone()).unwrap();
        let mut runtime = ProjectRuntime::default();
        let session = runtime.open_existing(&temporary.path).unwrap();
        let external = revised_history(&base, "external");
        let saved = store
            .save_if_current(external.clone(), &session.history_sha256)
            .unwrap();
        let candidate = revised_history(&external, "candidate");
        let bytes = fs::read(store.project_path()).unwrap();
        assert!(matches!(
            runtime.commit_history(
                &session.project_id,
                &saved.history_sha256,
                candidate.clone()
            ),
            Err(ProjectRuntimeError::WriteConflict { .. })
        ));
        assert_eq!(runtime.session(&session.project_id).unwrap(), session);
        assert_eq!(fs::read(store.project_path()).unwrap(), bytes);
        let refreshed = runtime.refresh(&session.project_id).unwrap();
        runtime
            .commit_history(&session.project_id, &refreshed.history_sha256, candidate)
            .unwrap();
    }

    #[test]
    fn normal_writers_preserve_a_pending_migration_journal() {
        let temporary = TempProject::new("pending-migration-writer");
        let store = ProjectStore::open(&temporary.path).unwrap();
        pending_migration(&store, true);
        let loaded = store.load().unwrap();
        let bytes = fs::read(store.project_path()).unwrap();
        let journal = fs::read(store.migration_journal_path()).unwrap();
        assert!(store.save(loaded.history.clone()).is_err());
        assert!(store
            .save_if_current(
                revised_history(&loaded.history, "premature-append"),
                &loaded.history_sha256,
            )
            .is_err());
        assert_eq!(fs::read(store.project_path()).unwrap(), bytes);
        assert_eq!(fs::read(store.migration_journal_path()).unwrap(), journal);
        assert!(!store.recovery_path().exists());
    }

    #[cfg(unix)]
    #[test]
    fn migration_rejects_linked_archives_and_directories() {
        use std::os::unix::fs::symlink;

        for linked_directory in [false, true] {
            let temporary = TempProject::new("migration-linked-archive");
            let outside = TempProject::new("migration-external-data");
            let store = ProjectStore::open(&temporary.path).unwrap();
            let archive = pending_migration(&store, true);
            let archived = fs::read(&archive).unwrap();
            let external = outside.path.join(archive.file_name().unwrap());
            fs::write(&external, &archived).unwrap();
            if linked_directory {
                fs::remove_dir_all(store.migration_directory()).unwrap();
                symlink(&outside.path, store.migration_directory()).unwrap();
            } else {
                fs::remove_file(&archive).unwrap();
                symlink(&external, &archive).unwrap();
            }
            let primary = fs::read(store.project_path()).unwrap();
            assert!(store
                .recover_migration(&ProjectMigrationRegistry::with_legacy_history_v1())
                .is_err());
            assert!(store.migration_journal_path().is_file());
            assert_eq!(fs::read(store.project_path()).unwrap(), primary);
            assert_eq!(fs::read(external).unwrap(), archived);
        }

        let temporary = TempProject::new("migration-linked-output");
        let outside = TempProject::new("migration-external-output");
        let store = ProjectStore::open(&temporary.path).unwrap();
        symlink(&outside.path, store.migration_directory()).unwrap();
        assert!(store.archive_migration_source(b"source bytes").is_err());
        assert_eq!(fs::read_dir(&outside.path).unwrap().count(), 0);
    }

    #[cfg(unix)]
    #[test]
    fn creation_preserves_dangling_artifact_links() {
        use std::os::unix::fs::symlink;

        for artifact in [
            PROJECT_FILE_NAME,
            PROJECT_RECOVERY_FILE_NAME,
            PROJECT_MIGRATION_JOURNAL_FILE_NAME,
        ] {
            let temporary = TempProject::new("create-dangling-link");
            let store = ProjectStore::open(&temporary.path).unwrap();
            let path = temporary.path.join(artifact);
            let missing = temporary.path.join("missing-source");
            symlink(&missing, &path).unwrap();
            assert!(store.create_if_absent(history()).is_err());
            assert_eq!(fs::read_link(path).unwrap(), missing);
        }
    }

    #[test]
    fn commit_rejects_truncation_and_fork_without_changing_files() {
        let temporary = TempProject::new("append-only");
        let store = ProjectStore::open(&temporary.path).expect("open store");
        let base = history();
        let committed = revised_history(&base, "committed");
        store.save(committed.clone()).expect("save history");
        let mut runtime = ProjectRuntime::default();
        let session = runtime
            .open_existing(&temporary.path)
            .expect("open session");
        let bytes = fs::read(store.project_path()).expect("read original");
        for candidate in [base.clone(), revised_history(&base, "fork")] {
            assert!(runtime
                .commit_history(&session.project_id, &session.history_sha256, candidate)
                .is_err());
            assert_eq!(fs::read(store.project_path()).unwrap(), bytes);
            assert_eq!(runtime.session(&session.project_id).unwrap(), session);
        }
        let extended = revised_history(&committed, "extension");
        runtime
            .commit_history(
                &session.project_id,
                &session.history_sha256,
                extended.clone(),
            )
            .expect("append valid extension");
        assert_eq!(store.load().unwrap().history, extended);
    }

    #[test]
    fn conditional_save_rejects_changed_run_inputs() {
        let temporary = TempProject::new("context-immutable");
        let store = ProjectStore::open(&temporary.path).expect("open store");
        store.save(history()).expect("save initial");
        let loaded = store.load().unwrap();
        let mut document = serde_json::to_value(&loaded.history).unwrap();
        document["context"]["rootSeed"] = Value::from(89);
        let candidate: ProjectHistory =
            serde_json::from_value(document).expect("replayable context");
        assert!(store
            .save_if_current(candidate, &loaded.history_sha256)
            .is_err());
        assert_eq!(store.load().unwrap().history, loaded.history);
    }

    #[test]
    fn runtime_creation_rejects_duplicate_identity_before_writing() {
        let first = TempProject::new("create-first");
        let second = TempProject::new("create-second");
        let mut runtime = ProjectRuntime::default();
        runtime
            .create_from_genesis(&first.path, history())
            .expect("create first");
        assert!(matches!(
            runtime.create_from_genesis(&second.path, history()),
            Err(ProjectRuntimeError::ProjectIdentityAlreadyOpen { .. })
        ));
        assert!(!second.path.join(PROJECT_FILE_NAME).exists());
    }

    #[test]
    fn pending_migration_rejects_missing_or_tampered_archive_before_clearing_journal() {
        for published in [false, true] {
            for missing in [false, true] {
                let temporary = TempProject::new("archive-integrity");
                let store = ProjectStore::open(&temporary.path).expect("open store");
                let archive = pending_migration(&store, published);
                if missing {
                    fs::remove_file(archive).unwrap();
                } else {
                    fs::write(archive, b"tampered source").unwrap();
                }
                let before = fs::read(store.project_path()).unwrap();
                assert!(store
                    .recover_migration(&ProjectMigrationRegistry::with_legacy_history_v1())
                    .is_err());
                assert!(store.migration_journal_path().exists());
                assert_eq!(fs::read(store.project_path()).unwrap(), before);
            }
        }
    }

    #[test]
    fn migration_rejects_corrupt_existing_content_addressed_archive() {
        let temporary = TempProject::new("archive-collision");
        let store = ProjectStore::open(&temporary.path).expect("open store");
        let source = serde_json::to_vec_pretty(&history()).unwrap();
        fs::write(store.project_path(), &source).unwrap();
        let archive = store.archive_migration_source(&source).unwrap();
        fs::write(archive, b"corrupt existing archive").unwrap();
        assert!(store
            .migrate(&ProjectMigrationRegistry::with_legacy_history_v1())
            .is_err());
        assert_eq!(fs::read(store.project_path()).unwrap(), source);
        assert!(!store.migration_journal_path().exists());
    }

    #[test]
    fn completed_migration_still_revalidates_registry_and_journal_source() {
        let temporary = TempProject::new("completed-source-proof");
        let store = ProjectStore::open(&temporary.path).expect("open store");
        pending_migration(&store, true);
        assert!(store
            .recover_migration(&ProjectMigrationRegistry::default())
            .is_err());
        assert!(store.migration_journal_path().exists());
        let mut journal = store.read_migration_journal().unwrap().unwrap();
        journal.source_schema = "unknown-source.v1".to_owned();
        store.write_migration_journal(&journal).unwrap();
        assert!(store
            .recover_migration(&ProjectMigrationRegistry::with_legacy_history_v1())
            .is_err());
        assert!(store.migration_journal_path().exists());
    }

    #[test]
    fn reads_do_not_publish_or_query_index_while_another_writer_holds_the_lease() {
        let temporary = TempProject::new("index-lease");
        let store = ProjectStore::open(&temporary.path).expect("open store");
        store.save(history()).unwrap();
        fs::remove_file(store.index_path()).unwrap();
        let _lease = store.acquire_write_lease().unwrap();
        let reader = ProjectStore::open(&temporary.path).unwrap();
        assert!(matches!(
            reader.load(),
            Err(ProjectStorageError::WriteLocked { .. })
        ));
        assert!(matches!(
            reader.event_index_entries(),
            Err(ProjectStorageError::WriteLocked { .. })
        ));
        assert!(!store.index_path().exists());
    }

    #[test]
    fn creation_is_exclusive_and_preserves_existing_recovery_artifacts() {
        let temporary = TempProject::new("create-race");
        let barrier = std::sync::Arc::new(std::sync::Barrier::new(2));
        let creators: Vec<_> = (0..2)
            .map(|_| {
                let barrier = barrier.clone();
                let root = temporary.path.clone();
                std::thread::spawn(move || {
                    let store = ProjectStore::open(root).unwrap();
                    barrier.wait();
                    store.create_if_absent(history())
                })
            })
            .collect();
        let outcomes: Vec<_> = creators
            .into_iter()
            .map(|thread| thread.join().unwrap())
            .collect();
        assert_eq!(outcomes.iter().filter(|result| result.is_ok()).count(), 1);
        let store = ProjectStore::open(&temporary.path).unwrap();
        assert_eq!(store.load().unwrap().history, history());
        assert!(!store.recovery_path().exists());

        for artifact in [
            PROJECT_RECOVERY_FILE_NAME,
            PROJECT_MIGRATION_JOURNAL_FILE_NAME,
        ] {
            let temporary = TempProject::new("create-recovery");
            let store = ProjectStore::open(&temporary.path).unwrap();
            let path = temporary.path.join(artifact);
            fs::write(&path, b"preserve forensic evidence").unwrap();
            assert!(store.create_if_absent(history()).is_err());
            assert_eq!(fs::read(path).unwrap(), b"preserve forensic evidence");
            assert!(!store.project_path().exists());
        }
    }

    #[test]
    fn completed_migration_rejects_archive_that_regenerates_a_different_target() {
        let temporary = TempProject::new("migration-target-proof");
        let store = ProjectStore::open(&temporary.path).unwrap();
        pending_migration(&store, true);
        let alternate = revised_history(&history(), "alternate-source");
        let source = serde_json::to_vec(&alternate).unwrap();
        let archive = store.archive_migration_source(&source).unwrap();
        let mut journal = store.read_migration_journal().unwrap().unwrap();
        journal.source_archive_file = archive.file_name().unwrap().to_str().unwrap().to_owned();
        store.write_migration_journal(&journal).unwrap();
        assert!(store
            .recover_migration(&ProjectMigrationRegistry::with_legacy_history_v1())
            .is_err());
        assert!(store.migration_journal_path().exists());
        assert_eq!(store.load().unwrap().history, history());
    }

    #[test]
    fn cross_process_lease_excludes_creation_and_projection() {
        const PROBE_ROOT: &str = "TELYSTA_STORAGE_LEASE_PROBE_ROOT";
        if let Some(root) = env::var_os(PROBE_ROOT) {
            let store = ProjectStore::open(PathBuf::from(root)).unwrap();
            assert!(matches!(
                store.create_if_absent(history()),
                Err(ProjectStorageError::WriteLocked { .. })
            ));
            assert!(matches!(
                store.load(),
                Err(ProjectStorageError::WriteLocked { .. })
            ));
            assert!(matches!(
                store.event_index_entries(),
                Err(ProjectStorageError::WriteLocked { .. })
            ));
            return;
        }
        let temporary = TempProject::new("process-lease");
        let store = ProjectStore::open(&temporary.path).unwrap();
        store.save(history()).unwrap();
        fs::remove_file(store.index_path()).unwrap();
        let _lease = store.acquire_write_lease().unwrap();
        let output = std::process::Command::new(env::current_exe().unwrap())
            .args([
                "--exact",
                "tests::cross_process_lease_excludes_creation_and_projection",
                "--nocapture",
            ])
            .env(PROBE_ROOT, &temporary.path)
            .output()
            .expect("run independent storage process");
        assert!(
            output.status.success(),
            "{}\n{}",
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        );
        assert!(!store.index_path().exists());
    }

    #[test]
    fn saves_replays_and_indexes_a_project() {
        let temporary = TempProject::new("round-trip");
        let store = ProjectStore::open(&temporary.path).expect("open project store");
        let expected = history();

        let saved = store.save(expected.clone()).expect("save project");
        assert_eq!(saved.index_status, IndexStatus::Rebuilt);
        let loaded = store.load().expect("load project");

        assert_eq!(loaded.history, expected);
        assert!(!loaded.recovered_from_last_valid);
        assert_eq!(loaded.index_status, IndexStatus::Fresh);
        assert_eq!(store.event_index_entries().expect("event index").len(), 1);
    }

    #[test]
    fn corrupt_primary_recovers_only_from_a_prior_valid_copy() {
        let temporary = TempProject::new("recovery");
        let store = ProjectStore::open(&temporary.path).expect("open project store");
        let expected = history();
        let saved = store.save(expected.clone()).expect("initial save");
        store
            .save_if_current(expected.clone(), &saved.history_sha256)
            .expect("second save writes recovery copy");
        fs::write(store.project_path(), b"{not valid JSON").expect("corrupt primary file");

        let loaded = store.load().expect("recover prior project");
        assert_eq!(loaded.history, expected);
        assert!(loaded.recovered_from_last_valid);
    }

    #[test]
    fn checksum_tampering_is_rejected_when_no_recovery_copy_exists() {
        let temporary = TempProject::new("checksum");
        let store = ProjectStore::open(&temporary.path).expect("open project store");
        store.save(history()).expect("save project");

        let mut document: Value =
            serde_json::from_slice(&fs::read(store.project_path()).expect("read project file"))
                .expect("parse project JSON");
        document["historySha256"] = Value::String("0".repeat(64));
        fs::write(
            store.project_path(),
            serde_json::to_vec(&document).expect("encode tampered project"),
        )
        .expect("write tampered project");

        assert!(matches!(
            store.load(),
            Err(ProjectStorageError::Validation(_))
        ));
    }

    #[test]
    fn legacy_history_requires_and_uses_an_explicit_migration() {
        let temporary = TempProject::new("migration");
        let store = ProjectStore::open(&temporary.path).expect("open project store");
        let expected = history();
        fs::write(
            store.project_path(),
            serde_json::to_vec_pretty(&expected).expect("encode legacy history"),
        )
        .expect("write legacy history");

        assert!(matches!(
            store.load(),
            Err(ProjectStorageError::MigrationRequired { .. })
        ));
        let migrated = store
            .migrate(&ProjectMigrationRegistry::with_legacy_history_v1())
            .expect("explicit migration");

        assert_eq!(migrated.project.history, expected);
        assert!(migrated.source_archive.expect("source archive").exists());
        assert_eq!(
            store.load().expect("load upgraded project").history,
            expected
        );
    }

    #[test]
    fn missing_index_is_rebuilt_from_the_authoritative_history() {
        let temporary = TempProject::new("rebuild-index");
        let store = ProjectStore::open(&temporary.path).expect("open project store");
        store.save(history()).expect("save project");
        fs::remove_file(store.index_path()).expect("remove derived index");

        let loaded = store.load().expect("load and rebuild index");
        assert_eq!(loaded.index_status, IndexStatus::Rebuilt);
        assert!(store.index_path().exists());
    }

    #[test]
    fn changed_index_rows_are_rebuilt_even_when_metadata_is_unchanged() {
        let temporary = TempProject::new("index-integrity");
        let store = ProjectStore::open(&temporary.path).expect("open project store");
        store.save(history()).expect("save project");
        let connection = Connection::open(store.index_path()).expect("open derived index");
        connection
            .execute("DELETE FROM project_events", [])
            .expect("tamper with derived index");
        drop(connection);

        let loaded = store.load().expect("load and rebuild changed index");
        assert_eq!(loaded.index_status, IndexStatus::Rebuilt);
        assert_eq!(
            store
                .event_index_entries()
                .expect("rebuilt event index")
                .len(),
            1
        );
    }

    #[test]
    fn write_lease_and_expected_history_hash_prevent_lost_updates() {
        let temporary = TempProject::new("concurrency");
        let first = ProjectStore::open(&temporary.path).expect("open first store");
        let second = ProjectStore::open(&temporary.path).expect("open second store");
        first.save(history()).expect("initial save");

        let lease = first.acquire_write_lease().expect("acquire first lease");
        assert!(matches!(
            second.save(history()),
            Err(ProjectStorageError::WriteLocked { .. })
        ));
        drop(lease);

        let current = second.load().expect("load current revision");
        second
            .save_if_current(history(), &current.history_sha256)
            .expect("save matching revision");
        assert!(matches!(
            second.save_if_current(history(), &"0".repeat(64)),
            Err(ProjectStorageError::WriteConflict { .. })
        ));
    }

    #[test]
    fn interrupted_migration_resumes_from_its_journal_and_source_archive() {
        let temporary = TempProject::new("migration-journal");
        let store = ProjectStore::open(&temporary.path).expect("open project store");
        let expected = history();
        let source = serde_json::to_vec_pretty(&expected).expect("encode legacy history");
        fs::write(store.project_path(), &source).expect("write legacy history");
        let archive = store
            .archive_migration_source(&source)
            .expect("archive migration source");
        let target = ProjectFile::new(expected.clone()).expect("build migrated project");
        let journal = MigrationJournal::new(
            PROJECT_HISTORY_SCHEMA.to_owned(),
            archive
                .file_name()
                .and_then(|name| name.to_str())
                .expect("archive file name")
                .to_owned(),
            target.history_sha256().to_owned(),
        )
        .expect("build migration journal");
        store
            .write_migration_journal(&journal)
            .expect("write migration journal");
        fs::remove_file(store.project_path()).expect("simulate interrupted publish");

        let recovered = store
            .recover_migration(&ProjectMigrationRegistry::with_legacy_history_v1())
            .expect("recover migration")
            .expect("pending journal exists");
        assert_eq!(recovered.project.history, expected);
        assert!(!store.migration_journal_path().exists());
    }

    #[test]
    fn duplicate_migration_registration_does_not_replace_the_original() {
        let mut registry = ProjectMigrationRegistry::with_legacy_history_v1();
        assert!(registry
            .register(ProjectMigration::new(
                PROJECT_HISTORY_SCHEMA,
                PROJECT_FILE_SCHEMA,
                intentionally_rejected_migration,
            ))
            .is_err());
        let raw = serde_json::to_value(history()).expect("encode legacy history");
        let migration = registry
            .find(PROJECT_HISTORY_SCHEMA)
            .expect("original migration retained");
        assert!((migration.transform)(raw).is_ok());
    }

    #[test]
    fn runtime_opens_exposes_and_closes_a_valid_project_session() {
        let temporary = TempProject::new("runtime-open");
        let store = ProjectStore::open(&temporary.path).expect("open project store");
        store.save(history()).expect("save project");

        let mut runtime = ProjectRuntime::default();
        let session = runtime
            .open_existing(&temporary.path)
            .expect("open valid project session");

        assert_eq!(session.schema_version, PROJECT_SESSION_SCHEMA);
        assert_eq!(session.summary.event_count, 1);
        assert_eq!(session.summary.phoneme_count, 2);
        assert_eq!(session.summary.lexeme_count, 1);
        assert!(!session.dirty);
        assert_eq!(session.status, ProjectSessionStatus::Ready);
        assert_eq!(
            runtime
                .session(&session.project_id)
                .expect("get open session"),
            session
        );
        assert!(matches!(
            runtime.open_existing(&temporary.path),
            Err(ProjectRuntimeError::ProjectAlreadyOpen { .. })
        ));
        assert_eq!(
            runtime
                .close(&session.project_id)
                .expect("close open project"),
            session
        );
        assert!(matches!(
            runtime.session(&session.project_id),
            Err(ProjectRuntimeError::UnknownProject { .. })
        ));
    }

    #[test]
    fn runtime_commits_only_replayable_history_at_the_open_revision() {
        let temporary = TempProject::new("runtime-commit");
        let store = ProjectStore::open(&temporary.path).expect("open project store");
        store.save(history()).expect("save project");

        let mut runtime = ProjectRuntime::default();
        let opened = runtime
            .open_existing(&temporary.path)
            .expect("open valid project session");
        let mut transaction = history().replay().expect("replay fixture history");
        transaction
            .revise_state(
                id(EntityKind::Event, "runtime-revision"),
                minimal_state(),
                "runtime commit test",
            )
            .expect("valid revision");

        let committed = runtime
            .commit_history(
                &opened.project_id,
                &opened.history_sha256,
                transaction.history(),
            )
            .expect("commit replayable history");
        assert_eq!(committed.summary.event_count, 2);
        assert_ne!(committed.history_sha256, opened.history_sha256);
        assert!(matches!(
            runtime.commit_history(&opened.project_id, &opened.history_sha256, history(),),
            Err(ProjectRuntimeError::WriteConflict { .. })
        ));
    }

    #[test]
    fn runtime_creation_refuses_non_genesis_history() {
        let temporary = TempProject::new("runtime-create");
        let mut transaction = history().replay().expect("replay fixture history");
        transaction
            .revise_state(
                id(EntityKind::Event, "creation-revision"),
                minimal_state(),
                "not a genesis history",
            )
            .expect("valid revision");

        let mut runtime = ProjectRuntime::default();
        assert!(matches!(
            runtime.create_from_genesis(&temporary.path, transaction.history()),
            Err(ProjectRuntimeError::CreationRequiresGenesisHistory)
        ));
        assert!(!temporary.path.join(PROJECT_FILE_NAME).exists());
    }
}
