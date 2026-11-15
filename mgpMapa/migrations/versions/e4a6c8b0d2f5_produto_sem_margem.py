"""Produtos sem margem (vendem-se ao preço do catálogo)

Revision ID: e4a6c8b0d2f5
Revises: d1f3b5a7c9e2
"""
from alembic import op
import sqlalchemy as sa

revision = 'e4a6c8b0d2f5'
down_revision = 'd1f3b5a7c9e2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('produtos', sa.Column('sem_margem', sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column('produtos', 'sem_margem')
