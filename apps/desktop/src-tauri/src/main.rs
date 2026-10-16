use std::{
    collections::BTreeSet,
    fs,
    path::{Path, PathBuf},
    sync::{Arc, Mutex},
    thread,
    time::Duration,
};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use tauri::{Emitter, Manager};
use telysta_application::{
    inspect_blueprint, ProjectApplication, ProjectRuntimeError, ProjectSession,
};
use telysta_core::{
    blueprint::{BlueprintError, BlueprintValidationReport, LanguageBlueprint},
    CancelResult, CommandResponse, DemoCheckpoint, DemoEngine, DemoProgress, DemoRun,
    DemoRunStatus, EngineEvent, EngineInfo,
};

const DESKTOP_CHECKPOINT_SCHEMA: &str = "telysta-desktop-demo-checkpoint.v1";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct StoredCheckpoint {
    schema_version: String,
    checksum: String,
    checkpoint: DemoCheckpoint,
}

impl StoredCheckpoint {
    fn from_checkpoint(checkpoint: DemoCheckpoint) -> Result<Self, String> {
        let payload = serde_json::to_vec(&checkpoint)
            .map_err(|error| format!("failed to encode checkpoint payload: {error}"))?;
        Ok(Self {
            schema_version: DESKTOP_CHECKPOINT_SCHEMA.to_owned(),
            checksum: sha256_hex(&payload),
            checkpoint,
        })
    }

    fn into_checkpoint(self) -> Result<DemoCheckpoint, String> {
        if self.schema_version != DESKTOP_CHECKPOINT_SCHEMA {
            return Err(format!(
                "unsupported desktop checkpoint schema: {}",
                self.schema_version
            ));
        }
        let payload = serde_json::to_vec(&self.checkpoint)
            .map_err(|error| format!("failed to encode checkpoint payload: {error}"))?;
        if self.checksum != sha256_hex(&payload) {
            return Err("desktop checkpoint checksum mismatch".to_owned());
        }
        Ok(self.checkpoint)
    }
}

#[derive(Clone)]
struct DesktopState {
    engine: Arc<Mutex<DemoEngine>>,
    checkpoint_base: Arc<PathBuf>,
    checkpoint_write_lock: Arc<Mutex<()>>,
    active_workers: Arc<Mutex<BTreeSet<String>>>,
    projects: Arc<Mutex<ProjectApplication>>,
}

struct WorkerLease {
    active_workers: Arc<Mutex<BTreeSet<String>>>,
    run_id: String,
}

impl Drop for WorkerLease {
    fn drop(&mut self) {
        if let Ok(mut active_workers) = self.active_workers.lock() {
            active_workers.remove(&self.run_id);
        }
    }
}

impl DesktopState {
    fn load(checkpoint_base: PathBuf) -> Result<Self, String> {
        Ok(Self {
            engine: Arc::new(Mutex::new(load_latest_checkpoint(&checkpoint_base)?)),
            checkpoint_base: Arc::new(checkpoint_base),
            checkpoint_write_lock: Arc::new(Mutex::new(())),
            active_workers: Arc::new(Mutex::new(BTreeSet::new())),
            projects: Arc::new(Mutex::new(ProjectApplication::default())),
        })
    }

    fn persist(&self) -> Result<(), String> {
        let _write_lock = self
            .checkpoint_write_lock
            .lock()
            .map_err(|_| "checkpoint write lock poisoned".to_owned())?;
        let checkpoint = self
            .engine
            .lock()
            .map_err(|_| "engine state lock poisoned".to_owned())?
            .checkpoint();
        let envelope = StoredCheckpoint::from_checkpoint(checkpoint.clone())?;
        let encoded = serde_json::to_vec_pretty(&envelope)
            .map_err(|error| format!("failed to encode desktop checkpoint: {error}"))?;
        let checkpoint_path = checkpoint_slot(&self.checkpoint_base, checkpoint.revision);
        atomic_replace(&checkpoint_path, &encoded)
    }

    fn start_demo(&self, run_id: String, seed: u64) -> Result<DemoRun, String> {
        let run = self
            .engine
            .lock()
            .map_err(|_| "engine state lock poisoned".to_owned())?
            .start_demo(run_id, seed)
            .map_err(|error| error.to_string())?;
        self.persist()?;
        Ok(run)
    }

    fn advance_demo(&self, run_id: &str) -> Result<Option<DemoProgress>, String> {
        self.engine
            .lock()
            .map_err(|_| "engine state lock poisoned".to_owned())
            .map(|mut engine| engine.advance_demo(run_id))
    }

    fn cancel(&self, run_id: String) -> Result<CancelResult, String> {
        let result = self
            .engine
            .lock()
            .map_err(|_| "engine state lock poisoned".to_owned())?
            .cancel(run_id);
        self.persist()?;
        Ok(result)
    }

    fn engine_info(&self) -> Result<EngineInfo, String> {
        self.engine
            .lock()
            .map_err(|_| "engine state lock poisoned".to_owned())
            .map(|engine| engine.engine_info())
    }

    fn recoverable_runs(&self) -> Result<Vec<DemoRun>, String> {
        self.engine
            .lock()
            .map_err(|_| "engine state lock poisoned".to_owned())
            .map(|engine| engine.recoverable_runs())
    }

    fn open_project(&self, project_root: String) -> Result<ProjectSession, ProjectRuntimeError> {
        self.projects
            .lock()
            .map_err(|_| ProjectRuntimeError::Storage {
                message: "project application lock poisoned".to_owned(),
            })?
            .open_project(PathBuf::from(project_root))
    }

    fn project_session(
        &self,
        project_id: &telysta_core::identity::EntityId,
    ) -> Result<ProjectSession, ProjectRuntimeError> {
        self.projects
            .lock()
            .map_err(|_| ProjectRuntimeError::Storage {
                message: "project application lock poisoned".to_owned(),
            })?
            .get_project_session(project_id)
    }

    fn refresh_project(
        &self,
        project_id: &telysta_core::identity::EntityId,
    ) -> Result<ProjectSession, ProjectRuntimeError> {
        self.projects
            .lock()
            .map_err(|_| ProjectRuntimeError::Storage {
                message: "project application lock poisoned".to_owned(),
            })?
            .refresh_project(project_id)
    }

    fn close_project(
        &self,
        project_id: &telysta_core::identity::EntityId,
    ) -> Result<ProjectSession, ProjectRuntimeError> {
        self.projects
            .lock()
            .map_err(|_| ProjectRuntimeError::Storage {
                message: "project application lock poisoned".to_owned(),
            })?
            .close_project(project_id)
    }

    fn claim_worker(&self, run_id: &str) -> Result<Option<WorkerLease>, String> {
        let mut active_workers = self
            .active_workers
            .lock()
            .map_err(|_| "active worker registry lock poisoned".to_owned())?;
        if !active_workers.insert(run_id.to_owned()) {
            return Ok(None);
        }
        Ok(Some(WorkerLease {
            active_workers: Arc::clone(&self.active_workers),
            run_id: run_id.to_owned(),
        }))
    }
}

#[tauri::command]
fn engine_info(
    state: tauri::State<'_, DesktopState>,
) -> Result<CommandResponse<EngineInfo>, String> {
    state
        .engine_info()
        .map(|info| CommandResponse::new("engine_info", info))
}

#[tauri::command]
fn run_demo(
    app: tauri::AppHandle,
    state: tauri::State<'_, DesktopState>,
    run_id: String,
    seed: u64,
) -> Result<CommandResponse<DemoRun>, String> {
    let run = state.start_demo(run_id, seed)?;
    if run.status == DemoRunStatus::Running {
        spawn_demo_worker(app, state.inner().clone(), run.run_id.clone())?;
    }
    Ok(CommandResponse::new("run_demo", run))
}

#[tauri::command]
fn cancel_run(
    app: tauri::AppHandle,
    state: tauri::State<'_, DesktopState>,
    run_id: String,
) -> Result<CommandResponse<CancelResult>, String> {
    let result = state.cancel(run_id)?;
    if result.accepted {
        app.emit(
            "engine://cancelled",
            EngineEvent::new("engine://cancelled", result.clone()),
        )
        .map_err(|error| format!("failed to emit cancellation: {error}"))?;
    }
    Ok(CommandResponse::new("cancel_run", result))
}

#[tauri::command]
fn recover_pending_runs(
    app: tauri::AppHandle,
    state: tauri::State<'_, DesktopState>,
) -> Result<CommandResponse<Vec<DemoRun>>, String> {
    let runs = state.recoverable_runs()?;
    for run in &runs {
        spawn_demo_worker(app.clone(), state.inner().clone(), run.run_id.clone())?;
    }
    Ok(CommandResponse::new("recover_pending_runs", runs))
}

/// Open an existing official project. Creation is intentionally absent until
/// the Genesis compiler can supply a complete, validated genesis history.
#[tauri::command]
fn open_project(
    state: tauri::State<'_, DesktopState>,
    project_root: String,
) -> Result<CommandResponse<ProjectSession>, ProjectRuntimeError> {
    state
        .open_project(project_root)
        .map(|session| CommandResponse::new("open_project", session))
}

#[tauri::command]
fn get_project_session(
    state: tauri::State<'_, DesktopState>,
    project_id: telysta_core::identity::EntityId,
) -> Result<CommandResponse<ProjectSession>, ProjectRuntimeError> {
    state
        .project_session(&project_id)
        .map(|session| CommandResponse::new("get_project_session", session))
}

#[tauri::command]
fn refresh_project(
    state: tauri::State<'_, DesktopState>,
    project_id: telysta_core::identity::EntityId,
) -> Result<CommandResponse<ProjectSession>, ProjectRuntimeError> {
    state
        .refresh_project(&project_id)
        .map(|session| CommandResponse::new("refresh_project", session))
}

#[tauri::command]
fn close_project(
    state: tauri::State<'_, DesktopState>,
    project_id: telysta_core::identity::EntityId,
) -> Result<CommandResponse<ProjectSession>, ProjectRuntimeError> {
    state
        .close_project(&project_id)
        .map(|session| CommandResponse::new("close_project", session))
}

#[tauri::command]
fn validate_blueprint(
    blueprint: Option<LanguageBlueprint>,
    blueprint_json: Option<String>,
) -> Result<CommandResponse<BlueprintValidationReport>, BlueprintError> {
    inspect_blueprint(blueprint, blueprint_json)
}

fn spawn_demo_worker(
    app: tauri::AppHandle,
    state: DesktopState,
    run_id: String,
) -> Result<(), String> {
    let Some(_lease) = state.claim_worker(&run_id)? else {
        return Ok(());
    };
    thread::spawn(move || {
        let _lease = _lease;
        loop {
            let progress = match state.advance_demo(&run_id) {
                Ok(progress) => progress,
                Err(error) => {
                    eprintln!("demo worker failed for {run_id}: {error}");
                    return;
                }
            };
            let Some(progress) = progress else {
                if let Err(error) = state.persist() {
                    eprintln!("failed to persist terminal demo state for {run_id}: {error}");
                }
                return;
            };

            if let Err(error) = state.persist() {
                eprintln!("failed to persist demo progress for {run_id}: {error}");
                return;
            }
            if let Err(error) = app.emit(
                "engine://progress",
                EngineEvent::new("engine://progress", progress),
            ) {
                eprintln!("failed to emit demo progress for {run_id}: {error}");
                return;
            }
            thread::sleep(Duration::from_millis(30));
        }
    });
    Ok(())
}

fn checkpoint_slot(base: &Path, revision: u64) -> PathBuf {
    base.with_extension(format!("{}.json", revision % 2))
}

fn atomic_replace(path: &Path, contents: &[u8]) -> Result<(), String> {
    let extension = path
        .extension()
        .and_then(|value| value.to_str())
        .unwrap_or("tmp");
    let temporary = path.with_extension(format!("{extension}.tmp"));
    fs::write(&temporary, contents).map_err(|error| {
        format!(
            "failed to write temporary checkpoint {}: {error}",
            temporary.display()
        )
    })?;

    if path.exists() {
        fs::remove_file(path).map_err(|error| {
            let _ = fs::remove_file(&temporary);
            format!("failed to replace checkpoint {}: {error}", path.display())
        })?;
    }
    fs::rename(&temporary, path).map_err(|error| {
        let _ = fs::remove_file(&temporary);
        format!("failed to finalize checkpoint {}: {error}", path.display())
    })
}

fn load_latest_checkpoint(base: &Path) -> Result<DemoEngine, String> {
    let mut valid_checkpoints = Vec::<DemoEngine>::new();
    let mut invalid_slots = Vec::<String>::new();

    for slot in 0..=1 {
        let path = base.with_extension(format!("{slot}.json"));
        if !path.exists() {
            continue;
        }
        match fs::read(&path)
            .map_err(|error| error.to_string())
            .and_then(|bytes| {
                serde_json::from_slice::<StoredCheckpoint>(&bytes)
                    .map_err(|error| error.to_string())
            })
            .and_then(|stored| stored.into_checkpoint())
            .and_then(|checkpoint| {
                DemoEngine::from_checkpoint(checkpoint).map_err(|error| error.to_string())
            }) {
            Ok(engine) => valid_checkpoints.push(engine),
            Err(error) => invalid_slots.push(format!("{} ({error})", path.display())),
        }
    }

    if let Some(engine) = valid_checkpoints
        .into_iter()
        .max_by_key(|engine| engine.checkpoint().revision)
    {
        return Ok(engine);
    }
    if invalid_slots.is_empty() {
        Ok(DemoEngine::default())
    } else {
        Err(format!(
            "no valid demo checkpoint is available: {}",
            invalid_slots.join(", ")
        ))
    }
}

fn sha256_hex(bytes: &[u8]) -> String {
    Sha256::digest(bytes)
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let app_data_dir = app
                .path()
                .app_data_dir()
                .map_err(|error| format!("failed to resolve app-data directory: {error}"))?;
            fs::create_dir_all(&app_data_dir)
                .map_err(|error| format!("failed to create app-data directory: {error}"))?;
            app.manage(DesktopState::load(app_data_dir.join("demo-checkpoint"))?);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            engine_info,
            run_demo,
            cancel_run,
            recover_pending_runs,
            open_project,
            get_project_session,
            refresh_project,
            close_project,
            validate_blueprint
        ])
        .run(tauri::generate_context!())
        .expect("error while running Telysta desktop application");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stored_checkpoint_rejects_a_modified_payload() {
        let mut engine = DemoEngine::default();
        engine.start_demo("checkpoint-test", 7).expect("run");
        let mut stored =
            StoredCheckpoint::from_checkpoint(engine.checkpoint()).expect("checkpoint");
        stored.checkpoint.revision += 1;

        assert!(stored.into_checkpoint().is_err());
    }

    #[test]
    fn worker_claim_is_idempotent_until_the_worker_finishes() {
        let state = DesktopState {
            engine: Arc::new(Mutex::new(DemoEngine::default())),
            checkpoint_base: Arc::new(PathBuf::from("unused-in-test")),
            checkpoint_write_lock: Arc::new(Mutex::new(())),
            active_workers: Arc::new(Mutex::new(BTreeSet::new())),
            projects: Arc::new(Mutex::new(ProjectApplication::default())),
        };

        let lease = state.claim_worker("run-id").expect("claim");
        assert!(lease.is_some());
        assert!(state
            .claim_worker("run-id")
            .expect("second claim")
            .is_none());
        drop(lease);
        assert!(state
            .claim_worker("run-id")
            .expect("claim after release")
            .is_some());
    }
}
