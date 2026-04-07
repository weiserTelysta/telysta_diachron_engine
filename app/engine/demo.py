"""CSG pipeline demo helpers — shared by CLI (main.py) and Streamlit.

Extracted from the former ``main.demo_csg_pipeline()`` so both entry
points use the same logic without duplication.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import app.core.console as console
from app.core.config import configs
from app.core.logging import get_logger
from app.core.settings import global_settings
from app.domain.language.branch import BranchConfig, BranchLanguage
from app.domain.syntax.csg import CSGEdge, CSGNode, ControlledSemanticGraph
from app.domain.syntax.pipeline import CSGPipeline, GenerationResult
from app.domain.syntax.semantic_graph import SemanticGraph
from app.domain.syntax.typology import TypologyMatrix

if TYPE_CHECKING:
    from app.engine.session import RunResult

logger = get_logger(__name__)

# ------------------------------------------------------------------
# Pre-built CSG examples
# ------------------------------------------------------------------

DEMO_CSGS: dict[str, dict] = {
    "I SEE YOU (PAST)": {
        "nodes": [
            {"id": "subj", "prime_id": "I", "attributes": {"person": "1", "number": "sg"}},
            {"id": "pred", "prime_id": "SEE", "attributes": {"tense": "PAST"}},
            {"id": "obj", "prime_id": "YOU"},
        ],
        "edges": [
            {"from_id": "subj", "to_id": "pred", "relation": "agent"},
            {"from_id": "pred", "to_id": "obj", "relation": "patient"},
        ],
    },
    "YOU KNOW SOMETHING": {
        "nodes": [
            {"id": "subj", "prime_id": "YOU", "attributes": {"person": "2", "number": "sg"}},
            {"id": "pred", "prime_id": "KNOW", "attributes": {"tense": "PRES"}},
            {"id": "obj", "prime_id": "SOMETHING"},
        ],
        "edges": [
            {"from_id": "subj", "to_id": "pred", "relation": "agent"},
            {"from_id": "pred", "to_id": "obj", "relation": "patient"},
        ],
    },
    "I WANT GOOD": {
        "nodes": [
            {"id": "subj", "prime_id": "I", "attributes": {"person": "1", "number": "sg"}},
            {"id": "pred", "prime_id": "WANT", "attributes": {"tense": "PRES"}},
            {"id": "obj", "prime_id": "GOOD"},
        ],
        "edges": [
            {"from_id": "subj", "to_id": "pred", "relation": "agent"},
            {"from_id": "pred", "to_id": "obj", "relation": "theme"},
        ],
    },
}


def build_csg(name: str) -> ControlledSemanticGraph:
    """Build a ``ControlledSemanticGraph`` from a named preset."""
    spec = DEMO_CSGS[name]
    csg = ControlledSemanticGraph()
    for n in spec["nodes"]:
        csg.add_node(CSGNode(id=n["id"], prime_id=n["prime_id"],
                             attributes=n.get("attributes", {})))
    for e in spec["edges"]:
        csg.add_edge(CSGEdge(from_id=e["from_id"], to_id=e["to_id"],
                             relation=e["relation"]))
    return csg


def load_prime_graph() -> SemanticGraph:
    return SemanticGraph.from_json(configs.DATA_DIR / "semantic_primes" / "primes.json")


def make_default_typology() -> TypologyMatrix:
    return TypologyMatrix(
        word_order="SVO",
        tense_system="inflectional",
        morph_type="agglutinative",
        case_system="nominative_accusative",
        agreement_features=["person", "number"],
        morpheme_table={
            "ACC": "o", "PAST": "et", "PRES": "a",
            "1SG": "m", "3SG": "s",
        },
    )


# ------------------------------------------------------------------
# Cross-era comparison (used by both CLI and Streamlit CSG tab)
# ------------------------------------------------------------------

def compare_eras_for_csg(
    csg: ControlledSemanticGraph,
    era0_hot: object,
    final_hot: object,
    registry: object,
    inventory: object,
    typology: TypologyMatrix | None = None,
) -> list[GenerationResult]:
    """Run the CSG pipeline for Era 0 and the final era, return both results."""
    prime_graph = load_prime_graph()
    typ = typology or make_default_typology()
    pipeline = CSGPipeline(prime_graph, typ, registry, inventory)
    return pipeline.compare_eras(
        csg,
        era_snapshots={
            0: (era0_hot, typ),
            final_hot.current_era: (final_hot, typ),
        },
    )


# ------------------------------------------------------------------
# Branch comparison (used by both CLI and Streamlit branch tab)
# ------------------------------------------------------------------

def run_branch_comparison(
    era0_hot: object,
    registry: object,
    inventory: object,
    csg: ControlledSemanticGraph,
    branch_a_name: str = "北方方言 (SVO)",
    branch_b_name: str = "南方方言 (SOV)",
    branch_eras: int = 5,
    seed: int = 888,
) -> tuple[GenerationResult, GenerationResult]:
    prime_graph = load_prime_graph()
    svo_typology = make_default_typology()
    sov_typology = svo_typology.clone_with(word_order="SOV")

    branch_a = BranchLanguage(
        BranchConfig(name=branch_a_name, fork_era=0),
        era0_hot, svo_typology, prime_graph, registry, inventory,
    )
    branch_b = BranchLanguage(
        BranchConfig(name=branch_b_name, fork_era=0,
                     typology_override=sov_typology),
        era0_hot, svo_typology, prime_graph, registry, inventory,
    )

    rng_a = random.Random(seed + 100)
    rng_b = random.Random(seed + 200)
    for _ in range(branch_eras):
        branch_a.evolve_one_era(rng=rng_a)
        branch_b.evolve_one_era(rng=rng_b)

    return branch_a.generate(csg), branch_b.generate(csg)


# ------------------------------------------------------------------
# CLI demo (called from main.py)
# ------------------------------------------------------------------

def run_cli_demo(result: RunResult) -> None:
    """Print the full CLI demo output (samples, proto-sentences, CSG, branches)."""
    from app.domain.syntax.assembler import SentenceAssembler

    # Sample words
    sample = list(result.final_hot.all_alive())[:5]
    console.demo_line("演化后词库样本（前 5 词）：")
    for e in sample:
        history = " → ".join(e.ipa_history + [e.ipa_current]) if e.ipa_history else e.ipa_current
        console.demo_line(f"  [{e.concept}] {history}")

    # Proto-sentences
    alive = list(result.final_hot.all_alive())
    assembler = SentenceAssembler(alive)
    rng = random.Random(result.seed)
    proto_sentences = assembler.assemble(n=10, rng=rng)
    console.demo_line("Proto-sentence assembly（10 句，纯 IPA 拼接，无形态变化）：")
    for i, s in enumerate(proto_sentences, 1):
        console.demo_line(f"  {i:2d}. /{s}/")

    console.demo_line(f"DAG 词源图: {result.final_hot.dag}")

    # CSG cross-era comparison
    csg = build_csg("I SEE YOU (PAST)")
    inv = result.engine.inventory
    reg = result.engine.registry

    console.demo_line("\n" + "=" * 60)
    console.demo_line("[Phase 3] CSG 跨时代同句对比")
    console.demo_line("=" * 60)
    console.demo_line("  CSG: I-SEE-YOU / tense=PAST / agent=1sg")

    era_results = compare_eras_for_csg(
        csg, result.era0_hot, result.final_hot, reg, inv,
    )
    for r in era_results:
        lexmap_str = " | ".join(
            f"{k}={v or '?'}"
            for k, v in r.lexmap_used.items()
            if k in ("I", "SEE", "YOU")
        )
        console.demo_line(f"  {r}   [{lexmap_str}]")
        if r.warnings:
            for w in r.warnings:
                logger.warning("    %s", w)

    # Branch comparison
    console.demo_line("\n" + "=" * 60)
    console.demo_line("[Phase 3] 分支语言独立演化对比")
    console.demo_line("=" * 60)

    result_a, result_b = run_branch_comparison(
        result.era0_hot, reg, inv, csg, seed=result.seed,
    )
    console.demo_line(f"  北方方言 (Era {result_a.era}): /{result_a.sentence}/")
    console.demo_line(f"  南方方言 (Era {result_b.era}): /{result_b.sentence}/")
    console.demo_line("=" * 60)
