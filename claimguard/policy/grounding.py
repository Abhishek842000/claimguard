"""Programmatic citation check. Do not trust the model to cite real chunks."""

from __future__ import annotations

from claimguard.schemas.policy import CitedClause, PolicyDetermination


def filter_grounded_clauses(
    determination: PolicyDetermination,
    retrieved_ids: set[str],
) -> PolicyDetermination:
    """Drop cited clauses whose ids were not in the retrieved set."""

    supporting = _keep(determination.supporting_clauses, retrieved_ids)
    exclusions = _keep(determination.exclusions_applied, retrieved_ids)
    dropped = (len(determination.supporting_clauses) - len(supporting)) + (
        len(determination.exclusions_applied) - len(exclusions)
    )
    return determination.model_copy(
        update={
            "supporting_clauses": supporting,
            "exclusions_applied": exclusions,
            "retrieved_chunk_ids": sorted(retrieved_ids),
            "grounded": dropped == 0,
        }
    )


def _keep(clauses: list[CitedClause], retrieved_ids: set[str]) -> list[CitedClause]:
    kept: list[CitedClause] = []
    for clause in clauses:
        if clause.clause_id in retrieved_ids or clause.document_id in retrieved_ids:
            kept.append(clause)
            continue
        # BM25 ids look like "{document_id}:{chunk_index}".
        if any(
            retrieved.startswith(f"{clause.document_id}:") or retrieved.startswith(f"{clause.clause_id}:")
            for retrieved in retrieved_ids
        ):
            kept.append(clause)
    return kept
