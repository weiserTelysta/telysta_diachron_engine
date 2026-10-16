//! Distinct project, operation, run, job and attempt identities (ADR-011).
//!
//! These wrappers do not extend the frozen `telysta-entity-id.v1` kind catalog.
//! Project/run strings retain their existing representation; the three new
//! execution identities are not accepted by the legacy `EntityId` parser.
//! The containing Operation/Run/Job records still need their own schema and
//! relationship validation: parsing an ID does not prove an object exists.
//!
//! ```compile_fail
//! use telysta_core::execution_identity::{ProjectId, RunId};
//! let _: ProjectId = RunId::new("same-local-value").unwrap();
//! ```
//!
//! ```compile_fail
//! use telysta_core::execution_identity::{OperationId, ProjectId};
//! let _: OperationId = ProjectId::new("same-local-value").unwrap();
//! ```
//!
//! ```compile_fail
//! use telysta_core::execution_identity::{RunId, OperationId};
//! let _: RunId = OperationId::new("same-local-value").unwrap();
//! ```
//!
//! ```compile_fail
//! use telysta_core::execution_identity::{JobId, RunId};
//! let _: JobId = RunId::new("same-local-value").unwrap();
//! ```
//!
//! ```compile_fail
//! use telysta_core::execution_identity::{AttemptId, JobId};
//! let _: AttemptId = JobId::new("same-local-value").unwrap();
//! ```

use std::{error::Error, fmt, str::FromStr};

use serde::{Deserialize, Deserializer, Serialize, Serializer};

use crate::identity::{validate_value, EntityId, EntityIdError};

/// Identifies this wrapper vocabulary, not a project-file or record format.
pub const EXECUTION_ID_SCHEMA: &str = "telysta-execution-id.v1";

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ExecutionIdError {
    WrongPrefix {
        expected_prefix: &'static str,
        value: String,
    },
    InvalidLocalValue(EntityIdError),
}

impl fmt::Display for ExecutionIdError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::WrongPrefix {
                expected_prefix,
                value,
            } => write!(
                formatter,
                "invalid execution ID {value:?}; expected {expected_prefix}<local-value>"
            ),
            Self::InvalidLocalValue(error) => error.fmt(formatter),
        }
    }
}

impl Error for ExecutionIdError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            Self::InvalidLocalValue(error) => Some(error),
            Self::WrongPrefix { .. } => None,
        }
    }
}

// Keep all five wrappers on the same byte-level grammar, without exposing a
// generic ID or a conversion that could erase an operation/job distinction.
macro_rules! execution_id {
    ($name:ident, $kind:literal, $description:literal) => {
        #[doc = $description]
        #[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
        pub struct $name(String);

        impl $name {
            pub fn new(local_value: impl AsRef<str>) -> Result<Self, ExecutionIdError> {
                let local_value = local_value.as_ref();
                validate_value(local_value).map_err(ExecutionIdError::InvalidLocalValue)?;
                Ok(Self(format!(
                    concat!("telysta:", $kind, ":{}"),
                    local_value
                )))
            }

            pub fn parse(value: impl Into<String>) -> Result<Self, ExecutionIdError> {
                let value = value.into();
                let local_value = value
                    .strip_prefix(concat!("telysta:", $kind, ":"))
                    .ok_or_else(|| ExecutionIdError::WrongPrefix {
                        expected_prefix: concat!("telysta:", $kind, ":"),
                        value: value.clone(),
                    })?;
                validate_value(local_value).map_err(ExecutionIdError::InvalidLocalValue)?;
                Ok(Self(value))
            }

            pub fn as_str(&self) -> &str {
                &self.0
            }
        }

        impl FromStr for $name {
            type Err = ExecutionIdError;

            fn from_str(value: &str) -> Result<Self, Self::Err> {
                Self::parse(value)
            }
        }

        impl fmt::Display for $name {
            fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
                self.0.fmt(formatter)
            }
        }

        impl Serialize for $name {
            fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
            where
                S: Serializer,
            {
                serializer.serialize_str(self.as_str())
            }
        }

        impl<'de> Deserialize<'de> for $name {
            fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
            where
                D: Deserializer<'de>,
            {
                let raw = String::deserialize(deserializer)?;
                Self::parse(raw).map_err(serde::de::Error::custom)
            }
        }
    };
}

execution_id!(ProjectId, "project", "A long-lived project identity.");
execution_id!(
    OperationId,
    "operation",
    "A semantic request identity, independent of execution attempts."
);
execution_id!(
    RunId,
    "run",
    "An immutable deterministic input identity under an operation."
);
execution_id!(
    JobId,
    "job",
    "A scheduling identity; never a language-history identity."
);
execution_id!(
    AttemptId,
    "attempt",
    "One execution attempt; restarting creates a new attempt."
);

// Only the two existing v1 kinds have an explicit checked legacy conversion.
// New operation/job/attempt IDs cannot be smuggled through EntityId v1.
impl TryFrom<&EntityId> for ProjectId {
    type Error = ExecutionIdError;

    fn try_from(value: &EntityId) -> Result<Self, Self::Error> {
        Self::parse(value.as_str())
    }
}

impl TryFrom<&EntityId> for RunId {
    type Error = ExecutionIdError;

    fn try_from(value: &EntityId) -> Result<Self, Self::Error> {
        Self::parse(value.as_str())
    }
}
