//! Immutable input declarations, not execution or commit capabilities (ADR-011 §14).
//!
//! Hashes and parent locks are checked here. Dependency availability, command
//! validity, registration, approval and staging require the application layer.
//! No OperationContext, writer, worker or legacy migration is provided.
//!
//! ```compile_fail
//! use telysta_core::operation::OperationSpec;
//! fn change(spec: &mut OperationSpec) { spec.request.target_history.clear(); }
//! ```
//!
//! ```compile_fail
//! use telysta_core::operation::RunSpec;
//! let _ = serde_json::from_str::<RunSpec>("{}"); // A parent is required.
//! ```

use std::{collections::BTreeSet, error::Error, fmt};

use serde::{Deserialize, Deserializer, Serialize, Serializer};

use crate::{
    execution_identity::{OperationId, ProjectId, RunId, EXECUTION_ID_SCHEMA},
    hash::sha256_hex,
    rng::{RngPath, RNG_TREE_SCHEMA},
    time::{SimYear, TimeModel, TimeReference, TIME_MODEL_SCHEMA},
};

pub const OPERATION_REQUEST_SCHEMA: &str = "telysta-operation-request.v1";
pub const OPERATION_SPEC_SCHEMA: &str = "telysta-operation-spec.v2";
pub const RUN_SPEC_SCHEMA: &str = "telysta-run-spec.v2";
pub const OPERATION_INPUT_HASH_SCHEMA: &str = "telysta-operation-input-hash.v1";
pub const RAW_DISTRIBUTION_VERSION: &str = "telysta-rng-next-u64.v1";
pub const UNIFORM_DISTRIBUTION_VERSION: &str = "telysta-rng-uniform-u64.v1";
pub const MAX_SAFE_DRAW_BUDGET: u64 = (1 << 53) - 1;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OperationInputError {
    pub code: &'static str,
    pub field: String,
    pub message: String,
}

impl fmt::Display for OperationInputError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{} at {}: {}", self.code, self.field, self.message)
    }
}

impl Error for OperationInputError {}

fn invalid(
    code: &'static str,
    field: impl Into<String>,
    message: impl Into<String>,
) -> OperationInputError {
    OperationInputError {
        code,
        field: field.into(),
        message: message.into(),
    }
}

fn nonblank(value: &str, field: &str) -> Result<(), OperationInputError> {
    if value.trim().is_empty() {
        Err(invalid(
            "invalid_operation_input",
            field,
            "must not be blank",
        ))
    } else {
        Ok(())
    }
}

fn hash_value(value: &str, field: &str) -> Result<(), OperationInputError> {
    if value.len() != 64
        || !value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    {
        return Err(invalid(
            "invalid_content_hash",
            field,
            "expected lowercase SHA-256",
        ));
    }
    Ok(())
}

fn schema(value: &str, field: &str) -> Result<(), OperationInputError> {
    let valid = value
        .strip_prefix("telysta-")
        .and_then(|s| s.rsplit_once(".v"))
        .is_some_and(|(name, version)| {
            !name.is_empty()
                && !version.is_empty()
                && name
                    .bytes()
                    .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'-')
                && version.bytes().all(|b| b.is_ascii_digit())
        });
    if valid {
        Ok(())
    } else {
        Err(invalid(
            "invalid_schema_identifier",
            field,
            "expected telysta-<name>.v<digits>",
        ))
    }
}

/// Lossless target wire encoding. Does not change legacy RunContext or RNG.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RootSeed(u64);

impl RootSeed {
    pub const fn new(value: u64) -> Self {
        Self(value)
    }
    pub const fn get(self) -> u64 {
        self.0
    }
}

impl Serialize for RootSeed {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        serializer.serialize_str(&self.0.to_string())
    }
}

impl<'de> Deserialize<'de> for RootSeed {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        let text = String::deserialize(deserializer)?;
        let value = text.parse::<u64>().map_err(serde::de::Error::custom)?;
        if value.to_string() != text {
            return Err(serde::de::Error::custom(
                "rootSeed must be canonical ASCII unsigned decimal",
            ));
        }
        Ok(Self(value))
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ContentLock {
    pub schema_version: String,
    pub content_sha256: String,
}

impl ContentLock {
    fn validate(&self, field: &str) -> Result<(), OperationInputError> {
        schema(&self.schema_version, &format!("{field}.schemaVersion"))?;
        hash_value(&self.content_sha256, &format!("{field}.contentSha256"))
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OperationKind {
    Genesis,
    Authoring,
    Simulation,
    Migration,
    Retcon,
    Import,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(
    tag = "kind",
    rename_all = "snake_case",
    rename_all_fields = "camelCase",
    deny_unknown_fields
)]
pub enum BaseHistory {
    Empty {},
    Existing { history_sha256: String },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct TimeLock {
    pub schema_version: String,
    pub origin_year: i32,
    pub generation_years: u16,
    pub step_years: u16,
    pub at_year: i32,
}

impl TimeLock {
    pub fn time_model(&self) -> Result<TimeModel, OperationInputError> {
        if self.schema_version != TIME_MODEL_SCHEMA {
            return Err(invalid(
                "unsupported_time_schema",
                "request.time.schemaVersion",
                "expected TimeModel v2",
            ));
        }
        TimeModel::new(
            SimYear(self.origin_year),
            self.generation_years,
            self.step_years,
        )
        .map_err(|e| invalid("invalid_time_lock", "request.time", e.to_string()))
    }

    pub fn time_reference(&self) -> Result<TimeReference, OperationInputError> {
        Ok(self.time_model()?.time_reference(SimYear(self.at_year)))
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct StreamBudget {
    pub relative_path: String,
    pub max_raw_draws: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(
    tag = "kind",
    rename_all = "snake_case",
    rename_all_fields = "camelCase",
    deny_unknown_fields
)]
pub enum RngLock {
    NoRng {},
    RngTree {
        schema_version: String,
        root_seed: RootSeed,
        path_root: String,
        distribution_version: String,
        stream_budgets: Vec<StreamBudget>,
    },
}

impl RngLock {
    fn validate(&self) -> Result<(), OperationInputError> {
        if let Self::RngTree {
            schema_version,
            path_root,
            distribution_version,
            stream_budgets,
            ..
        } = self
        {
            if schema_version != RNG_TREE_SCHEMA {
                return Err(invalid(
                    "unsupported_rng_schema",
                    "rngLock.schemaVersion",
                    "unknown tree version",
                ));
            }
            if !matches!(
                distribution_version.as_str(),
                RAW_DISTRIBUTION_VERSION | UNIFORM_DISTRIBUTION_VERSION
            ) {
                return Err(invalid(
                    "unsupported_rng_distribution",
                    "rngLock.distributionVersion",
                    "unknown distribution",
                ));
            }
            RngPath::parse(path_root)
                .map_err(|e| invalid("invalid_rng_path", "rngLock.pathRoot", e.to_string()))?;
            if stream_budgets.is_empty() {
                return Err(invalid(
                    "missing_rng_budget",
                    "rngLock.streamBudgets",
                    "declare at least one stream",
                ));
            }
            let mut paths = BTreeSet::new();
            for budget in stream_budgets {
                RngPath::parse(&budget.relative_path).map_err(|e| {
                    invalid(
                        "invalid_rng_path",
                        "rngLock.streamBudgets.relativePath",
                        e.to_string(),
                    )
                })?;
                if !paths.insert(&budget.relative_path) {
                    return Err(invalid(
                        "duplicate_rng_path",
                        "rngLock.streamBudgets",
                        "duplicate relative stream path",
                    ));
                }
                if budget.max_raw_draws > MAX_SAFE_DRAW_BUDGET {
                    return Err(invalid(
                        "invalid_rng_budget",
                        "rngLock.streamBudgets.maxRawDraws",
                        "budget exceeds safe integer policy",
                    ));
                }
            }
        }
        Ok(())
    }

    fn for_run(&self, role: RunRole, key: &str) -> Self {
        let mut inherited = self.clone();
        if let Self::RngTree { path_root, .. } = &mut inherited {
            path_root.push('.');
            path_root.push_str(role.as_str());
            path_root.push('.');
            path_root.push_str(key);
        }
        inherited
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ActorKind {
    User,
    Migration,
    System,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ActorProvenance {
    pub kind: ActorKind,
    pub actor_id: String,
    pub source: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum AuthorIntervention {
    None {},
    Recorded { report: ContentLock },
}

/// Untrusted input data. Only OperationSpec freezes and checks this declaration;
/// neither type verifies referenced payloads, approval or execution eligibility.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct OperationRequest {
    pub schema_version: String,
    pub identity_schema: String,
    pub project_id: ProjectId,
    pub kind: OperationKind,
    pub target_history: String,
    pub base_history: BaseHistory,
    pub command_schema: String,
    pub command_payload_sha256: String,
    pub parameter_sha256: String,
    pub engine_version: String,
    pub compiler_version: String,
    pub reducer_version: String,
    pub dependency_bundle: ContentLock,
    pub time: TimeLock,
    pub rng_lock: RngLock,
    pub actor_provenance: ActorProvenance,
    pub author_intervention: AuthorIntervention,
}

impl OperationRequest {
    fn validate(&self) -> Result<(), OperationInputError> {
        if self.schema_version != OPERATION_REQUEST_SCHEMA
            || self.identity_schema != EXECUTION_ID_SCHEMA
        {
            return Err(invalid(
                "unsupported_operation_schema",
                "request",
                "unknown request or identity schema",
            ));
        }
        match (&self.base_history, self.kind) {
            (BaseHistory::Empty {}, OperationKind::Genesis | OperationKind::Import) => {}
            (BaseHistory::Existing { history_sha256 }, kind) if kind != OperationKind::Genesis => {
                hash_value(history_sha256, "request.baseHistory.historySha256")?
            }
            _ => {
                return Err(invalid(
                    "invalid_history_base",
                    "request.baseHistory",
                    "base is incompatible with operation kind",
                ))
            }
        }
        nonblank(&self.target_history, "request.targetHistory")?;
        schema(&self.command_schema, "request.commandSchema")?;
        hash_value(&self.command_payload_sha256, "request.commandPayloadSha256")?;
        hash_value(&self.parameter_sha256, "request.parameterSha256")?;
        nonblank(&self.engine_version, "request.engineVersion")?;
        nonblank(&self.compiler_version, "request.compilerVersion")?;
        nonblank(&self.reducer_version, "request.reducerVersion")?;
        self.dependency_bundle
            .validate("request.dependencyBundle")?;
        self.time.time_model()?;
        self.rng_lock.validate()?;
        nonblank(
            &self.actor_provenance.actor_id,
            "request.actorProvenance.actorId",
        )?;
        nonblank(
            &self.actor_provenance.source,
            "request.actorProvenance.source",
        )?;
        if let AuthorIntervention::Recorded { report } = &self.author_intervention {
            report.validate("request.authorIntervention.report")?;
        } else if matches!(self.kind, OperationKind::Authoring | OperationKind::Retcon) {
            return Err(invalid(
                "missing_author_intervention",
                "request.authorIntervention",
                "authoring/retcon requires a declared report",
            ));
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct OperationSpec {
    schema_version: String,
    operation_id: OperationId,
    idempotency_key: String,
    request: OperationRequest,
    request_sha256: String,
    operation_spec_sha256: String,
}

impl OperationSpec {
    pub fn new(
        operation_id: OperationId,
        idempotency_key: String,
        request: OperationRequest,
    ) -> Result<Self, OperationInputError> {
        request.validate()?;
        nonblank(&idempotency_key, "idempotencyKey")?;
        let request_sha256 = digest("request", &request)?;
        let mut spec = Self {
            schema_version: OPERATION_SPEC_SCHEMA.to_owned(),
            operation_id,
            idempotency_key,
            request,
            request_sha256,
            operation_spec_sha256: String::new(),
        };
        spec.operation_spec_sha256 = spec_digest("operation", &spec, "operationSpecSha256")?;
        Ok(spec)
    }

    pub fn id(&self) -> &OperationId {
        &self.operation_id
    }
    pub fn idempotency_key(&self) -> &str {
        &self.idempotency_key
    }
    pub fn request(&self) -> &OperationRequest {
        &self.request
    }
    pub fn request_sha256(&self) -> &str {
        &self.request_sha256
    }
    pub fn sha256(&self) -> &str {
        &self.operation_spec_sha256
    }
    pub fn canonical_json(&self) -> Result<Vec<u8>, OperationInputError> {
        canonical(self)
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct RawOperationSpec {
    schema_version: String,
    operation_id: OperationId,
    idempotency_key: String,
    request: OperationRequest,
    request_sha256: String,
    operation_spec_sha256: String,
}

impl<'de> Deserialize<'de> for OperationSpec {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        let raw = RawOperationSpec::deserialize(deserializer)?;
        if raw.schema_version != OPERATION_SPEC_SCHEMA {
            return Err(serde::de::Error::custom(
                "unsupported operation spec schema; no implicit migration",
            ));
        }
        let spec = Self::new(raw.operation_id, raw.idempotency_key, raw.request)
            .map_err(serde::de::Error::custom)?;
        if raw.request_sha256 != spec.request_sha256
            || raw.operation_spec_sha256 != spec.operation_spec_sha256
        {
            return Err(serde::de::Error::custom("operation input hash mismatch"));
        }
        Ok(spec)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RunRole {
    Candidate,
    Replicate,
    Counterfactual,
    Migration,
    Single,
}

impl RunRole {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Candidate => "candidate",
            Self::Replicate => "replicate",
            Self::Counterfactual => "counterfactual",
            Self::Migration => "migration",
            Self::Single => "single",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RunSpec {
    schema_version: String,
    run_id: RunId,
    operation_id: OperationId,
    operation_spec_sha256: String,
    role: RunRole,
    run_key: String,
    parameter_sha256: String,
    rng_lock: RngLock,
    input_semantic_sha256: String,
    output_schema: String,
    run_spec_sha256: String,
}

impl RunSpec {
    pub fn new(
        parent: &OperationSpec,
        run_id: RunId,
        role: RunRole,
        run_key: String,
        input_semantic_sha256: String,
        output_schema: String,
    ) -> Result<Self, OperationInputError> {
        RngPath::parse(&run_key)
            .map_err(|e| invalid("invalid_run_key", "runKey", e.to_string()))?;
        if run_key.contains('.') {
            return Err(invalid(
                "invalid_run_key",
                "runKey",
                "expected a single RNG segment",
            ));
        }
        hash_value(&input_semantic_sha256, "inputSemanticSha256")?;
        schema(&output_schema, "outputSchema")?;
        let mut run = Self {
            schema_version: RUN_SPEC_SCHEMA.to_owned(),
            run_id,
            operation_id: parent.id().clone(),
            operation_spec_sha256: parent.sha256().to_owned(),
            role,
            rng_lock: parent.request.rng_lock.for_run(role, &run_key),
            run_key,
            parameter_sha256: parent.request.parameter_sha256.clone(),
            input_semantic_sha256,
            output_schema,
            run_spec_sha256: String::new(),
        };
        run.run_spec_sha256 = spec_digest("run", &run, "runSpecSha256")?;
        Ok(run)
    }

    /// Parse raw bytes through closed structs, then verify the supplied parent.
    /// A checksum on an unrelated or edited Run does not grant a parent match.
    pub fn from_json(parent: &OperationSpec, json: &str) -> Result<Self, OperationInputError> {
        let raw: RawRunSpec = serde_json::from_str(json)
            .map_err(|e| invalid("invalid_run_json", "run", e.to_string()))?;
        let run = Self {
            schema_version: raw.schema_version,
            run_id: raw.run_id,
            operation_id: raw.operation_id,
            operation_spec_sha256: raw.operation_spec_sha256,
            role: raw.role,
            run_key: raw.run_key,
            parameter_sha256: raw.parameter_sha256,
            rng_lock: raw.rng_lock,
            input_semantic_sha256: raw.input_semantic_sha256,
            output_schema: raw.output_schema,
            run_spec_sha256: raw.run_spec_sha256,
        };
        run.validate_against(parent)?;
        Ok(run)
    }

    pub fn validate_against(&self, parent: &OperationSpec) -> Result<(), OperationInputError> {
        let expected = Self::new(
            parent,
            self.run_id.clone(),
            self.role,
            self.run_key.clone(),
            self.input_semantic_sha256.clone(),
            self.output_schema.clone(),
        )?;
        if *self != expected {
            return Err(invalid(
                "run_parent_or_hash_mismatch",
                "run",
                "schema, parent identity/hash, inherited locks or run hash differ",
            ));
        }
        Ok(())
    }

    pub fn id(&self) -> &RunId {
        &self.run_id
    }
    pub fn operation_id(&self) -> &OperationId {
        &self.operation_id
    }
    pub fn operation_spec_sha256(&self) -> &str {
        &self.operation_spec_sha256
    }
    pub fn role(&self) -> RunRole {
        self.role
    }
    pub fn run_key(&self) -> &str {
        &self.run_key
    }
    pub fn rng_lock(&self) -> &RngLock {
        &self.rng_lock
    }
    pub fn sha256(&self) -> &str {
        &self.run_spec_sha256
    }
    pub fn canonical_json(&self) -> Result<Vec<u8>, OperationInputError> {
        canonical(self)
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct RawRunSpec {
    schema_version: String,
    run_id: RunId,
    operation_id: OperationId,
    operation_spec_sha256: String,
    role: RunRole,
    run_key: String,
    parameter_sha256: String,
    rng_lock: RngLock,
    input_semantic_sha256: String,
    output_schema: String,
    run_spec_sha256: String,
}

/// Checks one declared batch only. Durable uniqueness belongs to the ledger.
pub fn validate_run_set(
    parent: &OperationSpec,
    runs: &[RunSpec],
) -> Result<(), OperationInputError> {
    let mut ids = BTreeSet::new();
    let mut keys = BTreeSet::new();
    for run in runs {
        run.validate_against(parent)?;
        if !ids.insert(run.id()) || !keys.insert((run.role(), run.run_key())) {
            return Err(invalid(
                "duplicate_run_identity",
                "runs",
                "RunId and (role, runKey) must each be unique",
            ));
        }
    }
    Ok(())
}

fn canonical<T: Serialize>(value: &T) -> Result<Vec<u8>, OperationInputError> {
    let mut value = serde_json::to_value(value)
        .map_err(|e| invalid("serialization_failed", "input", e.to_string()))?;
    value.sort_all_objects();
    serde_json::to_vec(&value).map_err(|e| invalid("serialization_failed", "input", e.to_string()))
}

fn digest<T: Serialize>(kind: &str, value: &T) -> Result<String, OperationInputError> {
    let mut bytes = OPERATION_INPUT_HASH_SCHEMA.as_bytes().to_vec();
    bytes.push(0);
    bytes.extend_from_slice(kind.as_bytes());
    bytes.push(0);
    bytes.extend_from_slice(&canonical(value)?);
    Ok(sha256_hex(&bytes))
}

fn spec_digest<T: Serialize>(
    kind: &str,
    value: &T,
    excluded_field: &str,
) -> Result<String, OperationInputError> {
    let mut body = serde_json::to_value(value)
        .map_err(|e| invalid("serialization_failed", "input", e.to_string()))?;
    body.as_object_mut()
        .expect("private typed spec serializes as an object")
        .remove(excluded_field);
    digest(kind, &body)
}
