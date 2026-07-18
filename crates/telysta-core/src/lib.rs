//! Minimal Rust-native contract for the A-005 desktop shell.
//!
//! This crate deliberately does not mirror the Python `EngineHotState`.
//! It establishes a deterministic command boundary alongside the production
//! `LanguageState`, `RunContext`, project transaction, and event contracts.

pub mod blueprint;
pub mod data;
pub mod hash;
pub mod identity;
pub mod project;
pub mod rng;
pub mod state;
pub mod time;

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

pub const ENGINE_API_VERSION: &str = "telysta-engine-api.v1";
pub const ENGINE_VERSION: &str = env!("CARGO_PKG_VERSION");
pub const DEMO_CHECKPOINT_SCHEMA: &str = "telysta-demo-checkpoint.v1";

const DEMO_PHASES: [&str; 3] = ["validate_input", "derive_rng", "complete"];

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CommandResponse<T> {
    pub api_version: &'static str,
    pub command: &'static str,
    pub data: T,
}

impl<T> CommandResponse<T> {
    pub fn new(command: &'static str, data: T) -> Self {
        Self {
            api_version: ENGINE_API_VERSION,
            command,
            data,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct EngineEvent<T> {
    pub api_version: &'static str,
    pub event_type: &'static str,
    pub data: T,
}

impl<T> EngineEvent<T> {
    pub fn new(event_type: &'static str, data: T) -> Self {
        Self {
            api_version: ENGINE_API_VERSION,
            event_type,
            data,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct EngineInfo {
    pub api_version: &'static str,
    pub engine_version: &'static str,
    pub runtime: &'static str,
    pub python_runtime_required: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DemoProgress {
    pub run_id: String,
    pub current_step: u8,
    pub total_steps: u8,
    pub phase: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum DemoRunStatus {
    Running,
    Completed,
    Cancelled,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DemoRun {
    pub run_id: String,
    pub seed: u64,
    pub status: DemoRunStatus,
    pub current_step: u8,
    pub total_steps: u8,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CancelResult {
    pub run_id: String,
    pub accepted: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DemoEngineError {
    InvalidRunId(String),
    RunIdSeedConflict {
        run_id: String,
        existing_seed: u64,
        requested_seed: u64,
    },
    InvalidCheckpoint(String),
}

impl std::fmt::Display for DemoEngineError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::InvalidRunId(run_id) => write!(
                formatter,
                "invalid run ID {run_id:?}; use 1-128 ASCII letters, digits, hyphens, or underscores"
            ),
            Self::RunIdSeedConflict {
                run_id,
                existing_seed,
                requested_seed,
            } => write!(
                formatter,
                "run ID {run_id:?} already belongs to seed {existing_seed}, not requested seed {requested_seed}"
            ),
            Self::InvalidCheckpoint(message) => formatter.write_str(message),
        }
    }
}

impl std::error::Error for DemoEngineError {}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DemoCheckpoint {
    pub schema_version: String,
    pub revision: u64,
    pub runs: BTreeMap<String, DemoRun>,
}

#[derive(Debug, Default)]
pub struct DemoEngine {
    revision: u64,
    runs: BTreeMap<String, DemoRun>,
}

impl DemoEngine {
    pub fn engine_info(&self) -> EngineInfo {
        EngineInfo {
            api_version: ENGINE_API_VERSION,
            engine_version: ENGINE_VERSION,
            runtime: "rust-native",
            python_runtime_required: false,
        }
    }

    /// Start a run using a caller-supplied idempotency key.
    ///
    /// Retrying the same command with the same key and seed returns the
    /// existing run; reusing the key for another seed is rejected.
    pub fn start_demo(
        &mut self,
        run_id: impl Into<String>,
        seed: u64,
    ) -> Result<DemoRun, DemoEngineError> {
        let run_id = run_id.into();
        validate_run_id(&run_id)?;
        if let Some(existing) = self.runs.get(&run_id) {
            if existing.seed == seed {
                return Ok(existing.clone());
            }
            return Err(DemoEngineError::RunIdSeedConflict {
                run_id,
                existing_seed: existing.seed,
                requested_seed: seed,
            });
        }

        let run = DemoRun {
            run_id,
            seed,
            status: DemoRunStatus::Running,
            current_step: 0,
            total_steps: DEMO_PHASES.len() as u8,
        };
        self.runs.insert(run.run_id.clone(), run.clone());
        self.bump_revision();
        Ok(run)
    }

    pub fn advance_demo(&mut self, run_id: &str) -> Option<DemoProgress> {
        let run = self.runs.get_mut(run_id)?;
        if run.status != DemoRunStatus::Running {
            return None;
        }

        let phase = DEMO_PHASES.get(run.current_step as usize)?;
        run.current_step += 1;
        let progress = DemoProgress {
            run_id: run.run_id.clone(),
            current_step: run.current_step,
            total_steps: run.total_steps,
            phase: (*phase).to_owned(),
        };
        if run.current_step == run.total_steps {
            run.status = DemoRunStatus::Completed;
        }
        self.bump_revision();
        Some(progress)
    }

    pub fn cancel(&mut self, run_id: impl Into<String>) -> CancelResult {
        let run_id = run_id.into();
        let accepted = self.runs.get_mut(&run_id).is_some_and(|run| {
            if run.status != DemoRunStatus::Running {
                return false;
            }
            run.status = DemoRunStatus::Cancelled;
            true
        });
        if accepted {
            self.bump_revision();
        }
        CancelResult { run_id, accepted }
    }

    pub fn checkpoint(&self) -> DemoCheckpoint {
        DemoCheckpoint {
            schema_version: DEMO_CHECKPOINT_SCHEMA.to_owned(),
            revision: self.revision,
            runs: self.runs.clone(),
        }
    }

    pub fn from_checkpoint(checkpoint: DemoCheckpoint) -> Result<Self, DemoEngineError> {
        if checkpoint.schema_version != DEMO_CHECKPOINT_SCHEMA {
            return Err(DemoEngineError::InvalidCheckpoint(format!(
                "unsupported checkpoint schema: {}",
                checkpoint.schema_version
            )));
        }

        for (run_id, run) in &checkpoint.runs {
            if run_id != &run.run_id {
                return Err(DemoEngineError::InvalidCheckpoint(format!(
                    "checkpoint key does not match demo run identifier: {run_id}"
                )));
            }
            if let Err(error) = validate_run_id(run_id) {
                return Err(DemoEngineError::InvalidCheckpoint(error.to_string()));
            }
            if run.total_steps != DEMO_PHASES.len() as u8 || run.current_step > run.total_steps {
                return Err(DemoEngineError::InvalidCheckpoint(format!(
                    "invalid progress state for demo run: {run_id}"
                )));
            }
            if run.status == DemoRunStatus::Running && run.current_step == run.total_steps {
                return Err(DemoEngineError::InvalidCheckpoint(format!(
                    "unfinished demo run has no remaining work: {run_id}"
                )));
            }
        }

        Ok(Self {
            revision: checkpoint.revision,
            runs: checkpoint.runs,
        })
    }

    pub fn recoverable_runs(&self) -> Vec<DemoRun> {
        self.runs
            .values()
            .filter(|run| run.status == DemoRunStatus::Running)
            .cloned()
            .collect()
    }

    fn bump_revision(&mut self) {
        self.revision = self.revision.saturating_add(1);
    }
}

fn validate_run_id(run_id: &str) -> Result<(), DemoEngineError> {
    let valid = !run_id.is_empty()
        && run_id.len() <= 128
        && run_id
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || byte == b'-' || byte == b'_');
    if valid {
        Ok(())
    } else {
        Err(DemoEngineError::InvalidRunId(run_id.to_owned()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn engine_info_declares_rust_native_runtime() {
        let info = DemoEngine::default().engine_info();
        assert_eq!(info.api_version, ENGINE_API_VERSION);
        assert_eq!(info.runtime, "rust-native");
        assert!(!info.python_runtime_required);
    }

    #[test]
    fn same_seed_produces_same_demo_contract() {
        let mut first = DemoEngine::default();
        let mut second = DemoEngine::default();
        assert_eq!(
            first.start_demo("run-888", 888),
            second.start_demo("run-888", 888)
        );
    }

    #[test]
    fn a_cancelled_run_stops_future_progress() {
        let mut engine = DemoEngine::default();
        let run = engine.start_demo("cancel-me", 888).expect("run");
        assert!(engine.cancel(run.run_id.clone()).accepted);
        assert_eq!(engine.advance_demo(&run.run_id), None);
    }

    #[test]
    fn progress_contract_has_ordered_steps() {
        let mut engine = DemoEngine::default();
        let run = engine.start_demo("ordered-progress", 7).expect("run");
        let first = engine
            .advance_demo(&run.run_id)
            .expect("first progress event");
        engine
            .advance_demo(&run.run_id)
            .expect("second progress event");
        let final_step = engine
            .advance_demo(&run.run_id)
            .expect("final progress event");

        assert_eq!(first.current_step, 1);
        assert_eq!(final_step.current_step, 3);
        assert_eq!(final_step.phase, "complete");
        assert_eq!(engine.runs[&run.run_id].status, DemoRunStatus::Completed);
    }

    #[test]
    fn checkpoint_restores_an_interrupted_run() {
        let mut original = DemoEngine::default();
        let run = original.start_demo("restore-me", 42).expect("run");
        original
            .advance_demo(&run.run_id)
            .expect("first progress event");

        let mut recovered = DemoEngine::from_checkpoint(original.checkpoint()).expect("checkpoint");
        assert_eq!(
            recovered.recoverable_runs(),
            vec![original.runs[&run.run_id].clone()]
        );
        assert_eq!(
            recovered
                .advance_demo(&run.run_id)
                .expect("second progress event")
                .current_step,
            2
        );
        recovered
            .advance_demo(&run.run_id)
            .expect("final progress event");
        assert!(recovered.recoverable_runs().is_empty());
    }

    #[test]
    fn response_and_event_envelopes_are_versioned() {
        let response = CommandResponse::new("engine_info", DemoEngine::default().engine_info());
        let event = EngineEvent::new(
            "engine://progress",
            DemoProgress {
                run_id: "demo-0000000000000001".to_owned(),
                current_step: 1,
                total_steps: 3,
                phase: "validate_input".to_owned(),
            },
        );

        assert_eq!(response.api_version, ENGINE_API_VERSION);
        assert_eq!(event.api_version, ENGINE_API_VERSION);
        assert_eq!(event.event_type, "engine://progress");
    }

    #[test]
    fn run_id_is_idempotent_and_never_overwrites_a_different_seed() {
        let mut engine = DemoEngine::default();
        let first = engine.start_demo("retry-key", 11).expect("first run");
        assert_eq!(engine.start_demo("retry-key", 11), Ok(first.clone()));
        assert!(matches!(
            engine.start_demo("retry-key", 12),
            Err(DemoEngineError::RunIdSeedConflict { .. })
        ));
        assert!(matches!(
            engine.start_demo("invalid run id", 11),
            Err(DemoEngineError::InvalidRunId(_))
        ));
    }
}
