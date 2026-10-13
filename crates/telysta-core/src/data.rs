//! Versioned metadata for empirical and curated data sources.
//!
//! The core never treats a typological or lexical dataset as a language
//! template. A manifest records what data was used, what it covers, and what
//! its limits are; evidence in `LanguageState` can then cite stable records.

use std::{collections::BTreeMap, error::Error, fmt};

use serde::{Deserialize, Deserializer, Serialize};
use sha2::{Digest, Sha256};

use crate::identity::{EntityId, EntityKind};

pub const DATA_MANIFEST_SCHEMA: &str = "telysta-data-manifest.v1";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum DataFormat {
    CldfWordlist,
    CldfStructureDataset,
    Json,
    Csv,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum SamplingUnit {
    Inventory,
    Doculect,
    Language,
    Variety,
    FeatureValue,
    ConceptSet,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DataCoverage {
    pub sampling_unit: SamplingUnit,
    pub description: String,
    pub record_count: Option<u32>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DataManifestParts {
    pub id: EntityId,
    pub title: String,
    pub version: String,
    pub license: String,
    pub citation: String,
    pub pinned_uri: String,
    pub format: DataFormat,
    pub content_sha256: Option<String>,
    pub coverage: DataCoverage,
    pub limitations: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DataManifest {
    schema_version: String,
    id: EntityId,
    title: String,
    version: String,
    license: String,
    citation: String,
    pinned_uri: String,
    format: DataFormat,
    content_sha256: Option<String>,
    coverage: DataCoverage,
    limitations: Vec<String>,
}

impl DataManifest {
    pub fn new(parts: DataManifestParts) -> Result<Self, DataError> {
        Self::from_parts(DATA_MANIFEST_SCHEMA.to_owned(), parts)
    }

    pub fn id(&self) -> &EntityId {
        &self.id
    }

    pub fn version(&self) -> &str {
        &self.version
    }

    pub fn pinned_uri(&self) -> &str {
        &self.pinned_uri
    }

    pub fn content_sha256(&self) -> Option<&str> {
        self.content_sha256.as_deref()
    }

    pub fn format(&self) -> DataFormat {
        self.format
    }

    /// Verify a locked payload's exact bytes before a data adapter consumes it.
    ///
    /// This proves checksum integrity only. It does not parse the data, check
    /// record membership, approve its license, or validate an empirical claim.
    /// Metadata-only catalog entries remain valid but cannot verify a payload.
    pub fn verify_payload_checksum(&self, payload: &[u8]) -> Result<(), DataError> {
        self.validate()?;
        let expected = self.content_sha256().ok_or_else(|| {
            DataError::Validation(format!(
                "data set {} requires a pinned content SHA-256 before payload use",
                self.id
            ))
        })?;
        let actual = format!("{:x}", Sha256::digest(payload));
        if actual != expected {
            return Err(DataError::Validation(format!(
                "data set {} payload SHA-256 mismatch: expected {expected}, got {actual}",
                self.id
            )));
        }
        Ok(())
    }

    pub fn validate_reference(&self, reference: &DataReference) -> Result<(), DataError> {
        if reference.dataset_id != self.id {
            return Err(DataError::UnknownDataSet(reference.dataset_id.clone()));
        }
        Ok(())
    }

    pub fn validate(&self) -> Result<(), DataError> {
        if self.schema_version != DATA_MANIFEST_SCHEMA {
            return Err(DataError::UnsupportedSchema(self.schema_version.clone()));
        }
        ensure_kind(&self.id, EntityKind::DataSet, "data manifest ID")?;
        ensure_nonblank(&self.title, "data manifest title")?;
        ensure_nonblank(&self.version, "data manifest version")?;
        ensure_nonblank(&self.license, "data manifest license")?;
        ensure_nonblank(&self.citation, "data manifest citation")?;
        if !self.pinned_uri.starts_with("https://") {
            return Err(DataError::Validation(
                "data manifest pinned URI must use https".to_owned(),
            ));
        }
        ensure_nonblank(&self.coverage.description, "data coverage description")?;
        if self.limitations.is_empty()
            || self.limitations.iter().any(|value| value.trim().is_empty())
        {
            return Err(DataError::Validation(
                "data manifest must declare at least one non-blank limitation".to_owned(),
            ));
        }
        if let Some(content_sha256) = &self.content_sha256 {
            if content_sha256.len() != 64
                || !content_sha256
                    .bytes()
                    .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase())
            {
                return Err(DataError::Validation(
                    "data manifest content SHA-256 must be 64 lowercase hexadecimal characters"
                        .to_owned(),
                ));
            }
        }
        Ok(())
    }

    fn from_parts(schema_version: String, parts: DataManifestParts) -> Result<Self, DataError> {
        let manifest = Self {
            schema_version,
            id: parts.id,
            title: parts.title,
            version: parts.version,
            license: parts.license,
            citation: parts.citation,
            pinned_uri: parts.pinned_uri,
            format: parts.format,
            content_sha256: parts.content_sha256,
            coverage: parts.coverage,
            limitations: parts.limitations,
        };
        manifest.validate()?;
        Ok(manifest)
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RawDataManifest {
    schema_version: String,
    id: EntityId,
    title: String,
    version: String,
    license: String,
    citation: String,
    pinned_uri: String,
    format: DataFormat,
    content_sha256: Option<String>,
    coverage: DataCoverage,
    limitations: Vec<String>,
}

impl<'de> Deserialize<'de> for DataManifest {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let raw = RawDataManifest::deserialize(deserializer)?;
        Self::from_parts(
            raw.schema_version,
            DataManifestParts {
                id: raw.id,
                title: raw.title,
                version: raw.version,
                license: raw.license,
                citation: raw.citation,
                pinned_uri: raw.pinned_uri,
                format: raw.format,
                content_sha256: raw.content_sha256,
                coverage: raw.coverage,
                limitations: raw.limitations,
            },
        )
        .map_err(serde::de::Error::custom)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DataReference {
    dataset_id: EntityId,
    table: String,
    record_id: String,
}

impl DataReference {
    pub fn new(
        dataset_id: EntityId,
        table: impl Into<String>,
        record_id: impl Into<String>,
    ) -> Result<Self, DataError> {
        let reference = Self {
            dataset_id,
            table: table.into(),
            record_id: record_id.into(),
        };
        reference.validate()?;
        Ok(reference)
    }

    pub fn dataset_id(&self) -> &EntityId {
        &self.dataset_id
    }

    pub fn table(&self) -> &str {
        &self.table
    }

    pub fn record_id(&self) -> &str {
        &self.record_id
    }

    pub fn validate(&self) -> Result<(), DataError> {
        ensure_kind(
            &self.dataset_id,
            EntityKind::DataSet,
            "data reference dataset ID",
        )?;
        ensure_nonblank(&self.table, "data reference table")?;
        ensure_nonblank(&self.record_id, "data reference record ID")?;
        Ok(())
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RawDataReference {
    dataset_id: EntityId,
    table: String,
    record_id: String,
}

impl<'de> Deserialize<'de> for DataReference {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let raw = RawDataReference::deserialize(deserializer)?;
        Self::new(raw.dataset_id, raw.table, raw.record_id).map_err(serde::de::Error::custom)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DataRegistry {
    manifests: BTreeMap<EntityId, DataManifest>,
}

impl DataRegistry {
    pub fn new(manifests: Vec<DataManifest>) -> Result<Self, DataError> {
        let mut indexed = BTreeMap::new();
        for manifest in manifests {
            manifest.validate()?;
            if indexed.insert(manifest.id.clone(), manifest).is_some() {
                return Err(DataError::DuplicateDataSet);
            }
        }
        Ok(Self { manifests: indexed })
    }

    pub fn validate_reference(&self, reference: &DataReference) -> Result<(), DataError> {
        reference.validate()?;
        self.manifests
            .get(reference.dataset_id())
            .ok_or_else(|| DataError::UnknownDataSet(reference.dataset_id().clone()))?
            .validate_reference(reference)
    }

    pub fn manifests(&self) -> &BTreeMap<EntityId, DataManifest> {
        &self.manifests
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DataError {
    UnsupportedSchema(String),
    Validation(String),
    UnknownDataSet(EntityId),
    DuplicateDataSet,
}

impl fmt::Display for DataError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::UnsupportedSchema(schema) => write!(
                formatter,
                "unsupported data-manifest schema {schema:?}; expected {DATA_MANIFEST_SCHEMA}"
            ),
            Self::Validation(message) => formatter.write_str(message),
            Self::UnknownDataSet(id) => write!(formatter, "unknown data set {id}"),
            Self::DuplicateDataSet => {
                formatter.write_str("data registry contains a duplicate data-set ID")
            }
        }
    }
}

impl Error for DataError {}

fn ensure_kind(id: &EntityId, expected: EntityKind, label: &str) -> Result<(), DataError> {
    if id.kind() == expected {
        Ok(())
    } else {
        Err(DataError::Validation(format!(
            "{label} {id} has kind {:?}, expected {:?}",
            id.kind(),
            expected
        )))
    }
}

fn ensure_nonblank(value: &str, label: &str) -> Result<(), DataError> {
    if value.trim().is_empty() {
        Err(DataError::Validation(format!("{label} must not be blank")))
    } else {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn id(value: &str) -> EntityId {
        EntityId::new(EntityKind::DataSet, value).expect("valid data-set ID")
    }

    fn manifest() -> DataManifest {
        DataManifest::new(DataManifestParts {
            id: id("fixture-cldf"),
            title: "Fixture CLDF".to_owned(),
            version: "1.0.0".to_owned(),
            license: "CC-BY-4.0".to_owned(),
            citation: "Fixture et al. 2026".to_owned(),
            pinned_uri: "https://example.invalid/fixture-1.0.0.zip".to_owned(),
            format: DataFormat::CldfWordlist,
            content_sha256: Some("0".repeat(64)),
            coverage: DataCoverage {
                sampling_unit: SamplingUnit::Language,
                description: "One fixture language".to_owned(),
                record_count: Some(1),
            },
            limitations: vec!["Fixture data has no empirical value.".to_owned()],
        })
        .expect("valid manifest")
    }

    #[test]
    fn payload_checksum_is_required_before_consuming_catalog_data() {
        let mut catalog_entry = manifest();
        catalog_entry.content_sha256 = None;
        catalog_entry
            .validate()
            .expect("metadata-only catalog is valid");
        let error = catalog_entry.verify_payload_checksum(b"{}").unwrap_err();
        assert!(error
            .to_string()
            .contains("requires a pinned content SHA-256"));
    }

    #[test]
    fn payload_checksum_verifies_exact_bytes_not_normalized_json() {
        let mut locked = manifest();
        // SHA-256 known answer for the two raw bytes "{}".
        locked.content_sha256 =
            Some("44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a".to_owned());
        locked
            .verify_payload_checksum(b"{}")
            .expect("matching raw bytes");
        for changed in [b"{}\n".as_slice(), b"{ }", b"[]", b""] {
            let error = locked.verify_payload_checksum(changed).unwrap_err();
            assert!(error.to_string().contains("payload SHA-256 mismatch"));
        }
    }

    #[test]
    fn manifests_and_references_are_versioned_and_validated() {
        let manifest = manifest();
        let registry = DataRegistry::new(vec![manifest.clone()]).expect("registry");
        let reference =
            DataReference::new(manifest.id().clone(), "FormTable", "water").expect("reference");
        registry
            .validate_reference(&reference)
            .expect("known reference");
        assert_eq!(manifest.version(), "1.0.0");
        assert_eq!(manifest.format(), DataFormat::CldfWordlist);
    }

    #[test]
    fn manifest_deserialization_rejects_missing_limitations_and_bad_hashes() {
        let no_limitations = r#"{
            "schemaVersion":"telysta-data-manifest.v1",
            "id":"telysta:data-set:fixture",
            "title":"Fixture",
            "version":"1",
            "license":"CC-BY-4.0",
            "citation":"Fixture",
            "pinnedUri":"https://example.invalid/fixture",
            "format":"json",
            "contentSha256":null,
            "coverage":{"samplingUnit":"language","description":"fixture","recordCount":1},
            "limitations":[]
        }"#;
        let invalid_hash = no_limitations
            .replace("\"limitations\":[]", "\"limitations\":[\"fixture\"]")
            .replace("\"contentSha256\":null", "\"contentSha256\":\"bad\"");

        assert!(serde_json::from_str::<DataManifest>(no_limitations).is_err());
        assert!(serde_json::from_str::<DataManifest>(&invalid_hash).is_err());
    }

    #[test]
    fn curated_manifest_samples_are_valid_and_distinct() {
        let manifests = [
            include_str!("../../../data/manifests/phoible-2.0.json"),
            include_str!("../../../data/manifests/concepticon-3.4.0.json"),
            include_str!("../../../data/manifests/grambank-1.0.3.json"),
        ]
        .into_iter()
        .map(serde_json::from_str::<DataManifest>)
        .collect::<Result<Vec<_>, _>>()
        .expect("curated manifests");

        let registry = DataRegistry::new(manifests).expect("distinct manifest IDs");
        assert_eq!(registry.manifests().len(), 3);
    }
}
