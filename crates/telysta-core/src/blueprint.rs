//! Versioned user intent and feature registry for proto-language generation.
//!
//! A blueprint records intentions, not a partially generated language. Intent
//! identity is separate from feature identity so one feature may carry an
//! empirical prior, a creative preference, and a user lock without conflating
//! their epistemic status. Domain compilers consume a registry-validated
//! blueprint and must still produce a valid `LanguageState` transaction.

use std::{
    collections::{BTreeMap, BTreeSet},
    error::Error,
    fmt,
};

use serde::{Deserialize, Deserializer, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};

use crate::{
    identity::{EntityId, EntityKind},
    project::RunContext,
    state::{EvidenceClass, EvidenceRecord},
    time::SimYear,
};

pub const LANGUAGE_BLUEPRINT_SCHEMA: &str = "telysta-language-blueprint.v2";
pub const LEGACY_LANGUAGE_BLUEPRINT_SCHEMA_V1: &str = "telysta-language-blueprint.v1";
pub const FEATURE_REGISTRY_SCHEMA: &str = "telysta-feature-registry.v1";
pub const BUILTIN_PHONOLOGY_REGISTRY_VERSION: &str = "telysta-phonology-features.v1";
pub const BLUEPRINT_VALIDATION_REPORT_SCHEMA: &str = "telysta-blueprint-validation-report.v2";
pub const BLUEPRINT_MIGRATION_REPORT_SCHEMA: &str = "telysta-blueprint-migration-report.v1";
pub const MAX_BLUEPRINT_CANDIDATES: u16 = 64;
pub const MAX_BLUEPRINT_HORIZON_YEARS: u32 = 100_000;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BlueprintDomain {
    Phonology,
    Prosody,
    Morphology,
    Syntax,
    Lexicon,
    Semantics,
    Pragmatics,
    Orthography,
    Diachrony,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(
    rename_all = "snake_case",
    rename_all_fields = "camelCase",
    tag = "kind"
)]
pub enum BlueprintValue {
    Boolean { value: bool },
    Integer { value: i64 },
    Category { value: String },
    IntegerRange { minimum: i64, maximum: i64 },
    CategorySet { values: BTreeSet<String> },
}

impl BlueprintValue {
    fn validate(&self) -> Result<(), BlueprintError> {
        match self {
            Self::Boolean { .. } | Self::Integer { .. } => Ok(()),
            Self::Category { value } => ensure_nonblank(value, "blueprint category", None),
            Self::IntegerRange { minimum, maximum } if minimum <= maximum => Ok(()),
            Self::IntegerRange { minimum, maximum } => Err(BlueprintError::new(
                "invalid_value",
                None,
                format!("blueprint range minimum {minimum} exceeds maximum {maximum}"),
            )),
            Self::CategorySet { values } if values.is_empty() => Err(BlueprintError::new(
                "invalid_value",
                None,
                "blueprint category set must not be empty",
            )),
            Self::CategorySet { values } => {
                for value in values {
                    ensure_nonblank(value, "blueprint category-set value", None)?;
                }
                Ok(())
            }
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BlueprintControlKind {
    Locked,
    Preferred,
    Emergent,
    Hypothetical,
}

/// Compilation behavior is independent from evidence class. The validator
/// prevents statistical priors from masquerading as laws and requires disputed
/// hypotheses to remain explicit switches.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(
    rename_all = "snake_case",
    rename_all_fields = "camelCase",
    tag = "kind"
)]
pub enum BlueprintControl {
    Locked,
    Preferred {
        strength_basis_points: u16,
    },
    Emergent,
    Hypothetical {
        enabled: bool,
        confidence_basis_points: u16,
    },
}

impl BlueprintControl {
    pub const fn kind(&self) -> BlueprintControlKind {
        match self {
            Self::Locked => BlueprintControlKind::Locked,
            Self::Preferred { .. } => BlueprintControlKind::Preferred,
            Self::Emergent => BlueprintControlKind::Emergent,
            Self::Hypothetical { .. } => BlueprintControlKind::Hypothetical,
        }
    }

    fn validate(&self) -> Result<(), BlueprintError> {
        match self {
            Self::Locked | Self::Emergent => Ok(()),
            Self::Preferred {
                strength_basis_points,
            } => validate_positive_basis_points(
                *strength_basis_points,
                "preferred-intent strength",
                None,
            ),
            Self::Hypothetical {
                confidence_basis_points,
                ..
            } => validate_positive_basis_points(
                *confidence_basis_points,
                "research-hypothesis confidence",
                None,
            ),
        }
    }

    fn migration_priority(&self) -> u16 {
        match self {
            Self::Locked => 10_000,
            Self::Preferred {
                strength_basis_points,
            } => *strength_basis_points,
            Self::Emergent => 5_000,
            Self::Hypothetical {
                confidence_basis_points,
                ..
            } => *confidence_basis_points,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BlueprintIntent {
    pub id: EntityId,
    pub feature_id: EntityId,
    pub desired_value: BlueprintValue,
    pub control: BlueprintControl,
    pub priority_basis_points: u16,
    pub evidence_ids: BTreeSet<EntityId>,
    pub explanation: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum HistoricalPolicy {
    Disabled,
    Allowed,
    Preferred,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BlueprintHistoryScope {
    pub origin_year: SimYear,
    pub horizon_years: u32,
    pub branching: HistoricalPolicy,
    pub contact: HistoricalPolicy,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CandidateSelectionPolicy {
    FirstValid,
    ParetoFrontier,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BlueprintGenerationPolicy {
    pub candidate_count: u16,
    pub selection: CandidateSelectionPolicy,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LanguageBlueprintParts {
    pub blueprint_id: EntityId,
    pub display_name: String,
    pub history_scope: BlueprintHistoryScope,
    pub generation_policy: BlueprintGenerationPolicy,
    pub evidence: BTreeMap<EntityId, EvidenceRecord>,
    pub intents: BTreeMap<EntityId, BlueprintIntent>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LanguageBlueprint {
    schema_version: String,
    blueprint_id: EntityId,
    display_name: String,
    history_scope: BlueprintHistoryScope,
    generation_policy: BlueprintGenerationPolicy,
    evidence: BTreeMap<EntityId, EvidenceRecord>,
    intents: BTreeMap<EntityId, BlueprintIntent>,
}

impl LanguageBlueprint {
    pub fn new(parts: LanguageBlueprintParts) -> Result<Self, BlueprintError> {
        Self::from_parts(LANGUAGE_BLUEPRINT_SCHEMA.to_owned(), parts)
    }

    pub fn blueprint_id(&self) -> &EntityId {
        &self.blueprint_id
    }

    pub fn display_name(&self) -> &str {
        &self.display_name
    }

    pub fn history_scope(&self) -> &BlueprintHistoryScope {
        &self.history_scope
    }

    pub fn generation_policy(&self) -> &BlueprintGenerationPolicy {
        &self.generation_policy
    }

    pub fn evidence(&self) -> &BTreeMap<EntityId, EvidenceRecord> {
        &self.evidence
    }

    pub fn intents(&self) -> &BTreeMap<EntityId, BlueprintIntent> {
        &self.intents
    }

    pub fn canonical_json(&self) -> Result<Vec<u8>, BlueprintError> {
        self.validate()?;
        serde_json::to_vec(self)
            .map_err(|error| BlueprintError::new("serialization_failed", None, error.to_string()))
    }

    pub fn document_sha256(&self) -> Result<String, BlueprintError> {
        Ok(sha256_hex(&self.canonical_json()?))
    }

    pub fn summary(&self) -> BlueprintIntentSummary {
        let mut summary = BlueprintIntentSummary {
            intent_count: self.intents.len(),
            feature_count: self
                .intents
                .values()
                .map(|intent| intent.feature_id.clone())
                .collect::<BTreeSet<_>>()
                .len(),
            ..BlueprintIntentSummary::default()
        };
        for intent in self.intents.values() {
            match intent.control {
                BlueprintControl::Locked => summary.locked += 1,
                BlueprintControl::Preferred { .. } => summary.preferred += 1,
                BlueprintControl::Emergent => summary.emergent += 1,
                BlueprintControl::Hypothetical { enabled: true, .. } => {
                    summary.enabled_hypotheses += 1
                }
                BlueprintControl::Hypothetical { enabled: false, .. } => {
                    summary.disabled_hypotheses += 1
                }
            }
        }
        summary
    }

    pub fn validate(&self) -> Result<(), BlueprintError> {
        if self.schema_version != LANGUAGE_BLUEPRINT_SCHEMA {
            return Err(BlueprintError::new(
                "migration_required",
                Some("schemaVersion"),
                format!(
                    "unsupported language-blueprint schema {:?}; expected {LANGUAGE_BLUEPRINT_SCHEMA}",
                    self.schema_version
                ),
            ));
        }
        ensure_kind(
            &self.blueprint_id,
            EntityKind::Blueprint,
            "blueprint ID",
            Some("blueprintId"),
        )?;
        ensure_nonblank(
            &self.display_name,
            "blueprint display name",
            Some("displayName"),
        )?;
        if !(1..=MAX_BLUEPRINT_HORIZON_YEARS).contains(&self.history_scope.horizon_years) {
            return Err(BlueprintError::new(
                "invalid_history_scope",
                Some("historyScope.horizonYears"),
                format!("horizonYears must be in 1..={MAX_BLUEPRINT_HORIZON_YEARS}"),
            ));
        }
        self.history_scope
            .origin_year
            .0
            .checked_add_unsigned(self.history_scope.horizon_years)
            .ok_or_else(|| {
                BlueprintError::new(
                    "history_overflow",
                    Some("historyScope"),
                    "originYear + horizonYears exceeds the supported integer-year range",
                )
            })?;
        if !(1..=MAX_BLUEPRINT_CANDIDATES).contains(&self.generation_policy.candidate_count) {
            return Err(BlueprintError::new(
                "invalid_generation_policy",
                Some("generationPolicy.candidateCount"),
                format!("candidateCount must be in 1..={MAX_BLUEPRINT_CANDIDATES}"),
            ));
        }
        if self.intents.is_empty() {
            return Err(BlueprintError::new(
                "missing_intents",
                Some("intents"),
                "language blueprint must declare at least one intent",
            ));
        }
        validate_evidence(&self.evidence)?;
        for (intent_id, intent) in &self.intents {
            if intent_id != &intent.id {
                return Err(BlueprintError::new(
                    "identity_mismatch",
                    Some("intents"),
                    format!(
                        "intent key {intent_id} does not match embedded ID {}",
                        intent.id
                    ),
                ));
            }
            ensure_kind(
                &intent.id,
                EntityKind::Intent,
                "blueprint intent ID",
                Some("intents[].id"),
            )?;
            ensure_kind(
                &intent.feature_id,
                EntityKind::Feature,
                "blueprint feature ID",
                Some("intents[].featureId"),
            )?;
            intent.desired_value.validate()?;
            intent.control.validate()?;
            validate_positive_basis_points(
                intent.priority_basis_points,
                "intent priority",
                Some("intents[].priorityBasisPoints"),
            )?;
            ensure_nonblank(
                &intent.explanation,
                "intent explanation",
                Some("intents[].explanation"),
            )?;
            let evidence_class = intent_evidence_class(intent, &self.evidence)?;
            validate_control_evidence_pair(&intent.id, &intent.control, evidence_class)?;
        }
        Ok(())
    }

    pub fn validate_against_context(&self, context: &RunContext) -> Result<(), BlueprintError> {
        self.validate()?;
        context
            .validate()
            .map_err(|error| BlueprintError::new("invalid_run_context", None, error.to_string()))?;
        if self.history_scope.origin_year != context.time_model().origin {
            return Err(BlueprintError::new(
                "time_model_mismatch",
                Some("historyScope.originYear"),
                format!(
                    "blueprint origin year {} does not match run-context origin year {}",
                    self.history_scope.origin_year.0,
                    context.time_model().origin.0
                ),
            ));
        }
        for evidence in self.evidence.values() {
            for reference in &evidence.data_references {
                context
                    .data_lock()
                    .validate_reference(reference)
                    .map_err(|error| {
                        BlueprintError::new("data_lock_mismatch", None, error.to_string())
                    })?;
            }
        }
        Ok(())
    }

    pub fn validation_report(
        &self,
        registry: &FeatureRegistry,
    ) -> Result<BlueprintValidationReport, BlueprintError> {
        self.validate()?;
        registry.validate()?;
        let mut diagnostics = Vec::new();
        let mut features_by_domain = BTreeMap::new();
        let targeted_features = self
            .intents
            .values()
            .map(|intent| intent.feature_id.clone())
            .collect::<BTreeSet<_>>();

        for intent in self.intents.values() {
            let Some(definition) = registry.definitions.get(&intent.feature_id) else {
                diagnostics.push(BlueprintDiagnostic::error(
                    BlueprintDiagnosticCode::UnknownFeature,
                    Some(intent),
                    format!(
                        "feature {} is not present in registry {}",
                        intent.feature_id, registry.version
                    ),
                ));
                continue;
            };
            *features_by_domain.entry(definition.domain).or_insert(0) += 1;
            if let Err(message) = definition
                .value_schema
                .validate_value(&intent.desired_value)
            {
                diagnostics.push(BlueprintDiagnostic::error(
                    BlueprintDiagnosticCode::ValueSchemaMismatch,
                    Some(intent),
                    message,
                ));
            }
            if !definition.allowed_controls.contains(&intent.control.kind()) {
                diagnostics.push(BlueprintDiagnostic::error(
                    BlueprintDiagnosticCode::ControlNotAllowed,
                    Some(intent),
                    format!(
                        "control {:?} is not allowed for feature {}",
                        intent.control.kind(),
                        intent.feature_id
                    ),
                ));
            }
            for dependency in &definition.dependencies {
                if !targeted_features.contains(dependency) {
                    diagnostics.push(BlueprintDiagnostic::error(
                        BlueprintDiagnosticCode::MissingDependency,
                        Some(intent),
                        format!(
                            "feature {} requires feature {dependency}",
                            intent.feature_id
                        ),
                    ));
                }
            }
            for incompatible in &definition.incompatibilities {
                if targeted_features.contains(incompatible) {
                    diagnostics.push(BlueprintDiagnostic::error(
                        BlueprintDiagnosticCode::IncompatibleFeature,
                        Some(intent),
                        format!(
                            "feature {} is incompatible with feature {incompatible}",
                            intent.feature_id
                        ),
                    ));
                }
            }
            if definition.compiler_capability != CompilerCapability::Supported {
                diagnostics.push(BlueprintDiagnostic::warning(
                    BlueprintDiagnosticCode::CompilerUnavailable,
                    Some(intent),
                    format!(
                        "feature {} is {:?} in the current compiler",
                        intent.feature_id, definition.compiler_capability
                    ),
                ));
            }
        }
        diagnose_intent_conflicts(&self.intents, &mut diagnostics);

        let has_errors = diagnostics
            .iter()
            .any(|diagnostic| diagnostic.severity == DiagnosticSeverity::Error);
        let compiler_complete = self.intents.values().all(|intent| {
            registry
                .definitions
                .get(&intent.feature_id)
                .is_some_and(|definition| {
                    definition.compiler_capability == CompilerCapability::Supported
                })
        });
        Ok(BlueprintValidationReport {
            schema_version: BLUEPRINT_VALIDATION_REPORT_SCHEMA,
            blueprint_id: self.blueprint_id.clone(),
            blueprint_document_sha256: self.document_sha256()?,
            feature_registry_version: registry.version.clone(),
            feature_registry_sha256: registry.sha256()?,
            summary: self.summary(),
            intents_by_domain: features_by_domain,
            ready_for_compilation: !has_errors && compiler_complete,
            diagnostics,
        })
    }

    fn from_parts(
        schema_version: String,
        parts: LanguageBlueprintParts,
    ) -> Result<Self, BlueprintError> {
        let blueprint = Self {
            schema_version,
            blueprint_id: parts.blueprint_id,
            display_name: parts.display_name,
            history_scope: parts.history_scope,
            generation_policy: parts.generation_policy,
            evidence: parts.evidence,
            intents: parts.intents,
        };
        blueprint.validate()?;
        Ok(blueprint)
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RawLanguageBlueprintV2 {
    schema_version: String,
    blueprint_id: EntityId,
    display_name: String,
    history_scope: BlueprintHistoryScope,
    generation_policy: BlueprintGenerationPolicy,
    evidence: BTreeMap<EntityId, EvidenceRecord>,
    intents: BTreeMap<EntityId, BlueprintIntent>,
}

impl<'de> Deserialize<'de> for LanguageBlueprint {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let document = Value::deserialize(deserializer)?;
        let schema = document_schema(&document).map_err(serde::de::Error::custom)?;
        if schema == LEGACY_LANGUAGE_BLUEPRINT_SCHEMA_V1 {
            return Err(serde::de::Error::custom(format!(
                "blueprint schema {schema:?} requires explicit v1-to-v2 migration"
            )));
        }
        let raw: RawLanguageBlueprintV2 =
            serde_json::from_value(document).map_err(serde::de::Error::custom)?;
        Self::from_parts(
            raw.schema_version,
            LanguageBlueprintParts {
                blueprint_id: raw.blueprint_id,
                display_name: raw.display_name,
                history_scope: raw.history_scope,
                generation_policy: raw.generation_policy,
                evidence: raw.evidence,
                intents: raw.intents,
            },
        )
        .map_err(serde::de::Error::custom)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(
    rename_all = "snake_case",
    rename_all_fields = "camelCase",
    tag = "kind"
)]
pub enum FeatureValueSchema {
    Boolean,
    Integer {
        minimum: i64,
        maximum: i64,
    },
    Category {
        allowed: BTreeSet<String>,
    },
    IntegerRange {
        minimum: i64,
        maximum: i64,
    },
    CategorySet {
        allowed: BTreeSet<String>,
        minimum_items: usize,
        maximum_items: usize,
    },
}

impl FeatureValueSchema {
    fn validate(&self) -> Result<(), BlueprintError> {
        match self {
            Self::Boolean => Ok(()),
            Self::Integer { minimum, maximum } | Self::IntegerRange { minimum, maximum }
                if minimum <= maximum =>
            {
                Ok(())
            }
            Self::Integer { .. } | Self::IntegerRange { .. } => Err(BlueprintError::new(
                "invalid_feature_definition",
                None,
                "feature value-schema minimum exceeds maximum",
            )),
            Self::Category { allowed } if allowed.is_empty() => Err(BlueprintError::new(
                "invalid_feature_definition",
                None,
                "feature category schema must declare allowed values",
            )),
            Self::Category { allowed } => validate_category_values(allowed),
            Self::CategorySet {
                allowed,
                minimum_items,
                maximum_items,
            } => {
                validate_category_values(allowed)?;
                if minimum_items > maximum_items || *maximum_items > allowed.len() {
                    return Err(BlueprintError::new(
                        "invalid_feature_definition",
                        None,
                        "feature category-set cardinality is inconsistent with allowed values",
                    ));
                }
                Ok(())
            }
        }
    }

    fn validate_value(&self, value: &BlueprintValue) -> Result<(), String> {
        match (self, value) {
            (Self::Boolean, BlueprintValue::Boolean { .. }) => Ok(()),
            (Self::Integer { minimum, maximum }, BlueprintValue::Integer { value })
                if (minimum..=maximum).contains(&value) =>
            {
                Ok(())
            }
            (Self::Category { allowed }, BlueprintValue::Category { value })
                if allowed.contains(value) =>
            {
                Ok(())
            }
            (
                Self::IntegerRange { minimum, maximum },
                BlueprintValue::IntegerRange {
                    minimum: value_minimum,
                    maximum: value_maximum,
                },
            ) if minimum <= value_minimum
                && value_minimum <= value_maximum
                && value_maximum <= maximum =>
            {
                Ok(())
            }
            (
                Self::CategorySet {
                    allowed,
                    minimum_items,
                    maximum_items,
                },
                BlueprintValue::CategorySet { values },
            ) if (*minimum_items..=*maximum_items).contains(&values.len())
                && values.is_subset(allowed) =>
            {
                Ok(())
            }
            _ => Err(format!(
                "value {value:?} does not satisfy feature schema {self:?}"
            )),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CompilerCapability {
    Supported,
    Planned,
    DiagnosticOnly,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FeatureDefinition {
    pub id: EntityId,
    pub domain: BlueprintDomain,
    pub description: String,
    pub value_schema: FeatureValueSchema,
    pub allowed_controls: BTreeSet<BlueprintControlKind>,
    pub dependencies: BTreeSet<EntityId>,
    pub incompatibilities: BTreeSet<EntityId>,
    pub compiler_capability: CompilerCapability,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FeatureRegistry {
    schema_version: String,
    version: String,
    definitions: BTreeMap<EntityId, FeatureDefinition>,
}

impl FeatureRegistry {
    pub fn new(
        version: impl Into<String>,
        definitions: BTreeMap<EntityId, FeatureDefinition>,
    ) -> Result<Self, BlueprintError> {
        let registry = Self {
            schema_version: FEATURE_REGISTRY_SCHEMA.to_owned(),
            version: version.into(),
            definitions,
        };
        registry.validate()?;
        Ok(registry)
    }

    pub fn builtin_phonology_v1() -> Self {
        let all_controls = BTreeSet::from([
            BlueprintControlKind::Locked,
            BlueprintControlKind::Preferred,
            BlueprintControlKind::Emergent,
            BlueprintControlKind::Hypothetical,
        ]);
        let definitions = [
            feature_definition(
                "consonant-inventory-size",
                BlueprintDomain::Phonology,
                "Target range for contrastive consonants.",
                FeatureValueSchema::IntegerRange {
                    minimum: 6,
                    maximum: 100,
                },
                &all_controls,
            ),
            feature_definition(
                "vowel-inventory-size",
                BlueprintDomain::Phonology,
                "Target range for contrastive vowels.",
                FeatureValueSchema::IntegerRange {
                    minimum: 2,
                    maximum: 30,
                },
                &all_controls,
            ),
            feature_definition(
                "phonemic-length",
                BlueprintDomain::Phonology,
                "Whether segment length may be contrastive.",
                FeatureValueSchema::Boolean,
                &all_controls,
            ),
            feature_definition(
                "tone-system",
                BlueprintDomain::Prosody,
                "Requested lexical tone-system class.",
                categories(&["none", "simple", "complex"]),
                &all_controls,
            ),
            feature_definition(
                "maximum-onset-size",
                BlueprintDomain::Prosody,
                "Maximum number of consonants in an onset.",
                FeatureValueSchema::Integer {
                    minimum: 0,
                    maximum: 4,
                },
                &all_controls,
            ),
            feature_definition(
                "maximum-coda-size",
                BlueprintDomain::Prosody,
                "Maximum number of consonants in a coda.",
                FeatureValueSchema::Integer {
                    minimum: 0,
                    maximum: 4,
                },
                &all_controls,
            ),
            feature_definition(
                "stress-system",
                BlueprintDomain::Prosody,
                "Requested stress-system class.",
                categories(&["none", "fixed", "weight-sensitive", "lexical"]),
                &all_controls,
            ),
            feature_definition(
                "syllable-weight",
                BlueprintDomain::Prosody,
                "How syllable weight participates in phonology.",
                categories(&["none", "moraic", "rhyme-based"]),
                &all_controls,
            ),
            feature_definition(
                "cluster-tolerance",
                BlueprintDomain::Phonology,
                "Creative preference for consonant-cluster density.",
                categories(&["low", "medium", "high"]),
                &all_controls,
            ),
            feature_definition(
                "vowel-harmony",
                BlueprintDomain::Phonology,
                "Requested vowel-harmony class.",
                categories(&["none", "height", "backness", "rounding", "atr"]),
                &all_controls,
            ),
            feature_definition(
                "phonation-contrast",
                BlueprintDomain::Phonology,
                "Whether phonation type may be contrastive.",
                FeatureValueSchema::Boolean,
                &all_controls,
            ),
            feature_definition(
                "nasal-vowel-contrast",
                BlueprintDomain::Phonology,
                "Whether vowel nasality may be contrastive.",
                FeatureValueSchema::Boolean,
                &all_controls,
            ),
        ]
        .into_iter()
        .map(|definition| (definition.id.clone(), definition))
        .collect();
        Self::new(BUILTIN_PHONOLOGY_REGISTRY_VERSION, definitions)
            .expect("built-in phonology feature registry is valid")
    }

    pub fn version(&self) -> &str {
        &self.version
    }

    pub fn definitions(&self) -> &BTreeMap<EntityId, FeatureDefinition> {
        &self.definitions
    }

    pub fn sha256(&self) -> Result<String, BlueprintError> {
        self.validate()?;
        let bytes = serde_json::to_vec(self).map_err(|error| {
            BlueprintError::new("serialization_failed", None, error.to_string())
        })?;
        Ok(sha256_hex(&bytes))
    }

    pub fn validate(&self) -> Result<(), BlueprintError> {
        if self.schema_version != FEATURE_REGISTRY_SCHEMA {
            return Err(BlueprintError::new(
                "unsupported_registry_schema",
                Some("schemaVersion"),
                format!("expected feature registry schema {FEATURE_REGISTRY_SCHEMA}"),
            ));
        }
        ensure_nonblank(&self.version, "feature registry version", Some("version"))?;
        if self.definitions.is_empty() {
            return Err(BlueprintError::new(
                "empty_feature_registry",
                Some("definitions"),
                "feature registry must contain at least one definition",
            ));
        }
        for (id, definition) in &self.definitions {
            if id != &definition.id {
                return Err(BlueprintError::new(
                    "identity_mismatch",
                    Some("definitions"),
                    format!(
                        "feature definition key {id} does not match embedded ID {}",
                        definition.id
                    ),
                ));
            }
            ensure_kind(
                &definition.id,
                EntityKind::Feature,
                "feature definition ID",
                Some("definitions[].id"),
            )?;
            ensure_nonblank(
                &definition.description,
                "feature description",
                Some("definitions[].description"),
            )?;
            definition.value_schema.validate()?;
            if definition.allowed_controls.is_empty() {
                return Err(BlueprintError::new(
                    "invalid_feature_definition",
                    Some("definitions[].allowedControls"),
                    format!("feature {} allows no control modes", definition.id),
                ));
            }
            for related in definition
                .dependencies
                .iter()
                .chain(definition.incompatibilities.iter())
            {
                ensure_kind(
                    related,
                    EntityKind::Feature,
                    "related feature ID",
                    Some("definitions[]"),
                )?;
                if !self.definitions.contains_key(related) {
                    return Err(BlueprintError::new(
                        "invalid_feature_definition",
                        Some("definitions[]"),
                        format!(
                            "feature {} references undefined feature {related}",
                            definition.id
                        ),
                    ));
                }
            }
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BlueprintIntentSummary {
    pub intent_count: usize,
    pub feature_count: usize,
    pub locked: usize,
    pub preferred: usize,
    pub emergent: usize,
    pub enabled_hypotheses: usize,
    pub disabled_hypotheses: usize,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum DiagnosticSeverity {
    Error,
    Warning,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum BlueprintDiagnosticCode {
    UnknownFeature,
    ValueSchemaMismatch,
    ControlNotAllowed,
    MissingDependency,
    IncompatibleFeature,
    LockedIntentConflict,
    PreferenceOverridden,
    CompilerUnavailable,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BlueprintDiagnostic {
    pub code: BlueprintDiagnosticCode,
    pub severity: DiagnosticSeverity,
    pub intent_id: Option<EntityId>,
    pub feature_id: Option<EntityId>,
    pub related_intent_ids: BTreeSet<EntityId>,
    pub message: String,
}

impl BlueprintDiagnostic {
    fn error(
        code: BlueprintDiagnosticCode,
        intent: Option<&BlueprintIntent>,
        message: impl Into<String>,
    ) -> Self {
        Self::new(code, DiagnosticSeverity::Error, intent, message)
    }

    fn warning(
        code: BlueprintDiagnosticCode,
        intent: Option<&BlueprintIntent>,
        message: impl Into<String>,
    ) -> Self {
        Self::new(code, DiagnosticSeverity::Warning, intent, message)
    }

    fn new(
        code: BlueprintDiagnosticCode,
        severity: DiagnosticSeverity,
        intent: Option<&BlueprintIntent>,
        message: impl Into<String>,
    ) -> Self {
        Self {
            code,
            severity,
            intent_id: intent.map(|value| value.id.clone()),
            feature_id: intent.map(|value| value.feature_id.clone()),
            related_intent_ids: BTreeSet::new(),
            message: message.into(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BlueprintValidationReport {
    pub schema_version: &'static str,
    pub blueprint_id: EntityId,
    pub blueprint_document_sha256: String,
    pub feature_registry_version: String,
    pub feature_registry_sha256: String,
    pub summary: BlueprintIntentSummary,
    pub intents_by_domain: BTreeMap<BlueprintDomain, usize>,
    pub ready_for_compilation: bool,
    pub diagnostics: Vec<BlueprintDiagnostic>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BlueprintMigrationOutcome {
    pub schema_version: &'static str,
    pub source_schema: String,
    pub target_schema: &'static str,
    pub source_document_sha256: String,
    pub target_document_sha256: String,
    pub migrated_intent_count: usize,
    pub legacy_domains: BTreeMap<EntityId, BlueprintDomain>,
    pub blueprint: LanguageBlueprint,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct LegacyLanguageBlueprintV1 {
    schema_version: String,
    blueprint_id: EntityId,
    display_name: String,
    history_scope: BlueprintHistoryScope,
    generation_policy: BlueprintGenerationPolicy,
    evidence: BTreeMap<EntityId, EvidenceRecord>,
    features: BTreeMap<EntityId, LegacyBlueprintFeatureV1>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct LegacyBlueprintFeatureV1 {
    id: EntityId,
    domain: BlueprintDomain,
    value: BlueprintValue,
    control: BlueprintControl,
    evidence_ids: BTreeSet<EntityId>,
}

pub fn migrate_language_blueprint_v1_json(
    document: Value,
) -> Result<BlueprintMigrationOutcome, BlueprintError> {
    let source_schema = document_schema(&document)?;
    if source_schema != LEGACY_LANGUAGE_BLUEPRINT_SCHEMA_V1 {
        return Err(BlueprintError::new(
            "unsupported_migration_source",
            Some("schemaVersion"),
            format!(
                "expected migration source {LEGACY_LANGUAGE_BLUEPRINT_SCHEMA_V1:?}, found {source_schema:?}"
            ),
        ));
    }
    let source_bytes = serde_json::to_vec(&document)
        .map_err(|error| BlueprintError::new("serialization_failed", None, error.to_string()))?;
    let legacy: LegacyLanguageBlueprintV1 = serde_json::from_value(document).map_err(|error| {
        BlueprintError::new("invalid_legacy_blueprint", None, error.to_string())
    })?;
    if legacy.schema_version != LEGACY_LANGUAGE_BLUEPRINT_SCHEMA_V1 {
        return Err(BlueprintError::new(
            "unsupported_migration_source",
            Some("schemaVersion"),
            "legacy blueprint schema changed during migration parsing",
        ));
    }
    validate_evidence(&legacy.evidence)?;
    let mut intents = BTreeMap::new();
    let mut legacy_domains = BTreeMap::new();
    for (feature_key, feature) in legacy.features {
        if feature_key != feature.id {
            return Err(BlueprintError::new(
                "identity_mismatch",
                Some("features"),
                format!(
                    "legacy feature key {feature_key} does not match embedded ID {}",
                    feature.id
                ),
            ));
        }
        let intent_id = EntityId::derive(
            EntityKind::Intent,
            &legacy.blueprint_id,
            format!("v1-feature:{}", feature.id),
        );
        let intent = BlueprintIntent {
            id: intent_id.clone(),
            feature_id: feature.id.clone(),
            desired_value: feature.value,
            priority_basis_points: feature.control.migration_priority(),
            control: feature.control,
            evidence_ids: feature.evidence_ids,
            explanation: format!(
                "Explicitly migrated from v1 feature {} in the {:?} domain.",
                feature.id, feature.domain
            ),
        };
        intent.desired_value.validate()?;
        intent.control.validate()?;
        let evidence_class = intent_evidence_class(&intent, &legacy.evidence)?;
        validate_control_evidence_pair(&intent.id, &intent.control, evidence_class)?;
        legacy_domains.insert(intent_id.clone(), feature.domain);
        intents.insert(intent_id, intent);
    }
    let blueprint = LanguageBlueprint::new(LanguageBlueprintParts {
        blueprint_id: legacy.blueprint_id,
        display_name: legacy.display_name,
        history_scope: legacy.history_scope,
        generation_policy: legacy.generation_policy,
        evidence: legacy.evidence,
        intents,
    })?;
    Ok(BlueprintMigrationOutcome {
        schema_version: BLUEPRINT_MIGRATION_REPORT_SCHEMA,
        source_schema,
        target_schema: LANGUAGE_BLUEPRINT_SCHEMA,
        source_document_sha256: sha256_hex(&source_bytes),
        target_document_sha256: blueprint.document_sha256()?,
        migrated_intent_count: blueprint.intents.len(),
        legacy_domains,
        blueprint,
    })
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BlueprintError {
    pub code: String,
    pub path: Option<String>,
    pub message: String,
}

impl BlueprintError {
    fn new(code: impl Into<String>, path: Option<&str>, message: impl Into<String>) -> Self {
        Self {
            code: code.into(),
            path: path.map(str::to_owned),
            message: message.into(),
        }
    }
}

impl fmt::Display for BlueprintError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        if let Some(path) = &self.path {
            write!(formatter, "{} at {path}: {}", self.code, self.message)
        } else {
            write!(formatter, "{}: {}", self.code, self.message)
        }
    }
}

impl Error for BlueprintError {}

fn validate_evidence(evidence: &BTreeMap<EntityId, EvidenceRecord>) -> Result<(), BlueprintError> {
    for (id, record) in evidence {
        if id != &record.id {
            return Err(BlueprintError::new(
                "identity_mismatch",
                Some("evidence"),
                format!("evidence key {id} does not match embedded ID {}", record.id),
            ));
        }
        ensure_kind(
            &record.id,
            EntityKind::Evidence,
            "blueprint evidence ID",
            Some("evidence[].id"),
        )?;
        ensure_nonblank(
            &record.note,
            "blueprint evidence note",
            Some("evidence[].note"),
        )?;
        if record
            .citation
            .as_ref()
            .is_some_and(|citation| citation.trim().is_empty())
        {
            return Err(BlueprintError::new(
                "invalid_evidence",
                Some("evidence[].citation"),
                "citation must be absent or nonblank",
            ));
        }
        for reference in &record.data_references {
            reference.validate().map_err(|error| {
                BlueprintError::new(
                    "invalid_data_reference",
                    Some("evidence[].dataReferences"),
                    error.to_string(),
                )
            })?;
        }
    }
    Ok(())
}

fn intent_evidence_class(
    intent: &BlueprintIntent,
    evidence: &BTreeMap<EntityId, EvidenceRecord>,
) -> Result<EvidenceClass, BlueprintError> {
    let mut evidence_ids = intent.evidence_ids.iter();
    let first_id = evidence_ids.next().ok_or_else(|| {
        BlueprintError::new(
            "missing_evidence",
            Some("intents[].evidenceIds"),
            format!(
                "intent {} must cite at least one evidence record",
                intent.id
            ),
        )
    })?;
    let first = evidence.get(first_id).ok_or_else(|| {
        BlueprintError::new(
            "unknown_evidence",
            Some("intents[].evidenceIds"),
            format!("intent {} cites unknown evidence {first_id}", intent.id),
        )
    })?;
    for evidence_id in evidence_ids {
        let current = evidence.get(evidence_id).ok_or_else(|| {
            BlueprintError::new(
                "unknown_evidence",
                Some("intents[].evidenceIds"),
                format!("intent {} cites unknown evidence {evidence_id}", intent.id),
            )
        })?;
        if current.class != first.class {
            return Err(BlueprintError::new(
                "mixed_evidence_classes",
                Some("intents[].evidenceIds"),
                format!(
                    "intent {} mixes evidence classes; use separate intent IDs",
                    intent.id
                ),
            ));
        }
    }
    Ok(first.class)
}

fn validate_control_evidence_pair(
    intent_id: &EntityId,
    control: &BlueprintControl,
    evidence_class: EvidenceClass,
) -> Result<(), BlueprintError> {
    let valid = match evidence_class {
        EvidenceClass::HardConstraint => matches!(control, BlueprintControl::Locked),
        EvidenceClass::EmpiricalPrior => matches!(
            control,
            BlueprintControl::Preferred { .. } | BlueprintControl::Emergent
        ),
        EvidenceClass::ResearchHypothesis => {
            matches!(control, BlueprintControl::Hypothetical { .. })
        }
        EvidenceClass::CreativePreference => {
            !matches!(control, BlueprintControl::Hypothetical { .. })
        }
    };
    if valid {
        Ok(())
    } else {
        Err(BlueprintError::new(
            "control_evidence_mismatch",
            Some("intents[].control"),
            format!(
                "intent {intent_id} uses control {:?} incompatible with evidence class {evidence_class:?}",
                control.kind()
            ),
        ))
    }
}

fn diagnose_intent_conflicts(
    intents: &BTreeMap<EntityId, BlueprintIntent>,
    diagnostics: &mut Vec<BlueprintDiagnostic>,
) {
    let mut by_feature = BTreeMap::<EntityId, Vec<&BlueprintIntent>>::new();
    for intent in intents.values() {
        by_feature
            .entry(intent.feature_id.clone())
            .or_default()
            .push(intent);
    }
    for feature_intents in by_feature.values() {
        let locked = feature_intents
            .iter()
            .copied()
            .filter(|intent| matches!(intent.control, BlueprintControl::Locked))
            .collect::<Vec<_>>();
        let locked_values = locked
            .iter()
            .map(|intent| intent.desired_value.clone())
            .collect::<BTreeSet<_>>();
        if locked_values.len() > 1 {
            let related = locked
                .iter()
                .map(|intent| intent.id.clone())
                .collect::<BTreeSet<_>>();
            let mut diagnostic = BlueprintDiagnostic::error(
                BlueprintDiagnosticCode::LockedIntentConflict,
                locked.first().copied(),
                "multiple locked intents require different values for one feature",
            );
            diagnostic.related_intent_ids = related;
            diagnostics.push(diagnostic);
        }
        if let Some(locked_intent) = locked.first() {
            for preferred in feature_intents.iter().copied().filter(|intent| {
                matches!(intent.control, BlueprintControl::Preferred { .. })
                    && intent.desired_value != locked_intent.desired_value
            }) {
                let mut diagnostic = BlueprintDiagnostic::warning(
                    BlueprintDiagnosticCode::PreferenceOverridden,
                    Some(preferred),
                    format!(
                        "preferred value is overridden by locked intent {}",
                        locked_intent.id
                    ),
                );
                diagnostic
                    .related_intent_ids
                    .insert(locked_intent.id.clone());
                diagnostics.push(diagnostic);
            }
        }
    }
}

fn feature_definition(
    value: &str,
    domain: BlueprintDomain,
    description: &str,
    value_schema: FeatureValueSchema,
    allowed_controls: &BTreeSet<BlueprintControlKind>,
) -> FeatureDefinition {
    FeatureDefinition {
        id: EntityId::new(EntityKind::Feature, value).expect("built-in feature ID is valid"),
        domain,
        description: description.to_owned(),
        value_schema,
        allowed_controls: allowed_controls.clone(),
        dependencies: BTreeSet::new(),
        incompatibilities: BTreeSet::new(),
        compiler_capability: CompilerCapability::Planned,
    }
}

fn categories(values: &[&str]) -> FeatureValueSchema {
    FeatureValueSchema::Category {
        allowed: values.iter().map(|value| (*value).to_owned()).collect(),
    }
}

fn validate_category_values(values: &BTreeSet<String>) -> Result<(), BlueprintError> {
    if values.is_empty() {
        return Err(BlueprintError::new(
            "invalid_feature_definition",
            None,
            "feature category values must not be empty",
        ));
    }
    for value in values {
        ensure_nonblank(value, "feature category value", None)?;
    }
    Ok(())
}

fn validate_positive_basis_points(
    value: u16,
    label: &str,
    path: Option<&str>,
) -> Result<(), BlueprintError> {
    if (1..=10_000).contains(&value) {
        Ok(())
    } else {
        Err(BlueprintError::new(
            "invalid_basis_points",
            path,
            format!("{label} must be in 1..=10000"),
        ))
    }
}

fn ensure_kind(
    id: &EntityId,
    expected: EntityKind,
    label: &str,
    path: Option<&str>,
) -> Result<(), BlueprintError> {
    if id.kind() == expected {
        Ok(())
    } else {
        Err(BlueprintError::new(
            "invalid_entity_kind",
            path,
            format!(
                "{label} {id} has kind {:?}, expected {:?}",
                id.kind(),
                expected
            ),
        ))
    }
}

fn ensure_nonblank(value: &str, label: &str, path: Option<&str>) -> Result<(), BlueprintError> {
    if value.trim().is_empty() {
        Err(BlueprintError::new(
            "blank_value",
            path,
            format!("{label} must not be blank"),
        ))
    } else {
        Ok(())
    }
}

fn document_schema(document: &Value) -> Result<String, BlueprintError> {
    document
        .get("schemaVersion")
        .and_then(Value::as_str)
        .map(str::to_owned)
        .ok_or_else(|| {
            BlueprintError::new(
                "missing_schema",
                Some("schemaVersion"),
                "blueprint document must declare schemaVersion",
            )
        })
}

fn sha256_hex(bytes: &[u8]) -> String {
    Sha256::digest(bytes)
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        project::{ProjectDataLock, RunContextParts},
        time::TimeModel,
        ENGINE_VERSION,
    };

    fn id(kind: EntityKind, value: &str) -> EntityId {
        EntityId::new(kind, value).expect("valid fixture ID")
    }

    fn evidence(value: &str, class: EvidenceClass) -> (EntityId, EvidenceRecord) {
        let evidence_id = id(EntityKind::Evidence, value);
        (
            evidence_id.clone(),
            EvidenceRecord {
                id: evidence_id,
                class,
                note: format!("{value} fixture"),
                citation: None,
                data_references: BTreeSet::new(),
            },
        )
    }

    fn intent(
        blueprint_id: &EntityId,
        local: &str,
        feature: &str,
        value: BlueprintValue,
        control: BlueprintControl,
        evidence_id: EntityId,
    ) -> (EntityId, BlueprintIntent) {
        let intent_id = EntityId::derive(EntityKind::Intent, blueprint_id, local);
        (
            intent_id.clone(),
            BlueprintIntent {
                id: intent_id,
                feature_id: id(EntityKind::Feature, feature),
                desired_value: value,
                priority_basis_points: 7_500,
                control,
                evidence_ids: BTreeSet::from([evidence_id]),
                explanation: format!("{local} fixture intent"),
            },
        )
    }

    fn blueprint() -> LanguageBlueprint {
        let blueprint_id = id(EntityKind::Blueprint, "literary-proto-language");
        let prior = evidence("inventory-prior", EvidenceClass::EmpiricalPrior);
        let creative = evidence("inventory-preference", EvidenceClass::CreativePreference);
        let hypothesis = evidence("climate-hypothesis", EvidenceClass::ResearchHypothesis);
        let evidence = BTreeMap::from([prior.clone(), creative.clone(), hypothesis.clone()]);
        let intents = BTreeMap::from([
            intent(
                &blueprint_id,
                "inventory-prior",
                "consonant-inventory-size",
                BlueprintValue::IntegerRange {
                    minimum: 18,
                    maximum: 32,
                },
                BlueprintControl::Preferred {
                    strength_basis_points: 6_500,
                },
                prior.0,
            ),
            intent(
                &blueprint_id,
                "inventory-creative",
                "consonant-inventory-size",
                BlueprintValue::IntegerRange {
                    minimum: 22,
                    maximum: 28,
                },
                BlueprintControl::Preferred {
                    strength_basis_points: 8_000,
                },
                creative.0,
            ),
            intent(
                &blueprint_id,
                "climate-disabled",
                "phonation-contrast",
                BlueprintValue::Boolean { value: false },
                BlueprintControl::Hypothetical {
                    enabled: false,
                    confidence_basis_points: 1_000,
                },
                hypothesis.0,
            ),
        ]);
        LanguageBlueprint::new(LanguageBlueprintParts {
            blueprint_id,
            display_name: "Literary proto-language".to_owned(),
            history_scope: BlueprintHistoryScope {
                origin_year: SimYear(0),
                horizon_years: 2_000,
                branching: HistoricalPolicy::Allowed,
                contact: HistoricalPolicy::Allowed,
            },
            generation_policy: BlueprintGenerationPolicy {
                candidate_count: 8,
                selection: CandidateSelectionPolicy::ParetoFrontier,
            },
            evidence,
            intents,
        })
        .expect("valid blueprint")
    }

    fn supported_registry() -> FeatureRegistry {
        let mut definitions = FeatureRegistry::builtin_phonology_v1().definitions;
        for definition in definitions.values_mut() {
            definition.compiler_capability = CompilerCapability::Supported;
        }
        FeatureRegistry::new("test-supported.v1", definitions).expect("supported registry")
    }

    #[test]
    fn v2_allows_multiple_separate_intents_for_one_feature() {
        let blueprint = blueprint();
        assert_eq!(blueprint.summary().intent_count, 3);
        assert_eq!(blueprint.summary().feature_count, 2);
        let encoded = blueprint.canonical_json().expect("canonical blueprint");
        let restored: LanguageBlueprint =
            serde_json::from_slice(&encoded).expect("validated round trip");
        assert_eq!(restored, blueprint);
        assert_eq!(
            restored.document_sha256().expect("restored hash"),
            blueprint.document_sha256().expect("hash")
        );
    }

    #[test]
    fn built_in_registry_has_twelve_explicitly_planned_phonology_features() {
        let registry = FeatureRegistry::builtin_phonology_v1();
        assert_eq!(registry.definitions().len(), 12);
        assert!(registry
            .definitions()
            .values()
            .all(|definition| definition.compiler_capability == CompilerCapability::Planned));
        assert_eq!(registry.sha256().expect("hash").len(), 64);
    }

    #[test]
    fn report_distinguishes_valid_structure_from_compiler_readiness() {
        let blueprint = blueprint();
        let planned = blueprint
            .validation_report(&FeatureRegistry::builtin_phonology_v1())
            .expect("planned report");
        assert!(!planned.ready_for_compilation);
        assert!(planned
            .diagnostics
            .iter()
            .any(|diagnostic| { diagnostic.code == BlueprintDiagnosticCode::CompilerUnavailable }));

        let supported = blueprint
            .validation_report(&supported_registry())
            .expect("supported report");
        assert!(supported.ready_for_compilation);
        assert!(supported.diagnostics.is_empty());
    }

    #[test]
    fn report_returns_structured_unknown_feature_and_value_errors() {
        let mut unknown_blueprint = blueprint();
        let first = unknown_blueprint
            .intents
            .values_mut()
            .next()
            .expect("intent");
        first.feature_id = id(EntityKind::Feature, "unknown-feature");
        let unknown = unknown_blueprint
            .validation_report(&supported_registry())
            .expect("unknown report");
        assert_eq!(
            unknown.diagnostics[0].code,
            BlueprintDiagnosticCode::UnknownFeature
        );

        let mut mismatch_blueprint = blueprint();
        let first = mismatch_blueprint
            .intents
            .values_mut()
            .next()
            .expect("intent");
        first.desired_value = BlueprintValue::Boolean { value: true };
        let mismatch = mismatch_blueprint
            .validation_report(&supported_registry())
            .expect("mismatch report");
        assert!(mismatch.diagnostics.iter().any(|diagnostic| {
            diagnostic.code == BlueprintDiagnosticCode::ValueSchemaMismatch
                && diagnostic.severity == DiagnosticSeverity::Error
        }));
    }

    #[test]
    fn report_detects_conflicting_locks_without_rejecting_distinct_intents() {
        let mut blueprint = blueprint();
        let creative_id = id(EntityKind::Evidence, "inventory-preference");
        let first = intent(
            &blueprint.blueprint_id,
            "locked-small",
            "consonant-inventory-size",
            BlueprintValue::IntegerRange {
                minimum: 12,
                maximum: 16,
            },
            BlueprintControl::Locked,
            creative_id.clone(),
        );
        let second = intent(
            &blueprint.blueprint_id,
            "locked-large",
            "consonant-inventory-size",
            BlueprintValue::IntegerRange {
                minimum: 30,
                maximum: 36,
            },
            BlueprintControl::Locked,
            creative_id,
        );
        blueprint.intents.insert(first.0, first.1);
        blueprint.intents.insert(second.0, second.1);
        let report = blueprint
            .validation_report(&supported_registry())
            .expect("conflict report");
        assert!(!report.ready_for_compilation);
        assert!(report.diagnostics.iter().any(|diagnostic| {
            diagnostic.code == BlueprintDiagnosticCode::LockedIntentConflict
                && diagnostic.related_intent_ids.len() == 2
        }));
    }

    #[test]
    fn v1_requires_explicit_migration_and_preserves_domain_audit() {
        let legacy = serde_json::json!({
            "schemaVersion": LEGACY_LANGUAGE_BLUEPRINT_SCHEMA_V1,
            "blueprintId": "telysta:blueprint:legacy-fixture",
            "displayName": "Legacy fixture",
            "historyScope": {
                "originYear": 0,
                "horizonYears": 1000,
                "branching": "allowed",
                "contact": "disabled"
            },
            "generationPolicy": {
                "candidateCount": 4,
                "selection": "pareto_frontier"
            },
            "evidence": {
                "telysta:evidence:legacy-prior": {
                    "id": "telysta:evidence:legacy-prior",
                    "class": "empiricalPrior",
                    "note": "legacy prior",
                    "citation": null,
                    "dataReferences": []
                }
            },
            "features": {
                "telysta:feature:consonant-inventory-size": {
                    "id": "telysta:feature:consonant-inventory-size",
                    "domain": "phonology",
                    "value": {"kind": "integer_range", "minimum": 18, "maximum": 30},
                    "control": {"kind": "preferred", "strengthBasisPoints": 6000},
                    "evidenceIds": ["telysta:evidence:legacy-prior"]
                }
            }
        });
        assert!(serde_json::from_value::<LanguageBlueprint>(legacy.clone()).is_err());
        let migrated = migrate_language_blueprint_v1_json(legacy).expect("explicit migration");
        assert_eq!(migrated.source_schema, LEGACY_LANGUAGE_BLUEPRINT_SCHEMA_V1);
        assert_eq!(migrated.target_schema, LANGUAGE_BLUEPRINT_SCHEMA);
        assert_eq!(migrated.migrated_intent_count, 1);
        assert_eq!(migrated.legacy_domains.len(), 1);
        assert_ne!(
            migrated.source_document_sha256,
            migrated.target_document_sha256
        );
    }

    #[test]
    fn blueprint_rejects_priors_disguised_as_locks() {
        let mut blueprint = blueprint();
        let prior_intent = blueprint
            .intents
            .values_mut()
            .find(|intent| {
                intent
                    .evidence_ids
                    .contains(&id(EntityKind::Evidence, "inventory-prior"))
            })
            .expect("prior intent");
        prior_intent.control = BlueprintControl::Locked;
        assert!(blueprint.validate().is_err());
    }

    #[test]
    fn blueprint_checks_time_scope_and_overflow() {
        let blueprint = blueprint();
        let context = RunContext::new(RunContextParts {
            project_id: id(EntityKind::Project, "blueprint-project"),
            run_id: id(EntityKind::Run, "blueprint-run"),
            time_model: TimeModel::new(SimYear(0), 25, 10).expect("time model"),
            root_seed: 77,
            engine_version: ENGINE_VERSION.to_owned(),
            data_lock: ProjectDataLock::new(Vec::new()).expect("empty data lock"),
            rule_packs: BTreeMap::new(),
        })
        .expect("run context");
        blueprint
            .validate_against_context(&context)
            .expect("matching context");

        let mut document = serde_json::to_value(blueprint).expect("blueprint JSON");
        document["historyScope"]["originYear"] = serde_json::json!(i32::MAX);
        assert!(serde_json::from_value::<LanguageBlueprint>(document).is_err());
    }
}
