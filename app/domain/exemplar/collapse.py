from __future__ import annotations

import numpy as np

from app.domain.exemplar.matrix import COL_WEIGHT, COL_WORD_IDX, ExemplarMatrix


def batch_collapse_exemplars(em: ExemplarMatrix, keep_top_k: int = 5) -> ExemplarMatrix:
    """Collapse each word's exemplar pool to the top-k by weight.

    Fully vectorized — no Python loops over words or exemplars.

    Algorithm:
      1. Sort the entire matrix by (word_idx ASC, weight DESC) using a
         stable argsort on a combined sort key.
      2. Use np.unique on word_idx column to find group boundaries.
      3. For each group, retain only the first keep_top_k rows.
      4. Re-normalize weights within each group to sum to 1.0.
    """
    if len(em.matrix) == 0:
        return em

    word_col = em.matrix[:, COL_WORD_IDX]
    weight_col = em.matrix[:, COL_WEIGHT]

    sort_key = word_col * 1e9 + (1.0 - weight_col)
    sorted_indices = np.argsort(sort_key, kind="stable")
    sorted_matrix = em.matrix[sorted_indices]

    sorted_word_col = sorted_matrix[:, COL_WORD_IDX]

    _, group_starts, group_counts = np.unique(
        sorted_word_col, return_index=True, return_counts=True
    )

    keep_mask = np.zeros(len(sorted_matrix), dtype=bool)
    for start, count in zip(group_starts, group_counts):
        keep_count = min(int(count), keep_top_k)
        keep_mask[start: start + keep_count] = True

    collapsed = sorted_matrix[keep_mask].copy()

    collapsed_word_col = collapsed[:, COL_WORD_IDX]
    _, renorm_starts, renorm_counts = np.unique(
        collapsed_word_col, return_index=True, return_counts=True
    )
    for start, count in zip(renorm_starts, renorm_counts):
        group_weights = collapsed[start: start + count, COL_WEIGHT]
        total = group_weights.sum()
        if total > 0:
            collapsed[start: start + count, COL_WEIGHT] = group_weights / total

    result = ExemplarMatrix(
        matrix=collapsed,
        word_index=em.word_index,
        feature_names=em.feature_names,
    )
    return result


def sync_exemplars_to_entities(em: ExemplarMatrix, entities: list) -> None:
    """Write collapsed exemplar weights back into LexicalEntity.ipa_exemplars.

    Reads only COL_WORD_IDX, COL_FEATURE_BITS, COL_WEIGHT — no per-entity loop
    beyond the final assignment. The IPA form reconstruction from feature_bits
    is intentionally left as a future stub (requires inverse feature→symbol lookup).
    """
    if len(em.matrix) == 0:
        return

    word_col = em.matrix[:, COL_WORD_IDX].astype(int)
    weight_col = em.matrix[:, COL_WEIGHT]

    unique_words = np.unique(word_col)
    for w_idx in unique_words:
        if w_idx >= len(entities):
            continue
        mask = word_col == w_idx
        weights = weight_col[mask]
        entity = entities[int(w_idx)]

        if len(entity.ipa_exemplars) == len(weights):
            for i, ex in enumerate(entity.ipa_exemplars):
                ex["weight"] = float(weights[i])
