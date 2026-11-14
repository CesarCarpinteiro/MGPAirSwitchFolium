"""Observação em cada linha do orçamento

Revision ID: c9e1a3b5d7f0
Revises: b8d0f2a4c6e9
"""
from alembic import op
import sqlalchemy as sa

revision = 'c9e1a3b5d7f0'
down_revision = 'b8d0f2a4c6e9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('orcamento_linhas', sa.Column('nota', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('orcamento_linhas', 'nota')
