//! Runtime-facing project sessions built on the authoritative project store.
//!
//! A session is a derived, versioned view of a validated [`ProjectHistory`].
//! It is deliberately not part of `project.json`: UI selection, open handles,
//! and command availability must never become a second source of language
//! truth.  Mutations enter through [`ProjectRuntime::commit_history`], which
//! accepts only a complete, replay-valid project history and uses the storage
//! layer's optimistic-concurrency check.

use std::{
    collections::BTreeMap,
    error::Error,
    fmt, fs,
    path::{Path, PathBuf},
};

use serde::Serialize;
use telysta_core::{
    hash::{SemanticHashReport, SemanticHasher},
    identity::EntityId,
    project::ProjectHistory,
};

use crate::{IndexStatus, LoadedProject, ProjectStorageError, ProjectStore};

pub const PROJECT_SESSION_SCHEMA: &str = "telysta-project-session.v1";

/// The lifecycle state visible to a desktop client. A recovered session is
/// usable, but deliberately tells the client that the last valid copy was used
/// instead of silently hiding a previous interrupted write.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ProjectSessionStatus {
    Ready,
    Recovered,
}

/// The index is derived from `project.json`; this wire type makes that
/// distinction explicit without exposing persistence implementation details to
/// the desktop UI.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case", tag = "kind")]
pub enum ProjectSessionIndexStatus {
    Fresh,
    Rebuilt,
    Deferred { reason: String },
}

impl From<&IndexStatus> for ProjectSessionIndexStatus {
    fn from(status: &IndexStatus) -> Self {
        match status {
            IndexStatus::Fresh => Self::Fresh,
            IndexStatus::Rebuilt => Self::Rebuilt,
            IndexStatus::Deferred { reason } => Self::Deferred {
                reason: reason.clone(),
            },
        }
    }
}

/// A compact, stable read model for project-list and workspace views.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectSessionSummary {
    pub language_id: EntityId,
    pub as_of_year: i32,
    pub event_count: usize,
    pub phoneme_count: usize,
    pub morpheme_count: usize,
    pub construction_count: usize,
    pub lexeme_count: usize,
    pub sense_count: usize,
    pub register_count: usize,
}

/// The only project-shaped data returned by the runtime boundary.
///
/// The full `LanguageState` remains inside the core transaction and storage
/// contracts. A future expert inspector can expose explicitly versioned,
/// domain-focused read models rather than coupling the UI to internal state
/// fields.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectSession {
    pub schema_version: &'static str,
    pub project_id: EntityId,
    pub run_id: EntityId,
    pub project_root: String,
    pub history_sha256: String,
    pub engine_version: String,
    pub root_seed: u64,
    pub status: ProjectSessionStatus,
    pub index_status: ProjectSessionIndexStatus,
    pub dirty: bool,
    pub summary: ProjectSessionSummary,
    pub state_hashes: SemanticHashReport,
}

impl ProjectSession {
    fn from_loaded(root: &Path, loaded: &LoadedProject) -> Result<Self, ProjectRuntimeError> {
        let state = loaded
            .history
            .events()
            .last()
            .map(|event| event.state())
            .ok_or_else(|| ProjectRuntimeError::InvalidHistory {
                message: "loaded project history contains no resulting state".to_owned(),
            })?;
        let statistics = state.corpus_statistics();
        let summary = ProjectSessionSummary {
            language_id: state.language_id().clone(),
            as_of_year: state.as_of().year().0,
            event_count: loaded.history.events().len(),
            phoneme_count: statistics.phoneme_count,
            morpheme_count: statistics.morpheme_count,
            construction_count: statistics.construction_count,
            lexeme_count: statistics.lexeme_count,
            sense_count: statistics.sense_count,
            register_count: statistics.register_count,
        };
        let project_root =
            root.to_str()
                .ok_or_else(|| ProjectRuntimeError::InvalidProjectRoot {
                    message: format!(
                        "project root {} cannot be represented as a UTF-8 command value",
                        root.display()
                    ),
                })?;

        Ok(Self {
            schema_version: PROJECT_SESSION_SCHEMA,
            project_id: loaded.history.context().project_id().clone(),
            run_id: loaded.history.context().run_id().clone(),
            project_root: project_root.to_owned(),
            history_sha256: loaded.history_sha256.clone(),
            engine_version: loaded.history.context().engine_version().to_owned(),
            root_seed: loaded.history.context().root_seed(),
            status: if loaded.recovered_from_last_valid {
                ProjectSessionStatus::Recovered
            } else {
                ProjectSessionStatus::Ready
            },
            index_status: ProjectSessionIndexStatus::from(&loaded.index_status),
            dirty: false,
            summary,
            state_hashes: SemanticHasher::hash(state).map_err(|error| {
                ProjectRuntimeError::InvalidHistory {
                    message: error.to_string(),
                }
            })?,
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case", tag = "code")]
pub enum ProjectRuntimeError {
    InvalidProjectRoot {
        message: String,
    },
    ProjectMissing {
        project_root: String,
    },
    ProjectAlreadyOpen {
        project_id: EntityId,
        project_root: String,
    },
    ProjectIdentityAlreadyOpen {
        project_id: EntityId,
        project_root: String,
    },
    UnknownProject {
        project_id: EntityId,
    },
    ProjectIdentityMismatch {
        expected_project_id: EntityId,
        actual_project_id: EntityId,
    },
    RunIdentityMismatch {
        project_id: EntityId,
        expected_run_id: EntityId,
        actual_run_id: EntityId,
    },
    CreationRequiresGenesisHistory,
    WriteConflict {
        expected_history_sha256: String,
        actual_history_sha256: Option<String>,
    },
    InvalidHistory {
        message: String,
    },
    Storage {
        message: String,
    },
}

impl fmt::Display for ProjectRuntimeError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidProjectRoot { message }
            | Self::InvalidHistory { message }
            | Self::Storage { message } => formatter.write_str(message),
            Self::ProjectMissing { project_root } => {
                write!(formatter, "no Telysta project exists at {project_root}")
            }
            Self::ProjectAlreadyOpen {
                project_id,
                project_root,
            } => write!(
                formatter,
                "project {project_id} is already open at {project_root}"
            ),
            Self::ProjectIdentityAlreadyOpen {
                project_id,
                project_root,
            } => write!(
                formatter,
                "project identity {project_id} is already open from a different directory; refusing duplicate at {project_root}"
            ),
            Self::UnknownProject { project_id } => {
                write!(formatter, "project {project_id} is not open")
            }
            Self::ProjectIdentityMismatch {
                expected_project_id,
                actual_project_id,
            } => write!(
                formatter,
                "cannot commit history for {actual_project_id} into session for {expected_project_id}"
            ),
            Self::RunIdentityMismatch {
                project_id,
                expected_run_id,
                actual_run_id,
            } => write!(
                formatter,
                "cannot commit history for run {actual_run_id} into project {project_id} session for run {expected_run_id}"
            ),
            Self::CreationRequiresGenesisHistory => formatter.write_str(
                "a new project must be created from an exact, compiler-produced genesis history",
            ),
            Self::WriteConflict {
                expected_history_sha256,
                actual_history_sha256,
            } => write!(
                formatter,
                "project changed before commit: expected {expected_history_sha256}, found {}",
                actual_history_sha256.as_deref().unwrap_or("no current project")
            ),
        }
    }
}

impl Error for ProjectRuntimeError {}

impl From<ProjectStorageError> for ProjectRuntimeError {
    fn from(error: ProjectStorageError) -> Self {
        match error {
            ProjectStorageError::WriteConflict {
                expected_history_sha256,
                actual_history_sha256,
            } => Self::WriteConflict {
                expected_history_sha256,
                actual_history_sha256,
            },
            other => Self::Storage {
                message: other.to_string(),
            },
        }
    }
}

#[derive(Debug, Clone)]
struct OpenProject {
    store: ProjectStore,
    history: ProjectHistory,
    session: ProjectSession,
}

/// Process-local registry and mutation boundary for official project files.
///
/// File-level locking remains the authority across processes. This registry
/// prevents one desktop process from opening a second mutable handle for the
/// same canonical path or project identity.
#[derive(Debug, Default)]
pub struct ProjectRuntime {
    open_by_root: BTreeMap<PathBuf, EntityId>,
    open_by_project_id: BTreeMap<EntityId, OpenProject>,
}

impl ProjectRuntime {
    pub fn open_existing(
        &mut self,
        project_root: impl AsRef<Path>,
    ) -> Result<ProjectSession, ProjectRuntimeError> {
        let root = canonical_existing_directory(project_root.as_ref())?;
        if let Some(project_id) = self.open_by_root.get(&root) {
            return Err(ProjectRuntimeError::ProjectAlreadyOpen {
                project_id: project_id.clone(),
                project_root: root_to_wire(&root)?,
            });
        }

        let store = ProjectStore::open(root.clone())?;
        if !store.project_path().is_file() {
            return Err(ProjectRuntimeError::ProjectMissing {
                project_root: root_to_wire(&root)?,
            });
        }
        let loaded = store.load()?;
        self.register_loaded(root, store, loaded)
    }

    /// Create a project only from a fully validated history containing exactly
    /// one genesis event. The Tauri layer intentionally does not expose this
    /// method until the Genesis compiler can supply that history.
    pub fn create_from_genesis(
        &mut self,
        project_root: impl AsRef<Path>,
        history: ProjectHistory,
    ) -> Result<ProjectSession, ProjectRuntimeError> {
        if history.events().len() != 1 || !history.events()[0].is_genesis() {
            return Err(ProjectRuntimeError::CreationRequiresGenesisHistory);
        }
        history
            .replay()
            .map_err(|error| ProjectRuntimeError::InvalidHistory {
                message: error.to_string(),
            })?;

        let root = canonical_creation_directory(project_root.as_ref())?;
        if self.open_by_root.contains_key(&root) {
            let project_id = self
                .open_by_root
                .get(&root)
                .expect("presence was checked")
                .clone();
            return Err(ProjectRuntimeError::ProjectAlreadyOpen {
                project_id,
                project_root: root_to_wire(&root)?,
            });
        }
        if self
            .open_by_project_id
            .contains_key(history.context().project_id())
        {
            return Err(ProjectRuntimeError::ProjectIdentityAlreadyOpen {
                project_id: history.context().project_id().clone(),
                project_root: root_to_wire(&root)?,
            });
        }
        let store = ProjectStore::open(root.clone())?;
        let loaded = store.create_with_snapshot(history)?;
        self.register_loaded(root, store, loaded)
    }

    pub fn session(&self, project_id: &EntityId) -> Result<ProjectSession, ProjectRuntimeError> {
        self.open_by_project_id
            .get(project_id)
            .map(|project| project.session.clone())
            .ok_or_else(|| ProjectRuntimeError::UnknownProject {
                project_id: project_id.clone(),
            })
    }

    /// Reload an open project from its authoritative file. Because v1 commits
    /// immediately, no in-memory dirty state is silently discarded here.
    pub fn refresh(
        &mut self,
        project_id: &EntityId,
    ) -> Result<ProjectSession, ProjectRuntimeError> {
        let project = self.open_by_project_id.get_mut(project_id).ok_or_else(|| {
            ProjectRuntimeError::UnknownProject {
                project_id: project_id.clone(),
            }
        })?;
        let loaded = project.store.load()?;
        let session = ProjectSession::from_loaded(project.store.root(), &loaded)?;
        if &session.project_id != project_id {
            return Err(ProjectRuntimeError::ProjectIdentityMismatch {
                expected_project_id: project_id.clone(),
                actual_project_id: session.project_id,
            });
        }
        project.history = loaded.history;
        project.session = session.clone();
        Ok(session)
    }

    /// Commit a complete transaction history only if the caller still owns the
    /// version it opened. Direct `LanguageState` writes are intentionally not
    /// accepted here.
    pub fn commit_history(
        &mut self,
        project_id: &EntityId,
        expected_history_sha256: &str,
        history: ProjectHistory,
    ) -> Result<ProjectSession, ProjectRuntimeError> {
        let project = self.open_by_project_id.get_mut(project_id).ok_or_else(|| {
            ProjectRuntimeError::UnknownProject {
                project_id: project_id.clone(),
            }
        })?;
        let actual_project_id = history.context().project_id().clone();
        if &actual_project_id != project_id {
            return Err(ProjectRuntimeError::ProjectIdentityMismatch {
                expected_project_id: project_id.clone(),
                actual_project_id,
            });
        }
        let actual_run_id = history.context().run_id().clone();
        if actual_run_id != project.session.run_id {
            return Err(ProjectRuntimeError::RunIdentityMismatch {
                project_id: project_id.clone(),
                expected_run_id: project.session.run_id.clone(),
                actual_run_id,
            });
        }
        if expected_history_sha256 != project.session.history_sha256 {
            return Err(ProjectRuntimeError::WriteConflict {
                expected_history_sha256: expected_history_sha256.to_owned(),
                actual_history_sha256: Some(project.session.history_sha256.clone()),
            });
        }
        history
            .validate_extension_of(&project.history)
            .map_err(|error| ProjectRuntimeError::InvalidHistory {
                message: error.to_string(),
            })?;

        let loaded = project
            .store
            .save_if_current_with_snapshot(history, expected_history_sha256)?;
        let session = ProjectSession::from_loaded(project.store.root(), &loaded)?;
        project.history = loaded.history;
        project.session = session.clone();
        Ok(session)
    }

    pub fn close(&mut self, project_id: &EntityId) -> Result<ProjectSession, ProjectRuntimeError> {
        let project = self.open_by_project_id.remove(project_id).ok_or_else(|| {
            ProjectRuntimeError::UnknownProject {
                project_id: project_id.clone(),
            }
        })?;
        self.open_by_root.remove(project.store.root());
        Ok(project.session)
    }

    fn register_loaded(
        &mut self,
        root: PathBuf,
        store: ProjectStore,
        loaded: LoadedProject,
    ) -> Result<ProjectSession, ProjectRuntimeError> {
        let session = ProjectSession::from_loaded(&root, &loaded)?;
        if self.open_by_project_id.contains_key(&session.project_id) {
            return Err(ProjectRuntimeError::ProjectIdentityAlreadyOpen {
                project_id: session.project_id.clone(),
                project_root: session.project_root,
            });
        }
        self.open_by_root.insert(root, session.project_id.clone());
        self.open_by_project_id.insert(
            session.project_id.clone(),
            OpenProject {
                store,
                history: loaded.history,
                session: session.clone(),
            },
        );
        Ok(session)
    }
}

fn canonical_existing_directory(root: &Path) -> Result<PathBuf, ProjectRuntimeError> {
    if root.as_os_str().is_empty() {
        return Err(ProjectRuntimeError::InvalidProjectRoot {
            message: "project root must not be empty".to_owned(),
        });
    }
    let canonical =
        fs::canonicalize(root).map_err(|error| ProjectRuntimeError::InvalidProjectRoot {
            message: format!("cannot resolve project root {}: {error}", root.display()),
        })?;
    if !canonical.is_dir() {
        return Err(ProjectRuntimeError::InvalidProjectRoot {
            message: format!("project root {} is not a directory", canonical.display()),
        });
    }
    Ok(canonical)
}

fn canonical_creation_directory(root: &Path) -> Result<PathBuf, ProjectRuntimeError> {
    if root.as_os_str().is_empty() {
        return Err(ProjectRuntimeError::InvalidProjectRoot {
            message: "project root must not be empty".to_owned(),
        });
    }
    fs::create_dir_all(root).map_err(|error| ProjectRuntimeError::InvalidProjectRoot {
        message: format!("cannot create project root {}: {error}", root.display()),
    })?;
    canonical_existing_directory(root)
}

fn root_to_wire(root: &Path) -> Result<String, ProjectRuntimeError> {
    root.to_str()
        .map(str::to_owned)
        .ok_or_else(|| ProjectRuntimeError::InvalidProjectRoot {
            message: format!(
                "project root {} cannot be represented as a UTF-8 command value",
                root.display()
            ),
        })
}
