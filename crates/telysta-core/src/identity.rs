//! Stable, typed entity identifiers and explicit legacy-ID migration maps.
//!
//! Production state only stores validated `EntityId` values. A legacy string
//! or integer is never silently treated as a new production ID: migration
//! requires an explicit map with a declared source schema and target kind.

use std::{collections::BTreeMap, error::Error, fmt};

use serde::{Deserialize, Deserializer, Serialize, Serializer};
use sha2::{Digest, Sha256};

pub const ENTITY_ID_SCHEMA: &str = "telysta-entity-id.v1";

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EntityKind {
    Blueprint,
    Intent,
    Project,
    Run,
    Language,
    SpeechCommunity,
    FamilyNode,
    Phoneme,
    Lexeme,
    Sense,
    Morpheme,
    Construction,
    Feature,
    Evidence,
    DataSet,
    RulePack,
    Rule,
    ChangeProcess,
    Event,
}

impl EntityKind {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Blueprint => "blueprint",
            Self::Intent => "intent",
            Self::Project => "project",
            Self::Run => "run",
            Self::Language => "language",
            Self::SpeechCommunity => "speech-community",
            Self::FamilyNode => "family-node",
            Self::Phoneme => "phoneme",
            Self::Lexeme => "lexeme",
            Self::Sense => "sense",
            Self::Morpheme => "morpheme",
            Self::Construction => "construction",
            Self::Feature => "feature",
            Self::Evidence => "evidence",
            Self::DataSet => "data-set",
            Self::RulePack => "rule-pack",
            Self::Rule => "rule",
            Self::ChangeProcess => "change-process",
            Self::Event => "event",
        }
    }

    fn parse(value: &str) -> Option<Self> {
        match value {
            "blueprint" => Some(Self::Blueprint),
            "intent" => Some(Self::Intent),
            "project" => Some(Self::Project),
            "run" => Some(Self::Run),
            "language" => Some(Self::Language),
            "speech-community" => Some(Self::SpeechCommunity),
            "family-node" => Some(Self::FamilyNode),
            "phoneme" => Some(Self::Phoneme),
            "lexeme" => Some(Self::Lexeme),
            "sense" => Some(Self::Sense),
            "morpheme" => Some(Self::Morpheme),
            "construction" => Some(Self::Construction),
            "feature" => Some(Self::Feature),
            "evidence" => Some(Self::Evidence),
            "data-set" => Some(Self::DataSet),
            "rule-pack" => Some(Self::RulePack),
            "rule" => Some(Self::Rule),
            "change-process" => Some(Self::ChangeProcess),
            "event" => Some(Self::Event),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct EntityId(String);

impl EntityId {
    pub fn new(kind: EntityKind, value: impl AsRef<str>) -> Result<Self, EntityIdError> {
        let value = value.as_ref();
        validate_value(value)?;
        Ok(Self(format!("telysta:{}:{value}", kind.as_str())))
    }

    /// Derive an opaque, stable identifier from canonical inputs.
    ///
    /// `namespace` must be a project-stable identifier and `stable_key` must
    /// not contain display labels that users can later rename.
    pub fn derive(kind: EntityKind, namespace: &EntityId, stable_key: impl AsRef<str>) -> Self {
        let mut hasher = Sha256::new();
        hasher.update(ENTITY_ID_SCHEMA.as_bytes());
        hasher.update([0]);
        hasher.update(namespace.as_str().as_bytes());
        hasher.update([0]);
        hasher.update(kind.as_str().as_bytes());
        hasher.update([0]);
        hasher.update(stable_key.as_ref().as_bytes());
        let fingerprint = hasher.finalize();
        let value = fingerprint[..16]
            .iter()
            .map(|byte| format!("{byte:02x}"))
            .collect::<String>();
        Self::new(kind, value).expect("a hexadecimal digest is a valid entity ID value")
    }

    pub fn parse(value: impl Into<String>) -> Result<Self, EntityIdError> {
        let value = value.into();
        let mut components = value.split(':');
        let schema = components.next();
        let kind = components.next();
        let local = components.next();
        if schema != Some("telysta") || components.next().is_some() {
            return Err(EntityIdError::InvalidFormat(value));
        }
        let kind = kind
            .and_then(EntityKind::parse)
            .ok_or_else(|| EntityIdError::InvalidFormat(value.clone()))?;
        let local = local.ok_or_else(|| EntityIdError::InvalidFormat(value.clone()))?;
        validate_value(local)?;
        Ok(Self(format!("telysta:{}:{local}", kind.as_str())))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }

    pub fn kind(&self) -> EntityKind {
        self.0
            .split(':')
            .nth(1)
            .and_then(EntityKind::parse)
            .expect("validated EntityId always has a known kind")
    }
}

impl fmt::Display for EntityId {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.0.fmt(formatter)
    }
}

impl Serialize for EntityId {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(&self.0)
    }
}

impl<'de> Deserialize<'de> for EntityId {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let raw = String::deserialize(deserializer)?;
        Self::parse(raw).map_err(serde::de::Error::custom)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EntityIdError {
    InvalidFormat(String),
    InvalidValue(String),
}

impl fmt::Display for EntityIdError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidFormat(value) => write!(
                formatter,
                "invalid entity ID {value:?}; expected telysta:<known-kind>:<lowercase-value>"
            ),
            Self::InvalidValue(value) => write!(
                formatter,
                "invalid entity ID value {value:?}; use 1-96 lowercase ASCII letters, digits, or hyphens"
            ),
        }
    }
}

impl Error for EntityIdError {}

fn validate_value(value: &str) -> Result<(), EntityIdError> {
    let valid = !value.is_empty()
        && value.len() <= 96
        && value
            .bytes()
            .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'-')
        && !value.starts_with('-')
        && !value.ends_with('-');
    if valid {
        Ok(())
    } else {
        Err(EntityIdError::InvalidValue(value.to_owned()))
    }
}

/// A source value from the Python-era data model. Text and integer keys stay
/// distinct, so a migration cannot accidentally merge `1` with `"1"`.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(untagged)]
pub enum LegacyEntityRef {
    Text(String),
    Integer(u64),
}

impl LegacyEntityRef {
    pub fn canonical_key(&self) -> String {
        match self {
            Self::Text(value) => format!("text:{value}"),
            Self::Integer(value) => format!("integer:{value}"),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LegacyIdMap {
    source_schema: String,
    entity_kind: EntityKind,
    entries: BTreeMap<String, EntityId>,
}

impl LegacyIdMap {
    pub fn new(
        source_schema: impl Into<String>,
        entity_kind: EntityKind,
        entries: BTreeMap<String, EntityId>,
    ) -> Result<Self, LegacyIdMapError> {
        let source_schema = source_schema.into();
        if source_schema.trim().is_empty() {
            return Err(LegacyIdMapError::EmptySourceSchema);
        }
        if entries.keys().any(|key| !is_canonical_legacy_key(key)) {
            return Err(LegacyIdMapError::InvalidLegacyKey);
        }
        if entries.values().any(|id| id.kind() != entity_kind) {
            return Err(LegacyIdMapError::TargetKindMismatch);
        }
        Ok(Self {
            source_schema,
            entity_kind,
            entries,
        })
    }

    pub fn resolve(&self, legacy: &LegacyEntityRef) -> Result<&EntityId, LegacyIdMapError> {
        self.entries
            .get(&legacy.canonical_key())
            .ok_or_else(|| LegacyIdMapError::MissingLegacyKey(legacy.canonical_key()))
    }

    pub fn source_schema(&self) -> &str {
        &self.source_schema
    }

    pub fn entity_kind(&self) -> EntityKind {
        self.entity_kind
    }

    pub fn entries(&self) -> &BTreeMap<String, EntityId> {
        &self.entries
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RawLegacyIdMap {
    source_schema: String,
    entity_kind: EntityKind,
    entries: BTreeMap<String, EntityId>,
}

impl<'de> Deserialize<'de> for LegacyIdMap {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let raw = RawLegacyIdMap::deserialize(deserializer)?;
        Self::new(raw.source_schema, raw.entity_kind, raw.entries).map_err(serde::de::Error::custom)
    }
}

fn is_canonical_legacy_key(key: &str) -> bool {
    key.strip_prefix("text:")
        .is_some_and(|value| !value.is_empty())
        || key
            .strip_prefix("integer:")
            .is_some_and(|value| !value.is_empty() && value.parse::<u64>().is_ok())
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum LegacyIdMapError {
    EmptySourceSchema,
    InvalidLegacyKey,
    TargetKindMismatch,
    MissingLegacyKey(String),
}

impl fmt::Display for LegacyIdMapError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::EmptySourceSchema => formatter.write_str("legacy ID map needs a source schema"),
            Self::InvalidLegacyKey => formatter.write_str(
                "legacy ID map keys must be canonical text:<value> or integer:<unsigned-value> keys",
            ),
            Self::TargetKindMismatch => formatter.write_str(
                "legacy ID map contains a target whose entity kind differs from the declared kind",
            ),
            Self::MissingLegacyKey(key) => {
                write!(formatter, "legacy ID map has no entry for {key:?}")
            }
        }
    }
}

impl Error for LegacyIdMapError {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn entity_ids_are_typed_and_validated() {
        let id = EntityId::new(EntityKind::Language, "proto-telysta-1").expect("valid ID");
        assert_eq!(id.as_str(), "telysta:language:proto-telysta-1");
        assert_eq!(id.kind(), EntityKind::Language);
        assert!(EntityId::parse("telysta:language:PROTOTELYSTA").is_err());
        assert!(EntityId::parse("1").is_err());
    }

    #[test]
    fn derived_ids_are_repeatable_and_namespaced() {
        let project = EntityId::new(EntityKind::Project, "demo-project").expect("valid ID");
        let first = EntityId::derive(EntityKind::Lexeme, &project, "swadesh:water");
        let second = EntityId::derive(EntityKind::Lexeme, &project, "swadesh:water");
        let other_kind = EntityId::derive(EntityKind::Rule, &project, "swadesh:water");

        assert_eq!(first, second);
        assert_ne!(first, other_kind);
        assert_eq!(first.kind(), EntityKind::Lexeme);
    }

    #[test]
    fn legacy_maps_do_not_merge_text_and_integer_keys() {
        let target = EntityId::new(EntityKind::Lexeme, "water").expect("valid ID");
        let map = LegacyIdMap::new(
            "telysta.legacy-state.v1",
            EntityKind::Lexeme,
            BTreeMap::from([(LegacyEntityRef::Integer(1).canonical_key(), target.clone())]),
        )
        .expect("valid migration map");

        assert_eq!(map.resolve(&LegacyEntityRef::Integer(1)), Ok(&target));
        assert!(matches!(
            map.resolve(&LegacyEntityRef::Text("1".to_owned())),
            Err(LegacyIdMapError::MissingLegacyKey(_))
        ));
    }

    #[test]
    fn legacy_map_deserialization_cannot_bypass_validation() {
        let empty_schema = r#"{
            "sourceSchema":"",
            "entityKind":"lexeme",
            "entries":{"integer:1":"telysta:lexeme:water"}
        }"#;
        let mismatched_target = r#"{
            "sourceSchema":"telysta.legacy-state.v1",
            "entityKind":"lexeme",
            "entries":{"integer:1":"telysta:rule:water"}
        }"#;
        let noncanonical_key = r#"{
            "sourceSchema":"telysta.legacy-state.v1",
            "entityKind":"lexeme",
            "entries":{"1":"telysta:lexeme:water"}
        }"#;

        assert!(serde_json::from_str::<LegacyIdMap>(empty_schema).is_err());
        assert!(serde_json::from_str::<LegacyIdMap>(mismatched_target).is_err());
        assert!(serde_json::from_str::<LegacyIdMap>(noncanonical_key).is_err());
    }
}
