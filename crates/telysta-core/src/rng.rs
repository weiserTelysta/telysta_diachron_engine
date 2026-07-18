//! Versioned deterministic random streams derived from stable paths.
//!
//! A stream is keyed only by the root seed and its declared path. Creating or
//! consuming another stream cannot affect it, so adding a new simulation
//! module does not perturb existing random choices.

use std::{error::Error, fmt};

use sha2::{Digest, Sha256};

pub const RNG_TREE_SCHEMA: &str = "telysta-rng-tree.v1";

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct RngPath(Vec<String>);

impl RngPath {
    pub fn parse(path: impl AsRef<str>) -> Result<Self, RngError> {
        let path = path.as_ref();
        if path.is_empty() {
            return Err(RngError::InvalidPath(path.to_owned()));
        }
        let segments = path.split('.').map(str::to_owned).collect::<Vec<_>>();
        if segments.iter().any(|segment| {
            segment.is_empty()
                || segment.len() > 64
                || !segment.bytes().all(|byte| {
                    byte.is_ascii_lowercase()
                        || byte.is_ascii_digit()
                        || byte == b'-'
                        || byte == b'_'
                })
        }) {
            return Err(RngError::InvalidPath(path.to_owned()));
        }
        Ok(Self(segments))
    }

    pub fn as_str(&self) -> String {
        self.0.join(".")
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RngTree {
    root_seed: u64,
}

impl RngTree {
    pub const fn new(root_seed: u64) -> Self {
        Self { root_seed }
    }

    pub fn stream(&self, path: &RngPath) -> DeterministicRng {
        let mut hasher = Sha256::new();
        hasher.update(RNG_TREE_SCHEMA.as_bytes());
        hasher.update(self.root_seed.to_le_bytes());
        for segment in &path.0 {
            hasher.update((segment.len() as u32).to_le_bytes());
            hasher.update(segment.as_bytes());
        }
        DeterministicRng {
            key: hasher.finalize().into(),
            counter: 0,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DeterministicRng {
    key: [u8; 32],
    counter: u64,
}

impl DeterministicRng {
    pub fn next_u64(&mut self) -> u64 {
        let mut hasher = Sha256::new();
        hasher.update(RNG_TREE_SCHEMA.as_bytes());
        hasher.update(self.key);
        hasher.update(self.counter.to_le_bytes());
        self.counter = self.counter.wrapping_add(1);
        let digest = hasher.finalize();
        u64::from_le_bytes(digest[..8].try_into().expect("SHA-256 digest has 32 bytes"))
    }

    pub fn uniform(&mut self, upper_exclusive: u64) -> Result<u64, RngError> {
        if upper_exclusive == 0 {
            return Err(RngError::ZeroUpperBound);
        }
        let accepted_upper = u64::MAX - u64::MAX % upper_exclusive;
        loop {
            let value = self.next_u64();
            if value < accepted_upper {
                return Ok(value % upper_exclusive);
            }
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RngError {
    InvalidPath(String),
    ZeroUpperBound,
}

impl fmt::Display for RngError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidPath(path) => write!(
                formatter,
                "invalid RNG path {path:?}; use dot-separated lowercase ASCII segments"
            ),
            Self::ZeroUpperBound => {
                formatter.write_str("RNG upper bound must be greater than zero")
            }
        }
    }
}

impl Error for RngError {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn same_seed_and_path_produce_the_same_sequence() {
        let path = RngPath::parse("genesis.phonology").expect("path");
        let mut first = RngTree::new(888).stream(&path);
        let mut second = RngTree::new(888).stream(&path);
        assert_eq!(
            (0..8).map(|_| first.next_u64()).collect::<Vec<_>>(),
            (0..8).map(|_| second.next_u64()).collect::<Vec<_>>()
        );
    }

    #[test]
    fn streams_are_isolated_from_other_paths_and_consumption_order() {
        let tree = RngTree::new(888);
        let phonology = RngPath::parse("genesis.phonology").expect("path");
        let lexicon = RngPath::parse("genesis.lexicon").expect("path");
        let mut baseline = tree.stream(&phonology);
        let expected = (0..4).map(|_| baseline.next_u64()).collect::<Vec<_>>();

        let mut unrelated = tree.stream(&lexicon);
        for _ in 0..100 {
            unrelated.next_u64();
        }
        let mut after_unrelated_work = tree.stream(&phonology);
        assert_eq!(
            expected,
            (0..4)
                .map(|_| after_unrelated_work.next_u64())
                .collect::<Vec<_>>()
        );
    }

    #[test]
    fn paths_and_bounds_are_validated() {
        assert!(RngPath::parse("Genesis.Phonology").is_err());
        assert!(RngPath::parse("genesis..phonology").is_err());
        let path = RngPath::parse("genesis.lexicon").expect("path");
        assert_eq!(path.as_str(), "genesis.lexicon");
        assert!(matches!(
            RngTree::new(1).stream(&path).uniform(0),
            Err(RngError::ZeroUpperBound)
        ));
    }
}
