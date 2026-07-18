//! Stable semantic hashing for canonical language states.

use std::collections::BTreeMap;

use serde::Serialize;
use sha2::{Digest, Sha256};

use crate::state::{LanguageState, SemanticDomain, StateError};

pub const SEMANTIC_HASH_SCHEMA: &str = "telysta-semantic-hash.v1";

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SemanticHashReport {
    pub schema_version: &'static str,
    pub full: String,
    pub domains: BTreeMap<String, String>,
}

pub struct SemanticHasher;

impl SemanticHasher {
    pub fn hash(state: &LanguageState) -> Result<SemanticHashReport, StateError> {
        let mut domains = BTreeMap::new();
        for domain in SemanticDomain::ALL {
            let bytes = state.semantic_domain_json(domain)?;
            domains.insert(domain.as_str().to_owned(), sha256_hex(&bytes));
        }
        Ok(SemanticHashReport {
            schema_version: SEMANTIC_HASH_SCHEMA,
            full: sha256_hex(&state.canonical_json()?),
            domains,
        })
    }
}

pub fn sha256_hex(bytes: &[u8]) -> String {
    Sha256::digest(bytes)
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}
