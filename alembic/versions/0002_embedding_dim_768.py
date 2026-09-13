"""Widen pgvector columns for BAAI/bge-base-en-v1.5 (768-d).

Revision ID: 0002_emb_768
Revises: 0001_initial
Create Date: 2026-09-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0002_emb_768"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_DIM = 768
OLD_DIM = 384


def _recreate_embedding(table: str, dim: int) -> None:
    op.drop_index(f"ix_{table}_embedding", table_name=table)
    op.drop_column(table, "embedding")
    op.add_column(table, sa.Column("embedding", Vector(dim), nullable=False))
    op.execute(
        f"CREATE INDEX ix_{table}_embedding ON {table} "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def upgrade() -> None:
    _recreate_embedding("policy_chunks", NEW_DIM)
    _recreate_embedding("fraud_case_chunks", NEW_DIM)


def downgrade() -> None:
    _recreate_embedding("policy_chunks", OLD_DIM)
    _recreate_embedding("fraud_case_chunks", OLD_DIM)
