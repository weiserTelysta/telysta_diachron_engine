//! Project-scoped reproducibility and event-sourced language-state changes.
//!
//! `LanguageState` validates one language snapshot. This module adds the
//! project boundary that binds a snapshot to a seed, time model, locked data
//! and rule packages, and a versioned event history. The v1 event payload is a
//! validated state revision rather than a hidden in-place mutation; later
//! domain-specific events will refine this representation without allowing
//! callers to bypass the transaction boundary.

use std::{collections::BTreeMap, error::Error, fmt};

use serde::{Deserialize, Deserializer, Serialize};

use crate::{
    data::{DataManifest, DataReference, DataRegistry},
    identity::{EntityId, EntityKind},
    rng::{RngTree, RNG_TREE_SCHEMA},
    state::{LanguageState, StateError},
    time::{TimeModel, TimeReference},
};

pub const PROJECT_DATA_LOCK_SCHEMA: &str = "telysta-project-data-lock.v1";
pub const RUN_CONTEXT_SCHEMA: &str = "telysta-run-context.v1";
pub const PROJECT_EVENT_SCHEMA: &str = "telysta-project-event.v1";
pub const PROJECT_HISTORY_SCHEMA: &str = "telysta-project-history.v1";

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectDataLock {
    schema_version: String,
    manifests: BTreeMap<EntityId, DataManifest>,
}

impl ProjectDataLock {
    /// Create an immutable snapshot of the selected data manifests.
    ///
    /// A project may intentionally use no empirical datasets, but any dataset
    /// it does use must have an exact payload hash. This prevents a run from
    /// claiming reproducibility while depending on a moving remote download.
    pub fn new(manifests: Vec<DataManifest>) -> Result<Self, ProjectError> {
        let mut indexed = BTreeMap::new();
        for manifest in manifests {
            manifest.validate().map_err(ProjectError::from_data)?;
            let id = manifest.id().clone();
            if manifest.content_sha256().is_none() {
                return Err(ProjectError::validation(format!(
                    "locked data set {id} must declare contentSha256"
                )));
            }
            if indexed.insert(id, manifest).is_some() {
                return Err(ProjectError::validation(
                    "project data lock contains a duplicate data-set ID",
                ));
            }
        }
        let lock = Self {
            schema_version: PROJECT_DATA_LOCK_SCHEMA.to_owned(),
            manifests: indexed,
        };
        lock.validate()?;
        Ok(lock)
    }

    pub fn from_registry(
        registry: &DataRegistry,
        data_set_ids: impl IntoIterator<Item = EntityId>,
    ) -> Result<Self, ProjectError> {
        let mut manifests = Vec::new();
        for data_set_id in data_set_ids {
            let manifest = registry.manifests().get(&data_set_id).ok_or_else(|| {
                ProjectError::validation(format!("cannot lock unknown data set {data_set_id}"))
            })?;
            manifests.push(manifest.clone());
        }
        Self::new(manifests)
    }

    pub fn manifests(&self) -> &BTreeMap<EntityId, DataManifest> {
        &self.manifests
    }

    pub fn validate_reference(&self, reference: &DataReference) -> Result<(), ProjectError> {
        reference.validate().map_err(ProjectError::from_data)?;
        let manifest = self.manifests.get(reference.dataset_id()).ok_or_else(|| {
            ProjectError::validation(format!(
                "data reference uses data set {} that is not locked by this project",
                reference.dataset_id()
            ))
        })?;
        manifest
            .validate_reference(reference)
            .map_err(ProjectError::from_data)
    }

    /// Verify that a registry still contains byte-for-byte equivalent manifest
    /// metadata. Runtime replay uses the embedded lock, while this method is
    /// for import and refresh boundaries that have a registry available.
    pub fn validate_against_registry(&self, registry: &DataRegistry) -> Result<(), ProjectError> {
        self.validate()?;
        for (id, locked_manifest) in &self.manifests {
            let current_manifest = registry.manifests().get(id).ok_or_else(|| {
                ProjectError::validation(format!(
                    "locked data set {id} is absent from the supplied registry"
                ))
            })?;
            if current_manifest != locked_manifest {
                return Err(ProjectError::validation(format!(
                    "data manifest for {id} differs from the project's locked version"
                )));
            }
        }
        Ok(())
    }

    pub fn validate(&self) -> Result<(), ProjectError> {
        if self.schema_version != PROJECT_DATA_LOCK_SCHEMA {
            return Err(ProjectError::validation(format!(
                "unsupported project-data-lock schema {:?}; expected {PROJECT_DATA_LOCK_SCHEMA}",
                self.schema_version
            )));
        }
        for (id, manifest) in &self.manifests {
            if id != manifest.id() {
                return Err(ProjectError::validation(format!(
                    "data lock key {id} does not match embedded manifest ID {}",
                    manifest.id()
                )));
            }
            manifest.validate().map_err(ProjectError::from_data)?;
            if manifest.content_sha256().is_none() {
                return Err(ProjectError::validation(format!(
                    "locked data set {id} must declare contentSha256"
                )));
            }
        }
        Ok(())
    }

    fn from_parts(
        schema_version: String,
        manifests: BTreeMap<EntityId, DataManifest>,
    ) -> Result<Self, ProjectError> {
        let lock = Self {
            schema_version,
            manifests,
        };
        lock.validate()?;
        Ok(lock)
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RawProjectDataLock {
    schema_version: String,
    manifests: BTreeMap<EntityId, DataManifest>,
}

impl<'de> Deserialize<'de> for ProjectDataLock {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let raw = RawProjectDataLock::deserialize(deserializer)?;
        Self::from_parts(raw.schema_version, raw.manifests).map_err(serde::de::Error::custom)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RulePackLock {
    pub id: EntityId,
    pub version: String,
    pub content_sha256: String,
}

impl RulePackLock {
    fn validate(&self) -> Result<(), ProjectError> {
        ensure_kind(&self.id, EntityKind::RulePack, "rule pack ID")?;
        ensure_nonblank(&self.version, "rule pack version")?;
        ensure_sha256(&self.content_sha256, "rule pack content SHA-256")
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RunContextParts {
    pub project_id: EntityId,
    pub run_id: EntityId,
    pub time_model: TimeModel,
    pub root_seed: u64,
    pub engine_version: String,
    pub data_lock: ProjectDataLock,
    pub rule_packs: BTreeMap<EntityId, RulePackLock>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RunContext {
    schema_version: String,
    project_id: EntityId,
    run_id: EntityId,
    time_model: TimeModel,
    root_seed: u64,
    engine_version: String,
    rng_schema: String,
    data_lock: ProjectDataLock,
    rule_packs: BTreeMap<EntityId, RulePackLock>,
}

impl RunContext {
    pub fn new(parts: RunContextParts) -> Result<Self, ProjectError> {
        Self::from_parts(
            RUN_CONTEXT_SCHEMA.to_owned(),
            RNG_TREE_SCHEMA.to_owned(),
            parts,
        )
    }

    pub fn project_id(&self) -> &EntityId {
        &self.project_id
    }

    pub fn run_id(&self) -> &EntityId {
        &self.run_id
    }

    pub fn time_model(&self) -> &TimeModel {
        &self.time_model
    }

    pub const fn root_seed(&self) -> u64 {
        self.root_seed
    }

    pub fn engine_version(&self) -> &str {
        &self.engine_version
    }

    pub fn data_lock(&self) -> &ProjectDataLock {
        &self.data_lock
    }

    pub fn rule_packs(&self) -> &BTreeMap<EntityId, RulePackLock> {
        &self.rule_packs
    }

    pub const fn rng_tree(&self) -> RngTree {
        RngTree::new(self.root_seed)
    }

    pub fn validate_time_reference(&self, reference: &TimeReference) -> Result<(), ProjectError> {
        self.time_model
            .validate_time_reference(reference)
            .map_err(|error| ProjectError::validation(error.to_string()))
    }

    pub fn validate(&self) -> Result<(), ProjectError> {
        if self.schema_version != RUN_CONTEXT_SCHEMA {
            return Err(ProjectError::validation(format!(
                "unsupported run-context schema {:?}; expected {RUN_CONTEXT_SCHEMA}",
                self.schema_version
            )));
        }
        ensure_kind(&self.project_id, EntityKind::Project, "project ID")?;
        ensure_kind(&self.run_id, EntityKind::Run, "run ID")?;
        self.time_model
            .validate()
            .map_err(|error| ProjectError::validation(error.to_string()))?;
        ensure_nonblank(&self.engine_version, "engine version")?;
        if self.rng_schema != RNG_TREE_SCHEMA {
            return Err(ProjectError::validation(format!(
                "unsupported RNG schema {:?}; expected {RNG_TREE_SCHEMA}",
                self.rng_schema
            )));
        }
        self.data_lock.validate()?;
        for (id, lock) in &self.rule_packs {
            if id != &lock.id {
                return Err(ProjectError::validation(format!(
                    "rule-pack map key {id} does not match embedded ID {}",
                    lock.id
                )));
            }
            lock.validate()?;
        }
        Ok(())
    }

    fn from_parts(
        schema_version: String,
        rng_schema: String,
        parts: RunContextParts,
    ) -> Result<Self, ProjectError> {
        let context = Self {
            schema_version,
            project_id: parts.project_id,
            run_id: parts.run_id,
            time_model: parts.time_model,
            root_seed: parts.root_seed,
            engine_version: parts.engine_version,
            rng_schema,
            data_lock: parts.data_lock,
            rule_packs: parts.rule_packs,
        };
        context.validate()?;
        Ok(context)
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RawRunContext {
    schema_version: String,
    project_id: EntityId,
    run_id: EntityId,
    time_model: TimeModel,
    root_seed: u64,
    engine_version: String,
    rng_schema: String,
    data_lock: ProjectDataLock,
    rule_packs: BTreeMap<EntityId, RulePackLock>,
}

impl<'de> Deserialize<'de> for RunContext {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let raw = RawRunContext::deserialize(deserializer)?;
        Self::from_parts(
            raw.schema_version,
            raw.rng_schema,
            RunContextParts {
                project_id: raw.project_id,
                run_id: raw.run_id,
                time_model: raw.time_model,
                root_seed: raw.root_seed,
                engine_version: raw.engine_version,
                data_lock: raw.data_lock,
                rule_packs: raw.rule_packs,
            },
        )
        .map_err(serde::de::Error::custom)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", tag = "kind")]
pub enum LanguageEventPayload {
    Genesis {
        state: LanguageState,
    },
    StateRevision {
        reason: String,
        state: LanguageState,
    },
}

impl LanguageEventPayload {
    fn state(&self) -> &LanguageState {
        match self {
            Self::Genesis { state } | Self::StateRevision { state, .. } => state,
        }
    }

    fn validate(&self) -> Result<(), ProjectError> {
        match self {
            Self::Genesis { state } => state.validate().map_err(ProjectError::from_state),
            Self::StateRevision { reason, state } => {
                ensure_nonblank(reason, "state-revision reason")?;
                state.validate().map_err(ProjectError::from_state)
            }
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectEvent {
    schema_version: String,
    event_id: EntityId,
    run_id: EntityId,
    sequence: u64,
    occurred_at: TimeReference,
    payload: LanguageEventPayload,
}

impl ProjectEvent {
    fn genesis(
        event_id: EntityId,
        run_id: EntityId,
        state: LanguageState,
    ) -> Result<Self, ProjectError> {
        Self::from_parts(
            PROJECT_EVENT_SCHEMA.to_owned(),
            event_id,
            run_id,
            1,
            state.as_of().clone(),
            LanguageEventPayload::Genesis { state },
        )
    }

    fn state_revision(
        event_id: EntityId,
        run_id: EntityId,
        sequence: u64,
        state: LanguageState,
        reason: impl Into<String>,
    ) -> Result<Self, ProjectError> {
        Self::from_parts(
            PROJECT_EVENT_SCHEMA.to_owned(),
            event_id,
            run_id,
            sequence,
            state.as_of().clone(),
            LanguageEventPayload::StateRevision {
                reason: reason.into(),
                state,
            },
        )
    }

    pub fn event_id(&self) -> &EntityId {
        &self.event_id
    }

    pub fn sequence(&self) -> u64 {
        self.sequence
    }

    pub fn occurred_at(&self) -> &TimeReference {
        &self.occurred_at
    }

    pub fn state(&self) -> &LanguageState {
        self.payload.state()
    }

    /// True only for the unique first event accepted by a project history.
    /// Runtime creation uses this narrow query instead of deserializing an
    /// event payload outside the core validation boundary.
    pub fn is_genesis(&self) -> bool {
        matches!(self.payload, LanguageEventPayload::Genesis { .. })
    }

    fn from_parts(
        schema_version: String,
        event_id: EntityId,
        run_id: EntityId,
        sequence: u64,
        occurred_at: TimeReference,
        payload: LanguageEventPayload,
    ) -> Result<Self, ProjectError> {
        let event = Self {
            schema_version,
            event_id,
            run_id,
            sequence,
            occurred_at,
            payload,
        };
        event.validate()?;
        Ok(event)
    }

    fn validate(&self) -> Result<(), ProjectError> {
        if self.schema_version != PROJECT_EVENT_SCHEMA {
            return Err(ProjectError::validation(format!(
                "unsupported project-event schema {:?}; expected {PROJECT_EVENT_SCHEMA}",
                self.schema_version
            )));
        }
        ensure_kind(&self.event_id, EntityKind::Event, "event ID")?;
        ensure_kind(&self.run_id, EntityKind::Run, "event run ID")?;
        if self.sequence == 0 {
            return Err(ProjectError::validation("event sequence must start at one"));
        }
        self.occurred_at
            .validate()
            .map_err(|error| ProjectError::validation(error.to_string()))?;
        self.payload.validate()?;
        if self.payload.state().as_of() != &self.occurred_at {
            return Err(ProjectError::validation(format!(
                "event {} timestamp must equal its resulting language-state timestamp",
                self.event_id
            )));
        }
        Ok(())
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RawProjectEvent {
    schema_version: String,
    event_id: EntityId,
    run_id: EntityId,
    sequence: u64,
    occurred_at: TimeReference,
    payload: LanguageEventPayload,
}

impl<'de> Deserialize<'de> for ProjectEvent {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let raw = RawProjectEvent::deserialize(deserializer)?;
        Self::from_parts(
            raw.schema_version,
            raw.event_id,
            raw.run_id,
            raw.sequence,
            raw.occurred_at,
            raw.payload,
        )
        .map_err(serde::de::Error::custom)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectHistory {
    schema_version: String,
    context: RunContext,
    events: Vec<ProjectEvent>,
}

impl ProjectHistory {
    pub fn context(&self) -> &RunContext {
        &self.context
    }

    pub fn events(&self) -> &[ProjectEvent] {
        &self.events
    }

    pub fn replay(&self) -> Result<StateTransaction, ProjectError> {
        StateTransaction::from_history(self.clone())
    }

    /// Validate an append-only successor, including an identical retry.
    /// Replay validity alone does not authorize rewriting a committed prefix.
    pub fn validate_extension_of(&self, base: &Self) -> Result<(), ProjectError> {
        if self.context != base.context || !self.events.starts_with(&base.events) {
            return Err(ProjectError::validation(
                "committed history must preserve its run context and extend the current event prefix",
            ));
        }
        base.replay()?;
        self.replay()?;
        Ok(())
    }

    fn from_parts(
        schema_version: String,
        context: RunContext,
        events: Vec<ProjectEvent>,
    ) -> Result<Self, ProjectError> {
        let history = Self {
            schema_version,
            context,
            events,
        };
        if history.schema_version != PROJECT_HISTORY_SCHEMA {
            return Err(ProjectError::validation(format!(
                "unsupported project-history schema {:?}; expected {PROJECT_HISTORY_SCHEMA}",
                history.schema_version
            )));
        }
        history.context.validate()?;
        StateTransaction::from_history(history.clone())?;
        Ok(history)
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RawProjectHistory {
    schema_version: String,
    context: RunContext,
    events: Vec<ProjectEvent>,
}

impl<'de> Deserialize<'de> for ProjectHistory {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let raw = RawProjectHistory::deserialize(deserializer)?;
        Self::from_parts(raw.schema_version, raw.context, raw.events)
            .map_err(serde::de::Error::custom)
    }
}

#[derive(Debug, Clone)]
pub struct StateTransaction {
    context: RunContext,
    current_state: LanguageState,
    events: Vec<ProjectEvent>,
}

impl StateTransaction {
    pub fn begin(
        context: RunContext,
        genesis_event_id: EntityId,
        initial_state: LanguageState,
    ) -> Result<Self, ProjectError> {
        context.validate()?;
        let genesis = ProjectEvent::genesis(
            genesis_event_id,
            context.run_id().clone(),
            initial_state.clone(),
        )?;
        let mut transaction = Self {
            context,
            current_state: initial_state,
            events: Vec::new(),
        };
        transaction.apply_event(genesis)?;
        Ok(transaction)
    }

    pub fn context(&self) -> &RunContext {
        &self.context
    }

    pub fn current_state(&self) -> &LanguageState {
        &self.current_state
    }

    pub fn events(&self) -> &[ProjectEvent] {
        &self.events
    }

    /// Commit a fully validated replacement state. This deliberately makes a
    /// state change visible as a durable event before finer-grained language
    /// deltas are introduced by the proto-language and diachrony work.
    pub fn revise_state(
        &mut self,
        event_id: EntityId,
        next_state: LanguageState,
        reason: impl Into<String>,
    ) -> Result<(), ProjectError> {
        let event = ProjectEvent::state_revision(
            event_id,
            self.context.run_id().clone(),
            (self.events.len() as u64).saturating_add(1),
            next_state,
            reason,
        )?;
        self.apply_event(event)
    }

    pub fn history(&self) -> ProjectHistory {
        ProjectHistory {
            schema_version: PROJECT_HISTORY_SCHEMA.to_owned(),
            context: self.context.clone(),
            events: self.events.clone(),
        }
    }

    fn from_history(history: ProjectHistory) -> Result<Self, ProjectError> {
        if history.schema_version != PROJECT_HISTORY_SCHEMA {
            return Err(ProjectError::validation(format!(
                "unsupported project-history schema {:?}; expected {PROJECT_HISTORY_SCHEMA}",
                history.schema_version
            )));
        }
        history.context.validate()?;
        let mut state = None;
        let mut seen_events = BTreeMap::new();
        for event in &history.events {
            validate_event_application(
                &history.context,
                event,
                state.as_ref(),
                &seen_events,
                (seen_events.len() as u64).saturating_add(1),
            )?;
            seen_events.insert(event.event_id.clone(), event.occurred_at.clone());
            state = Some(event.state().clone());
        }
        let current_state = state.ok_or_else(|| {
            ProjectError::validation("project history must begin with a genesis event")
        })?;
        Ok(Self {
            context: history.context,
            current_state,
            events: history.events,
        })
    }

    fn apply_event(&mut self, event: ProjectEvent) -> Result<(), ProjectError> {
        let seen_events = self
            .events
            .iter()
            .map(|existing| (existing.event_id.clone(), existing.occurred_at.clone()))
            .collect::<BTreeMap<_, _>>();
        let previous = if self.events.is_empty() {
            None
        } else {
            Some(&self.current_state)
        };
        validate_event_application(
            &self.context,
            &event,
            previous,
            &seen_events,
            (self.events.len() as u64).saturating_add(1),
        )?;
        self.current_state = event.state().clone();
        self.events.push(event);
        Ok(())
    }
}

fn validate_event_application(
    context: &RunContext,
    event: &ProjectEvent,
    previous: Option<&LanguageState>,
    seen_events: &BTreeMap<EntityId, TimeReference>,
    expected_sequence: u64,
) -> Result<(), ProjectError> {
    event.validate()?;
    if event.run_id != *context.run_id() {
        return Err(ProjectError::validation(format!(
            "event {} belongs to run {}, not active run {}",
            event.event_id,
            event.run_id,
            context.run_id()
        )));
    }
    if event.sequence != expected_sequence {
        return Err(ProjectError::validation(format!(
            "event {} has sequence {}, expected {}",
            event.event_id, event.sequence, expected_sequence
        )));
    }
    if seen_events.contains_key(&event.event_id) {
        return Err(ProjectError::validation(format!(
            "project history repeats event ID {}",
            event.event_id
        )));
    }
    context.validate_time_reference(event.occurred_at())?;
    context.validate_time_reference(event.state().as_of())?;
    validate_state_data_references(event.state(), context.data_lock())?;

    match (previous, &event.payload) {
        (None, LanguageEventPayload::Genesis { .. }) => {}
        (None, _) => {
            return Err(ProjectError::validation(
                "the first project event must be a genesis event",
            ))
        }
        (Some(_), LanguageEventPayload::Genesis { .. }) => {
            return Err(ProjectError::validation(
                "a genesis event is only valid at the start of project history",
            ))
        }
        (Some(previous_state), LanguageEventPayload::StateRevision { .. }) => {
            if event.state().language_id() != previous_state.language_id() {
                return Err(ProjectError::validation(
                    "a state revision cannot change the language identity",
                ));
            }
            if event.state().as_of().year() < previous_state.as_of().year() {
                return Err(ProjectError::validation(
                    "a state revision cannot move the language timestamp backwards",
                ));
            }
        }
    }

    for entry in event.state().provenance().entries.values() {
        let referenced_time = if entry.event_id == event.event_id {
            event.occurred_at()
        } else {
            seen_events.get(&entry.event_id).ok_or_else(|| {
                ProjectError::validation(format!(
                    "state provenance references event {} before it appears in project history",
                    entry.event_id
                ))
            })?
        };
        if &entry.created_at != referenced_time {
            return Err(ProjectError::validation(format!(
                "state provenance for {} records time {:?}, but event {} occurred at {:?}",
                entry.entity_id, entry.created_at, entry.event_id, referenced_time
            )));
        }
    }
    Ok(())
}

fn validate_state_data_references(
    state: &LanguageState,
    data_lock: &ProjectDataLock,
) -> Result<(), ProjectError> {
    for evidence in state.evidence().values() {
        for reference in &evidence.data_references {
            data_lock.validate_reference(reference)?;
        }
    }
    Ok(())
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProjectError {
    message: String,
}

impl ProjectError {
    fn validation(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
        }
    }

    fn from_data(error: impl fmt::Display) -> Self {
        Self::validation(error.to_string())
    }

    fn from_state(error: StateError) -> Self {
        Self::validation(error.to_string())
    }
}

impl fmt::Display for ProjectError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.message.fmt(formatter)
    }
}

impl Error for ProjectError {}

fn ensure_kind(id: &EntityId, expected: EntityKind, label: &str) -> Result<(), ProjectError> {
    if id.kind() == expected {
        Ok(())
    } else {
        Err(ProjectError::validation(format!(
            "{label} {id} has kind {:?}, expected {:?}",
            id.kind(),
            expected
        )))
    }
}

fn ensure_nonblank(value: &str, label: &str) -> Result<(), ProjectError> {
    if value.trim().is_empty() {
        Err(ProjectError::validation(format!(
            "{label} must not be blank"
        )))
    } else {
        Ok(())
    }
}

fn ensure_sha256(value: &str, label: &str) -> Result<(), ProjectError> {
    if value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase())
    {
        Ok(())
    } else {
        Err(ProjectError::validation(format!(
            "{label} must be 64 lowercase hexadecimal characters"
        )))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        data::{DataCoverage, DataFormat, DataManifestParts, SamplingUnit},
        state::fixture_minimal_state,
        time::{SimYear, TimeModel},
    };

    fn id(kind: EntityKind, value: &str) -> EntityId {
        EntityId::new(kind, value).expect("valid fixture ID")
    }

    fn context(data_lock: ProjectDataLock) -> RunContext {
        RunContext::new(RunContextParts {
            project_id: id(EntityKind::Project, "fixture-project"),
            run_id: id(EntityKind::Run, "fixture-run"),
            time_model: TimeModel::new(SimYear(0), 25, 1).expect("time model"),
            root_seed: 888,
            engine_version: "0.1.0".to_owned(),
            data_lock,
            rule_packs: BTreeMap::new(),
        })
        .expect("valid run context")
    }

    fn locked_manifest(version: &str) -> DataManifest {
        DataManifest::new(DataManifestParts {
            id: id(EntityKind::DataSet, "fixture-data"),
            title: "Fixture data".to_owned(),
            version: version.to_owned(),
            license: "CC-BY-4.0".to_owned(),
            citation: "Fixture et al. 2026".to_owned(),
            pinned_uri: "https://example.invalid/fixture-data.zip".to_owned(),
            format: DataFormat::Json,
            content_sha256: Some("0".repeat(64)),
            coverage: DataCoverage {
                sampling_unit: SamplingUnit::Language,
                description: "One fixture language".to_owned(),
                record_count: Some(1),
            },
            limitations: vec!["Fixture only".to_owned()],
        })
        .expect("valid fixture manifest")
    }

    #[test]
    fn transaction_history_round_trips_and_replays() {
        let context = context(ProjectDataLock::new(Vec::new()).expect("empty data lock"));
        let mut transaction = StateTransaction::begin(
            context,
            id(EntityKind::Event, "genesis"),
            fixture_minimal_state(),
        )
        .expect("begin transaction");
        transaction
            .revise_state(
                id(EntityKind::Event, "fixture-revision"),
                fixture_minimal_state(),
                "validated fixture revision",
            )
            .expect("revision");

        let history = transaction.history();
        let encoded = serde_json::to_vec(&history).expect("history JSON");
        let restored: ProjectHistory = serde_json::from_slice(&encoded).expect("validated history");
        let replayed = restored.replay().expect("replay");

        assert_eq!(history.events().len(), 2);
        assert_eq!(replayed.current_state(), transaction.current_state());
        assert_eq!(replayed.events(), transaction.events());
    }

    #[test]
    fn history_rejects_event_run_or_provenance_that_cannot_be_replayed() {
        let context = context(ProjectDataLock::new(Vec::new()).expect("empty data lock"));
        let mut transaction = StateTransaction::begin(
            context,
            id(EntityKind::Event, "genesis"),
            fixture_minimal_state(),
        )
        .expect("begin transaction");
        transaction
            .revise_state(
                id(EntityKind::Event, "fixture-revision"),
                fixture_minimal_state(),
                "validated fixture revision",
            )
            .expect("revision");

        let mut invalid_run = serde_json::to_value(transaction.history()).expect("history JSON");
        invalid_run["events"][1]["runId"] =
            serde_json::Value::String(id(EntityKind::Run, "other-run").to_string());
        assert!(serde_json::from_value::<ProjectHistory>(invalid_run).is_err());

        let mut invalid_provenance =
            serde_json::to_value(transaction.history()).expect("history JSON");
        invalid_provenance["events"][0]["payload"]["state"]["provenance"]["entries"]
            ["telysta:language:proto-fixture"]["eventId"] =
            serde_json::Value::String(id(EntityKind::Event, "future-event").to_string());
        assert!(serde_json::from_value::<ProjectHistory>(invalid_provenance).is_err());
    }

    #[test]
    fn history_rejects_an_event_from_a_different_time_model_with_the_same_schema() {
        let context = context(ProjectDataLock::new(Vec::new()).expect("empty data lock"));
        let transaction = StateTransaction::begin(
            context,
            id(EntityKind::Event, "genesis"),
            fixture_minimal_state(),
        )
        .expect("begin transaction");
        let mut history = serde_json::to_value(transaction.history()).expect("history JSON");
        history["context"]["timeModel"] = serde_json::to_value(
            TimeModel::new(SimYear(100), 25, 1).expect("different valid time model"),
        )
        .expect("time model JSON");

        assert!(serde_json::from_value::<ProjectHistory>(history).is_err());
    }

    #[test]
    fn history_rejects_provenance_timestamp_that_differs_from_its_event() {
        let context = context(ProjectDataLock::new(Vec::new()).expect("empty data lock"));
        let mut transaction = StateTransaction::begin(
            context,
            id(EntityKind::Event, "genesis"),
            fixture_minimal_state(),
        )
        .expect("begin transaction");
        transaction
            .revise_state(
                id(EntityKind::Event, "fixture-revision"),
                fixture_minimal_state(),
                "validated fixture revision",
            )
            .expect("revision");

        let mut history = serde_json::to_value(transaction.history()).expect("history JSON");
        history["events"][1]["occurredAt"]["year"] = serde_json::json!(1);
        history["events"][1]["payload"]["state"]["asOf"]["year"] = serde_json::json!(1);
        history["events"][1]["payload"]["state"]["provenance"]["entries"]
            ["telysta:language:proto-fixture"]["eventId"] =
            serde_json::Value::String(id(EntityKind::Event, "fixture-revision").to_string());

        assert!(serde_json::from_value::<ProjectHistory>(history).is_err());
    }

    #[test]
    fn data_locks_require_payload_hashes_and_detect_registry_drift() {
        let manifest = locked_manifest("1.0.0");
        let registry = DataRegistry::new(vec![manifest.clone()]).expect("registry");
        let lock = ProjectDataLock::from_registry(&registry, vec![manifest.id().clone()])
            .expect("data lock");
        let reference =
            DataReference::new(manifest.id().clone(), "ValueTable", "fixture").expect("reference");
        lock.validate_reference(&reference)
            .expect("locked reference");

        let drifted_registry =
            DataRegistry::new(vec![locked_manifest("1.0.1")]).expect("drifted registry");
        assert!(lock.validate_against_registry(&drifted_registry).is_err());

        let unhashed = DataManifest::new(DataManifestParts {
            content_sha256: None,
            ..DataManifestParts {
                id: id(EntityKind::DataSet, "unhashed-data"),
                title: "Unhashed data".to_owned(),
                version: "1.0.0".to_owned(),
                license: "CC-BY-4.0".to_owned(),
                citation: "Fixture et al. 2026".to_owned(),
                pinned_uri: "https://example.invalid/unhashed-data.zip".to_owned(),
                format: DataFormat::Json,
                content_sha256: Some("0".repeat(64)),
                coverage: DataCoverage {
                    sampling_unit: SamplingUnit::Language,
                    description: "One fixture language".to_owned(),
                    record_count: Some(1),
                },
                limitations: vec!["Fixture only".to_owned()],
            }
        })
        .expect("manifest itself allows an un-downloaded payload");
        assert!(ProjectDataLock::new(vec![unhashed]).is_err());
    }

    #[test]
    fn run_context_deserialization_cannot_change_rng_contract() {
        let context = context(ProjectDataLock::new(Vec::new()).expect("empty data lock"));
        let mut value = serde_json::to_value(&context).expect("context JSON");
        value["rngSchema"] = serde_json::Value::String("other-rng.v1".to_owned());
        assert!(serde_json::from_value::<RunContext>(value).is_err());

        let path = crate::rng::RngPath::parse("genesis.phonology").expect("path");
        assert_eq!(
            context.rng_tree().stream(&path).next_u64(),
            context.rng_tree().stream(&path).next_u64()
        );
    }

    #[test]
    fn history_extension_preserves_context_and_exact_committed_prefix() {
        let mut transaction = StateTransaction::begin(
            context(ProjectDataLock::new(Vec::new()).unwrap()),
            id(EntityKind::Event, "genesis"),
            fixture_minimal_state(),
        )
        .unwrap();
        let base = transaction.history();
        transaction
            .revise_state(
                id(EntityKind::Event, "first"),
                fixture_minimal_state(),
                "first revision",
            )
            .unwrap();
        let committed = transaction.history();
        base.validate_extension_of(&base).unwrap();
        committed.validate_extension_of(&base).unwrap();
        assert!(base.validate_extension_of(&committed).is_err());

        let mut fork = base.replay().unwrap();
        fork.revise_state(
            id(EntityKind::Event, "fork"),
            fixture_minimal_state(),
            "another valid branch",
        )
        .unwrap();
        assert!(fork.history().validate_extension_of(&committed).is_err());

        let mut changed_context = committed.clone();
        changed_context.context.root_seed += 1;
        changed_context.replay().unwrap();
        assert!(changed_context.validate_extension_of(&committed).is_err());

        let mut invalid_tail = committed.clone();
        invalid_tail.events.push(committed.events[1].clone());
        assert!(invalid_tail.validate_extension_of(&committed).is_err());
    }
}
