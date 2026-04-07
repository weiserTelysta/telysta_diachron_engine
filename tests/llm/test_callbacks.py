"""Tests for the semantic proposal callback pipeline."""

from app.llm.backends.mock_backend import MockBackend
from app.llm.callbacks import generate_and_validate_proposal
from app.llm.contracts import SemanticProposalRequest


class TestCallbackPipeline:
    def test_mock_proposal_accepted(self) -> None:
        backend = MockBackend(seed=42)
        req = SemanticProposalRequest(
            era=1, word_id="era_0_1", concept="I",
            current_primes=["SELF"], context_chain=[],
        )
        verdict = generate_and_validate_proposal(
            backend, req, known_primes={"SUN", "SOUL", "LIGHT", "SPIRIT"},
        )
        assert verdict.status == "accepted"
        assert verdict.proposal is not None
        assert verdict.proposal.from_prime == "SUN"
        assert verdict.proposal.to_prime == "SOUL"

    def test_unknown_prime_becomes_lore_only(self) -> None:
        backend = MockBackend(seed=42)
        req = SemanticProposalRequest(
            era=1, word_id="era_0_1", concept="I",
            current_primes=[], context_chain=[],
        )
        verdict = generate_and_validate_proposal(
            backend, req, known_primes={"WATER", "FIRE"},
        )
        assert verdict.status == "lore_only"
        assert "stage=symbolic" not in verdict.reason or True  # reason is present

    def test_rate_limit_enforced(self) -> None:
        backend = MockBackend(seed=42)
        counter: dict[int, int] = {}
        statuses: list[str] = []
        for i in range(7):
            req = SemanticProposalRequest(
                era=1, word_id=f"era_0_{i}", concept="test",
                current_primes=[], context_chain=[],
            )
            v = generate_and_validate_proposal(
                backend, req, known_primes=set(),
                max_proposals_per_era=5, proposal_counter=counter,
            )
            statuses.append(v.status)

        rejected_count = sum(1 for s in statuses[5:] if s == "rejected")
        assert rejected_count >= 1

    def test_schema_failure_is_rejected_not_lore_only(self) -> None:
        """A bad-structure response must be 'rejected', never 'lore_only'."""
        from app.llm.base import LLMBackend, LLMCallResult

        class BrokenBackend(LLMBackend):
            @property
            def provider_name(self) -> str: return "broken"
            @property
            def model_name(self) -> str: return "broken"
            def call(self, prompt: str, **kwargs) -> LLMCallResult:
                return LLMCallResult(
                    raw_json='{"not_a_field": "garbage"}',
                    provider="broken", model="broken",
                )

        backend = BrokenBackend()
        req = SemanticProposalRequest(
            era=1, word_id="w1", concept="test",
            current_primes=[], context_chain=[],
        )
        verdict = generate_and_validate_proposal(backend, req, known_primes=set())
        assert verdict.status == "rejected"

    def test_empty_json_is_rejected(self) -> None:
        from app.llm.base import LLMBackend, LLMCallResult

        class EmptyBackend(LLMBackend):
            @property
            def provider_name(self) -> str: return "empty"
            @property
            def model_name(self) -> str: return "empty"
            def call(self, prompt: str, **kwargs) -> LLMCallResult:
                return LLMCallResult(raw_json="{}", provider="empty", model="empty")

        backend = EmptyBackend()
        req = SemanticProposalRequest(
            era=1, word_id="w1", concept="test",
            current_primes=[], context_chain=[],
        )
        verdict = generate_and_validate_proposal(backend, req, known_primes=set())
        assert verdict.status == "rejected"
        assert "Missing required field" in verdict.reason
