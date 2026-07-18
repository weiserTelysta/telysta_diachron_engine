//! Deterministic historical time primitives for diachronic simulation.
//!
//! The model uses integer years and half-open intervals `[start, end)`. This
//! avoids floating-point drift, gives simultaneous processes an explicit
//! overlap relation, and keeps UI-facing eras separate from simulation time.

use std::{
    collections::{BTreeMap, BTreeSet},
    error::Error,
    fmt,
};

use serde::{Deserialize, Deserializer, Serialize};
use sha2::{Digest, Sha256};

use crate::identity::{EntityId, EntityKind};

/// The current time-model wire schema. v2 binds every reference to a
/// canonical fingerprint of its complete model, not merely this label.
pub const TIME_MODEL_SCHEMA: &str = "telysta-time-model.v2";
pub const LEGACY_TIME_MODEL_SCHEMA_V1: &str = "telysta-time-model.v1";
pub const BASIS_POINTS: u16 = 10_000;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(transparent)]
pub struct SimYear(pub i32);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TimeRange {
    pub start: SimYear,
    pub end: SimYear,
}

impl TimeRange {
    /// Construct a half-open range `[start, end)`.
    pub fn new(start: SimYear, end: SimYear) -> Result<Self, TimeError> {
        if end <= start {
            return Err(TimeError::InvalidRange { start, end });
        }
        Ok(Self { start, end })
    }

    pub fn duration_years(self) -> i64 {
        i64::from(self.end.0) - i64::from(self.start.0)
    }

    pub fn contains(self, year: SimYear) -> bool {
        self.start <= year && year < self.end
    }

    pub fn overlaps(self, other: Self) -> bool {
        self.start < other.end && other.start < self.end
    }

    pub fn validate(&self) -> Result<(), TimeError> {
        Self::new(self.start, self.end).map(|_| ())
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RawTimeRange {
    start: SimYear,
    end: SimYear,
}

impl<'de> Deserialize<'de> for TimeRange {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let raw = RawTimeRange::deserialize(deserializer)?;
        Self::new(raw.start, raw.end).map_err(serde::de::Error::custom)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TimeModel {
    pub schema_version: String,
    pub origin: SimYear,
    pub generation_years: u16,
    pub step_years: u16,
}

/// A stable identity for one exact historical coordinate system.
///
/// The schema version alone cannot distinguish models with different origins,
/// generation lengths, or step lengths. Persisted time references therefore
/// carry this fingerprint as well as their schema version.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(transparent)]
pub struct TimeModelFingerprint(String);

impl TimeModelFingerprint {
    fn from_model(model: &TimeModel) -> Self {
        let mut hasher = Sha256::new();
        hasher.update(b"telysta-time-model-fingerprint.v1\0");
        update_fingerprint_string(&mut hasher, &model.schema_version);
        hasher.update(model.origin.0.to_be_bytes());
        hasher.update(model.generation_years.to_be_bytes());
        hasher.update(model.step_years.to_be_bytes());
        Self(format!("{:x}", hasher.finalize()))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }

    fn validate(&self) -> Result<(), TimeError> {
        if self.0.len() == 64
            && self.0.bytes().all(|byte| {
                byte.is_ascii_digit() || (byte.is_ascii_lowercase() && byte.is_ascii_hexdigit())
            })
        {
            Ok(())
        } else {
            Err(TimeError::InvalidTimeModelFingerprint(self.0.clone()))
        }
    }
}

impl<'de> Deserialize<'de> for TimeModelFingerprint {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let fingerprint = Self(String::deserialize(deserializer)?);
        fingerprint.validate().map_err(serde::de::Error::custom)?;
        Ok(fingerprint)
    }
}

fn update_fingerprint_string(hasher: &mut Sha256, value: &str) {
    hasher.update((value.len() as u32).to_be_bytes());
    hasher.update(value.as_bytes());
}

impl TimeModel {
    pub fn new(origin: SimYear, generation_years: u16, step_years: u16) -> Result<Self, TimeError> {
        if !(10..=100).contains(&generation_years) {
            return Err(TimeError::InvalidGenerationLength(generation_years));
        }
        if !(1..=1_000).contains(&step_years) {
            return Err(TimeError::InvalidStepLength(step_years));
        }
        Ok(Self {
            schema_version: TIME_MODEL_SCHEMA.to_owned(),
            origin,
            generation_years,
            step_years,
        })
    }

    pub fn step_range(&self, step_index: u32) -> Result<TimeRange, TimeError> {
        let start = i64::from(self.origin.0) + i64::from(self.step_years) * i64::from(step_index);
        let end = start + i64::from(self.step_years);
        let start = i32::try_from(start).map_err(|_| TimeError::YearOverflow)?;
        let end = i32::try_from(end).map_err(|_| TimeError::YearOverflow)?;
        TimeRange::new(SimYear(start), SimYear(end))
    }

    pub fn generation_coordinate(&self, year: SimYear) -> GenerationCoordinate {
        GenerationCoordinate {
            numerator: i64::from(year.0) - i64::from(self.origin.0),
            denominator: self.generation_years,
        }
    }

    pub fn time_reference(&self, year: SimYear) -> TimeReference {
        TimeReference::new(self, year)
    }

    pub fn fingerprint(&self) -> TimeModelFingerprint {
        TimeModelFingerprint::from_model(self)
    }

    pub fn validate_time_reference(&self, reference: &TimeReference) -> Result<(), TimeError> {
        self.validate()?;
        reference.validate()?;
        if reference.time_model_schema != self.schema_version {
            return Err(TimeError::MismatchedTimeModelFingerprint);
        }
        if reference.time_model_fingerprint != self.fingerprint() {
            return Err(TimeError::MismatchedTimeModelFingerprint);
        }
        Ok(())
    }

    pub fn validate_versioned_range(&self, range: &VersionedTimeRange) -> Result<(), TimeError> {
        self.validate()?;
        range.validate()?;
        if range.time_model_schema != self.schema_version
            || range.time_model_fingerprint != self.fingerprint()
        {
            return Err(TimeError::MismatchedTimeModelFingerprint);
        }
        Ok(())
    }

    pub fn validate(&self) -> Result<(), TimeError> {
        if self.schema_version != TIME_MODEL_SCHEMA {
            return Err(TimeError::UnsupportedTimeModelSchema(
                self.schema_version.clone(),
            ));
        }
        Self::new(self.origin, self.generation_years, self.step_years).map(|_| ())
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RawTimeModel {
    schema_version: String,
    origin: SimYear,
    generation_years: u16,
    step_years: u16,
}

impl<'de> Deserialize<'de> for TimeModel {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let raw = RawTimeModel::deserialize(deserializer)?;
        let model = Self {
            schema_version: raw.schema_version,
            origin: raw.origin,
            generation_years: raw.generation_years,
            step_years: raw.step_years,
        };
        model.validate().map_err(serde::de::Error::custom)?;
        Ok(model)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GenerationCoordinate {
    pub numerator: i64,
    pub denominator: u16,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TimeReference {
    time_model_schema: String,
    time_model_fingerprint: TimeModelFingerprint,
    year: SimYear,
}

impl TimeReference {
    pub fn new(time_model: &TimeModel, year: SimYear) -> Self {
        Self {
            time_model_schema: time_model.schema_version.clone(),
            time_model_fingerprint: time_model.fingerprint(),
            year,
        }
    }

    pub fn time_model_schema(&self) -> &str {
        &self.time_model_schema
    }

    pub fn time_model_fingerprint(&self) -> &TimeModelFingerprint {
        &self.time_model_fingerprint
    }

    pub fn year(&self) -> SimYear {
        self.year
    }

    pub fn validate(&self) -> Result<(), TimeError> {
        if self.time_model_schema != TIME_MODEL_SCHEMA {
            Err(TimeError::UnsupportedTimeModelSchema(
                self.time_model_schema.clone(),
            ))
        } else {
            self.time_model_fingerprint.validate()
        }
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RawTimeReference {
    time_model_schema: String,
    time_model_fingerprint: TimeModelFingerprint,
    year: SimYear,
}

impl<'de> Deserialize<'de> for TimeReference {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let raw = RawTimeReference::deserialize(deserializer)?;
        let reference = Self {
            time_model_schema: raw.time_model_schema,
            time_model_fingerprint: raw.time_model_fingerprint,
            year: raw.year,
        };
        reference.validate().map_err(serde::de::Error::custom)?;
        Ok(reference)
    }
}

/// A half-open time range that is explicitly tied to a TimeModel schema.
/// Future project migrations must migrate this reference, not reinterpret the
/// contained integer years under a different model.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct VersionedTimeRange {
    time_model_schema: String,
    time_model_fingerprint: TimeModelFingerprint,
    range: TimeRange,
}

impl VersionedTimeRange {
    pub fn new(time_model: &TimeModel, range: TimeRange) -> Self {
        Self {
            time_model_schema: time_model.schema_version.clone(),
            time_model_fingerprint: time_model.fingerprint(),
            range,
        }
    }

    pub fn time_model_schema(&self) -> &str {
        &self.time_model_schema
    }

    pub fn time_model_fingerprint(&self) -> &TimeModelFingerprint {
        &self.time_model_fingerprint
    }

    pub fn range(&self) -> TimeRange {
        self.range
    }

    pub fn validate(&self) -> Result<(), TimeError> {
        if self.time_model_schema != TIME_MODEL_SCHEMA {
            return Err(TimeError::UnsupportedTimeModelSchema(
                self.time_model_schema.clone(),
            ));
        }
        self.time_model_fingerprint.validate()?;
        self.range.validate()
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RawVersionedTimeRange {
    time_model_schema: String,
    time_model_fingerprint: TimeModelFingerprint,
    range: TimeRange,
}

impl<'de> Deserialize<'de> for VersionedTimeRange {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let raw = RawVersionedTimeRange::deserialize(deserializer)?;
        let range = Self {
            time_model_schema: raw.time_model_schema,
            time_model_fingerprint: raw.time_model_fingerprint,
            range: raw.range,
        };
        range.validate().map_err(serde::de::Error::custom)?;
        Ok(range)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AdoptionPoint {
    pub at: SimYear,
    pub basis_points: u16,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AdoptionCurve {
    pub points: Vec<AdoptionPoint>,
}

impl AdoptionCurve {
    /// A monotonic, piecewise-linear adoption curve evaluated with integer
    /// arithmetic. Interpolation rounds down, which is part of the v1 contract.
    pub fn new(points: Vec<AdoptionPoint>) -> Result<Self, TimeError> {
        if points.is_empty() {
            return Err(TimeError::EmptyAdoptionCurve);
        }
        for pair in points.windows(2) {
            if pair[0].at >= pair[1].at {
                return Err(TimeError::UnorderedAdoptionPoints);
            }
            if pair[0].basis_points > pair[1].basis_points {
                return Err(TimeError::RegressiveAdoptionCurve);
            }
        }
        if points.iter().any(|point| point.basis_points > BASIS_POINTS) {
            return Err(TimeError::InvalidAdoptionValue);
        }
        Ok(Self { points })
    }

    pub fn adoption_at(&self, year: SimYear) -> u16 {
        let first = self
            .points
            .first()
            .expect("validated adoption curve is non-empty");
        let last = self
            .points
            .last()
            .expect("validated adoption curve is non-empty");
        if year <= first.at {
            return first.basis_points;
        }
        if year >= last.at {
            return last.basis_points;
        }

        let pair = self
            .points
            .windows(2)
            .find(|pair| pair[0].at <= year && year < pair[1].at)
            .expect("a point inside a validated curve has a containing segment");
        let elapsed = i64::from(year.0) - i64::from(pair[0].at.0);
        let duration = i64::from(pair[1].at.0) - i64::from(pair[0].at.0);
        let delta = i64::from(pair[1].basis_points) - i64::from(pair[0].basis_points);
        (i64::from(pair[0].basis_points) + delta * elapsed / duration) as u16
    }

    pub fn validate(&self) -> Result<(), TimeError> {
        Self::new(self.points.clone()).map(|_| ())
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RawAdoptionCurve {
    points: Vec<AdoptionPoint>,
}

impl<'de> Deserialize<'de> for AdoptionCurve {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let raw = RawAdoptionCurve::deserialize(deserializer)?;
        Self::new(raw.points).map_err(serde::de::Error::custom)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ScheduledProcess {
    pub id: EntityId,
    pub active: VersionedTimeRange,
    pub adoption: AdoptionCurve,
    pub depends_on: BTreeSet<EntityId>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ChangeSchedule {
    time_model_schema: String,
    time_model_fingerprint: TimeModelFingerprint,
    processes: BTreeMap<EntityId, ScheduledProcess>,
}

impl ChangeSchedule {
    pub fn new(
        time_model: &TimeModel,
        processes: Vec<ScheduledProcess>,
    ) -> Result<Self, TimeError> {
        let mut indexed = BTreeMap::new();
        for process in processes {
            if indexed.insert(process.id.clone(), process).is_some() {
                return Err(TimeError::DuplicateProcessId);
            }
        }
        Self::from_indexed(
            time_model.schema_version.clone(),
            time_model.fingerprint(),
            indexed,
        )
    }

    fn from_indexed(
        time_model_schema: String,
        time_model_fingerprint: TimeModelFingerprint,
        indexed: BTreeMap<EntityId, ScheduledProcess>,
    ) -> Result<Self, TimeError> {
        if time_model_schema != TIME_MODEL_SCHEMA {
            return Err(TimeError::UnsupportedTimeModelSchema(time_model_schema));
        }
        time_model_fingerprint.validate()?;
        for (process_id, process) in &indexed {
            if process_id != &process.id {
                return Err(TimeError::ProcessKeyMismatch(process_id.clone()));
            }
            if process.id.kind() != EntityKind::ChangeProcess {
                return Err(TimeError::InvalidProcessIdKind(process.id.clone()));
            }
            process.active.validate()?;
            if process.active.time_model_schema() != time_model_schema
                || process.active.time_model_fingerprint() != &time_model_fingerprint
            {
                return Err(TimeError::MismatchedProcessTimeModel(process.id.clone()));
            }
            process.adoption.validate()?;
            if !process
                .adoption
                .points
                .iter()
                .all(|point| process.active.range().contains(point.at))
            {
                return Err(TimeError::AdoptionOutsideActiveRange(process.id.clone()));
            }
        }

        for process in indexed.values() {
            for dependency in &process.depends_on {
                let Some(predecessor) = indexed.get(dependency) else {
                    return Err(TimeError::MissingDependency {
                        process: process.id.clone(),
                        dependency: dependency.clone(),
                    });
                };
                if predecessor.active.range().end > process.active.range().start {
                    return Err(TimeError::OverlappingDependency {
                        process: process.id.clone(),
                        dependency: dependency.clone(),
                    });
                }
            }
        }

        let schedule = Self {
            time_model_schema,
            time_model_fingerprint,
            processes: indexed,
        };
        if schedule.topological_order().is_err() {
            return Err(TimeError::DependencyCycle);
        }
        Ok(schedule)
    }

    pub fn validate(&self) -> Result<(), TimeError> {
        Self::from_indexed(
            self.time_model_schema.clone(),
            self.time_model_fingerprint.clone(),
            self.processes.clone(),
        )
        .map(|_| ())
    }

    pub fn time_model_schema(&self) -> &str {
        &self.time_model_schema
    }

    pub fn time_model_fingerprint(&self) -> &TimeModelFingerprint {
        &self.time_model_fingerprint
    }

    pub fn processes(&self) -> &BTreeMap<EntityId, ScheduledProcess> {
        &self.processes
    }

    pub fn concurrent_pairs(&self) -> Vec<(EntityId, EntityId)> {
        let processes = self.processes.values().collect::<Vec<_>>();
        let mut pairs = Vec::new();
        for (index, process) in processes.iter().enumerate() {
            for other in processes.iter().skip(index + 1) {
                if process.active.range().overlaps(other.active.range()) {
                    pairs.push((process.id.clone(), other.id.clone()));
                }
            }
        }
        pairs
    }

    pub fn topological_order(&self) -> Result<Vec<EntityId>, TimeError> {
        let mut remaining_dependencies = self
            .processes
            .iter()
            .map(|(id, process)| (id.clone(), process.depends_on.clone()))
            .collect::<BTreeMap<_, _>>();
        let mut ready = remaining_dependencies
            .iter()
            .filter(|(_, dependencies)| dependencies.is_empty())
            .map(|(id, _)| id.clone())
            .collect::<BTreeSet<_>>();
        let mut result = Vec::with_capacity(self.processes.len());

        while let Some(id) = ready.pop_first() {
            result.push(id.clone());
            remaining_dependencies.remove(&id);
            for dependencies in remaining_dependencies.values_mut() {
                dependencies.remove(&id);
            }
            ready.extend(
                remaining_dependencies
                    .iter()
                    .filter(|(_, dependencies)| dependencies.is_empty())
                    .map(|(id, _)| id.clone()),
            );
        }

        if remaining_dependencies.is_empty() {
            Ok(result)
        } else {
            Err(TimeError::DependencyCycle)
        }
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RawChangeSchedule {
    time_model_schema: String,
    time_model_fingerprint: TimeModelFingerprint,
    processes: BTreeMap<EntityId, ScheduledProcess>,
}

impl<'de> Deserialize<'de> for ChangeSchedule {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let raw = RawChangeSchedule::deserialize(deserializer)?;
        Self::from_indexed(
            raw.time_model_schema,
            raw.time_model_fingerprint,
            raw.processes,
        )
        .map_err(serde::de::Error::custom)
    }
}

/// Migrate a persisted v1 time model into the current model. This is an
/// explicit boundary: normal deserialization never guesses how legacy years
/// should be interpreted.
pub fn migrate_legacy_time_model_v1_json(value: serde_json::Value) -> Result<TimeModel, TimeError> {
    #[derive(Deserialize)]
    #[serde(rename_all = "camelCase")]
    struct LegacyTimeModelV1 {
        schema_version: String,
        origin: SimYear,
        generation_years: u16,
        step_years: u16,
    }

    let legacy: LegacyTimeModelV1 = serde_json::from_value(value)
        .map_err(|error| TimeError::InvalidLegacyMigration(error.to_string()))?;
    if legacy.schema_version != LEGACY_TIME_MODEL_SCHEMA_V1 {
        return Err(TimeError::InvalidLegacyMigration(format!(
            "expected legacy time-model schema {LEGACY_TIME_MODEL_SCHEMA_V1:?}, found {:?}",
            legacy.schema_version
        )));
    }
    TimeModel::new(legacy.origin, legacy.generation_years, legacy.step_years)
}

/// Migrate one v1 time reference using the exact model that originally gave
/// its integer year meaning. Callers must supply that source model; no default
/// model or schema-only inference is permitted.
pub fn migrate_legacy_time_reference_v1_json(
    value: serde_json::Value,
    source_model: &TimeModel,
) -> Result<TimeReference, TimeError> {
    #[derive(Deserialize)]
    #[serde(rename_all = "camelCase")]
    struct LegacyTimeReferenceV1 {
        time_model_schema: String,
        year: SimYear,
    }

    source_model.validate()?;
    let legacy: LegacyTimeReferenceV1 = serde_json::from_value(value)
        .map_err(|error| TimeError::InvalidLegacyMigration(error.to_string()))?;
    if legacy.time_model_schema != LEGACY_TIME_MODEL_SCHEMA_V1 {
        return Err(TimeError::InvalidLegacyMigration(format!(
            "expected legacy time-reference schema {LEGACY_TIME_MODEL_SCHEMA_V1:?}, found {:?}",
            legacy.time_model_schema
        )));
    }
    Ok(source_model.time_reference(legacy.year))
}

/// Migrate one v1 versioned range with an explicit source time model.
pub fn migrate_legacy_versioned_time_range_v1_json(
    value: serde_json::Value,
    source_model: &TimeModel,
) -> Result<VersionedTimeRange, TimeError> {
    #[derive(Deserialize)]
    #[serde(rename_all = "camelCase")]
    struct LegacyVersionedTimeRangeV1 {
        time_model_schema: String,
        range: TimeRange,
    }

    source_model.validate()?;
    let legacy: LegacyVersionedTimeRangeV1 = serde_json::from_value(value)
        .map_err(|error| TimeError::InvalidLegacyMigration(error.to_string()))?;
    if legacy.time_model_schema != LEGACY_TIME_MODEL_SCHEMA_V1 {
        return Err(TimeError::InvalidLegacyMigration(format!(
            "expected legacy versioned-range schema {LEGACY_TIME_MODEL_SCHEMA_V1:?}, found {:?}",
            legacy.time_model_schema
        )));
    }
    Ok(VersionedTimeRange::new(source_model, legacy.range))
}

/// Migrate a v1 schedule after rebinding every active range to the supplied
/// source model. The source model is mandatory because v1 did not persist a
/// model fingerprint.
pub fn migrate_legacy_change_schedule_v1_json(
    mut value: serde_json::Value,
    source_model: &TimeModel,
) -> Result<ChangeSchedule, TimeError> {
    source_model.validate()?;
    let object = value.as_object_mut().ok_or_else(|| {
        TimeError::InvalidLegacyMigration("legacy change schedule must be a JSON object".to_owned())
    })?;
    let schema = object
        .get("timeModelSchema")
        .and_then(serde_json::Value::as_str)
        .ok_or_else(|| {
            TimeError::InvalidLegacyMigration(
                "legacy change schedule is missing timeModelSchema".to_owned(),
            )
        })?;
    if schema != LEGACY_TIME_MODEL_SCHEMA_V1 {
        return Err(TimeError::InvalidLegacyMigration(format!(
            "expected legacy change-schedule schema {LEGACY_TIME_MODEL_SCHEMA_V1:?}, found {schema:?}"
        )));
    }
    object.insert(
        "timeModelSchema".to_owned(),
        serde_json::Value::String(TIME_MODEL_SCHEMA.to_owned()),
    );
    object.insert(
        "timeModelFingerprint".to_owned(),
        serde_json::Value::String(source_model.fingerprint().as_str().to_owned()),
    );
    let processes = object
        .get_mut("processes")
        .and_then(serde_json::Value::as_object_mut)
        .ok_or_else(|| {
            TimeError::InvalidLegacyMigration(
                "legacy change schedule is missing processes".to_owned(),
            )
        })?;
    for process in processes.values_mut() {
        let active = process
            .as_object_mut()
            .and_then(|process| process.get_mut("active"))
            .ok_or_else(|| {
                TimeError::InvalidLegacyMigration(
                    "legacy scheduled process is missing active range".to_owned(),
                )
            })?;
        let migrated =
            migrate_legacy_versioned_time_range_v1_json(std::mem::take(active), source_model)?;
        *active = serde_json::to_value(migrated)
            .map_err(|error| TimeError::InvalidLegacyMigration(error.to_string()))?;
    }
    serde_json::from_value(value)
        .map_err(|error| TimeError::InvalidLegacyMigration(error.to_string()))
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TimeError {
    InvalidRange {
        start: SimYear,
        end: SimYear,
    },
    InvalidGenerationLength(u16),
    InvalidStepLength(u16),
    UnsupportedTimeModelSchema(String),
    InvalidTimeModelFingerprint(String),
    MismatchedTimeModelFingerprint,
    InvalidLegacyMigration(String),
    YearOverflow,
    EmptyAdoptionCurve,
    UnorderedAdoptionPoints,
    RegressiveAdoptionCurve,
    InvalidAdoptionValue,
    InvalidProcessIdKind(EntityId),
    ProcessKeyMismatch(EntityId),
    MismatchedProcessTimeModel(EntityId),
    AdoptionOutsideActiveRange(EntityId),
    DuplicateProcessId,
    MissingDependency {
        process: EntityId,
        dependency: EntityId,
    },
    OverlappingDependency {
        process: EntityId,
        dependency: EntityId,
    },
    DependencyCycle,
}

impl fmt::Display for TimeError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidRange { start, end } => {
                write!(
                    formatter,
                    "time range [{}, {}) must have start before end",
                    start.0, end.0
                )
            }
            Self::InvalidGenerationLength(value) => {
                write!(
                    formatter,
                    "generation length {value} must be between 10 and 100 years"
                )
            }
            Self::InvalidStepLength(value) => {
                write!(
                    formatter,
                    "step length {value} must be between 1 and 1000 years"
                )
            }
            Self::UnsupportedTimeModelSchema(value) => write!(
                formatter,
                "unsupported time-model schema {value:?}; expected {TIME_MODEL_SCHEMA}"
            ),
            Self::InvalidTimeModelFingerprint(value) => write!(
                formatter,
                "invalid time-model fingerprint {value:?}; expected a lowercase SHA-256 hex digest"
            ),
            Self::MismatchedTimeModelFingerprint => {
                formatter.write_str("time reference does not belong to the supplied time model")
            }
            Self::InvalidLegacyMigration(message) => {
                write!(formatter, "cannot migrate legacy time data: {message}")
            }
            Self::YearOverflow => {
                formatter.write_str("time calculation exceeds the supported i32 year range")
            }
            Self::EmptyAdoptionCurve => {
                formatter.write_str("an adoption curve needs at least one point")
            }
            Self::UnorderedAdoptionPoints => {
                formatter.write_str("adoption points must be strictly ordered by year")
            }
            Self::RegressiveAdoptionCurve => {
                formatter.write_str("adoption values must be monotonic")
            }
            Self::InvalidAdoptionValue => {
                write!(formatter, "adoption values must be at most {BASIS_POINTS}")
            }
            Self::InvalidProcessIdKind(id) => write!(
                formatter,
                "scheduled process {id} must use the change-process kind"
            ),
            Self::ProcessKeyMismatch(id) => write!(
                formatter,
                "change schedule key {id} does not match the embedded process ID"
            ),
            Self::MismatchedProcessTimeModel(id) => write!(
                formatter,
                "scheduled process {id} references a different time-model schema"
            ),
            Self::AdoptionOutsideActiveRange(id) => write!(
                formatter,
                "adoption point for {id} falls outside its active range"
            ),
            Self::DuplicateProcessId => {
                formatter.write_str("change schedule contains a duplicate process ID")
            }
            Self::MissingDependency {
                process,
                dependency,
            } => write!(
                formatter,
                "process {process} depends on missing process {dependency}"
            ),
            Self::OverlappingDependency {
                process,
                dependency,
            } => write!(
                formatter,
                "process {process} depends on {dependency} before it has finished"
            ),
            Self::DependencyCycle => {
                formatter.write_str("change schedule contains a dependency cycle")
            }
        }
    }
}

impl Error for TimeError {}

#[cfg(test)]
mod tests {
    use super::*;

    fn process_id(value: &str) -> EntityId {
        EntityId::new(EntityKind::ChangeProcess, value).expect("valid ID")
    }

    fn curve(start: i32, end: i32) -> AdoptionCurve {
        AdoptionCurve::new(vec![
            AdoptionPoint {
                at: SimYear(start),
                basis_points: 0,
            },
            AdoptionPoint {
                at: SimYear(end - 1),
                basis_points: BASIS_POINTS,
            },
        ])
        .expect("valid curve")
    }

    fn active_range(time_model: &TimeModel, start: i32, end: i32) -> VersionedTimeRange {
        VersionedTimeRange::new(
            time_model,
            TimeRange::new(SimYear(start), SimYear(end)).expect("range"),
        )
    }

    #[test]
    fn time_model_uses_years_and_exact_generation_coordinates() {
        let model = TimeModel::new(SimYear(1200), 28, 25).expect("valid model");
        assert_eq!(
            model.step_range(2).expect("step"),
            TimeRange::new(SimYear(1250), SimYear(1275)).expect("range")
        );
        assert_eq!(
            model.generation_coordinate(SimYear(1228)),
            GenerationCoordinate {
                numerator: 28,
                denominator: 28
            }
        );
        assert_eq!(
            model.time_reference(SimYear(1200)).time_model_schema(),
            TIME_MODEL_SCHEMA
        );
    }

    #[test]
    fn deserialization_enforces_time_model_invariants() {
        let invalid = r#"{
            "schemaVersion":"telysta-time-model.v1",
            "origin":1200,
            "generationYears":0,
            "stepYears":25
        }"#;
        assert!(serde_json::from_str::<TimeModel>(invalid).is_err());

        let invalid_range = r#"{"start":1200,"end":1200}"#;
        assert!(serde_json::from_str::<TimeRange>(invalid_range).is_err());

        let invalid_reference = r#"{"timeModelSchema":"telysta-time-model.v0","year":1200}"#;
        assert!(serde_json::from_str::<TimeReference>(invalid_reference).is_err());

        let invalid_versioned_range = r#"{
            "timeModelSchema":"telysta-time-model.v0",
            "range":{"start":1200,"end":1201}
        }"#;
        assert!(serde_json::from_str::<VersionedTimeRange>(invalid_versioned_range).is_err());
    }

    #[test]
    fn time_references_bind_the_exact_model_not_only_its_schema() {
        let first = TimeModel::new(SimYear(0), 25, 1).expect("first model");
        let second = TimeModel::new(SimYear(100), 25, 1).expect("second model");
        let reference = first.time_reference(SimYear(10));

        assert_ne!(first.fingerprint(), second.fingerprint());
        assert!(first.validate_time_reference(&reference).is_ok());
        assert!(matches!(
            second.validate_time_reference(&reference),
            Err(TimeError::MismatchedTimeModelFingerprint)
        ));

        let process = ScheduledProcess {
            id: process_id("bound-process"),
            active: active_range(&second, 100, 110),
            adoption: curve(100, 110),
            depends_on: BTreeSet::new(),
        };
        assert!(matches!(
            ChangeSchedule::new(&first, vec![process]),
            Err(TimeError::MismatchedProcessTimeModel(_))
        ));
    }

    #[test]
    fn legacy_time_migration_requires_an_explicit_source_model() {
        let legacy_model = serde_json::json!({
            "schemaVersion": LEGACY_TIME_MODEL_SCHEMA_V1,
            "origin": 0,
            "generationYears": 25,
            "stepYears": 1
        });
        assert!(serde_json::from_value::<TimeModel>(legacy_model.clone()).is_err());
        let model = migrate_legacy_time_model_v1_json(legacy_model).expect("migrated model");

        let legacy_reference = serde_json::json!({
            "timeModelSchema": LEGACY_TIME_MODEL_SCHEMA_V1,
            "year": 40
        });
        assert!(serde_json::from_value::<TimeReference>(legacy_reference.clone()).is_err());
        let migrated_reference =
            migrate_legacy_time_reference_v1_json(legacy_reference, &model).expect("reference");
        assert_eq!(migrated_reference.year(), SimYear(40));
        assert!(model.validate_time_reference(&migrated_reference).is_ok());

        let legacy_range = serde_json::json!({
            "timeModelSchema": LEGACY_TIME_MODEL_SCHEMA_V1,
            "range": {"start": 40, "end": 50}
        });
        let migrated_range =
            migrate_legacy_versioned_time_range_v1_json(legacy_range, &model).expect("range");
        assert!(model.validate_versioned_range(&migrated_range).is_ok());
    }

    #[test]
    fn half_open_ranges_make_boundary_and_concurrency_explicit() {
        let first = TimeRange::new(SimYear(0), SimYear(10)).expect("range");
        let adjacent = TimeRange::new(SimYear(10), SimYear(20)).expect("range");
        let overlapping = TimeRange::new(SimYear(9), SimYear(20)).expect("range");
        assert!(!first.overlaps(adjacent));
        assert!(first.overlaps(overlapping));
        assert!(!first.contains(SimYear(10)));
    }

    #[test]
    fn adoption_curve_is_deterministic_without_floats() {
        let curve = AdoptionCurve::new(vec![
            AdoptionPoint {
                at: SimYear(100),
                basis_points: 0,
            },
            AdoptionPoint {
                at: SimYear(120),
                basis_points: 5_000,
            },
            AdoptionPoint {
                at: SimYear(140),
                basis_points: BASIS_POINTS,
            },
        ])
        .expect("curve");
        assert_eq!(curve.adoption_at(SimYear(110)), 2_500);
        assert_eq!(curve.adoption_at(SimYear(130)), 7_500);
        assert!(AdoptionCurve::new(vec![
            AdoptionPoint {
                at: SimYear(100),
                basis_points: 5_000,
            },
            AdoptionPoint {
                at: SimYear(120),
                basis_points: 4_999,
            },
        ])
        .is_err());
    }

    #[test]
    fn schedule_allows_concurrency_but_not_overlapping_dependencies() {
        let time_model = TimeModel::new(SimYear(0), 25, 1).expect("valid model");
        let first = ScheduledProcess {
            id: process_id("first"),
            active: active_range(&time_model, 100, 120),
            adoption: curve(100, 120),
            depends_on: BTreeSet::new(),
        };
        let independent = ScheduledProcess {
            id: process_id("independent"),
            active: active_range(&time_model, 110, 130),
            adoption: curve(110, 130),
            depends_on: BTreeSet::new(),
        };
        let dependent = ScheduledProcess {
            id: process_id("dependent"),
            active: active_range(&time_model, 120, 140),
            adoption: curve(120, 140),
            depends_on: BTreeSet::from([first.id.clone()]),
        };
        let schedule = ChangeSchedule::new(
            &time_model,
            vec![first.clone(), independent, dependent.clone()],
        )
        .expect("valid schedule");
        assert_eq!(schedule.concurrent_pairs().len(), 2);
        assert_eq!(schedule.time_model_schema(), TIME_MODEL_SCHEMA);
        assert_eq!(schedule.time_model_fingerprint(), &time_model.fingerprint());
        assert_eq!(
            schedule.topological_order().expect("order"),
            vec![first.id.clone(), dependent.id, process_id("independent")]
        );

        let invalid_dependent = ScheduledProcess {
            id: process_id("invalid-dependent"),
            active: active_range(&time_model, 119, 140),
            adoption: curve(119, 140),
            depends_on: BTreeSet::from([first.id.clone()]),
        };
        assert!(matches!(
            ChangeSchedule::new(&time_model, vec![invalid_dependent, first]),
            Err(TimeError::OverlappingDependency { .. })
        ));
    }

    #[test]
    fn legacy_schedules_rebind_every_active_range_to_the_source_model() {
        let time_model = TimeModel::new(SimYear(0), 25, 1).expect("time model");
        let schedule = ChangeSchedule::new(
            &time_model,
            vec![ScheduledProcess {
                id: process_id("legacy-process"),
                active: active_range(&time_model, 10, 20),
                adoption: curve(10, 20),
                depends_on: BTreeSet::new(),
            }],
        )
        .expect("schedule");
        let mut legacy = serde_json::to_value(&schedule).expect("schedule JSON");
        legacy["timeModelSchema"] =
            serde_json::Value::String(LEGACY_TIME_MODEL_SCHEMA_V1.to_owned());
        legacy
            .as_object_mut()
            .expect("schedule object")
            .remove("timeModelFingerprint");
        for process in legacy["processes"]
            .as_object_mut()
            .expect("processes")
            .values_mut()
        {
            process["active"]["timeModelSchema"] =
                serde_json::Value::String(LEGACY_TIME_MODEL_SCHEMA_V1.to_owned());
            process["active"]
                .as_object_mut()
                .expect("active range")
                .remove("timeModelFingerprint");
        }

        assert!(serde_json::from_value::<ChangeSchedule>(legacy.clone()).is_err());
        assert_eq!(
            migrate_legacy_change_schedule_v1_json(legacy, &time_model).expect("migration"),
            schedule
        );
    }
}
