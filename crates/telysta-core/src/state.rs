//! Canonical semantic state for one simulated language.
//!
//! `LanguageState` is the only serializable language truth. Search indexes,
//! corpus counters, task status, logs, and UI selections are derived views or
//! runtime metadata and must not be stored in this type.

use std::{
    collections::{BTreeMap, BTreeSet},
    error::Error,
    fmt,
};

use serde::{Deserialize, Deserializer, Serialize};

use crate::{
    data::DataReference,
    identity::{EntityId, EntityKind},
    time::{migrate_legacy_time_reference_v1_json, TimeModel, TimeReference, BASIS_POINTS},
};

pub const LANGUAGE_STATE_SCHEMA: &str = "telysta-language-state.v2";
pub const LEGACY_LANGUAGE_STATE_SCHEMA_V1: &str = "telysta-language-state.v1";

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum SemanticDomain {
    Identity,
    Evidence,
    Phonology,
    Prosody,
    Morphology,
    Constructions,
    Lexicon,
    Pragmatics,
    Orthography,
    Typology,
    Provenance,
}

impl SemanticDomain {
    pub const ALL: [Self; 11] = [
        Self::Identity,
        Self::Evidence,
        Self::Phonology,
        Self::Prosody,
        Self::Morphology,
        Self::Constructions,
        Self::Lexicon,
        Self::Pragmatics,
        Self::Orthography,
        Self::Typology,
        Self::Provenance,
    ];

    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Identity => "identity",
            Self::Evidence => "evidence",
            Self::Phonology => "phonology",
            Self::Prosody => "prosody",
            Self::Morphology => "morphology",
            Self::Constructions => "constructions",
            Self::Lexicon => "lexicon",
            Self::Pragmatics => "pragmatics",
            Self::Orthography => "orthography",
            Self::Typology => "typology",
            Self::Provenance => "provenance",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum EvidenceClass {
    HardConstraint,
    EmpiricalPrior,
    ResearchHypothesis,
    CreativePreference,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EvidenceRecord {
    pub id: EntityId,
    pub class: EvidenceClass,
    pub note: String,
    pub citation: Option<String>,
    pub data_references: BTreeSet<DataReference>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FeatureAssertion {
    pub feature_id: EntityId,
    pub value: String,
    pub evidence_ids: BTreeSet<EntityId>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum SegmentClass {
    Consonant,
    Vowel,
    Suprasegmental,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Phoneme {
    pub id: EntityId,
    pub ipa: String,
    pub class: SegmentClass,
    pub evidence_ids: BTreeSet<EntityId>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PhonologyState {
    pub phonemes: BTreeMap<EntityId, Phoneme>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProsodyState {
    pub syllable_nuclei: BTreeSet<EntityId>,
    pub max_syllable_moras: u8,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Morpheme {
    pub id: EntityId,
    pub gloss: String,
    pub evidence_ids: BTreeSet<EntityId>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MorphologyState {
    pub morphemes: BTreeMap<EntityId, Morpheme>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Construction {
    pub id: EntityId,
    pub name: String,
    pub semantic_frame: String,
    pub morpheme_ids: BTreeSet<EntityId>,
    pub evidence_ids: BTreeSet<EntityId>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ConstructionInventory {
    pub constructions: BTreeMap<EntityId, Construction>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ConceptReference {
    pub catalog: String,
    pub concept_id: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Sense {
    pub id: EntityId,
    pub concept: ConceptReference,
    pub related_sense_ids: BTreeSet<EntityId>,
    pub evidence_ids: BTreeSet<EntityId>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Lexeme {
    pub id: EntityId,
    pub phoneme_sequence: Vec<EntityId>,
    pub morpheme_ids: BTreeSet<EntityId>,
    pub sense_ids: BTreeSet<EntityId>,
    pub register: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LexiconSenseGraph {
    pub lexemes: BTreeMap<EntityId, Lexeme>,
    pub senses: BTreeMap<EntityId, Sense>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RegisterDefinition {
    pub description: String,
    pub formality_basis_points: u16,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PragmaticsAndRegisters {
    pub default_register: String,
    pub registers: BTreeMap<String, RegisterDefinition>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", tag = "kind")]
pub enum OrthographyState {
    Disabled,
    Alphabetic {
        script: String,
        graphemes: BTreeMap<EntityId, String>,
    },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FamilyPosition {
    pub node_id: EntityId,
    pub parent_language_id: Option<EntityId>,
    pub community_ids: BTreeSet<EntityId>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum ProvenanceKind {
    Genesis,
    Inherited,
    Contact,
    UserAuthored,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProvenanceEntry {
    pub entity_id: EntityId,
    pub event_id: EntityId,
    pub kind: ProvenanceKind,
    pub created_at: TimeReference,
    pub evidence_ids: BTreeSet<EntityId>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProvenanceLedger {
    pub entries: BTreeMap<EntityId, ProvenanceEntry>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LanguageStateParts {
    pub language_id: EntityId,
    pub as_of: TimeReference,
    pub evidence: BTreeMap<EntityId, EvidenceRecord>,
    pub phonology: PhonologyState,
    pub prosody: ProsodyState,
    pub morphology: MorphologyState,
    pub constructions: ConstructionInventory,
    pub lexicon: LexiconSenseGraph,
    pub pragmatics: PragmaticsAndRegisters,
    pub orthography: OrthographyState,
    pub typology: BTreeMap<EntityId, FeatureAssertion>,
    pub family_position: FamilyPosition,
    pub provenance: ProvenanceLedger,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LanguageState {
    schema_version: String,
    language_id: EntityId,
    as_of: TimeReference,
    evidence: BTreeMap<EntityId, EvidenceRecord>,
    phonology: PhonologyState,
    prosody: ProsodyState,
    morphology: MorphologyState,
    constructions: ConstructionInventory,
    lexicon: LexiconSenseGraph,
    pragmatics: PragmaticsAndRegisters,
    orthography: OrthographyState,
    typology: BTreeMap<EntityId, FeatureAssertion>,
    family_position: FamilyPosition,
    provenance: ProvenanceLedger,
}

impl LanguageState {
    pub fn new(parts: LanguageStateParts) -> Result<Self, StateError> {
        Self::from_parts(LANGUAGE_STATE_SCHEMA.to_owned(), parts)
    }

    pub fn schema_version(&self) -> &str {
        &self.schema_version
    }

    pub fn language_id(&self) -> &EntityId {
        &self.language_id
    }

    pub fn as_of(&self) -> &TimeReference {
        &self.as_of
    }

    pub fn phonology(&self) -> &PhonologyState {
        &self.phonology
    }

    pub fn lexicon(&self) -> &LexiconSenseGraph {
        &self.lexicon
    }

    pub fn evidence(&self) -> &BTreeMap<EntityId, EvidenceRecord> {
        &self.evidence
    }

    pub fn provenance(&self) -> &ProvenanceLedger {
        &self.provenance
    }

    pub fn canonical_json(&self) -> Result<Vec<u8>, StateError> {
        self.validate()?;
        serde_json::to_vec(self).map_err(|error| StateError::validation(error.to_string()))
    }

    pub fn semantic_domain_json(&self, domain: SemanticDomain) -> Result<Vec<u8>, StateError> {
        self.validate()?;
        let bytes = match domain {
            SemanticDomain::Identity => serde_json::to_vec(&IdentityDomain {
                schema_version: &self.schema_version,
                language_id: &self.language_id,
                as_of: &self.as_of,
                family_position: &self.family_position,
            }),
            SemanticDomain::Evidence => serde_json::to_vec(&self.evidence),
            SemanticDomain::Phonology => serde_json::to_vec(&self.phonology),
            SemanticDomain::Prosody => serde_json::to_vec(&self.prosody),
            SemanticDomain::Morphology => serde_json::to_vec(&self.morphology),
            SemanticDomain::Constructions => serde_json::to_vec(&self.constructions),
            SemanticDomain::Lexicon => serde_json::to_vec(&self.lexicon),
            SemanticDomain::Pragmatics => serde_json::to_vec(&self.pragmatics),
            SemanticDomain::Orthography => serde_json::to_vec(&self.orthography),
            SemanticDomain::Typology => serde_json::to_vec(&self.typology),
            SemanticDomain::Provenance => serde_json::to_vec(&self.provenance),
        };
        bytes.map_err(|error| StateError::validation(error.to_string()))
    }

    pub fn corpus_statistics(&self) -> CorpusStatistics {
        CorpusStatistics {
            phoneme_count: self.phonology.phonemes.len(),
            morpheme_count: self.morphology.morphemes.len(),
            construction_count: self.constructions.constructions.len(),
            lexeme_count: self.lexicon.lexemes.len(),
            sense_count: self.lexicon.senses.len(),
            register_count: self.pragmatics.registers.len(),
        }
    }

    pub fn semantic_entity_ids(&self) -> BTreeSet<EntityId> {
        let mut ids = BTreeSet::from([
            self.language_id.clone(),
            self.family_position.node_id.clone(),
        ]);
        ids.extend(self.phonology.phonemes.keys().cloned());
        ids.extend(self.morphology.morphemes.keys().cloned());
        ids.extend(self.constructions.constructions.keys().cloned());
        ids.extend(self.lexicon.lexemes.keys().cloned());
        ids.extend(self.lexicon.senses.keys().cloned());
        ids
    }

    pub fn validate(&self) -> Result<(), StateError> {
        if self.schema_version != LANGUAGE_STATE_SCHEMA {
            return Err(StateError::validation(format!(
                "unsupported language-state schema {:?}; expected {LANGUAGE_STATE_SCHEMA}",
                self.schema_version
            )));
        }
        ensure_kind(&self.language_id, EntityKind::Language, "language ID")?;
        self.as_of
            .validate()
            .map_err(|error| StateError::validation(error.to_string()))?;
        validate_evidence(&self.evidence)?;
        validate_phonology(&self.phonology, &self.evidence)?;
        validate_prosody(&self.prosody, &self.phonology)?;
        validate_morphology(&self.morphology, &self.evidence)?;
        validate_constructions(&self.constructions, &self.morphology, &self.evidence)?;
        validate_pragmatics(&self.pragmatics)?;
        validate_lexicon(
            &self.lexicon,
            &self.phonology,
            &self.morphology,
            &self.pragmatics,
            &self.evidence,
        )?;
        validate_orthography(&self.orthography, &self.phonology)?;
        validate_typology(&self.typology, &self.evidence)?;
        validate_family_position(&self.family_position)?;
        validate_provenance(self)?;
        Ok(())
    }

    fn from_parts(schema_version: String, parts: LanguageStateParts) -> Result<Self, StateError> {
        let state = Self {
            schema_version,
            language_id: parts.language_id,
            as_of: parts.as_of,
            evidence: parts.evidence,
            phonology: parts.phonology,
            prosody: parts.prosody,
            morphology: parts.morphology,
            constructions: parts.constructions,
            lexicon: parts.lexicon,
            pragmatics: parts.pragmatics,
            orthography: parts.orthography,
            typology: parts.typology,
            family_position: parts.family_position,
            provenance: parts.provenance,
        };
        state.validate()?;
        Ok(state)
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RawLanguageState {
    schema_version: String,
    language_id: EntityId,
    as_of: TimeReference,
    evidence: BTreeMap<EntityId, EvidenceRecord>,
    phonology: PhonologyState,
    prosody: ProsodyState,
    morphology: MorphologyState,
    constructions: ConstructionInventory,
    lexicon: LexiconSenseGraph,
    pragmatics: PragmaticsAndRegisters,
    orthography: OrthographyState,
    typology: BTreeMap<EntityId, FeatureAssertion>,
    family_position: FamilyPosition,
    provenance: ProvenanceLedger,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct IdentityDomain<'a> {
    schema_version: &'a str,
    language_id: &'a EntityId,
    as_of: &'a TimeReference,
    family_position: &'a FamilyPosition,
}

impl<'de> Deserialize<'de> for LanguageState {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let raw = RawLanguageState::deserialize(deserializer)?;
        Self::from_parts(
            raw.schema_version,
            LanguageStateParts {
                language_id: raw.language_id,
                as_of: raw.as_of,
                evidence: raw.evidence,
                phonology: raw.phonology,
                prosody: raw.prosody,
                morphology: raw.morphology,
                constructions: raw.constructions,
                lexicon: raw.lexicon,
                pragmatics: raw.pragmatics,
                orthography: raw.orthography,
                typology: raw.typology,
                family_position: raw.family_position,
                provenance: raw.provenance,
            },
        )
        .map_err(serde::de::Error::custom)
    }
}

/// Migrate a persisted v1 language state with an explicit source time model.
///
/// The v1 state format stored a time-model schema label only. A caller must
/// provide the precise legacy model that gave each year its meaning; ordinary
/// `LanguageState` deserialization intentionally rejects that ambiguous data.
pub fn migrate_legacy_language_state_v1_json(
    mut value: serde_json::Value,
    source_time_model: &TimeModel,
) -> Result<LanguageState, StateError> {
    source_time_model
        .validate()
        .map_err(|error| StateError::validation(error.to_string()))?;
    {
        let object = value
            .as_object_mut()
            .ok_or_else(|| StateError::validation("legacy language state must be a JSON object"))?;
        let schema = object
            .get("schemaVersion")
            .and_then(serde_json::Value::as_str)
            .ok_or_else(|| {
                StateError::validation("legacy language state is missing schemaVersion")
            })?;
        if schema != LEGACY_LANGUAGE_STATE_SCHEMA_V1 {
            return Err(StateError::validation(format!(
                "expected legacy language-state schema {LEGACY_LANGUAGE_STATE_SCHEMA_V1:?}, found {schema:?}"
            )));
        }

        let as_of = object
            .get_mut("asOf")
            .ok_or_else(|| StateError::validation("legacy language state is missing asOf"))?;
        let migrated_as_of =
            migrate_legacy_time_reference_v1_json(std::mem::take(as_of), source_time_model)
                .map_err(|error| StateError::validation(error.to_string()))?;
        *as_of = serde_json::to_value(migrated_as_of)
            .map_err(|error| StateError::validation(error.to_string()))?;

        let entries = object
            .get_mut("provenance")
            .and_then(serde_json::Value::as_object_mut)
            .and_then(|provenance| provenance.get_mut("entries"))
            .and_then(serde_json::Value::as_object_mut)
            .ok_or_else(|| {
                StateError::validation("legacy language state is missing provenance entries")
            })?;
        for entry in entries.values_mut() {
            let created_at = entry
                .as_object_mut()
                .and_then(|entry| entry.get_mut("createdAt"))
                .ok_or_else(|| {
                    StateError::validation("legacy provenance entry is missing createdAt")
                })?;
            let migrated_created_at = migrate_legacy_time_reference_v1_json(
                std::mem::take(created_at),
                source_time_model,
            )
            .map_err(|error| StateError::validation(error.to_string()))?;
            *created_at = serde_json::to_value(migrated_created_at)
                .map_err(|error| StateError::validation(error.to_string()))?;
        }
        object.insert(
            "schemaVersion".to_owned(),
            serde_json::Value::String(LANGUAGE_STATE_SCHEMA.to_owned()),
        );
    }
    serde_json::from_value(value).map_err(|error| StateError::validation(error.to_string()))
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct CorpusStatistics {
    pub phoneme_count: usize,
    pub morpheme_count: usize,
    pub construction_count: usize,
    pub lexeme_count: usize,
    pub sense_count: usize,
    pub register_count: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StateError {
    message: String,
}

impl StateError {
    fn validation(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
        }
    }
}

impl fmt::Display for StateError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.message.fmt(formatter)
    }
}

impl Error for StateError {}

fn validate_evidence(evidence: &BTreeMap<EntityId, EvidenceRecord>) -> Result<(), StateError> {
    if evidence.is_empty() {
        return Err(StateError::validation(
            "language state needs at least one evidence record",
        ));
    }
    for (id, record) in evidence {
        if id != &record.id {
            return Err(StateError::validation(format!(
                "evidence map key {id} does not match embedded ID {}",
                record.id
            )));
        }
        ensure_kind(id, EntityKind::Evidence, "evidence ID")?;
        ensure_nonblank(&record.note, "evidence note")?;
        if record.class != EvidenceClass::CreativePreference {
            let citation = record.citation.as_deref().ok_or_else(|| {
                StateError::validation(format!("evidence {id} requires a citation"))
            })?;
            ensure_nonblank(citation, "evidence citation")?;
        }
        for data_reference in &record.data_references {
            data_reference
                .validate()
                .map_err(|error| StateError::validation(error.to_string()))?;
        }
    }
    Ok(())
}

fn validate_phonology(
    phonology: &PhonologyState,
    evidence: &BTreeMap<EntityId, EvidenceRecord>,
) -> Result<(), StateError> {
    if phonology.phonemes.is_empty() {
        return Err(StateError::validation(
            "phonology must contain at least one phoneme",
        ));
    }
    let mut ipa_symbols = BTreeSet::new();
    for (id, phoneme) in &phonology.phonemes {
        if id != &phoneme.id {
            return Err(StateError::validation(format!(
                "phoneme map key {id} does not match embedded ID"
            )));
        }
        ensure_kind(id, EntityKind::Phoneme, "phoneme ID")?;
        ensure_nonblank(&phoneme.ipa, "IPA symbol")?;
        if !ipa_symbols.insert(phoneme.ipa.clone()) {
            return Err(StateError::validation(format!(
                "duplicate IPA symbol {:?}",
                phoneme.ipa
            )));
        }
        validate_evidence_ids(&phoneme.evidence_ids, evidence, "phoneme")?;
    }
    Ok(())
}

fn validate_prosody(prosody: &ProsodyState, phonology: &PhonologyState) -> Result<(), StateError> {
    if prosody.max_syllable_moras == 0 {
        return Err(StateError::validation(
            "max syllable moras must be greater than zero",
        ));
    }
    if prosody.syllable_nuclei.is_empty() {
        return Err(StateError::validation(
            "prosody must declare at least one syllable nucleus",
        ));
    }
    for nucleus_id in &prosody.syllable_nuclei {
        let phoneme = phonology.phonemes.get(nucleus_id).ok_or_else(|| {
            StateError::validation(format!("prosodic nucleus {nucleus_id} is not in phonology"))
        })?;
        if phoneme.class != SegmentClass::Vowel {
            return Err(StateError::validation(format!(
                "prosodic nucleus {nucleus_id} must be a vowel phoneme"
            )));
        }
    }
    Ok(())
}

fn validate_morphology(
    morphology: &MorphologyState,
    evidence: &BTreeMap<EntityId, EvidenceRecord>,
) -> Result<(), StateError> {
    for (id, morpheme) in &morphology.morphemes {
        if id != &morpheme.id {
            return Err(StateError::validation(format!(
                "morpheme map key {id} does not match embedded ID"
            )));
        }
        ensure_kind(id, EntityKind::Morpheme, "morpheme ID")?;
        ensure_nonblank(&morpheme.gloss, "morpheme gloss")?;
        validate_evidence_ids(&morpheme.evidence_ids, evidence, "morpheme")?;
    }
    Ok(())
}

fn validate_constructions(
    constructions: &ConstructionInventory,
    morphology: &MorphologyState,
    evidence: &BTreeMap<EntityId, EvidenceRecord>,
) -> Result<(), StateError> {
    for (id, construction) in &constructions.constructions {
        if id != &construction.id {
            return Err(StateError::validation(format!(
                "construction map key {id} does not match embedded ID"
            )));
        }
        ensure_kind(id, EntityKind::Construction, "construction ID")?;
        ensure_nonblank(&construction.name, "construction name")?;
        ensure_nonblank(&construction.semantic_frame, "construction semantic frame")?;
        for morpheme_id in &construction.morpheme_ids {
            if !morphology.morphemes.contains_key(morpheme_id) {
                return Err(StateError::validation(format!(
                    "construction {id} references missing morpheme {morpheme_id}"
                )));
            }
        }
        validate_evidence_ids(&construction.evidence_ids, evidence, "construction")?;
    }
    Ok(())
}

fn validate_pragmatics(pragmatics: &PragmaticsAndRegisters) -> Result<(), StateError> {
    if pragmatics.registers.is_empty() {
        return Err(StateError::validation("at least one register is required"));
    }
    if !pragmatics
        .registers
        .contains_key(&pragmatics.default_register)
    {
        return Err(StateError::validation(format!(
            "default register {:?} is not declared",
            pragmatics.default_register
        )));
    }
    for (name, register) in &pragmatics.registers {
        ensure_nonblank(name, "register name")?;
        ensure_nonblank(&register.description, "register description")?;
        if register.formality_basis_points > BASIS_POINTS {
            return Err(StateError::validation(format!(
                "register {name:?} has an invalid formality value"
            )));
        }
    }
    Ok(())
}

fn validate_lexicon(
    lexicon: &LexiconSenseGraph,
    phonology: &PhonologyState,
    morphology: &MorphologyState,
    pragmatics: &PragmaticsAndRegisters,
    evidence: &BTreeMap<EntityId, EvidenceRecord>,
) -> Result<(), StateError> {
    let mut owned_senses = BTreeSet::new();
    for (id, lexeme) in &lexicon.lexemes {
        if id != &lexeme.id {
            return Err(StateError::validation(format!(
                "lexeme map key {id} does not match embedded ID"
            )));
        }
        ensure_kind(id, EntityKind::Lexeme, "lexeme ID")?;
        if lexeme.phoneme_sequence.is_empty() {
            return Err(StateError::validation(format!(
                "lexeme {id} has an empty phoneme sequence"
            )));
        }
        if lexeme.sense_ids.is_empty() {
            return Err(StateError::validation(format!("lexeme {id} has no sense")));
        }
        if !pragmatics.registers.contains_key(&lexeme.register) {
            return Err(StateError::validation(format!(
                "lexeme {id} references unknown register {:?}",
                lexeme.register
            )));
        }
        for phoneme_id in &lexeme.phoneme_sequence {
            if !phonology.phonemes.contains_key(phoneme_id) {
                return Err(StateError::validation(format!(
                    "lexeme {id} references missing phoneme {phoneme_id}"
                )));
            }
        }
        for morpheme_id in &lexeme.morpheme_ids {
            if !morphology.morphemes.contains_key(morpheme_id) {
                return Err(StateError::validation(format!(
                    "lexeme {id} references missing morpheme {morpheme_id}"
                )));
            }
        }
        for sense_id in &lexeme.sense_ids {
            if !lexicon.senses.contains_key(sense_id) {
                return Err(StateError::validation(format!(
                    "lexeme {id} references missing sense {sense_id}"
                )));
            }
            if !owned_senses.insert(sense_id.clone()) {
                return Err(StateError::validation(format!(
                    "sense {sense_id} is owned by more than one lexeme"
                )));
            }
        }
    }

    if owned_senses.len() != lexicon.senses.len() {
        return Err(StateError::validation("lexicon contains an orphan sense"));
    }
    for (id, sense) in &lexicon.senses {
        if id != &sense.id {
            return Err(StateError::validation(format!(
                "sense map key {id} does not match embedded ID"
            )));
        }
        ensure_kind(id, EntityKind::Sense, "sense ID")?;
        ensure_nonblank(&sense.concept.catalog, "concept catalog")?;
        ensure_nonblank(&sense.concept.concept_id, "concept ID")?;
        for related_id in &sense.related_sense_ids {
            if related_id == id || !lexicon.senses.contains_key(related_id) {
                return Err(StateError::validation(format!(
                    "sense {id} has an invalid related sense {related_id}"
                )));
            }
        }
        validate_evidence_ids(&sense.evidence_ids, evidence, "sense")?;
    }
    Ok(())
}

fn validate_orthography(
    orthography: &OrthographyState,
    phonology: &PhonologyState,
) -> Result<(), StateError> {
    if let OrthographyState::Alphabetic { script, graphemes } = orthography {
        ensure_nonblank(script, "orthography script")?;
        if graphemes.is_empty() {
            return Err(StateError::validation(
                "alphabetic orthography needs at least one grapheme",
            ));
        }
        for (phoneme_id, grapheme) in graphemes {
            if !phonology.phonemes.contains_key(phoneme_id) {
                return Err(StateError::validation(format!(
                    "orthography references missing phoneme {phoneme_id}"
                )));
            }
            ensure_nonblank(grapheme, "grapheme")?;
        }
    }
    Ok(())
}

fn validate_typology(
    typology: &BTreeMap<EntityId, FeatureAssertion>,
    evidence: &BTreeMap<EntityId, EvidenceRecord>,
) -> Result<(), StateError> {
    for (feature_id, assertion) in typology {
        if feature_id != &assertion.feature_id {
            return Err(StateError::validation(format!(
                "typology map key {feature_id} does not match embedded feature ID"
            )));
        }
        ensure_kind(feature_id, EntityKind::Feature, "typological feature ID")?;
        ensure_nonblank(&assertion.value, "typological feature value")?;
        if assertion.evidence_ids.is_empty() {
            return Err(StateError::validation(format!(
                "typological feature {feature_id} requires at least one evidence record"
            )));
        }
        validate_evidence_ids(&assertion.evidence_ids, evidence, "typological feature")?;
    }
    Ok(())
}

fn validate_family_position(position: &FamilyPosition) -> Result<(), StateError> {
    ensure_kind(&position.node_id, EntityKind::FamilyNode, "family node ID")?;
    if position.community_ids.is_empty() {
        return Err(StateError::validation(
            "family position needs at least one speech community",
        ));
    }
    if let Some(parent_language_id) = &position.parent_language_id {
        ensure_kind(
            parent_language_id,
            EntityKind::Language,
            "parent language ID",
        )?;
    }
    for community_id in &position.community_ids {
        ensure_kind(
            community_id,
            EntityKind::SpeechCommunity,
            "speech community ID",
        )?;
    }
    Ok(())
}

fn validate_provenance(state: &LanguageState) -> Result<(), StateError> {
    for (id, entry) in &state.provenance.entries {
        if id != &entry.entity_id {
            return Err(StateError::validation(format!(
                "provenance key {id} does not match embedded entity ID {}",
                entry.entity_id
            )));
        }
        ensure_kind(&entry.event_id, EntityKind::Event, "provenance event ID")?;
        entry
            .created_at
            .validate()
            .map_err(|error| StateError::validation(error.to_string()))?;
        if entry.created_at.time_model_fingerprint() != state.as_of.time_model_fingerprint() {
            return Err(StateError::validation(format!(
                "provenance for {id} references a different time model"
            )));
        }
        if entry.created_at.year() > state.as_of.year() {
            return Err(StateError::validation(format!(
                "provenance for {id} occurs after the language-state timestamp"
            )));
        }
        validate_evidence_ids(&entry.evidence_ids, &state.evidence, "provenance")?;
    }
    for required_id in state.semantic_entity_ids() {
        if !state.provenance.entries.contains_key(&required_id) {
            return Err(StateError::validation(format!(
                "missing provenance for semantic entity {required_id}"
            )));
        }
    }
    Ok(())
}

fn validate_evidence_ids(
    evidence_ids: &BTreeSet<EntityId>,
    evidence: &BTreeMap<EntityId, EvidenceRecord>,
    context: &str,
) -> Result<(), StateError> {
    for evidence_id in evidence_ids {
        ensure_kind(evidence_id, EntityKind::Evidence, "evidence reference")?;
        if !evidence.contains_key(evidence_id) {
            return Err(StateError::validation(format!(
                "{context} references missing evidence {evidence_id}"
            )));
        }
    }
    Ok(())
}

fn ensure_kind(id: &EntityId, expected: EntityKind, label: &str) -> Result<(), StateError> {
    if id.kind() == expected {
        Ok(())
    } else {
        Err(StateError::validation(format!(
            "{label} {id} has kind {:?}, expected {:?}",
            id.kind(),
            expected
        )))
    }
}

fn ensure_nonblank(value: &str, label: &str) -> Result<(), StateError> {
    if value.trim().is_empty() {
        Err(StateError::validation(format!("{label} must not be blank")))
    } else {
        Ok(())
    }
}

#[cfg(test)]
pub(crate) fn fixture_minimal_state() -> LanguageState {
    tests::minimal_state()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hash::SemanticHasher;
    use crate::time::{SimYear, TimeModel};

    fn id(kind: EntityKind, value: &str) -> EntityId {
        EntityId::new(kind, value).expect("valid entity ID")
    }

    pub(crate) fn minimal_state() -> LanguageState {
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

    #[test]
    fn canonical_state_round_trips_and_excludes_derived_statistics() {
        let state = minimal_state();
        let encoded = state.canonical_json().expect("canonical state");
        let restored: LanguageState = serde_json::from_slice(&encoded).expect("state round trip");

        assert_eq!(restored, state);
        assert_eq!(
            state.corpus_statistics(),
            CorpusStatistics {
                phoneme_count: 2,
                morpheme_count: 0,
                construction_count: 0,
                lexeme_count: 1,
                sense_count: 1,
                register_count: 1,
            }
        );
        assert!(!String::from_utf8(encoded)
            .expect("utf-8 JSON")
            .contains("corpusStatistics"));
    }

    #[test]
    fn legacy_state_time_references_require_explicit_migration() {
        let state = minimal_state();
        let source_time_model = TimeModel::new(SimYear(0), 25, 1).expect("time model");
        let mut legacy = serde_json::to_value(&state).expect("state JSON");
        legacy["schemaVersion"] =
            serde_json::Value::String(LEGACY_LANGUAGE_STATE_SCHEMA_V1.to_owned());
        legacy["asOf"]["timeModelSchema"] =
            serde_json::Value::String(crate::time::LEGACY_TIME_MODEL_SCHEMA_V1.to_owned());
        legacy["asOf"]
            .as_object_mut()
            .expect("asOf object")
            .remove("timeModelFingerprint");
        for entry in legacy["provenance"]["entries"]
            .as_object_mut()
            .expect("provenance entries")
            .values_mut()
        {
            entry["createdAt"]["timeModelSchema"] =
                serde_json::Value::String(crate::time::LEGACY_TIME_MODEL_SCHEMA_V1.to_owned());
            entry["createdAt"]
                .as_object_mut()
                .expect("createdAt object")
                .remove("timeModelFingerprint");
        }

        assert!(serde_json::from_value::<LanguageState>(legacy.clone()).is_err());
        let migrated =
            migrate_legacy_language_state_v1_json(legacy, &source_time_model).expect("migration");
        assert_eq!(migrated, state);
    }

    #[test]
    fn state_rejects_missing_provenance_and_invalid_lexical_references() {
        let mut missing_provenance = minimal_state();
        let language_id = missing_provenance.language_id().clone();
        missing_provenance.provenance.entries.remove(&language_id);
        assert!(missing_provenance.validate().is_err());

        let mut missing_phoneme = minimal_state();
        let lexeme = missing_phoneme
            .lexicon
            .lexemes
            .values_mut()
            .next()
            .expect("lexeme");
        lexeme
            .phoneme_sequence
            .push(id(EntityKind::Phoneme, "missing"));
        assert!(missing_phoneme.validate().is_err());
    }

    #[test]
    fn deserialization_rejects_missing_provenance_and_unsourced_typology() {
        let state = minimal_state();
        let mut without_provenance = serde_json::to_value(&state).expect("state JSON");
        without_provenance["provenance"]["entries"]
            .as_object_mut()
            .expect("provenance object")
            .remove(state.language_id().as_str());
        assert!(serde_json::from_value::<LanguageState>(without_provenance).is_err());

        let mut unsourced_typology = minimal_state();
        let feature_id = id(EntityKind::Feature, "word-order");
        unsourced_typology.typology.insert(
            feature_id.clone(),
            FeatureAssertion {
                feature_id,
                value: "sov".to_owned(),
                evidence_ids: BTreeSet::new(),
            },
        );
        assert!(unsourced_typology.validate().is_err());
    }

    #[test]
    fn semantic_hashes_are_stable_and_localize_a_lexical_change() {
        let state = minimal_state();
        let baseline = SemanticHasher::hash(&state).expect("baseline hash");
        assert_eq!(baseline.domains.len(), SemanticDomain::ALL.len());
        assert_eq!(baseline, SemanticHasher::hash(&state).expect("repeat hash"));

        let mut altered = state.clone();
        let vowel_id = altered
            .phonology
            .phonemes
            .iter()
            .find(|(_, phoneme)| phoneme.class == SegmentClass::Vowel)
            .map(|(id, _)| id.clone())
            .expect("vowel");
        altered
            .lexicon
            .lexemes
            .values_mut()
            .next()
            .expect("lexeme")
            .phoneme_sequence
            .push(vowel_id);
        let changed = SemanticHasher::hash(&altered).expect("changed hash");

        assert_ne!(baseline.full, changed.full);
        assert_ne!(baseline.domains["lexicon"], changed.domains["lexicon"]);
        assert_eq!(baseline.domains["phonology"], changed.domains["phonology"]);
    }
}
